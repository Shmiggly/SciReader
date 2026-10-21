"""Canonical MathML comparison used by the verification gate and SciSpeech-Bench (needs Node + tools/math-speech)."""

import shutil

import pytest

from scireader.llm.verify import _strip_delims, compare

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for MathJax")


@pytest.mark.parametrize(
    "src, back",
    [
        (r"E = mc^2", r"E=m c^{2}"),
        (r"\varepsilon_0 \cdot x", r"\epsilon_0 x"),
        (r"\dfrac{a}{b}", r"\frac{a}{b}"),
        (r"\mathrm{MAE} = x", r"\text{MAE} = x"),
        (r"MAE = x", r"\text{MAE} = x"),
        (r"\boldsymbol{C} = \boldsymbol{F}^T \boldsymbol{F}", r"C = F^T F"),
        (r"x_i^2", r"x^2_i"),
        (r"K(x, x')", r"K(x, x^{\prime})"),
        (r"\left( a + b \right) c", r"(a+b)c"),
        (r"a \times b", r"a b"),
        (r"f(x) = \sin x", r"f(x)=\sin x"),
        (r"r' = \cos(\theta - \psi) + \cos(\psi)", r"r' = \cos(\theta - \psi) + \cos\psi"),
        (r"\exp(x) + \log(2)", r"\exp x + \log 2"),
        (r"\left.\Theta\right|_{Z=0} = 0", r"\Theta|_{Z=0} = 0"),
        (r"\left. \frac{dx}{dt} \right|_{t=0}", r"\frac{dx}{dt}\Big|_{t=0}"),
        (r"\left|x\right|_2", r"|x|_2"),
        (r"J = \det F", r"J = \operatorname{det} F"),
        (r"\sigma(x) = \max(x)", r"\sigma(x) = \mathrm{max}(x)"),
        (r"\frac{\left(T - T_g\right)^{2}}{4}", r"\frac{(T - T_g)^2}{4}"),
        (r"\left(x_i\right)_{j} + f\left(x\right)^2", r"(x_i)_j + f(x)^2"),
        (r"\sigma^2_n\left(x_{n+1}\right) = 1", r"\sigma^2_n(x_{n+1}) = 1"),
        (r"\left(x\right)_i^2", r"(x)_i^2"),
    ],
)
def test_equivalent_forms_match(src, back):
    assert compare(src, back).status == "match"


@pytest.mark.parametrize(
    "src, back",
    [
        (r"\frac{1}{e^{h\nu/k_B T}-1}", r"\frac{1}{e^{h\nu/k_B}T-1}"),  # the Planck trap: T leaves the exponent
        (r"\Theta|_{Z=0} = 0", r"\Theta_{Z} = 0"),  # evaluation bar dropped
        (r"\sigma^2", r"\sigma_2"),
        (r"a - b", r"a + b"),
        (r"\Theta = 1", r"\theta = 1"),  # case matters
        (r"f(x) = 1", r"f x = 1"),  # a plain function keeps its parentheses: f x is f times x
        (r"\cos(\theta - \psi)", r"\cos\theta - \psi"),  # a longer argument keeps them too
        (r"\Theta|_{Z=0} = 0", r"\Theta_{Z=0} = 0"),  # evaluation bar dropped, subscript kept
        (r"\left(a + b\right)^2", r"a + b^2"),  # the exponent covers the group, not just b
        (r"(a + b)^2 c", r"(a + b c)^2"),
    ],
)
def test_changed_math_is_caught(src, back):
    assert compare(src, back).status != "match"


def test_grouping_only_difference_is_relaxed():
    assert compare(r"\frac{a}{b+c}", r"a/(b+c)").status == "relaxed"


def test_invalid_transcription_is_a_mismatch():
    c = compare(r"x = 1", r"\frac{x}{")
    assert c.status == "mismatch"


@pytest.mark.parametrize(
    "raw, expected",
    [
        (r"\( T_g = \frac{a}{b} \)", r"T_g = \frac{a}{b}"),
        ("```latex\nE=mc^2\n```", "E=mc^2"),
        ("Here it is: $$x^2$$", "x^2"),
        (r"\[ x = 1 \]", "x = 1"),
        ("C = F^T F\n-", "C = F^T F"),
        ("P = a\n\\newline\nP = a", "P = a"),
        ("y = 2.", "y = 2"),
    ],
)
def test_latex_extraction_from_model_answers(raw, expected):
    assert _strip_delims(raw) == expected
