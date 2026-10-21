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
    doc = store.document(doc_id)
    if doc is not None and source.get("type") == "arxiv" and doc.get("source") != source:
        doc["source"] = source  # e.g. parsed earlier from a local file, now known to be on arXiv
        store.write_json(doc_id, "document.json", doc)
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


# ---------------------------------------------------------------------------------------------
# Pronunciation review and the user lexicon

from ..speech.lexicon import Lexicon, LexiconEntry  # noqa: E402
from ..speech.pipeline import get_lexicon  # noqa: E402
from ..speech.review import candidates  # noqa: E402


@router.get("/docs/{doc_id}/pronunciation")
def pronunciation(doc_id: str) -> dict:
    _check(doc_id)
    doc = store.document(doc_id)
    if doc is None:
        raise HTTPException(404, "Not parsed yet")
    return {"terms": candidates(doc, get_lexicon())}


def _user_lexicon() -> Lexicon:
    s = get_settings()
    return Lexicon.load(s.lexicon_path, s.user_lexicon_path)


@router.get("/lexicon")
def lexicon_all() -> dict:
    lx = get_lexicon()
    return {"entries": [e.to_dict() for e in lx.entries], "user_count": len(lx.user_entries)}


class EntryReq(BaseModel):
    term: str
    say_as: str
    ipa: str | None = None
    case_sensitive: bool = True
    tags: list[str] = []
    note: str = ""


@router.put("/lexicon/user")
def lexicon_put(req: EntryReq) -> dict:
    if not req.term.strip() or not req.say_as.strip():
        raise HTTPException(400, "Term and pronunciation are required")
    lx = _user_lexicon()
    entry = LexiconEntry.from_dict({**req.model_dump(), "source": "user"})
    lx.add(entry)
    lx.save_user(get_settings().user_lexicon_path)
    return entry.to_dict()


@router.delete("/lexicon/user/{term}")
def lexicon_delete(term: str) -> dict:
    lx = _user_lexicon()
    ok = lx.remove(term)
    lx.save_user(get_settings().user_lexicon_path)
    return {"ok": ok}


@router.get("/lexicon/export")
def lexicon_export() -> FileResponse:
    s = get_settings()
    out = s.data_dir / "lexicon-export.json"
    _user_lexicon().export(out, name="My SciReader pronunciations")
    return FileResponse(out, media_type="application/json", filename="scireader-lexicon.json")


class ImportReq(BaseModel):
    lexicon: dict
    decisions: dict[str, str] = {}  # term -> "mine" | "theirs"


@router.post("/lexicon/import")
def lexicon_import(req: ImportReq) -> dict:
    entries = [LexiconEntry.from_dict(e, default_source="imported") for e in req.lexicon.get("entries", []) if e.get("term")]
    if not entries:
        raise HTTPException(400, "No entries found in that file")
    lx = _user_lexicon()
    conflicts = lx.merge([e for e in entries if req.decisions.get(e.term) != "mine"])
    # Merge keeps the user's version on conflict; apply "take theirs" decisions explicitly.
    for e in entries:
        if req.decisions.get(e.term) == "theirs":
            lx.add(e)
    lx.save_user(get_settings().user_lexicon_path)
    pending = [c for c in conflicts if c.term not in req.decisions]
    return {"added": len(entries) - len(conflicts), "conflicts": [
        {"term": c.term, "mine": c.mine.to_dict(), "theirs": c.theirs.to_dict()} for c in pending]}


# ---------------------------------------------------------------------------------------------
# Audiobook export

from .. import audiobook  # noqa: E402


@router.post("/docs/{doc_id}/audiobook")
def audiobook_start(doc_id: str, voice: str = "af_heart", eq_mode: str = "auto") -> dict:
    _check(doc_id)
    if store.document(doc_id) is None:
        raise HTTPException(404, "Not parsed yet")
    return audiobook.start(store, doc_id, voice, eq_mode)


@router.get("/docs/{doc_id}/audiobook/status")
def audiobook_status(doc_id: str) -> dict:
    _check(doc_id)
    st = audiobook.status(doc_id)
    if st.get("state") == "idle" and audiobook.output_path(store, doc_id).exists():
        st = {"state": "done", "progress": 1.0, "message": "Ready"}
    return st


@router.get("/docs/{doc_id}/audiobook/download")
def audiobook_download(doc_id: str) -> FileResponse:
    _check(doc_id)
    p = audiobook.output_path(store, doc_id)
    if not p.exists():
        raise HTTPException(404, "No audiobook yet")
    title = re.sub(r"[^A-Za-z0-9 -]+", "", (store.meta(doc_id).get("title") or "paper"))[:50].strip() or "paper"
    return FileResponse(p, media_type="application/zip", filename=f"{title} - SciReader audiobook.zip")
