"""Speech routes: per-sentence audio with word timings mapped to PDF rectangles, voices and previews."""

from __future__ import annotations

import threading
from collections import OrderedDict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

try:
    from ..speech.lexicon import strip_markup
except ImportError:  # pragma: no cover
    def strip_markup(s: str) -> str:
        return s
from ..speech.pipeline import speak
from ..tts.engine import audio_path, get_engine, registry, synth_cached
from .docs import _check, store

router = APIRouter(prefix="/api")

_cache: OrderedDict[str, tuple[dict, dict]] = OrderedDict()
_cache_lock = threading.Lock()


def _indexed(doc_id: str) -> tuple[dict, dict]:
    """(sentences by id with their block, speech index) for a document, LRU-cached."""
    with _cache_lock:
        if doc_id in _cache:
            _cache.move_to_end(doc_id)
            return _cache[doc_id]
    doc = store.document(doc_id)
    if doc is None:
        raise HTTPException(404, "Not parsed yet")
    speech = store.read_json(doc_id, "speech.json") or {}
    by_id = {}
    for b in doc["blocks"]:
        for s in b.get("sentences", []):
            by_id[s["id"]] = (s, b)
    with _cache_lock:
        _cache[doc_id] = (by_id, speech)
        while len(_cache) > 4:
            _cache.popitem(last=False)
    return by_id, speech


def invalidate(doc_id: str | None = None) -> None:
    with _cache_lock:
        if doc_id is None:
            _cache.clear()
        else:
            _cache.pop(doc_id, None)


def equation_spoken(block: dict, mode: str) -> str:
    number = block.get("eq_number")
    label = f"Equation {number}" if number else "Equation"
    speech = block.get("speech_rules")
    if mode == "skip" or not speech:
        return f"{label}."
    return f"{label}: {speech}."


@router.get("/tts/{doc_id}/{sentence_id}")
def tts(doc_id: str, sentence_id: str, voice: str = "af_heart", eq_mode: str = "full") -> dict:
    _check(doc_id)
    by_id, speech = _indexed(doc_id)
    if sentence_id not in by_id:
        raise HTTPException(404, "Unknown sentence")
    sentence, block = by_id[sentence_id]
    entry = speech.get(sentence_id, {})
    if block["type"] == "equation":
        spoken = equation_spoken(block, eq_mode)
        norm = None
    elif block.get("skip_reason") and block["type"] != "caption":
        spoken = sentence["text"]
        norm = None
    else:
        norm = speak(sentence["text"], [tuple(x) for x in entry.get("drop", [])])
        spoken = norm.spoken
    if not spoken.strip():
        spoken = "."
    try:
        key, meta = synth_cached(spoken, voice)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"Speech engine unavailable: {exc}") from exc

    words_out = []
    boxes = entry.get("words", [])
    for w in meta["words"]:
        rects: list = []
        if norm is not None and boxes:
            d0, d1 = norm.spoken_to_display(w["s0"], w["s1"])
            for b0, b1, r in boxes:
                if b0 < d1 and d0 < b1:
                    rects.extend(r)
        words_out.append({"start": w["start"], "end": w["end"], "rects": rects})
    return {
        "sentence_id": sentence_id,
        "audio_url": f"/api/audio/{key}.wav",
        "duration": meta["duration"],
        "spoken": strip_markup(spoken),
        "words": words_out,
    }


@router.get("/audio/{name}")
def audio(name: str) -> FileResponse:
    key = name.removesuffix(".wav")
    if not key.isalnum():
        raise HTTPException(404)
    p = audio_path(key)
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="audio/wav", headers={"Cache-Control": "max-age=31536000, immutable"})


@router.get("/voices")
def voices() -> dict:
    eng = registry()["engines"][0]
    return {"engine": eng["id"], "default": eng["default_voice"], "voices": eng["voices"],
            "ready": get_engine().ready, "device": get_engine().device, "error": get_engine().error}


PREVIEW_TEXT = "The glass transition temperature of PEGDA rises to 45 degrees Celsius after curing."


@router.get("/voices/{voice}/preview")
def preview(voice: str) -> dict:
    ids = {v["id"] for v in registry()["engines"][0]["voices"]}
    if voice not in ids:
        raise HTTPException(404, "Unknown voice")
    spoken = speak(PREVIEW_TEXT).spoken
    key, meta = synth_cached(spoken, voice)
    return {"audio_url": f"/api/audio/{key}.wav", "duration": meta["duration"], "spoken": strip_markup(spoken)}
