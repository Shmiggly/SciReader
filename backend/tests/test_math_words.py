"""Natural wording of spoken equations, reading modes, figure narration and citation markers (listening check)."""

import shutil

import pytest

from scireader.api.tts import LONG_WORDS, equation_spoken
from scireader.llm.figures import spoken_for
from scireader.parsing.builder import _leading_citation, _superscript_citations
from scireader.speech.math_words import natural, prepare_for_rules

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for MathJax")


@pytest.mark.parametrize(
    "spoken, latex, expected",
    [
        # Rule-based readings (Speech Rule Engine, ClearSpeak).
        ("y equals f of x comma x is a member of R to the d-th power", "", "y equals f of x where x is a member of R to the d power"),
        ("f sub high of x equals rho f sub low of x plus f sub err of x", "", "f high of x equals rho f low of x, plus f error of x"),
        ("capital Theta vertical bar sub Z equals 0 equals 0", "", "capital Theta evaluated at Z equals 0 equals 0"),
        ("the cosine of open paren theta minus psi close paren", "", "the cosine of parenthesis theta, minus psi close parenthesis"),
        (r"d of A over d of t equals negative open paren b I of A minus REG close paren", r"\frac { d [ A ] } { d t } = - ( b I [ A ] - \mathrm{REG} )",
         "the derivative of the concentration of A with respect to time equals negative parenthesis b I times the concentration of A, minus REG close parenthesis"),
        # Verified AI narrations.
        ("f sub high of open parenthesis x close parenthesis equals rho times f sub low of open parenthesis x close parenthesis.", "",
         "f high of x equals rho times f low of x."),
        ("m sub i comma j superscript open parenthesis k close parenthesis equals phi of x sub i comma e sub i close parenthesis.", "",
         "m i comma j superscript k equals phi of x i comma e i."),
        ("d square bracket A close square bracket all over d t equals negative open parenthesis b I square bracket A close square bracket minus REG close parenthesis.",
         r"\frac { d [ A ] } { d t } = - ( b I [ A ] - \mathrm{REG} )",
         "the derivative of the concentration of A with respect to time equals negative parenthesis b I times the concentration of A, minus REG close parenthesis."),
        ("y colon one to n, where the subscript on y runs from one to n", "", "y colon one to n, where the subscript on y runs from one to n"),
        # A pause before a term, not inside an index or exponent, nor in plus or minus.
        ("x sub n plus 1 equals e to the minus x plus y plus or minus z", "", "x n plus 1 equals e to the minus x, plus y, plus or minus z"),
        # Brackets are concentrations only in a kinetics equation (a time derivative of a bracketed quantity).
        ("E open bracket X close bracket", r"E [ X ]", "E open bracket X close bracket"),
    ],
)
def test_natural_wording(spoken, latex, expected):
    assert natural(spoken, latex) == expected


@pytest.mark.parametrize(
    "latex, expected",
    [
        (r"r' = { \frac { U _ { c } } { V _ { j m } } } \cos \psi", r"r' = { \frac { U _ { c } } { V _ { j m } } }  \cdot \cos \psi"),
        (r"\frac{a}{b} x", r"\frac{a}{b}  \cdot x"),
        (r"\frac{a}{b} + x", r"\frac{a}{b} + x"),  # a sum needs no "times"
        (r"\left( \frac{a}{b} \right) x", r"\left( \frac{a}{b} \right) x"),
    ],
)
def test_times_after_a_fraction(latex, expected):
    assert prepare_for_rules(latex) == expected


def _eq(n_words: int) -> tuple[dict, dict]:
    block = {"eq_number": "7", "eq_label": "Momentum", "latex": "x", "speech_rules": " ".join(["x"] * n_words)}
    ai = {"verdict": "fallback", "source": {"status": "agree"}, "latex": "x", "speech_rules": block["speech_rules"],
          "brief": "The momentum balance along the jet."}
    return block, ai


def test_auto_mode_summarizes_long_equations():
    block, ai = _eq(LONG_WORDS + 10)
    assert equation_spoken(block, "auto", ai) == "Equation 7, Momentum, a long equation. AI summary: The momentum balance along the jet."
    assert equation_spoken(block, "full_all", ai).startswith("Equation 7, Momentum: x x x")
    short, ai2 = _eq(5)
    assert equation_spoken(short, "auto", ai2) == "Equation 7, Momentum: x x x x x."


def test_precise_mode_keeps_the_checked_wording():
    block = {"eq_number": "29", "eq_label": None, "latex": "f", "speech_rules": "f sub high of x"}
    ai = {"verdict": "verified", "speech_ai": "f sub high of open parenthesis x close parenthesis.", "source": {"status": "agree"},
          "latex": "f", "speech_rules": "f sub high of x"}
    assert equation_spoken(block, "precise", ai) == "Equation 29: f sub high of open parenthesis x close parenthesis."
    assert equation_spoken(block, "auto", ai) == "Equation 29: f high of x."


def test_figure_narration_goes_straight_to_the_description():
    entry = {"label": "Figure 3", "panels": ["b"], "caption_part": "b Profiling results.", "description": "A bar chart of task times."}
    assert spoken_for(entry) == "Figure 3, panel b. AI description: A bar chart of task times."
    assert spoken_for({**entry, "description": None}) == "Figure 3, panel b. b Profiling results."


@pytest.mark.parametrize(
    "stext, before, expected",
    [
        ("19 Another promising approach is to represent the material as a graph.", "…for natural language processing.", (0, 3, [19])),
        ("1-3 The result is a constant flux of materials data.", "…to the community.", (0, 4, [1, 2, 3])),
        ("300 K is the reference temperature.", "Next sentence.", None),  # a unit, not a citation
        ("19 Another approach.", "", None),  # first sentence of a block: could be a list label
        ("19 another approach.", "First.", None),
    ],
)
def test_leading_citation(stext, before, expected):
    assert _leading_citation(stext, before) == expected


def test_superscript_range_with_a_baseline_dash():
    text = "inverse predictors, 12-16 which locate"
    sup = [False] * len(text)
    for k in (20, 21, 23, 24):  # "12" and "16" are raised, the dash is not
        sup[k] = True
    (a, b, nums), = _superscript_citations(text, sup)
    assert text[a:b].strip() == "12-16" and nums == [12, 13, 14, 15, 16]


def test_final_r_respelled_for_the_voice_only():
    from scireader.tts.engine import for_voice

    assert for_voice("Equation 8, Charge: sigma equals R.") == "Equation 8, Charge: sigma equals ar."
    assert for_voice("R sub j squared equals 1.") == "R sub j squared equals 1."
