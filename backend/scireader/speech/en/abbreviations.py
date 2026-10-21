"""Abbreviations, reference labels and symbols (English)."""

from __future__ import annotations

# Reference labels: expanded when followed by a number ("Fig. 3b" → "Figure 3 b").
REF_LABELS: dict[str, str] = {
    "Fig.": "Figure", "Figs.": "Figures", "fig.": "figure", "figs.": "figures",
    "Figure": "Figure", "Figures": "Figures", "figure": "figure", "figures": "figures",
    "Eq.": "Equation", "Eqs.": "Equations", "Eqn.": "Equation", "Eqns.": "Equations",
    "eq.": "equation", "eqs.": "equations", "eqn.": "equation",
    "Equation": "Equation", "Equations": "Equations", "equation": "equation",
    "Table": "Table", "Tables": "Tables", "Tab.": "Table", "table": "table",
    "Ref.": "Reference", "Refs.": "References", "ref.": "reference", "refs.": "references",
    "Sec.": "Section", "Secs.": "Sections", "Section": "Section", "Sections": "Sections",
    "Scheme": "Scheme", "Schemes": "Schemes", "Chap.": "Chapter", "Ch.": "Chapter",
    "No.": "number", "Nos.": "numbers", "pp.": "pages", "p.": "page",
    "Suppl. Fig.": "Supplementary Figure",
}

# Free-standing abbreviations (case-aware: each listed casing is matched exactly).
# value: (spoken, keep_final_period) — keep the period when the abbreviation ends a sentence.
ABBREVIATIONS: dict[str, tuple[str, bool]] = {
    "e.g.": ("for example", False), "E.g.": ("For example", False), "e. g.": ("for example", False),
    "i.e.": ("that is", False), "I.e.": ("That is", False), "i. e.": ("that is", False),
    "et al.": ("et al", True),
    "ca.": ("about", False),
    "vs.": ("versus", False), "vs": ("versus", False), "Vs.": ("Versus", False),
    "cf.": ("compare", False), "Cf.": ("Compare", False),
    "approx.": ("approximately", False), "Approx.": ("Approximately", False),
    "resp.": ("respectively", True),
    "viz.": ("namely", False),
    "a.u.": ("arbitrary units", True), "arb. units": ("arbitrary units", True),
    "w.r.t.": ("with respect to", False),
    "Suppl.": ("Supplementary", False),
    "Fig.": ("Figure", False), "Figs.": ("Figures", False),
    "Eq.": ("Equation", False), "Eqs.": ("Equations", False), "Eqn.": ("Equation", False),
    "Ref.": ("Reference", False), "Refs.": ("References", False),
    "Sec.": ("Section", False), "Tab.": ("Table", False),
}

# Context-free symbols.
SYMBOLS: dict[str, str] = {
    "±": "plus or minus", "∓": "minus or plus",
    "≈": "approximately", "≃": "approximately", "≅": "approximately equal to",
    "∝": "proportional to",
    "≤": "less than or equal to", "⩽": "less than or equal to",
    "≥": "greater than or equal to", "⩾": "greater than or equal to",
    "≠": "not equal to", "≡": "equivalent to", "≪": "much less than", "≫": "much greater than",
    "→": "to", "⟶": "to", "⇒": "implies", "⇔": "if and only if", "⇌": "is in equilibrium with",
    "∞": "infinity", "√": "square root of", "∑": "sum", "∏": "product", "∫": "integral",
    "∈": "in", "∉": "not in", "⊥": "perpendicular to", "∥": "parallel to", "∠": "angle",
    "‰": "per mille", "′": "prime", "″": "double prime",
    "½": "one half", "⅓": "one third", "¼": "one quarter", "¾": "three quarters",
    "·": "dot", "⋅": "dot", "∙": "dot",
}

# Exponents spoken as words.
EXPONENT_WORDS = {"2": "squared", "3": "cubed"}

# Label words before a number that make a following single-letter token a panel/ID, not a unit.
UNIT_BLOCKING_LABELS = (
    "Fig", "Figs", "Figure", "Figures", "Table", "Tables", "Tab", "Eq", "Eqs", "Eqn",
    "Equation", "Equations", "Section", "Sec", "Ref", "Refs", "Scheme", "Chapter", "Step",
    "step", "Sample", "sample", "No", "Entry", "entry", "Run", "run", "Model", "model",
    "Case", "case", "Type", "type", "Panel", "panel", "Appendix", "Example", "Exp",
)
