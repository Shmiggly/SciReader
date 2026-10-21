"""Rule-based sentence splitter for scientific prose (character spans, trimmed)."""

from __future__ import annotations

import re

# Never a sentence end (case-sensitive token before the period).
_NO_SPLIT = frozenset(
    """Fig Figs fig figs Eq Eqs eq eqs Eqn Eqns eqn Ref Refs ref refs Sec Secs sec Tab Tabs
    No Nos vs Vs cf Cf ca approx Approx resp Dr Prof St Inc Ltd Mr Ms Mrs Jr Vol vol pp
    viz Suppl Supp Ch Chap Eds Ed Corp Co Dept Univ Assoc""".split()
)
_DOTTED_ABBR_RE = re.compile(r"(?:[A-Za-z]\.)+[A-Za-z]")  # e.g / i.e / U.S / a.u
_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_CANDIDATE_RE = re.compile(
    r"(?P<punct>[.?!…]+)"
    r"(?P<close>[\"'”’)\]]*)"
    rf"(?P<cite>[{_SUP}]+(?:[,–\-−⁻][{_SUP}]+)*|\d+(?:[,–\-]\d+)*)?"
    r"(?P<space>\s+)"
)
_PARA_RE = re.compile(r"\n[ \t]*\n")
_OPENERS = "([{\"'“‘"


def _token_before(text: str, i: int) -> str:
    j = i
    while j > 0 and not text[j - 1].isspace() and text[j - 1] not in "([{\"'“‘":
        j -= 1
    return text[j:i]


def _is_boundary(text: str, m: re.Match) -> bool:
    nxt_i = m.end()
    if nxt_i >= len(text):
        return False  # trailing punctuation: the final span ends here anyway
    nxt = text[nxt_i]
    if not (nxt.isupper() or nxt.isdigit() or nxt in _OPENERS):
        return False
    punct = m.group("punct")
    p0 = m.start("punct")
    cite = m.group("cite")
    if cite and cite[0].isdigit():
        # "printing.12 Next": only after a word, never after a number ("3.14")
        if p0 == 0 or not (text[p0 - 1].isalpha() or text[p0 - 1] in ")]"):
            return False
    if punct != ".":
        return True  # ?, !, ellipsis followed by a capital
    tok = _token_before(text, p0)
    core = tok.rstrip(".")
    if core in _NO_SPLIT or _DOTTED_ABBR_RE.fullmatch(core):
        return False
    if core == "al" and tok == "al" and text[max(0, p0 - 6) : p0].endswith("et al"):
        return nxt.isupper()  # "et al. (2020)", "et al. 2019" stay together
    if len(core) == 1 and core.isupper():
        # initials ("J. Smith", "A. B. Smith") — but "at 300 K. The" is a unit after a number
        k = p0 - 1
        while k >= 0 and text[k] in "   ":
            k -= 1
        k -= 1  # skip the letter itself
        while k >= 0 and text[k] in "   ":
            k -= 1
        return k >= 0 and text[k].isdigit()
    if core.isdigit() and len(core) <= 2 and not m.group("close"):
        # numbered item at the start of the text / a line / after ':' or ';'
        k = p0 - len(core) - 1
        while k >= 0 and text[k] in " \t":
            k -= 1
        if k < 0 or text[k] in "\n:;":
            return False
    return True


def split_sentences(text: str) -> list[tuple[int, int]]:
    """Character spans (start, end) of sentences in ``text``, trimmed, in order."""
    cuts: list[int] = []
    for m in _CANDIDATE_RE.finditer(text):
        if _is_boundary(text, m):
            cuts.append(m.start("space"))
    for m in _PARA_RE.finditer(text):
        cuts.append(m.start())
    cuts = sorted(set(cuts))
    spans: list[tuple[int, int]] = []
    start = 0
    for c in cuts + [len(text)]:
        s, e = start, c
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            spans.append((s, e))
        start = c
    return spans
