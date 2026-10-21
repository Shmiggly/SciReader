"""SciReader backend: a local HTTP API (FastAPI) that also serves the built frontend."""

from __future__ import annotations

import os
import threading

from .config import get_settings

settings = get_settings()
# Models are cached locally; never reach for the network at runtime unless asked to download.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from . import __version__  # noqa: E402
from .api import docs as docs_api  # noqa: E402
from .api import tts as tts_api  # noqa: E402

app = FastAPI(title="SciReader", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(docs_api.router)
app.include_router(tts_api.router)


@app.on_event("startup")
def _startup() -> None:
    from .tts.engine import warm_up

    threading.Thread(target=warm_up, name="tts-warmup", daemon=True).start()


@app.get("/api/health")
def health() -> dict:
    from .tts.engine import get_engine

    eng = get_engine()
    return {"ok": True, "version": __version__, "tts": {"ready": eng.ready, "device": eng.device, "error": eng.error}}


dist = settings.frontend_dist
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


def run() -> None:
    import uvicorn

    uvicorn.run("scireader.main:app", host="127.0.0.1", port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
