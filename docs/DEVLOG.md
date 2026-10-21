# SciReader devlog

Append-only history: what was done and what was learned, newest at the bottom. Current truth lives in `NOTES.md`. This file feeds the write-up ("what you learned").

## 2026-10-20: pre-hackathon prep

- Read the OSI Hackathon 2026 page: judging rubric (impact, innovativeness, novelty, relevance to physical sciences & math, each 1–5), submission requirements (public post with ≤ 4-min video, write-up, public repo with README), deadline Thu Oct 22 7:00 PM CDT.
- Compared two directions: (1) a science-aware read-aloud reader for papers, (2) AI safety for the physical sciences. Recommended (1), with a "verified math narration" layer as the bridge to AI reliability, and parked a sharpened version of (2) in NOTES §10.
- Landscape: closed commercial competitors exist (Paper2Audio, Audiolizer, Listening, Audeus); none is open source or local, and none reports math fidelity. MinerU 2.5 leads formula parsing benchmarks; Docling is the MIT, CPU-friendly option; Kokoro-82M is the default local TTS pick.
- Environment check: RTX 4070 12 GB, 64 GB RAM; no Python/Node/uv/gh installed yet; C: nearly full.
- Wrote NOTES.md, CLAUDE.md, docs/prompts/kickoff.md and docs/prompts/followups.md. No app code (written during the event).
- User confirmed the direction: Idea 1 + verified math narration.
- Installed the toolchain via winget: uv 0.13.4, Python 3.12.15, Node 24.20.0 LTS, gh 2.102.0. Learned that the Claude desktop app is MSIX-packaged: its shells' AppData writes are redirected to a private copy (the first uv Python install landed there and broke uv's version junction). Fixed by moving Python, the uv cache and tool dirs, the npm cache and HF_HOME to D: through user env vars.
- GPU smoke test in a scratch venv (`D:\scratch\gpu-smoke`): PyTorch 2.14.1+cu132 on the RTX 4070, plus Kokoro-82M. One sentence synthesizes in ~0.1 s (61–84× real time, 0.7 GB VRAM) with per-word timestamps, so word highlighting moved into the core slice. Learned: misaki's automatic spaCy-model download breaks in a uv venv (pin `en_core_web_sm` explicitly), and a good neural voice still says "eV" as "ee-vee" and "K" as "kay", which is concrete evidence for the science normalizer.
- User decision: the whole app runs fully offline with local models (no cloud API keys). Installed Ollama 0.40.6 with models on D:, and pulled `qwen3.5:9b` (narrator, vision, Q&A) and `gemma4:12b` (independent back-transcriber).
- Offline LLM smoke test on 8 physics/chemistry equations: all narrations faithful; 7/8 round trips exact. The miss was Planck's law: "divided by k sub B T" is ambiguous out loud, a perfect example of what verification is for. qwen3.5 described a synthetic XRD figure correctly. Learned: SymPy's LaTeX parser can't handle most physics notation (6/8 failed), so the verifier will compare canonical MathML trees instead; `ollama ps` under-reports gemma4's VRAM (~8.5 GB real), so the two LLMs must run in separate batches.
- Chose 5 sample papers (+1 backup) from the demo domain (polymers for additive manufacturing + ML), verified via OpenAlex and arXiv: licenses, LaTeX-source availability, equation and figure counts. Flagship: the CC BY physics-informed Bayesian learning paper on electrohydrodynamic polymer jet printing (33 equations). Learned: the arXiv search API rate-limited us immediately (OpenAlex is the fallback), arXiv licenses often differ from the CC BY journal version, and MDPI/Europe PMC block scripted PDF downloads.

## 2026-10-21 (just after midnight): plan walkthrough with the user

- Went through the whole build step by step and folded every decision into the kickoff prompt and NOTES §5:
  - **What it is:** a borderless app window; Apache-2.0 (commercial use stays open, so licenses are tracked).
  - **Reading:** resume where you left off; focus mode on by default; no dark page; sentence + word highlight.
  - **Voice:** heart voice; science pronunciation lexicon (PEGDA → "peg-dah", Tg → "T G").
  - **The user's ideas:** a pronunciation review screen with shareable lexicons; equation-reference and figure popups; panel-aware figure descriptions ("Fig. 3b" describes only panel b).
  - **Equations:** fallback chain verified AI → rules → "Equation N"; a "checking…" badge state.
  - **Benchmark:** analysis in a marimo notebook for the sponsor prize.
  - **Start:** kickoff 6:30 AM; questions go out as notifications.
- Measured and verified along the way:
  - Kokoro runs with `HF_HUB_OFFLINE=1` (fully offline), and all 28 English voices are cached.
  - Plain respellings work for custom pronunciations.
  - The voice's phonemizer runs without the model, which makes phoneme-level scoring of units possible.
  - Raw Kokoro says MPa as "em-pah", nm as "en em", and mW/cm² as "em double-u slash C M two".
  - qwen3.5:9b VRAM barely grows with context (4K → 32K adds ~0.9 GB), so ask-the-paper can use the whole paper instead of retrieval.
- A session with a very long context makes every step expensive; hence fresh sessions per block.
- Logged in to GitHub with gh (config on D: through GH_CONFIG_DIR), created the private repo Shmiggly/SciReader and pushed the prep commit. The repo becomes public at submission.
