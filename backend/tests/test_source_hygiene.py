from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_control_characters_in_source():
    # A regex replacement once held raw \x01/\x02 bytes instead of backreferences, garbling numbers in captions.
    bad = []
    for pattern in ("backend/scireader/**/*.py", "bench/**/*.py", "frontend/src/**/*.ts*", "tools/math-speech/*.js"):
        for p in ROOT.glob(pattern):
            text = p.read_text(encoding="utf-8")
            if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
                bad.append(str(p.relative_to(ROOT)))
    assert not bad, bad
