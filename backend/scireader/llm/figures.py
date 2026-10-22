"""Figure narration at mentions, panel-aware.

"Fig. 3b" / "Figure 3(b)" / "Fig. 3B" → describe only panel b (and read only panel b's part of the caption);
"Fig. 3" → the whole figure; "Fig. 3a–c" → panels a to c together. The reader decides when a target is
described (frontend store.ts: once, at the first mention playback reaches, by default); figures never
mentioned are read at their layout position. Supplementary figures ("Fig. S2") are ignored. Descriptions
come from the reader model (vision) on a crop of the PDF page, prepared in the background.
"""

from __future__ import annotations

import io
import re
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

from ..parsing.captions import caption_label
from ..store.docs import DocStore
from . import ollama

# A figure reference in running text, any case ("Fig. 3", "FIG. 3", IOP's "figure 4(a)"), also glued to the word
# before it by the text layer ("infigure 1"); a plural word may list several figures ("Figures 16 and 17",
# "Figs. 9–10", "figures 4(a), (c), and 5(a)").
_WORD = re.compile(r"(?:\b|(?<=\bin)|(?<=\bof)|(?<=\bsee)|(?<=\band)|(?<=\bto))(fig(?:ure)?(s?))\b\.?\s*(?=[Ss]?\d)", re.I)
_NUM = re.compile(r"([Ss]?)(\d{1,3})(?!\d)(?!\.\d)")
# Panels right after the number: "3b", "2A", "2a-c", "4ai-ii" (sub-panel numerals are ignored), then ", b" / " and b".
_ATTACHED = re.compile(r"([A-Za-z])(?:\s*[-–]\s*([A-Za-z]))?(?:[ivx]+(?:\s*[-–]\s*[ivx]+)?)?(?![A-Za-z0-9])")
_MORE_LETTER = re.compile(r"\s*(?:,\s*(?:and\b|&)?|and\b|&)\s*([A-Za-z])(?![A-Za-z0-9])")
# ...or in parentheses: "3(b)", "3 (a, b)", "4 (m-p)", then "-(e)" (a range) or ", (c)" / " and (c)".
_PAREN = re.compile(r"\s*\(\s*([A-Za-z](?:\s*(?:[-–,&]|,?\s*and\b)\s*[A-Za-z])*)\s*\)")
_MORE_PAREN = re.compile(r"\s*(?:([-–])|,\s*(?:and\b|&)?|and\b|&)\s*\(\s*([A-Za-z])\s*\)")
_MORE_FIG = re.compile(r"\s*(?:([-–])|,\s*(?:and\b|&)?|and\b|&)\s*(?=\d)")
_SUPPLEMENTARY = re.compile(r"(?:supplementa(?:ry|l)|extended\s+data|supporting)(?:\s+information)?\s*$", re.I)
PANEL_START = re.compile(r"(?:(?<=^)|(?<=[.;:]\s)|(?<=\)\s))(?:\(([A-Za-z])\)|([a-h])\)?)\s+(?=[A-Z(])")

DESCRIBE_SYSTEM = (
    "You describe figures from scientific papers for a listener who cannot see them. Be concrete and faithful "
    "to what is visible: say the plot type, what the axes show (with units), what the curves, markers, colors "
    "or images show, and the key trends or comparisons. Do not speculate beyond the image and caption, and do "
    "not start with 'This figure'. Plain spoken English, no markdown, no lists."
)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="figures")
_status: dict[str, dict] = {}
_wanted: dict[str, list[str]] = {}  # targets to describe next (the reader's position, a clicked mention)
_lock = threading.Lock()

KEY = re.compile(r"(\d{1,3})([a-z]*)")


def _letter_range(a: str, z: str) -> list[str]:
    if a.isupper() == z.isupper() and 0 < ord(z) - ord(a) <= 15:
        return [chr(c) for c in range(ord(a), ord(z) + 1)]
    return [a, z]


