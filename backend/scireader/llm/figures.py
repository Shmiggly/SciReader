"""Figure narration at first mention, panel-aware.

"Fig. 3b" / "Figure 3(b)" → describe only panel b (and read only panel b's part of the caption);
"Fig. 3" → the whole figure; "Fig. 3a–c" → panels a to c together. Each target is described once, at
its first mention; figures never mentioned are read at their layout position. Supplementary figures
("Fig. S2") are ignored. Descriptions come from the reader model (vision) on a crop of the PDF page.
"""

from __future__ import annotations

import io
import re
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

from ..store.docs import DocStore
from . import ollama

MENTION = re.compile(
    r"\b(Fig(?:ure)?s?\.?)\s*(S?\d+)\s*(?:\(\s*([a-h](?:\s*[-–,]\s*[a-h])*)\s*\)|([a-h](?:\s*[-–]\s*[a-h])?)(?:[ivx]+(?:\s*[-–]\s*[ivx]+)?)?)?(?![A-Za-z0-9])"
)
PANEL_START = re.compile(r"(?:(?<=^)|(?<=[.;:]\s)|(?<=\)\s))\(?([a-h])\)?\s+(?=[A-Z(])")

DESCRIBE_SYSTEM = (
    "You describe figures from scientific papers for a listener who cannot see them. Be concrete and faithful "
    "to what is visible: say the plot type, what the axes show (with units), what the curves, markers, colors "
    "or images show, and the key trends or comparisons. Do not speculate beyond the image and caption, and do "
    "not start with 'This figure'. Plain spoken English, no markdown, no lists."
)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="figures")
_status: dict[str, dict] = {}
_lock = threading.Lock()


def expand_panels(spec: str | None) -> list[str]:
    if not spec:
        return []
    spec = spec.replace(" ", "")
    out: list[str] = []
    for part in spec.split(","):
        m = re.fullmatch(r"([a-h])[-–]([a-h])", part)
        if m:
            out.extend(chr(c) for c in range(ord(m.group(1)), ord(m.group(2)) + 1))
        elif re.fullmatch(r"[a-h]", part):
            out.append(part)
    return sorted(set(out))


def target_key(number: str, panels: list[str]) -> str:
    return f"{number}{''.join(panels)}" if panels else number


def find_mentions(doc: dict) -> list[dict]:
    """All figure mentions in readable text, in reading order, with a first-mention flag per target."""
    figs = {f["number"]: f for f in doc["figures"] if f.get("number") and f.get("kind") == "figure"}
    seen: set[str] = set()
    out = []
    for b in doc["blocks"]:
        if b["type"] not in ("paragraph", "abstract", "list_item") or b.get("skip_reason"):
            continue
        for s in b["sentences"]:
            for m in MENTION.finditer(s["text"]):
                number = m.group(2)
                if number.startswith("S") or number not in figs:
                    continue
                panels = expand_panels(m.group(3) or m.group(4))
                key = target_key(number, panels)
                first = key not in seen
                seen.add(key)
                out.append({"sentence_id": s["id"], "span": [m.start(), m.end()], "key": key, "number": number,
                            "panels": panels, "figure_id": figs[number]["id"], "first": first})
    return out


def caption_text(doc: dict, fig: dict) -> str:
    cb = next((b for b in doc["blocks"] if b["id"] == fig.get("caption_block_id")), None)
    return re.sub(r"\s+", " ", cb["text"]).strip() if cb else ""


def caption_part(caption: str, panels: list[str]) -> str:
    """The caption's title + the parts for the requested panels (or the first sentence if they can't be split)."""
    body = re.sub(r"^\s*Fig(?:ure)?\.?\s*\d+[.:]?\s*", "", caption)
    starts = [(m.start(), m.group(1)) for m in PANEL_START.finditer(body)]
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


def describe(store: DocStore, doc_id: str, doc: dict, key: str, detail: bool = False) -> dict:
    res = store.read_json(doc_id, "figures.json") or {}
    cache_key = key + (":detail" if detail else "")
    if cache_key in res and res[cache_key].get("description"):
        return res[cache_key]
    number = re.match(r"\d+", key).group(0)
    panels = list(key[len(number):])
    fig = next(f for f in doc["figures"] if f.get("number") == number and f.get("kind") == "figure")
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
    cap = entry.get("caption_part") or ""
    desc = entry.get("description")
    parts = [f"{who}. {cap}".strip()]
    if desc:
        parts.append(f"AI description of {who}: {desc}")
    return " ".join(p if p.endswith(".") else p + "." for p in parts)


def status(doc_id: str) -> dict:
    with _lock:
        return dict(_status.get(doc_id, {}))


def start(store: DocStore, doc_id: str) -> dict:
    with _lock:
        st = _status.get(doc_id)
        if st and st.get("state") in ("queued", "running"):
            return dict(st)
        _status[doc_id] = {"state": "queued"}
    _executor.submit(_prepare_all, store, doc_id)
    return status(doc_id)


def _prepare_all(store: DocStore, doc_id: str) -> None:
    try:
        doc = store.document(doc_id)
        if doc is None or not ollama.available():
            with _lock:
                _status[doc_id] = {"state": "unavailable"}
            return
        keys = []
        for m in find_mentions(doc):
            if m["first"] and m["key"] not in keys:
                keys.append(m["key"])
        with _lock:
            _status[doc_id] = {"state": "running", "done": 0, "total": len(keys)}
        for i, k in enumerate(keys):
            describe(store, doc_id, doc, k)
            with _lock:
                _status[doc_id].update(done=i + 1)
        with _lock:
            _status[doc_id]["state"] = "done"
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        with _lock:
            _status[doc_id] = {"state": "error", "message": str(exc)}
