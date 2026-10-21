"""AI routes (local LLMs through Ollama): verified equation narration status and results."""

from __future__ import annotations

from fastapi import APIRouter

from ..llm import equations, ollama
from .docs import _check, store

router = APIRouter(prefix="/api")


@router.get("/ai/status")
def ai_status() -> dict:
    return {"ollama": ollama.available(), "models": ollama.models_for_jobs()}


@router.get("/docs/{doc_id}/equations")
def get_equations(doc_id: str) -> dict:
    _check(doc_id)
    return {"status": equations.status(doc_id), "results": _public(equations.results(store, doc_id))}


@router.post("/docs/{doc_id}/equations/verify")
def verify(doc_id: str, force: bool = False) -> dict:
    _check(doc_id)
    if store.document(doc_id) is None:
        return {"state": "error", "message": "Not parsed"}
    return equations.start(store, doc_id, force=force)


def _public(res: dict) -> dict:
    return {
        bid: {
            "verdict": r.get("verdict"),
            "speech_ai": r.get("speech_ai"),
            "brief": r.get("brief"),
            "reason": r.get("reason"),
            "attempts": r.get("attempts", []),
            "models": r.get("models"),
            "source": r.get("source"),
            "latex": r.get("latex"),
            "speech_rules": r.get("speech_rules"),
        }
        for bid, r in res.items()
    }


# ---------------------------------------------------------------------------------------------
# Figures: mentions, crops, descriptions, narration audio

from fastapi import HTTPException  # noqa: E402
from fastapi.responses import Response  # noqa: E402

from ..llm import figures  # noqa: E402
from ..tts.engine import synth_cached  # noqa: E402


@router.get("/docs/{doc_id}/figures")
def get_figures(doc_id: str) -> dict:
    _check(doc_id)
    doc = store.document(doc_id)
    if doc is None:
        raise HTTPException(404, "Not parsed yet")
    descs = store.read_json(doc_id, "figures.json") or {}
    return {"status": figures.status(doc_id), "mentions": figures.find_mentions(doc),
            "descriptions": {k: {"description": v.get("description"), "caption_part": v.get("caption_part"),
                                 "label": v.get("label"), "panels": v.get("panels")} for k, v in descs.items()}}


@router.post("/docs/{doc_id}/figures/prepare")
def prepare_figures(doc_id: str) -> dict:
    _check(doc_id)
    return figures.start(store, doc_id)


