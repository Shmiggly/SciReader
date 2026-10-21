"""Verified equation narration.

1. The reader model narrates each equation (LaTeX + the sentence before it) in natural speech.
2. The checker model, which never sees the LaTeX, transcribes that speech back into LaTeX.
3. Both LaTeX strings are compared as canonical MathML trees (verify.py).
4. Mismatch → one repair round telling the narrator what was lost → re-check.
Verdicts: verified (exact) · uncertain (same symbols, grouping differs) · fallback (rules reading) · unreadable.
Runs in batches per paper so the two models swap a few times, not per equation.
"""

from __future__ import annotations

import re
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from ..store.docs import DocStore
from . import ollama
from .verify import compare

NARRATE_SYSTEM = (
    "You read equations aloud for a scientist who is listening to a paper. Turn the LaTeX equation into the "
    "words a physicist would say when reading it to a colleague, so that the listener could write the exact "
    "equation back down. Say every symbol, subscript, superscript, operator and number, in order. Make "
    "grouping unambiguous: for fractions say 'the fraction with numerator … over denominator …' or "
    "'… all over …'; for exponents or roots that span several terms say where they end ('… end exponent', "
    "'… end root'); say 'open parenthesis' / 'close parenthesis' only when needed. Use natural names for Greek "
    "letters and functions (e.g. 'sigma', 'the square root of', 'the integral from 0 to infinity of'). Do not "
    "explain, interpret, or add words, and do not say 'Equation'. Output one line of plain English: no LaTeX, "
    "no symbols, no markdown."
)
TRANSCRIBE_SYSTEM = (
    "You transcribe spoken mathematics into LaTeX. Write exactly the equation the words describe, nothing more "
    "and nothing less. Output only the LaTeX code, without dollar signs, code fences or explanation."
)
BRIEF_SYSTEM = (
    "In one short sentence of at most 20 words, say what this equation expresses, naming the quantities in "
    "words instead of reading the symbols. Plain English only."
)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="verify")
_status: dict[str, dict] = {}
_lock = threading.Lock()


def _context_for(blocks: list[dict], idx: int) -> str:
    for j in range(idx - 1, max(-1, idx - 4), -1):
        b = blocks[j]
        if b["type"] in ("paragraph", "abstract", "list_item") and b.get("sentences"):
            return b["sentences"][-1]["text"][:400]
    return ""


def _clean_speech(s: str) -> str:
    s = s.strip().strip('"').strip()
    s = re.sub(r"^(equation\s*\d*\s*[:.]\s*)", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s)
    return s.rstrip(".") + "."


def narrate_messages(latex: str, context: str, feedback: str | None = None, previous: str | None = None) -> list[dict]:
    user = (f"Sentence before the equation: {context}\n" if context else "") + f"LaTeX: {latex}"
    msgs = [{"role": "system", "content": NARRATE_SYSTEM}, {"role": "user", "content": user}]
    if feedback and previous:
        msgs += [
            {"role": "assistant", "content": previous},
            {"role": "user", "content": (
                "A listener who wrote your reading down got a different equation: " + feedback
                + ". Read the equation again so that this part is unambiguous. One line of plain English.")},
        ]
    return msgs


def status(doc_id: str) -> dict:
    with _lock:
        return dict(_status.get(doc_id, {}))


def results(store: DocStore, doc_id: str) -> dict:
    return store.read_json(doc_id, "equations.json") or {}


def start(store: DocStore, doc_id: str, force: bool = False) -> dict:
    with _lock:
        st = _status.get(doc_id)
        if st and st.get("state") in ("queued", "running"):
            return dict(st)
        _status[doc_id] = {"state": "queued", "message": "Waiting", "done": 0, "total": 0}
    _executor.submit(_run, store, doc_id, force)
    return status(doc_id)


def _set(doc_id: str, **kw) -> None:
    with _lock:
        _status.setdefault(doc_id, {}).update(kw)


def _run(store: DocStore, doc_id: str, force: bool) -> None:
    try:
        _verify_document(store, doc_id, force)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        _set(doc_id, state="error", message=str(exc))


