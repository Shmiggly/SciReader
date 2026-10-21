# SciReader: Hackathon Kickoff Brief

> **How to use:** fill in the "Before sending" block, then paste everything from the horizontal rule down as the first message of a **fresh** Claude Code session opened in `D:\Github\SciReader\SciReader`, with **auto** permission mode (not plan mode). Blanks you leave empty are treated as unknown, and the agent proceeds without them.
>
> **Before starting the session:** restart the Claude app (so it picks up the new env vars), check that the Ollama icon is in the system tray, open the session **directly on the repo folder, not in a worktree** (so commits land on `main`), and pick **auto** in the message box (new sessions default to asking for permission).

---

## Before sending (2 minutes)

- Domain: ______
- Papers I want in `samples/` (arXiv IDs, or PDFs I already dropped in `samples/`): ______
- LLM access (fixed, nothing to fill): **no cloud API, no key.** Everything runs locally; Ollama already has `qwen3.5:9b` and `gemma4:12b`.
- Sponsor prize rules learned at kickoff (Valency / Adaption / marimo): ______
- Anything else that changed since last night: ______

---

## 0. How you'll work today

I'm doing the OSI Hackathon 2026 solo (~36 h, **deadline Thu Oct 22, 7:00 PM CDT**; check the system clock for my local time). **I'm leaving right after sending this and will be unreachable for about 3 hours.** You're on your own until I'm back. The hackathon facts, judging rubric, my environment and past decisions are in `NOTES.md` (auto-loaded through `CLAUDE.md`). Read it first.

Rules for the unattended stretch:

1. **Never wait on me.** Don't use AskUserQuestion, plan mode, or anything that needs my approval: it would sit there for 3 hours. When something is ambiguous, pick the option that best serves the spec below, record it in `NOTES.md` §Decision log with one line of reasoning, and keep going. Real questions for me go in `NOTES.md` §Open questions.
2. **Don't end your turn early.** Work through the milestones in §7 in order. Stop only when M3 is done and verified, or when you're blocked on something only I can do (log it, then switch to the next unblocked task). If M3 is done before I'm back, continue into M4 and M5.
3. **Keep `main` runnable.** Vertical slice first, depth later. Commit after every working step with a clear message, and **push to `origin` (private repo `Shmiggly/SciReader`) at least after every milestone**: it's my backup and how I watch progress. If a push fails, log it in NOTES and keep working; never force-push. Work on `main`. Tag every milestone that works end to end (`m0-setup`, `m1-backend`, `m2-slice`, …, and `demo-ready` before the freeze) and push the tags, so I can roll back to a working demo with one command. Use a short-lived branch only for a risky swap, such as replacing the parser.
4. **Time-box.** If a dependency or approach fights you for more than ~30 minutes, take the fallback named in this spec (or the simplest thing that works), log it, and move on.
5. **No interactive or elevated commands.** Always use non-interactive flags. Nothing that needs admin or UAC. Run long installs and downloads in the background and work on something else meanwhile.
6. **Use subagents sparingly.** Each subagent re-reads the project from scratch. Run at most 2 at a time, and only for chunks that are independent and live in separate directories (for example: the normalizer and its tests in `backend/scireader/speech/`, the parser bake-off in `backend/scireader/parsing/`). You own the integration.
7. **Verify for real.** Run the tests, start the app, open it in the browser pane (`.claude/launch.json` + preview), click through it like a user, and save one screenshot per milestone to `docs/screenshots/`. I'll use them for the video and to check progress.
8. **Disk:** model weights and caches go on D: (`HF_HOME=D:\models\hf` if not already set; app models in `D:\models\scireader`). C: is 89 % full. Never commit weights, large PDFs, `.env` or secrets.
9. **Memory across sessions:** `NOTES.md` is current truth. Update it at every milestone (status, decisions, gotchas, how to run) and delete what's no longer true. `docs/DEVLOG.md` is append-only history (what was done, what was learned) and feeds the write-up.
10. **Fully offline at runtime.** The app must work with Wi-Fi off: no cloud APIs, no CDN links, no runtime downloads. LLMs run through Ollama on `http://127.0.0.1:11434`. Don't build anything that needs a cloud API key.

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
- **Fully offline & private:** runs entirely on my laptop (RTX 4070 12 GB, 64 GB RAM) with Wi-Fi off. All AI is local: Kokoro for speech; Ollama for LLMs (`qwen3.5:9b` narrates, describes figures and answers questions; `gemma4:12b` independently back-transcribes for verification). With Ollama off, the reader still fully works and only the AI features are disabled. Importing from arXiv is the only feature that needs a network, and it fails gracefully offline.
- **One-click models:** TTS voices and models are downloaded and managed inside the app, with no terminal.
- **Focus aids:** designed for people who lose their place, with sentence/line focus, dimming and auto-follow.

