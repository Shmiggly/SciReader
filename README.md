# SciReader

**An open-source, offline, science-aware read-aloud companion for scientific papers.**

![SciReader reading a polymer-printing paper: focus mode, sentence and word highlight](docs/screenshots/m2-reader-focus-highlight.jpg)

The PDF stays in front of you exactly as published. In the background SciReader keeps a parsed copy of the paper (sections, sentences, equations as LaTeX, figures, captions, references, all with page coordinates). You click any sentence to start listening, and a highlight follows the voice on the real page. Equations, units and chemistry are spoken the way a scientist would say them. When an AI narrates an equation, an independent model writes the narration back as LaTeX and SciReader checks that it still is the same equation before speaking it.

Everything runs on your own computer, with Wi-Fi off: no accounts, no cloud APIs, no telemetry. That makes it usable on unpublished manuscripts and papers under review.

> Built in 36 hours, solo, for the OSI Hackathon 2026 ("Build the Future of Scientific Intelligence").

## Why

It's easy to lose your place in long text and reread the same lines. Audiobooks fixed that for books; nothing fixed it for papers. Read-aloud tools start at the first character and read everything: running headers, page numbers, "[12]", affiliations, the reference list. Equations come out as gibberish. Units are mangled: a good neural voice says "1.12 eV at 300 K" as "one point one two ee-vee at three hundred kay" and "MPa" as "em-pah". Commercial paper readers are closed, cloud-only subscriptions, and none says how faithfully it renders the math.

Researchers with dyslexia, ADHD or low vision, non-native readers, and anyone listening on a commute hit the same wall, and in physics, chemistry, materials science and math the wall is specifically **equations, units, chemical formulas and figures**.

## What it does

**Read like a scientist**
- Science-aware normalization (deterministic, 284 tests): units and compound units (`mW cm⁻²` → "milliwatts per square centimeter"), scientific notation, ±, ≈, ranges, Greek letters, sub/superscripts, chemical formulas and isotopes (`Fe₂O₃`, `Ca²⁺`, `¹³C`), abbreviations (Fig., Eq., et al., e.g.).
- Equations are announced and read from LaTeX with the Speech Rule Engine, or with **verified AI narration** (below). Full / Brief (labeled AI summary) / Skip modes; → skips the rest of a long equation.
- A shareable **pronunciation lexicon** (`lexicons/science-en.json`, 100+ polymer, additive-manufacturing and characterization terms: PEGDA → "peg-dah", Tg → "T G", PA12 → "P A twelve") plus your own lexicon, which overrides it.
- A **pronunciation review screen** lists the terms in the open paper that the voice will probably say badly, ranked by frequency. You hear each one in context, type how it should sound, preview, and save; the fix applies everywhere at once. Lexicons export and import (with keep-mine / take-theirs on conflicts), the seed of an open, community-grown science pronunciation dataset.

**Verified math narration** (the signature feature)
1. A local LLM (`qwen3.5:9b`) narrates each display equation naturally.
2. A different model family (`gemma4:12b`), which never sees the LaTeX, writes the narration back as LaTeX.
3. Both are compared as canonical MathML trees (MathJax), not as strings.
4. On a mismatch the narrator gets one repair round ("'k_B T' came back as 'k_B' times 'T'"). If it still fails, SciReader falls back to the rule-based reading, and if even that is impossible it says only "Equation 3".

Each equation gets a badge on the PDF: *checking…*, ✓ verified, ? uncertain, ✗ rules, unreadable. Clicking it shows the equation (KaTeX), exactly what is spoken, and the check's attempts. Playback never waits for the AI.

**Start anywhere, keep your place**
- Click any sentence or section heading to start reading there; sentence and word highlight on the PDF; auto-follow with "Back to reading position"; focus mode dims everything but the current paragraph.
- Skips page headers/footers, citation markers (including superscript numerals, detected from glyph size and baseline), affiliations, footnotes and the reference list (each a toggle). Hover a citation to see its reference.
- Resume where you left off; recent papers; a clean text view (Atkinson Hyperlegible or OpenDyslexic); optional pause after each paragraph; audiobook export (one MP3 per section).

**Figures and questions (all local AI, always labeled)**
- When the text first mentions a figure, the figure pops up where it was mentioned and SciReader reads its caption and a short AI description. It is panel-aware: "Fig. 3b" describes only panel b. `D` asks for more detail.
- `E` on a sentence that cites "Eq. (4)" shows the equation over the text, reads it, and resumes.
- Explain the current sentence (colleague level, or "Simpler"), ask the paper questions, or listen to a 1–2 minute summary. Answers come only from the paper and cite the sentences they use; citation chips jump to them on the PDF.

**Fully offline, one-click models**
- Kokoro-82M voices (28 English voices, ~0.06 s per sentence on an RTX 4070) and Ollama LLMs, managed from a model panel with downloads, deletion, a GPU-memory fit warning and a "Ready offline ✓" check.
- Scanned papers are detected and parsed with OCR. Papers on arXiv can use their own LaTeX source for exact equations.

