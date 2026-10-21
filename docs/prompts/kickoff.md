# SciReader: Hackathon Kickoff Brief

> **How to use:** fill in the "Before sending" block, then paste everything from the horizontal rule down as the first message of a **fresh** Claude Code session opened in `D:\Github\SciReader\SciReader`, with **auto** permission mode (not plan mode). Blanks you leave empty are treated as unknown, and the agent proceeds without them.

---

## Before sending (2 minutes)

- Domain: ______
- Papers I want in `samples/` (arXiv IDs, or PDFs I already dropped in `samples/`): ______
- LLM access: `ANTHROPIC_API_KEY` in `.env`? yes / no. Other credits or local models: ______
- Sponsor prize rules learned at kickoff (Valency / Adaption / marimo): ______
- Anything else that changed since last night: ______

---

## 0. How you'll work today

I'm doing the OSI Hackathon 2026 solo (~36 h, **deadline Thu Oct 22, 7:00 PM CDT**; check the system clock for my local time). **I'm leaving right after sending this and will be unreachable for about 3 hours.** You're on your own until I'm back. The hackathon facts, judging rubric, my environment and past decisions are in `NOTES.md` (auto-loaded through `CLAUDE.md`). Read it first.

Rules for the unattended stretch:

1. **Never wait on me.** Don't use AskUserQuestion, plan mode, or anything that needs my approval: it would sit there for 3 hours. When something is ambiguous, pick the option that best serves the spec below, record it in `NOTES.md` §Decision log with one line of reasoning, and keep going. Real questions for me go in `NOTES.md` §Open questions.
2. **Don't end your turn early.** Work through the milestones in §7 in order. Stop only when M3 is done and verified, or when you're blocked on something only I can do (log it, then switch to the next unblocked task). If M3 is done before I'm back, continue into M4 and M5.
3. **Keep `main` runnable.** Vertical slice first, depth later. Commit after every working step with a clear message, and **push to `origin` (private repo `Shmiggly/SciReader`) at least after every milestone**: it's my backup and how I watch progress. If a push fails, log it in NOTES and keep working; never force-push.
4. **Time-box.** If a dependency or approach fights you for more than ~30 minutes, take the fallback named in this spec (or the simplest thing that works), log it, and move on.
5. **No interactive or elevated commands.** Always use non-interactive flags. Nothing that needs admin or UAC. Run long installs and downloads in the background and work on something else meanwhile.
6. **Parallelize with subagents** when work is independent and lives in separate directories (for example: the normalizer and its tests in `backend/scireader/speech/`, the parser bake-off in `backend/scireader/parsing/`, benchmark data collection in `bench/`). You own the integration.
7. **Verify for real.** Run the tests, start the app, open it in the browser pane (`.claude/launch.json` + preview), click through it like a user, and save one screenshot per milestone to `docs/screenshots/`. I'll use them for the video and to check progress.
8. **Disk:** model weights and caches go on D: (`HF_HOME=D:\models\hf` if not already set; app models in `D:\models\scireader`). C: is 89 % full. Never commit weights, large PDFs, `.env` or secrets.
9. **Memory across sessions:** `NOTES.md` is current truth. Update it at every milestone (status, decisions, gotchas, how to run) and delete what's no longer true. `docs/DEVLOG.md` is append-only history (what was done, what was learned) and feeds the write-up.
10. Load the `claude-api` skill before writing Claude API code.

## 1. The problem (also the pitch)

Long text is hard to follow, and scientific articles are much harder: readers lose their place in the lines and reread the same lines over and over. Audiobooks running in the background changed this for books. Every open-source read-aloud tool is bad at papers:
- they start from the first character and read everything (running headers, page numbers, citation brackets, affiliations, the reference list);
- equations come out as gibberish or are skipped;
- you can't easily start from the section or sentence you want;
- the voices are bad.

Commercial apps (Paper2Audio, Audiolizer, Listening, Audeus, Speechify, ElevenReader) are closed, cloud-only and subscription-based. They can't be trusted with unpublished manuscripts or papers under review, and none of them says how faithfully it renders the math.

Researchers with dyslexia, ADHD, low vision or blindness, non-native English readers, and anyone who wants to "read" a paper on a commute hit the same wall. In physics, chemistry, materials science and mathematics, the wall is specifically **equations, units, chemical formulas and figures**.

## 2. What we're building

**SciReader** is an open-source, local-first, science-aware reading companion. The PDF stays in front of me exactly as published. In the background it's linked to a structured, parsed copy (text blocks, sections, equations as LaTeX, figures, captions, tables, references, all with page coordinates), so the audio follows the paper's real structure and the current sentence is highlighted on the PDF itself.

