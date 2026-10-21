# SciReader: follow-up prompts

Short prompts for later sessions. `NOTES.md` is auto-loaded through `CLAUDE.md`, so these stay short. Paste the text under a heading.

## Checkpoint: when I'm back

I'm back. Before anything else:
1. Show me what works: start the app in the browser pane and walk me through it on one sample paper, with screenshots.
2. List what's broken or faked, the decisions you made that I should review, and your questions (also in NOTES.md §0 and §9).
3. Given the deadline (Thu Oct 22, 7:00 PM CDT) and the time left, propose the plan for the next block: what to cut, what to keep, in order.
Then wait for my go-ahead.

## Resume: new session, same plan

Continue SciReader. Read NOTES.md (auto-loaded), the last entries of docs/DEVLOG.md and `git log --oneline -15`. Then continue with the next unchecked milestone in NOTES.md §8, following the operating rules in docs/prompts/kickoff.md §0. Update NOTES.md and commit after each working step.
My feedback / changes since last time: ______

## Iterate: after I've tested something

Here's my feedback from testing, in priority order:
1. ______
2. ______
Fix them in this order. For each one, reproduce it first, fix, verify in the browser pane, commit. Log anything that changes the plan in NOTES.md. Don't start new features until these are done.

## Unattended again (I'm stepping away)

I'm stepping away for about ___ hours. Work unattended with the rules in docs/prompts/kickoff.md §0 (never wait on me, decide and log, commit often, time-box). Goals for this stretch, in order: ______. When done or blocked, write NOTES.md §0 "When you're back".

## Ship: final stretch (start no later than 8 h before the deadline)

Feature freeze now. Do M7 from docs/prompts/kickoff.md §7:
1. Make the README submission-ready: pitch, screenshots/GIF, install and run steps, features, architecture diagram, benchmark figure + numbers, dependency licenses.
2. Write docs/writeup.md: one page, one figure, what we built and what we learned.
3. Write docs/demo_script.md: a ≤ 4-min video script, beat by beat, with what's on screen for each line.
4. Audit the repo before it goes public: no secrets, no `.env`, no weights, no PDFs we can't redistribute; a clean clone + setup works from the README. Also check NOTES.md and docs/ for personal details I may not want public, and list them for me to decide.
5. **Make the repo public** (it's private until now; the submission requires a public repo with a README): after I OK the audit, run `gh repo edit Shmiggly/SciReader --visibility public --accept-visibility-change-consequences`, then check that the repo page opens in a logged-out browser.
6. List anything I must do by hand (record the video, social post, submission form).
