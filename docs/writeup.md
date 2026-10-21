# SciReader: listening to physics, chemistry and materials papers without losing the math

*OSI Hackathon 2026 · solo · draft written by the agent during the build; to be reviewed and personalized by the author.*

## The problem

It's easy to lose your place in long text and reread the same lines; audiobooks fixed that for books, but not for papers. Read-aloud tools start at the first character and read running headers, citation brackets and the reference list; equations come out as gibberish; units are mangled ("1.12 eV at 300 K" → "one point one two ee-vee at three hundred kay"). Commercial paper readers are closed, cloud-only, and silent about how faithfully they render math, so they can't be trusted with manuscripts under review. In the physical sciences the wall is specifically equations, units, chemical formulas and figures.

## What we built

SciReader is an open-source (Apache-2.0) reading companion that runs entirely on a laptop GPU, with Wi-Fi off.

- **PDF-first:** the real PDF stays on screen. Docling parses layout, reading order and formula LaTeX; PDFium glyph boxes give every sentence and word a rectangle, so clicking any sentence starts reading there and a highlight follows the voice (Kokoro-82M, ~0.06 s per sentence). Page furniture, citation markers (including superscript numerals, found from glyph size and baseline), affiliations and references are skipped.
- **Read like a scientist:** a deterministic normalizer (284 tests) handles units, notation, Greek, chemistry and abbreviations; a shareable pronunciation lexicon and a review screen let users fix how terms like "PEGDA" sound across every paper.
- **Verified math narration:** a local LLM narrates each equation; a second model from another family, which never sees the LaTeX, writes the narration back; the two are compared as canonical MathML trees. Mismatches get one repair round, then fall back to a rule-based reading (Speech Rule Engine). Every equation carries a badge (✓ verified, ? uncertain, ✗ rules, unreadable).
- **Local AI, always labeled:** figures pop up at their first mention with panel-aware descriptions ("Fig. 3b" describes only panel b); explain, ask and summaries cite the sentences they rely on.

## What we learned (SciSpeech-Bench)

We built an open benchmark: 220 display equations from 24 open arXiv papers (half polymers/materials), with arXiv LaTeX source as ground truth. Each pipeline's speech is written back to LaTeX by an independent judge (`phi4:14b`) and compared structurally.

![Faithfulness by pipeline](../bench/figures/faithfulness.png)

- **Unverified local LLM narration silently changes about 1 in 3 equations.** On the 63 equations the judge can reliably transcribe, `qwen3.5:9b` narrations were faithful 64 % of the time (`qwen3.5:4b`: 57 %). The errors are fluent and plausible-sounding: a dropped evaluation bar, a denominator that swallows a factor, a subscript that becomes a product.
- **Verification catches most of them.** The back-transcription gate flags ~4 in 5 errors, lifting faithful readings to 89 % (9B) and 87 % (4B). In a manual check of 30 narrations, none of the gate-verified ones was wrong. It still uses natural AI narration for 45 % of equations; the rest fall back to rule-based speech. A smaller model plus a verifier nearly matches a larger one plus a verifier.
- **A generic reader's text-layer reading** was faithful for only 41 % of the same equations, and on 99 unit and chemistry snippets scored by phonemes, a generic pipeline mispronounced 47 % versus 0 % for SciReader.
- **Measurement matters.** Our first scoring said every pipeline was ~15 % faithful; the cause was the judge's formatting and our comparator, not the pipelines. Structural comparison of canonical MathML (not SymPy, which failed on most physics notation, and not string similarity) plus a judge from a third model family were essential, and the judge remains the ceiling over all 220 equations (naive 24 %, rules 29 %, LLM 32 %, verified 38 %).
- **Parsing is the real bottleneck on journal PDFs.** On a Springer Nature paper, OCR'd formula LaTeX was noisy enough that only 5 of 33 equations could be verified; the gate correctly refused the rest. For arXiv papers, SciReader can swap in the source LaTeX.

## Why it matters

A faithfulness gate turns an LLM from "usually right" into "right or explicitly unsure", which is what accessibility tools for science need: a listener can't see that a narration dropped a parenthesis. The same pattern (independent back-translation + structural check + labeled fallback) applies to any AI that rewrites scientific content. Next: per-field pronunciation packs, more languages (French first), a mobile client, and adjudicated benchmark items.

*Code, benchmark data (CC BY 4.0 annotations) and the marimo analysis notebook: https://github.com/Shmiggly/SciReader*
