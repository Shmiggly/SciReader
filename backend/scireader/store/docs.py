"""Document cache (by file hash) and per-paper reading state, stored as files under the data dir."""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from ..config import get_settings

_state_lock = threading.Lock()


def replace_retry(tmp: Path, target: Path, tries: int = 20) -> None:
    """os.replace, retried: on Windows it fails while another thread has the target open for reading."""
    for i in range(tries):
        try:
            tmp.replace(target)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.05)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


class DocStore:
    def __init__(self, root: Path | None = None):
        self.root = root or get_settings().docs_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def dir(self, doc_id: str) -> Path:
        if not doc_id.isalnum():
            raise ValueError("bad document id")
        return self.root / doc_id

    def pdf_path(self, doc_id: str) -> Path:
        return self.dir(doc_id) / "source.pdf"

    def add_pdf(self, src: Path, name: str, source: dict) -> str:
        doc_id = file_hash(src)
        d = self.dir(doc_id)
        d.mkdir(parents=True, exist_ok=True)
        if not self.pdf_path(doc_id).exists():
            shutil.copyfile(src, self.pdf_path(doc_id))
        meta = self.meta(doc_id)
        meta.update({"id": doc_id, "name": name, "source": source})
        meta.setdefault("added", time.time())
        self.write_json(doc_id, "meta.json", meta)
        return doc_id

    def meta(self, doc_id: str) -> dict:
        return self.read_json(doc_id, "meta.json") or {}

    def has_document(self, doc_id: str) -> bool:
        return (self.dir(doc_id) / "document.json").exists()

    def document(self, doc_id: str) -> dict | None:
        return self.read_json(doc_id, "document.json")

    def read_json(self, doc_id: str, name: str) -> Any:
        p = self.dir(doc_id) / name
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def write_json(self, doc_id: str, name: str, data: Any) -> None:
        p = self.dir(doc_id) / name
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        replace_retry(tmp, p)

    def list_recent(self, limit: int = 12) -> list[dict]:
        state = load_state()
        items = []
        for d in self.root.iterdir():
            if not d.is_dir() or not (d / "document.json").exists():
                continue
            meta = self.meta(d.name)
            rs = state.get("papers", {}).get(d.name, {})
            items.append({
                "id": d.name,
                "title": meta.get("title") or meta.get("name"),
                "name": meta.get("name"),
                "last_opened": rs.get("last_opened", meta.get("added", 0)),
                "position": rs.get("position"),
            })
        items.sort(key=lambda x: x["last_opened"] or 0, reverse=True)
        return items[:limit]


# Reading state: {"papers": {doc_id: {sentence_id, section_title, snippet, speed, voice, eq_mode, last_opened}}}


def load_state() -> dict:
    p = get_settings().state_path
    if not p.exists():
        return {"papers": {}, "settings": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"papers": {}, "settings": {}}


def update_state(fn) -> dict:
    with _state_lock:
        state = load_state()
        fn(state)
        p = get_settings().state_path
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        replace_retry(tmp, p)
        return state