Design principles (use them to resolve ambiguity):
- **PDF-first:** I always see the real paper; highlights and clicks happen on it.
- **Start anywhere:** clicking a sentence, paragraph or section heading starts reading from there, instantly.
- **Read like a scientist:** equations, units, chemical formulas, Greek letters, scientific notation, Fig./Eq./Ref. are spoken the way a physicist or chemist would say them aloud.
- **Faithful by default:** body text is read verbatim (deterministic normalization only). AI touches only what can't be read verbatim (equations, figures, tables) and on-demand features. Every AI rewrite of math is verified against the source (§4 P1). I can always see what is being spoken ("spoken text" on hover).
- **Local & private:** runs on my laptop (RTX 4070 12 GB, 64 GB RAM). AI providers are pluggable: Claude API when a key is present, any OpenAI-compatible local server (Ollama, LM Studio) otherwise, and a fully working no-LLM mode.
- **One-click models:** TTS voices and models are downloaded and managed inside the app, with no terminal.
- **Focus aids:** designed for people who lose their place, with sentence/line focus, dimming and auto-follow.

## 3. Why this can win (map to the rubric in NOTES.md)

- **Relevance (target 5):** reading physical-science papers aloud fails on math, units and chemistry, and that's exactly what we attack. Demos use real physics, chemistry, materials and math papers. Relevance is our weakest criterion, so science-specific features get priority over generic polish.
- **Novelty (target 4–5):** *verified math narration*. It's the first read-aloud tool that checks its own AI narration against the source LaTeX and refuses to speak math it can't verify. Plus an open benchmark.
- **Innovativeness:** one loop combining document-layout AI, local neural TTS, LLM narration and symbolic verification.
- **Impact:** clear users (researchers with reading difficulties, visually impaired scientists, anyone with a commute) and a clear change: papers become listenable without losing fidelity, open source and local so labs can use it on unpublished work.
- **The finding (SciSpeech-Bench, §6):** how often generic pipelines and unverified LLM narration silently change the math, and how much verification fixes it. That's our "discovery" figure.

## 4. Feature spec

P0 = must be in the demo. P1 = should. P2 = stretch. Build in that order.

### P0: core reader
- **Open a paper:** drag & drop or file picker; paste an arXiv ID/URL (download the PDF). A local library list of opened papers (cached).
- **Parse → Document JSON** (schema in §5): block types, reading order, page + bbox, sentences, equations (LaTeX), figures + captions, tables, footnotes, page headers/footers, bibliography entries. Cache by file hash; show progress while parsing.
- **Viewer:** PDF rendered with pdf.js, continuous scroll and zoom; an overlay layer maps blocks and sentences to rectangles; an outline sidebar of sections (click to jump or start reading).
- **Click-to-read:** clicking any sentence starts playback there. Section headings in the outline also start playback.
- **Playback bar:** play/pause, previous/next sentence, previous/next paragraph, next section, speed 0.5–3× (pitch-preserving), voice picker, volume. Keyboard: Space play/pause, ←/→ sentence, Shift+←/→ paragraph, +/- speed. Media Session API so headset and media keys work.
- **Highlighting:** the current sentence is highlighted on the PDF (word-level if the TTS gives timestamps, else sentence-level). Auto-scroll follows. **Focus mode** dims everything except the current paragraph and puts a reading ruler on the current line.
- **Smart skipping** (each a toggle, sensible defaults): page headers, footers and page numbers; inline citation markers (`[12]`, `[3–5]`, `(Smith et al., 2020)`, superscript numeric citations, detectable from font size and baseline); author affiliations and emails; the bibliography; figure and table bodies (captions are read). Acknowledgments are read by default.
- **Science-aware text normalization** (deterministic, no LLM): units and compound units (mol L⁻¹, cm⁻¹, m s⁻², eV, meV, Å, K, °C, GPa, kJ/mol), scientific notation (1.2 × 10⁻³, 1.2e-3), ± ≈ ~ ∝ ≤ ≥, ranges (5–10 K), Greek letters, sub/superscripts, chemical formulas (H₂O, Fe₂O₃, CO₂, NH₄⁺, Ca²⁺), isotopes (¹³C), abbreviations (e.g., i.e., et al., Fig., Figs., Eq., Eqs., Ref., Sec., ca., vs., cf.), and ambiguity traps ("5 min" vs "min(x)", "Si" vs "S i"). Display text and spoken text are stored separately. pytest suite with **≥ 100 cases**.
- **Equations, deterministic baseline:** LaTeX → MathML → speech with Speech Rule Engine (ClearSpeak), run through a small Node helper. Inline math is normalized in place. Display equations are announced ("Equation 3:") with modes: read in full / brief / skip.
- **Local TTS:** Kokoro-82M (Apache-2.0) as the default engine, on GPU if available, else CPU. Synthesize per sentence, stream, prefetch the next 3–5 sentences, cache audio on disk keyed by (model, voice, speed, spoken text). **Target: < 1.5 s from click to sound.**
- **Model manager:** a panel listing TTS engines and voices from a registry (name, size, license, languages, quality notes, GPU/CPU), with a Download button and progress bar, Delete, and "Set default". The registry is a JSON file so new engines are easy to add; engines sit behind an interface. Start with Kokoro. Add a second engine only after P0 is done: Piper for low-end CPUs, or Chatterbox / Qwen3-TTS for quality. Check licenses and avoid non-commercial ones (e.g. XTTS-v2) as the default.