## SciSpeech-Bench

An open benchmark of how faithfully read-aloud pipelines speak math, with an analysis notebook in [marimo](https://marimo.io) (`bench/analysis.py`, static export in `bench/analysis.html`).

- **Equations:** 220 display equations from 24 open arXiv papers (115 polymers/materials, 40 physics, 35 chemistry, 30 math), with the LaTeX from the arXiv source as ground truth. Each pipeline's speech is transcribed back to LaTeX by an independent judge model from a third family (`phi4:14b`) and compared structurally.
- **Units and chemistry by sound:** 99 snippets phonemized with the voice's own phonemizer. **A generic reader mispronounces 47 % of them; SciReader 0 %** (caveat: we wrote the snippets knowing the normalizer's rules).

![SciSpeech-Bench: share of equations a listener can write back, per pipeline](bench/figures/faithfulness.png)

**What we found** (judge: `phi4:14b`, a third model family; details and caveats in [`bench/README.md`](bench/README.md)):
- **Unverified local LLM narration silently changes about 1 in 3 equations.** On the 63 equations the judge can reliably transcribe (it reconstructs their rule-based reading), `qwen3.5:9b` narrations were written back faithfully only 64 % of the time; `qwen3.5:4b` 57 %.
- **Verification fixes most of it.** The gate catches about 4 in 5 of those errors (recall 78–81 %), raising faithful readings to **89 %** (9B) and **87 %** (4B), while still using natural AI narration for 45 % of all equations (99 of 220) and the rule-based reading for the rest.
- **A generic reader's text-layer reading** is faithful for only 41 % of those equations.
- Over all 220 equations the judge itself is the ceiling (it fails on many long equations even from a perfect reading), but the order holds: naive 24 % < rules 29 % < LLM 32 % < **LLM + verify 38 %**.

In the left panel, rules = 100 % by construction (that is how the subset is defined). The analysis is a [marimo](https://marimo.io) notebook: open `bench/analysis.html` without installing anything, or run `marimo edit bench/analysis.py` to filter by field and judge.

## How it works

```mermaid
flowchart LR
  PDF[PDF] --> D[Docling: layout, reading order, formula LaTeX]
  PDF --> P[PDFium: glyph boxes]
  D --> B[Document builder: sections, sentences, skips, citations]
  P --> B
  B --> N[Science normalizer + lexicon]
  N --> K[Kokoro TTS + word timings]
  B --> E[Equations: SRE rules / LLM narration]
  E --> V[Verifier: back-transcription + MathML compare]
  K --> UI[React + pdf.js reader]
  V --> UI
  B --> AI[Ollama: figures, explain, ask, summaries]
  AI --> UI
```

- `backend/` (Python 3.12, FastAPI, uv): `parsing/` (Docling adapter, document builder, PDFium alignment, LaTeX cleanup, arXiv source mode), `speech/` (sentence splitter, English normalizer, lexicon, math speech client, pronunciation review), `tts/` (Kokoro engine, voice registry, audio cache), `llm/` (Ollama provider, verified narration, figures, explain/ask), `api/`, `store/`.
- `frontend/` (Vite, React, TypeScript, pdf.js, KaTeX, zustand). The UI follows the system theme; the PDF page is never darkened.
- `tools/math-speech/`: a small Node helper (MathJax + Speech Rule Engine) over JSON lines.
- `bench/`: SciSpeech-Bench data, scripts, results, figures and the marimo notebooks.

## Install and run (Windows)

Requirements: [uv](https://docs.astral.sh/uv/), Node.js LTS, git; an NVIDIA GPU helps but is optional. For the AI features, [Ollama](https://ollama.com) with `qwen3.5:9b` (reader) and `gemma4:12b` (checker); both can be downloaded from SciReader's model panel.

```powershell
git clone https://github.com/Shmiggly/SciReader
cd SciReader
./scripts/setup.ps1   # Python + Node dependencies, voice and parser models, UI build
./scripts/dev.ps1     # starts the backend and opens SciReader in its own app window
```

Development with hot reload: `./scripts/dev.ps1 -Hot`. Sample papers: `uv run --no-project python scripts/fetch_samples.py`.

Configuration lives in `.env` (see `.env.example`): data folder, model folder, Ollama URL and model names.

## Pronunciation lexicons

Entries are plain respellings ("peg-dah", "T G") with an optional IPA field; see [`lexicons/README.md`](lexicons/README.md) for the format. Share your file from the pronunciation screen and contribute field packs back. Lexicon annotations are CC BY 4.0.

## Licenses

SciReader is Apache-2.0. Dependencies and models are tracked in [`docs/LICENSES.md`](docs/LICENSES.md); the one flag is misaki's GPL-3.0 espeak-ng fallback (fine for this open-source build). Model weights are downloaded by the user and never redistributed.
