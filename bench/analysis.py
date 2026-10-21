import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="SciSpeech-Bench")


@app.cell
def _():
    import json
    from pathlib import Path

    import marimo as mo
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    ROOT = Path(__file__).resolve().parent
    return Path, ROOT, json, mo, pd, plt


@app.cell
def _(mo):
    mo.md(
        """
        # SciSpeech-Bench: how faithfully do read-aloud pipelines speak math?

        Ground truth is the LaTeX from arXiv source tarballs (not OCR). For each display equation we produce
        the spoken text of each pipeline, ask an **independent model family** (`phi4:14b`) to write the speech
        back as LaTeX, and compare both as canonical MathML trees: **exact** (same tree) or **faithful**
        (same symbols in the same order; brackets or fraction grouping may differ).

        | Condition | What is spoken |
        |---|---|
        | a · naive | the equation's glyphs in reading order, as a generic reader gets them from the PDF text layer |
        | b · rules | Speech Rule Engine (ClearSpeak) from the source LaTeX |
        | c · LLM | local LLM narration (`qwen3.5:9b`), unverified |
        | d · LLM + verify | c, back-transcribed by `gemma4:12b` and checked; one repair; else rules (SciReader) |
        | f · 4B | c and d with the smaller `qwen3.5:4b` narrator |
        """
    )
    return


@app.cell
def _(ROOT, json, pd):
    def _load(path):
        p = ROOT / path
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    items = _load("results/results.jsonl")
    units = pd.DataFrame(_load("results/units.jsonl"))
    papers = json.loads((ROOT / "data" / "papers.json").read_text(encoding="utf-8")) if (ROOT / "data" / "papers.json").exists() else []
    COND_LABEL = {
        "a_naive": "a · naive (PDF text)",
        "b_sre": "b · rules (SRE)",
        "c_llm": "c · LLM 9B",
        "d_verified": "d · LLM 9B + verify",
        "f_llm4b": "f · LLM 4B",
        "f_verified4b": "f · LLM 4B + verify",
    }
    rows = []
    for it in items:
        for judge, conds in it.get("judge", {}).items():
            for cond, r in conds.items():
                rows.append({"id": it["id"], "field": it["field"], "judge": judge, "condition": cond,
                             "label": COND_LABEL.get(cond, cond), "result": r["result"],
                             "exact": r["result"] == "match", "faithful": r["result"] in ("match", "relaxed")})
    long = pd.DataFrame(rows)
    return COND_LABEL, items, long, papers, units


@app.cell
def _(items, long, mo, papers):
    _fields = sorted(long["field"].unique()) if len(long) else []
    _judges = sorted(long["judge"].unique()) if len(long) else []
    field_pick = mo.ui.multiselect(options=_fields, value=_fields, label="Fields")
    judge_pick = mo.ui.dropdown(options=_judges, value=("phi4:14b" if "phi4:14b" in _judges else (_judges[0] if _judges else None)), label="Judge")
    mo.vstack([
        mo.md(f"**{len(items)} equations** from **{len(papers)} arXiv papers**."),
        mo.hstack([field_pick, judge_pick], justify="start"),
    ])
    return field_pick, judge_pick


@app.cell
def _(COND_LABEL, field_pick, judge_pick, long, pd):
    sel = long[(long["judge"] == judge_pick.value) & (long["field"].isin(field_pick.value))] if len(long) else long
    summary = (
        sel.groupby("condition")[["exact", "faithful"]].mean().mul(100).round(1)
        .reindex([c for c in COND_LABEL if c in set(sel["condition"])])
        .rename(index=COND_LABEL)
        if len(sel) else pd.DataFrame()
    )
    summary
    return sel, summary


