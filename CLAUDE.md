# SciReader: instructions for Claude

@NOTES.md

## Always
- `NOTES.md` (imported above) is the source of truth for this project: hackathon facts, decisions, environment, architecture, roadmap, open questions. Read it before doing anything.
- Keep it current. After any decision, milestone, discovered gotcha or environment change, update the relevant section of `NOTES.md` and **remove information that is no longer true**. Append the narrative of what was done and learned to `docs/DEVLOG.md`.
- Hackathon mode: deadline **Thu Oct 22, 2026, 7:00 PM CDT**. Speed over polish, keep `main` runnable, commit after every working step.
- When the user is away, never block on them: decide, log the decision in `NOTES.md`, put questions in its "Open questions" section, keep working.

## Environment
- Windows 11; prefer PowerShell scripts for dev tooling (`scripts/*.ps1`). Python via `uv`, frontend via `npm`.
- Model weights and caches go on D: (`D:\models\...`). C: is nearly full. Cache/tool env vars already point to D: (see NOTES §3).
- Claude desktop is MSIX-packaged: anything your shells write under `%APPDATA%`/`%LOCALAPPDATA%` lands in a private redirected copy. Don't install tools or caches there.
- Use `uv run` for Python; bare `python` is the Microsoft Store stub.
- Never commit secrets (`.env`), model weights, or PDFs we can't redistribute.
- Load the `claude-api` skill before writing Claude API code.
