"""Client for the Node math-speech helper (MathJax TeX -> MathML, Speech Rule Engine -> speech)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

from ..config import get_settings


class MathSpeech:
    """A long-lived Node process speaking JSON lines; thread-safe, restarts on failure."""

    def __init__(self, helper_dir: Path | None = None):
        self.helper_dir = helper_dir or get_settings().math_speech_dir
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._counter = 0

    def _start(self) -> None:
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Node.js not found on PATH (needed for equation speech)")
        self._proc = subprocess.Popen(
            [node, str(self.helper_dir / "index.js")],
            cwd=str(self.helper_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        ready = self._proc.stdout.readline()
        if '"ready"' not in ready:
            raise RuntimeError(f"math-speech helper failed to start: {ready!r}")

    def _ensure(self) -> None:
        if self._proc is None or self._proc.poll() is not None:
            self._start()

    def run(self, latex: str, display: bool = True, speech: bool = True, style: str = "clearspeak") -> dict:
        with self._lock:
            for attempt in range(2):
                try:
                    self._ensure()
                    self._counter += 1
                    req = {"id": str(self._counter), "latex": latex, "display": display, "speech": speech, "style": style}
                    self._proc.stdin.write(json.dumps(req) + "\n")
                    self._proc.stdin.flush()
                    line = self._proc.stdout.readline()
                    if not line:
                        raise RuntimeError("helper exited")
                    return json.loads(line)
                except Exception as exc:  # noqa: BLE001
                    self.close()
                    if attempt == 1:
                        return {"mathml": None, "speech": None, "error": f"helper failure: {exc}"}
        return {"mathml": None, "speech": None, "error": "unreachable"}

    def speak(self, latex: str, display: bool = True) -> str | None:
        res = self.run(latex, display=display)
        if res.get("error") or not res.get("speech"):
            return None
        return polish_speech(res["speech"])

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:  # noqa: BLE001
                pass
            self._proc = None


_POLISH = [
    (re.compile(r"\bnormal d\b"), "d"),
    (re.compile(r"\bnormal (?=[A-Za-z]\b)"), ""),
    # SRE reads an upright Δ as a triangle; scientists say "delta G", "delta H".
    (re.compile(r"\bnormal triangle\b"), "delta"),
    # ...and an upright Ω as the unit, which it only is after a number ("5 ohms").
    (re.compile(r"(?<![\d.] )\bohms\b"), "capital Omega"),
    # Upright capital Greek ("normal Theta") is just a capital letter to a listener.
    (re.compile(r"\bnormal (?=(?:Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega)\b)"), "capital "),
    (re.compile(r"\s+"), " "),
]


def polish_speech(s: str) -> str:
    """Small, safe wording fixes on top of ClearSpeak output."""
    for pat, rep in _POLISH:
        s = pat.sub(rep, s)
    return s.strip()


_instance: MathSpeech | None = None
_instance_lock = threading.Lock()


def get_math_speech() -> MathSpeech:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = MathSpeech()
        return _instance