## 3. Why this can win (map to the rubric in NOTES.md)

- **Relevance (target 5):** reading physical-science papers aloud fails on math, units and chemistry, and that's exactly what we attack. Demos use real physics, chemistry, materials and math papers. Relevance is our weakest criterion, so science-specific features get priority over generic polish.
- **Novelty (target 4–5):** *verified math narration*. It's the first read-aloud tool that checks its own AI narration against the source LaTeX and refuses to speak math it can't verify. Plus an open benchmark.
- **Innovativeness:** one loop combining document-layout AI, local neural TTS, LLM narration and symbolic verification.
- **Impact:** clear users (researchers with reading difficulties, visually impaired scientists, anyone with a commute) and a clear change: papers become listenable without losing fidelity, open source and fully offline, so labs can use it on unpublished work, on a plane, or under data policies that forbid cloud AI.
- **The finding (SciSpeech-Bench, §6):** how often generic pipelines and unverified LLM narration silently change the math, and how much verification fixes it. That's our "discovery" figure.

## 4. Feature spec

P0 = must be in the demo. P1 = should. P2 = stretch. Build in that order.

### P0: core reader
- **Open a paper:** drag & drop or file picker; paste an arXiv ID/URL (download the PDF). A local library list of opened papers (cached).
- **Parse → Document JSON** (schema in §5): block types, reading order, page + bbox, sentences, equations (LaTeX), figures + captions, tables, footnotes, page headers/footers, bibliography entries. Cache by file hash; show progress while parsing.
- **Viewer:** PDF rendered with pdf.js, continuous scroll and zoom; an overlay layer maps blocks and sentences to rectangles; an outline sidebar of sections (click to jump or start reading).
- **Click-to-read:** clicking any sentence starts playback there. Section headings in the outline also start playback.
- **Playback bar:** play/pause, previous/next sentence, previous/next paragraph, next section, speed 0.5–3× (pitch-preserving), voice picker, volume. Keyboard: Space play/pause, ←/→ sentence, Shift+←/→ paragraph, +/- speed. Media Session API so headset and media keys work.
- **Highlighting:** the current sentence is highlighted on the PDF, and the current word within it (Kokoro returns per-word timestamps, verified on this machine). Auto-scroll follows. **Focus mode** dims everything except the current paragraph and puts a reading ruler on the current line.
- **Smart skipping** (each a toggle, sensible defaults): page headers, footers and page numbers; inline citation markers (`[12]`, `[3–5]`, `(Smith et al., 2020)`, superscript numeric citations, detectable from font size and baseline); author affiliations and emails; the bibliography; figure and table bodies (captions are read). Acknowledgments are read by default.
- **Science-aware text normalization** (deterministic, no LLM): units and compound units (mol L⁻¹, cm⁻¹, m s⁻², eV, meV, Å, K, °C, GPa, kJ/mol), scientific notation (1.2 × 10⁻³, 1.2e-3), ± ≈ ~ ∝ ≤ ≥, ranges (5–10 K), Greek letters, sub/superscripts, chemical formulas (H₂O, Fe₂O₃, CO₂, NH₄⁺, Ca²⁺), isotopes (¹³C), abbreviations (e.g., i.e., et al., Fig., Figs., Eq., Eqs., Ref., Sec., ca., vs., cf.), and ambiguity traps ("5 min" vs "min(x)", "Si" vs "S i"). Display text and spoken text are stored separately. pytest suite with **≥ 100 cases**.
- **Equations, deterministic baseline:** LaTeX → MathML → speech with Speech Rule Engine (ClearSpeak), run through a small Node helper. Inline math is normalized in place. Display equations are announced ("Equation 3:") with modes: read in full / brief / skip.
- **Local TTS:** Kokoro-82M (Apache-2.0) as the default engine, on GPU if available, else CPU. Synthesize per sentence, stream, prefetch the next 3–5 sentences, cache audio on disk keyed by (model, voice, speed, spoken text). **Target: < 1.5 s from click to sound.** It's realistic: the smoke test measured ~0.1 s per sentence on the RTX 4070 (60–85× real time, 0.7 GB VRAM). The cold import takes ~10 s, so load and warm up the model in the background at backend startup.
- **Model manager:** a panel listing TTS engines and voices from a registry (name, size, license, languages, quality notes, GPU/CPU), with a Download button and progress bar, Delete, and "Set default". The registry is a JSON file so new engines are easy to add; engines sit behind an interface. Start with Kokoro. Add a second engine only after P0 is done: Piper for low-end CPUs, or Chatterbox / Qwen3-TTS for quality. Check licenses and avoid non-commercial ones (e.g. XTTS-v2) as the default. The same panel lists the Ollama LLMs (installed, size) and can pull new ones through Ollama's `/api/pull` with streamed progress, so the LLM side is one-click too.

