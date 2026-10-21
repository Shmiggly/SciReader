"""Inspect how SciReader parses a PDF: block types, reading order, skips and spoken text.

Usage:  uv run python -m scireader.parsing.inspect_doc path/to/paper.pdf [--all] [--reparse]
The parse is cached in the data dir (same cache the app uses), so a second run is instant.
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

from ..store.docs import DocStore


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--all", action="store_true", help="print every sentence, not just the first of each block")
    ap.add_argument("--reparse", action="store_true", help="rebuild the document even if cached")
    ap.add_argument("--redocling", action="store_true", help="also rerun Docling (slow)")
    args = ap.parse_args()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    from ..parsing.docling_parser import DoclingParser

    store = DocStore()
    pdf = Path(args.pdf)
    doc_id = store.add_pdf(pdf, pdf.name, {"type": "file", "ref": pdf.name})
    cache = store.dir(doc_id) / "docling.json"
    if args.redocling and cache.exists():
        cache.unlink()
    doc = store.document(doc_id)
    if doc is None or args.reparse or args.redocling:
        t0 = time.time()
        doc, speech = DoclingParser().parse(pdf, doc_id, {"type": "file", "ref": pdf.name},
                                            lambda m, f: print(f"  [{f:4.0%}] {m}", flush=True), cache)
        store.write_json(doc_id, "speech.json", speech)
        store.write_json(doc_id, "document.json", doc)
        meta = store.meta(doc_id)
        meta.update(title=doc["title"], stats=doc["stats"], parse_seconds=round(time.time() - t0, 1))
        store.write_json(doc_id, "meta.json", meta)
        print(f"parsed in {time.time() - t0:.1f} s")
    print(f"id={doc_id}  title={doc['title']!r}")
    print(f"authors={doc['authors'][:6]}")
    print(f"stats={doc['stats']}")
    print("outline:", " | ".join(("  " * (o['level'] - 1)) + o["title"] for o in doc["outline"]))
    for b in doc["blocks"]:
        skip = f" SKIP:{b['skip_reason']}" if b.get("skip_reason") else ""
        head = f"{b['id']:>5} p{b['page'] + 1:<2} {b['type']:<11}{skip}"
        sents = b["sentences"] if args.all else b["sentences"][:1]
        if not sents:
            print(f"{head} | {b['text'][:100]!r}")
        for s in sents:
            print(f"{head} | {s['text'][:110]!r}")
            if s["spoken"] != s["text"]:
                print(f"{'':>30}→ {s['spoken'][:150]!r}")
    print(f"figures: {[(f['label'], f['page'] + 1) for f in doc['figures']]}")
    print(f"bibliography: {len(doc['bibliography'])} entries; citations: {len(doc['citations'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
