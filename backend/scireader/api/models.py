"""Model manager routes: TTS voices, parser models, local LLMs (Ollama), storage and offline readiness."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import get_settings
from ..store.docs import load_state, update_state
from ..tts.engine import get_engine, registry

router = APIRouter(prefix="/api/models")

PARSER_REPOS = {
    "docling-project/docling-layout-heron": "Layout analysis (Docling Heron)",
    "docling-project/docling-models": "Table structure (TableFormer)",
    "docling-project/CodeFormulaV2": "Formula → LaTeX (CodeFormula)",
}
# Measured on an RTX 4070 with nvidia-smi (NOTES §3); estimates marked.
VRAM_GB = {"qwen3.5:9b": 6.2, "gemma4:12b": 8.5, "qwen3.5:4b": 3.6, "qwen3.5:2b": 2.2, "kokoro": 0.7}
LLM_CATALOG = [
    {"name": "qwen3.5:9b", "role": "Reader: narration, figures, explain, ask (vision)", "size_gb": 6.6},
    {"name": "gemma4:12b", "role": "Checker: independent back-transcription", "size_gb": 8.0},
    {"name": "qwen3.5:4b", "role": "Smaller reader for laptops with less GPU memory", "size_gb": 3.4},
]


def _hub_dir() -> Path:
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def _repo_dir(repo_id: str) -> Path:
    return _hub_dir() / ("models--" + repo_id.replace("/", "--"))


def _cached_file(repo_id: str, filename: str) -> Path | None:
    from huggingface_hub import try_to_load_from_cache

    p = try_to_load_from_cache(repo_id, filename)
    return Path(p) if isinstance(p, str) and Path(p).exists() else None


def _dir_size(p: Path) -> int:
    if not p.exists():
        return 0
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _gpu() -> dict:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().splitlines()[0]
        name, total, used = [x.strip() for x in out.split(",")]
        return {"name": name, "total_gb": round(int(total) / 1024, 1), "used_gb": round(int(used) / 1024, 1)}
    except Exception:  # noqa: BLE001
        return {"name": None, "total_gb": None, "used_gb": None}


def _ollama_models() -> tuple[bool, list[dict], list[str]]:
    url = get_settings().ollama_url
    try:
        with httpx.Client(timeout=3) as c:
            tags = c.get(f"{url}/api/tags").json().get("models", [])
            loaded = [m.get("name") for m in c.get(f"{url}/api/ps").json().get("models", [])]
        return True, [
            {"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1),
             "params": (m.get("details") or {}).get("parameter_size"),
             "quant": (m.get("details") or {}).get("quantization_level"),
             "vram_gb": VRAM_GB.get(m["name"])}
            for m in tags
        ], loaded
    except Exception:  # noqa: BLE001
        return False, [], []


def jobs() -> dict:
    s = get_settings()
    st = load_state().get("settings", {})
    return {"reader": st.get("reader_model", s.narrator_model), "checker": st.get("checker_model", s.verifier_model)}


@router.get("")
def overview() -> dict:
    s = get_settings()
    eng = registry()["engines"][0]
    engine = get_engine()
    weights_ok = all(_cached_file(eng["repo_id"], f) for f in eng["files"])
    voices = []
    for v in eng["voices"]:
        voices.append({**v, "installed": _cached_file(eng["repo_id"], eng["voice_file"].format(voice=v["id"])) is not None})
    parser = [{"repo": r, "name": n, "installed": _repo_dir(r).exists() and _dir_size(_repo_dir(r)) > 0} for r, n in PARSER_REPOS.items()]
    ollama_up, llms, loaded = _ollama_models()
    installed_names = {m["name"] for m in llms}
    math_ok = (s.math_speech_dir / "node_modules" / "speech-rule-engine").exists() and shutil.which("node") is not None
    default_voice = load_state().get("settings", {}).get("default_voice", eng["default_voice"])
    offline_ready = weights_ok and any(v["installed"] and v["id"] == default_voice for v in voices) and all(p["installed"] for p in parser) and math_ok
    j = jobs()
    return {
        "tts": {
            "engine": {k: eng[k] for k in ("id", "name", "license", "size_mb", "languages", "gpu", "quality")},
            "weights_installed": weights_ok,
            "ready": engine.ready,
            "device": engine.device,
            "default_voice": default_voice,
            "voices": voices,
        },
        "parser": parser,
        "math_speech": {"installed": math_ok},
        "llm": {
            "ollama": ollama_up,
            "url": s.ollama_url,
            "installed": llms,
            "loaded": loaded,
            "catalog": [{**c, "installed": c["name"] in installed_names, "vram_gb": VRAM_GB.get(c["name"])} for c in LLM_CATALOG],
            "jobs": j,
        },
        "gpu": {**_gpu(), "kokoro_gb": VRAM_GB["kokoro"]},
        "storage": {
            "data_dir": str(s.data_dir),
            "data_bytes": _dir_size(s.data_dir),
            "hf_cache": str(_hub_dir()),
            "hf_bytes": _dir_size(_hub_dir()),
            "ollama_models_dir": os.environ.get("OLLAMA_MODELS", "(Ollama default)"),
            "how_to_change": "Set SCIREADER_DATA_DIR, HF_HOME and OLLAMA_MODELS in .env / user environment, then restart.",
        },
        "offline_ready": offline_ready,
        "ai_ready": ollama_up and j["reader"] in installed_names,
    }


@router.post("/voices/{voice}/download")
def download_voice(voice: str) -> dict:
    eng = registry()["engines"][0]
    if voice not in {v["id"] for v in eng["voices"]}:
        raise HTTPException(404, "Unknown voice")
    from huggingface_hub import hf_hub_download

    try:
        hf_hub_download(eng["repo_id"], eng["voice_file"].format(voice=voice))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Download failed (offline?): {exc.__class__.__name__}") from exc
    return {"ok": True}


@router.delete("/voices/{voice}")
def delete_voice(voice: str) -> dict:
    eng = registry()["engines"][0]
    if voice == load_state().get("settings", {}).get("default_voice", eng["default_voice"]):
        raise HTTPException(400, "That's the default voice; pick another default first")
    p = _cached_file(eng["repo_id"], eng["voice_file"].format(voice=voice))
    if p:
        real = p.resolve()
        p.unlink(missing_ok=True)
        if real != p and real.exists():
            real.unlink(missing_ok=True)
    return {"ok": True}


class DefaultVoice(BaseModel):
    voice: str


@router.put("/voices/default")
def set_default_voice(body: DefaultVoice) -> dict:
    update_state(lambda s: s.setdefault("settings", {}).update(default_voice=body.voice))
    return {"ok": True}


class Jobs(BaseModel):
    reader: str | None = None
    checker: str | None = None


@router.put("/llm/jobs")
def set_jobs(body: Jobs) -> dict:
    def fn(s: dict) -> None:
        st = s.setdefault("settings", {})
        if body.reader:
            st["reader_model"] = body.reader
        if body.checker:
            st["checker_model"] = body.checker

    update_state(fn)
    return jobs()


class Pull(BaseModel):
    name: str


@router.post("/llm/pull")
def pull(body: Pull) -> StreamingResponse:
    url = get_settings().ollama_url

    def stream():
        try:
            with httpx.Client(timeout=None) as c:
                with c.stream("POST", f"{url}/api/pull", json={"model": body.name, "stream": True}) as r:
                    for line in r.iter_lines():
                        if line.strip():
                            yield f"data: {line}\n\n"
            yield 'data: {"status": "done"}\n\n'
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': f'Ollama unreachable or offline: {exc.__class__.__name__}'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.delete("/llm/{name:path}")
def delete_llm(name: str) -> dict:
    url = get_settings().ollama_url
    try:
        r = httpx.request("DELETE", f"{url}/api/delete", json={"model": name}, timeout=30)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Ollama is not running") from exc
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return {"ok": True}
