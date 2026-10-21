# SciReader

**An open-source, local-first, science-aware reading companion for scientific papers.**

The PDF stays in front of you exactly as published. In the background SciReader keeps a parsed, structured copy (sections, sentences, equations as LaTeX, figures, captions, references, all with page coordinates), so you can click any sentence to start listening, follow a highlight on the real page, and hear equations, units and chemistry spoken the way a scientist would say them. AI narration of math checks itself against the source LaTeX before it is spoken.

Everything runs on your own machine, with Wi-Fi off: no accounts, no cloud APIs, no telemetry. That makes it usable on unpublished manuscripts and papers under review.

> Status: built during the OSI Hackathon 2026 (Oct 21-22, 2026). Work in progress.

## Why

Read-aloud tools fail on papers: they read running headers, page numbers, citation brackets and the reference list; equations come out as gibberish; you can't start where you want; units are mangled ("1.12 eV at 300 K" becomes "one point one two ee-vee at three hundred kay"). People who lose their place in long text (dyslexia, ADHD, low vision, non-native readers, anyone listening on a commute) hit that wall hardest in physics, chemistry, materials science and math.

## Features (planned for the hackathon)

- PDF-first viewer with click-to-read from any sentence, sentence + word highlighting, auto-follow and focus mode.
- Smart skipping of page furniture, citation markers, affiliations and the bibliography.
- Science-aware normalization of units, scientific notation, Greek letters, chemical formulas and abbreviations, plus a shareable pronunciation lexicon (`lexicons/science-en.json`).
- Equations read aloud from LaTeX (Speech Rule Engine), and verified AI narration: a local LLM narrates, an independent LLM transcribes the speech back to LaTeX, and the two are compared before anything is spoken.
- Local neural TTS (Kokoro-82M) and local LLMs through Ollama, managed from inside the app.
- SciSpeech-Bench: an open benchmark of how faithfully read-aloud pipelines speak math.

## Quick start (Windows)

Requirements: [uv](https://docs.astral.sh/uv/), Node.js LTS, git, and optionally [Ollama](https://ollama.com) for the AI features.

```powershell
git clone https://github.com/Shmiggly/SciReader
cd SciReader
./scripts/setup.ps1   # installs Python + Node dependencies, downloads models
./scripts/dev.ps1     # starts the backend and opens the app window
```

## Repository layout

| Path | What |
|---|---|
| `backend/` | Python 3.12 FastAPI backend (`scireader` package): parsing, speech, TTS, LLM, API, store |
| `frontend/` | Vite + React + TypeScript UI with pdf.js |
| `tools/math-speech/` | Node helper: LaTeX → MathML → speech (MathJax + Speech Rule Engine) |
| `lexicons/` | Science pronunciation lexicon (shipped) |
| `bench/` | SciSpeech-Bench data, scripts, results and the marimo analysis notebook |
| `samples/` | Sample paper manifest (PDFs are downloaded by `scripts/fetch_samples.py`, not committed) |
| `docs/` | Dev log, screenshots, write-up, licenses |

## License

Apache-2.0. Dependency and model licenses are tracked in [`docs/LICENSES.md`](docs/LICENSES.md).
