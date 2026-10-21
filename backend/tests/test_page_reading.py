"""Second reading of equations from the page: cleanup of the vision model's LaTeX, the PDF text layer as tiebreaker."""

import shutil

import pytest

from scireader.llm import page_reading as pr

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for MathJax")


@pytest.mark.parametrize(
    "raw, number, text, expected",
    [
        # The model kept the label, letter by letter, inside the braces it wrapped each line in.
        (r" { \mathrm { M o m e n t u m : } \; R e V _ { j } = B o }", "7", "Momentum: ReV j \xbc Bo \xf07\xde",
         r"{ R e V _ { j } = B o }"),
        (r"\textbf{Continuity}\!: R_j^2 V_j = 1", "6", "Continuity: R 2 j V j \xbc 1 \xf06\xde", r"R_j^2 V_j = 1"),
        (r"\sigma = R \tag 8", "8", "Charge: σ \xbc R \xf08\xde", r"\sigma = R"),
        (r"y = f(x) \qquad \text{(21)}", "21", "", r"y = f(x)"),
        ("```latex\n$$E = mc^2 \\quad (3)$$\n```", "3", "", r"E = mc^2"),
        (r"\begin{array}{l} a = b \\ c = d \end{array} \quad (4)", "4", "", r"a = b c = d"),
        (r"\begin{aligned} a &= b \\ &= c \end{aligned}", None, "", r"a = b = c"),
        # A trailing (2) is only an equation number when the parser found that number or spacing sets it off.
        (r"g = f(2)", None, "", r"g = f(2)"),
        (r"g = f(2)", "2", "", r"g = f"),
        (r"x = 1 \quad (5)", None, "", r"x = 1"),
        (r"\mu _ { \mathrm { h i g h } } = 1", None, "", r"\mu _ { \mathrm{high} } = 1"),
    ],
)
def test_clean_transcription(raw, number, text, expected):
    assert pr.clean_transcription(raw, number, text) == expected


def test_springer_text_layer_symbols():
    # Flagship eq 27: μ_n(x_{n+1}) = k_{n+1} K^{-1} y_{1:n}, with Springer glyphs for = ( ) + and the minus.
    text = "μ n x n\xfe1 \x00 \x01 \xbc k n\xfe1 K \x001 y 1:n \xf027\xde"
    bag = pr.text_symbols(text, None, "27", springer=True)
    assert bag["-"] == 1 and bag["+"] == 2 and bag["="] == 1 and bag[":"] == 1
    assert bag["2"] == 0 and bag["7"] == 0  # the equation number is not part of the equation


def test_text_layer_pieces_that_are_not_symbols():
    # A radical's bar ("ffiffi..."), the Springer radical sign (a lone r), TeX's tall-delimiter pieces, the label.
    text = "Electric field: E t \xbc 1 \xfe ffiffiffiffiffiffi 1\xfe R 2 r 0 B B @ x 1 C C A 2 6 6 4 y 3 7 7 5"
    bag = pr.text_symbols(text, "Electric field", None, springer=True)
    assert bag == {"E": 1, "t": 1, "=": 1, "1": 2, "+": 2, "R": 1, "2": 1, "x": 1, "y": 1}


def test_springer_confusables():
    # In Springer's math fonts the prime is set as 0 and the element-of sign as a lunate epsilon.
    bag = pr.text_symbols("xϵR d V 0 j", None, None, springer=True)
    assert bag["ε∈"] == 1 and bag["0'"] == 1


@needs_node
def test_two_readings_that_agree_confirm_the_source():
    b = {"text": "m x \xf0 \xde \xbc E\xbd f x \xf0 \xde\x8a \xf022\xde", "eq_number": "22"}
    d = pr.decide(r"m ( x ) = E [ f ( x ) ]", r"m(x) = E\left[f(x)\right]", b, springer=True)
    assert d["status"] == "agree" and d["used"] == "parser"


@needs_node
def test_text_layer_picks_the_reading_that_matches_the_page():
    b = {"text": "μ n x n\xfe1 \x00 \x01 \xbc k n\xfe1 K \x001 y 1:n \xf027\xde", "eq_number": "27"}
    d = pr.decide(r"\mu_n(x_{n+1}) = k_{n+1} K^{1} y_{1;n}", r"\mu_n(x_{n+1}) = k_{n+1} K^{-1} y_{1:n}", b, springer=True)
    assert d["status"] == "page" and d["used"] == "vision"
    assert d["off"] == {"parser": 2, "vision": 0}


@needs_node
def test_a_tie_keeps_the_parser_reading_and_marks_it_disputed():
    b = {"text": "a b c \xbc 1", "eq_number": None}
    d = pr.decide(r"\frac{a}{b c} = 1", r"\frac{a}{b} c = 1", b, springer=True)
    assert d["status"] == "disputed" and d["used"] == "parser"


@needs_node
def test_vision_only_needs_the_text_layer_to_back_it():
    b = {"text": "τ zz \xbc 2β f Θ \xf0 \xde \xf011\xde", "eq_number": "11"}
    ok = pr.decide(r"\tau _ { = } = \frac{", r"\tau_{zz} = 2 \beta f(\Theta)", b, springer=True)
    assert ok["status"] == "vision_only" and ok["used"] == "vision"
    bad = pr.decide(r"\tau _ { = } = \frac{", r"\alpha = \gamma + \delta \kappa \lambda", b, springer=True)
    assert bad["status"] == "unreadable" and bad["used"] == "parser"


@needs_node
def test_no_usable_second_reading():
    b = {"text": "x \xbc 1", "eq_number": None}
    assert pr.decide("x = 1", None, b, springer=True)["status"] == "single"
    assert pr.decide("x = 1", r"\frac{x}{", b, springer=True)["status"] == "single"