### P1: AI layer + reflow
- **Provider abstraction:** `anthropic` (claude-sonnet-5-5 for quality tasks, claude-haiku-5-5 for bulk narration) when `ANTHROPIC_API_KEY` is set; `openai-compatible` base URL (Ollama, LM Studio) otherwise; `none` disables AI features gracefully with a hint. Cache every LLM response on disk (hash of model + prompt). Use prompt caching for the paper text with Claude.
- **Verified equation narration (the signature feature):**
  1. A narrator LLM turns LaTeX plus surrounding context into natural speech ("E equals m c squared"; "the Hamiltonian H equals the sum over i of p i squared over 2 m").
  2. An independent back-transcriber (separate call that never sees the original LaTeX) turns that speech back into LaTeX.
  3. Compare: symbolic equivalence with SymPy when both sides parse (`sympy.parsing.latex` with the lark backend, or latex2sympy2), otherwise normalized-token / tree-edit similarity.
  4. Verdict: **verified ✓** (use LLM speech), **uncertain ?** (use LLM speech, show a badge), **failed ✗** (fall back to SRE speech, show a badge).

  Precompute for all equations in the background after parsing. Each equation gets a badge; clicking it shows the LaTeX (KaTeX), the spoken text and the verdict.
- **Figure narration:** crop the figure and caption from the page image and ask a vision model for a short description (plot type, axes, units, key trends, panels). Read it when playback reaches the figure, or (setting) when the text first references "Fig. N". Always labeled, in speech ("AI description of Figure 2: …") and in the UI.
- **Explain selection:** select text or an equation → "Explain" → a short plain-language explanation grounded in the paper, with citation chips that jump to and highlight the source spans. Can be read aloud.
- **Ask the paper:** a Q&A panel grounded in the parsed document. Answers cite spans (click → highlight on the PDF) and can be read aloud.
- **Listen to a summary:** a 1–2-minute spoken summary per section or for the whole paper, clearly labeled as AI.
- **Citations:** hover or click an in-text citation to see the bibliography entry, with a DOI/arXiv link when present.
- **Reflow view:** a clean single-column text view of the parsed document (adjustable font, size, line spacing, width; dyslexia-friendly font option), synced with the PDF (same highlight, click-to-read). Toggle or side-by-side.

### P2: stretch (pick by demo value)
- **Audiobook export:** MP3/M4B with one chapter per section, for listening away from the screen.
- **arXiv source mode:** when the paper is on arXiv, fetch the LaTeX source and use its exact equations, aligned to the parsed equation blocks. Perfect math without OCR.
- More TTS engines (voice cloning, multilingual); per-section voice and speed.
- Desktop packaging (Tauri or Electron), only after everything else.
- A marimo notebook for the benchmark analysis, if the marimo sponsor prize rules make it worthwhile.

## 5. Architecture (defaults; deviate only with a logged reason)

- **Monorepo:**
  - `backend/`: Python 3.12 managed with uv; FastAPI + uvicorn; package `scireader` with `parsing/` (parser adapters + Document builder), `speech/` (sentence splitter, normalizer, math speech), `tts/` (engine interface, `registry.json`, downloader, audio cache), `llm/` (providers, narration, verification, QA), `api/` (routes), `store/` (document cache on disk). Tests in `backend/tests/`.
  - `frontend/`: Vite + React + TypeScript + pdfjs-dist, a small store (Zustand), KaTeX for math display. Minimal, clean UI with dark mode.
  - `tools/math-speech/`: Node helper (speech-rule-engine + mathjax-full), called from the backend in batches over stdin/stdout JSON.
  - `bench/`: SciSpeech-Bench (data, scripts, results, figures).
  - `scripts/`: `dev.ps1` (starts backend + frontend), `setup.ps1` (first-time setup).
  - `docs/`: `DEVLOG.md`, `screenshots/`, `writeup.md`, `demo_script.md`, `prompts/`.
