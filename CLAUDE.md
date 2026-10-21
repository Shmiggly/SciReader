# SciReader: instructions for Claude

@NOTES.md

## Always
- `NOTES.md` (imported above) is the source of truth for this project: hackathon facts, decisions, environment, architecture, roadmap, open questions. Read it before doing anything.
- Keep it current. After any decision, milestone, discovered gotcha or environment change, update the relevant section of `NOTES.md` and **remove information that is no longer true**. Append the narrative of what was done and learned to `docs/DEVLOG.md`.
- Hackathon mode: deadline **Thu Oct 22, 2026, 7:00 PM CDT**. Speed over polish, keep `main` runnable, commit after every working step.
- When the user is away, never block on them. Decide technical things yourself and log them in `NOTES.md`. For choices that matter to them, send a one-line `PushNotification` (question + the default you're taking), note it in NOTES §9, and keep working with the default.

## Environment
- Windows 11; prefer PowerShell scripts for dev tooling (`scripts/*.ps1`). Python via `uv`, frontend via `npm`.
- Model weights and caches go on D: (`D:\models\...`). C: is nearly full. Cache/tool env vars already point to D: (see NOTES §3).
- Claude desktop is MSIX-packaged: anything your shells write under `%APPDATA%`/`%LOCALAPPDATA%` lands in a private redirected copy. Don't install tools or caches there.
- Use `uv run` for Python; bare `python` is the Microsoft Store stub.
- Never commit secrets (`.env`), model weights, or PDFs we can't redistribute.
- Fully offline at runtime: no cloud APIs, no CDN links, no runtime downloads. LLMs run through Ollama at `http://127.0.0.1:11434` (`qwen3.5:9b`, `gemma4:12b`). Don't build anything that needs a cloud API key.
- Work on `main`, tag working milestones, push after each one. Use subagents sparingly (each one re-reads the project).
