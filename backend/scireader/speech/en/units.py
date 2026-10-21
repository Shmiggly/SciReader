"""Unit symbols → English words, and compound-unit speech."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    singular: str
    plural: str
    kind: str = ""  # "length" → square/cubic wording for powers
    bare_ok: bool = False  # may be expanded without a preceding number


PREFIX_WORDS = {
    "T": "tera", "G": "giga", "M": "mega", "k": "kilo", "h": "hecto", "c": "centi",
    "m": "milli", "µ": "micro", "μ": "micro", "n": "nano", "p": "pico", "f": "femto",
}

# symbol, singular, plural, kind, allowed prefixes
_BASE = [
    ("m", "meter", "meters", "length", "kcmµμn"),
    ("s", "second", "seconds", "time", "mµμnpf"),
    ("g", "gram", "grams", "", "kmµμn"),
    ("L", "liter", "liters", "", "mµμn"),
    ("l", "liter", "liters", "", "mµμ"),  # lowercase only with a prefix (mL/ml)
    ("mol", "mole", "moles", "", "kmµμn"),
    ("M", "molar", "molar", "", "mµμnp"),
    ("K", "kelvin", "kelvin", "", "m"),
    ("K", "kelvin", "kelvin", "", ""),  # Kelvin sign
    ("Pa", "pascal", "pascals", "", "kMGhm"),
    ("N", "newton", "newtons", "", "kmµμn"),
    ("J", "joule", "joules", "", "kmµμM"),
    ("W", "watt", "watts", "", "kmµμ"),
    ("V", "volt", "volts", "", "kmµμ"),
    ("A", "ampere", "amperes", "", "mµμnp"),
    ("Hz", "hertz", "hertz", "", "kMGT"),
    ("eV", "electron volt", "electron volts", "", "mkMG"),
    ("Da", "dalton", "daltons", "", "k"),
    ("Ω", "ohm", "ohms", "", "kM"),
    ("Ω", "ohm", "ohms", "", "kM"),  # Ohm sign
    ("S", "siemens", "siemens", "", "mµμ"),
    ("Wh", "watt hour", "watt hours", "", "k"),
    ("Ah", "amp hour", "amp hours", "", "m"),
    ("cal", "calorie", "calories", "", "k"),
]

_SPECIAL = {
    "°C": ("degree Celsius", "degrees Celsius"), "° C": ("degree Celsius", "degrees Celsius"),
    "℃": ("degree Celsius", "degrees Celsius"), "°F": ("degree Fahrenheit", "degrees Fahrenheit"),
    "° F": ("degree Fahrenheit", "degrees Fahrenheit"), "℉": ("degree Fahrenheit", "degrees Fahrenheit"),
    "°": ("degree", "degrees"),
    "Å": ("angstrom", "angstroms"), "Å": ("angstrom", "angstroms"),
    "min": ("minute", "minutes"), "h": ("hour", "hours"), "hr": ("hour", "hours"),
    "%": ("percent", "percent"), "‰": ("per mille", "per mille"),
    "wt%": ("weight percent", "weight percent"), "wt.%": ("weight percent", "weight percent"),
    "wt %": ("weight percent", "weight percent"), "wt. %": ("weight percent", "weight percent"),
    "vol%": ("volume percent", "volume percent"), "vol.%": ("volume percent", "volume percent"),
    "vol %": ("volume percent", "volume percent"),
    "mol%": ("mole percent", "mole percent"), "mol %": ("mole percent", "mole percent"),
    "at%": ("atomic percent", "atomic percent"), "at.%": ("atomic percent", "atomic percent"),
    "ppm": ("part per million", "parts per million"), "ppb": ("part per billion", "parts per billion"),
    "rpm": ("revolution per minute", "revolutions per minute"),
    "cP": ("centipoise", "centipoise"), "mPa·s": ("millipascal second", "millipascal seconds"),
    "mPa⋅s": ("millipascal second", "millipascal seconds"), "mPa s": ("millipascal second", "millipascal seconds"),
    "Pa·s": ("pascal second", "pascal seconds"), "Pa⋅s": ("pascal second", "pascal seconds"),
    "Pa s": ("pascal second", "pascal seconds"),
    "dB": ("decibel", "decibels"), "atm": ("atmosphere", "atmospheres"), "Torr": ("torr", "torr"),
    "mbar": ("millibar", "millibar"),
}

# Expanded only after a number even though they are 2+ characters long.
_NOT_BARE = {
    "min", "hr", "mol", "Pa", "Da", "ms", "ns", "ps", "fs", "cal", "Ah", "Wh", "Pa s", "mPa s",
    "° C", "° F", "Ω", "Ω", "K", "mol %", "wt %", "vol %", "pM", "nA", "pA", "fM",
}
_ALWAYS_BARE = {"%", "°", "Å", "Å", "‰", "℃", "℉"}

UNITS: dict[str, Unit] = {}
for _sym, _sg, _pl, _kind, _prefixes in _BASE:
    if _sym != "l":
        UNITS[_sym] = Unit(_sg, _pl, _kind)
    for _p in _prefixes:
        _pw = PREFIX_WORDS[_p]
        UNITS[_p + _sym] = Unit(_pw + _sg, _pw + _pl, _kind)
for _sym, (_sg, _pl) in _SPECIAL.items():
    UNITS[_sym] = Unit(_sg, _pl, "")
for _sym, _u in list(UNITS.items()):
    _bare = _sym in _ALWAYS_BARE or (len(_sym) >= 2 and _sym not in _NOT_BARE)
    UNITS[_sym] = Unit(_u.singular, _u.plural, _u.kind, _bare)

# Single-character symbols must NOT be glued to a number ("112710A", "5A" panels, "1990s"),
# except kelvin after a number >= 100 ("300K"; "10K polymers" means ten thousand).
NEED_SPACE = {s for s in UNITS if len(s) == 1} - {"%", "°", "Å", "Å", "‰", "℃", "℉"}

_SYMS_SORTED = sorted(UNITS, key=len, reverse=True)
_SYM_ALT = "|".join(re.escape(s) for s in _SYMS_SORTED)
SUP_CHARS = "⁰¹²³⁴⁵⁶⁷⁸⁹"

# A unit factor: symbol + optional exponent, not followed by a word character.
FACTOR_RE = re.compile(
    rf"(?P<sym>{_SYM_ALT})"
    r"(?:(?P<caret>\^\{?\(?[−\-–+]?\d{1,2}\)?\}?)"
    r"|(?P<dash>[−\-–]\d)(?![\d])(?!\.\d)"
    r"|(?P<flat>[23])(?![\d])(?!\.\d)"
    rf"|(?P<sup>[⁻⁺]?[{SUP_CHARS}]+))?"
    r"(?![^\W_])"
)
# Same, but where a unit expression may start (not glued to a preceding letter).
START_RE = re.compile(r"(?<![^\W\d_])(?<![\-/·⋅])(?=(?:" + _SYM_ALT + "))")


def parse_exponent(m: re.Match) -> int | None:
    """Integer exponent of a FACTOR_RE match (1 if none); None if invalid."""
    sym = m.group("sym")
    if m.group("caret"):
        raw = re.sub(r"[\^{}()]", "", m.group("caret"))
    elif m.group("dash"):
        raw = "-" + m.group("dash")[1:]
    elif m.group("flat"):
        if UNITS[sym].kind != "length":
            return None
        raw = m.group("flat")
    elif m.group("sup"):
        raw = m.group("sup").translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-"))
    else:
        return 1
    raw = raw.replace("−", "-").replace("–", "-").replace("+", "")
    try:
        n = int(raw)
    except ValueError:
        return None
    return n if n != 0 else None


def power_words(u: Unit, n: int, plural: bool) -> str:
    word = u.plural if plural else u.singular
    if n == 1:
        return word
    if u.kind == "length" and n in (2, 3):
        return ("square " if n == 2 else "cubic ") + word
    if n == 2:
        return word + " squared"
    if n == 3:
        return word + " cubed"
    return f"{word} to the {n}"


def speak_compound(factors: list[tuple[Unit, int]], plural: bool) -> str:
    """factors: (unit, exponent) in order; negative exponents are denominators."""
    num = [(u, n) for u, n in factors if n > 0]
    den = [(u, -n) for u, n in factors if n < 0]
    parts: list[str] = []
    if num:
        for i, (u, n) in enumerate(num):
            parts.append(power_words(u, n, plural and i == len(num) - 1))
    elif den:
        u, n = den.pop(0)
        parts.append("inverse " + power_words(u, 1, plural) if n == 1 else "per " + power_words(u, n, False))
    for u, n in den:
        parts.append("per " + power_words(u, n, False))
    return " ".join(parts)
