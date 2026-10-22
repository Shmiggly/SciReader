**SciReader is an open-source, fully local read-aloud companion for physics, chemistry and materials papers that speaks equations only after checking them: a second AI model writes each spoken equation back to LaTeX and it must match the source exactly. On SciSpeech-Bench, 220 equations from 24 arXiv papers, this gate lifts faithful AI narration from 61 % to 89 %, while a generic reader mispronounces a third of scientific units.**

## Introduction

Listening is how many researchers, especially those with dyslexia, ADHD, low vision or reading in a second language, keep their place in long text, but papers are where read-aloud tools break: they read citation brackets and page headers, say "1.12 eV" as "one point one two ee-vee", and turn equations into noise. LLMs can narrate math fluently, which makes their errors dangerous: a listener cannot see a dropped parenthesis. Commercial paper readers are closed, cloud-only, and none reports how faithfully it reads math. We asked: can a local system read a physical-science paper aloud *and know* when its equation reading is right?

## Methods

**Reader.** The PDF stays on screen exactly as published. Docling parses layout, equations and figures; sentences are aligned to the PDF's characters, so a click starts reading anywhere and a sentence and word highlight follows the voice (Kokoro-82M). A deterministic normalizer reads units, Greek, notation and chemistry ("$\mathrm{Fe_2O_3}$", "mW/cm²"), with a shareable pronunciation dataset per user. Everything runs on one consumer GPU through Ollama, with Wi-Fi off.

**Verified equation narration.** For an equation with source LaTeX $L$, the narrator model ($N$, `qwen3.5:9b`) produces speech $s = N(L)$; an independent checker from another model family ($C$, `gemma4:12b`), which never sees $L$, writes it back as $\hat L = C(s)$. Both are converted to canonical MathML trees $T(\cdot)$, and the narration is spoken only if

$$T\big(C(N(L))\big) = T(L),$$

with one repair round on a mismatch. Otherwise a rule-based reading (Speech Rule Engine) is used, and a badge on every equation shows which. Because OCR'd LaTeX can itself be wrong, each equation is also read a second time from the page image by the vision model, and the PDF's text layer settles disagreements. Figures are described by the vision model at their first mention, panel by panel; references like "Eq. (9)" open the equation with an on-request AI explanation; every AI output is labeled.

**SciSpeech-Bench.** 220 display equations from 24 open arXiv papers (half polymers and materials), arXiv LaTeX as ground truth, four pipelines (naive, rule-based, LLM, LLM + gate), scored by an independent judge (`phi4:14b`) writing each pipeline's speech back to LaTeX. Units and chemistry are scored by sound (phoneme distance), on our snippets and on 50 held-out snippets from 18 other papers. The analysis is a [marimo](https://marimo.io) notebook (`bench/analysis.py`).

![Faithfulness by pipeline](bench/figures/faithfulness.png)

## Results

- **Unverified LLM narration silently changes more than 1 in 3 equations.** On the 70 equations the judge transcribes reliably, `qwen3.5:9b` alone was faithful 61 % of the time (4B: 57 %), with fluent errors: a dropped evaluation bar, $N\alpha$ moved into a denominator in the Lorentz–Lorenz equation.
- **The gate fixes most of it.** It catches about 3 in 4 errors; faithful readings rise to 89 % (9B) and 90 % (4B), so a small model plus a verifier matches a larger one. In a 30-item manual check, none of the gate-verified narrations was wrong.
- **Units and chemistry:** a generic reader mispronounced 36 % of held-out snippets, SciReader 10 %.
- **Parsing is the bottleneck on journal PDFs.** On a Springer Nature paper the gate verified few equations because the OCR'd LaTeX was wrong; reading each equation again from the page corrected 17 of 32 sources (e.g. $K^{-1}$ read as $K^{1}$), and the gate refused what it could not confirm.

![Units by sound](bench/figures/units_heldout.png)

## Conclusions

A faithfulness gate turns an LLM from "usually right" into "right or explicitly unsure", which is what accessibility tools for science need. Measuring it mattered: fluent narration hid a one-in-three error rate that no listener would notice. The pattern (independent back-translation, structural comparison, labeled fallback) applies to any AI that rewrites scientific content, and here it runs privately on a laptop, so it works on unpublished work.

## Future directions

More fields and notations (tensor and chemical-reaction schemes), other languages, larger and community-shared pronunciation datasets per field, a benchmark leaderboard for math narration, inline math and tables, and a phone app. Code, benchmark data (CC BY 4.0 annotations) and the notebook: https://github.com/Shmiggly/SciReader
