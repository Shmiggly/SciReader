# SciReader: Hackathon Kickoff Brief

> **How to start (Wed 6:30 AM, at the computer):**
> 1. Restart the Claude app (so it picks up the new env vars) and check that the Ollama icon is in the system tray.
> 2. Code tab → new session → folder `D:\Github\SciReader\SciReader`, **not in a worktree** (so commits land on `main`).
> 3. In the message box: **Auto** permission mode (new sessions default to asking for permission, which would stall the run), model **Opus 5.5**, effort **Max**.
> 4. Send this short message (add any news, e.g. Valency or Adaption rules, before "ultrathink"):
>    `Start the hackathon. Your brief is docs/prompts/kickoff.md: read all of it and follow it, starting with §0. ultrathink`
> 5. Leave once NOTES.md §1 says "M0 in progress" and the agent is scaffolding.
>
> Pasting this whole file into the chat also works, but pointing at the file keeps one source of truth. Don't send the GitHub link: the session works on the local folder. Blanks below are treated as unknown, and the agent proceeds without them.

---

## Before sending (2 minutes)

- Domain: **polymers for additive manufacturing (3D printing), with AI/ML.** Demo on papers from this field.
- Papers for `samples/` (chosen and verified 2026-10-20; details in NOTES §6). Download them with a small script driven by `samples/manifest.json` (URL, license, role). Gitignore the PDFs themselves, so the repo stays small and arXiv-licensed copies aren't redistributed.
  1. **Flagship demo:** "Physics-Informed Bayesian learning of electrohydrodynamic polymer jet printing dynamics", Communications Engineering 2023 (CC BY 4.0, 33 equations, 9 figures). PDF: `https://www.nature.com/articles/s44172-023-00069-0.pdf` (arXiv 2204.09513 is PDF-only).
  2. arXiv `2209.13557` "Polymer informatics at-scale with multitask graph neural networks": dense inline math (547 inline, 14 display), LaTeX source.
  3. arXiv `2307.10139` "Artificial neural networks for predicting mechanical properties of crystalline polyamide12 via molecular dynamics": PA12, MD + ANN, units, many figures, LaTeX source.
  4. arXiv `2511.23306` "First steps towards machine learning for prediction and pre-correction in direct laser writing" (CC BY 4.0 on arXiv): two-photon polymerization + ML, tables, LaTeX source.
  5. "A critical review for synergic kinetics and strategies for enhanced photopolymerizations for 3D-printing and additive manufacturing", Polymers 2021, 13, 2325 (CC BY 4.0, 10 kinetics equations, 23 figures, two-column journal layout). **MDPI blocks scripted downloads (403)**: I download it by hand to `samples/polym13142325.pdf`. If it isn't there, skip it and use the backup.
  - Backup: arXiv `2512.08896` "Open Polymer Challenge: post-competition report" (CC BY 4.0, LaTeX source).
- LLM access (fixed, nothing to fill): **no cloud API, no key.** Everything runs locally; Ollama already has `qwen3.5:9b` and `gemma4:12b`.
- Sponsor prizes: **marimo** only requires that the project uses their platform in some way, so we use a marimo notebook for the benchmark analysis (§6). Valency / Adaption rules: ______
- Anything else that changed since last night: ______

---

## 0. How you'll work today

I'm doing the OSI Hackathon 2026 solo (~36 h, **deadline Thu Oct 22, 7:00 PM CDT**; check the system clock for my local time). We kick off around **Wed 6:30 AM Eastern** (my machine's time zone; the deadline is **Thu 8:00 PM Eastern**). **Right after sending this I'll be away from the computer for about 3 hours, so you work unattended.** The hackathon facts, judging rubric, my environment and past decisions are in `NOTES.md` (auto-loaded through `CLAUDE.md`). Read it first.

Rules for the unattended stretch:

1. **Ask me without stopping.**
   - **Technical choices:** decide yourself, and log them in `NOTES.md` §5 with one line of reasoning.
   - **Anything that matters to me** (a product or UX choice, what to cut, anything visible in the demo) when you're unsure:
     - Send me a notification with the `PushNotification` tool (load it with ToolSearch). Keep it to one line under 200 characters: the question plus the default you're taking.
     - **Keep working with that default.** My reply reaches you mid-turn; adjust then.
     - Batch questions, and also note them in `NOTES.md` §9.
   - **Other notifications:** notify me when you're blocked, and once when M3 is done. Never for routine progress.
   - **Blocking:** use AskUserQuestion only if every remaining task is blocked on my answer. Never use plan mode or anything else that waits for approval.
