# SciReader — Project Notes (living document)

> **Single source of truth across conversations.** Auto-loaded through `CLAUDE.md`.
> Update it at every milestone and after every decision, gotcha or environment change.
> Keep it current: delete what is no longer true instead of stacking corrections. History goes to `docs/DEVLOG.md`.

**Last updated:** 2026-10-20 (evening before the hackathon, prep only)

---

## 0. When you're back (agent writes this at the end of each unattended stretch)

_Empty until the hackathon starts. Format: 5-line summary · how to launch · 2-minute test script · decisions to review · questions._

---

## 1. Status at a glance

- **Phase:** PRE-HACKATHON. No app code yet (code gets written during the event).
- **Direction (confirmed 2026-10-20):** Idea 1 (science-aware read-aloud reader) + "verified math narration" as the bridge to AI reliability/safety.
- **Toolchain:** installed and verified 2026-10-20 (§3).
- **GitHub:** private repo https://github.com/Shmiggly/SciReader (prep committed and pushed).
- **Next actions (user):** restart the Claude app, finish the rest of §4. At kickoff, fill the blanks at the top of `docs/prompts/kickoff.md` and send it as the first message of a fresh session opened in this repo.

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

- Demo domain: **TBD** (sample papers should come from it).
- The problem: readers who lose their place reread the same lines; audiobooks help with books. Existing open-source readers fail on papers (start at the first character, read everything, bad voices, no section selection).
- **Machine:** Windows 11 Home, PowerShell 5.1 + Git Bash. RTX 4070 (12 GB VRAM, driver 617.42), 64 GB RAM.
  Disk: **D: ~840 GB free** (use it for models/caches), **C: 89 % full (~107 GB free)**: never let caches default to C:.
