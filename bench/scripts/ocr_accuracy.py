"""Equation OCR accuracy against the papers' own LaTeX (arXiv source): the parser's formula OCR (Docling), the vision
model reading the page crop, and the reading the app uses after the second reading (page_reading.decide).

Ground truth: each display equation's source LaTeX, aligned in order (scireader.parsing.arxiv_source). Alignment
is run with both readings, so equations the parser garbled can still be matched; an equation is scored when the
two alignments agree or only one finds a row. Scoring uses the gate's comparison: exact (match) or same symbols
(match or relaxed). The parsed papers must be in .data/docs and their sources in bench/raw (bench/scripts/collect.py).

Usage: uv run --directory backend python ../bench/scripts/ocr_accuracy.py [--model qwen3.5:9b]
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from scireader.llm import page_reading as pr  # noqa: E402
from scireader.llm.verify import compare  # noqa: E402
from scireader.parsing import arxiv_source as ax  # noqa: E402
from scireader.store.docs import DocStore  # noqa: E402

PAPERS = {"2209.13557": "93245516eb377ad7", "2307.10139": "ab50c9e555a0c40a", "2511.23306": "f7d2264d0ee723fc",
          "2512.08896": "3600267c6eb34a8c"}
RESULTS = ROOT / "bench" / "results"


def source_tex(arxiv_id: str) -> str:
    blob = (ROOT / "bench" / "raw" / f"{arxiv_id}.src").read_bytes()
    try:
        raw = gzip.decompress(blob)
    except OSError:
        raw = blob
    try:
        with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
            return "\n".join(tf.extractfile(m).read().decode("utf-8", "replace")
                             for m in tf.getmembers() if m.isfile() and m.name.endswith(".tex") and m.size < 3_000_000)
    except tarfile.TarError:
        return raw.decode("utf-8", "replace")


def score(truth: str, latex: str | None) -> str:
    if not latex:
        return "none"
    return compare(truth.replace(" \\\\ ", " "), latex).status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3.5:9b")
    args = ap.parse_args()
    store = DocStore()
    rows_out = []
    for aid, doc_id in PAPERS.items():
        doc = store.document(doc_id)
        if doc is None:
            print(f"{aid}: not parsed, skipped")
            continue
        eqs = [b for b in doc["blocks"] if b["type"] == "equation" and b.get("skip_reason") != "junk"]
        springer = pr.is_springer(doc["blocks"])
        pdf = str(store.pdf_path(doc_id))
        vision = {b["id"]: pr.clean_transcription(pr.transcribe(args.model, pdf, b), b.get("eq_number"), b.get("text") or "")
                  for b in eqs}
        rows = ax.source_equations(source_tex(aid))
        by_parser = ax.align(eqs, rows)
        by_vision = ax.align([{**b, "latex": vision[b["id"]]} for b in eqs], rows)
        for b in eqs:
            t1, t2 = by_parser.get(b["id"]), by_vision.get(b["id"])
            if t1 and t2 and t1 != t2:
                continue  # ambiguous alignment: not scored
            truth = t1 or t2
            if not truth:
                continue
            parser = b.get("latex") or ""
            d = pr.decide(parser, vision[b["id"]], b, springer)
            chosen = vision[b["id"]] if d["used"] == "vision" else parser
            rows_out.append({"paper": aid, "block": b["id"], "eq": b.get("eq_number"), "truth": truth, "parser": parser,
                             "vision": vision[b["id"]], "status": d["status"], "used": d["used"],
                             "parser_vs_truth": score(truth, parser), "vision_vs_truth": score(truth, vision[b["id"]]),
                             "chosen_vs_truth": score(truth, chosen)})
        print(f"{aid}: {len(eqs)} equations, {sum(1 for r in rows_out if r['paper'] == aid)} aligned to the source", flush=True)

    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "ocr_accuracy.jsonl", "w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = len(rows_out)
    print(f"\n{n} equations scored against the arXiv source")
    for who in ("parser", "vision", "chosen"):
        c = Counter(r[f"{who}_vs_truth"] for r in rows_out)
        print(f"  {who:7s} exact {c['match']:3d} ({c['match'] / max(n, 1):.0%})  same symbols {c['match'] + c['relaxed']:3d} "
              f"({(c['match'] + c['relaxed']) / max(n, 1):.0%})")
    print("  by second-reading status (exact vs source of the reading used):")
    for st, k in sorted(Counter((r["status"], r["used"]) for r in rows_out).items()):
        ok = sum(1 for r in rows_out if (r["status"], r["used"]) == st and r["chosen_vs_truth"] == "match")
        print(f"    {st[0]:11s} used {st[1]:6s} {k:3d}  exact {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
