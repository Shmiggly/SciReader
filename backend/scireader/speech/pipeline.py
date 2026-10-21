"""Sentence → spoken text: citation markers dropped, science normalization, lexicon."""

from __future__ import annotations

import re
from functools import lru_cache

from ..config import get_settings
from .en import greek as _greek
from .en.normalizer import normalize
from .lexicon import Lexicon
from .normalized import Normalized
from .splitter import split_sentences  # noqa: F401  (re-exported for the builder)

# Inline numeric citations: [12], [3-5], [1, 4, 7], [12,13]
BRACKET_CITE = re.compile(r"\s?\[\s*\d{1,3}(?:\s*[-–,]\s*\d{1,3})*\s*\]")
# Author-year citations: (Smith et al., 2020), (Smith and Jones, 2019; Lee 2020a)
_AUTHOR = r"[A-Z][A-Za-z'’\-]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z'’\-]+|&\s*[A-Z][A-Za-z'’\-]+))?"
AUTHOR_YEAR_CITE = re.compile(
    r"\s?\((?:(?:see\s+|e\.g\.,?\s+)?" + _AUTHOR + r",?\s+(?:19|20)\d{2}[a-z]?(?:,\s*(?:19|20)\d{2}[a-z]?)*(?:;\s*)?)+\)"
)


def find_citations(text: str) -> list[tuple[int, int, list[int]]]:
    """Return (start, end, numbers) for citation markers in text (numbers empty for author-year)."""
    out: list[tuple[int, int, list[int]]] = []
    for m in BRACKET_CITE.finditer(text):
        out.append((m.start(), m.end(), expand_numbers(m.group(0))))
    for m in AUTHOR_YEAR_CITE.finditer(text):
        if not any(s < m.end() and m.start() < e for s, e, _ in out):
            out.append((m.start(), m.end(), []))
    return sorted(out)


def expand_numbers(s: str) -> list[int]:
    nums: list[int] = []
    for part in re.split(r"\s*,\s*", re.sub(r"[\[\]\s]", "", s)):
        m = re.fullmatch(r"(\d+)[-–](\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < b - a < 60:
                nums.extend(range(a, b + 1))
                continue
        if part.isdigit():
            nums.append(int(part))
    return nums


@lru_cache(maxsize=1)
def _lexicon_cached(mtime_user: float, mtime_shipped: float) -> Lexicon:  # noqa: ARG001 - cache key
    s = get_settings()
    return Lexicon.load(s.lexicon_path, s.user_lexicon_path)


def get_lexicon() -> Lexicon:
    s = get_settings()
    mu = s.user_lexicon_path.stat().st_mtime if s.user_lexicon_path.exists() else 0.0
    ms = s.lexicon_path.stat().st_mtime if s.lexicon_path.exists() else 0.0
    return _lexicon_cached(mu, ms)


# Dot accents on variables (time derivatives): "γ̇" -> "gamma dot".
DOT_ACCENT = re.compile(r"([^\W\d_])̇")


def speak(text: str, drop_spans: list[tuple[int, int]] = (), lexicon: Lexicon | None = None) -> Normalized:
    """Normalize one sentence; `drop_spans` (e.g. citation markers) are removed from the spoken text."""
    protected = [(a, b, "") for a, b in sorted(drop_spans)]
    for m in DOT_ACCENT.finditer(text):
        if not any(a < m.end() and m.start() < b for a, b, _ in protected):
            name = _greek.math_char_spoken(m.group(1)) or m.group(1)
            protected.append((m.start(), m.end(), f"{name} dot"))
    protected.sort()
    merged: list[tuple[int, int, str]] = []
    for a, b, s in protected:
        if merged and a < merged[-1][1]:
            pa, pb, _ = merged[-1]
            merged[-1] = (pa, max(pb, b), "")
        else:
            merged.append((a, b, s))
    return normalize(text, lexicon=lexicon if lexicon is not None else get_lexicon(), protected=merged)