### P1: AI layer + reflow
- **LLM provider (local only):** Ollama, through its native `/api/chat` (supports `images` and `think: false`) or the OpenAI-compatible `/v1/chat/completions`; both were verified on this machine. Defaults: `qwen3.5:9b` for narration, figures, explain/ask and summaries; `gemma4:12b` for back-transcription only. Model names are configurable. When Ollama isn't running, AI features are disabled gracefully with a hint. Cache every LLM response on disk (hash of model + prompt). Use `think: false` and temperature 0 for narration and transcription. Keep the provider interface generic, but don't implement cloud providers.
- **Verified equation narration (the signature feature):**
  1. A narrator LLM turns LaTeX plus surrounding context into natural speech ("E equals m c squared"; "the Hamiltonian H equals the sum over i of p i squared over 2 m").
  2. An independent back-transcriber (separate call that never sees the original LaTeX) turns that speech back into LaTeX.
  3. Compare structurally, not with SymPy alone. In the smoke test, SymPy's LaTeX parser (lark backend) failed on 6 of 8 equations (`\Delta`, `\hbar`, `\nabla`, integrals, `\mathrm`), and raw string similarity scored a correct round trip at 0.70. Primary check: convert both LaTeX strings to MathML with MathJax (the same Node helper as SRE) and compare canonicalized trees (flatten `mrow`; unify `\varepsilon`/`\epsilon`, `\dfrac`/`\frac`, implicit vs explicit multiplication, `e^{x}`/`\exp`, `\mathrm{A}`/`A`). Secondary: SymPy equivalence or numeric spot checks, only when both sides parse.
  4. Verdict: **verified ✓** (use LLM speech) or **uncertain ?** (use LLM speech, show a badge). On a mismatch, retry once by telling the narrator what was lost (for example "make it explicit that k_B T is the whole denominator") and re-verify. Still failing → **failed ✗** (fall back to SRE speech, show a badge).

  Run it in two batches per paper (all narrations with qwen, then all back-transcriptions with gemma using `keep_alive: 0`) so the models swap once, not per equation; they don't fit in VRAM together. A smoke-test case worth showing in the demo: Planck's law, narrated as "e to the h nu divided by k sub B T", came back as `e^{h\nu/k_B T}`. The spoken form is ambiguous about the denominator, and the round trip exposes it.

  Precompute for all equations in the background after parsing. Each equation gets a badge; clicking it shows the LaTeX (KaTeX), the spoken text and the verdict.
