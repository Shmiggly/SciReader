"""Minimal stand-ins for the normalizer/splitter/lexicon (used only if those modules fail to import)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Normalized:
    display: str
    spoken: str
    segments: list[tuple[int, int, int, int]]

    def spoken_to_display(self, s0: int, s1: int) -> tuple[int, int]:
        d0 = d1 = None
        for a, b, c, d in self.segments:
            if d0 is None and s0 < d:
                d0 = a + max(0, min(s0 - c, b - a)) if d - c == b - a else a
            if s1 <= d or (a, b, c, d) == self.segments[-1]:
                d1 = a + max(0, min(s1 - c, b - a)) if d - c == b - a else b
                break
        return (d0 or 0, d1 if d1 is not None else len(self.display))


class Lexicon:
    @classmethod
    def load(cls, *_a, **_k) -> "Lexicon":
        return cls()


def normalize(text: str, *, lexicon=None, protected=()) -> Normalized:
    segs, out, pos, sp = [], [], 0, 0
    for a, b, rep in sorted(protected):
        if a > pos:
            segs.append((pos, a, sp, sp + a - pos)); out.append(text[pos:a]); sp += a - pos
        segs.append((a, b, sp, sp + len(rep))); out.append(rep); sp += len(rep); pos = b
    if pos < len(text):
        segs.append((pos, len(text), sp, sp + len(text) - pos)); out.append(text[pos:])
    return Normalized(text, "".join(out), segs)


_SPLIT = re.compile(r"(?<![A-Z])(?<!Fig)(?<!Eq)(?<!al)(?<!e\.g)(?<!i\.e)(?<!Ref)[.!?](?=\s+[A-Z(\[])")


def split_sentences(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SPLIT.finditer(text):
        spans.append((start, m.end())); start = m.end()
        while start < len(text) and text[start].isspace():
            start += 1
    if start < len(text):
        spans.append((start, len(text.rstrip())))
    return [(a, b) for a, b in spans if b > a]
