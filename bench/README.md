# SciSpeech-Bench

How faithfully do read-aloud pipelines speak mathematics? An open, reproducible benchmark that runs entirely on a local GPU after a one-time data download.

## Data (`data/`)

- `papers.json`: 24 open arXiv papers (2019–2026), at least half in polymers and materials (the author's field), the rest physics, chemistry and mathematics. IDs, titles, licenses (where OpenAlex reports one) and links.
- `equations.jsonl`: 220 display equations. **Ground truth is the LaTeX from each paper's arXiv source tarball**, not OCR. Rows of `align`-style environments are split into separate equations; simple `\newcommand` macros are expanded; only equations MathJax can render are kept (at most 12 per paper).
- `units.jsonl`: 99 hand-written snippets (units, notation, Greek, chemical formulas, polymer acronyms, abbreviations) with their correct spoken reading.

We store IDs, extracted LaTeX and our annotations, not the papers. Annotations are CC BY 4.0.

## Conditions (`scripts/run.py`)

| | Spoken text |
|---|---|
| a · naive | The equation's glyphs in reading order, the way a generic reader gets them from a PDF text layer (simulated from MathML token order). |
| b · rules | Speech Rule Engine, ClearSpeak style, from the source LaTeX. |
| c · LLM | Local narration by `qwen3.5:9b`, unverified. |
| d · LLM + verify | c, back-transcribed by `gemma4:12b` (never sees the LaTeX) and compared as canonical MathML; one repair round; otherwise fall back to b. This is SciReader's pipeline. |
| f · 4B | c and d with `qwen3.5:4b` as narrator. |

## Metrics

- **Faithfulness:** an independent judge from a third model family (`phi4:14b`) writes each spoken text back as LaTeX, and we compare it to the ground truth as canonical MathML (`backend/scireader/llm/verify.py`): **exact** (same tree after normalizing styles, variants, spacing and implicit multiplication) or **faithful** (same symbols in the same order; brackets or fraction grouping may differ).
- **Silent error rate:** the share of unverified LLM narrations (c) that the judge cannot write back as the same equation.
- **Gate precision/recall:** how well the verification gate's verdict on c predicts the judge's verdict.
- **Units and chemistry by sound (`scripts/units.py`):** each snippet is phonemized three times with misaki and its espeak fallback (exactly the phonemizer Kokoro uses): the raw text a generic reader would send, SciReader's normalized text, and the correct reading. A snippet is mispronounced when the phoneme edit distance to the correct reading exceeds 25 % of its length.
- **Naturalness:** 30 blind clips rated 1–5 by a listener (`rate.py`, a marimo app).

## Run it

```powershell
cd backend
uv sync --group bench
uv run python ../bench/scripts/collect.py      # one-time: OpenAlex + arXiv sources (polite: >= 3 s between requests)
uv run python ../bench/scripts/units.py        # seconds, no GPU
uv run python ../bench/scripts/run.py --judges phi4:14b   # local GPU; every model call is cached on disk
uv run marimo edit ../bench/analysis.py        # interactive analysis; figures go to bench/figures/
uv run marimo export html ../bench/analysis.py -o ../bench/analysis.html
uv run python ../bench/scripts/rating_audio.py && uv run marimo run ../bench/rate.py   # blind ratings
```

Requires Ollama with `qwen3.5:9b`, `qwen3.5:4b`, `gemma4:12b` and `phi4:14b`.

## Extend it

Add queries in `scripts/collect.py` (field, search text) or arXiv IDs to `SAMPLES`, rerun the collector, then `run.py`. Cached model calls make reruns cheap. Contributions of new fields (electrochemistry, astrophysics…) and of adjudicated items are welcome.

**Manual adjudication (30 narrations, `bench/data/adjudication.json`).** We checked 30 unverified 9B narrations by hand (15 the judge accepted, 15 it rejected). The judge's "faithful" calls were right 14/15 times, but its "error" calls only 7/15 times: it often fails to transcribe correct long readings. So the judge underestimates every pipeline; correcting for that, unverified narration still changes about a third of equations. The gate verified 15 of the 30 narrations and **none of them was wrong**; it rejected (or flagged as uncertain) all 8 real errors, and rejected 6 correct narrations, which then fall back to the rule-based reading.

## Caveats

- The naive condition is simulated from MathML token order, not extracted from rendered PDFs.
- Judge errors count against every condition (see the adjudication above).
- The units snippets were written by the same team that wrote the normalizer.