@app.cell
def _(ROOT, judge_pick, plt, summary):
    def faithfulness_figure(summary, judge, path=None):
        fig, ax = plt.subplots(figsize=(8.2, 4.2), dpi=150)
        labels = list(summary.index)
        colors = ["#2f5d8a" if "verify" in l else ("#9a9a9a" if "naive" in l else "#c7ccd3") for l in labels]
        bars = ax.bar(range(len(labels)), summary["faithful"], color=colors, width=0.62, zorder=2)
        ax.bar(range(len(labels)), summary["exact"], color="none", edgecolor="#1d2024", hatch="///", width=0.62,
               linewidth=0, zorder=3, alpha=0.35)
        for b, v in zip(bars, summary["faithful"]):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(range(len(labels)), [l.replace(" · ", "\n") for l in labels], fontsize=8.5)
        ax.set_ylim(0, 105)
        ax.set_ylabel("Equations a listener can write back (%)")
        ax.set_title(f"Spoken math faithfulness (judge: {judge}; hatched = exact match)", fontsize=10.5, loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e6e6", zorder=0)
        fig.tight_layout()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(path.with_suffix(".png"))
            fig.savefig(path.with_suffix(".svg"))
        return fig

    _fig = faithfulness_figure(summary, judge_pick.value, ROOT / "figures" / "faithfulness") if len(summary) else None
    _fig
    return (faithfulness_figure,)


@app.cell
def _(items, judge_pick, mo, pd):
    def gate_stats(items, judge, raw="c_llm", ver="d_verified"):
        """Silent error rate of unverified narration, and the gate's precision / recall at catching errors."""
        rows = []
        for it in items:
            j = it.get("judge", {}).get(judge, {}).get(raw)
            g = it.get(f"{raw}_gate1")
            if not j or not g:
                continue
            error = j["result"] == "mismatch"
            rejected = it.get(f"{ver}_verdict") == "fallback" or g["result"] != "match"
            rows.append({"error": error, "rejected": rejected, "verdict": it.get(f"{ver}_verdict")})
        df = pd.DataFrame(rows)
        if df.empty:
            return None
        tp = int((df.error & df.rejected).sum())
        fp = int((~df.error & df.rejected).sum())
        fn = int((df.error & ~df.rejected).sum())
        return {
            "n": len(df),
            "silent_error_rate": round(100 * df.error.mean(), 1),
            "precision": round(100 * tp / max(1, tp + fp), 1),
            "recall": round(100 * tp / max(1, tp + fn), 1),
            "verdicts": df.verdict.value_counts().to_dict(),
        }

    _g9 = gate_stats(items, judge_pick.value)
    _g4 = gate_stats(items, judge_pick.value, "f_llm4b", "f_verified4b")

    def _fmt(name, g):
        if not g:
            return f"- {name}: no data"
        return (f"- **{name}:** unverified narration silently changes the math in **{g['silent_error_rate']}%** of "
                f"{g['n']} equations; the gate flags errors with precision {g['precision']}% and recall "
                f"{g['recall']}%; verdicts {g['verdicts']}")

    mo.md("### Verification gate\n" + _fmt("qwen3.5:9b", _g9) + "\n" + _fmt("qwen3.5:4b", _g4))
    return (gate_stats,)


@app.cell
def _(ROOT, mo, plt, units):
    if len(units):
        _by = units.groupby("category")[["wrong_raw", "wrong_scireader"]].mean().mul(100).round(0)
        _fig, _ax = plt.subplots(figsize=(7.5, 3.4), dpi=150)
        _x = range(len(_by))
        _ax.bar([i - 0.18 for i in _x], _by["wrong_raw"], width=0.36, color="#9a9a9a", label="generic reader", zorder=2)
        _ax.bar([i + 0.18 for i in _x], _by["wrong_scireader"], width=0.36, color="#2f5d8a", label="SciReader", zorder=2)
        _ax.set_xticks(list(_x), list(_by.index))
        _ax.set_ylabel("Mispronounced (%)")
        _ax.set_title(f"Units and chemistry by sound ({len(units)} snippets, phoneme distance > 0.25)", fontsize=10.5, loc="left")
        _ax.spines[["top", "right"]].set_visible(False)
        _ax.grid(axis="y", color="#e6e6e6", zorder=0)
        _ax.legend(frameon=False)
        _fig.tight_layout()
        (ROOT / "figures").mkdir(exist_ok=True)
        _fig.savefig(ROOT / "figures" / "units.png")
        _fig.savefig(ROOT / "figures" / "units.svg")
        _out = mo.vstack([
            mo.md(f"### Units and chemistry\nA generic reader mispronounces **{units.wrong_raw.mean():.0%}** of snippets; SciReader **{units.wrong_scireader.mean():.0%}**."),
            _fig,
        ])
    else:
        _out = mo.md("No units results yet.")
    _out
    return


@app.cell
def _(items, judge_pick, mo):
    _rows = []
    for _it in items[:400]:
        _j = _it.get("judge", {}).get(judge_pick.value, {})
        _rows.append({"id": _it["id"], "latex": _it["latex"][:90], "naive": _it.get("a_naive", "")[:60],
                      "LLM": _it.get("c_llm", "")[:90], "LLM judge": _j.get("c_llm", {}).get("result"),
                      "gate": _it.get("d_verified_verdict")})
    mo.vstack([mo.md("### Browse items"), mo.ui.table(_rows, page_size=10)])
    return


if __name__ == "__main__":
    app.run()