2. **Don't end your turn early.** Work through the milestones in §7 in order. Stop only when M3 is done and verified, or when you're blocked on something only I can do (log it, then switch to the next unblocked task). If M3 is done before I'm back, continue into M4 and M5.
3. **Keep `main` runnable.** Vertical slice first, depth later. Commit after every working step with a clear message, and **push to `origin` (private repo `Shmiggly/SciReader`) at least after every milestone**: it's my backup and how I watch progress. If a push fails, log it in NOTES and keep working; never force-push. Work on `main`. Tag every milestone that works end to end (`m0-setup`, `m1-backend`, `m2-slice`, …, and `demo-ready` before the freeze) and push the tags, so I can roll back to a working demo with one command. Use a short-lived branch only for a risky swap, such as replacing the parser.
4. **Time-box.** If a dependency or approach fights you for more than ~30 minutes, take the fallback named in this spec (or the simplest thing that works), log it, and move on.
5. **No interactive or elevated commands.** Always use non-interactive flags. Nothing that needs admin or UAC. Run long installs and downloads in the background and work on something else meanwhile.
6. **Use subagents sparingly.** Each subagent re-reads the project from scratch. Run at most 2 at a time, and only for chunks that are independent and live in separate directories (for example: the normalizer and its tests in `backend/scireader/speech/`, the parser bake-off in `backend/scireader/parsing/`). You own the integration.
7. **Verify for real.** Run the tests, start the app, open it in the browser pane (`.claude/launch.json` + preview), click through it like a user, and save one screenshot per milestone to `docs/screenshots/`. I'll use them for the video and to check progress.
8. **Disk:** model weights and caches go on D: (`HF_HOME=D:\models\hf` if not already set; app models in `D:\models\scireader`). C: is 89 % full. Never commit weights, large PDFs, `.env` or secrets.
9. **Memory across sessions:** `NOTES.md` is current truth. Update it at every milestone (status, decisions, gotchas, how to run) and delete what's no longer true. `docs/DEVLOG.md` is append-only history (what was done, what was learned) and feeds the write-up.
10. **Fully offline at runtime.** The app must work with Wi-Fi off: no cloud APIs, no CDN links, no runtime downloads. LLMs run through Ollama on `http://127.0.0.1:11434`. Don't build anything that needs a cloud API key.
11. **Fresh sessions on request.** If I ask for a fresh session for the next block:
    1. Commit, push and update NOTES.md.
    2. Start a new session on this repo folder (not a worktree), with the "Resume" prompt from `docs/prompts/followups.md` plus my note as its brief.
    3. Set its effort to max (`set_session_effort`).
    4. Stop working here.

## 1. The problem (also the pitch)

Long text is hard to follow, and scientific articles are much harder: readers lose their place in the lines and reread the same lines over and over. Audiobooks running in the background changed this for books. Every open-source read-aloud tool is bad at papers:
- they start from the first character and read everything (running headers, page numbers, citation brackets, affiliations, the reference list);
- equations come out as gibberish or are skipped;
- you can't easily start from the section or sentence you want;
- the voices are bad.

Commercial apps (Paper2Audio, Audiolizer, Listening, Audeus, Speechify, ElevenReader) are closed, cloud-only and subscription-based. They can't be trusted with unpublished manuscripts or papers under review, and none of them says how faithfully it renders the math.

Researchers with dyslexia, ADHD, low vision or blindness, non-native English readers, and anyone who wants to "read" a paper on a commute hit the same wall. In physics, chemistry, materials science and mathematics, the wall is specifically **equations, units, chemical formulas and figures**.

## 2. What we're building