- **Figure narration:** crop the figure and caption from the page image and ask `qwen3.5:9b` (it reads images) for a short description (plot type, axes, units, key trends, panels). In the smoke test it described a synthetic XRD plot correctly, peaks included, in ~10 s with a model swap. Read it when playback reaches the figure, or (setting) when the text first references "Fig. N". Always labeled, in speech ("AI description of Figure 2: …") and in the UI.
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
- **TTS:** engine interface `synth(text, voice, speed) -> (audio, word_timestamps | None)`. Verified with kokoro 0.9.4: each `KPipeline` result has `.tokens`, each with `.text`, `.phonemes`, `.start_ts`, `.end_ts` (seconds), so word highlighting is P0. Kokoro setup gotchas from the smoke test (details in NOTES §3): declare `en_core_web_sm` as an explicit dependency (misaki's runtime auto-download fails in a uv venv); get CUDA torch from the PyTorch index (`cu132` worked) through `[[tool.uv.index]]` + `[tool.uv.sources]`; set `HF_HUB_OFFLINE=1` once models are cached. Endpoint `GET /api/tts/{doc}/{sentence_id}?voice&speed` returns audio (WAV or Opus) plus timestamps. Downloads go through `huggingface_hub` with progress over SSE.
- **GPU budget (12 GB, measured with nvidia-smi):** other apps ~2.8 GB, `qwen3.5:9b` ~6.2 GB, `gemma4:12b` ~8.5 GB, Kokoro ~0.7 GB. While reading, keep qwen + Kokoro resident (~9.7 GB total). Load gemma only for batch verification, then unload it. Run the parser before any of them and unload it afterwards. `ollama ps` under-reports gemma4's VRAM, so trust nvidia-smi.
- **Offline checklist:** bundle the pdf.js worker and KaTeX CSS/fonts through Vite (no CDN links); bundle any web fonts locally (e.g. OpenDyslexic, OFL); SRE's locale files come from its npm package; download parser models during M0; set `HF_HUB_OFFLINE=1` at runtime; check `http://127.0.0.1:11434/api/version` at startup. Verify by checking the browser network panel for any non-localhost request.
- **Config:** `.env` (gitignored) and `.env.example`: `OLLAMA_URL`, `NARRATOR_MODEL`, `VERIFIER_MODEL`, `MODELS_DIR`, `HF_HOME`, `HF_HUB_OFFLINE`.
- **Licenses:** everything we depend on by default must be compatible with an open-source repo; list each dependency's license in the README. Avoid Marker as default (weights restricted for organizations above revenue thresholds) and XTTS-v2 (non-commercial).

## 6. SciSpeech-Bench (the measurable result)

Goal: one clear figure for the write-up and a reusable open benchmark.

- **Data:** ~200 display equations, plus ~100 inline expressions and ~100 unit/chemistry snippets, from 15–25 open-access arXiv papers across physics, chemistry, materials science and math (prefer CC-BY). Store arXiv IDs and extracted LaTeX, not PDFs. **Ground truth is the LaTeX from the arXiv source tarball, not OCR.** Respect arXiv etiquette: ≤ 1 request per 3 s, descriptive User-Agent.
- **Conditions:**
  - (a) naive: what a generic reader speaks (the PDF text layer of the equation region);
  - (b) SRE ClearSpeak from the source LaTeX;
  - (c) local LLM narration (`qwen3.5:9b`), unverified;
  - (d) the same + verification gate with one repair retry (fallback to SRE);
  - (e) optional: the full SciReader pipeline from the parsed PDF (OCR LaTeX → speech), which also measures the parser's math accuracy;
  - (f) optional: (c) and (d) with `qwen3.5:4b` too, to show how the error rate grows as the model shrinks and how much verification closes the gap.
- **Metrics:**
  - **Faithfulness:** back-transcription with a fixed, independent model (`gemma4:12b`), then the canonical MathML comparison (plus SymPy where it parses) against the ground-truth LaTeX. Have a ~30-item subset adjudicated (by me, or by careful manual inspection) to separate narrator errors from transcriber errors.
  - **Naturalness:** LLM-judge pairwise preference on a subset, plus a ~30-item blind subset I'll rate myself later (make a tiny rating page or CSV).
  - Report the **silent error rate of unverified local-LLM narration** and the verifier's precision/recall at catching errors.
- **Outputs:** `bench/results/*.json`, `bench/figures/faithfulness.png` (+ `.svg`), a short `bench/README.md`. Collecting the arXiv data needs the network once; everything after that runs locally and costs only time. Cache every model call.

## 7. Milestones (times from kickoff; adjust if behind, but keep the order)

- **M0 (0:00–0:20) Setup:** verify the toolchain (uv, Python 3.12, Node LTS, git) and that Ollama is up with both models (`ollama list`); scaffold the monorepo, `.gitignore`, `.env.example`, README skeleton, `.claude/launch.json` for the dev servers. Download 3–5 sample papers into `samples/` (from "Before sending"; otherwise pick equation-heavy open-access arXiv papers in physics, physical chemistry, materials and math; gitignore PDFs that aren't CC-BY). Start parser model downloads in the background (Kokoro-82M is already in the HF cache on D:). Commit.
- **M1 (0:20–1:15) Parse + speak, backend only:** Docling → Document JSON for all samples, plus an inspection script that prints block types and reading order; sentence splitter; normalizer + tests (subagent); Kokoro synthesizes a sentence to WAV; MinerU bake-off, time-boxed (subagent, separate directory). Commit.
- **M2 (1:15–2:15) Vertical slice:** frontend PDF viewer + overlays + click-to-read + playback bar + sentence and word highlight + auto-scroll + prefetch + audio cache; skip headers, footers, citations and bibliography. Screenshot. Commit. **This is the minimum I want to see when I'm back.**
- **M3 (2:15–3:00) Math + models + focus:** SRE equation speech and equation modes; model manager panel with download progress; focus mode; outline sidebar with click-to-read. Commit.
  Then write `NOTES.md` §0 "When you're back": a 5-line summary, how to launch, a 2-minute test script, decisions to review, questions. Update §1 Status and §8 Roadmap.
- **M4 AI layer:** Ollama provider, verified equation narration with badges, figure narration, explain/ask with span citations, summaries.
- **M5 SciSpeech-Bench** and its figure.
- **M6 Depth:** reflow view, audiobook export, a second TTS engine, arXiv source mode (pick by demo value).
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
8. With Wi-Fi turned off, everything above still works (only arXiv import needs the network).

## 9. Don'ts

- Don't let an LLM paraphrase body text that's being read as the paper. Verbatim + normalization only.
- Don't read the bibliography, page furniture or citation markers by default.
- Don't build accounts, cloud sync or telemetry, and don't add cloud API calls or CDN links.
- Don't polish visuals before M2 works end to end.
- Don't start Electron/Tauri before M5.
- Don't commit secrets, model weights or PDFs we can't redistribute.
- Don't stay stuck for more than ~30 minutes: take the fallback and log it.

## 10. Demo story (design the product for this)

- **0:00–0:30:** the problem: readers reread the same line; audiobooks help; existing readers fail on papers (show a generic reader mangling an equation and reading "[12]"; even a good neural voice says "1.12 eV at 300 K" as "one point one two ee-vee at three hundred kay").
- **0:30–2:30:** SciReader on a real paper: click to start anywhere, highlight + focus mode, an equation spoken naturally with its verification badge, a figure described, explain/ask with citations, a new voice in one click. Turn Wi-Fi off on camera, and everything keeps working.
- **2:30–3:30:** the SciSpeech-Bench figure: generic pipelines mangle X % of equations, unverified local-LLM narration silently alters Y %, verification catches Z % (show the Planck ambiguity as the concrete example).
- **3:30–4:00:** open source, local, who it helps, what's next.

**Start now:** set `NOTES.md` §1 Status to "Hackathon started, M0 in progress", then go.
