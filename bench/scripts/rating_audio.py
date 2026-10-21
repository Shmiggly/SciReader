"""Prepare the blind naturalness rating set: 10 equations x 3 readings (naive, rules, SciReader), as audio.

Writes bench/rating/items.json (blind ids, shuffled) and bench/rating/audio/*.wav (gitignored).
Usage: uv run --directory backend python ../bench/scripts/rating_audio.py
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from scireader.speech.pipeline import speak  # noqa: E402
from scireader.tts.engine import audio_path, synth_cached  # noqa: E402

OUT = ROOT / "bench" / "rating"
CONDS = {"a_naive": "naive", "b_sre": "rules", "d_verified": "scireader"}


def main() -> int:
    items = [json.loads(l) for l in (ROOT / "bench" / "results" / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = random.Random(2026)
    ai = [it for it in items if it.get("d_verified_verdict") in ("verified", "uncertain")]
    rest = [it for it in items if it not in ai]
    rng.shuffle(ai)
    rng.shuffle(rest)
    picked = (ai + rest)[:10]
    (OUT / "audio").mkdir(parents=True, exist_ok=True)
    clips = []
    for it in picked:
        for cond, name in CONDS.items():
            text = it[cond]
            spoken = speak(text).spoken if cond != "a_naive" else text
            key, _ = synth_cached(spoken, "af_heart")
            clip_id = f"{len(clips):02d}"
            clips.append({"eq_id": it["id"], "latex": it["latex"], "condition": name, "spoken": spoken, "key": key})
    rng.shuffle(clips)
    for n, c in enumerate(clips):
        c["blind_id"] = f"clip{n + 1:02d}"
        shutil.copyfile(audio_path(c["key"]), OUT / "audio" / f"{c['blind_id']}.wav")
    (OUT / "items.json").write_text(json.dumps(clips, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(clips)} clips written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