**SciReader** is an open-source, local-first, science-aware reading companion. The PDF stays in front of me exactly as published. In the background it's linked to a structured, parsed copy (text blocks, sections, equations as LaTeX, figures, captions, tables, references, all with page coordinates), so the audio follows the paper's real structure and the current sentence is highlighted on the PDF itself. It runs as a local web app shown in a **borderless app window**, so it looks and feels like a desktop program. Target for now: reading on a PC or laptop screen. A mobile app and a one-click installer are future ideas, so keep the design ready for them (§5).

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
- **App window:** `scripts/dev.ps1` starts the backend and opens the UI with `msedge --app=http://localhost:<port>` (Edge ships with Windows 11). Fall back to Chrome `--app`, then the default browser. Add a web app manifest and icon so it gets its own window title, taskbar entry and "install as app" option.
- **Open a paper (one at a time):** drag & drop or file picker; paste an arXiv ID/URL (downloads the PDF; the only online feature, and it fails gracefully offline). Show a small "Recent papers" list on the start screen so I can reopen a paper (its parse is cached). No folder library yet.
- **Resume where I left off:** for each paper, remember the last sentence, speed, voice and equation mode. Reopening a paper offers "Continue from <section>: <first words of the sentence>". Keep this reading state in the local data store.
- **Parse → Document JSON** (schema in §5): block types, reading order, page + bbox, sentences, equations (LaTeX), figures + captions, tables, footnotes, page headers/footers, bibliography entries. Cache by file hash; show progress while parsing.
- **Viewer:** PDF rendered with pdf.js, continuous scroll and zoom; an overlay layer maps blocks and sentences to rectangles; an outline sidebar of sections (click to jump or start reading).
- **Click-to-read:** clicking any sentence starts playback there. Section headings in the outline also start playback.
- **Playback bar:** play/pause, previous/next sentence, previous/next paragraph, next section, speed 0.5–3× (pitch-preserving), voice picker, volume. Keyboard: Space play/pause, ←/→ sentence (→ also skips the rest of an equation), Shift+←/→ paragraph, +/- speed, `F` focus mode, `E` hear the cited equation, `D` more detail on the current figure description. Media Session API so headset and media keys work.
- **Highlighting:** the current sentence gets a soft highlight on the PDF and the current word a stronger one (Kokoro returns per-word timestamps, verified on this machine). Offer 3–4 color presets, including a high-contrast one.
- **Following:** auto-scroll keeps the current sentence in view. If I scroll away manually, stop following and show a "Back to reading position" button.
- **Focus mode is on by default** (toggle with `F`). It dims everything except the current paragraph and marks that paragraph with a bar in the margin.
- **No dark or inverted PDF page:** the page always renders as published.
- **Smart skipping** (each a toggle, sensible defaults): page headers, footers and page numbers; inline citation markers (`[12]`, `[3–5]`, `(Smith et al., 2020)`, superscript numeric citations, detectable from font size and baseline); author affiliations and emails; the bibliography; footnotes; figure and table bodies (captions are read). Acknowledgments are read by default.
- **Section announcements:** when playback enters a new section, say its title first ("Section 2: Methods"). It's a toggle, on by default.
- **Science-aware text normalization** (deterministic, no LLM): units and compound units (mol L⁻¹, cm⁻¹, m s⁻², eV, meV, Å, K, °C, GPa, kJ/mol), scientific notation (1.2 × 10⁻³, 1.2e-3), ± ≈ ~ ∝ ≤ ≥, ranges (5–10 K), Greek letters, sub/superscripts, chemical formulas (H₂O, Fe₂O₃, CO₂, NH₄⁺, Ca²⁺), isotopes (¹³C), abbreviations (e.g., i.e., et al., Fig., Figs., Eq., Eqs., Ref., Sec., ca., vs., cf.), and ambiguity traps ("5 min" vs "min(x)", "Si" vs "S i"). Display text and spoken text are stored separately. pytest suite with **≥ 100 cases**.
- **Pronunciation lexicon:** a science lexicon shipped in the repo (`lexicons/science-en.json`), plus my own user lexicon in the data dir, which overrides it.
  - Entries are plain-text respellings applied before the voice's own pronunciation step, which is simple for anyone to write. Verified: "peg-dah" → /pˈɛɡdˌɑ/, "T G" → "tee jee". An optional expert field can hold IPA (misaki supports inline `[word](/phonemes/)`; verify).
  - Seed it with ~50 polymer and additive-manufacturing terms, with my pronunciations:
    - **PEGDA → "peg-dah"** (hard "da"); **Tg → "T G"** (letters); Tm → "T M".
    - Spelled as letters: PLA, ABS, PETG, TPU, PDMS, PEEK. PA12 → "P A twelve".
    - wt% → "weight percent", vol% → "volume percent".
    - Process acronyms as letters: SLA, DLP, FFF, FDM, SLS, MJF, DIW; 2PP → "two P P".
    - Characterization methods as letters: DSC, TGA, DMA, FTIR, GPC, SEM, XRD.
  - Format: JSON with term, say-as, optional IPA, case sensitivity, tags (field), source (shipped/user/imported) and note. Document it in the README so people can share files and contribute back. That's the start of an open, community-grown science pronunciation dataset.
  - The audio cache is keyed by spoken text, so a lexicon change applies everywhere automatically.
- **Default voice:** Kokoro `af_heart` (my choice after listening to samples).
- **Equations, deterministic baseline:** LaTeX → MathML → speech with Speech Rule Engine (ClearSpeak), run through a small Node helper. Inline math is normalized in place. Display equations are announced ("Equation 3:") with modes: **full (default)** / brief / skip, switchable from the playback bar and remembered per paper.
  - Full can feel heavy on very long equations, so → (next sentence) instantly skips the rest of an equation. Evaluate on the flagship's longest equations; if it's a real problem, add an "auto" mode later (full for short equations, brief for long ones).
  - Skip mode says only "Equation 3". Brief mode is AI wording and is always labeled as such.
