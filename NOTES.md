# SciReader — Project Notes (living document)

> **Single source of truth across conversations.** Auto-loaded through `CLAUDE.md`.
> Update it at every milestone and after every decision, gotcha or environment change.
> Keep it current: delete what is no longer true instead of stacking corrections. History goes to `docs/DEVLOG.md`.

**Last updated:** 2026-10-21 00:47 EDT (M2 vertical slice working)

---

## 0. When you're back (agent writes this at the end of each unattended stretch)

**Interim note (00:47 EDT).**
- **Works now:** open a paper (drop/pick, arXiv, sample list, recent list) → Docling parse (~100 s first time, cached after) → PDF with click-to-read, sentence + word highlight, focus mode (on by default), auto-follow with "Back to reading position", prefetch + disk audio cache, outline sidebar, skipping of page furniture/affiliations/bibliography, superscript and bracket citation markers dropped from speech, equations spoken with SRE (from Docling's OCR LaTeX). Screenshot: `docs/screenshots/m2-reader-focus-highlight.jpg`.
- **01:00 update:** science normalizer + splitter + 102-term lexicon are in (284 tests pass); model manager panel and `scripts/dev.ps1`/`setup.ps1` done; all 6 samples pre-parsed. Work pauses from ~01:00 to 02:10 EDT. **Left for M3:** verify TTS with the real normalizer in the browser, tag `m3`, final version of this section.
- **How to launch (dev):** two terminals: `uv run --directory backend uvicorn scireader.main:app --port 8765` and `npm --prefix frontend run dev`, then open http://localhost:5173. (`scripts/dev.ps1` comes in M3.)
- **Decisions to review:** author list skipped by default along with affiliations (toggle in ⚙ Reading settings); captions are read at their layout position until figure narration (M4) moves them to first mention; speed uses the browser's pitch-preserving playbackRate (instant, no re-synthesis).

---

## 1. Status at a glance

- **Phase:** **Hackathon running (started Wed 2026-10-21 00:21 EDT, earlier than the planned 6:30). M0 done, M2 vertical slice works end to end; M1 normalizer being finished.**
- **Direction (confirmed 2026-10-20):** Idea 1 (science-aware read-aloud reader) + "verified math narration" as the bridge to AI reliability/safety.
- **Fully offline (user requirement, 2026-10-20):** no API key. All runtime AI is local: Kokoro for speech, Ollama with `qwen3.5:9b` + `gemma4:12b` for LLM work.
- **GitHub:** private repo https://github.com/Shmiggly/SciReader. Tags: `m0-setup`, `m2-slice`.
- **Pacing:** fresh session per block, at most one subagent, small outputs.

---

## 2. Hackathon facts

- **Event:** OSI Hackathon 2026, "Build the Future of Scientific Intelligence".
  Page: https://scientificintelligence.org/campaigns/osi-hackathon-2026
  Successor of the LLM Hackathon for Applications in Materials Science & Chemistry (https://llmhackathon.github.io, 120+ example projects; 2025 outcomes report arXiv:2605.03205).
  Collaborators: UChicago, Argonne, Materials Discovery Research Institute (MDRI), NVIDIA, Valency, marimo.
- **Timeline:** kickoff Wed **Oct 21, 2026** (anywhere on Earth). **Deadline Thu Oct 22, 2026, 7:00 PM CDT** (= 8:00 PM EDT = 00:00 UTC Oct 23). Awards Thu Nov 19 per the page; selected teams present at a virtual event in late November.
- **Team:** solo is allowed ("A team of one is allowed"). Solo, ~36 h total; the agent runs unattended for long stretches.
- **Scope:** anything that meaningfully advances the physical sciences or mathematics. Organizers push "two days to a real discovery" and "speed over polish, learning over perfection".
- **Submission (4 items):**
  1. Public social post (X, LinkedIn, Bluesky, YouTube, …) viewable without login, with a video ≤ 4 min (don't speed up the voice).
  2. Write-up: what you built and what you learned (the video tl;dr says one page + a figure).
  3. **Public repo with a README**, openable without signing in.
  4. Rules confirmation checkbox.
- **Prizes:** MDRI general prize (~$10K total), sponsor prizes from Valency, Adaption and marimo (you must use their platform; exact rules not on the page → check Slack at kickoff), an NVIDIA DGX Spark (export controls).
- **Resources:** sponsor credits, curated datasets, mentors on Slack/Zoom. Own subscriptions and clusters allowed.
- **Pre-existing code:** the page doesn't address it. Working assumption: notes, prompts, environment setup and model downloads before kickoff are fine; app code is written during the event. Ask on Slack or blaiszik@uchicago.edu if unsure.

### Judging rubric (each criterion scored 1–5)

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| Potential for impact | Hard to see who would use it or what it would change | Useful to a narrow group, or impact depends on a lot more work | Clear users and a clear change in how they could work if carried forward |
| Innovativeness | Repeats an existing tool or tutorial with little change | Known approach in a new setting, or a fresh combination | A new idea or approach others haven't tried in this form |
| Novelty | Mirrors prior work with little new capability | Original tooling enabling new lines of exploration | First-of-its-kind capability opening clear follow-on avenues |
| Relevance to physical sciences & math | General-purpose work, no specific scientific problem | Touches a scientific problem, link loose or indirect | Addresses a specific, real problem in physical sciences or math |

**Our weakest criterion is Relevance.** A generic PDF reader scores 1–3. Everything science-specific (equations, units, chemistry, figures, the benchmark) is what lifts it, so it gets priority in demos and the write-up.

---

## 3. The user and the environment

- Demo domain: **polymers for additive manufacturing, with AI/ML**. Sample papers come from this field (§6).
- The problem: readers who lose their place reread the same lines; audiobooks help with books. Existing open-source readers fail on papers (start at the first character, read everything, bad voices, no section selection).
- **Machine:** Windows 11 Home, PowerShell 5.1 + Git Bash. RTX 4070 (12 GB VRAM, driver 617.42), 64 GB RAM.
  Disk: **D: ~840 GB free** (use it for models/caches), **C: 89 % full (~107 GB free)**: never let caches default to C:.
- **Toolchain (installed & verified 2026-10-20):** git 2.55 · uv 0.13.4 · Python 3.12.15 (uv-managed, `D:\tools\uv\python`) · Node 24.20.0 LTS + npm 11.19 (`C:\Program Files\nodejs`) · gh 2.102.0 (`C:\Program Files\GitHub CLI`, logged in, see GitHub below) · Ollama 0.40.6 (`%LOCALAPPDATA%\Programs\Ollama`). Not installed: Docker. No cloud API keys, by design (the app is fully offline).
- **User env vars (HKCU) set 2026-10-20:** `HF_HOME=D:\models\hf` · `UV_CACHE_DIR=D:\cache\uv` · `UV_PYTHON_INSTALL_DIR=D:\tools\uv\python` · `UV_TOOL_DIR=D:\tools\uv\tools` · `NPM_CONFIG_CACHE=D:\cache\npm` · `GH_CONFIG_DIR=D:\tools\gh` · `OLLAMA_MODELS=D:\models\ollama`. App model dir planned: `D:\models\scireader`.
- **Python usage:** always `uv run …` / `uv venv`. Bare `python` hits the Microsoft Store alias; `~\.local\bin` (uv's `python3.12.exe` shim) is not on PATH.
- **Conda:** Miniconda3 (Python 3.12.4) and Anaconda Desktop are installed (plus old Anaconda2 leftovers), but they're not on PATH and not hooked into PowerShell or bash. Don't use them for this project and don't run `conda init` (an auto-activated base env can confuse uv's interpreter discovery). uv is the only Python toolchain.
- **gh config:** `GH_CONFIG_DIR=D:\tools\gh` (user env var, set 2026-10-20). gh's default `%APPDATA%\GitHub CLI` would be redirected inside the Claude app (see the MSIX gotcha below); this way the app and normal terminals share one login. The user ran `gh auth login --web` (HTTPS) from the app's Terminal panel on 2026-10-20. Verify with `gh auth status`.
- **Gotcha: Claude desktop is an MSIX-packaged app.** Shells it launches have writes to `%APPDATA%`/`%LOCALAPPDATA%` silently redirected to `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\…`, invisible to normal terminals (and it broke uv's Python junction). Keep tools and caches on D: through the env vars above. Installers run through winget/msiexec are unaffected.
- **Gotcha: env changes need a restart.** Shells inherit the environment the Claude app started with. After installing tools or changing env vars, restart the Claude app (or refresh `$env:Path` from the registry inside the command).
- **GPU + TTS smoke test (2026-10-20, passed).** Scratch venv `D:\scratch\gpu-smoke\.venv` (outside the repo; disposable).
  - PyTorch **2.14.1+cu132** (CUDA 13.2), installed with `uv pip install torch --torch-backend=auto`. Sees the RTX 4070; 20 × 4096² matmuls in 0.18 s. Wheels are now in the uv cache on D:, so the project install will be fast.
  - **Kokoro 0.9.4** (misaki 0.9.4, spaCy 3.8, espeakng-loader 0.2.4). Weights `hexgrad/Kokoro-82M` are in `D:\models\hf` (347 MB incl. all voices). Voice `af_heart`.
  - Timings on GPU: cold import ~9.5 s, model load 1.6 s, then **~0.1 s per sentence** (5.7–8.5 s of audio, 61–84× real time). Peak VRAM **0.7 GB**.
  - **Word timestamps: yes.** Each `KPipeline` result has `.tokens` with `.text`, `.phonemes`, `.start_ts`, `.end_ts` (seconds); 38/38 words were timed.
  - Normalizer evidence: "1.12 eV at 300 K" is spoken as "one point one two **ee-vee** at three hundred **kay**", so units need our normalizer. "H equals p squared over 2 m" (already spelled out) is fine.
- **Gotcha: spaCy model.** misaki auto-downloads `en_core_web_sm` on first use by shelling out to an installer, and that fails inside a non-activated uv venv ("No virtual environment found"). Declare it as an explicit dependency: `en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl`.
- **Gotcha: CUDA torch in a uv project.** `--torch-backend=auto` only works with `uv pip`. In `pyproject.toml`, add the PyTorch index (`https://download.pytorch.org/whl/cu132`) as an explicit `[[tool.uv.index]]` and pin `torch` to it in `[tool.uv.sources]`.
- **espeak-ng:** no separate Windows installer was needed (bundled by `espeakng-loader`). Hugging Face warns about unauthenticated requests (harmless); set `HF_HUB_OFFLINE=1` once models are cached so the app runs offline.
- **Ollama (installed 2026-10-20).** Server runs from the tray app at login (outside the Claude sandbox) on `http://127.0.0.1:11434`. Models live in `D:\models\ollama`: `qwen3.5:9b` (6.6 GB, text + images, 256K context) and `gemma4:12b` (8.0 GB, 11.9B Q4_K_M, text + images). Both the native `/api/chat` (with `images`, `think: false`) and the OpenAI-compatible `/v1/chat/completions` work.
- **Measured VRAM (nvidia-smi, 12 GB card):** other apps ~2.8 GB at idle · `qwen3.5:9b` ~6.2 GB · `gemma4:12b` ~8.5 GB · Kokoro ~0.7 GB. So qwen + Kokoro fit together while reading (~9.7 GB total); gemma can't share with qwen (Ollama swaps them). Context length barely matters for qwen3.5: total VRAM was 8.6 GB at `num_ctx` 4096, 8.9 GB at 8192 and 9.5 GB at 32768 (other apps 2.2 GB at that moment). So a whole paper fits in context next to Kokoro. **`ollama ps` under-reports gemma4** (shows 1.1 GB): trust nvidia-smi.
- **Load times:** cold first load from disk 18–28 s; warm swap ~5 s. After loading, ~70 tokens/s for qwen3.5:9b, so narrating one equation takes 0.2–0.7 s.
- **LLM smoke test (2026-10-20), 8 physics/chem equations:** qwen3.5:9b narrations were all faithful and natural. gemma4:12b blind back-transcription recovered 7/8. The miss (Planck's law) is the textbook case for verification: "e to the h nu divided by k sub B T" is ambiguous about the denominator, and the transcriber also dropped "(T)". Figure test: qwen3.5:9b described a synthetic two-phase XRD plot correctly (axes, units, legend, all 10 peak positions) in ~10 s including a model swap.
- **Gotcha: SymPy's LaTeX parser (lark backend) failed on 6 of 8 equations** (`\Delta`, `\varepsilon`, `\hbar`, `\nabla`, integrals, `\mathrm`). Plain string similarity is also misleading (0.70 for a correct Arrhenius round trip). The verifier needs canonicalized structural comparison (see §5).
- Test scripts and outputs are in the scratchpad and `D:\scratch\gpu-smoke\out` (throwaway, not project code).
- **Repo:** local `D:\Github\SciReader\SciReader`, branch `main`, remote `origin` = https://github.com/Shmiggly/SciReader (**PRIVATE** until submission; flipping it public is in M7). The outer `D:\Github\SciReader` folder only holds this repo.
- **GitHub:** account `Shmiggly`, gh logged in over HTTPS (token in Windows Credential Manager, config in `D:\tools\gh`). `gh auth setup-git` is done, so `git push` uses gh's login. That needs `GH_CONFIG_DIR` in the environment: restart the Claude app, or set `$env:GH_CONFIG_DIR = 'D:\tools\gh'` in the command. Git identity: `Shmiggly` (global config). In PowerShell 5.1, commit with `git commit -F <file>` because here-strings piped to `-F -` don't arrive.

---

## 4. Pre-hackathon checklist (tonight, user does these)

Installs can trigger UAC prompts, which would stall an unattended agent, so they happen tonight.

- [x] uv, Python 3.12, Node LTS, GitHub CLI installed; caches and Python moved to D: (see §3). Done 2026-10-20.
- [x] gh logged in as Shmiggly; private repo `Shmiggly/SciReader` created and pushed. Done 2026-10-20.
- [ ] **Restart the Claude desktop app** before kickoff so new sessions inherit the new PATH and env vars.
- [x] Kokoro-82M pre-downloaded and GPU smoke test passed (results in §3). Done 2026-10-20.
- [x] Ollama 0.40.6 installed; `qwen3.5:9b` + `gemma4:12b` pulled to D: and tested (§3). Done 2026-10-20.
- [ ] Before kickoff: check that the Ollama icon is in the system tray (its server starts at login).
- [x] Sample papers chosen from the demo domain (§6). Done 2026-10-20.
- [x] Sample #5 downloaded by hand to `samples/polym13142325.pdf` (9.2 MB, CC BY 4.0; not committed). Done 2026-10-20.
- [ ] Kickoff session: open it directly on the repo folder (**not** in a worktree, so commits land on `main`) and pick **auto** mode in the message box (new sessions default to asking for permission, which would stall the unattended run). Keep-awake is already on, battery included, but a closed laptop lid still sleeps. Model Opus 5.5, effort **Max**.
- [ ] At kickoff: read the sponsor prize rules (Valency, Adaption, marimo) on Slack and note them in the kickoff prompt.

---

## 5. Decision log (newest first; one line of reasoning each)

- **2026-10-21 · MinerU bake-off dropped (time-boxed, ~10 min).** `mineru` is now 4.0.12, an agent-oriented "document library" with telemetry (we disabled it) and a cloud parse service. Its local `flash` tier returned no equations at all on the flagship, and the formula-capable tiers say "Local parse-server is disabled. Use --tier flash or --remote" (remote = cloud, ruled out). Docling stays the only parser; its formula OCR quality is what the verifier and benchmark measure. Scratch venv in `D:\scratch\mineru` (deletable).
- **2026-10-21 · Build decisions (agent, during M0–M2):**
  - **Sentence/word rects from PDFium chars, not Docling:** Docling has block boxes only; we align block text to PDFium characters (difflib, whitespace ignored), which also gives superscript detection for numeric citations (loose box height + raised baseline; `FPDFText_GetFontSize` returns 1.0 in Nature PDFs because of the text matrix).
  - **Springer Nature glyph fix:** their PDFs encode inline-math glyphs wrongly (`¼` → `=`, `ð…Þ` → `( )`, `þ` → `+`); applied per document when ≥ 6 such glyphs appear.
  - **Equation LaTeX cleanup:** Docling CodeFormulaV2 emits tokenized LaTeX (`J e t \ R a d i u s … \quad ( 1 )`); we strip the equation number (it becomes "Equation 1:"), join runs of ≥ 3 single letters into `\mathrm{word}`, and drop junk formulas (e.g. `\begin{matrix} 2 \\ 2 \end{matrix}`).
  - **TTS endpoint recomputes spoken text** (normalizer + current lexicon) on each request; the audio cache is keyed by spoken text, so lexicon edits apply everywhere automatically. Citation spans per sentence live in `speech.json` next to `document.json`.
  - **Speed** via the browser's pitch-preserving `playbackRate` (instant changes, cache reuse) instead of Kokoro's speed parameter.
  - **Author list skipped by default** together with affiliations (toggle in Reading settings).
  - **Data dir** defaults to `<repo>/.data` (gitignored; on D: here). HF models stay in `HF_HOME` (Docling downloaded layout-heron, TableFormer and CodeFormulaV2 there, ~1.5 GB with Kokoro).
  - **Preview tool gotcha:** the session's preview reads `.claude/launch.json` from the folder the session was opened on. This session was opened on the outer `D:\Github\SciReader`, so a copy lives there too (outside the repo).

- **2026-10-21 · Plan walkthrough, step 9 (schedule, cuts, submission):**
  - **Kickoff** Wed 6:30 AM Eastern. The first ~3 h run unattended.
  - **Questions:** the agent asks through `PushNotification` with a stated default and keeps working (no blocking questions unless everything is blocked).
  - **Effort:** Max for every session; "ultrathink" is added to the prompts as a backup.
  - **Sessions:** a fresh session per block, with a "Hand off" prompt.
  - **Schedule and cut order** are in §8. Freeze Thu 14:00, submit by 19:00.
  - **The user records the video** in their own voice.
- **2026-10-21 · Plan walkthrough, step 8 (benchmark):** user agreed with all picks.
  - **Papers:** at least half polymers/materials.
  - **Size:** 200 equations (minimum 100).
  - **Ratings:** the user's ~30 blind naturalness ratings.
  - **Units and chemistry:** scored at the phoneme level with misaki (offline).
  - **Release:** the dataset goes public (CC BY 4.0 annotations).
  - **marimo prize** only requires using their platform somehow, so **the benchmark analysis and figures live in a marimo notebook** (`bench/analysis.py`, plus a static HTML export).
- **2026-10-20 · Plan walkthrough, step 7 (model manager):** user agreed with all picks.
  - Voice previews.
  - A dropdown per AI job (reader / checker).
  - GPU-memory fit warning (no hardware profiles yet).
  - No second voice engine for the hackathon (Qwen3-TTS first later: Apache-2.0, multilingual → French).
  - The video's one-click download is `qwen3.5:4b`, which the benchmark also needs; delete it and re-download it on camera.
- **2026-10-20 · Plan walkthrough, step 6 (AI helpers):**
  - **Figure descriptions play at first mention:** finish the sentence, then the caption and description. They aren't repeated when the layout reaches the figure.
  - **The figure pops up where it was mentioned** (user's idea).
  - **Panel-aware** (user's idea): "Fig. 3b" describes only panel b, and "Fig. 3" describes the whole figure. Each target is described once.
  - **Short descriptions** with `D` for more detail.
  - **Explain** defaults to colleague level, with a "Simpler" button.
  - **Typed questions only** (voice later).
  - **Summaries** are kept but come last among the AI features.
  - **Figure descriptions** are prepared in the background for every mentioned target.
- **2026-10-20 · Plan walkthrough, step 5 (equations):**
  - **Full** reading by default. The user is wary it may sound heavy on long equations: → skips the rest of an equation, and an "auto" mode is an option if needed.
  - **Fallback chain:** verified AI reading → rule-based reading → say only "Equation 3" (unreadable).
  - **Badges** get a "checking…" state, so it's clear when verification isn't done yet; playback never waits for the AI.
  - **Equation references:** pressing `E` on "Eq. (3)" shows a popup anchored over the reference with the equation (crop from the PDF) and its badge, reads it, and returns (P1).
  - Ask the paper uses whole-paper context (measured cheap) instead of retrieval.
- **2026-10-20 · Plan walkthrough, step 4 (the voice):**
  - Default voice `af_heart`, chosen from samples.
  - Section titles announced on entry; footnotes skipped by default (toggle).
  - Pronunciation lexicon is core: shipped `lexicons/science-en.json`, plus a user lexicon that overrides it. The user's pronunciations: PEGDA → "peg-dah" (hard "da"), Tg → "T G". Plain respellings work (verified with Kokoro).
  - The user's idea, a **pronunciation review screen** (P1), lists likely-mispronounced terms per paper, lets you fix them, and supports export/import so lexicons grow and can be shared. It's the seed of an open science pronunciation dataset.
  - Auto-pause after each paragraph is off, a possible addition at the end (P2).
- **2026-10-20 · Plan walkthrough, step 3 (reading screen):**
  - Sentence + word highlight, with 3–4 color presets including high-contrast.
  - Scrolling away stops auto-follow and shows a "Back to reading position" button.
  - Focus mode is on by default (key `F`).
  - No dark or inverted PDF page (the app's interface still follows the system theme).
  - The clean text (reflow) view is a toggle, not side by side.
  - Layout as in the walkthrough mockup: outline on the left, PDF in the center, AI rail on the right, playback bar at the bottom.
- **2026-10-20 · Plan walkthrough, step 2 (opening a paper):**
  - **Resume where I left off** is core (M3).
  - **One paper open at a time**, plus a small "Recent papers" list. I kept that list because it's how you get back to a paper to resume; the user can drop it.
  - **Scanned/OCR PDFs** are the first stretch pick, skipped on the first pass.
  - **Later updates:** starting to listen before parsing finishes, a library from a folder, Zotero.
- **2026-10-20 · Plan walkthrough, step 1 (what it is and how it runs):**
  - **Borderless app window:** Edge `--app` mode + a web app manifest, so it looks like a desktop program.
  - **English only** for now.
  - **Simple install** for the hackathon (README + setup script); a one-click installer is a future goal.
  - **Apache-2.0**, keeping commercial use open, so dependency licenses get tracked from day one.
  - **Name stays SciReader.**
  - **Target is reading on a PC/laptop screen;** a mobile app is a future idea, so keep the backend a clean API.
- **2026-10-20 · Fully offline (user requirement).** The app must work with Wi-Fi off: no cloud APIs, no CDNs, no runtime downloads. arXiv import is the only online feature and must fail gracefully. No cloud API keys anywhere. This also strengthens the pitch: private, free, usable on unpublished work.
- **2026-10-20 · Local LLMs.** `qwen3.5:9b` narrates equations, describes figures, and does explain/ask/summaries. `gemma4:12b` (a different model family, so errors are less correlated) only back-transcribes for verification. Run verification in two batches per paper (all narrations, then all back-transcriptions with `keep_alive: 0`) so the models swap once, not per equation. Use `think: false` and temperature 0 for narration and transcription. No cloud provider is implemented; the provider interface stays generic.
- **2026-10-20 · Verifier design.** Primary check: convert both LaTeX strings to MathML with MathJax (the same Node helper as SRE) and compare canonicalized trees (flatten `mrow`; unify `\varepsilon`/`\epsilon`, `\dfrac`/`\frac`, implicit vs explicit multiplication, `e^{x}`/`\exp`, `\mathrm{A}`/`A`). SymPy equivalence or numeric spot checks are secondary, only when both sides parse. On a mismatch, retry once by telling the narrator what was lost, then fall back to SRE speech.
- **2026-10-20 · Git workflow.** Work on `main` (solo, no reviewer). Tag every working milestone (`m0-setup`, …, `m2-slice`, …, `demo-ready`) and push tags for one-command rollback. Use a short-lived branch only for a risky swap. Don't start the kickoff session in a worktree.
- **2026-10-20 · Direction:** Idea 1 (science-aware reader) over Idea 2 (AI safety for physical sciences). It's buildable solo in 36 h, an agent can build it unattended from a spec, it demos well in a 4-min video, and it answers a real need. Its Relevance risk is countered by being science-native (math/units/chemistry) and by a measurable benchmark. **Confirmed by the user.**
- **2026-10-20 · Combination:** the AI-reliability angle goes into **verified narration**: every LLM rewrite of math is back-transcribed and checked for symbolic equivalence against the source LaTeX; failures fall back to deterministic speech. The benchmark measures how often unverified LLM narration silently changes the math. That's a real faithfulness/hallucination eval at small scale.
- **2026-10-20 · Fidelity principle:** body text is read verbatim (deterministic normalization only). AI touches only equations, figures and tables, plus on-demand features, and always labels itself.
- **2026-10-20 · Stack defaults:** Python 3.12 + uv + FastAPI backend; Vite + React + TS + pdfjs-dist frontend; Node helper for Speech Rule Engine; local web app first, desktop packaging only as a stretch.
- **2026-10-20 · Parser:** Docling first (MIT, Windows-friendly, layout labels + bbox + reading order + formula LaTeX). Time-boxed MinerU 2.5 bake-off (best formula scores on OmniDocBench in 2026; GPU; license moved to a custom Apache-based license in Apr 2026 with commercial terms above a usage threshold, so it stays optional only, given the Apache-2.0 license). Marker is avoided as default (weights restricted above revenue thresholds; verify if revisited).
- **2026-10-20 · TTS:** Kokoro-82M (Apache-2.0, fast, good quality, CPU or GPU) as default. Candidates for a 2nd engine: Piper (low-end CPU), Chatterbox (MIT, cloning), Qwen3-TTS (Apache-2.0). Avoid XTTS-v2 as default (non-commercial license).
- **2026-10-20 · Word highlighting moves to P0 (M2).** The smoke test showed Kokoro returns per-word timestamps and synthesizes a sentence in ~0.1 s, so word-level highlight is cheap and directly serves readers who lose their place.

---

## 6. Product definition (summary; full spec in `docs/prompts/kickoff.md`)

**Pitch:** SciReader is an open-source, local-first reading companion for scientific papers. The PDF stays in front of you; a parsed, structured copy runs in the background so you can click anywhere to start listening, follow a highlight on the real page, and hear equations, units and chemistry spoken the way a scientist would say them, with AI narration that checks itself against the source.

**Principles:** PDF-first · start anywhere · read like a scientist · faithful by default · fully offline & private · one-click models · focus aids for people who lose their place.

**Novelty pillars:** (1) science-aware speech, (2) verified math narration, (3) SciSpeech-Bench, an open benchmark and the write-up figure, (4) fully offline on a consumer GPU, so it works on unpublished manuscripts, papers under review, and with Wi-Fi off.

### Sample papers (chosen and verified 2026-10-20)

All are in the demo domain. Licenses and counts were checked on arXiv and journal pages; "LaTeX" means arXiv has TeX source (usable as benchmark ground truth). PDFs are fetched by script (manifest in `samples/`) and gitignored.

| # | Paper | Source | License | Content | Role |
|---|---|---|---|---|---|
| 1 | Physics-Informed Bayesian learning of electrohydrodynamic polymer jet printing dynamics (Commun. Eng. 2023, doi 10.1038/s44172-023-00069-0) | `nature.com/articles/s44172-023-00069-0.pdf` (4 MB; arXiv 2204.09513 is PDF-only, CC BY-NC-SA there) | CC BY 4.0 | 33 eqs, 9 figs | **Flagship demo**: physics + ML + polymer AM |
| 2 | Polymer informatics at-scale with multitask graph neural networks (Chem. Mater. 2023) | arXiv `2209.13557` (LaTeX) | arXiv default (journal CC BY) | 14 display + 547 inline math, 6 figs | Dense symbols/units, normalizer stress test, bench |
| 3 | ANNs for predicting mechanical properties of crystalline polyamide12 via MD (Polymers 2023) | arXiv `2307.10139` (LaTeX) | arXiv default (journal CC BY) | 7 display + 85 inline, 28 fig panels | PA12, MD + ANN, units, figures, bench |
| 4 | First steps towards ML for prediction and pre-correction in direct laser writing (2025) | arXiv `2511.23306` (LaTeX, 11 MB PDF) | CC BY 4.0 | 4 display + 132 inline, 11 figs, 7 tables | Two-photon polymerization + ML, tables, bench |
| 5 | A critical review for synergic kinetics and strategies for enhanced photopolymerizations for 3D-printing and AM (Polymers 2021, 13, 2325) | `mdpi.com/2073-4360/13/14/2325/pdf`, **manual browser download** to `samples/polym13142325.pdf` | CC BY 4.0 | 10 display eqs, 23 figs | Kinetics + chemistry schemes, two-column journal layout |
| B | Open Polymer Challenge: post-competition report (2025) | arXiv `2512.08896` (LaTeX) | CC BY 4.0 | 6 display + 62 inline, 5 figs | Backup for #5, bench |

**Gotchas (2026-10-20):** the arXiv search API returned 429 "Rate exceeded" on the first call; OpenAlex works (arXiv source filter `locations.source.id:S4306400194`; no key, shared ~$0.10/day budget per IP, about 100 requests). `arxiv.org/abs|html|pdf|src` all respond. MDPI and Europe PMC return 403 to scripted PDF downloads; Nature and arXiv PDFs download fine.

**Competitors (closed, cloud, subscription):** Paper2Audio, Audiolizer, Listening, Audeus, Speechify, ElevenReader. None is open source or local, and none publishes how faithfully it renders math.

---

## 7. Architecture (current truth; update as it gets built)

- `backend/scireader/`: `config.py` (env/.env), `main.py` (FastAPI app, serves `frontend/dist` if built, warms Kokoro at startup), `parsing/` (`docling_parser.py` → `builder.py` heuristics + sentences; `pdfchars.py` PDFium chars/alignment/superscripts; `latex.py` OCR LaTeX cleanup; `inspect_doc.py` CLI), `speech/` (`pipeline.py` citations + normalize; `math_speech.py` Node client; normalizer/splitter/lexicon from the subagent), `tts/` (`engine.py` Kokoro + audio cache, `registry.json` voices), `api/` (`docs.py`, `tts.py`, `jobs.py`), `store/docs.py` (doc cache by SHA-256 prefix, reading state in `state.json`).
- `frontend/src/`: `App.tsx` (start screen + parse progress), `Reader.tsx` (layout, outline, playback bar, settings, keyboard), `PdfView.tsx` (pdf.js pages, overlays, hit testing, follow), `store.ts` (zustand + audio engine), `api.ts` (types).
- `tools/math-speech/index.js`: JSON lines over stdin/stdout, MathJax 3 (mathjax-full) + SRE 5.0-rc (ClearSpeak).
- Data per paper in `.data/docs/<id>/`: `source.pdf`, `docling.json` (cache), `document.json`, `speech.json`, `meta.json`. Audio cache `.data/audio/<key>.wav|.json`.
- Not built yet: `scripts/dev.ps1`, `setup.ps1`, `bench/`, model manager, LLM layer.

**How to run (dev):** `uv run --directory backend uvicorn scireader.main:app --port 8765` + `npm --prefix frontend run dev` → http://localhost:5173. Inspect a parse: `uv run --directory backend python -m scireader.parsing.inspect_doc ../samples/<file>.pdf`.

---

## 8. Roadmap & milestone status

Details in the kickoff prompt §7. **Clock schedule** (Eastern, the machine's time zone; kickoff Wed 6:30 AM, deadline Thu 8:00 PM = 7:00 PM CDT):

| When | What | Who |
|---|---|---|
| Wed 6:30–9:30 | M0–M3 | Agent, unattended |
| Wed ~9:30 | Checkpoint prompt, then a fresh session | User |
| Wed 10:00–16:00 | M4 AI layer | Agent, the user steering |
| Wed 16:00–20:00 | M5 benchmark + marimo analysis; the user's ~30 blind ratings | Agent + ~15 min of the user |
| Wed 20:00–23:00 | M6 starts (pronunciation review screen first) | Agent |
| Wed night | Long benchmark GPU runs keep going; optional agent stretch | GPU / agent |
| Thu 7:00–14:00 | M6 continues, then fixes (fresh session in the morning) | Agent, the user steering |
| **Thu 14:00** | **Feature freeze**, tag `demo-ready` | |
| Thu 14:00–17:00 | M7: README, write-up + figure, video script, repo audit | Agent |
| Thu 17:00–18:30 | User records the video (own voice, not sped up; Windows Snipping Tool or OBS), uploads and posts it | User |
| Thu 18:30–19:00 | Repo public, submission form | User, agent checks |
| Thu 20:00 | Deadline (1 h buffer) | |

**Cut order if behind (cut from the top):**
1. Summaries
2. Auto-pause, audiobook export, arXiv source mode
3. Scanned-PDF OCR
4. Clean text view
5. Benchmark extras (inline and unit items, 4B model, full-PDF pipeline)
6. Equation-reference popup
7. Pronunciation review screen (the lexicon file stays)
8. Ask the paper (Explain stays)

**Never cut:**
- the reader core: click-to-read, highlight, voice, skipping, normalizer + lexicon, resume;
- verified equations with badges;
- figures at first mention;
- a minimal benchmark (100 equations, 4 main conditions) with its marimo figure;
- the video and write-up.

- [x] M0 (0:00–0:20) Setup, scaffold, samples, background model downloads (tag `m0-setup`)
- [ ] M1 (0:20–1:15) Parse → Document JSON ✓, Kokoro synth ✓, sentence split + normalizer + tests (subagent, in progress), MinerU bake-off (dropped, see §5). All 6 samples parse: flagship ~100 s cold, the others 18–27 s.
- [x] M2 (1:15–2:15) **Vertical slice**: PDF viewer, click-to-read, sentence + word highlight, auto-scroll, skipping (tag `m2-slice`)
- [ ] M3 (2:15–3:00) SRE equation speech, model manager, focus mode, outline; "When you're back" section
- [ ] M4 AI layer: verified equation narration, figure narration, explain/ask with citations, summaries
- [ ] M5 SciSpeech-Bench + figure
- [ ] M6 Reflow view, audiobook export, 2nd TTS engine, arXiv source mode
- [ ] M7 Ship: freeze at T-6 h; README, write-up, demo script, video, **make the repo public** (private until then), submission form (by Thu 7 PM CDT)

---

## 9. Open questions for the user

1. Valency and Adaption sponsor prize rules (check on Slack at kickoff; anything we use must work offline). marimo is settled: the benchmark analysis is a marimo notebook.

---

## 10. Parked ideas (not for this hackathon unless the plan changes)

- **Idea 2, sharpest version:** "Do AI-scientist agents fabricate when the science can't be done?" An eval where agents get computational chemistry/materials tasks that are secretly impossible or underspecified (missing data, non-converging setups, contradictory inputs). Measure how often they report fabricated results vs. admit failure. Fills the "verification gap" named in the 2026 AI-scientist surveys (arXiv:2608.05179). Crowded neighbors to differentiate from: SciHazard, LabSafety Bench, LABSHIELD, ChemSafetyBench, WMDP. Good candidate for a post-hackathon project.
- **Future product path (user, 2026-10-20):** one-click installer, mobile app, other languages (French first), library from a folder, Zotero integration, start listening before parsing finishes, asking questions by voice (offline speech recognition), a second voice engine (Qwen3-TTS first: Apache-2.0, multilingual, voice cloning), a community-shared science pronunciation dataset (field packs: polymers, electrochemistry, astrophysics…). Before any closed release: replace GPL pieces (espeak-ng/phonemizer via misaki), avoid MinerU, and re-check model licenses (`docs/LICENSES.md`).
- Podcast-style two-voice paper discussions (VibeVoice-like), but only after fidelity is solved.
- Reading-comprehension checks (quick spoken questions after each section).

---

## 11. Key references

- PDF parsing comparisons 2026: https://dev.to/moksh/pdf-parsers-for-rag-in-2026-when-open-weights-beat-the-frontier-models-4o9n · https://builderai.tools/blog/pdf-parsing-for-rag-mineru-docling-marker-compared · OmniDocBench https://github.com/opendatalab/OmniDocBench · MinerU2.5 arXiv:2509.22186 · MinerU2.5-Pro arXiv:2604.04771
- Local TTS roundups 2026: https://www.yaps.ai/blog/best-local-tts-models · https://localaimaster.com/blog/best-local-tts-models
- Competitor landscape: https://www.audeus.com/blog/best-apps-for-listening-to-research-papers · https://paper2audio.com/faq
- AI safety × science: International AI Safety Report 2026 arXiv:2602.21012 · SciHazard arXiv:2607.18665 · AI-scientist verification gap arXiv:2608.05179

---

## 12. Maintenance rules for this file

- Every session: read it first. After each milestone, decision, gotcha or environment change: update the right section **and delete what's no longer true**.
- Keep it under ~400 lines. Move finished narrative (what was done, what was learned) to `docs/DEVLOG.md` (append-only; it feeds the write-up).
- Dates are absolute (YYYY-MM-DD). Note "unverified" next to anything not yet checked.
- Prompts live in `docs/prompts/`: `kickoff.md` (first message at kickoff) and `followups.md` (checkpoint, resume, iterate, unattended, ship).
