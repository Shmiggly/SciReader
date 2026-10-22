"""Running headers that Docling leaves inside text blocks (MDPI page numbers, review-version headers, printouts)."""

from scireader.parsing.builder import RawBlock, _page_marks, apply_heuristics


def _block(text: str, page: int, type_: str = "paragraph") -> RawBlock:
    return RawBlock(type=type_, page=page, bbox=[50.0, 100.0, 500.0, 120.0], text=text, provs=[], ref="#")


def test_header_only_blocks_are_page_furniture():
    blocks = [
        _block("16 of 25", 14),
        _block("20 of 25 20 of 25", 18),
        _block("Polymers 2021, 13, x FOR PEER REVIEW 8 of 25", 7, "caption"),
        _block("3 of 5 samples failed the test.", 3),
    ]
    apply_heuristics(blocks, pdftext=None)  # no headings, so the text layer isn't needed
    assert [b.skip_reason for b in blocks] == ["page_furniture", "page_furniture", "page_furniture", None]


def test_page_marks_inside_text():
    text = "5 of 24 [A] to produce the first-radical (R')"
    assert [text[a:b] for a, b in _page_marks(text, 4)] == ["5 of 24"]  # its own page number, merged in by Docling
    assert _page_marks(text, 0) == []  # on another page it could be prose
    text = "an electron transfer between CQ and the Polymers 2021, 13, x FOR PEER REVIEW 7 of 25"
    assert [text[a:b] for a, b in _page_marks(text, 6)] == ["Polymers 2021, 13, x FOR PEER REVIEW 7 of 25"]
    text = "Page 1 of 1 Figure 2: Polyamide12 molecules."
    assert [text[a:b] for a, b in _page_marks(text, 2)] == ["Page 1 of 1"]