@router.get("/docs/{doc_id}/figures/{fig_id}/image")
def figure_image(doc_id: str, fig_id: str) -> Response:
    _check(doc_id)
    doc = store.document(doc_id)
    fig = next((f for f in (doc or {}).get("figures", []) if f["id"] == fig_id), None)
    if fig is None:
        raise HTTPException(404, "Unknown figure")
    cache = store.dir(doc_id) / f"{fig_id}.png"
    if not cache.exists():
        cache.write_bytes(figures.crop_png(str(store.pdf_path(doc_id)), fig["page"], fig["bbox"]))
    return Response(cache.read_bytes(), media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@router.get("/tts/{doc_id}/figure/{key}")
def figure_tts(doc_id: str, key: str, voice: str = "af_heart", detail: bool = False) -> dict:
    """Narration for a figure target: label + caption part + labeled AI description (if ready)."""
    _check(doc_id)
    doc = store.document(doc_id)
    if doc is None:
        raise HTTPException(404, "Not parsed yet")
    descs = store.read_json(doc_id, "figures.json") or {}
    entry = descs.get(key + (":detail" if detail else ""))
    if entry is None and detail and ollama.available():
        try:
            entry = figures.describe(store, doc_id, doc, key, detail=detail)
        except Exception:  # noqa: BLE001 - playback never waits on a failing AI
            entry = None
    if entry is None:
        number = key.rstrip("abcdefgh")
        fig = next((f for f in doc["figures"] if f.get("number") == number), None)
        if fig is None:
            raise HTTPException(404, "Unknown figure")
        panels = list(key[len(number):])
        entry = {"label": f"Figure {number}", "panels": panels,
                 "caption_part": figures.caption_part(figures.caption_text(doc, fig), panels), "description": None}
    from ..speech.pipeline import speak

    spoken = speak(figures.spoken_for(entry)).spoken
    k, meta = synth_cached(spoken, voice)
    return {"audio_url": f"/api/audio/{k}.wav", "duration": meta["duration"], "spoken": spoken,
            "description": entry.get("description"), "label": entry.get("label"), "panels": entry.get("panels"),
            "words": []}


# ---------------------------------------------------------------------------------------------
# Explain / Ask (grounded, with sentence citations) and reading arbitrary AI text aloud

from pydantic import BaseModel  # noqa: E402

from ..llm import qa  # noqa: E402


class AskReq(BaseModel):
    question: str
    history: list[dict] = []


class ExplainReq(BaseModel):
    sentence_ids: list[str] = []
    text: str = ""
    level: str = "colleague"


def _doc_or_404(doc_id: str) -> dict:
    _check(doc_id)
    doc = store.document(doc_id)
    if doc is None:
        raise HTTPException(404, "Not parsed yet")
    return doc


@router.post("/docs/{doc_id}/ask")
def ask(doc_id: str, req: AskReq) -> dict:
    doc = _doc_or_404(doc_id)
    try:
        return qa.ask(doc, req.question, req.history)
    except ollama.LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/docs/{doc_id}/explain")
def explain(doc_id: str, req: ExplainReq) -> dict:
    doc = _doc_or_404(doc_id)
    try:
        return qa.explain(doc, req.sentence_ids, req.level, req.text)
    except ollama.LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


class SayReq(BaseModel):
    text: str
    voice: str = "af_heart"
    label: str = ""


@router.post("/tts/say")
def say(req: SayReq) -> dict:
    """Speak arbitrary text (AI answers, explanations) through the same normalizer and voice."""
    from ..speech.pipeline import speak

    text = (req.label + " " if req.label else "") + req.text
    spoken = speak(text[:4000]).spoken
    k, meta = synth_cached(spoken, req.voice)
    return {"audio_url": f"/api/audio/{k}.wav", "duration": meta["duration"], "spoken": spoken, "words": []}


class SummaryReq(BaseModel):
    section_id: str | None = None


@router.post("/docs/{doc_id}/summary")
def summary(doc_id: str, req: SummaryReq) -> dict:
    doc = _doc_or_404(doc_id)
    try:
        return qa.summarize(doc, req.section_id)
    except ollama.LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/docs/{doc_id}/crop")
def crop(doc_id: str, page: int, x0: float, y0: float, x1: float, y1: float) -> Response:
    """A crop of a PDF page (exactly as published), e.g. an equation for the reference popup."""
    _check(doc_id)
    key = f"crop_{page}_{int(x0)}_{int(y0)}_{int(x1)}_{int(y1)}.png"
    cache = store.dir(doc_id) / key
    if not cache.exists():
        cache.write_bytes(figures.crop_png(str(store.pdf_path(doc_id)), page, [x0, y0, x1, y1], scale=2.5))
    return Response(cache.read_bytes(), media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@router.post("/docs/{doc_id}/arxiv-source")
def arxiv_source(doc_id: str, arxiv_id: str | None = None) -> dict:
    """Use the paper's arXiv LaTeX for its equations (needs internet once; cached afterwards)."""
    from ..parsing import arxiv_source as ax

    doc = _doc_or_404(doc_id)
    aid = arxiv_id or (doc.get("source", {}).get("ref") if doc.get("source", {}).get("type") == "arxiv" else None)
    if not aid:
        raise HTTPException(400, "This paper has no arXiv ID")
    cache = store.dir(doc_id) / "arxiv_src.tex"
    if cache.exists():
        tex = cache.read_text(encoding="utf-8")
    else:
        try:
            tex = ax.fetch_tex(aid)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Couldn't reach arXiv (offline?): {exc.__class__.__name__}") from exc
        if not tex:
            raise HTTPException(404, "arXiv has no LaTeX source for this paper (PDF-only submission)")
        cache.write_text(tex, encoding="utf-8")
    rows = ax.source_equations(tex)
    eq_blocks = [b for b in doc["blocks"] if b["type"] == "equation"]
    mapping = ax.align(eq_blocks, rows)
    n = ax.apply(doc, mapping)
    store.write_json(doc_id, "document.json", doc)
    # Re-check the replaced equations with the exact LaTeX.
    res = equations.results(store, doc_id)
    for bid in mapping:
        res.pop(bid, None)
    store.write_json(doc_id, "equations.json", res)
    from . import tts as tts_api

    tts_api.invalidate(doc_id)
    equations.start(store, doc_id)
    return {"matched": n, "equations": len(eq_blocks), "source_rows": len(rows), "arxiv": aid}
