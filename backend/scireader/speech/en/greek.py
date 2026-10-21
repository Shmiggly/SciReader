"""Greek letters and math-alphanumeric characters (English names)."""

from __future__ import annotations

import unicodedata

GREEK_NAMES: dict[str, str] = {
    # lowercase
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "ϵ": "epsilon",
    "ζ": "zeta", "η": "eta", "θ": "theta", "ϑ": "theta", "ι": "iota", "κ": "kappa",
    "ϰ": "kappa", "λ": "lambda", "μ": "mu", "µ": "mu", "ν": "nu", "ξ": "xi",
    "ο": "omicron", "π": "pi", "ϖ": "pi", "ρ": "rho", "ϱ": "rho", "σ": "sigma",
    "ς": "sigma", "τ": "tau", "υ": "upsilon", "φ": "phi", "ϕ": "phi", "χ": "chi",
    "ψ": "psi", "ω": "omega",
    # uppercase
    "Α": "alpha", "Β": "beta", "Γ": "gamma", "Δ": "delta", "∆": "delta", "Ε": "epsilon",
    "Ζ": "zeta", "Η": "eta", "Θ": "theta", "Ι": "iota", "Κ": "kappa", "Λ": "lambda",
    "Μ": "mu", "Ν": "nu", "Ξ": "xi", "Ο": "omicron", "Π": "pi", "Ρ": "rho", "Σ": "sigma",
    "Τ": "tau", "Υ": "upsilon", "Φ": "phi", "Χ": "chi", "Ψ": "psi", "Ω": "omega",
    "Ω": "omega",
    # operators that read like letters
    "∇": "nabla", "∂": "partial", "ℏ": "h bar",
}


def is_math_alnum(ch: str) -> bool:
    return "\U0001d400" <= ch <= "\U0001d7ff"


_MATH_CACHE: dict[str, str] = {}


def math_char_spoken(ch: str) -> str:
    """Spoken form of a Mathematical Alphanumeric Symbol (𝑥 → x, 𝛼 → alpha, 𝟑 → 3)."""
    out = _MATH_CACHE.get(ch)
    if out is None:
        plain = unicodedata.normalize("NFKC", ch)
        out = GREEK_NAMES.get(plain, plain)
        _MATH_CACHE[ch] = out
    return out


def plain_char(ch: str) -> str:
    """Plain letter for a math-alphanumeric char (𝑥 → x, 𝛼 → α); other chars unchanged."""
    return unicodedata.normalize("NFKC", ch) if is_math_alnum(ch) else ch
