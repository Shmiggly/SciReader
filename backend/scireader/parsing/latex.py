"""Clean up formula LaTeX produced by OCR (Docling CodeFormula) before it is spoken or verified."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Trailing equation numbers: "\quad ( 1 )", "& & ( 6 )", "\tag{3}", "\qquad (12a)", also with \, spacing.
_SPACING = r"(?:\\quad|\\qquad|\\,|\\;|\\ |\\!|~|&|\\hfill|\s)*"
_EQNUM_END = re.compile(_SPACING + r"\(\s*((?:\d\s*){1,3}[a-z]?)\s*\)" + _SPACING + r"[.,]?\s*$")
_EQNUM_TAG = re.compile(r"\\tag\*?\s*\{\s*([^{}]+?)\s*\}")
# Runs of 3+ single letters separated by spaces, e.g. "J e t" -> "\mathrm{Jet}" (OCR tokenization of words).
_LETTER_RUN = re.compile(r"(?<![\\A-Za-z])((?:[A-Za-z] ){2,}[A-Za-z])(?![A-Za-z])")


# A number set off by alignment/spacing, possibly followed by OCR debris: "= 1 & & ( 6 ) & & \stackrel{...}"
_EQNUM_MID = re.compile(r"(?:&\s*|\\q?quad\s*)\(\s*((?:\d\s*){1,3}[a-z]?)\s*\)")


def extract_equation_number(latex: str) -> tuple[str, str | None]:
    """Return (latex without its number, number or None)."""
    m = _EQNUM_TAG.search(latex)
    if m:
        return (latex[: m.start()] + latex[m.end():]).strip(), m.group(1).replace(" ", "")
    m = _EQNUM_END.search(latex)
    if m:
        return latex[: m.start()].rstrip(), m.group(1).replace(" ", "")
    m = _EQNUM_MID.search(latex)
    if m:
        return latex[: m.start()].rstrip(), m.group(1).replace(" ", "")
    return latex, None


def _join_letter_runs(latex: str) -> str:
    def repl(m: re.Match) -> str:
        word = m.group(1).replace(" ", "")
        # "R e V _ { j }" is Re·V_j (the subscript belongs to the last letter), not a word; "l o w _ { 1 }" is.
        if re.match(r"\s*[_^]", m.string[m.end():]) and any(c.isupper() for c in word[1:]):
            return m.group(0)
        return r"\mathrm{" + word + "}"

    return _LETTER_RUN.sub(repl, latex)


# A text label typeset before a display equation ("Charge:", "Jet Radius", "Electric field:"), read from the PDF
# text layer. The OCR LaTeX carries a garbled copy of it ("C h \arg e \cdot", "\mathrm{Momtun} \colon").
_PDF_LABEL = re.compile(r"^\s*([A-Z][a-z]{2,}(?: [A-Za-z][a-z]+){0,3}):?\s")
_LABEL_TOKEN = re.compile(
    r"\s*(?:\\(?:mathrm|text|operatorname)\s*\{[^{}]*\}"
    r"|\\(?:arg|det|deg|dim|exp|ker|lg|ln|log|max|min|sin|cos|tan|sec|hom)\b"
    r"|[A-Za-z]{2,}:"
    r"|[A-Za-z]\s*_\s*\{\s*\}"  # a letter with an empty subscript: OCR debris
    r"|[A-Za-z](?![A-Za-z])(?!\s*[_^]))"  # a single letter, unless it carries a sub/superscript (then it's math)
)
_LABEL_END = re.compile(r"\s*(?:\\colon|:|\\cdot)")


def equation_intro(number: str | None, label: str | None) -> str:
    """How an equation is announced: "Equation 8, Charge", "Equation 8", "Electric field" or "Equation"."""
    if number:
        return f"Equation {number}, {label}" if label else f"Equation {number}"
    return label or "Equation"


def split_label(latex: str, pdf_text: str) -> tuple[str | None, str]:
    """(label, latex without the label) when the PDF shows a word label before the equation, else (None, latex)."""
    m = _PDF_LABEL.match(pdf_text or "")
    if not m:
        return None, latex
    label = m.group(1)
    pos = 0
    while (t := _LABEL_TOKEN.match(latex, pos)) and t.end() > pos:
        pos = t.end()
    if (e := _LABEL_END.match(latex, pos)) is not None:
        pos = e.end()
    prefix, rest = latex[:pos], latex[pos:].strip()
    letters = re.sub(r"[^A-Za-z]", "", re.sub(r"\\(?:mathrm|text|operatorname|colon|cdot)", "", prefix)).lower()
    want = re.sub(r"[^a-z]", "", label.lower())
    if len(letters) < 3 or SequenceMatcher(None, letters, want).ratio() < 0.6 or not latex_has_content(rest):
        return None, latex
    return label, rest


def clean_latex(latex: str) -> str:
    """Make OCR LaTeX friendlier for MathJax/SRE without changing its math."""
    s = latex.strip()
    s = s.strip("$").strip()
    # Text labels: "\text {Right Jet Angle}" is fine; tokenized words are joined.
    s = _join_letter_runs(s)
    # Alignment ampersands and line breaks are layout only.
    s = re.sub(r"(?<!\\)&", " ", s)
    s = re.sub(r"\\\\(\[[^\]]*\])?", " ", s)
    s = re.sub(r"\\(?:quad|qquad)\b", " ", s)
    s = re.sub(r"\\[ ,;:!](?![a-zA-Z])", " ", s)  # explicit spacing commands
    s = re.sub(r"\s+", " ", s).strip()
    # Trailing punctuation from the sentence the equation ends.
    s = re.sub(r"\s*[,.;]\s*$", "", s)
    return s


def is_fragment(number: str | None, label: str | None, latex: str | None, bbox, others) -> bool:
    """A piece the parser split off a neighbouring equation: mostly inside a larger equation's box (GNN paper p. 11:
    a duplicate "x_0^(1)" that took its superscript for an equation number), or with no number, no label and nothing
    readable, thin or partly inside a larger equation (flagship p. 13: a lone "2 2" matrix beside two radicals)."""
    x0, y0, x1, y1 = bbox
    area = max((x1 - x0) * (y1 - y0), 1e-6)
    empty = not (number or label or latex_has_content(latex))
    for o in others:
        ix, iy = min(x1, o[2]) - max(x0, o[0]), min(y1, o[3]) - max(y0, o[1])
        if ix > 0 and iy > 0 and (o[2] - o[0]) * (o[3] - o[1]) > area:
            inside = ix * iy / area
            if inside >= 0.6 or (empty and inside >= 0.3):
                return True
    return empty and (x1 - x0 < 20 or y1 - y0 < 6)


def latex_has_content(latex: str | None) -> bool:
    if not latex:
        return False
    if "\\begin{matrix}" in latex and "=" not in latex:
        return False
    s = re.sub(r"\\(?:begin|end)\{\w+\}|\\(?:left|right|quad|qquad|mathrm|text|operatorname|displaystyle)\b", "", latex)
    s = re.sub(r"\\[a-zA-Z]+", "x", s)  # a command such as \sigma is one symbol
    stripped = re.sub(r"[{}\s&\\]", "", s)
    return len(stripped) >= 3 and bool(re.search(r"[A-Za-z=+<>]", stripped))
