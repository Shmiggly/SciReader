"""Rebuild parsed papers from their cached Docling output after a builder change (no Docling run).

Equation checks are kept unless the equation's LaTeX or label changed; figure descriptions are keyed by figure
and stay valid. A paper that used arXiv source mode gets its source LaTeX applied again. Restart the backend
afterwards (it caches documents); opening a paper re-checks the equations whose results were dropped.

Usage:  uv run python -m scireader.parsing.rebuild [doc_id ...]   (default: every parsed paper)
"""

from __future__ import annotations

import argparse
import io
import sys

from ..store.docs import DocStore


def rebuild(store: DocStore, doc_id: str) -> str:
    from . import arxiv_source as ax
    from .docling_parser import DoclingParser

    cache = store.dir(doc_id) / "docling.json"
    old = store.document(doc_id)
    if old is None or not cache.exists():
        return "skipped (no cached parse)"
    meta = store.meta(doc_id)
    doc, speech = DoclingParser().parse(store.pdf_path(doc_id), doc_id, old.get("source") or meta.get("source", {}),
                                        None, cache)
    tex = store.dir(doc_id) / "arxiv_src.tex"
    if tex.exists():
        eq_blocks = [b for b in doc["blocks"] if b["type"] == "equation"]
        ax.apply(doc, ax.align(eq_blocks, ax.source_equations(tex.read_text(encoding="utf-8"))))

    def eqs(d: dict) -> dict:
        return {b["id"]: (b.get("latex"), b.get("eq_label")) for b in d["blocks"] if b["type"] == "equation"}

    def sents(d: dict) -> dict:
        return {s["id"]: s["text"] for b in d["blocks"] for s in b["sentences"]}

    old_eq, new_eq = eqs(old), eqs(doc)
    changed = [bid for bid, v in new_eq.items() if old_eq.get(bid) != v]
    res = store.read_json(doc_id, "equations.json")
    if res is not None:
        for bid in changed:
            res.pop(bid, None)
        store.write_json(doc_id, "equations.json", res)
    old_s, new_s = sents(old), sents(doc)
    edited = sum(1 for k, v in new_s.items() if k in old_s and old_s[k] != v)
    store.write_json(doc_id, "speech.json", speech)
    store.write_json(doc_id, "document.json", doc)
    meta.update(title=doc["title"], stats=doc["stats"])
    store.write_json(doc_id, "meta.json", meta)
    return (f"{len(new_s)} sentences (was {len(old_s)}), {edited} edited; "
            f"{len(changed)} of {len(new_eq)} equations changed (checks dropped)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("doc_ids", nargs="*")
    args = ap.parse_args()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    store = DocStore()
    ids = args.doc_ids or sorted(d.name for d in store.root.iterdir() if (d / "document.json").exists())
    for doc_id in ids:
        title = (store.meta(doc_id).get("title") or "")[:60]
        print(f"{doc_id} {title}: {rebuild(store, doc_id)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
