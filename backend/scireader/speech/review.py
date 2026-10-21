"""Pronunciation review: terms in a paper that the voice will probably say badly, ranked by frequency."""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from .lexicon import Lexicon

TOKEN = re.compile(r"(?<![\w-])[A-Za-z][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*(?![\w])")
ELEMENTS = set(
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr "
    "Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir "
    "Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu".split()
)
FORMULA = re.compile(r"^(?:[A-Z][a-z]?\d*)+$")
COMMON_CAPS = {"I", "A", "AI", "OK", "US", "UK", "EU", "PhD", "DOI", "URL", "PDF", "ID", "IDs", "http", "https", "www"}


@lru_cache(maxsize=1)
def _known_words() -> tuple[dict, dict]:
    from misaki import en

    g2p = en.G2P(trf=False, british=False, fallback=None)
    return g2p.lexicon.golds, g2p.lexicon.silvers


_SUFFIXES = [("ies", "y"), ("ied", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"), ("d", ""), ("ing", ""),
             ("ing", "e"), ("ly", ""), ("ally", "al"), ("er", ""), ("ers", "")]


def _known(word: str) -> bool:
    golds, silvers = _known_words()
    w = word.lower()
    forms = {word, w, word.capitalize()}
    for suf, rep in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            forms.add(w[: -len(suf)] + rep)
    return any(f in golds or f in silvers for f in forms)


def classify(term: str) -> str | None:
    if term in COMMON_CAPS or re.fullmatch(r"S\d+[a-z]?(?:-[a-z])?", term):
        return None  # supplementary labels ("Fig. S2") are not formulas
    letters = [c for c in term if c.isalpha()]
    uppers = sum(c.isupper() for c in letters)
    if FORMULA.match(term) and any(ch.isdigit() for ch in term):
        parts = re.findall(r"[A-Z][a-z]?", term)
        if parts and all(p in ELEMENTS for p in parts):
            return "formula"
    if uppers >= 2 or (uppers >= 1 and any(c.isdigit() for c in term)):
        return "abbreviation"
    if len(term) <= 3 and term[0].isupper() and uppers == 1 and len(letters) >= 2 and not _known(term):
        return "abbreviation"  # Tg, Tm, Mw
    if len(letters) >= 5 and not _known(term) and not _known(term.rstrip("s")) and "-" not in term and "/" not in term:
        return "unknown word"
    return None


def candidates(doc: dict, lexicon: Lexicon, limit: int = 80) -> list[dict]:
    counts: Counter[str] = Counter()
    first: dict[str, tuple[str, str, int]] = {}
    kinds: dict[str, str] = {}
    for b in doc["blocks"]:
        if b.get("skip_reason") or b["type"] in ("equation", "figure", "table"):
            continue
        for s in b["sentences"]:
            for m in TOKEN.finditer(s["text"]):
                term = m.group(0)
                kind = kinds.get(term) or classify(term)
                if not kind:
                    continue
                kinds[term] = kind
                counts[term] += 1
                first.setdefault(term, (s["id"], s["text"], m.start()))
    out = []
    for term, n in counts.most_common(limit):
        sid, text, pos = first[term]
        entry = lexicon.get(term)
        out.append({
            "term": term, "count": n, "kind": kinds[term], "sentence_id": sid,
            "snippet": _snippet(text, pos, term),
            "in_lexicon": entry is not None,
            "say_as": entry.say_as if entry else None,
            "source": entry.source if entry else None,
        })
    return out


def _snippet(text: str, pos: int, term: str, words: int = 7) -> str:
    left = text[:pos].split()[-words:]
    right = text[pos + len(term):].split()[:words]
    return " ".join(left + [term] + right).strip()