- **Document JSON (v1):**
  ```
  { id, title, authors, source: {type: "file"|"arxiv", ref},
    pages: [{index, width, height}],
    outline: [{id, title, level, block_id}],
    blocks: [{ id, type: "title|heading|abstract|paragraph|list_item|equation|figure|caption|table|footnote|page_header|page_footer|bib_entry|other",
               page, bbox: [x0, y0, x1, y1],        // PDF points, origin top-left
               section_id, text, latex?, figure_id?, skip_reason?,
               sentences: [{ id, text, spoken, rects: [[page, x0, y0, x1, y1], ...] }] }],
    figures: [{id, label, page, bbox, caption_block_id, description?}],
    bibliography: [{id, label, text, doi?, arxiv?}],
    citations: [{sentence_id, span: [start, end], bib_ids}] }
  ```
  The frontend converts PDF points to viewport pixels with the pdf.js viewport scale.
- **Parsing:** `Parser.parse(pdf_path) -> Document`. Implement **Docling** first (MIT, Windows-friendly; layout labels, reading order, bbox, formula LaTeX through its formula enrichment). Then time-box a **MinerU 2.5** attempt (best formula accuracy in 2026 benchmarks, GPU) on the same samples, and keep whichever gives better reading order and equations on our samples. Log the comparison in NOTES.
  Sentence rects: get word or char boxes with pypdfium2 (or the pdf.js text content) inside each block's bbox, and align them to the sentence text with fuzzy character alignment. Fall back to the block bbox if alignment fails.
