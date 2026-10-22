"""Equations mentioned in the text, and AI descriptions of equations.

A mention ("Eq. (3)", IOP's "equation (9) and (10)", "Eq. 1 and 2") opens its equation in a popup over the reading
area, like a figure mention. The AI description, made on request by the reader model, says what an equation
expresses and what its symbols stand for, from the LaTeX that is narrated and the text around the equation (the
"where R_j is the jet radius" after it). It is labeled as AI wherever it is shown or read, and cached per equation
with the LaTeX it was made from.
"""

from __future__ import annotations

import re
import threading

from ..parsing.latex import equation_intro
from ..store.docs import DocStore
from . import ollama
from .figures import crop_png, span_rects

# The word, then a number right after it: "Eq. 5", "Eqs. (4)", "Eqn. 2", "Equation(6)", "equations (13)". Not
# supplementary equations ("Eq. S3"), and not words that end in "equation" ("inequation").
_WORD = re.compile(r"\b(?:eqs?|eqns?|equations?)\b\.?\s*(?=\(?\s*\d)", re.I)
_PAREN = re.compile(r"\(\s*(\d{1,3}(?:[a-z](?![a-z]))?)\s*\)")
_BARE = re.compile(r"(\d{1,3}(?:[a-z](?![a-z]))?)(?![\d.]?\d)")
# More numbers in the same style: "(9) and (10)", "(13), (14)", "(15), and (16)", "(3)–(5)", "1 and 2".
_MORE = re.compile(r"\s*(?:,\s*(?:and\b|&)?|and\b|&|[-–])\s*")

DESCRIBE_SYSTEM = (
    "You explain an equation from a scientific paper to a listener who cannot see it. In about 80 words of plain "
    "spoken English, say what the equation expresses or computes and what its main symbols stand for, using what "
    "the paper's text around it says; do not invent a meaning for a symbol the text doesn't define. Do not read the "
    "equation out symbol by symbol, do not start with 'This equation', and use no LaTeX, markdown or lists."
)

_lock = threading.Lock()


def parse_refs(text: str) -> list[tuple[int, int, str]]:
    """(start, end, equation number) for each equation reference in a sentence, in order. A list after the word
    gives one reference per number ("equation (9) and (10)": "equation (9)", then "(10)")."""
    out: list[tuple[int, int, str]] = []
    for w in _WORD.finditer(text):
        start, p = w.start(), w.end()
        num = _PAREN if text[p] == "(" else _BARE  # later numbers must be written the same way
        while m := num.match(text, p):
            out.append((start, m.end(), m.group(1).lower()))
            more = _MORE.match(text, m.end())
            if not more or not num.match(text, more.end()):
                break
            start = p = more.end()
    return out


def labels(number: str | None) -> list[str]:
    """The numbers an equation answers to: "6"; a stacked "1a,b" also to "1a", "1b" and "1"."""
    if not number:
        return []
    m = re.fullmatch(r"(\d+)([a-z](?:,[a-z])*)", number)
    return [number, *(m.group(1) + x for x in m.group(2).split(",")), m.group(1)] if m else [number]


def resolve(equations: list[dict], number: str) -> dict | None:
    """The equation block a reference points to: the same number, else one it answers to (the first, in order)."""
    return next((b for b in equations if b["eq_number"] == number), None) or next(
        (b for b in equations if number in labels(b["eq_number"])), None)


def numbered(doc: dict) -> list[dict]:
    return [b for b in doc["blocks"] if b["type"] == "equation" and b.get("eq_number") and b.get("skip_reason") != "junk"]