- **Local TTS:** Kokoro-82M (Apache-2.0) as the default engine, on GPU if available, else CPU. Synthesize per sentence, stream, prefetch the next 3–5 sentences, cache audio on disk keyed by (model, voice, speed, spoken text). **Target: < 1.5 s from click to sound.** It's realistic: the smoke test measured ~0.1 s per sentence on the RTX 4070 (60–85× real time, 0.7 GB VRAM). The cold import takes ~10 s, so load and warm up the model in the background at backend startup.
- **Model manager:** a panel listing TTS engines and voices from a registry (name, size, license, languages, quality notes, GPU/CPU), with a Download button and progress bar, Delete, and "Set default". The registry is a JSON file so new engines are easy to add; engines sit behind an interface. Kokoro is the only engine for the hackathon. A second engine is a later update, Qwen3-TTS first: Apache-2.0, multilingual (the path to French), voice cloning. Check licenses and avoid non-commercial ones (e.g. XTTS-v2) as the default.
  - **Voices:** a ▶ preview for each voice (a short sample sentence, cached).
  - **LLMs:** the same panel lists the Ollama LLMs (installed, size) and pulls new ones through Ollama's `/api/pull` with streamed progress, so the LLM side is one-click too. A dropdown for each AI job (**reader**: narration, figures, explain, ask; **checker**: back-transcription) picks which model does it.
  - **Fit:** show each model's estimated GPU memory, and warn when a choice won't fit next to the voice. Warning only; automatic hardware profiles come with the future installer.
  - **Status:** also show the parser models' status, disk use and storage location (changeable), and a **"Ready offline ✓"** line confirming everything needed is downloaded. Delete always asks for confirmation.

