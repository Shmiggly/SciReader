"""Chemical element data and formula speech (English).

Spoken style: one-letter element symbols are said as the letter ("H"), two-letter symbols
as hyphen-joined capitals ("C-A") so the voice spells them instead of reading a word
(misaki reduces a lone "A" to the article "uh"; "C-A" is spelled reliably). Counts stay
digits ("H 2 O"), charges become "plus"/"minus" ("C-A 2 plus").
"""

from __future__ import annotations

import re

_ELEMENTS_RAW = """
H hydrogen|He helium|Li lithium|Be beryllium|B boron|C carbon|N nitrogen|O oxygen|F fluorine|
Ne neon|Na sodium|Mg magnesium|Al aluminum|Si silicon|P phosphorus|S sulfur|Cl chlorine|Ar argon|
K potassium|Ca calcium|Sc scandium|Ti titanium|V vanadium|Cr chromium|Mn manganese|Fe iron|
Co cobalt|Ni nickel|Cu copper|Zn zinc|Ga gallium|Ge germanium|As arsenic|Se selenium|Br bromine|
Kr krypton|Rb rubidium|Sr strontium|Y yttrium|Zr zirconium|Nb niobium|Mo molybdenum|
Tc technetium|Ru ruthenium|Rh rhodium|Pd palladium|Ag silver|Cd cadmium|In indium|Sn tin|
Sb antimony|Te tellurium|I iodine|Xe xenon|Cs cesium|Ba barium|La lanthanum|Ce cerium|
Pr praseodymium|Nd neodymium|Pm promethium|Sm samarium|Eu europium|Gd gadolinium|Tb terbium|
Dy dysprosium|Ho holmium|Er erbium|Tm thulium|Yb ytterbium|Lu lutetium|Hf hafnium|Ta tantalum|
W tungsten|Re rhenium|Os osmium|Ir iridium|Pt platinum|Au gold|Hg mercury|Tl thallium|Pb lead|
Bi bismuth|Po polonium|At astatine|Rn radon|Fr francium|Ra radium|Ac actinium|Th thorium|
Pa protactinium|U uranium|Np neptunium|Pu plutonium|Am americium|Cm curium|Bk berkelium|
Cf californium|Es einsteinium|Fm fermium|Md mendelevium|No nobelium|Lr lawrencium|
Rf rutherfordium|Db dubnium|Sg seaborgium|Bh bohrium|Hs hassium|Mt meitnerium|Ds darmstadtium|
Rg roentgenium|Cn copernicium|Nh nihonium|Fl flerovium|Mc moscovium|Lv livermorium|
Ts tennessine|Og oganesson
"""

ELEMENT_NAMES: dict[str, str] = {}
for _item in _ELEMENTS_RAW.replace("\n", "").split("|"):
    _sym, _name = _item.split()
    ELEMENT_NAMES[_sym] = _name
ELEMENTS = frozenset(ELEMENT_NAMES)

# Special isotope names: (mass, symbol) → spoken
ISOTOPE_NAMES: dict[tuple[str, str], str] = {
    ("1", "H"): "hydrogen 1",
    ("2", "H"): "deuterium",
    ("3", "H"): "tritium",
}

# Two-letter symbols allowed in digit-less formulas (NaCl, GaAs, ZnO); keeps "IDs", "ReLu" out.
COMMON_TWO_LETTER = frozenset(
    "Na Cl Ca Mg Al Si Fe Cu Zn Ag Au Ti Li Ga As In Cd Se Te Pb Sn Ni Co Mn Cr Mo Br Ba Sr Zr Pt Pd Bi Ge Hf Nb Ta".split()
)

# Tokens that parse as formulas but are not chemistry.
NOT_FORMULAS = frozenset({"NaN", "HeLa", "InN"})

SUP_TO_ASCII = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
SUB_TO_ASCII = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

_PART_RE = re.compile(r"[A-Z][a-z]?|[0-9₀-₉]+|[()]")
_FULL_RE = re.compile(r"(?:[A-Z][a-z]?|[0-9₀-₉]+|[()])+")


def say_element(sym: str) -> str:
    return sym if len(sym) == 1 else "-".join(sym.upper())


def speak_charge(charge: str) -> str:
    c = charge.translate(SUP_TO_ASCII).replace("−", "-")
    sign = c[-1]
    num = c[:-1]
    word = "plus" if sign == "+" else "minus"
    return f"{num} {word}" if num else word


def speak_formula(body: str, charge: str = "") -> str | None:
    """Spoken form of a formula token, or None if it is not a plausible formula."""
    if body in NOT_FORMULAS or not _FULL_RE.fullmatch(body):
        return None
    parts = _PART_RE.findall(body)
    n_el = 0
    two_letter = False
    uncommon = False
    has_digit = False
    depth = 0
    for p in parts:
        if p == "(":
            depth += 1
        elif p == ")":
            depth -= 1
            if depth < 0:
                return None
        elif p[0].isupper():
            if p not in ELEMENTS:
                return None
            n_el += 1
            two_letter = two_letter or len(p) == 2
            uncommon = uncommon or (len(p) == 2 and p not in COMMON_TWO_LETTER)
        else:
            has_digit = True
    if depth != 0 or n_el == 0:
        return None
    if not (has_digit or charge or (n_el >= 2 and two_letter and not uncommon and len(body) <= 6)):
        return None
    words: list[str] = []
    for p in parts:
        if p in "()":
            continue
        words.append(say_element(p) if p[0].isupper() else p.translate(SUB_TO_ASCII))
    if charge:
        words.append(speak_charge(charge))
    return " ".join(words)


def speak_isotope(mass_sup: str, sym: str) -> str | None:
    if sym not in ELEMENTS:
        return None
    mass = mass_sup.translate(SUP_TO_ASCII)
    special = ISOTOPE_NAMES.get((mass, sym))
    if special:
        return special
    return f"{ELEMENT_NAMES[sym]} {mass}"
