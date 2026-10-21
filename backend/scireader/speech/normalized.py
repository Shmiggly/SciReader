"""Shared result type for text normalization: display text, spoken text, and an
exact offset map between the two (used for word-level highlighting)."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field

Segment = tuple[int, int, int, int]  # (d0, d1, s0, s1)


@dataclass(frozen=True)
class Normalized:
    display: str  # input text, unchanged
    spoken: str  # what the TTS should say
    # (d0, d1, s0, s1): sorted, contiguous, covering display[0:len] and spoken[0:len].
    # Identity runs have display[d0:d1] == spoken[s0:s1]; every rewrite is one segment;
    # deleted text has s0 == s1.
    segments: list[Segment] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_d_starts", [seg[0] for seg in self.segments])
        object.__setattr__(self, "_s_starts", [seg[2] for seg in self.segments])

    @classmethod
    def identity(cls, text: str) -> "Normalized":
        return cls(text, text, [(0, len(text), 0, len(text))] if text else [])

    def is_identity_segment(self, seg: Segment) -> bool:
        d0, d1, s0, s1 = seg
        return d1 - d0 == s1 - s0 and self.display[d0:d1] == self.spoken[s0:s1]

    def spoken_to_display(self, s0: int, s1: int) -> tuple[int, int]:
        """Display span covering the spoken span [s0, s1)."""
        return self._map(s0, s1, 2, len(self.spoken), self._s_starts)  # type: ignore[attr-defined]

    def display_to_spoken(self, d0: int, d1: int) -> tuple[int, int]:
        """Spoken span covering the display span [d0, d1)."""
        return self._map(d0, d1, 0, len(self.display), self._d_starts)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ internals
    def _map(self, a0: int, a1: int, src: int, src_len: int, starts: list[int]) -> tuple[int, int]:
        segs = self.segments
        if not segs:
            return (0, 0)
        a0 = max(0, min(a0, src_len))
        a1 = max(a0, min(a1, src_len))
        dst = 2 - src  # 0 <-> 2

        def conv(seg: Segment, x0: int, x1: int) -> tuple[int, int]:
            f0, f1 = seg[src], seg[src + 1]
            t0, t1 = seg[dst], seg[dst + 1]
            if self.is_identity_segment(seg):
                return (t0 + (x0 - f0), t0 + (x1 - f0))
            return (t0, t1)

        i = max(0, bisect_right(starts, a0) - 1)
        if a0 == a1:
            # point query: the first non-empty segment containing a0 (or the end)
            for j in range(i, len(segs)):
                seg = segs[j]
                f0, f1 = seg[src], seg[src + 1]
                if f0 <= a0 < f1:
                    p = conv(seg, a0, a0)[0]
                    return (p, p)
                if f0 > a0:
                    break
            end = segs[-1][dst + 1]
            return (end, end)
        lo: int | None = None
        hi: int | None = None
        # step back over empty-source segments that start at a0
        while i > 0 and segs[i][src] >= a0:
            i -= 1
        for j in range(i, len(segs)):
            seg = segs[j]
            f0, f1 = seg[src], seg[src + 1]
            if f0 >= a1:
                break
            if f1 <= a0 or f0 == f1:
                continue
            t0, t1 = conv(seg, max(a0, f0), min(a1, f1))
            lo = t0 if lo is None else min(lo, t0)
            hi = t1 if hi is None else max(hi, t1)
        if lo is None or hi is None:
            return (0, 0)
        return (lo, hi)
