"""Runtime configuration (environment variables and .env), with no machine-specific paths in code."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, existing environment wins, empty values ignored."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    models_dir: Path
    ollama_url: str
    narrator_model: str
    verifier_model: str
    port: int
    repo_root: Path = REPO_ROOT
    lexicon_path: Path = field(default=REPO_ROOT / "lexicons" / "science-en.json")
    math_speech_dir: Path = field(default=REPO_ROOT / "tools" / "math-speech")
    frontend_dist: Path = field(default=REPO_ROOT / "frontend" / "dist")

    @property
    def docs_dir(self) -> Path:
        return self.data_dir / "docs"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def user_lexicon_path(self) -> Path:
        return self.data_dir / "lexicon.user.json"

    @property
    def state_path(self) -> Path:
        return self.data_dir / "state.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv(REPO_ROOT / ".env")
    data_dir = Path(os.environ.get("SCIREADER_DATA_DIR") or REPO_ROOT / ".data")
    models_dir = Path(os.environ.get("MODELS_DIR") or data_dir / "models")
    for d in (data_dir, models_dir, data_dir / "docs", data_dir / "audio"):
        d.mkdir(parents=True, exist_ok=True)
    return Settings(
        data_dir=data_dir,
        models_dir=models_dir,
        ollama_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
        narrator_model=os.environ.get("NARRATOR_MODEL", "qwen3.5:9b"),
        verifier_model=os.environ.get("VERIFIER_MODEL", "gemma4:12b"),
        port=int(os.environ.get("SCIREADER_PORT", "8765")),
    )