def _inner_letters(inner: str) -> list[str]:
    """Letters inside "(a, b)", "(a-c)", "(A and B)"."""
    tokens = re.findall(r"[A-Za-z]|[-–]", re.sub(r"\band\b|&", ",", inner))
    out: list[str] = []
    for i, t in enumerate(tokens):
        if t in "-–":
            if out and i + 1 < len(tokens) and tokens[i + 1] not in "-–":
                out.extend(_letter_range(out.pop(), tokens[i + 1])[:-1])
        else:
            out.append(t)
    return out


def _panels_at(text: str, p: int) -> tuple[list[str], int]:
    """Panel letters right after a figure number at text[p], and where they end."""
    m = _ATTACHED.match(text, p)
    if m:
        letters = _letter_range(m.group(1), m.group(2)) if m.group(2) else [m.group(1)]
        end = m.end()
        while (n := _MORE_LETTER.match(text, end)) and n.group(1).isupper() == m.group(1).isupper():
            letters.append(n.group(1))
            end = n.end()
        return letters, end
    m = _PAREN.match(text, p)
    if m:
        letters = _inner_letters(m.group(1))
        end = m.end()
        while n := _MORE_PAREN.match(text, end):
            letters.extend(_letter_range(letters[-1], n.group(2))[1:] if n.group(1) and letters else [n.group(2)])
            end = n.end()
        return letters, end
    return [], p


def parse_refs(text: str) -> list[tuple[int, int, str, list[str]]]:
    """(start, end, figure number, panel letters) for each main-text figure reference in a sentence, in order."""
    out: list[tuple[int, int, str, list[str]]] = []
    for w in _WORD.finditer(text):
        if _SUPPLEMENTARY.search(text[: w.start()]):
            continue
        start, p = w.start(), w.end()
        while n := _NUM.match(text, p):
            letters, end = _panels_at(text, n.end())
            supplementary = bool(n.group(1))
            if not supplementary:
                out.append((start, end, n.group(2), letters))
            more = _MORE_FIG.match(text, end) if w.group(2) else None  # only a plural word lists several figures
            if not more:
                break
            if more.group(1):  # "Figures 9-10": every figure in the range
                last = _NUM.match(text, more.end())
                if not last:
                    break
                lo, hi = int(n.group(2)), int(last.group(2))
                if not supplementary and not last.group(1) and lo < hi <= lo + 6:
                    out.extend((n.start(), last.end(), str(k), []) for k in range(lo + 1, hi))
                    out.append((last.start(), last.end(), last.group(2), []))
                end = last.end()
                more = _MORE_FIG.match(text, end)
                if not more or more.group(1):
                    break
            start, p = more.end(), more.end()
    return out


def target_key(number: str, panels: list[str]) -> str:
    return f"{number}{''.join(panels)}" if panels else number


def split_key(key: str) -> tuple[str, list[str]] | None:
    m = KEY.fullmatch(key)
    return (m.group(1), list(m.group(2))) if m else None


def span_rects(entry: dict | None, a: int, z: int) -> list[list[float]]:
    """Boxes on the page for characters [a, z) of a sentence, from its word boxes (speech.json), one per line."""
    out: list[list[float]] = []
    for w0, w1, rects in (entry or {}).get("words", []):
        if w0 >= z or w1 <= a:
            continue
        for r in rects:
            last = out[-1] if out else None
            if last and last[0] == r[0] and abs(last[2] - r[2]) < 3 and abs(last[4] - r[4]) < 3 and r[1] <= last[3] + 8:
                last[1], last[2], last[3], last[4] = min(last[1], r[1]), min(last[2], r[2]), max(last[3], r[3]), max(last[4], r[4])
            else:
                out.append(list(r))
    return out


