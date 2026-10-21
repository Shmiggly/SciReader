"""Verified equation narration.

0. The reader model, as a vision model, reads each equation again from the page; the parser's LaTeX is confirmed,
   corrected or marked disputed against that second reading and the PDF text layer (page_reading.py).
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

from ..parsing.latex import latex_has_content
from ..speech.math_speech import get_math_speech
from ..store.docs import DocStore
from . import ollama, page_reading
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
    eqs = [(i, b) for i, b in enumerate(blocks) if b["type"] == "equation" and b.get("skip_reason") != "junk"]
    res: dict = {} if force else results(store, doc_id)
    # Results from before the second reading existed are redone (model calls are cached: only new work costs).
    todo = [(i, b) for i, b in eqs
            if b["id"] not in res or res[b["id"]].get("verdict") in (None, "pending") or "source" not in res[b["id"]]]
    total = len(eqs)
    _set(doc_id, state="running", message="Reading equations from the page", done=total - len(todo), total=total,
         started=time.time())

    def save() -> None:
        store.write_json(doc_id, "equations.json", res)

    # Batch 0: second reading of the page (reader model, as a vision model). Saved as pending so playback uses the
    # corrected rule-based reading while the narrations are checked.
    springer = page_reading.is_springer(blocks)
    pdf = str(store.pdf_path(doc_id))
    for n, (i, b) in enumerate(todo):
        _set(doc_id, message=f"Reading equations from the page ({n + 1}/{len(todo)})")
        res[b["id"]] = {**_source(reader, pdf, b, springer), "verdict": "pending", "attempts": []}
    save()

    work: dict[str, dict] = {}
    for i, b in todo:
        base = {k: res[b["id"]][k] for k in ("source", "latex", "speech_rules")}
        if not base["latex"].strip() or not base["speech_rules"]:
            res[b["id"]] = {**base, "verdict": "unreadable" if not base["speech_rules"] else "fallback",
                            "reason": "no usable LaTeX from the parser or the page", "attempts": []}
            continue
        work[b["id"]] = {"latex": base["latex"], "context": _context_for(blocks, i), "attempts": [], "base": base}
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
            **w["base"],
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


def _source(model: str, pdf: str, b: dict, springer: bool) -> dict:
    """The LaTeX to narrate, check and read by rules: the parser's, or the vision model's reading of the page when
    the PDF text layer backs it (page_reading.decide). Both readings are kept in "source"."""
    parser = b.get("latex") or ""
    if b.get("latex_source") == "arxiv":
        return {"latex": parser, "speech_rules": b.get("speech_rules"), "source": {"status": "arxiv", "used": "arxiv"}}
    vision, error = None, None
    try:
        vision = page_reading.clean_transcription(page_reading.transcribe(model, pdf, b), b.get("eq_number"), b.get("text") or "")
    except Exception as exc:  # noqa: BLE001 - a reader model without vision, or Ollama failing: keep the parser's
        error = str(exc)[:200]
    info = {**page_reading.decide(parser, vision, b, springer), "model": model, "error": error}
    latex, speech = parser, b.get("speech_rules")
    if info["used"] == "vision":
        spoken = get_math_speech().speak(vision) if latex_has_content(vision) else None
        if spoken:
            latex, speech = vision, spoken
        else:  # the page reading can't be read aloud by the rules engine either
            info.update(status="single" if speech else "unreadable", used="parser")
    return {"latex": latex, "speech_rules": speech, "source": info}


def _check_batch(doc_id: str, checker: str, items: list, res: dict, total: int) -> None:
    for n, (bid, w) in enumerate(items):
        _set(doc_id, message=f"Checking narrations ({n + 1}/{len(items)})")
        w["back"] = ollama.chat(checker, [{"role": "system", "content": TRANSCRIBE_SYSTEM},
                                          {"role": "user", "content": w["speech"]}], num_predict=400)
        w["cmp"] = compare(w["latex"], w["back"])