- **Speech pipeline:** block → sentences (rule-based splitter aware of "Fig. 2", "et al.", "e.g.", decimals) → normalizer → math speech (inline and display) → spoken text → TTS.
- **TTS:** engine interface `synth(text, voice, speed) -> (audio, word_timestamps | None)`. For Kokoro, check whether the `kokoro` package's `KPipeline` exposes per-token timestamps for English (I believe tokens carry `start_ts`/`end_ts`, but verify). If yes, add word highlighting; if not, sentence level only. Endpoint `GET /api/tts/{doc}/{sentence_id}?voice&speed` returns audio (WAV or Opus) plus timestamps. Downloads go through `huggingface_hub` with progress over SSE.
- **GPU budget (12 GB):** load lazily. Never keep the parser VLM, the TTS model and a local LLM in VRAM at the same time; unload the parser after parsing.
- **Config:** `.env` (gitignored) and `.env.example`: `ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `MODELS_DIR`, `HF_HOME`.
- **Licenses:** everything we depend on by default must be compatible with an open-source repo; list each dependency's license in the README. Avoid Marker as default (weights restricted for organizations above revenue thresholds) and XTTS-v2 (non-commercial).

## 6. SciSpeech-Bench (the measurable result)

Goal: one clear figure for the write-up and a reusable open benchmark.

- **Data:** ~200 display equations, plus ~100 inline expressions and ~100 unit/chemistry snippets, from 15–25 open-access arXiv papers across physics, chemistry, materials science and math (prefer CC-BY). Store arXiv IDs and extracted LaTeX, not PDFs. **Ground truth is the LaTeX from the arXiv source tarball, not OCR.** Respect arXiv etiquette: ≤ 1 request per 3 s, descriptive User-Agent.
- **Conditions:**
  - (a) naive: what a generic reader speaks (the PDF text layer of the equation region);
  - (b) SRE ClearSpeak from the source LaTeX;
  - (c) LLM narration, unverified;
  - (d) LLM narration + verification gate (fallback to SRE);
  - (e) optional: the full SciReader pipeline from the parsed PDF (OCR LaTeX → speech), which also measures the parser's math accuracy.
- **Metrics:**
  - **Faithfulness:** back-transcription with a fixed, independent model, then SymPy equivalence or normalized similarity against the ground-truth LaTeX.
  - **Naturalness:** LLM-judge pairwise preference on a subset, plus a ~30-item blind subset I'll rate myself later (make a tiny rating page or CSV).
  - Report the **silent error rate of unverified LLM narration** and the verifier's precision/recall at catching errors.
- **Outputs:** `bench/results/*.json`, `bench/figures/faithfulness.png` (+ `.svg`), a short `bench/README.md`. Keep API spend sane: cache everything, use the cheaper model for bulk work, cap runs.

## 7. Milestones (times from kickoff; adjust if behind, but keep the order)

- **M0 (0:00–0:20) Setup:** verify the toolchain (uv, Python 3.12, Node LTS, git); scaffold the monorepo, `.gitignore`, `.env.example`, README skeleton, `.claude/launch.json` for the dev servers. Download 3–5 sample papers into `samples/` (from "Before sending"; otherwise pick equation-heavy open-access arXiv papers in physics, physical chemistry, materials and math; gitignore PDFs that aren't CC-BY). Start model downloads in the background (Kokoro, parser models). Commit.
- **M1 (0:20–1:15) Parse + speak, backend only:** Docling → Document JSON for all samples, plus an inspection script that prints block types and reading order; sentence splitter; normalizer + tests (subagent); Kokoro synthesizes a sentence to WAV; MinerU bake-off, time-boxed (subagent, separate directory). Commit.
- **M2 (1:15–2:15) Vertical slice:** frontend PDF viewer + overlays + click-to-read + playback bar + sentence highlight + auto-scroll + prefetch + audio cache; skip headers, footers, citations and bibliography. Screenshot. Commit. **This is the minimum I want to see when I'm back.**
- **M3 (2:15–3:00) Math + models + focus:** SRE equation speech and equation modes; model manager panel with download progress; focus mode; outline sidebar with click-to-read. Commit.
  Then write `NOTES.md` §0 "When you're back": a 5-line summary, how to launch, a 2-minute test script, decisions to review, questions. Update §1 Status and §8 Roadmap.
- **M4 AI layer:** provider abstraction, verified equation narration with badges, figure narration, explain/ask with span citations, summaries.
- **M5 SciSpeech-Bench** and its figure.
- **M6 Depth:** reflow view, word-level highlight, audiobook export, a second TTS engine, arXiv source mode (pick by demo value).
- **M7 Ship (start no later than 8 h before the deadline; feature freeze at T-6 h):** README (pitch, GIF/screenshots, install, features, architecture diagram, licenses, benchmark result); `docs/writeup.md` (one page + figure: what we built, what we learned); `docs/demo_script.md` (≤ 4-min video, beat by beat); repo ready to go public (no secrets, no non-redistributable PDFs, no weights). **The GitHub repo `Shmiggly/SciReader` is private until then.** After I OK the audit, make it public (see the Ship prompt in `docs/prompts/followups.md`).

## 8. Definition of done for the demo

On a real, equation-heavy physics or chemistry paper:
1. Open it; the outline appears after a parse of about a minute.
2. Click a sentence in Section 2: audio starts within ~1.5 s, the highlight on the PDF tracks the speech, and the page auto-scrolls.
3. Citation markers aren't read; running headers and page numbers are skipped.
4. An equation is spoken naturally with a ✓ verified badge, and I can see its LaTeX and spoken text.
5. A figure gets a spoken, labeled AI description.
6. I select a confusing sentence, hit "Explain", and get a grounded answer with a clickable source chip.
7. I download a second voice in the model manager and switch to it.
8. Everything works offline except Claude calls (and fully offline with a local LLM).

## 9. Don'ts

- Don't let an LLM paraphrase body text that's being read as the paper. Verbatim + normalization only.
- Don't read the bibliography, page furniture or citation markers by default.
- Don't build accounts, cloud sync or telemetry.
- Don't polish visuals before M2 works end to end.
- Don't start Electron/Tauri before M5.
- Don't commit secrets, model weights or PDFs we can't redistribute.
- Don't stay stuck for more than ~30 minutes: take the fallback and log it.

## 10. Demo story (design the product for this)

- **0:00–0:30:** the problem: readers reread the same line; audiobooks help; existing readers fail on papers (show a generic reader mangling an equation and reading "[12]").
- **0:30–2:30:** SciReader on a real paper: click to start anywhere, highlight + focus mode, an equation spoken naturally with its verification badge, a figure described, explain/ask with citations, a new voice in one click, all local.
- **2:30–3:30:** the SciSpeech-Bench figure: generic pipelines mangle X % of equations, unverified LLM narration silently alters Y %, verification catches Z %.
- **3:30–4:00:** open source, local, who it helps, what's next.

**Start now:** set `NOTES.md` §1 Status to "Hackathon started, M0 in progress", then go.
