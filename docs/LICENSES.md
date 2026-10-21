# Dependency and model licenses

SciReader is Apache-2.0. Every dependency and model is tracked here; anything GPL, AGPL, non-commercial or usage-limited is flagged. "Unverified" means not yet checked against the upstream license file.

## Python (backend)

| Package | License | Notes |
|---|---|---|
| fastapi, uvicorn, pydantic, httpx, python-multipart | MIT / BSD | |
| docling, docling-core, docling-parse, docling-ibm-models | MIT | Parser (default) |
| pypdfium2 (PDFium) | Apache-2.0 / BSD-3 | Char boxes; chosen over PyMuPDF (AGPL) |
| torch, torchvision | BSD-3 | CUDA build from download.pytorch.org |
| transformers, huggingface_hub | Apache-2.0 | |
| kokoro | Apache-2.0 | TTS engine |
| misaki | Apache-2.0 | G2P for Kokoro. **Flag:** pulls in espeak-ng / phonemizer (GPL-3.0) for out-of-dictionary words. Acceptable for this open-source build; replace before any closed commercial release. |
| spaCy, en_core_web_sm | MIT | Used by misaki |
| soundfile (libsndfile) | BSD-3 / LGPL-2.1 | |
| numpy | BSD-3 | |

## Node

| Package | License | Notes |
|---|---|---|
| react, react-dom, zustand, vite, @vitejs/plugin-react | MIT | |
| typescript | Apache-2.0 | |
| pdfjs-dist | Apache-2.0 | |
| katex | MIT | |
| mathjax-full | Apache-2.0 | LaTeX → MathML |
| speech-rule-engine | Apache-2.0 | MathML → speech (ClearSpeak) |

## Models (downloaded by the user, never redistributed)

| Model | License | Use |
|---|---|---|
| hexgrad/Kokoro-82M | Apache-2.0 | TTS voices |
| docling-project/docling-layout-heron, docling-models (TableFormer), CodeFormulaV2 | Apache-2.0 / MIT (unverified per model card) | Layout, tables, formula LaTeX |
| qwen3.5:9b (Ollama) | Apache-2.0 (unverified) | Narration, figures, explain/ask |
| gemma4:12b (Ollama) | Gemma terms / Apache-2.0 (unverified) | Back-transcription for verification |

## Avoided as defaults

- PyMuPDF (AGPL), Marker (weights restricted above revenue thresholds), XTTS-v2 (non-commercial).
- MinerU: custom license with commercial terms above a usage threshold; optional parser only.
