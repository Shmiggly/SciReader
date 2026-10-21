"""Document routes: open (upload / sample / arXiv), parse status, document JSON, PDF, reading state."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import get_settings
from ..store.docs import DocStore, load_state, update_state
from . import jobs

router = APIRouter(prefix="/api")
store = DocStore()
USER_AGENT = "SciReader/0.1 (open-source paper reader; https://github.com/Shmiggly/SciReader)"


def _open_pdf(path: Path, name: str, source: dict) -> dict:
    doc_id = store.add_pdf(path, name, source)
    st = jobs.start_parse(doc_id, store)
    return {"id": doc_id, "status": st}


@router.post("/docs/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Please choose a PDF file")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=get_settings().data_dir) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        head = tmp_path.read_bytes()[:5]
        if head != b"%PDF-":
            raise HTTPException(400, "That file is not a PDF")
        return _open_pdf(tmp_path, file.filename or "paper.pdf", {"type": "file", "ref": file.filename})
    finally:
        tmp_path.unlink(missing_ok=True)


class ArxivReq(BaseModel):
    ref: str


@router.post("/docs/arxiv")
def from_arxiv(req: ArxivReq) -> dict:
    m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", req.ref) or re.search(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})", req.ref)
    if not m:
        raise HTTPException(400, "That doesn't look like an arXiv ID or URL")
    arxiv_id = m.group(0)
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    try:
        with httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            r = client.get(url)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Couldn't reach arXiv (are you offline?): {exc.__class__.__name__}") from exc
    if not r.content.startswith(b"%PDF"):
        raise HTTPException(502, "arXiv didn't return a PDF")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=get_settings().data_dir) as tmp:
        tmp.write(r.content)
        tmp_path = Path(tmp.name)
    try:
        return _open_pdf(tmp_path, f"arXiv {arxiv_id}", {"type": "arxiv", "ref": arxiv_id})
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/samples")
def samples() -> list[dict]:
    root = get_settings().repo_root / "samples"
    manifest = root / "manifest.json"
    if not manifest.exists():
        return []
    papers = json.loads(manifest.read_text(encoding="utf-8")).get("papers", [])
    return [
        {"id": p["id"], "title": p["title"], "role": p.get("role"), "license": p.get("license")}
        for p in papers
        if (root / p["file"]).exists()
    ]


@router.post("/samples/{sample_id}/open")
def open_sample(sample_id: str) -> dict:
    root = get_settings().repo_root / "samples"
    papers = json.loads((root / "manifest.json").read_text(encoding="utf-8")).get("papers", [])
    p = next((x for x in papers if x["id"] == sample_id), None)
    if p is None or not (root / p["file"]).exists():
        raise HTTPException(404, "Sample not found")
    source = {"type": "arxiv", "ref": p["arxiv"]} if p.get("arxiv") else {"type": "file", "ref": p["file"]}
    return _open_pdf(root / p["file"], p["file"], source)


@router.get("/docs/recent")
def recent() -> list[dict]:
    return store.list_recent()


@router.get("/docs/{doc_id}/status")
def doc_status(doc_id: str) -> dict:
    _check(doc_id)
    return jobs.status(doc_id, store)


@router.post("/docs/{doc_id}/parse")
def reparse(doc_id: str, force: bool = False) -> dict:
    _check(doc_id)
    return jobs.start_parse(doc_id, store, force=force)


@router.get("/docs/{doc_id}")
def get_doc(doc_id: str) -> dict:
    _check(doc_id)
    doc = store.document(doc_id)
    if doc is None:
        raise HTTPException(404, "Not parsed yet")
    return doc


@router.get("/docs/{doc_id}/pdf")
def get_pdf(doc_id: str) -> FileResponse:
    _check(doc_id)
    p = store.pdf_path(doc_id)
    if not p.exists():
        raise HTTPException(404, "PDF not found")
    return FileResponse(p, media_type="application/pdf")


@router.delete("/docs/{doc_id}")
def forget(doc_id: str) -> dict:
    _check(doc_id)
    shutil.rmtree(store.dir(doc_id), ignore_errors=True)
    update_state(lambda s: s.get("papers", {}).pop(doc_id, None))
    return {"ok": True}


class ReadingState(BaseModel):
    sentence_id: str | None = None
    section_title: str | None = None
    snippet: str | None = None
    speed: float | None = None
    voice: str | None = None
    eq_mode: str | None = None


@router.get("/state/{doc_id}")
def get_state(doc_id: str) -> dict:
    _check(doc_id)
    return load_state().get("papers", {}).get(doc_id, {})


@router.put("/state/{doc_id}")
def put_state(doc_id: str, body: ReadingState) -> dict:
    _check(doc_id)
    data = {k: v for k, v in body.model_dump().items() if v is not None}

    def fn(state: dict) -> None:
        paper = state.setdefault("papers", {}).setdefault(doc_id, {})
        paper.update(data)
        if body.sentence_id:
            paper["position"] = {"sentence_id": body.sentence_id, "section_title": body.section_title,
                                 "snippet": body.snippet}
        paper["last_opened"] = time.time()

    return update_state(fn)["papers"][doc_id]


@router.get("/settings")
def get_app_settings() -> dict:
    return load_state().get("settings", {})


@router.put("/settings")
def put_app_settings(body: dict) -> dict:
    return update_state(lambda s: s.setdefault("settings", {}).update(body))["settings"]


def _check(doc_id: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{16}", doc_id):
        raise HTTPException(404, "Unknown document")
