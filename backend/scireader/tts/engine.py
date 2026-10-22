"""TTS engine interface, the Kokoro engine, and the on-disk audio cache."""

from __future__ import annotations

import hashlib
import io
import json
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np

from ..config import get_settings

REGISTRY_PATH = Path(__file__).with_name("registry.json")


@lru_cache(maxsize=1)
def registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


@dataclass
class Word:
    text: str
    start: float  # seconds
    end: float
    s0: int  # char span in the spoken text
    s1: int


@dataclass
class Synth:
    audio: np.ndarray  # float32 mono
    sample_rate: int
    words: list[Word]


class TTSEngine(Protocol):
    id: str

    def synth(self, text: str, voice: str, speed: float = 1.0) -> Synth: ...


def _resolve(repo_id: str, filename: str) -> str:
    """Local cached file if present (works offline), else download."""
    from huggingface_hub import hf_hub_download

    try:
        return hf_hub_download(repo_id, filename, local_files_only=True)
    except Exception:  # noqa: BLE001
        return hf_hub_download(repo_id, filename)


class KokoroEngine:
    id = "kokoro"

    def __init__(self) -> None:
        self.repo_id = "hexgrad/Kokoro-82M"
        self._model = None
        self._pipelines: dict[str, object] = {}
        self._lock = threading.Lock()
        self.device = "cpu"
        self.ready = False
        self.error: str | None = None

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            try:
                import torch
                from kokoro import KModel

                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                config = _resolve(self.repo_id, "config.json")
                weights = _resolve(self.repo_id, "kokoro-v1_0.pth")
                self._model = KModel(repo_id=self.repo_id, config=config, model=weights).to(self.device).eval()
                self.ready = True
            except Exception as exc:  # noqa: BLE001
                self.error = f"{type(exc).__name__}: {exc}"
                raise

    def _pipeline(self, lang: str):
        from kokoro import KPipeline

        if lang not in self._pipelines:
            self._pipelines[lang] = KPipeline(lang_code=lang, repo_id=self.repo_id, model=self._model)
        return self._pipelines[lang]

    def voice_path(self, voice: str) -> str:
        return _resolve(self.repo_id, f"voices/{voice}.pt")

    def synth(self, text: str, voice: str, speed: float = 1.0) -> Synth:
        self.load()
        lang = voice[0] if voice[:1] in ("a", "b") else "a"
        with self._lock:
            pipe = self._pipeline(lang)
            chunks: list[np.ndarray] = []
            words: list[Word] = []
            offset = 0.0
            cursor = 0
            for result in pipe(text, voice=self.voice_path(voice), speed=speed, split_pattern=None):
                audio = result.audio
                if audio is None:
                    continue
                audio = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
                for tok in result.tokens or []:
                    t = (tok.text or "").strip()
                    if not t or tok.start_ts is None or tok.end_ts is None:
                        continue
                    idx = text.find(t, cursor)
                    if idx < 0:
                        continue
                    cursor = idx + len(t)
                    if not any(ch.isalnum() for ch in t):
                        continue
                    words.append(Word(t, offset + float(tok.start_ts), offset + float(tok.end_ts), idx, idx + len(t)))
                chunks.append(audio.astype(np.float32))
                offset += len(audio) / 24000
            audio = np.concatenate(chunks) if chunks else np.zeros(2400, dtype=np.float32)
            return Synth(audio=audio, sample_rate=24000, words=words)


_engine: KokoroEngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> KokoroEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = KokoroEngine()
        return _engine


def warm_up() -> None:
    """Load the model and synthesize once so the first click plays fast."""
    t0 = time.time()
    eng = get_engine()
    try:
        eng.load()
        eng.synth("SciReader is ready.", registry()["engines"][0]["default_voice"])
        print(f"[tts] Kokoro ready on {eng.device} in {time.time() - t0:.1f} s", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[tts] Kokoro failed to load: {exc}", flush=True)


# ---------------------------------------------------------------------------------------------
# Audio cache: key = hash(engine, voice, speed, spoken text)


def cache_key(engine: str, voice: str, speed: float, spoken: str) -> str:
    h = hashlib.sha1(f"{engine}|{voice}|{speed:.2f}|{spoken}".encode("utf-8")).hexdigest()
    return h[:24]


def audio_path(key: str) -> Path:
    return get_settings().audio_dir / f"{key}.wav"


# Respellings for the voice only (the text keeps the symbol): a lone "R" ending an utterance came out weak and
# short; "ar" was the user's pick in an A/B listening test (2026-10-21).
_VOICE_FIXES = [(re.compile(r"(?<![\w'])R(?=[.!?]?\s*$)"), "ar")]


def for_voice(spoken: str) -> str:
    for rx, rep in _VOICE_FIXES:
        spoken = rx.sub(rep, spoken)
    return spoken


def synth_cached(spoken: str, voice: str, speed: float = 1.0) -> tuple[str, dict]:
    """Return (key, meta) with meta = {duration, words: [{start, end, s0, s1}]}; synthesizes on a miss."""
    import soundfile as sf

    eng = get_engine()
    spoken = for_voice(spoken)
    key = cache_key(eng.id, voice, speed, spoken)
    wav = audio_path(key)
    meta_path = wav.with_suffix(".json")
    if wav.exists() and meta_path.exists():
        return key, json.loads(meta_path.read_text(encoding="utf-8"))
    res = eng.synth(spoken, voice, speed)
    buf = io.BytesIO()
    sf.write(buf, res.audio, res.sample_rate, format="WAV", subtype="PCM_16")
    tmp = wav.with_suffix(".tmp")
    tmp.write_bytes(buf.getvalue())
    tmp.replace(wav)
    meta = {
        "duration": round(len(res.audio) / res.sample_rate, 3),
        "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "s0": w.s0, "s1": w.s1} for w in res.words],
    }
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return key, meta