def find_mentions(doc: dict, speech: dict | None = None) -> list[dict]:
    """All figure mentions in readable text, in reading order, with a first-mention flag per target and, given the
    speech index, the mention's boxes on the page (for clicking it)."""
    figs: dict[str, dict] = {}
    for f in doc["figures"]:
        if f.get("number") and f.get("kind") == "figure":
            figs.setdefault(f["number"], f)  # the first one (a later copy is a pasted duplicate, as in MDPI)
    seen: set[str] = set()
    out = []
    for b in doc["blocks"]:
        if b["type"] not in ("paragraph", "abstract", "list_item") or b.get("skip_reason"):
            continue
        for s in b["sentences"]:
            for a, z, number, letters in parse_refs(s["text"]):
                if number not in figs:
                    continue
                panels = sorted({c.lower() for c in letters})
                key = target_key(number, panels)
                first = key not in seen
                seen.add(key)
                m = {"sentence_id": s["id"], "span": [a, z], "key": key, "number": number, "panels": panels,
                     "figure_id": figs[number]["id"], "first": first}
                if speech is not None:
                    m["rects"] = span_rects(speech.get(s["id"]), a, z)
                out.append(m)
    return out


def caption_text(doc: dict, fig: dict) -> str:
    """The figure's caption from its label on (without running headers or printout lines before it)."""
    cb = next((b for b in doc["blocks"] if b["id"] == fig.get("caption_block_id")), None)
    if not cb:
        return ""
    text = re.sub(r"\s+", " ", cb["text"]).strip()
    lab = caption_label(text)
    return text[lab[2]:] if lab else text


def caption_part(caption: str, panels: list[str]) -> str:
    """The caption's title + the parts for the requested panels (or the first sentence if they can't be split)."""
    body = re.sub(r"^\s*Fig(?:ure)?\.?\s*\d+[.:]?\s*", "", caption, flags=re.I)
    starts = [(m.start(), (m.group(1) or m.group(2)).lower()) for m in PANEL_START.finditer(body)]
    letters = [l for _, l in starts]
    title = body[: starts[0][0]].strip() if starts else ""
    if not panels:
        return body
    if starts and all(p in letters for p in panels):
        parts = []
        for i, (pos, letter) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(body)
            if letter in panels:
                parts.append(body[pos:end].strip())
        return (title + " " + " ".join(parts)).strip()
    first = re.split(r"(?<=\.)\s+", body, maxsplit=1)[0]
    return first


def crop_png(pdf_path: str, page: int, bbox: list[float], scale: float = 2.0) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        pg = pdf[page]
        w, h = pg.get_size()
        x0, y0, x1, y1 = bbox
        pad = 4
        crop = (max(0, x0 - pad), max(0, h - y1 - pad), max(0, w - x1 - pad), max(0, y0 - pad))
        img = pg.render(scale=scale, crop=crop).to_pil()
        if img.width > 1400:
            img = img.resize((1400, int(img.height * 1400 / img.width)))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        pdf.close()


def describe_messages(label: str, caption: str, panels: list[str], detail: bool = False) -> list[dict]:
    which = f"only panel {', '.join(panels)} of {label}" if panels else label
    words = "about 150 words, with more detail on values and trends" if detail else "about 70 words"
    user = (f"Here is {label} with its caption: \"{caption}\"\n"
            f"Describe {which} in {words}." + (" Focus on that panel and ignore the others." if panels else ""))
    return [{"role": "system", "content": DESCRIBE_SYSTEM}, {"role": "user", "content": user}]


def figure_for(doc: dict, number: str) -> dict | None:
    return next((f for f in doc["figures"] if f.get("number") == number and f.get("kind") == "figure"), None)


def cached(descriptions: dict, key: str, fig: dict | None) -> dict | None:
    """A ready description of a target, if it was made from this figure (a rebuild can renumber figures)."""
    e = descriptions.get(key)
    if not e or not e.get("description") or fig is None or e.get("figure_id", fig["id"]) != fig["id"]:
        return None
    return e


def target(doc: dict, key: str, descriptions: dict) -> dict | None:
    """A figure target for the popup and the caption-only reading: label, panels, caption part and the AI
    description if it is ready."""
    parts = split_key(key)
    fig = figure_for(doc, parts[0]) if parts else None
    if fig is None:
        return None
    number, panels = parts
    entry = cached(descriptions, key, fig) or {}
    return {"key": key, "figure_id": fig["id"], "label": f"Figure {number}", "panels": panels,
            "caption_part": entry.get("caption_part") or caption_part(caption_text(doc, fig), panels),
            "description": entry.get("description")}


