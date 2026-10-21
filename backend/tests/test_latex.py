from scireader.parsing.latex import clean_latex, split_label


def test_word_runs_join_but_symbol_products_with_subscripts_do_not():
    assert clean_latex("J e t \\ R a d i u s \\quad 2 R _ { j }") == "\\mathrm{Jet} \\mathrm{Radius} 2 R _ { j }"
    assert clean_latex("f _ { h i g h } ( x )") == "f _ { \\mathrm{high} } ( x )"
    # Reynolds number times V_j: the subscript belongs to V, so the letters stay separate.
    assert clean_latex("R e V _ { j } V _ { j } ^ { \\prime }") == "R e V _ { j } V _ { j } ^ { \\prime }"
    assert clean_latex("y _ { l o w _ { 1 ; n } }") == "y _ { \\mathrm{low} _ { 1 ; n } }"


def test_split_label_from_garbled_ocr():
    # Flagship paper (Commun. Eng. 2023): the PDF has "Charge: σ = R (8)", the OCR LaTeX a garbled label.
    assert split_label("C h \\arg e \\cdot \\sigma = R", "Charge: σ ¼ R ð8Þ") == ("Charge", "\\sigma = R")
    assert split_label("\\mathrm{Momtun} \\colon R e V _ { j } = B o", "Momentum: ReV j ¼ Bo") == ("Momentum", "R e V _ { j } = B o")
    assert split_label("\\mathrm{Jet} \\mathrm{Aea} A _ { j } = [ x ]", "Jet Area A j ¼ ½x") == ("Jet Area", "A _ { j } = [ x ]")
    assert split_label("E _ { } \\text {Electric field} \\colon E _ { t } = 1", "Electric field: E t ¼ 1") == ("Electric field", "E _ { t } = 1")
    assert split_label("Constitutive: \\tau _ { z z } = 2 \\beta", "Constitutive: τ zz ¼ 2β") == ("Constitutive", "\\tau _ { z z } = 2 \\beta")
    assert split_label("L \\text { left Jet Angle} \\theta _ { j } = 1", "Left Jet Angle θ jl ¼ 1") == ("Left Jet Angle", "\\theta _ { j } = 1")


def test_split_label_leaves_plain_equations_alone():
    assert split_label("m ( x ) = E [ f ( x ) ]", "m x ð Þ ¼ E½ f x ð Þ ð22Þ") == (None, "m ( x ) = E [ f ( x ) ]")
    # A word in the PDF text that the LaTeX doesn't repeat: nothing is stripped.
    assert split_label("E = m c ^ { 2 }", "Energy E ¼ mc 2") == (None, "E = m c ^ { 2 }")
    assert split_label("a b c = d", "Energy a b c = d") == (None, "a b c = d")