- **Toolchain (installed & verified 2026-10-20):** git 2.55 · uv 0.13.4 · Python 3.12.15 (uv-managed, `D:\tools\uv\python`) · Node 24.20.0 LTS + npm 11.19 (`C:\Program Files\nodejs`) · gh 2.102.0 (`C:\Program Files\GitHub CLI`, **not logged in yet**). Not installed: Ollama, Docker. No `ANTHROPIC_API_KEY` yet.
- **User env vars (HKCU) set 2026-10-20:** `HF_HOME=D:\models\hf` · `UV_CACHE_DIR=D:\cache\uv` · `UV_PYTHON_INSTALL_DIR=D:\tools\uv\python` · `UV_TOOL_DIR=D:\tools\uv\tools` · `NPM_CONFIG_CACHE=D:\cache\npm` · `GH_CONFIG_DIR=D:\tools\gh`. App model dir planned: `D:\models\scireader`.
- **Python usage:** always `uv run …` / `uv venv`. Bare `python` hits the Microsoft Store alias; `~\.local\bin` (uv's `python3.12.exe` shim) is not on PATH.
- **Conda:** Miniconda3 (Python 3.12.4) and Anaconda Desktop are installed (plus old Anaconda2 leftovers), but they're not on PATH and not hooked into PowerShell or bash. Don't use them for this project and don't run `conda init` (an auto-activated base env can confuse uv's interpreter discovery). uv is the only Python toolchain.
- **gh config:** `GH_CONFIG_DIR=D:\tools\gh` (user env var, set 2026-10-20). gh's default `%APPDATA%\GitHub CLI` would be redirected inside the Claude app (see the MSIX gotcha below); this way the app and normal terminals share one login. The user ran `gh auth login --web` (HTTPS) from the app's Terminal panel on 2026-10-20. Verify with `gh auth status`.
- **Gotcha: Claude desktop is an MSIX-packaged app.** Shells it launches have writes to `%APPDATA%`/`%LOCALAPPDATA%` silently redirected to `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\…`, invisible to normal terminals (and it broke uv's Python junction). Keep tools and caches on D: through the env vars above. Installers run through winget/msiexec are unaffected.
- **Gotcha: env changes need a restart.** Shells inherit the environment the Claude app started with. After installing tools or changing env vars, restart the Claude app (or refresh `$env:Path` from the registry inside the command).
- **Repo:** local `D:\Github\SciReader\SciReader`, branch `main`, remote `origin` = https://github.com/Shmiggly/SciReader (**PRIVATE** until submission; flipping it public is in M7). The outer `D:\Github\SciReader` folder only holds this repo.
- **GitHub:** account `Shmiggly`, gh logged in over HTTPS (token in Windows Credential Manager, config in `D:\tools\gh`). `gh auth setup-git` is done, so `git push` uses gh's login. That needs `GH_CONFIG_DIR` in the environment: restart the Claude app, or set `$env:GH_CONFIG_DIR = 'D:\tools\gh'` in the command. Git identity: `Shmiggly` (global config). In PowerShell 5.1, commit with `git commit -F <file>` because here-strings piped to `-F -` don't arrive.

---

## 4. Pre-hackathon checklist (tonight, user does these)

Installs can trigger UAC prompts, which would stall an unattended agent, so they happen tonight.

- [x] uv, Python 3.12, Node LTS, GitHub CLI installed; caches and Python moved to D: (see §3). Done 2026-10-20.
- [x] gh logged in as Shmiggly; private repo `Shmiggly/SciReader` created and pushed. Done 2026-10-20.
- [ ] **Restart the Claude desktop app** before kickoff so new sessions inherit the new PATH and env vars.
- [ ] Optional pre-downloads (saves ~15 min at kickoff): `uvx --from huggingface_hub hf download hexgrad/Kokoro-82M`. Optional GPU smoke test (CUDA PyTorch + Kokoro) to catch Windows/CUDA/espeak issues tonight rather than during the unattended stretch.
- [ ] Optional: `winget install --id Ollama.Ollama -e` (fully offline LLM fallback; a 7–8B model fits in 12 GB).
- [ ] Get an Anthropic API key or sponsor credits; at kickoff put it in `.env` (gitignored), never in chat or commits.
- [ ] Pick 3–5 papers from your own field that are genuinely hard to read (equations, units, figures). arXiv IDs are ideal.
- [ ] Claude desktop app: session in **auto** permission mode (not plan mode), keep-awake on, Windows sleep off while plugged in.
- [ ] At kickoff: read the sponsor prize rules (Valency, Adaption, marimo) on Slack and note them in the kickoff prompt.

---

## 5. Decision log (newest first; one line of reasoning each)

- **2026-10-20 · Direction:** Idea 1 (science-aware reader) over Idea 2 (AI safety for physical sciences). It's buildable solo in 36 h, an agent can build it unattended from a spec, it demos well in a 4-min video, and it answers a real need. Its Relevance risk is countered by being science-native (math/units/chemistry) and by a measurable benchmark. **Confirmed by the user.**
- **2026-10-20 · Combination:** the AI-reliability angle goes into **verified narration**: every LLM rewrite of math is back-transcribed and checked for symbolic equivalence against the source LaTeX; failures fall back to deterministic speech. The benchmark measures how often unverified LLM narration silently changes the math. That's a real faithfulness/hallucination eval at small scale.
- **2026-10-20 · Fidelity principle:** body text is read verbatim (deterministic normalization only). AI touches only equations, figures and tables, plus on-demand features, and always labels itself.
- **2026-10-20 · Stack defaults:** Python 3.12 + uv + FastAPI backend; Vite + React + TS + pdfjs-dist frontend; Node helper for Speech Rule Engine; local web app first, desktop packaging only as a stretch.
- **2026-10-20 · Parser:** Docling first (MIT, Windows-friendly, layout labels + bbox + reading order + formula LaTeX). Time-boxed MinerU 2.5 bake-off (best formula scores on OmniDocBench in 2026; GPU; license moved to a custom Apache-based license in Apr 2026, fine for open source). Marker is avoided as default (weights restricted above revenue thresholds; verify if revisited).
- **2026-10-20 · TTS:** Kokoro-82M (Apache-2.0, fast, good quality, CPU or GPU) as default. Candidates for a 2nd engine: Piper (low-end CPU), Chatterbox (MIT, cloning), Qwen3-TTS (Apache-2.0). Avoid XTTS-v2 as default (non-commercial license). Word timestamps from Kokoro are **unverified**: fall back to sentence-level highlight.
- **2026-10-20 · LLM:** provider abstraction. Claude via API when a key exists (claude-sonnet-5-5 for quality, claude-haiku-5-5 for bulk), any OpenAI-compatible local server otherwise, and a full no-LLM mode.

---

## 6. Product definition (summary; full spec in `docs/prompts/kickoff.md`)

**Pitch:** SciReader is an open-source, local-first reading companion for scientific papers. The PDF stays in front of you; a parsed, structured copy runs in the background so you can click anywhere to start listening, follow a highlight on the real page, and hear equations, units and chemistry spoken the way a scientist would say them, with AI narration that checks itself against the source.

**Principles:** PDF-first · start anywhere · read like a scientist · faithful by default · local & private · one-click models · focus aids for people who lose their place.

**Novelty pillars:** (1) science-aware speech, (2) verified math narration, (3) SciSpeech-Bench, an open benchmark and the write-up figure, (4) local/private, so it works on unpublished manuscripts and papers under review.

**Competitors (closed, cloud, subscription):** Paper2Audio, Audiolizer, Listening, Audeus, Speechify, ElevenReader. None is open source or local, and none publishes how faithfully it renders math.

---

## 7. Architecture (current truth; update as it gets built)

_Planned, not built yet:_ `backend/` (FastAPI; parsing, speech, tts, llm, api, store) · `frontend/` (React + pdf.js) · `tools/math-speech/` (Node SRE helper) · `bench/` (SciSpeech-Bench) · `scripts/` (dev.ps1, setup.ps1) · `docs/` (DEVLOG, screenshots, writeup, demo script, prompts) · `samples/` (test PDFs, mostly gitignored).
Model dir: `D:\models\scireader`. HF cache: `D:\models\hf`.

**How to run:** _not yet._

---

## 8. Roadmap & milestone status

Times are from kickoff. Details in the kickoff prompt §7.

- [ ] M0 (0:00–0:20) Setup, scaffold, samples, background model downloads
- [ ] M1 (0:20–1:15) Parse → Document JSON, sentence split, normalizer + tests, Kokoro synth, MinerU bake-off
- [ ] M2 (1:15–2:15) **Vertical slice**: PDF viewer, click-to-read, highlight, auto-scroll, skipping
- [ ] M3 (2:15–3:00) SRE equation speech, model manager, focus mode, outline; "When you're back" section
- [ ] M4 AI layer: verified equation narration, figure narration, explain/ask with citations, summaries
- [ ] M5 SciSpeech-Bench + figure
- [ ] M6 Reflow view, word-level highlight, audiobook export, 2nd TTS engine, arXiv source mode
- [ ] M7 Ship: freeze at T-6 h; README, write-up, demo script, video, **make the repo public** (private until then), submission form (by Thu 7 PM CDT)

---

## 9. Open questions for the user

1. Domain, and 3–5 sample papers?
2. Which LLM access will you have (Anthropic key, sponsor credits, local only)?
3. Sponsor prize rules (Valency / Adaption / marimo): is one worth targeting? (marimo is cheap to target: the benchmark analysis could be a marimo notebook.)

---

## 10. Parked ideas (not for this hackathon unless the plan changes)

- **Idea 2, sharpest version:** "Do AI-scientist agents fabricate when the science can't be done?" An eval where agents get computational chemistry/materials tasks that are secretly impossible or underspecified (missing data, non-converging setups, contradictory inputs). Measure how often they report fabricated results vs. admit failure. Fills the "verification gap" named in the 2026 AI-scientist surveys (arXiv:2608.05179). Crowded neighbors to differentiate from: SciHazard, LabSafety Bench, LABSHIELD, ChemSafetyBench, WMDP. Good candidate for a post-hackathon project.
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
