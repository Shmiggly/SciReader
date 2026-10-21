from scireader.parsing.builder import repair_springer_math


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


def test_char_map_follows_moved_characters():
    out, mapped = repair_springer_math("a f x ( ) b", list(range(11)))
    assert out == "a f(x) b"
    assert [mapped[i] for i in range(len(out))] == [0, 1, 2, 6, 4, 8, 9, 10]
