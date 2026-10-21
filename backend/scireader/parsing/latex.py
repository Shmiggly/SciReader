"""Clean up formula LaTeX produced by OCR (Docling CodeFormula) before it is spoken or verified."""

from __future__ import annotations

import re

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
        return r"\mathrm{" + word + "}"

    return _LETTER_RUN.sub(repl, latex)


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


def latex_has_content(latex: str | None) -> bool:
    if not latex:
        return False
    if "\\begin{matrix}" in latex and "=" not in latex:
        return False
    stripped = re.sub(r"\\(?:begin|end)\{\w+\}|\\[a-zA-Z]+|[{}\s&\\]", "", latex)
    return len(stripped) >= 3 and bool(re.search(r"[A-Za-z=+<>]", stripped))
