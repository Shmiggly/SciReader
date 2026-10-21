"""Explain and Ask, grounded in the parsed paper with sentence-level citations.

The whole paper goes into the prompt with sentence IDs ("[s123] ..."), as a fixed prefix so Ollama reuses
its cache between questions. Papers longer than ~28K tokens fall back to BM25-style retrieval.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from . import ollama

MAX_PAPER_TOKENS = 28000
NUM_CTX = 32768

SYSTEM = (
    "You are a careful research assistant helping a scientist read the paper below. Answer only from the "
    "paper. After each claim, cite the sentence IDs you used in square brackets, like [s12] or [s12][s40]. "
    "If the paper does not answer the question, say so plainly. Write in plain spoken English (it may be read "
    "aloud): no markdown, no bullet lists, no LaTeX; say symbols in words. Be concise."
)


def _readable_lines(doc: dict) -> list[tuple[str, str]]:
    lines = []
    for b in doc["blocks"]:
        if b.get("skip_reason") and b["type"] not in ("caption",):
            continue
        if b["type"] in ("figure", "table"):
            continue
        for s in b["sentences"]:
            if b["type"] == "equation":
                text = f"Equation {b.get('eq_number') or ''}: {b.get('latex') or s['text']}"
            elif b["type"] == "heading":
                text = f"Section: {s['text']}"
            else:
                text = s["text"]
            lines.append((s["id"], text))
    return lines


def paper_context(doc: dict, question: str = "") -> str:
    lines = _readable_lines(doc)
    full = "\n".join(f"[{sid}] {t}" for sid, t in lines)
    if len(full) / 4 <= MAX_PAPER_TOKENS or not question:
        return f"Title: {doc.get('title', '')}\n\n{full[: MAX_PAPER_TOKENS * 4]}"
    # Long paper: keep the best-matching sentences (BM25) plus their neighbours, in paper order.
    keep = set(_bm25_top(lines, question, 160))
    idx = {sid: i for i, (sid, _) in enumerate(lines)}
    for sid in list(keep):
        i = idx[sid]
        for j in (i - 1, i + 1):
            if 0 <= j < len(lines):
                keep.add(lines[j][0])
    picked = "\n".join(f"[{sid}] {t}" for sid, t in lines if sid in keep)
    return f"Title: {doc.get('title', '')}\n(Excerpts most relevant to the question)\n\n{picked}"


def _tok(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2]


def _bm25_top(lines: list[tuple[str, str]], query: str, k: int) -> list[str]:
    docs = [_tok(t) for _, t in lines]
    n = len(docs)
    avg = sum(len(d) for d in docs) / max(1, n)
    df = Counter(w for d in docs for w in set(d))
    q = _tok(query)
    scores = []
    for (sid, _), d in zip(lines, docs):
        tf = Counter(d)
        sc = 0.0
        for w in q:
            if w not in tf:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            sc += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(d) / avg))
        scores.append((sc, sid))
    return [sid for sc, sid in sorted(scores, reverse=True)[:k] if sc > 0]


CITE = re.compile(r"\[\s*(s\d+(?:\s*[,;]\s*s\d+)*)\s*\]")


def parse_answer(text: str, valid: set[str]) -> dict:
    cites: list[str] = []
    for m in CITE.finditer(text):
        for sid in re.split(r"\s*[,;]\s*", m.group(1)):
            if sid in valid and sid not in cites:
                cites.append(sid)
    spoken = re.sub(r"\s+", " ", CITE.sub("", text)).replace(" .", ".").replace(" ,", ",").strip()
    spoken = re.sub(r"[*#`_]+", "", spoken)
    return {"answer": text.strip(), "spoken": spoken, "citations": cites}


def ask(doc: dict, question: str, history: list[dict] | None = None) -> dict:
    model = ollama.models_for_jobs()["reader"]
    msgs = [{"role": "system", "content": SYSTEM + "\n\nPAPER:\n" + paper_context(doc, question)}]
    for h in (history or [])[-4:]:
        msgs.append({"role": "user", "content": h["q"]})
        msgs.append({"role": "assistant", "content": h["a"]})
    msgs.append({"role": "user", "content": question})
    text = ollama.chat(model, msgs, num_ctx=NUM_CTX, num_predict=600, keep_alive="30m")
    valid = {sid for sid, _ in _readable_lines(doc)}
    return {**parse_answer(text, valid), "model": model}


LEVELS = {
    "colleague": "Explain it to a materials scientist colleague (PhD level, polymers and additive manufacturing, "
                 "comfortable with ML) who wants the gist and the reasoning, in 3 to 5 sentences.",
    "simpler": "Explain it in plain, simple language for someone outside the field, with an everyday analogy if it "
               "helps, in 3 to 5 short sentences.",
}


def explain(doc: dict, sentence_ids: list[str], level: str = "colleague", extra: str = "") -> dict:
    model = ollama.models_for_jobs()["reader"]
    by_id = {s["id"]: (s, b) for b in doc["blocks"] for s in b["sentences"]}
    parts = []
    for sid in sentence_ids:
        if sid in by_id:
            s, b = by_id[sid]
            parts.append(f"[{sid}] " + (f"Equation {b.get('eq_number') or ''}: {b.get('latex')}" if b["type"] == "equation" else s["text"]))
    passage = "\n".join(parts) or extra
    question = (f"Explain this passage from the paper:\n{passage}\n\n{LEVELS.get(level, LEVELS['colleague'])} "
                "Use the rest of the paper for context and cite the sentences you rely on.")
    msgs = [{"role": "system", "content": SYSTEM + "\n\nPAPER:\n" + paper_context(doc, passage)},
            {"role": "user", "content": question}]
    text = ollama.chat(model, msgs, num_ctx=NUM_CTX, num_predict=500, keep_alive="30m")
    valid = set(by_id)
    return {**parse_answer(text, valid), "model": model, "level": level}


SUMMARY_PROMPT = (
    "Write a spoken summary of {what} for a materials scientist who will listen to it, about {words} words: "
    "the question, the approach, the key results with their numbers, and the main limitation. Plain spoken "
    "English, no lists, no markdown, symbols in words. Cite sentence IDs in square brackets after each claim."
)


def summarize(doc: dict, section_id: str | None = None) -> dict:
    """1-2 minute spoken summary of the whole paper or one section (AI, labeled as such by the caller)."""
    model = ollama.models_for_jobs()["reader"]
    if section_id:
        title = next((o["title"] for o in doc["outline"] if o["id"] == section_id), "this section")
        ids = [s["id"] for b in doc["blocks"] if b.get("section_id") == section_id and not b.get("skip_reason")
               for s in b["sentences"]]
        what = f"the section \"{title}\" (sentences {ids[0]} to {ids[-1]})" if ids else f"the section \"{title}\""
        words = 150
    else:
        what, words = "the whole paper", 260
    msgs = [{"role": "system", "content": SYSTEM + "\n\nPAPER:\n" + paper_context(doc)},
            {"role": "user", "content": SUMMARY_PROMPT.format(what=what, words=words)}]
    text = ollama.chat(model, msgs, num_ctx=NUM_CTX, num_predict=700, keep_alive="30m")
    valid = {sid for sid, _ in _readable_lines(doc)}
    return {**parse_answer(text, valid), "model": model, "section_id": section_id}