def find_mentions(doc: dict, speech: dict | None = None) -> list[dict]:
    """Every reference to a numbered equation in readable text and captions, in reading order, with its boxes on the
    page given the speech index (for clicking it)."""
    eqs = numbered(doc)
    out = []
    for b in doc["blocks"]:
        if b["type"] not in ("paragraph", "abstract", "list_item", "caption") or b.get("skip_reason"):
            continue
        for s in b["sentences"]:
            for a, z, number in parse_refs(s["text"]):
                eq = resolve(eqs, number)
                if eq is None:
                    continue
                m = {"sentence_id": s["id"], "span": [a, z], "number": number, "block_id": eq["id"]}
                if speech is not None:
                    m["rects"] = span_rects(speech.get(s["id"]), a, z)
                out.append(m)
    return out


def _text_near(blocks: list[dict], i: int, step: int) -> str:
    """Up to two sentences of running text right before (step -1) or after (step 1) block i, past other equations,
    captions and page furniture, but not across a heading."""
    j = i + step
    while 0 <= j < len(blocks) and abs(j - i) <= 8:
        b = blocks[j]
        if b["type"] == "heading":
            break
        if b["type"] in ("paragraph", "abstract", "list_item") and b.get("sentences") and not b.get("skip_reason"):
            texts = [s["text"] for s in b["sentences"]]
            text = " ".join(texts[-2:] if step < 0 else texts[:2])
            return text[-600:] if step < 0 else text[:600]
        j += step
    return ""


def label_for(block: dict) -> str:
    return equation_intro(block.get("eq_number"), block.get("eq_label"))


def latex_for(block: dict, result: dict | None) -> str:
    """The LaTeX that is narrated: the one chosen after the second reading of the page, else the parser's."""
    return ((result or {}).get("latex") if result and "source" in result else block.get("latex")) or ""


def describe_messages(label: str, latex: str, before: str, after: str) -> list[dict]:
    parts = [f"{label} of the paper."]
    if before:
        parts.append(f'Text just before it: "{before}"')
    parts.append(f"The equation in LaTeX: {latex}" if latex.strip() else "The equation is in the image.")
    if after:
        parts.append(f'Text just after it: "{after}"')
    parts.append(f"Explain {label} in about 80 words.")
    return [{"role": "system", "content": DESCRIBE_SYSTEM}, {"role": "user", "content": "\n".join(parts)}]


def tidy(text: str) -> str:
    """One paragraph that starts "It …" rather than "This equation …" (it is read after "Equation 9. AI description:";
    the model starts that way despite the prompt)."""
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^(?:This|The) equation(?=\s)", "It", text)


def cached(store: DocStore, doc_id: str, block: dict, result: dict | None) -> dict | None:
    """A ready description of the equation, if it was made from the LaTeX narrated now."""
    e = (store.read_json(doc_id, "eq_descriptions.json") or {}).get(block["id"])
    return e if e and e.get("description") and e.get("latex") == latex_for(block, result) else None


def describe(store: DocStore, doc_id: str, doc: dict, block: dict) -> dict:
    """The equation's AI description, made now by the reader model if there isn't one for its current LaTeX."""
    result = (store.read_json(doc_id, "equations.json") or {}).get(block["id"])
    if entry := cached(store, doc_id, block, result):
        return entry
    blocks = doc["blocks"]
    i = next(k for k, b in enumerate(blocks) if b["id"] == block["id"])
    latex = latex_for(block, result)
    images = None if latex.strip() else [crop_png(str(store.pdf_path(doc_id)), block["page"], block["bbox"])]
    model = ollama.models_for_jobs()["reader"]
    msgs = describe_messages(label_for(block), latex, _text_near(blocks, i, -1), _text_near(blocks, i, 1))
    text = ollama.chat(model, msgs, images=images, num_predict=300, num_ctx=4096)
    entry = {"description": tidy(text), "latex": latex, "model": model}
    with _lock:
        res = store.read_json(doc_id, "eq_descriptions.json") or {}
        res[block["id"]] = entry
        store.write_json(doc_id, "eq_descriptions.json", res)
    return entry


def spoken_for(block: dict, description: str) -> str:
    return f"{label_for(block)}. AI description: {description.rstrip('.')}."
