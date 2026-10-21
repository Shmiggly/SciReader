"""Local LLM provider: Ollama's native /api/chat, with an on-disk response cache. No cloud providers."""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from pathlib import Path

import httpx

from ..config import get_settings
from ..store.docs import load_state


class LLMUnavailable(RuntimeError):
    pass


def models_for_jobs() -> dict:
    s = get_settings()
    st = load_state().get("settings", {})
    return {"reader": st.get("reader_model", s.narrator_model), "checker": st.get("checker_model", s.verifier_model)}


def available() -> bool:
    try:
        r = httpx.get(f"{get_settings().ollama_url}/api/version", timeout=2)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


_cache_lock = threading.Lock()


def _cache_dir() -> Path:
    d = get_settings().data_dir / "llm_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def chat(
    model: str,
    messages: list[dict],
    *,
    images: list[bytes] | None = None,
    temperature: float = 0.0,
    num_ctx: int | None = None,
    keep_alive: str | int | None = None,
    num_predict: int | None = None,
    use_cache: bool = True,
    timeout: float = 300,
) -> str:
    """One non-streaming chat completion (thinking off). Cached by (model, messages, images, options)."""
    msgs = [dict(m) for m in messages]
    if images:
        msgs[-1]["images"] = [base64.b64encode(b).decode("ascii") for b in images]
    options: dict = {"temperature": temperature}
    if num_ctx:
        options["num_ctx"] = num_ctx
    if num_predict:
        options["num_predict"] = num_predict
    key_src = json.dumps({"model": model, "messages": msgs, "options": options}, sort_keys=True)
    key = hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:32]
    path = _cache_dir() / f"{key}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["content"]
    body = {"model": model, "messages": msgs, "stream": False, "think": False, "options": options}
    if keep_alive is not None:
        body["keep_alive"] = keep_alive
    try:
        r = httpx.post(f"{get_settings().ollama_url}/api/chat", json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"Ollama is not reachable: {exc.__class__.__name__}") from exc
    if r.status_code != 200:
        raise LLMUnavailable(f"Ollama error {r.status_code}: {r.text[:200]}")
    content = (r.json().get("message") or {}).get("content", "").strip()
    with _cache_lock:
        path.write_text(json.dumps({"model": model, "content": content}), encoding="utf-8")
    return content


def unload(model: str) -> None:
    """Ask Ollama to free a model's GPU memory now."""
    try:
        httpx.post(f"{get_settings().ollama_url}/api/generate", json={"model": model, "keep_alive": 0}, timeout=30)
    except httpx.HTTPError:
        pass
