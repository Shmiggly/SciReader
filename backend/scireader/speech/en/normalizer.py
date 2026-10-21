"""English science-aware text normalizer.

Design: every rule proposes replacement spans over the ORIGINAL text (protected spans first,
then the lexicon, then rules in priority order; a later span may not overlap an earlier one).
The spoken text and the exact display↔spoken segment map are assembled in one pass.
Digits stay digits (the voice reads them well); only units, symbols, exponents, chemistry,
Greek, abbreviations and similar are rewritten.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from typing import TYPE_CHECKING, Sequence

from ..normalized import Normalized
from . import abbreviations as AB
from . import chem as CH
from . import greek as GR
from . import units as UN

if TYPE_CHECKING:
    from ..lexicon import Lexicon

__all__ = ["normalize"]

SP = "    "
WS = SP + "\t\n\r"
SUPD = "⁰¹²³⁴-⁹"  # superscript digits (char-class body)
_SUP_TR = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ", "0123456789+-=()ni")
_SUB_TR = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜᵢⱼᵣᵤᵥ", "0123456789+-=()aeoxhklmnpstijruv")
MATH = "\U0001d400-\U0001d7ff"
GREEK_CLASS = "Ͱ-Ͽµ∂∇ℏ∆Ω"


# --------------------------------------------------------------------------- span collector
class _Spans:
    __slots__ = ("starts", "items")

    def __init__(self) -> None:
        self.starts: list[int] = []
        self.items: list[tuple[int, int, str]] = []

    def free(self, s: int, e: int) -> bool:
        i = bisect_right(self.starts, s)
        if i and self.items[i - 1][1] > s:
            return False
        if i < len(self.starts) and self.starts[i] < e:
            return False
        return True

    def add(self, s: int, e: int, rep: str) -> bool:
        if s >= e or not self.free(s, e):
            return False
        i = bisect_right(self.starts, s)
        self.starts.insert(i, s)
        self.items.insert(i, (s, e, rep))
        return True

    def add_group(self, group: list[tuple[int, int, str]]) -> bool:
        group = [g for g in group if g[0] < g[1]]
        if not group or not all(self.free(s, e) for s, e, _ in group):
            return False
        for g in group:
            self.add(*g)
        return True


# --------------------------------------------------------------------------- helpers
def _exp_value(raw: str) -> str:
    """'−3' / '⁻³' / '^{-3}' → 'minus 3'; 'n+1' → 'n plus 1'."""
    r = raw.translate(_SUP_TR)
    r = re.sub(r"[\^{}()]", "", r).replace("−", "-").replace("–", "-")
    r = r.lstrip("+")
    if re.fullmatch(r"-?\d+", r):
        neg = r.startswith("-")
        digits = r.lstrip("-").lstrip("0") or "0"
        return ("minus " if neg else "") + digits
    r = r.replace("-", " minus ").replace("+", " plus ")
    return re.sub(r"\s+", " ", r).strip()


def _exponent_words(raw: str) -> str:
    v = _exp_value(raw)
    if v in AB.EXPONENT_WORDS:
        return AB.EXPONENT_WORDS[v]
    return "to the " + v


def _sentence_end_after(text: str, i: int) -> bool:
    j = i
    while j < len(text) and text[j] in WS:
        j += 1
    return j >= len(text) or (j > i and text[j].isupper())


# --------------------------------------------------------------------------- rules
_ITEM = (
    r"(?:\(S?\d+(?:\.\d+)*[a-z]?\)|S?\d+(?:\.\d+)*(?:\([a-zA-Z]\)|[a-zA-Z](?:[–\-][a-zA-Z])?)?)(?![\w])"
)
_JOIN = r"(?:[  ]?[–\-−][  ]?|,[  ]?| and | to | & )"
_REF_RE = re.compile(
    r"(?<![\w.])(?P<label>"
    + "|".join(re.escape(k) for k in sorted(AB.REF_LABELS, key=len, reverse=True))
    + r")(?P<gap>[  ]?)(?P<body>"
    + _ITEM
    + r"(?:"
    + _JOIN
    + _ITEM
    + r")*)"
)


def _speak_ref_body(body: str) -> str:
    s = re.sub(r"[  ]?[–\-−][  ]?", " to ", body)
    s = s.replace("(", " ").replace(")", " ").replace("&", "and")
    s = re.sub(r"(?<=\d)(?=[a-zA-Z])", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace(" ,", ",")


def _rule_refs(text: str, sp: _Spans) -> None:
    for m in _REF_RE.finditer(text):
        label = m.group("label")
        if label[-1].isalpha() and not m.group("gap"):
            continue  # "Figure3" is not a reference
        sp.add_group(
            [
                (m.start("label"), m.end("label"), AB.REF_LABELS[label]),
                (m.start("body"), m.end("body"), _speak_ref_body(m.group("body"))),
            ]
        )


_ABBR_RE = re.compile(
    r"(?<![\w.])(?:"
    + "|".join(re.escape(k) for k in sorted(AB.ABBREVIATIONS, key=len, reverse=True))
    + r")(?![\w])"
)


def _rule_abbreviations(text: str, sp: _Spans) -> None:
    for m in _ABBR_RE.finditer(text):
        spoken, keep = AB.ABBREVIATIONS[m.group()]
        if m.group().endswith(".") and keep and _sentence_end_after(text, m.end()):
            spoken += "."
        sp.add(m.start(), m.end(), spoken)


_EXP_ALT = (
    r"\^\{?\(?[−\-–+]?\d{1,3}\)?\}?"
    rf"|[⁻⁺]?[{SUPD}]+"
)
_SCI_X_RE = re.compile(
    r"(?<![\w.])(?P<mant>\d+(?:\.\d+)?)[   ]*(?P<op>[×✕xX*·⋅])[   ]*10"
    rf"(?P<exp>{_EXP_ALT}|[−\-–]\d{{1,3}}(?![\d.])|[1-9]\d?(?![\d.]))?(?![\d])"
)
_SCI_E_RE = re.compile(r"(?<![\w.])(?P<mant>\d+(?:\.\d+)?)(?P<e>[eE])(?P<exp>[+\-−]?\d{1,3})(?![\w.])")
_POW10_RE = re.compile(rf"(?<![\w.,])10(?P<exp>{_EXP_ALT}|−\d{{1,2}}(?![\d.]))(?![\d])")


def _rule_scientific(text: str, sp: _Spans) -> None:
    for m in _SCI_X_RE.finditer(text):
        exp = m.group("exp")
        if not exp:
            continue
        op = m.group("op")
        if exp[0].isdigit() and op not in "×✕":
            continue  # "2x103" without a real times sign: too ambiguous
        sp.add(m.start("op"), m.end(), "times 10 to the " + _exp_value(exp))
    for m in _SCI_E_RE.finditer(text):
        sp.add(m.start("e"), m.end(), "times 10 to the " + _exp_value(m.group("exp")))
    for m in _POW10_RE.finditer(text):
        sp.add(m.start("exp"), m.end(), "to the " + _exp_value(m.group("exp")))


_ISOTOPE_RE = re.compile(rf"(?<![\w{SUPD}])(?P<mass>[{SUPD}]+)(?P<sym>[A-Z][a-z]?)(?![a-z])")


def _rule_isotopes(text: str, sp: _Spans) -> None:
    for m in _ISOTOPE_RE.finditer(text):
        spoken = CH.speak_isotope(m.group("mass"), m.group("sym"))
        if spoken:
            sp.add(m.start(), m.end(), spoken)


_CHEM_RE = re.compile(
    rf"(?<![\w\-.{SUPD}₀-₉/])"
    r"(?P<body>[A-Z](?:[A-Za-z0-9₀-₉]|\([A-Za-z0-9₀-₉]+\))*)"
    rf"(?P<charge>[{SUPD}]*[⁺⁻]|\d?[+−](?=[\s,.;:)\]]|$))?"
    r"(?![\w])"
)


def _rule_chemistry(text: str, sp: _Spans) -> None:
    for m in _CHEM_RE.finditer(text):
        spoken = CH.speak_formula(m.group("body"), m.group("charge") or "")
        if spoken and spoken != m.group():
            sp.add(m.start(), m.end(), spoken)


_NUM_BEFORE_RE = re.compile(
    rf"(?:(?<![\w.,])(?P<num>\d+(?:[.,]\d+)*)|(?P<sup>[{SUPD}]))(?P<sp>[    ]?)\Z"
)
_LABEL_BEFORE_RE = re.compile(
    r"\b(?:" + "|".join(AB.UNIT_BLOCKING_LABELS) + r")\.?[  ]?S?\d+[  ]?\Z"
)


_SPACED_POWER_RE = re.compile(r" ([23])(?![\w.])")


def _factor(m: re.Match | None) -> tuple[UN.Unit, int, str] | None:
    if m is None:
        return None
    n = UN.parse_exponent(m)
    if n is None:
        return None
    return UN.UNITS[m.group("sym")], n, m.group("sym")


def _parse_unit_expr(text: str, i: int):
    f = _factor(UN.FACTOR_RE.match(text, i))
    if f is None:
        return None
    m0 = UN.FACTOR_RE.match(text, i)
    end = m0.end()  # type: ignore[union-attr]
    factors = [(f[0], f[1])]
    syms = [f[2]]
    explicit = f[1] != 1
    L = len(text)
    while end < L:
        c = text[end]
        if c == "/":
            q = end + 1
            paren = q < L and text[q] == "("
            q += paren
            m2 = UN.FACTOR_RE.match(text, q)
            f2 = _factor(m2)
            if f2 is None:
                break
            den = [(f2[0], -f2[1])]
            dsyms = [f2[2]]
            q = m2.end()  # type: ignore[union-attr]
            fm = _SPACED_POWER_RE.match(text, q)
            if fm and f2[1] == 1 and f2[0].kind == "length":  # "mW/cm 2" (flattened, spaced)
                den[0] = (f2[0], -int(fm.group(1)))
                q = fm.end()
            if paren:
                while q < L and text[q] in " ·⋅":
                    m3 = UN.FACTOR_RE.match(text, q + 1)
                    f3 = _factor(m3)
                    if f3 is None:
                        break
                    den.append((f3[0], -f3[1]))
                    dsyms.append(f3[2])
                    q = m3.end()  # type: ignore[union-attr]
                if q >= L or text[q] != ")":
                    break
                q += 1
            factors += den
            syms += dsyms
            end = q
            explicit = True
            continue
        if c in "·⋅" or c in SP:
            m2 = UN.FACTOR_RE.match(text, end + 1)
            f2 = _factor(m2)
            if f2 is None or (c in SP and f2[1] > 0):
                break
            factors.append((f2[0], f2[1]))
            syms.append(f2[2])
            end = m2.end()  # type: ignore[union-attr]
            explicit = True
            continue
        break
    return end, factors, syms, explicit


def _rule_units(text: str, sp: _Spans) -> None:
    pos = 0
    while True:
        m = UN.START_RE.search(text, pos)
        if m is None:
            return
        i = m.start()
        res = _parse_unit_expr(text, i)
        if res is None:
            pos = i + 1
            continue
        end, factors, syms, explicit = res
        first_sym, first_unit = syms[0], factors[0][0]
        pre = text[max(0, i - 40) : i]
        nb = _NUM_BEFORE_RE.search(pre)
        ok = False
        plural = True
        if nb:
            if not nb.group("sp") and first_sym in UN.NEED_SPACE and not (
                first_sym in ("K", "K") and nb.group("num") and float(nb.group("num").replace(",", "")) >= 100
            ):
                ok = False
            elif len(first_sym) == 1 and not first_unit.bare_ok and _LABEL_BEFORE_RE.search(pre):
                ok = False
            else:
                ok = True
                if nb.group("num") == "1":
                    k = nb.start("num") - 1
                    if k < 0 or pre[k] not in "−-–^":
                        plural = False
        elif i == 0 or text[i - 1] in WS + "([{,;":
            if len(factors) == 1:
                ok = first_unit.bare_ok
            else:  # "kJ/mol", "mW cm−2" yes; "S/N", "g/mol", "J mol−1 K−1" only after a number
                ok = explicit and all(len(s) >= 2 for s in syms)
        if ok and sp.add(i, end, UN.speak_compound(factors, plural)):
            pos = end
        else:
            pos = i + 1


_RANGE_RE = re.compile(
    r"(?<![\w.,/−\-–])(?P<a>\d+(?:\.\d+)?)(?P<s1>[   ]?)(?P<d>[–—\-−])"
    r"(?P<s2>[   ]?)(?P<b>\d+(?:\.\d+)?)(?![\d])(?![.,]\d)(?![−\-–]\d)"
)


def _rule_ranges(text: str, sp: _Spans) -> None:
    for m in _RANGE_RE.finditer(text):
        d = m.group("d")
        a, b = float(m.group("a")), float(m.group("b"))
        s1, s2 = m.group("s1"), m.group("s2")
        if d == "-" and (b <= a or s1 != s2):
            continue
        if d == "−" and (s1 or s2 or m.group("a") == "10" or b <= a):
            continue
        sp.add(m.start("d"), m.end("d"), "to")


_SYMBOL_RE = re.compile("|".join(re.escape(k) for k in sorted(AB.SYMBOLS, key=len, reverse=True)))
_TILDE_RE = re.compile(r"[~∼](?=[  ]?[−\-]?\.?\d)")
_VAR_OR_NUM = rf"(?:[−\-~∼]?[  ]?\.?\d|[A-Za-z](?![A-Za-z])|[{GREEK_CLASS}{MATH}])"
_CMP_RE = re.compile(rf"(?<![<>=\-!])(?P<op><=|>=|<|>)(?![<>=])(?=[  ]?{_VAR_OR_NUM})")
_EQ_RE = re.compile(
    rf"(?<=[\w)\]′{SUPD}{GREEK_CLASS}{MATH}  ])(?<![<>=!])=(?!=)(?=[  ]?[\w(−\-.{GREEK_CLASS}{MATH}])"
)
_PLUS_RE = re.compile(r"(?<=[\w)\]] )\+(?= [\w(])")
_MINUS_SPACED_RE = re.compile(r"(?<=[\w)\]′²³] )−(?= [\w(])")
_NEG_RE = re.compile(rf"(?:(?<=^)|(?<=[\s(\[=,:;/]))(?:[−\-](?=\.?\d)|−(?=[A-Za-z{GREEK_CLASS}{MATH}]))")
_ARROW_RE = re.compile(r"-{1,2}>")
# PDF font artifact: some journal fonts extract "=" as "¼" ("R 0 ¼ 17"); a spaced "¼" is "equals".
_QUARTER_EQ_RE = re.compile(r"(?<=\s)¼(?=\s)")
_TIMES_RE = re.compile(r"×|(?<=\d) x (?=\d)")
_CMP_WORDS = {"<": "less than", ">": "greater than", "<=": "less than or equal to", ">=": "greater than or equal to"}


def _rule_symbols(text: str, sp: _Spans) -> None:
    for m in _TILDE_RE.finditer(text):
        sp.add(m.start(), m.end(), "about")
    for m in _TIMES_RE.finditer(text):
        a = m.start() - 1
        while a >= 0 and text[a] in SP:
            a -= 1
        b = m.end()
        while b < len(text) and text[b] in SP:
            b += 1
        dims = a >= 0 and b < len(text) and text[a].isdigit() and text[b].isdigit()
        if m.group() == "×" or dims:
            sp.add(m.start(), m.end(), "by" if dims else "times")
    for m in _CMP_RE.finditer(text):
        sp.add(m.start(), m.end(), _CMP_WORDS[m.group("op")])
    for m in _EQ_RE.finditer(text):
        sp.add(m.start(), m.end(), "equals")
    for m in _PLUS_RE.finditer(text):
        sp.add(m.start(), m.end(), "plus")
    for rx in (_MINUS_SPACED_RE, _NEG_RE):
        for m in rx.finditer(text):
            sp.add(m.start(), m.end(), "minus")
    for m in _ARROW_RE.finditer(text):
        sp.add(m.start(), m.end(), "to")
    for m in _QUARTER_EQ_RE.finditer(text):
        sp.add(m.start(), m.end(), "equals")
    for m in _SYMBOL_RE.finditer(text):
        sp.add(m.start(), m.end(), AB.SYMBOLS[m.group()])


_SUP_RUN_RE = re.compile(rf"[{SUPD}⁺⁻ⁿⁱ⁽⁾⁼]+(?:,[{SUPD}⁻]+)*")
_CITE_RUN_RE = re.compile(rf"[{SUPD}]+(?:[,⁻–][{SUPD}]+)*")
_SUB_RUN_RE = re.compile(r"[₀-₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜᵢⱼᵣᵤᵥ]+")
_UNDERSCORE_RE = re.compile(
    rf"(?<=[A-Za-z0-9){GREEK_CLASS}{MATH}])_(?:\{{(?P<b>[A-Za-z0-9,\- ]{{1,12}})\}}|(?P<s>[A-Za-z0-9]+))"
)
_CARET_RE = re.compile(
    rf"(?<=[A-Za-z0-9){GREEK_CLASS}{MATH}])\^(?:\{{(?P<b>[^{{}}]{{1,12}})\}}|\((?P<p>[^()]{{1,12}})\)|(?P<s>[−\-+]?[A-Za-z0-9]+))"
)


def _spell_small(s: str) -> str:
    parts = re.findall(r"\d+|[A-Za-z]+|[+\-=]", s)
    out = []
    for p in parts:
        if p == "+":
            out.append("plus")
        elif p == "-":
            out.append("minus")
        elif p == "=":
            out.append("equals")
        elif p.isalpha() and len(p) <= 2:
            out.extend(p)
        else:
            out.append(p)
    return " ".join(out)


def _rule_scripts(text: str, sp: _Spans) -> None:
    for m in _SUP_RUN_RE.finditer(text):
        run = m.group()
        i = m.start()
        ch = text[i - 1] if i else ""
        cite_like = bool(_CITE_RUN_RE.fullmatch(run))
        rep: str
        if ch.isdigit():
            j = i - 1
            while j >= 0 and (text[j].isdigit() or text[j] == "."):
                j -= 1
            base = text[j + 1 : i]
            rep = ("to the " + _exp_value(run)) if base == "10" else _exponent_words(run)
        elif ch.isalpha():
            j = i - 1
            while j >= 0 and text[j].isalpha():
                j -= 1
            word = text[j + 1 : i]
            mathy = any(GR.is_math_alnum(c) or c in GR.GREEK_NAMES for c in word)
            rep = "" if (len(word) >= 3 and not mathy and cite_like) else _exponent_words(run)
        elif ch in ".,;:" and cite_like:
            rep = ""
        elif ch in ")]":
            rep = "" if (cite_like and (len(run) > 1 or "," in run)) else _exponent_words(run)
        else:
            rep = _spell_small(run.translate(_SUP_TR))
        sp.add(m.start(), m.end(), rep)
    for m in _SUB_RUN_RE.finditer(text):
        sp.add(m.start(), m.end(), _spell_small(m.group().translate(_SUB_TR)))
    for m in _UNDERSCORE_RE.finditer(text):
        sp.add(m.start(), m.end(), _spell_small(m.group("b") or m.group("s")))
    for m in _CARET_RE.finditer(text):
        sp.add(m.start(), m.end(), _exponent_words(m.group("b") or m.group("p") or m.group("s")))


_GREEK_RE = re.compile(rf"[{GREEK_CLASS}{MATH}]")


def _rule_greek(text: str, sp: _Spans) -> None:
    for m in _GREEK_RE.finditer(text):
        ch = m.group()
        if GR.is_math_alnum(ch):
            rep = GR.math_char_spoken(ch)
        elif ch in "µμ" and m.end() < len(text) and text[m.end()].isupper():
            rep = "micro"  # µCT, µSLA
        else:
            rep = GR.GREEK_NAMES.get(ch)
            if rep is None:
                continue
        sp.add(m.start(), m.end(), rep)


_RULES = (
    _rule_refs,
    _rule_abbreviations,
    _rule_scientific,
    _rule_isotopes,
    _rule_chemistry,
    _rule_units,
    _rule_ranges,
    _rule_symbols,
    _rule_scripts,
    _rule_greek,
)


# --------------------------------------------------------------------------- assembly
def _tidy_deletions(text: str, items: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Absorb whitespace around deleted spans so the spoken text has no double spaces
    and no space before punctuation. Added as separate deletion segments."""
    extra: list[tuple[int, int, str]] = []
    n = len(text)
    for k, (s, e, rep) in enumerate(items):
        if rep:
            continue
        prev_end = items[k - 1][1] if k else 0
        next_start = items[k + 1][0] if k + 1 < len(items) else n
        w = s
        while w > prev_end and text[w - 1] in WS:
            w -= 1
        after = text[e] if e < n else ""
        if w < s and (after == "" or after in WS or after in ".,;:!?)]}"):
            extra.append((w, s, ""))
        elif w == 0:
            x = e
            while x < next_start and text[x] in WS:
                x += 1
            if x > e:
                extra.append((e, x, ""))
    if not extra:
        return items
    return sorted(items + extra)


