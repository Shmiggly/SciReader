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
    return ROOT, json, mo, pd, plt


@app.cell
def _(mo):
    mo.md(
        """
        # SciSpeech-Bench: how faithfully do read-aloud pipelines speak math?

        Ground truth is the LaTeX from arXiv source tarballs (not OCR). For each display equation we take the
        spoken text of each pipeline, ask an **independent model family** (`phi4:14b`) to write the speech back
        as LaTeX, and compare both as canonical MathML trees: **exact** (same tree) or **faithful** (same symbols
        in the same order; brackets or fraction grouping may differ).

        | Condition | What is spoken |
        |---|---|
        | a · naive | the equation's glyphs in reading order, as a generic reader gets them from the PDF text layer |
        | b · rules | Speech Rule Engine (ClearSpeak) from the source LaTeX |
        | c · LLM | local LLM narration (`qwen3.5:9b`), unverified |
        | d · LLM + verify | c, back-transcribed by `gemma4:12b` and checked; one repair; else rules (**SciReader**) |
        | f · 4B | c and d with the smaller `qwen3.5:4b` narrator |

        The judge is the ceiling of this metric: it cannot write back every long equation even from a perfect
        reading. So we also report the **judge-capable subset**: equations whose rule-based reading (b, which is
        faithful by construction) the judge reconstructs.
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
    _pp = ROOT / "data" / "papers.json"
    papers = json.loads(_pp.read_text(encoding="utf-8")) if _pp.exists() else []
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
def _(COND_LABEL, field_pick, judge_pick, long, mo, pd):
    sel = long[(long["judge"] == judge_pick.value) & (long["field"].isin(field_pick.value))] if len(long) else long

    def _summ(df):
        if not len(df):
            return pd.DataFrame()
        return (df.groupby("condition")[["exact", "faithful"]].mean().mul(100).round(1)
                .reindex([c for c in COND_LABEL if c in set(df["condition"])]).rename(index=COND_LABEL))

    capable_ids = set(sel[(sel["condition"] == "b_sre") & sel["faithful"]]["id"]) if len(sel) else set()
    summary = _summ(sel)
    summary_capable = _summ(sel[sel["id"].isin(capable_ids)]) if capable_ids else pd.DataFrame()
    mo.vstack([
        mo.md(f"**All {sel['id'].nunique() if len(sel) else 0} equations** (limited by the judge's own transcription ability), % of equations"),
        summary,
        mo.md(f"**Judge-capable subset: {len(capable_ids)} equations**, % of equations"),
        summary_capable,
    ])
    return capable_ids, summary, summary_capable


@app.cell
def _(ROOT, judge_pick, plt, summary, summary_capable):
    def faithfulness_figure(panels, judge, path=None):
        fig, axes = plt.subplots(1, len(panels), figsize=(11, 4.3), dpi=150, sharey=True)
        axes = axes if len(panels) > 1 else [axes]
        for ax, (title, summ) in zip(axes, panels):
            labels = list(summ.index)
            colors = ["#2f5d8a" if "verify" in l else ("#9a9a9a" if "naive" in l else "#c7ccd3") for l in labels]
            bars = ax.bar(range(len(labels)), summ["faithful"], color=colors, width=0.62, zorder=2)
            ax.bar(range(len(labels)), summ["exact"], color="none", edgecolor="#1d2024", hatch="///", width=0.62,
                   linewidth=0, zorder=3, alpha=0.3)
            for b, v in zip(bars, summ["faithful"]):
                ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%", ha="center", va="bottom", fontsize=8.5)
            ax.set_xticks(range(len(labels)), [l.split(" · ")[0] + "\n" + l.split(" · ")[1] for l in labels], fontsize=7.5)
            ax.set_ylim(0, 108)
            ax.set_title(title, fontsize=10, loc="left")
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="y", color="#e6e6e6", zorder=0)
        axes[0].set_ylabel("Equations written back faithfully (%)")
        fig.suptitle(f"Can a listener write the equation back? Independent judge: {judge}; hatched = exact match",
                     fontsize=10.5, x=0.01, ha="left")
        fig.tight_layout()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(path.with_suffix(".png"))
            fig.savefig(path.with_suffix(".svg"))
        return fig

    _panels = []
    if len(summary_capable):
        _panels.append((f"Judge-capable subset", summary_capable))
    if len(summary):
        _panels.append(("All equations (judge-limited)", summary))
    _fig = faithfulness_figure(_panels, judge_pick.value, ROOT / "figures" / "faithfulness") if _panels else None
    _fig
    return


@app.cell
def _(capable_ids, items, judge_pick, mo, pd):
    def gate_stats(raw):
        rows = []
        for it in items:
            if capable_ids and it["id"] not in capable_ids:
                continue
            j = it.get("judge", {}).get(judge_pick.value, {}).get(raw)
            g = it.get(f"{raw}_gate1")
            if not j or not g:
                continue
            rows.append({"error": j["result"] not in ("match", "relaxed"), "rejected": g["result"] != "match"})
        df = pd.DataFrame(rows)
        if df.empty:
            return None
        tp = int((df.error & df.rejected).sum())
        fp = int((~df.error & df.rejected).sum())
        fn = int((df.error & ~df.rejected).sum())
        return {"n": len(df), "silent": round(100 * df.error.mean()), "precision": round(100 * tp / max(1, tp + fp)),
                "recall": round(100 * tp / max(1, tp + fn)), "passed": fn, "errors": tp + fn}

    def verdicts(key):
        out = {}
        for it in items:
            out[it.get(key)] = out.get(it.get(key), 0) + 1
        return out

    def _fmt(name, g, key):
        if not g:
            return f"- {name}: no data"
        return (f"- **{name}:** unverified narration silently changes the math in **{g['silent']}%** of {g['n']} "
                f"equations; the gate catches **{g['recall']}%** of those errors (precision {g['precision']}%; "
                f"{g['passed']} of {g['errors']} errors slipped through). Verdicts over all equations: {verdicts(key)}")

    mo.md("### Verification gate (judge-capable subset)\n" + _fmt("qwen3.5:9b", gate_stats("c_llm"), "d_verified_verdict")
          + "\n" + _fmt("qwen3.5:4b", gate_stats("f_llm4b"), "f_verified4b_verdict"))
    return


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
    for _it in items:
        _j = _it.get("judge", {}).get(judge_pick.value, {})
        _rows.append({"id": _it["id"], "field": _it["field"], "latex": _it["latex"][:90], "LLM said": _it.get("c_llm", "")[:90],
                      "judge on LLM": _j.get("c_llm", {}).get("result"), "gate": _it.get("d_verified_verdict")})
    mo.vstack([mo.md("### Browse items"), mo.ui.table(_rows, page_size=10)])
    return


@app.cell
def _(ROOT, json, mo, pd):
    _rp = ROOT / "results" / "ratings.json"
    if _rp.exists():
        _r = pd.DataFrame(json.loads(_rp.read_text(encoding="utf-8")).values())
        _t = _r.groupby("condition")["score"].agg(["count", "mean", "median"]).round(2)
        _t = _t.reindex([c for c in ("naive", "rules", "scireader") if c in _t.index])
        _out = mo.vstack([
            mo.md("### Naturalness: blind ratings by the author (1 = can't follow, 5 = natural, could write it down)"),
            _t,
            mo.md("Ten equations, each heard three ways in random order with the pipeline hidden (`rate.py`)."),
        ])
    else:
        _out = mo.md("No ratings yet: run `marimo run bench/rate.py`.")
    _out
    return


if __name__ == "__main__":
    app.run()