def _verify_document(store: DocStore, doc_id: str, force: bool) -> None:
    doc = store.document(doc_id)
    if doc is None:
        _set(doc_id, state="error", message="Not parsed")
        return
    if not ollama.available():
        _set(doc_id, state="unavailable", message="Ollama is not running: equations use the rule-based reading")
        return
    models = ollama.models_for_jobs()
    reader, checker = models["reader"], models["checker"]
    blocks = doc["blocks"]
    eqs = [(i, b) for i, b in enumerate(blocks) if b["type"] == "equation"]
    res: dict = {} if force else results(store, doc_id)
    todo = [(i, b) for i, b in eqs if b["id"] not in res or res[b["id"]].get("verdict") in (None, "pending")]
    total = len(eqs)
    _set(doc_id, state="running", message="Narrating equations", done=total - len(todo), total=total, started=time.time())

    def save() -> None:
        store.write_json(doc_id, "equations.json", res)

    work: dict[str, dict] = {}
    for i, b in todo:
        latex = b.get("latex") or ""
        if not latex.strip() or not b.get("speech_rules"):
            res[b["id"]] = {"verdict": "unreadable" if not b.get("speech_rules") else "fallback",
                            "reason": "no usable LaTeX from the parser", "attempts": []}
            continue
        work[b["id"]] = {"latex": latex, "context": _context_for(blocks, i), "attempts": []}
    save()

    # Batch 1: narrations (reader model).
    for bid, w in work.items():
        _set(doc_id, message=f"Narrating equations ({len(w['attempts'])}/{len(work)})")
        w["speech"] = _clean_speech(ollama.chat(reader, narrate_messages(w["latex"], w["context"]), num_predict=400))
        w["brief"] = ollama.chat(reader, [{"role": "system", "content": BRIEF_SYSTEM},
                                          {"role": "user", "content": (f"Context: {w['context']}\n" if w["context"] else "") + f"LaTeX: {w['latex']}"}],
                                 num_predict=80).strip().strip('"')
    # Batch 2: back-transcription (checker model, unloaded afterwards).
    pending = list(work.items())
    _check_batch(doc_id, checker, pending, res, total)
    save()
    # Repair round for mismatches: reader again, then checker again.
    retry = [(bid, w) for bid, w in work.items() if w["cmp"].status == "mismatch"]
    if retry:
        _set(doc_id, message=f"Repairing {len(retry)} narrations")
        for bid, w in retry:
            w["first"] = {"speech": w["speech"], "back": w["back"], "cmp": w["cmp"]}
            w["speech"] = _clean_speech(ollama.chat(reader, narrate_messages(w["latex"], w["context"], w["cmp"].diff, w["speech"]), num_predict=400))
        _check_batch(doc_id, checker, retry, res, total)
    ollama.unload(checker)

    for bid, w in work.items():
        attempts = []
        if "first" in w:
            f = w["first"]
            attempts.append({"speech": f["speech"], "back": f["back"], "result": f["cmp"].status, "diff": f["cmp"].diff})
        c = w["cmp"]
        attempts.append({"speech": w["speech"], "back": w["back"], "result": c.status, "diff": c.diff})
        best = max(attempts, key=lambda a: {"match": 3, "relaxed": 2}.get(a["result"], 0))
        if best["result"] == "match":
            verdict = "verified"
        elif best["result"] == "relaxed":
            verdict = "uncertain"
        elif c.status == "error":
            verdict = "fallback"
        else:
            verdict = "fallback"
        res[bid] = {
            "verdict": verdict,
            "speech_ai": best["speech"] if verdict in ("verified", "uncertain") else None,
            "brief": w.get("brief"),
            "attempts": attempts,
            "reason": c.error or (best["diff"] if verdict != "verified" else ""),
            "models": {"reader": reader, "checker": checker},
        }
    save()
    counts = {}
    for r in res.values():
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    _set(doc_id, state="done", message="Equations checked", done=total, counts=counts)


def _check_batch(doc_id: str, checker: str, items: list, res: dict, total: int) -> None:
    for n, (bid, w) in enumerate(items):
        _set(doc_id, message=f"Checking narrations ({n + 1}/{len(items)})")
        w["back"] = ollama.chat(checker, [{"role": "system", "content": TRANSCRIBE_SYSTEM},
                                          {"role": "user", "content": w["speech"]}], num_predict=400)
        w["cmp"] = compare(w["latex"], w["back"])
