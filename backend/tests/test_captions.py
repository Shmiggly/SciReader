"""Figure numbers from captions on the page, and equation numbers read from the PDF's characters (cases from the
MDPI, PA12 and IOP sample papers)."""

from scireader.parsing.captions import caption_label, link_captions, paragraph_caption, printed_equation_number
from scireader.parsing.pdfchars import PdfChar


def test_caption_labels_behind_furniture():
    assert caption_label("Figure 2: Polyamide12 molecules.") == ("figure", "2", 0)
    assert caption_label("Page 1 of 1 Figure 2: Polyamide12 molecules.") == ("figure", "2", 12)
    pa12 = "Page 1 of 1 Printed by Materials Studio at 4:04:21 PM on 2/24/2023 Figure 3: Unit cell of PA12."
    assert caption_label(pa12) == ("figure", "3", pa12.index("Figure"))
    assert caption_label("20 of 24 Figure 20. Photopolymerization profiles")[:2] == ("figure", "20")
    assert caption_label("Table 1. Cont.") == ("table", "1", 0)
    # Docling's wrong "captions": text that is no caption at all
    assert caption_label("3,4-epoxycyclohexylcarboxylate (EPOX) were used as benchmark monomers. Polymers 2021, 13, x FOR PEER REVIEW 8 of 25") is None
    assert caption_label("with a very thin sample, as shown in Figure 5. The unique feature") is None


def test_paragraphs_that_are_captions():
    assert paragraph_caption("Figure 4. Schematics of photochemical pathways in a three-initiator system") == "4"
    assert paragraph_caption("Figure 11: Kinetic scheme of a dual-wavelength mixture") == "11"
    assert paragraph_caption("Figure 4 shows the schematics of the system") is None
    assert paragraph_caption("Figure 4. shows the schematics") is None


def _fig(i, page, bbox, cap=None, kind="figure"):
    return {"id": f"fig{i}", "kind": kind, "label": None, "number": None, "page": page, "bbox": bbox, "caption_block_id": cap}


def _blk(i, page, bbox, text, type_="caption", figure_id=None):
    b = {"id": f"b{i}", "type": type_, "page": page, "bbox": bbox, "text": text, "sentences": []}
    if figure_id:
        b["figure_id"] = figure_id
    return b


def test_captions_take_the_figure_above_them():
    # MDPI p. 8: captions sit under their figures, but Docling linked "Figure 7." to the figure below it and missed
    # "Figure 6." (a paragraph) and "Figure 8.".
    figures = [
        _fig(0, 0, [35, 46, 70, 70]),  # a logo: too small to be a figure
        _fig(1, 8, [168, 203, 434, 349]),
        _fig(2, 8, [172, 415, 472, 572]),
        _fig(3, 8, [169, 622, 406, 736], cap="b2"),
        _fig(4, 8, [166, 100, 560, 190], cap="b5", kind="table"),
    ]
    blocks = [
        _blk(1, 8, [167, 339, 560, 420], "Figure 6. The schematics of a three-initiator system.", "paragraph"),
        _blk(2, 8, [48, 572, 559, 604], "Figure 7. The proposed scheme for the G1/Iod/NVK copper complex.", figure_id="fig3"),
        _blk(3, 8, [166, 744, 560, 783], "Figure 8. (A) 3D-photopolymerization experiments."),
        _blk(4, 8, [167, 790, 560, 800], "Figure 6 shows the scheme.", "paragraph"),
        _blk(5, 8, [167, 80, 436, 95], "Table 2. Rates.", figure_id="fig4"),
    ]
    blocks[4]["figure_id"] = "fig4"
    link_captions(figures, blocks)
    assert [(f["id"], f["number"], f["caption_block_id"]) for f in figures[:4]] == [
        ("fig0", None, None), ("fig1", "6", "b1"), ("fig2", "7", "b2"), ("fig3", "8", "b3")]
    assert [b.get("figure_id") for b in blocks[:3]] == ["fig1", "fig2", "fig3"]
    assert blocks[0]["type"] == "caption" and blocks[3]["type"] == "paragraph"
    assert figures[4]["caption_block_id"] == "b5"  # tables keep Docling's link


def test_docling_link_kept_when_the_page_shows_nothing_better():
    # PA12 p. 2: the caption is linked and its label sits behind a printout header; nothing else is near.
    figures = [_fig(1, 2, [195, 322, 397, 464], cap="b22")]
    blocks = [_blk(22, 2, [64, 450, 531, 471], "Page 1 of 1 Figure 2: Polyamide12 molecules.", figure_id="fig1")]
    link_captions(figures, blocks)
    assert (figures[0]["number"], figures[0]["label"], figures[0]["caption_block_id"]) == ("2", "Figure 2", "b22")


def _chars(text: str, x: float, y: float = 100.0, size: float = 9.4, w: float = 4.5) -> list[PdfChar]:
    out = []
    for ch in text:
        if ch != " ":
            out.append(PdfChar(ch, (x, y, x + w, y + size), size, y + size))
        x += w
    return out


def test_equation_numbers_printed_at_the_line_end():
    formula = _chars("v=0,", 300)
    assert printed_equation_number(formula + _chars("(2)", 539.5), [300, 98, 553, 112]) == "2"
    assert printed_equation_number(formula + _chars("(1a,b)", 526), [300, 98, 553, 112]) == "1a,b"
    assert printed_equation_number(formula + _chars("(x)", 539.5), [300, 98, 553, 112]) is None
    assert printed_equation_number(formula, [300, 98, 553, 112]) is None
    # A raised script glued to the formula, as in h^(1), is part of it.
    glued = _chars("h", 530) + _chars("(1)", 534.5, y=96, size=6.5, w=4.5)
    assert printed_equation_number(formula + glued, [300, 96, 548, 112]) is None
    # IOP eq. 10: tall delimiters make most of the equation's characters large.
    tall = _chars("(", 340, size=12.7) + _chars(")", 360, size=12.7) + _chars("⎛⎞⎝⎠", 380, size=12.7) + _chars("n,", 400)
    assert printed_equation_number(tall + _chars("(10)", 535), [300, 98, 553, 112]) == "10"
