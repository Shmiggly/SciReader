# SciReader: listening to physics, chemistry and materials papers without losing the math

*OSI Hackathon 2026 · solo · draft written by the agent during the build; to be reviewed and personalized by the author.*

## The problem

It's easy to lose your place in long text and reread the same lines; audiobooks fixed that for books, but not for papers. Read-aloud tools start at the first character and read running headers, citation brackets and the reference list; equations come out as gibberish; units are mangled ("1.12 eV at 300 K" → "one point one two ee-vee at three hundred kay"). Commercial paper readers are closed, cloud-only, and silent about how faithfully they render math, so they can't be trusted with manuscripts under review. In the physical sciences the wall is specifically equations, units, chemical formulas and figures.

## What we built

SciReader is an open-source (Apache-2.0) reading companion that runs entirely on a laptop GPU, with Wi-Fi off.

- **PDF-first:** the real PDF stays on screen. Docling parses layout, reading order and formula LaTeX; PDFium glyph boxes give every sentence and word a rectangle, so clicking any sentence starts reading there and a highlight follows the voice (Kokoro-82M, ~0.06 s per sentence). Page furniture, citation markers (including superscript numerals, found from glyph size and baseline), affiliations and references are skipped.
- **Read like a scientist:** a deterministic normalizer (284 tests) handles units, notation, Greek, chemistry and abbreviations; a shareable pronunciation lexicon and a review screen let users fix how terms like "PEGDA" sound across every paper.
- **Verified math narration:** a local LLM narrates each equation; a second model from another family, which never sees the LaTeX, writes the narration back; the two are compared as canonical MathML trees. Only an exact round trip is spoken as AI; anything else (one repair round included) falls back to a rule-based reading (Speech Rule Engine). Every equation carries a badge (✓ verified, ? uncertain, ✗ rules, unreadable).
- **Local AI, always labeled:** figures pop up at their first mention with panel-aware descriptions ("Fig. 3b" describes only panel b); explain, ask and summaries cite the sentences they rely on.

## What we learned (SciSpeech-Bench)

We built an open benchmark: 220 display equations from 24 open arXiv papers (half polymers/materials), with arXiv LaTeX source as ground truth. Each pipeline's speech is written back to LaTeX by an independent judge (`phi4:14b`) and compared structurally.

![Faithfulness by pipeline](../bench/figures/faithfulness.png)

- **Unverified local LLM narration silently changes about 1 in 3 equations.** On the 66 equations the judge can reliably transcribe, `qwen3.5:9b` narrations were faithful 64 % of the time (`qwen3.5:4b`: 59 %). The errors are fluent and plausible-sounding: a dropped evaluation bar, a denominator that swallows a factor, a subscript that becomes a product.
- **Verification catches most of them.** The back-transcription gate catches 3 in 4 errors; speaking AI only after an exact round trip lifts faithful readings to 88 % (9B) and 91 % (4B), with AI narration used for 37 % of equations and rule-based speech for the rest. A small model plus a verifier does as well as a larger one. In a manual check of 30 narrations, none of the gate-verified ones was wrong.
- **"Almost verified" is not safe.** We first also spoke narrations that came back with the right symbols but different grouping. One of the two in our manual check was the Lorentz–Lorenz equation with Nα moved into the denominator: grouping is exactly where LLMs fail silently. Now only exact round trips are spoken.
- **Naturalness (blind ratings by the author, 10 equations × 3 readings, 1–5):** naive 2.6, rules 3.8, SciReader as shipped 3.8 (the AI narrations alone rated 4.0, but three of them were the "almost verified" kind). Verified narration is as easy to follow as the rule-based reading, and both are far above a generic reader; its value is that it reads like a person when it can prove it is right.
- **Self-written tests flatter you.** On 99 unit and chemistry snippets we wrote, a generic pipeline mispronounced 47 % and SciReader 0 %. On 50 held-out snippets sampled automatically from 18 papers (reference readings from another model, corrected blind to our output), it is 36 % vs 10 %. A generic reader's text-layer reading of equations was faithful for 44 %.
- **Measurement matters.** Our first scoring said every pipeline was ~15 % faithful; the cause was the judge's formatting and our comparator, not the pipelines. Structural comparison of canonical MathML (not SymPy, which failed on most physics notation, and not string similarity) plus a judge from a third model family were essential, and the judge remains the ceiling over all 220 equations (naive 24 %, rules 30 %, LLM 32 %, verified 37 %).
- **Parsing is the real bottleneck on journal PDFs.** On a Springer Nature paper, OCR'd formula LaTeX was noisy enough that only 6 of 33 equations could be verified; the gate correctly refused the rest. But the gate checks the narration against the *parsed* LaTeX, not the page: the parser had folded the bold label "Charge:" into one formula, and the narration faithfully read "C h arg e times sigma". Taking labels from the PDF text layer fixed that case; for arXiv papers, SciReader can swap in the source LaTeX.

## Why it matters

A faithfulness gate turns an LLM from "usually right" into "right or explicitly unsure", which is what accessibility tools for science need: a listener can't see that a narration dropped a parenthesis. The same pattern (independent back-translation + structural check + labeled fallback) applies to any AI that rewrites scientific content. Next: per-field pronunciation packs, more languages (French first), a mobile client, and adjudicated benchmark items.

*Code, benchmark data (CC BY 4.0 annotations) and the marimo analysis notebook: https://github.com/Shmiggly/SciReader*
