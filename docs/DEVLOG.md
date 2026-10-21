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

## 2026-10-21 00:21–01:00 EDT: hackathon kickoff, M0–M3 (agent, unattended)

- The user started the session at 00:21 instead of 6:30. M0 scaffold in ~15 min: uv backend resolved first try (torch 2.14.1+cu132, Docling 2.141, Kokoro 0.9.4 with transformers 5.20), Vite 8 + React 19 + pdf.js 6 + TypeScript 7 frontend, Node math-speech helper (mathjax-full 3 + SRE 5.0-rc). All six sample PDFs fetched (the MDPI one was already downloaded by hand).
- Docling on the flagship: ~100 s on the RTX 4070 including the first model download; it found all 33 display equations, 9 figure captions, 35 references. Its formula LaTeX (CodeFormulaV2) is tokenized and sometimes garbled ("M o m t u n" for Momentum, "C h \arg e" for Charge), and one equation came out as plain text. That is exactly the failure the verifier and the benchmark are about.
- Learned: Springer Nature PDFs map inline-math glyphs to wrong code points (`¼` for `=`, `ð…Þ` for parentheses, `þ` for `+`); a one-to-one translation table fixes most of it. Superscript citations show up in Docling text as " 18 ."; PDFium's `FPDFText_GetFontSize` returns 1.0 there (text-matrix scaling), so superscripts are detected from loose glyph box heights and raised baselines instead (63 citation markers found and dropped from speech).
- Kokoro in the app: 10–13 s cold load at startup (warmed in a background thread), then ~0.06 s per sentence; word timestamps map back to PDF word boxes through the normalizer's span map.
- M2 vertical slice verified in the browser pane: click a sentence → audio starts, sentence + word highlight on the PDF, focus mode, auto-follow, prefetch of the next sentences, playback flows through paragraphs. M3: model manager (voices with preview/default/delete, Ollama models with pull progress and job assignment, parser status, storage, "Ready offline ✓"), `scripts/dev.ps1` (Edge `--app` window) and `scripts/setup.ps1`.
- Big context + subagent is expensive; keep outputs small.

## 2026-10-21 02:13–03:00 EDT: M4 AI layer, M6 features, M5 benchmark (agent, unattended)

- Verified equation narration on the flagship: 33 equations in 99 s → 5 verified, 2 uncertain, 22 rules fallback, 4 unreadable. Learned: the verifier mostly rejects because the *parser's* LaTeX is noisy (OCR of a Springer PDF), not because the narrator is bad; and qwen3.5:9b did silently drop structure (it read `\Theta|_{Z=0} = 0` as "Theta sub Z equals zero equals zero"), which the round trip caught.
- Figure narration: 22 first-mention targets (panels included) described by qwen3.5:9b from page crops in ~4 min; the panel-b description of Fig. 3 talked only about panel b.
- Ask the paper with the whole paper in context (80K chars) and sentence IDs: 10.6 s for the first question, 1.8 s after (Ollama prefix cache), with correct citations.
- Pronunciation review: candidates = abbreviations, formulas and words outside misaki's dictionary (with suffix stripping, otherwise every plural is flagged). A saved respelling applied immediately and word highlighting still mapped 23/23 words.
- SciSpeech-Bench data: OpenAlex search + arXiv `/src` (many hits are PDF-only); simple `
ewcommand` expansion; 220 equations from 24 papers. Units by sound with misaki + espeak fallback (exactly the voice's G2P): generic 47 % vs SciReader 0 % mispronounced on 99 snippets (caveat: snippets written by us, knowing the rules).
- Benchmark design issue caught: the in-app checker (gemma4:12b) can't also be the faithfulness judge, so the benchmark uses phi4:14b (third model family) as judge. Two judges at ~0.4 calls/s would take 2.5 h, so the secondary judge was dropped.
- With a ~500K-token context every step is expensive; big batched steps matter.

## 2026-10-21 03:00–03:25 EDT: benchmark results, M6 finish, M7 drafts

- First scoring of SciSpeech-Bench said every pipeline was ~15 % faithful, even the naive glyph string. The cause was measurement: the judge wrapped answers in `\( \)`, added stray "-" lines and repeated equations, and the comparator treated `	ext{MAE}` and `MAE` as different. Fixing extraction and comparing text letter by letter gave a sensible order (naive 24 < rules 29 < LLM 32 < verified 38 % over all 220), with the judge as the ceiling.
- Controlling for the judge (the 63 equations whose rule-based reading it reconstructs): unverified qwen3.5:9b 64 % faithful, with the gate 89 %; 4B 57 % → 87 %; naive 41 %. A manual check of 30 narrations: the judge's "faithful" calls were right 14/15, its "error" calls only 7/15; none of the 15 gate-verified narrations was wrong, and all 8 real errors were rejected or flagged. Typical silent LLM errors: an invented fraction, a factor moved into a denominator, a superscript index read as a plain number, ambiguous fraction or exponent extents.
- M6 finished: E equation popup, citation hover, text view with dyslexia-friendly fonts, audiobook export (libsndfile's MP3 encoder, no new dependency), auto-pause, scanned-PDF OCR (RapidOCR on torch, detected automatically), arXiv source mode (7 of 11 equations aligned on the GNN paper).
- Verified the production path: the backend serves the built UI on one port with zero non-localhost requests; `dev.ps1 -NoBrowser` starts and serves it.

## 2026-10-21 07:00–07:15 EDT: checkpoint walkthrough (fresh session)

- Walked through the flagship in the browser pane. Click-to-read, sentence + word highlight, focus mode, the Fig. 3b popup (panel-b description correct), the verified-equation popover, Explain (~15 s with citation chips), pronunciation review, text view and the model manager all work; 309 backend tests pass.
- Found that the gate only checks the narration against the *parsed* LaTeX. On the flagship, Docling folded the bold label "Charge:" into equation 8, and the app speaks "C times h times arg of e times sigma equals R" under a "? uncertain" badge.
- Found that "uncertain" narrations (same symbols, different grouping) are spoken, although grouping is exactly where LLMs fail silently: in the 30-item manual check, 1 of the 2 uncertain items was a real error (Lorentz–Lorenz with Nα moved into the denominator).
- Springer PDFs also garble inline math in the text layer ("f x ( )" for f(x), ";" for ",", "=" for "…"), and dehyphenation drops the hyphen in compounds split across lines ("physicsbased"). Both reach the voice.
