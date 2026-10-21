import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="SciSpeech-Bench ratings")


@app.cell
def _():
    import json
    from pathlib import Path

    import marimo as mo

    ROOT = Path(__file__).resolve().parent
    RATING = ROOT / "rating"
    clips = json.loads((RATING / "items.json").read_text(encoding="utf-8")) if (RATING / "items.json").exists() else []
    saved_path = ROOT / "results" / "ratings.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8")) if saved_path.exists() else {}
    return RATING, clips, json, mo, saved, saved_path


@app.cell
def _(clips, mo):
    mo.md(
        f"""
        # Blind ratings: how easy is each reading to follow?

        {len(clips)} short clips, in random order. Each reads one equation aloud; the pipeline that produced
        it is hidden. Listen, look at the equation, and rate **1 (can't follow) to 5 (natural, I could write it
        down)**. It takes about 15 minutes. Press **Save** at the bottom (you can save partway and come back).
        """
    )
    return


@app.cell
def _(RATING, clips, mo, saved):
    sliders = {
        c["blind_id"]: mo.ui.slider(1, 5, value=saved.get(c["blind_id"], {}).get("score", 3), label="Rating", show_value=True)
        for c in clips
    }
    rows = []
    for c in clips:
        rows.append(mo.vstack([
            mo.md(f"**{c['blind_id']}**\n\n$$\n{c['latex']}\n$$"),
            mo.audio(src=str(RATING / "audio" / f"{c['blind_id']}.wav")),
            sliders[c["blind_id"]],
        ]))
    mo.vstack(rows, gap=1.5)
    return (sliders,)


@app.cell
def _(mo):
    save = mo.ui.run_button(label="Save ratings")
    save
    return (save,)


@app.cell
def _(clips, json, mo, save, saved_path, sliders):
    mo.stop(not save.value)
    out = {c["blind_id"]: {"score": sliders[c["blind_id"]].value, "condition": c["condition"], "eq_id": c["eq_id"]} for c in clips}
    saved_path.parent.mkdir(parents=True, exist_ok=True)
    saved_path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    mo.md(f"Saved {len(out)} ratings to `bench/results/ratings.json`. Thank you!")
    return


if __name__ == "__main__":
    app.run()
