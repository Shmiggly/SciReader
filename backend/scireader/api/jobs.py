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


def start_parse(doc_id: str, store: DocStore, force: bool = False) -> dict:
    with _lock:
        st = _status.get(doc_id)
        if st and st["state"] in ("queued", "parsing"):
            return st
    if store.has_document(doc_id) and not force:
        return {"state": "ready", "message": "Ready", "progress": 1.0}
    _set(doc_id, state="queued", message="Queued", progress=0.0, started=time.time())
    _executor.submit(_run, doc_id, store, force)
    return status(doc_id, store)


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
        store.write_json(doc_id, "speech.json", speech_index)
        store.write_json(doc_id, "document.json", document)
        meta["title"] = document.get("title")
        meta["parse_seconds"] = round(time.time() - t0, 1)
        meta["stats"] = document.get("stats")
        store.write_json(doc_id, "meta.json", meta)
        _set(doc_id, state="ready", message="Ready", progress=1.0)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        _set(doc_id, state="error", message=f"Parsing failed: {exc}", progress=0.0)