def describe(store: DocStore, doc_id: str, doc: dict, key: str, detail: bool = False) -> dict:
    res = store.read_json(doc_id, "figures.json") or {}
    cache_key = key + (":detail" if detail else "")
    number, panels = split_key(key)
    fig = figure_for(doc, number)
    if fig is None:
        raise KeyError(f"No figure {number}")
    if entry := cached(res, cache_key, fig):
        return entry
    caption = caption_text(doc, fig)
    png = crop_png(str(store.pdf_path(doc_id)), fig["page"], fig["bbox"])
    label = f"Figure {number}"
    model = ollama.models_for_jobs()["reader"]
    text = ollama.chat(model, describe_messages(label, caption, panels, detail), images=[png], num_predict=400,
                       num_ctx=8192)
    entry = {"key": key, "figure_id": fig["id"], "panels": panels, "label": label,
             "caption_part": caption_part(caption, panels), "description": text.strip(), "model": model,
             "detail": detail}
    with _lock:
        res = store.read_json(doc_id, "figures.json") or {}
        res[cache_key] = entry
        store.write_json(doc_id, "figures.json", res)
    return entry


def spoken_for(entry: dict) -> str:
    panels = entry.get("panels") or []
    who = f"{entry['label']}, panel{'s' if len(panels) > 1 else ''} {' and '.join(panels)}" if panels else entry["label"]
    desc = entry.get("description")
    # With a description, go straight to it after the label (user's listening check); the caption is the fallback.
    parts = [f"{who}.", f"AI description: {desc}"] if desc else [f"{who}. {entry.get('caption_part') or ''}".strip()]
    return " ".join(p if p.endswith(".") else p + "." for p in parts)


def status(doc_id: str) -> dict:
    with _lock:
        return dict(_status.get(doc_id, {}))


def start(store: DocStore, doc_id: str, first: list[str] | None = None) -> dict:
    """Describe every mentioned target in the background, in reading order; `first` (where the reader is, or a
    clicked mention) goes to the front of the queue, also while the job runs."""
    with _lock:
        if first:
            _wanted[doc_id] = list(dict.fromkeys(first + _wanted.get(doc_id, [])))
        st = _status.get(doc_id)
        if st and st.get("state") in ("queued", "running"):
            return dict(st)
        _status[doc_id] = {"state": "queued"}
    _executor.submit(_prepare_all, store, doc_id)
    return status(doc_id)


def next_key(keys: list[str], done: set[str], wanted: list[str]) -> str | None:
    """The next target to describe: the first wanted one not done yet, else the next in reading order."""
    return next((k for k in wanted if k in keys and k not in done), None) or next((k for k in keys if k not in done), None)


def _prepare_all(store: DocStore, doc_id: str) -> None:
    try:
        doc = store.document(doc_id)
        if doc is None or not ollama.available():
            with _lock:
                _status[doc_id] = {"state": "unavailable"}
            return
        keys = list(dict.fromkeys(m["key"] for m in find_mentions(doc)))
        res = store.read_json(doc_id, "figures.json") or {}
        done = {k for k in keys if cached(res, k, figure_for(doc, split_key(k)[0]))}
        failed = 0
        with _lock:
            _status[doc_id] = {"state": "running", "done": len(done), "total": len(keys)}
        while True:
            with _lock:
                k = next_key(keys, done, _wanted.get(doc_id, []))
            if k is None:
                break
            try:
                describe(store, doc_id, doc, k)
            except ollama.LLMUnavailable:
                raise
            except Exception:  # noqa: BLE001 - one bad figure doesn't stop the others
                traceback.print_exc()
                failed += 1
            done.add(k)
            with _lock:
                _status[doc_id].update(done=len(done))
        with _lock:
            _status[doc_id].update(state="done", failed=failed)
            _wanted.pop(doc_id, None)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        with _lock:
            _status[doc_id] = {"state": "error", "message": str(exc)}
