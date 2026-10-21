from scireader.parsing.latex import clean_latex, is_fragment, split_label


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


def test_equation_fragments_are_recognized():
    # Flagship p. 13: Docling split a 5.9 pt wide "2 2" matrix off the radicals of equation 9.
    eq9 = [131.5, 312.1, 291.7, 341.1]
    junk = r"\begin{matrix} 2 2 \end{matrix}"
    assert is_fragment(None, None, junk, [239.0, 280.5, 244.9, 344.2], [eq9])
    # Unreadable but real: a number, a label, or a box of its own keeps the block an equation.
    assert not is_fragment("11", None, junk, [52.8, 383.2, 291.7, 470.6], [])
    assert not is_fragment(None, "Electric field", "", [90.4, 271.2, 239.0, 299.7], [eq9])
    assert not is_fragment(None, None, junk, [90.0, 400.0, 240.0, 430.0], [eq9])
    assert is_fragment(None, None, "", [140.0, 315.0, 200.0, 335.0], [eq9])
    assert not is_fragment(None, None, "E = m c ^ { 2 }", [239.0, 280.5, 244.9, 344.2], [eq9])
    # GNN paper p. 11: a duplicate piece of the equation below, numbered "1" from its own superscript "(1)".
    assert is_fragment("1", None, "x _ { 0 } ^ { ( 1 ) }", [270.9, 447.7, 289.6, 461.5], [[269.3, 451.1, 342.7, 523.0]])
    assert not is_fragment(None, None, "x _ { 0 } ^ { ( 1 ) } = [ 4 1 , 4 1 ]", [269.3, 451.1, 342.7, 523.0],
                           [[270.9, 447.7, 289.6, 461.5]])