### P1: AI layer + reflow
- **LLM provider (local only):** Ollama, through its native `/api/chat` (supports `images` and `think: false`) or the OpenAI-compatible `/v1/chat/completions`; both were verified on this machine. Defaults: `qwen3.5:9b` for narration, figures, explain/ask and summaries; `gemma4:12b` for back-transcription only. Model names are configurable. When Ollama isn't running, AI features are disabled gracefully with a hint. Cache every LLM response on disk (hash of model + prompt). Use `think: false` and temperature 0 for narration and transcription. Keep the provider interface generic, but don't implement cloud providers.
- **Verified equation narration (the signature feature):**
  1. A narrator LLM turns LaTeX plus surrounding context into natural speech ("E equals m c squared"; "the Hamiltonian H equals the sum over i of p i squared over 2 m").
  2. An independent back-transcriber (separate call that never sees the original LaTeX) turns that speech back into LaTeX.
  3. Compare structurally, not with SymPy alone. In the smoke test, SymPy's LaTeX parser (lark backend) failed on 6 of 8 equations (`\Delta`, `\hbar`, `\nabla`, integrals, `\mathrm`), and raw string similarity scored a correct round trip at 0.70. Primary check: convert both LaTeX strings to MathML with MathJax (the same Node helper as SRE) and compare canonicalized trees (flatten `mrow`; unify `\varepsilon`/`\epsilon`, `\dfrac`/`\frac`, implicit vs explicit multiplication, `e^{x}`/`\exp`, `\mathrm{A}`/`A`). Secondary: SymPy equivalence or numeric spot checks, only when both sides parse.
  4. Verdict: **verified ✓** (use LLM speech) or **uncertain ?** (use LLM speech, show a badge). On a mismatch, retry once by telling the narrator what was lost (for example "make it explicit that k_B T is the whole denominator") and re-verify. Still failing → **fallback ✗**: use the rule-based (SRE) reading. If even the rules can't produce a reading (malformed or missing LaTeX), say only "Equation 3" and mark it **unreadable**.

  Run it in two batches per paper (all narrations with qwen, then all back-transcriptions with gemma using `keep_alive: 0`) so the models swap once, not per equation; they don't fit in VRAM together. A smoke-test case worth showing in the demo: Planck's law, narrated as "e to the h nu divided by k sub B T", came back as `e^{h\nu/k_B T}`. The spoken form is ambiguous about the denominator, and the round trip exposes it.

  Precompute for all equations in the background after parsing.
  - **Playback never waits for the AI:** if I reach an equation before its check is done, read it with the rules for that pass.
  - **Badge states:** **checking…** (a spinner, so I can see it isn't done yet) → ✓ verified / ? uncertain / ✗ rules fallback / unreadable.
  - Clicking a badge shows the equation (KaTeX), exactly what's spoken, and the check's result.
- **Equation references:** when the current sentence cites an equation ("as shown in Eq. (3)"), show a small hint. Pressing `E` (or clicking the reference) pauses reading and opens a small popup anchored over "Eq. (3)". The popup shows the equation itself (a crop from the PDF page, so it's exactly as published) and its badge. SciReader reads the equation, closes the popup, and resumes where I was. If the sentence cites several equations, pressing `E` again moves to the next. This needs references linked to equation blocks through their printed numbers.
- **Figure narration (at first mention, panel-aware):**
  - **Description:** crop the figure and caption from the page image and ask `qwen3.5:9b` (it reads images) for a short description of about 80 words: plot type, axes and units, what the curves are, key trends. `D` asks for more detail. In the smoke test it described a synthetic XRD plot correctly, peaks included, in ~10 s with a model swap.
  - **When it plays:** when the text first mentions a figure, finish that sentence, then read the caption and the description.
  - **On screen:** at that moment the figure **pops up anchored where it was mentioned** (a crop from the PDF), like the equation popup. It closes when reading moves on, with a pin to keep it open.
  - **No repeats:** don't repeat it when the layout reaches the figure. Read a figure at its layout position only if the text never mentions it.
  - **Targets are the whole figure or specific panels.** "Fig. 3b" or "Figure 3(b)" → describe **only panel b**, and read only panel b's part of the caption when it can be split out (else the caption's first sentence). "Fig. 3" → describe the whole figure with its full caption. Ranges like "Fig. 3a–c" → those panels together.
  - **Once per target:** each target is described once, at its first mention. Detect panels by passing the whole figure plus caption and asking the model to focus on the named panel (stretch: have it return the panel's box and outline it in the popup).
  - **Other cases:** say nothing extra for supplementary figures that aren't in the PDF ("Fig. S2").
  - **Labeling:** always labeled, in speech ("AI description of Figure 3, panel b: …") and in the UI.
  - **Background work:** after parsing, scan the text for all figure and panel mentions and prepare a description for every mentioned target, so they're ready when playback gets there.
- **Explain selection:** select text or an equation → "Explain" → a short explanation grounded in the paper, with citation chips that jump to and highlight the source spans. Can be read aloud. Default level: **colleague** (a materials scientist), with a **"Simpler"** button that re-explains in plainer language. Questions are typed only (asking by voice is a later update).
- **Ask the paper:** a Q&A panel grounded in the parsed document. Answers cite spans (click → highlight on the PDF) and can be read aloud.
  - Context design (measured 2026-10-20): put the **whole paper** in the prompt, with sentence IDs (e.g. `[s123] …`) so answers can cite exact sentences.
  - Use `num_ctx` 32768. That added only ~0.9 GB of VRAM over 4K for `qwen3.5:9b`, so qwen + Kokoro + other apps ≈ 10.3 GB of 12.3.
  - Keep the paper text as a fixed prompt prefix so Ollama reuses its cache between questions (only the first question pays the reading time).
  - Fall back to BM25 retrieval over sentences only for papers longer than ~28K tokens.
- **Listen to a summary:** a 1–2-minute spoken summary per section or for the whole paper, clearly labeled as AI. **Last in line** among the AI features.
- **Citations:** hover or click an in-text citation to see the bibliography entry, with a DOI/arXiv link when present.
- **Pronunciation review screen (my idea; a strong demo moment):** a second screen for the open paper.
  - It lists terms the voice will probably say badly: words outside the voice's dictionary (check how misaki marks fallback/out-of-vocabulary tokens), all-caps and mixed-case abbreviations (PEGDA, PA12, Tg), chemical formulas, and unit strings the normalizer doesn't know. Sort them by how often they appear in the paper.
  - Each row has the term, its count, ▶ "how it sounds now" (in a context snippet from the paper), a "say it like" box, ▶ preview, and Save.
  - Saved entries go to my user lexicon and apply right away.
  - **Export / Import** buttons share lexicon files between users. Import merges, and on a conflict asks "keep mine / take theirs".
  - The file grows over time and is portable.
- **Reflow view:** a clean single-column text view of the parsed document (adjustable font, size, line spacing, width; dyslexia-friendly font option), synced with the PDF (same highlight, click-to-read). It's a toggle that replaces the PDF view, not side by side (too cramped on a laptop).

### P2: stretch (pick by demo value)
- **Scanned or old papers (first stretch pick):** image-only PDFs through Docling's OCR option (slower parse). Detect image-only pages and tell me when OCR is needed.
- **Audiobook export:** MP3/M4B with one chapter per section, for listening away from the screen.
- **arXiv source mode:** when the paper is on arXiv, fetch the LaTeX source and use its exact equations, aligned to the parsed equation blocks. Perfect math without OCR.
- **Auto-pause:** optionally pause after each paragraph so I can absorb it, then continue with Space (off by default).
- Per-section voice and speed.
- Desktop packaging (Tauri or Electron), only after everything else.

## 5. Architecture (defaults; deviate only with a logged reason)

- **Monorepo:**
  - `backend/`: Python 3.12 managed with uv; FastAPI + uvicorn; package `scireader` with `parsing/` (parser adapters + Document builder), `speech/` (sentence splitter, normalizer, math speech), `tts/` (engine interface, `registry.json`, downloader, audio cache), `llm/` (providers, narration, verification, QA), `api/` (routes), `store/` (document cache and per-paper reading state on disk, under a configurable data dir). Tests in `backend/tests/`.
  - `frontend/`: Vite + React + TypeScript + pdfjs-dist, a small store (Zustand), KaTeX for math display. Minimal, clean UI. The app's own interface follows the system light/dark theme; the PDF page itself is never darkened or inverted.
  - `tools/math-speech/`: Node helper (speech-rule-engine + mathjax-full), called from the backend in batches over stdin/stdout JSON.
  - `bench/`: SciSpeech-Bench (data, scripts, results, figures).
  - `scripts/`: `dev.ps1` (starts backend + frontend and opens the app window), `setup.ps1` (first-time setup). Keep installation simple for the hackathon: README + `setup.ps1`.
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
- **Parsing:** `Parser.parse(pdf_path) -> Document`. Implement **Docling** first (MIT, Windows-friendly; layout labels, reading order, bbox, formula LaTeX through its formula enrichment). Then time-box a **MinerU 2.5** attempt (best formula accuracy in 2026 benchmarks, GPU) on the same samples. Docling stays the default unless MinerU is dramatically better on equations, and even then MinerU is only an optional parser, because its license reportedly has commercial terms above a usage threshold (§5 Licenses). Log the comparison in NOTES.
  Sentence rects: get word or char boxes with pypdfium2 (or the pdf.js text content) inside each block's bbox, and align them to the sentence text with fuzzy character alignment. Fall back to the block bbox if alignment fails.
- **Speech pipeline:** block → sentences (rule-based splitter aware of "Fig. 2", "et al.", "e.g.", decimals) → normalizer → math speech (inline and display) → spoken text → TTS.
- **TTS:** engine interface `synth(text, voice, speed) -> (audio, word_timestamps | None)`. Verified with kokoro 0.9.4: each `KPipeline` result has `.tokens`, each with `.text`, `.phonemes`, `.start_ts`, `.end_ts` (seconds), so word highlighting is P0. Kokoro setup gotchas from the smoke test (details in NOTES §3): declare `en_core_web_sm` as an explicit dependency (misaki's runtime auto-download fails in a uv venv); get CUDA torch from the PyTorch index (`cu132` worked) through `[[tool.uv.index]]` + `[tool.uv.sources]`; set `HF_HUB_OFFLINE=1` once models are cached. Endpoint `GET /api/tts/{doc}/{sentence_id}?voice&speed` returns audio (WAV or Opus) plus timestamps. Downloads go through `huggingface_hub` with progress over SSE.
- **GPU budget (12 GB, measured with nvidia-smi):** other apps ~2.8 GB, `qwen3.5:9b` ~6.2 GB, `gemma4:12b` ~8.5 GB, Kokoro ~0.7 GB. While reading, keep qwen + Kokoro resident (~9.7 GB total). Load gemma only for batch verification, then unload it. Run the parser before any of them and unload it afterwards. `ollama ps` under-reports gemma4's VRAM, so trust nvidia-smi.
- **Offline checklist:** bundle the pdf.js worker and KaTeX CSS/fonts through Vite (no CDN links); bundle any web fonts locally (e.g. OpenDyslexic, OFL); SRE's locale files come from its npm package; download parser models during M0; set `HF_HUB_OFFLINE=1` at runtime; check `http://127.0.0.1:11434/api/version` at startup. Verify by checking the browser network panel for any non-localhost request.
- **Config:** `.env` (gitignored) and `.env.example`: `OLLAMA_URL`, `NARRATOR_MODEL`, `VERIFIER_MODEL`, `MODELS_DIR`, `HF_HOME`, `HF_HUB_OFFLINE`.
- **Future-proofing (cheap now, valuable later):**
  - Keep the backend a clean HTTP API, independent of the UI, so a mobile client or a packaged desktop app can reuse it.
  - No hardcoded machine paths in code (everything through config), and one entry-point launcher, so a one-click installer is possible later.
  - English only for now, but keep language-specific normalization rules in their own module (e.g. `speech/en/`) so other languages can be added.
- **Licenses:** the project is **Apache-2.0** (commercial use stays open), so dependency licenses matter now.
  - Prefer MIT, BSD and Apache dependencies. Track every dependency and model with its license in `docs/LICENSES.md`, and flag anything GPL, AGPL, non-commercial or usage-limited.
  - Avoid as defaults: Marker (weights restricted above revenue thresholds), XTTS-v2 (non-commercial), PyMuPDF (AGPL; use pypdfium2 instead).
  - Already known flags:
    - misaki pulls in espeak-ng and phonemizer (GPL-3.0) for out-of-dictionary words. That's acceptable for this open-source build; note it as something to replace before any closed commercial release.
    - MinerU's license has commercial terms above a usage threshold (keep it optional).
    - Model licenses: Kokoro is Apache-2.0; check and record Qwen3.5's and Gemma 4's. Users download models themselves through Ollama, and we never redistribute weights.

## 6. SciSpeech-Bench (the measurable result)

Goal: one clear figure for the write-up and a reusable open benchmark.

- **Data:** target **200 display equations (minimum 100)**; ~100 inline expressions and ~100 unit/chemistry snippets are a bonus. Source: 15–25 open-access arXiv papers, **at least half polymers/materials** (the demo domain, including samples 2–4 and the backup), the rest physics, chemistry and math to show it generalizes (prefer CC-BY). Store arXiv IDs and extracted LaTeX, not PDFs. **Ground truth is the LaTeX from the arXiv source tarball, not OCR.** Respect arXiv etiquette: ≤ 1 request per 3 s, descriptive User-Agent. Include samples 2–4 and the backup (they have LaTeX source), and fill up with polymer/materials papers first. Gotchas from 2026-10-20: the arXiv search API (`export.arxiv.org/api`) returned "429 Rate exceeded" even on the first call. Search with OpenAlex instead (`api.openalex.org/works`, filter `locations.source.id:S4306400194` for arXiv; no key, but a shared free budget of about 100 requests a day per IP). `arxiv.org/abs`, `/html`, `/pdf` and `/src` all worked. A HEAD on `/src/<id>` tells TeX source (`application/gzip`) from PDF-only (`application/pdf`).
- **Conditions:**
  - (a) naive: what a generic reader speaks (the PDF text layer of the equation region);
  - (b) SRE ClearSpeak from the source LaTeX;
  - (c) local LLM narration (`qwen3.5:9b`), unverified;
  - (d) the same + verification gate with one repair retry (fallback to SRE);
  - (e) optional: the full SciReader pipeline from the parsed PDF (OCR LaTeX → speech), which also measures the parser's math accuracy;
  - (f) optional: (c) and (d) with `qwen3.5:4b` too, to show how the error rate grows as the model shrinks and how much verification closes the gap.
- **Metrics:**
  - **Faithfulness:** back-transcription with a fixed, independent model (`gemma4:12b`), then the canonical MathML comparison (plus SymPy where it parses) against the ground-truth LaTeX. Have a ~30-item subset adjudicated (by me, or by careful manual inspection) to separate narrator errors from transcriber errors.
  - **Naturalness:** LLM-judge pairwise preference on a subset, plus **~30 blind items I'll rate myself** (~15 min of my time; make a tiny rating page that hides which pipeline produced each reading).
  - **Units and chemistry, scored by sound:** for each snippet, phonemize three texts with the voice's own phonemizer (misaki via `KPipeline(model=False)`; verified to run offline): (1) the raw text a generic reader would send, (2) SciReader's normalized text, (3) a hand-checked correct reading. Score the phoneme edit distance to the correct reading. Headline: "generic readers mispronounce X % of units and formulas" (e.g. MPa → "em-pah"). No audio or speech recognition needed.
  - Report the **silent error rate of unverified local-LLM narration** and the verifier's precision/recall at catching errors.
- **Analysis in marimo (sponsor prize requirement: use their platform; marimo is Apache-2.0):** `bench/analysis.py` is a marimo notebook.
  - It loads the results, computes every metric, and **produces the figures**.
  - It has small interactive controls (filter by field, model, condition).
  - Commit a static HTML export (`marimo export html`) so judges can view it without running anything.
  - Mention marimo in the README, write-up and video.
- **Release the dataset** in `bench/data/`: arXiv IDs + links, equations, correct readings, scripts. Our annotations are CC BY 4.0, and the README says how to extend it.
- **Outputs:** `bench/results/*.json`, `bench/figures/faithfulness.png` (+ `.svg`), a short `bench/README.md`. Collecting the arXiv data needs the network once; everything after that runs locally and costs only time. Cache every model call.

## 7. Milestones (times from kickoff; adjust if behind, but keep the order)

- **M0 (0:00–0:20) Setup:** verify the toolchain (uv, Python 3.12, Node LTS, git) and that Ollama is up with both models (`ollama list`); scaffold the monorepo, `LICENSE` (Apache-2.0), `.gitignore`, `.env.example`, README skeleton, `.claude/launch.json` for the dev servers. Fetch the sample papers listed in "Before sending" into `samples/` (manifest + download script; PDFs gitignored). Start parser model downloads in the background (Kokoro-82M is already in the HF cache on D:). Commit.
- **M1 (0:20–1:15) Parse + speak, backend only:** Docling → Document JSON for all samples, plus an inspection script that prints block types and reading order; sentence splitter; normalizer + seed pronunciation lexicon + tests (subagent); Kokoro synthesizes a sentence to WAV; MinerU bake-off, time-boxed (subagent, separate directory). Commit.
- **M2 (1:15–2:15) Vertical slice:** frontend PDF viewer + overlays + click-to-read + playback bar + sentence and word highlight + auto-scroll + prefetch + audio cache; skip headers, footers, citations and bibliography. Screenshot. Commit. **This is the minimum I want to see when I'm back.**
- **M3 (2:15–3:00) Math + models + focus:** SRE equation speech and equation modes; model manager panel with download progress; focus mode; outline sidebar with click-to-read; resume where I left off. Commit.
  Then write `NOTES.md` §0 "When you're back": a 5-line summary, how to launch, a 2-minute test script, decisions to review, questions. Update §1 Status and §8 Roadmap.
- **M4 AI layer:** Ollama provider, verified equation narration with badges, figure narration at first mention (popup, panel-aware), explain (colleague level + "Simpler") and ask with span citations; summaries last.
- **M5 SciSpeech-Bench:**
  - Collect data: 100 equations first, then grow toward 200, then the inline and unit items.
  - Run all conditions, including `qwen3.5:4b`. Long GPU runs are scripts, so launch them in the background (they need no agent).
  - Build the marimo analysis notebook that makes the figure, and the rating page for my ~30 blind ratings.
- **M6 Depth:** P1 leftovers first (pronunciation review screen, equation-reference popup, then reflow view). Then P2 by demo value: scanned-PDF OCR first, then audiobook export, auto-pause, arXiv source mode.
- **M7 Ship (start no later than 8 h before the deadline; feature freeze at T-6 h):** README (pitch, GIF/screenshots, install, features, architecture diagram, licenses, benchmark result); `docs/writeup.md` (one page + figure: what we built, what we learned); `docs/demo_script.md` (≤ 4-min video, beat by beat); repo ready to go public (no secrets, no non-redistributable PDFs, no weights). **The GitHub repo `Shmiggly/SciReader` is private until then.** After I OK the audit, make it public (see the Ship prompt in `docs/prompts/followups.md`).

## 8. Definition of done for the demo

On the flagship sample (the polymer jet printing paper, 33 equations):
1. Open it; the outline appears after a parse of about a minute.
2. Click a sentence in Section 2: audio starts within ~1.5 s, the highlight on the PDF tracks the speech, and the page auto-scrolls.
3. Citation markers aren't read; running headers and page numbers are skipped.
4. An equation is spoken naturally with a ✓ verified badge, and I can see its LaTeX and spoken text.
5. When the text first mentions a figure, it pops up there and I hear its caption and a labeled AI description. "Fig. 3b" describes only panel b.
6. I select a confusing sentence, hit "Explain", and get a grounded answer with a clickable source chip.
7. In the model manager I preview and switch voices, and download `qwen3.5:4b` with a progress bar. If the benchmark already pulled it, delete it first so the download is real on camera.
8. I close the paper, reopen it from "Recent papers", and it offers to continue where I stopped.
9. With Wi-Fi turned off, everything above still works (only arXiv import needs the network).

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
- **0:30–2:30:** SciReader on a real paper from the demo domain (the polymer jet printing flagship): click to start anywhere, highlight + focus mode, an equation spoken naturally with its verification badge, a figure popping up at its first mention with just the referenced panel described, explain/ask with citations, an AI model downloaded in one click. The pronunciation screen catches "PEGDA"; I type "peg-dah" once and hear it fixed across the paper. Turn Wi-Fi off on camera, and everything keeps working.
- **2:30–3:30:** the SciSpeech-Bench figure: generic pipelines mangle X % of equations, unverified local-LLM narration silently alters Y %, verification catches Z % (show the Planck ambiguity as the concrete example).
- **3:30–4:00:** open source, local, who it helps, what's next.

**Start now:** set `NOTES.md` §1 Status to "Hackathon started, M0 in progress", then go.
