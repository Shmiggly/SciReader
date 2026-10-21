# SciReader: listening to physics, chemistry and materials papers without losing the math

*OSI Hackathon 2026 · solo · one-page draft of `writeup.md`, to be reviewed and personalized by the author.*

**The problem.** It's easy to lose your place in long text and reread the same lines; audiobooks fixed that for books, not for papers. Read-aloud tools start at the first character, read headers and reference lists, turn equations into gibberish and units into nonsense ("1.12 eV" becomes "one point one two ee-vee"). Commercial paper readers are closed and cloud-only, and none reports how faithfully it reads math.

**What we built.** SciReader is an open-source (Apache-2.0) reading companion that runs entirely on a laptop GPU, with Wi-Fi off. The real PDF stays on screen: click any sentence to start, and a sentence and word highlight follows the voice. A deterministic normalizer and a shareable pronunciation lexicon read units, Greek, notation and chemistry the way a scientist would. A local LLM narrates each equation; a second model from another family, which never sees the source, writes the narration back to LaTeX, and the two are compared as canonical MathML. Only an exact round trip is spoken as AI; anything else falls back to a rule-based reading, and a badge on every equation says which. Figures pop up at their first mention with panel-aware descriptions; explain and ask cite the sentences they use.

**What we learned.** SciSpeech-Bench: 220 display equations from 24 open arXiv papers (half polymers and materials), arXiv source as ground truth, each pipeline's speech written back by an independent judge (`phi4:14b`).

![Faithfulness by pipeline](../bench/figures/faithfulness.png)

- **Unverified LLM narration silently changes more than 1 in 3 equations.** On the 70 equations the judge reliably transcribes, `qwen3.5:9b` was faithful 61 % of the time (4B: 57 %), with fluent errors: a dropped evaluation bar, a factor swallowed by a denominator.
- **A verifier fixes most of it.** The gate catches 3 in 4 errors; speaking AI only after an exact round trip lifts faithful readings to 89 % (9B) and 90 % (4B), so a small model plus a verifier matches a larger one. In a 30-item manual check (adjudicated by the build agent), none of the 15 gate-verified narrations was wrong.
- **"Almost verified" is not safe.** Narrations that came back with the right symbols but different grouping included the Lorentz–Lorenz equation with Nα moved into the denominator. Only exact round trips are spoken now.
- **Faithfulness is the win, not naturalness.** In blind ratings by the author (10 equations, 1–5), SciReader as shipped scored 3.8, the same as the rule-based reading, both well above a naive reading (2.6).
- **Self-written tests flatter you.** On 99 unit and chemistry snippets we wrote, a generic pipeline mispronounced 47 % and SciReader 0 %; on 50 held-out snippets sampled from 18 papers (references from another model, corrected blind to our output), 36 % vs 10 %.
- **Parsing is the bottleneck on journal PDFs.** On a Springer Nature paper, the OCR'd formula LaTeX was noisy enough that only 6 of 33 equations could be verified; the gate refused the rest, as it should. But it checks against the parse, not the page, so SciReader now reads each equation again from the page with the vision model and lets the PDF's text layer settle disagreements: 17 of 32 take the page reading (K⁻¹ that the OCR read as K¹, all 3 garbled ones).

**Why it matters.** A faithfulness gate turns an LLM from "usually right" into "right or explicitly unsure", which is what accessibility tools for science need: a listener can't see a dropped parenthesis. The same pattern (independent back-translation, structural check, labeled fallback) applies to any AI that rewrites scientific content.

*Code, benchmark data (CC BY 4.0 annotations) and the marimo notebook: https://github.com/Shmiggly/SciReader*
