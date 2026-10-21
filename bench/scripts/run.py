"""Run SciSpeech-Bench conditions on bench/data/equations.jsonl and write bench/results/results.jsonl.

Conditions (spoken text per equation):
  a_naive     what a generic reader speaks: the equation's glyphs in reading order, no structure
              (simulated PDF text layer: MathML token texts in document order)
  b_sre       Speech Rule Engine, ClearSpeak, from the source LaTeX
  c_llm       local LLM narration (qwen3.5:9b), unverified
  d_verified  c + verification gate (gemma4:12b back-transcription, canonical MathML compare,
              one repair round); only an exact round trip is spoken as AI, otherwise b_sre
  f_llm4b / f_verified4b   the same with qwen3.5:4b as narrator
Judging: an independent model family (phi4:14b) transcribes every spoken text back to LaTeX; we compare
to the source with the same canonical MathML comparison (match / relaxed / mismatch). gemma4:12b is a
secondary judge (it is also the gate's checker, so it is not independent for d).

Every model call is cached on disk, so the script can be re-run and extended cheaply.
Usage: uv run --directory backend python ../bench/scripts/run.py [--limit N] [--judges phi4:14b,gemma4:12b]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from scireader.llm import ollama  # noqa: E402
from scireader.llm.equations import TRANSCRIBE_SYSTEM, _clean_speech, narrate_messages  # noqa: E402
from scireader.llm.verify import compare, to_mathml  # noqa: E402
from scireader.speech.math_speech import MathSpeech, polish_speech  # noqa: E402

DATA = ROOT / "bench" / "data"
RESULTS = ROOT / "bench" / "results"


def glyphs(latex: str) -> str:
    """The equation as a PDF text layer would give it: token glyphs in order, no structure."""
    ml, _ = to_mathml(latex)
    if not ml:
        return latex
    out = []
    for el in ET.fromstring(ml).iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("mi", "mn", "mo", "mtext") and el.text and el.text.strip():
            t = el.text.strip()
            if t in ("⁡", "⁢", "⁣"):
                continue
            out.append(t)
    return " ".join(out)


def narrate(model: str, latex: str) -> str:
    return _clean_speech(ollama.chat(model, narrate_messages(latex, ""), num_predict=400))


def transcribe(model: str, speech: str, system: str = TRANSCRIBE_SYSTEM) -> str:
    return ollama.chat(model, [{"role": "system", "content": system}, {"role": "user", "content": speech}],
                       num_predict=500)


# The judge's prompt is frozen: the gate's checker prompt is part of the pipeline under test and changes with it,
# the judge must not (otherwise a pipeline change also changes how every condition is scored).
JUDGE_SYSTEM = (
    "You transcribe spoken mathematics into LaTeX. Write exactly the equation the words describe, nothing more "
    "and nothing less. Output only the LaTeX code, without dollar signs, code fences or explanation."
)


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--narrators", default="qwen3.5:9b,qwen3.5:4b")
    ap.add_argument("--checker", default="gemma4:12b")
    ap.add_argument("--judges", default="phi4:14b,gemma4:12b")
    args = ap.parse_args()
    items = [json.loads(line) for line in (DATA / "equations.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        items = items[: args.limit]
    narrators = [m for m in args.narrators.split(",") if m]
    judges = [m for m in args.judges.split(",") if m]
    ms = MathSpeech(ROOT / "tools" / "math-speech")
    RESULTS.mkdir(parents=True, exist_ok=True)

    log(f"{len(items)} equations; narrators {narrators}; checker {args.checker}; judges {judges}")
    for it in items:
        it["a_naive"] = glyphs(it["latex"])
        it["b_sre"] = polish_speech(ms.run(it["latex"], display=True).get("speech") or "")

    tags = {narrators[0]: ("c_llm", "d_verified")}
    if len(narrators) > 1:
        tags[narrators[1]] = ("f_llm4b", "f_verified4b")

    # Batch 1: narrations, one model at a time.
    for model, (raw_key, _) in tags.items():
        log(f"narrating with {model}")
        for it in items:
            it[raw_key] = narrate(model, it["latex"])
        ollama.unload(model)
    # Batch 2: gate check (checker model).
    log(f"gate check with {args.checker}")
    for model, (raw_key, _) in tags.items():
        for it in items:
            back = transcribe(args.checker, it[raw_key])
            it[f"{raw_key}_gate1"] = {"back": back, "result": compare(it["latex"], back).status}
    ollama.unload(args.checker)
    # Batch 3: repairs for mismatches, then re-check.
    for model, (raw_key, _) in tags.items():
        log(f"repairs with {model}")
        for it in items:
            g = it[f"{raw_key}_gate1"]
            if g["result"] == "mismatch":
                c = compare(it["latex"], g["back"])
                msgs = narrate_messages(it["latex"], "", c.diff or "the structure differs", it[raw_key])
                it[f"{raw_key}_repair"] = _clean_speech(ollama.chat(model, msgs, num_predict=400))
        ollama.unload(model)
    log(f"re-check repairs with {args.checker}")
    for model, (raw_key, ver_key) in tags.items():
        for it in items:
            g1 = it[f"{raw_key}_gate1"]
            if f"{raw_key}_repair" in it:
                back = transcribe(args.checker, it[f"{raw_key}_repair"])
                r2 = compare(it["latex"], back).status
                it[f"{raw_key}_gate2"] = {"back": back, "result": r2}
            else:
                r2 = None
            if g1["result"] == "match":
                verdict, text = "verified", it[raw_key]
            elif r2 == "match":
                verdict, text = "verified", it[f"{raw_key}_repair"]
            elif "relaxed" in (g1["result"], r2):
                # Same symbols, different grouping: like the app, speak the rules reading, not the AI narration.
                verdict, text = "uncertain", it["b_sre"]
            else:
                verdict, text = "fallback", it["b_sre"]
            it[ver_key] = text
            it[f"{ver_key}_verdict"] = verdict
    ollama.unload(args.checker)

    # Batch 4: judges transcribe every condition's speech back to LaTeX.
    conds = ["a_naive", "b_sre"] + [k for pair in tags.values() for k in pair]
    for judge in judges:
        log(f"judging with {judge}")
        for it in items:
            for cond in conds:
                back = transcribe(judge, it[cond], JUDGE_SYSTEM)
                c = compare(it["latex"], back)
                it.setdefault("judge", {}).setdefault(judge, {})[cond] = {"back": back, "result": c.status,
                                                                         "ratio": round(c.ratio, 3), "diff": c.diff}
        ollama.unload(judge)

    with open(RESULTS / "results.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    # Quick summary.
    for judge in judges:
        line = []
        for cond in conds:
            n = len(items)
            m = sum(1 for it in items if it["judge"][judge][cond]["result"] == "match")
            r = sum(1 for it in items if it["judge"][judge][cond]["result"] in ("match", "relaxed"))
            line.append(f"{cond}: exact {m / n:.0%} faithful {r / n:.0%}")
        log(f"[{judge}] " + " | ".join(line))
    ms.close()
    log("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
