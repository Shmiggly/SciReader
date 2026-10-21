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
- Logged in to GitHub with gh (config on D: through GH_CONFIG_DIR), created the private repo Shmiggly/SciReader and pushed the prep commit. The repo becomes public at submission.