def _assemble(text: str, items: list[tuple[int, int, str]]) -> Normalized:
    out: list[str] = []
    segs: list[tuple[int, int, int, int]] = []
    pos = 0
    spos = 0
    last = ""
    n = len(text)
    for s, e, rep in items:
        if pos < s:
            chunk = text[pos:s]
            out.append(chunk)
            segs.append((pos, s, spos, spos + len(chunk)))
            spos += len(chunk)
            last = chunk[-1]
        if rep:
            if last.isalnum() and rep[0].isalnum():
                rep = " " + rep
            if e < n and text[e].isalnum() and rep[-1].isalnum():
                rep = rep + " "
            last = rep[-1]
        out.append(rep)
        segs.append((s, e, spos, spos + len(rep)))
        spos += len(rep)
        pos = e
    if pos < n:
        out.append(text[pos:])
        segs.append((pos, n, spos, spos + n - pos))
    return Normalized(text, "".join(out), segs)


def normalize(
    text: str,
    *,
    lexicon: "Lexicon | None" = None,
    protected: Sequence[tuple[int, int, str]] = (),
) -> Normalized:
    """Normalize English scientific prose for TTS. See module docstring."""
    sp = _Spans()
    for s, e, rep in sorted(protected):
        if not (0 <= s <= e <= len(text)):
            raise ValueError(f"protected span out of range: {(s, e)}")
        if s == e:
            continue
        if not sp.add(s, e, rep):
            raise ValueError(f"protected spans overlap at {(s, e)}")
    if lexicon is not None:
        for s, e, rep in lexicon.find(text):
            sp.add(s, e, rep)
    for rule in _RULES:
        rule(text, sp)
    items = _tidy_deletions(text, sp.items)
    return _assemble(text, items)
