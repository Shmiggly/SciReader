"""Structural comparison of two LaTeX equations through canonicalized MathML (MathJax via the Node helper).

SymPy's LaTeX parser fails on most physics notation and plain string similarity is misleading, so we
compare MathML trees after normalizing away differences that don't change the math as heard:
mrow nesting, styles/attributes, ε/ϵ-style variants, \\mathrm{A} vs A, \\dfrac vs \\frac, implicit vs
explicit multiplication, bracket shapes, spacing, msubsup vs nested scripts, parentheses around a
one-symbol function argument (\\cos(\\psi) vs \\cos\\psi), and where an evaluation bar's subscript attaches
(\\left.\\Theta\\right|_{Z=0} vs \\Theta|_{Z=0}).
"""

from __future__ import annotations

import difflib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from ..speech.math_speech import get_math_speech

TRANSPARENT = {"math", "mrow", "mstyle", "mpadded", "semantics", "mtd", "mtr", "mtable", "mlabeledtr", "menclose", "mphantom"}
SCRIPTS = {"msub", "msup", "msubsup", "mfrac", "msqrt", "mroot", "munder", "mover", "munderover"}
DROP_MO = {"\u2061", "\u2062", "\u2063", "\u2064", "⋅", "·", "×", "*", "∗", "", ","}
OPEN = {"(", "[", "{", "⟨", "⌊", "⌈", "\u2016"}
CLOSE = {")", "]", "}", "⟩", "⌋", "⌉"}
VARIANTS = {"ϵ": "ε", "ϕ": "φ", "ϑ": "θ", "ϰ": "κ", "ϱ": "ρ", "ϖ": "π", "−": "-", "∣": "|", "′": "'", "″": "''", "ℓ": "l"}
UNDER_OVER = {"munder": "msub", "mover": "msup", "munderover": "msubsup"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _norm_text(t: str | None) -> str:
    t = (t or "").strip()
    return "".join(VARIANTS.get(ch, ch) for ch in t)


FN = "fn"  # MathJax's function application (U+2061) after \sin, \log, \operatorname...; folded away by _fold


def canon_tokens(el: ET.Element, relaxed: bool = False) -> list[str]:
    return _fold(_tokens(el, relaxed))


def _fold(tokens: list[str]) -> list[str]:
    """Drop the parentheses around a one-token argument of a function name (\\cos(\\psi) is \\cos\\psi), then the
    function-application markers. f(x) keeps its parentheses: MathJax marks only operator names."""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == FN:
            if tokens[i + 1:i + 2] == ["("] and tokens[i + 3:i + 4] == [")"] and tokens[i + 2][:2] in ("i:", "n:"):
                out.append(tokens[i + 2])
                i += 4
                continue
            i += 1
            continue
        out.append(t)
        i += 1
    return out


def _tokens(el: ET.Element, relaxed: bool = False) -> list[str]:
    tag = _local(el.tag)
    if tag in ("mspace", "none", "mprescripts", "annotation", "annotation-xml"):
        return []
    if tag in TRANSPARENT:
        out: list[str] = []
        for ch in el:
            out.extend(_tokens(ch, relaxed))
        return out
    if tag == "mi":
        return [f"o:{c}" if c == "'" else f"i:{c}" for c in _norm_text(el.text) if not c.isspace()]
    if tag == "mn":
        return [f"n:{c}" for c in _norm_text(el.text).replace(",", "") if not c.isspace()]
    if tag == "mtext":
        # 	ext{MAE}, \mathrm{MAE} and MAE are the same thing when heard: compare letter by letter.
        return [f"i:{c}" for c in _norm_text(el.text) if c.isalnum()]
    if tag in ("mo", "ms"):
        t = _norm_text(el.text)
        if t == "\u2061":
            return [FN]
        if t in DROP_MO:
            return []
        if t in OPEN:
            return [] if relaxed else ["("]
        if t in CLOSE:
            return [] if relaxed else [")"]
        return [f"o:{t}"]
    if tag in UNDER_OVER:
        tag = UNDER_OVER[tag]
    kids = list(el)
    if tag in ("msub", "msubsup") and len(kids) == (2 if tag == "msub" else 3):
        parts = [_tokens(k, relaxed) for k in kids]
        base, lead = parts[0], []
        if len(base) > 1 and base[-1] == "o:|":
            # An evaluation bar carries the subscript, wherever MathJax attaches it: \left.X\right|_{a} is X|_{a}.
            lead, base = base[:-1], ["o:|"]
        if tag == "msub":
            return [*lead, "msub(", *base, ",", *parts[1], ")"]
        return [*lead, "msup(", "msub(", *base, ",", *parts[1], ")", ",", *parts[2], ")"]
    if tag == "mfrac" and relaxed and len(kids) == 2:
        num, den = (_tokens(k, relaxed) for k in kids)
        return [*num, "o:/", *den]
    if tag in SCRIPTS:
        out = [f"{tag}("]
        for i, k in enumerate(kids):
            if i:
                out.append(",")
            out.extend(_tokens(k, relaxed))
        out.append(")")
        return out
    out = []
    for ch in el:
        out.extend(_tokens(ch, relaxed))
    return out


def _parse(mathml: str) -> ET.Element:
    return ET.fromstring(mathml)


def to_mathml(latex: str) -> tuple[str | None, str | None]:
    res = get_math_speech().run(latex, display=True, speech=False)
    return res.get("mathml"), res.get("error")


@dataclass
class Comparison:
    status: str  # "match" | "relaxed" | "mismatch" | "error"
    ratio: float
    diff: str
    error: str | None = None


def compare(source_latex: str, back_latex: str) -> Comparison:
    src_ml, err = to_mathml(source_latex)
    if not src_ml:
        return Comparison("error", 0.0, "", f"source LaTeX does not parse: {err}")
    back_ml, err2 = to_mathml(_strip_delims(back_latex))
    if not back_ml:
        return Comparison("mismatch", 0.0, "the transcription is not valid LaTeX", err2)
    try:
        a_el, b_el = _parse(src_ml), _parse(back_ml)
    except ET.ParseError as exc:
        return Comparison("error", 0.0, "", f"MathML parse error: {exc}")
    a, b = canon_tokens(a_el), canon_tokens(b_el)
    ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    if a == b:
        return Comparison("match", 1.0, "")
    ar, br = canon_tokens(a_el, True), canon_tokens(b_el, True)
    if ar == br:
        return Comparison("relaxed", ratio, "same symbols and order; grouping or brackets differ")
    return Comparison("mismatch", ratio, describe_diff(a, b))


def describe_diff(a: list[str], b: list[str], limit: int = 3) -> str:
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    parts = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        src = _pretty(a[i1:i2])
        got = _pretty(b[j1:j2])
        if op == "delete":
            parts.append(f"'{src}' was lost")
        elif op == "insert":
            parts.append(f"'{got}' was added")
        else:
            parts.append(f"'{src}' came back as '{got}'")
        if len(parts) >= limit:
            break
    return "; ".join(parts)


def _pretty(tokens: list[str]) -> str:
    out = []
    for t in tokens:
        if ":" in t and not t.endswith("("):
            out.append(t.split(":", 1)[1])
        else:
            out.append({"msup(": "^(", "msub(": "_(", "mfrac(": "frac(", "msqrt(": "sqrt("}.get(t, t))
    return " ".join(out)[:80]


def _strip_delims(s: str) -> str:
    r"""Pull the LaTeX out of a model answer: code fences, $$...$$, \[...\], \(...\), $...$, labels."""
    s = s.strip()
    m = re.search(r"```(?:latex|tex|math)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    for pat in (r"\$\$(.*?)\$\$", r"\\\[(.*?)\\\]", r"\\\((.*?)\\\)", r"(?<!\\)\$(.*?)(?<!\\)\$"):
        m = re.search(pat, s, re.S)
        if m and m.group(1).strip():
            s = m.group(1).strip()
            break
    s = re.sub(r"^(?:latex|tex|answer|equation)\s*:\s*", "", s, flags=re.I)
    s = re.sub(r"\\begin\{(equation|align|gather|displaymath)\*?\}|\\end\{(equation|align|gather|displaymath)\*?\}", "", s)
    s = re.sub(r"\\(label|tag)\{[^}]*\}", "", s)
    s = s.replace("\\newline", "\n")
    # Drop decoration lines ("-", "---", "|") and, when a model repeats or continues the equation on
    # several lines without alignment markers, keep the first full line.
    lines = [ln.strip() for ln in s.splitlines()]
    lines = [ln for ln in lines if ln and not re.fullmatch(r"[-–—*_.,;:|=\s]+", ln)]
    if len(lines) > 1 and not any("&" in ln or ln.endswith("\\\\") for ln in lines):
        s = lines[0]
    else:
        s = " ".join(lines)
    return s.strip().rstrip(".,;:-– ").strip()
