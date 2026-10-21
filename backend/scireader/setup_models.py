"""Download the models SciReader needs to run offline: Kokoro (weights + default voice) and Docling's models."""

from __future__ import annotations

import os
import sys


def main() -> int:
    os.environ["HF_HUB_OFFLINE"] = "0"
    from huggingface_hub import hf_hub_download

    from .tts.engine import registry

    eng = registry()["engines"][0]
    for f in eng["files"]:
        print(f"Kokoro: {f}", flush=True)
        hf_hub_download(eng["repo_id"], f)
    hf_hub_download(eng["repo_id"], eng["voice_file"].format(voice=eng["default_voice"]))

    print("Docling: layout, table and formula models (into the Hugging Face cache)", flush=True)
    from docling.datamodel.base_models import InputFormat

    from .parsing.docling_parser import _make_converter

    _make_converter().initialize_pipeline(InputFormat.PDF)
    print("Models ready.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
