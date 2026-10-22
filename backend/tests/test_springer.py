from scireader.parsing.builder import repair_springer_math, repair_springer_symbols
from scireader.parsing.pdfchars import PdfChar


def _fix(text: str) -> str:
    out, mapped = repair_springer_math(text, list(range(len(text))))
    assert len(out) == len(mapped)
    return out


def test_inline_math_from_springer_text_layer():
    assert _fix("f x ( ) can be completely estimated by a mean m x ( ) and a covariance function K x; x' ( ):") == (
        "f(x) can be completely estimated by a mean m(x) and a covariance function K(x, x'):")
    assert _fix("pairs of observations D = x; y; i = 1; 2; =; n that are") == (
        "pairs of observations D = x, y; i = 1, 2, …, n that are")


def test_prose_is_untouched():
    s = "We tested two cases; in both, the jet (Fig. 3) was stable at 1:1 ratios = 0.5."
    assert _fix(s) == s


def _glyphs(text: str, prime: bool = False) -> list:
    """Glyphs as the flagship's text layer has them: 8.66 pt, a digit 4.3 pt wide, the prime (a "0") 1.4 pt."""
    out, x = [], 0.0
    for ch in text:
        w = 1.4 if prime and ch == "0" else 4.3
        out.append(None if ch == " " else PdfChar(ch, (x, 0.0, x + w, 8.0), 8.66, 8.0))
        x += w
    return out


def test_springer_prime_and_element_of():
    # Flagship p. 13: "the curvature θ′" and "K ∈ R^{n×n}" as the text layer gives them.
    assert repair_springer_symbols("the curvature θ 0 at", _glyphs("the curvature θ 0 at", prime=True)) == "the curvature θ ′ at"
    assert repair_springer_symbols("at x = 0 and θ 0", _glyphs("at x = 0 and θ 0")) == "at x = 0 and θ 0"  # real zeros
    assert repair_springer_symbols("θ); KϵR nxn , which", _glyphs("θ); KϵR nxn , which")) == "θ); K∈R nxn , which"
    assert repair_springer_symbols("where ϵ is small", _glyphs("where ϵ is small")) == "where ϵ is small"


def test_char_map_follows_moved_characters():
    out, mapped = repair_springer_math("a f x ( ) b", list(range(11)))
    assert out == "a f(x) b"
    assert [mapped[i] for i in range(len(out))] == [0, 1, 2, 6, 4, 8, 9, 10]
