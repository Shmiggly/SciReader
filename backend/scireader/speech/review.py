"""Pronunciation review: terms in a paper that the voice will probably say badly, ranked by frequency, split into
those the user's dataset doesn't have yet and those it has."""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from typing import TYPE_CHECKING

from .lexicon import LexiconEntry

if TYPE_CHECKING:
    from .dataset import Dataset

def kind_of(term: str, detected: str) -> str:
    """The dataset's kind for a detected term: names ("Herschel-Bulkley", "Bingham"), words, formulas, acronyms."""
    if detected == "formula":
        return "formula"
    if re.fullmatch(r"[A-Z][a-z]+(?:-[A-Z][a-z]+)+", term) or (detected == "unknown word" and term[:1].isupper() and term[1:].islower()):
        return "name"
    return "word" if detected == "unknown word" else "acronym"

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
    if re.fullmatch(r"[A-Za-z]{1,3}\d*/(?:\d+|[A-Za-z]{1,2}\d*)", term):
        return None  # math in the text ("H/2", "H/W"), read by the normalizer
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


def entry_view(e: LexiconEntry) -> dict:
    return {"term": e.term, "say_as": e.say_as, "ipa": e.ipa, "kind": e.kind, "case_sensitive": e.case_sensitive,
            "tags": e.tags, "note": e.note, "source": e.source, "checked": e.checked, "added": e.added}


def paper_view(doc: dict, ds: "Dataset", limit: int = 80) -> dict:
    """The pronunciation screen for one paper: terms the voice will probably say badly that the dataset doesn't have
    (suggested), every dataset term the paper uses (known), and terms with two entries in the dataset (duplicates)."""
    lex = ds.lexicon()
    dup_groups = ds.duplicates()
    dup_terms = {ds.entries[g[0]].term.lower() for g in dup_groups}
    counts: Counter[str] = Counter()
    first: dict[str, tuple[str, str, int, str]] = {}
    kinds: dict[str, str] = {}
    known: dict[str, LexiconEntry] = {}
    for b in doc["blocks"]:
        if b.get("skip_reason") or b["type"] in ("equation", "figure", "table"):
            continue
        for s in b["sentences"]:
            spans = []
            for a, z, e in lex.find_entries(s["text"]):
                spans.append((a, z))
                known.setdefault(e.term, e)
                counts[e.term] += 1
                first.setdefault(e.term, (s["id"], s["text"], a, s["text"][a:z]))
            for m in TOKEN.finditer(s["text"]):
                term = m.group(0)
                if any(a <= m.start() < z for a, z in spans):
                    continue  # part of a dataset term ("PA12" in "PA12-based")
                kind = kinds.get(term) or classify(term)
                if not kind:
                    continue
                kinds[term] = kind
                counts[term] += 1
                first.setdefault(term, (s["id"], s["text"], m.start(), term))

    def row(term: str) -> dict:
        sid, text, pos, as_written = first[term]
        return {"term": term, "count": counts[term], "sentence_id": sid, "snippet": _snippet(text, pos, as_written)}

    suggested = [{**row(t), "kind": kind_of(t, kinds[t])}
                 for t, _ in counts.most_common() if t in kinds and t not in known][:limit]
    in_dataset = [{**row(t), "entry": entry_view(e), "duplicate": t.lower() in dup_terms}
                  for t, e in sorted(known.items(), key=lambda kv: -counts[kv[0]])]
    duplicates = [{"term": ds.entries[g[0]].term, "in_paper": ds.entries[g[0]].term in known,
                   "entries": [entry_view(ds.entries[i]) for i in g]} for g in dup_groups]
    duplicates.sort(key=lambda d: not d["in_paper"])
    return {"suggested": suggested, "known": in_dataset, "duplicates": duplicates,
            "dataset": {"entries": len(ds.entries), "mine": sum(e.source == "me" for e in ds.entries),
                        "unchecked": sum(not e.checked for e in ds.entries), "duplicates": len(dup_groups)}}


def _snippet(text: str, pos: int, term: str, words: int = 7) -> str:
    left = text[:pos].split()[-words:]
    right = text[pos + len(term):].split()[:words]
    return " ".join(left + [term] + right).strip()
