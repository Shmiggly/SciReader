# SciSpeech-Bench

How faithfully do read-aloud pipelines speak mathematics? An open, reproducible benchmark that runs entirely on a local GPU after a one-time data download.

## Data (`data/`)

- `papers.json`: 24 open arXiv papers (2019–2026), at least half in polymers and materials (the author's field), the rest physics, chemistry and mathematics. IDs, titles, licenses (where OpenAlex reports one) and links.
- `equations.jsonl`: 220 display equations. **Ground truth is the LaTeX from each paper's arXiv source tarball**, not OCR. Rows of `align`-style environments are split into separate equations; simple `\newcommand` macros are expanded; only equations MathJax can render are kept (at most 12 per paper).
- `units.jsonl`: 99 hand-written snippets (units, notation, Greek, chemical formulas, polymer acronyms, abbreviations) with their correct spoken reading.
- `units_heldout_dev.jsonl`, `units_heldout_test.jsonl`: snippets sampled automatically from the PDF text layer of 18 benchmark papers that are neither app samples nor math papers, with reference readings by `phi4:14b`; `units_heldout_fixes.json` holds the hand corrections to those references (and the non-prose snippets dropped), decided before scoring and without looking at SciReader's output.

We store IDs, extracted LaTeX and our annotations, not the papers. Annotations are CC BY 4.0.

## Conditions (`scripts/run.py`)

| | Spoken text |
|---|---|
| a · naive | The equation's glyphs in reading order, the way a generic reader gets them from a PDF text layer (simulated from MathML token order). |
| b · rules | Speech Rule Engine, ClearSpeak style, from the source LaTeX. |
| c · LLM | Local narration by `qwen3.5:9b`, unverified. |
| d · LLM + verify | c, back-transcribed by `gemma4:12b` (never sees the LaTeX) and compared as canonical MathML; one repair round; spoken only after an exact round trip, otherwise b ("uncertain" grouping included). This is SciReader's pipeline. |
| f · 4B | c and d with `qwen3.5:4b` as narrator. |

## Metrics

- **Faithfulness:** an independent judge from a third model family (`phi4:14b`) writes each spoken text back as LaTeX, and we compare it to the ground truth as canonical MathML (`backend/scireader/llm/verify.py`): **exact** (same tree after normalizing styles, variants, spacing and implicit multiplication) or **faithful** (same symbols in the same order; brackets or fraction grouping may differ).
- **Silent error rate:** the share of unverified LLM narrations (c) that the judge cannot write back as the same equation.
- **Gate precision/recall:** how well the verification gate's verdict on c predicts the judge's verdict.
- **Units and chemistry by sound (`scripts/units.py`, `scripts/units_heldout.py`):** each snippet is phonemized three times with misaki and its espeak fallback (exactly the phonemizer Kokoro uses): the raw text a generic reader would send, SciReader's normalized text, and the correct reading. A snippet is mispronounced when the phoneme edit distance to the correct reading exceeds 25 % of its length. In the held-out set, a chemical formula counts as right in either convention (compound name or element symbols) for both readers. Its `dev` sample was used to find and fix normalizer gaps; the `test` sample (disjoint) was scored once, after the fixes: **generic reader 36 %, SciReader 10 % mispronounced (50 snippets)**, against 47 % vs 0 % on our own 99 snippets.
- **Naturalness:** 30 blind clips rated 1–5 by a listener (`rate.py`, a marimo app); results below.
- **Equation OCR (`scripts/ocr_accuracy.py`):** how often the app's source LaTeX for a display equation is right, before any narration. It compares, against each sample paper's own arXiv LaTeX, the PDF parser's formula OCR (Docling), `qwen3.5:9b` reading the equation's crop of the page, and the reading the app uses after its second reading (agreement, or the PDF text layer as tiebreaker; `backend/scireader/llm/page_reading.py`). On 20 equations from 3 arXiv-typeset samples (the 4th didn't align): parser 18 exact, vision 17, app 18; the two readings agreed on 18 (17 right), 2 stayed disputed, and the vision reading was never picked over a correct parse. These clean pdfTeX papers are the easy case; the gain is on publisher PDFs with noisy OCR (the Springer flagship, which has no arXiv source: 17 of 32 equations take the page reading, see the main README).

## Run it

```powershell
cd backend
uv sync --group bench
uv run python ../bench/scripts/collect.py      # one-time: OpenAlex + arXiv sources (polite: >= 3 s between requests)
uv run python ../bench/scripts/units.py        # seconds, no GPU
uv run python ../bench/scripts/units_heldout.py test --golds   # fetch PDFs, sample, phi4 references (review them)
uv run python ../bench/scripts/units_heldout.py test           # score
uv run python ../bench/scripts/run.py --judges phi4:14b   # local GPU; every model call is cached on disk
uv run marimo edit ../bench/analysis.py        # interactive analysis; figures go to bench/figures/
uv run marimo export html ../bench/analysis.py -o ../bench/analysis.html
uv run python ../bench/scripts/rating_audio.py && uv run marimo run ../bench/rate.py   # blind ratings
```

Requires Ollama with `qwen3.5:9b`, `qwen3.5:4b`, `gemma4:12b` and `phi4:14b`.

## Extend it

Add queries in `scripts/collect.py` (field, search text) or arXiv IDs to `SAMPLES`, rerun the collector, then `run.py`. Cached model calls make reruns cheap. Contributions of new fields (electrochemistry, astrophysics…) and of adjudicated items are welcome.

## Results (judge `phi4:14b`)

- **Judge-capable subset (70 equations whose rules reading the judge reconstructs):** naive 43 %, unverified LLM 9B 61 % (so it silently changes 39 %), 9B + verify 89 %; 4B 57 % → 90 %. The gate catches 78 % (9B) and 77 % (4B) of the judge's errors. AI narration is spoken for 81 of 220 equations (37 %).
- **All 220 equations** (the judge is the ceiling): naive 25 %, rules 32 %, LLM 33 %, LLM + verify 40 %, 4B 32 %, 4B + verify 37 %.
- These numbers use the comparator as of tag `m6.3-equations`, which also treats as equal what prints the same: parentheses around a one-symbol function argument, where an evaluation bar's or a bracket's script attaches (`\left(x\right)^2` vs `(x)^2`), and operator names (`\det` vs `\operatorname{det}`). Rescoring the cached model calls changed no spoken narration's correctness in the 30-item manual check.

**Manual adjudication (30 narrations, `bench/data/adjudication.json`).** The agent that built the pipeline checked 30 unverified 9B narrations by hand (15 the judge accepted, 15 it rejected), so treat this as a sanity check, not an independent audit. The judge's "faithful" calls were right 14/15 times, but its "error" calls only 7/15 times: it often fails to transcribe correct long readings. So the judge underestimates every pipeline; correcting for that, unverified narration still changes about a third of equations. The gate verified 15 of the 30 narrations and **none of them was wrong**; it rejected or marked uncertain all 8 real errors, and rejected 6 correct narrations, which then fall back to the rule-based reading. One of the 2 uncertain narrations was a real error (Lorentz–Lorenz, Nα moved into the denominator), which is why uncertain narrations are not spoken.

**Blind ratings (`results/ratings.json`).** The author rated 30 clips (10 equations × naive / rules / SciReader, random order, pipeline hidden) from 1 to 5: naive 2.6, rules 3.8, AI narration as rated 4.0. Three of the ten AI clips were uncertain narrations that SciReader no longer speaks; with the rules clip's score in their place (rated in the same session), SciReader as shipped scores 3.8, the same as rules. One rules clip still used older wording ("sub normal Gamma").

## Caveats

- The naive condition is simulated from MathML token order, not extracted from rendered PDFs.
- Judge errors count against every condition (see the adjudication above).
- `units.jsonl` was written by the same team that wrote the normalizer; the held-out set exists for that reason. Its references come from an LLM with hand corrections, and the 0.25 phoneme threshold is a convention.
- Rules readings were re-judged after a wording fix (upright Δ is "delta", not "normal triangle"; capital Greek is "capital Theta"), which changed 29 equations' rules readings.
