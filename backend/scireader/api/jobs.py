"""Background parse jobs (one at a time: the parser uses the GPU)."""

from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..store.docs import DocStore

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="parse")
_status: dict[str, dict] = {}
_lock = threading.Lock()


def status(doc_id: str, store: DocStore) -> dict:
    with _lock:
        st = _status.get(doc_id)
    if st:
        return st
    if store.has_document(doc_id):
        return {"state": "ready", "message": "Ready", "progress": 1.0}
    return {"state": "new", "message": "Not parsed yet", "progress": 0.0}


def _set(doc_id: str, **kw) -> None:
    with _lock:
        st = _status.setdefault(doc_id, {"state": "queued", "message": "Queued", "progress": 0.0})
        st.update(kw)


def start_parse(doc_id: str, store: DocStore, force: bool = False, rebuild: bool = False) -> dict:
    """Prepare a paper in the background. `force`: run the layout analysis (Docling) again; `rebuild` (Reload on the
    start screen): build the paper again from its stored layout analysis with the current code, in seconds."""
    with _lock:
        st = _status.get(doc_id)
        if st and st["state"] in ("queued", "parsing"):
            return st
    if store.has_document(doc_id) and not (force or rebuild):
        return {"state": "ready", "message": "Ready", "progress": 1.0}
    from ..llm import equations

    if store.has_document(doc_id) and equations.status(doc_id).get("state") in ("queued", "running"):
        # Its results are saved by block id as the checks go: a new build under them could mix two versions.
        return {"state": "error", "progress": 0.0,
                "message": "The equation checks for this paper are still running; reload it once they are done."}
    _set(doc_id, state="queued", message="Queued", progress=0.0, started=time.time())
    _executor.submit(_run, doc_id, store, force)
    return status(doc_id, store)


def changed_equations(old: dict, new: dict) -> set[str]:
    """Equation block ids that hold another equation (or none) after a new build: their checks are redone. A new
    number alone keeps them (the checks are about the formula)."""
    def formulas(doc: dict) -> dict[str, tuple]:
        return {b["id"]: (b.get("latex"), b.get("page"), tuple(b.get("bbox") or ())) for b in doc["blocks"] if b["type"] == "equation"}

    before, after = formulas(old), formulas(new)
    return {bid for bid, f in before.items() if after.get(bid) != f}


def _run(doc_id: str, store: DocStore, force: bool) -> None:
    from ..parsing.docling_parser import DoclingParser

    def progress(msg: str, frac: float) -> None:
        _set(doc_id, state="parsing", message=msg, progress=round(frac, 3))

    try:
        progress("Starting", 0.01)
        meta = store.meta(doc_id)
        pdf = store.pdf_path(doc_id)
        cache = store.dir(doc_id) / "docling.json"
        if force and cache.exists():
            cache.unlink()
        t0 = time.time()
        document, speech_index = DoclingParser().parse(
            Path(pdf), doc_id, meta.get("source", {"type": "file", "ref": meta.get("name")}), progress, cache
        )
        progress("Saving", 0.97)
        old = store.document(doc_id)
        store.write_json(doc_id, "speech.json", speech_index)
        store.write_json(doc_id, "document.json", document)
        checks = store.read_json(doc_id, "equations.json")
        if old is not None and checks:
            gone = changed_equations(old, document)
            if gone & checks.keys():
                store.write_json(doc_id, "equations.json", {k: v for k, v in checks.items() if k not in gone})
        meta["title"] = document.get("title")
        meta["parse_seconds"] = round(time.time() - t0, 1)
        meta["stats"] = document.get("stats")
        store.write_json(doc_id, "meta.json", meta)
        _set(doc_id, state="ready", message="Ready", progress=1.0)
        from ..llm import equations

        equations.start(store, doc_id)  # verified narration in the background (needs Ollama)
        from ..llm import figures

        figures.start(store, doc_id)  # figure descriptions for every first mention
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        _set(doc_id, state="error", message=f"Parsing failed: {exc}", progress=0.0)
