"""Build SciReader's Document JSON (v1) from a Docling conversion plus the PDF text layer.

Steps: Docling items → blocks (type, page, bbox, text/LaTeX) → structural heuristics (title,
front matter, authors, affiliations, references, boilerplate) → character alignment with the PDF
(sentence and word rectangles, superscript citations) → sentences with spoken text.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Callable

from ..speech.math_speech import get_math_speech
from ..speech.pipeline import expand_numbers, find_citations, get_lexicon, speak, split_sentences
from .latex import clean_latex, equation_intro, extract_equation_number, is_fragment, latex_has_content, split_label
from .pdfchars import PdfChar, PdfText, align, rects_for_span, restore_hyphens, superscript_mask

Progress = Callable[[str, float], None]

LABEL_MAP = {
    "title": "title",
    "section_header": "heading",
    "text": "paragraph",
    "paragraph": "paragraph",
    "list_item": "list_item",
    "formula": "equation",
    "picture": "figure",
    "chart": "figure",
    "caption": "caption",
    "table": "table",
    "footnote": "footnote",
    "page_header": "page_header",
    "page_footer": "page_footer",
    "reference": "bib_entry",
    "document_index": "other",
    "code": "other",
}

# Default skip reasons (the frontend can toggle each category back on).
SKIP_BY_TYPE = {
    "page_header": "page_furniture",
    "page_footer": "page_furniture",
    "footnote": "footnote",
    "bib_entry": "bibliography",
    "figure": "figure_body",
    "table": "table_body",
}

REFS_HEADING = re.compile(r"^\s*(\d+\.?\s*)?(references|bibliography|literature cited|works cited|references and notes)\s*$", re.I)
ABSTRACT_HEADING = re.compile(r"^\s*abstract\s*[:.]?\s*$", re.I)
BACK_MATTER_SKIP = re.compile(
    r"^\s*(open access\b|this article is licensed under|reprints and permission|publisher'?s note|"
    r"received:|accepted:|published online|correspondence and requests|peer review information|"
    r"©|copyright)", re.I,
)
AFFILIATION = re.compile(
    r"(universit|institut|department|dept\.|laborator|college|school of|faculty|centre|center for|"
    r"@|e-?mail|corresponding author|correspondence)", re.I,
)
FIG_LABEL = re.compile(r"^\s*(fig(?:ure)?|table|scheme)\.?\s*(S?\d+[A-Za-z]?)", re.I)
DOI = re.compile(r"\b10\.\d{4,9}/[^\s,;]+[^\s,;.)]")
ARXIV = re.compile(r"arXiv[:\s]*(\d{4}\.\d{4,5})", re.I)
DROP_CAP = re.compile(r"^([B-HJ-Z]) ([a-z]{1,})\b")
# Springer Nature PDFs encode math glyphs with wrong code points (MathPi fonts).
SPRINGER_GLYPHS = str.maketrans({"¼": "=", "ð": "(", "Þ": ")", "þ": "+", "Ã": "×"})
# ...and set decimal points as colons ("0:033 s"); only "0:ddd" is safe to fix (ratios like 1:1 exist).
SPRINGER_DECIMAL = re.compile(r"(?<![\d:])(0):(\d)")


# Springer also sets inline-math parentheses as separate glyphs that the text layer puts after their content
# ("f x ð Þ" for f(x)), math commas as ";" and "…" as "=". These patterns never occur in prose.
_SPRINGER_CALL = re.compile(r"\b([A-Za-zα-ωΑ-Ω]) ((?:[A-Za-z0-9α-ω]'?)(?:; ?[A-Za-z0-9α-ω]'?){0,3}) ?(\() ?(\))")
_SPRINGER_LIST = re.compile(r"\b\d+(?:; \d+)+; =; [a-zA-Z]\b|\b[a-zA-Z]; [a-zA-Z]\b")


def repair_springer_math(text: str, mapped: list) -> tuple[str, list]:
    """"f x ( )" → "f(x)", "K x; x' ( )" → "K(x, x')", "i = 1; 2; =; n" → "i = 1, 2, …, n", keeping the char map."""
    out_t: list[str] = []
    out_m: list = []
    last = 0
    for m in _SPRINGER_CALL.finditer(text):
        out_t.append(text[last:m.start()])
        out_m.extend(mapped[last:m.start()])
        seq = [(m.start(1), m.group(1)), (m.start(3), "(")]
        seq += [(m.start(2) + k, "," if ch == ";" else ch) for k, ch in enumerate(m.group(2))]
        seq.append((m.start(4), ")"))
        for i, ch in seq:
            out_t.append(ch)
            out_m.append(mapped[i])
        last = m.end()
    out_t.append(text[last:])
    out_m.extend(mapped[last:])
    text = "".join(out_t)
    # Same-length substitutions: the char map is unchanged.
    text = _SPRINGER_LIST.sub(lambda m: m.group(0).replace(";", ",").replace("=", "…"), text)
    return text, out_m


def _compound(left: str, right: str) -> bool:
    """A hyphen at a line end is part of the word when both halves are words and the joined form isn't one:
    "physics-based", "data-driven" (but "how-ever" → "however", "pro-cessing" → "processing")."""
    from ..speech.review import _known

    return len(left) >= 3 and len(right) >= 3 and _known(left) and _known(right) and not _known(left + right)


@dataclass
class RawBlock:
    type: str
    page: int
    bbox: list[float]
    text: str
    provs: list[tuple[int, list[float]]]
    ref: str
    latex: str | None = None
    caption_refs: list[str] = field(default_factory=list)
    skip_reason: str | None = None
    heading_size: float = 0.0
    eq_number: str | None = None


def _bbox_tl(prov: Any, page_h: float) -> list[float]:
    bb = prov.bbox
    if str(bb.coord_origin).upper().endswith("BOTTOMLEFT"):
        return [bb.l, page_h - bb.t, bb.r, page_h - bb.b]
    return [bb.l, bb.t, bb.r, bb.b]


def docling_blocks(doc: Any) -> tuple[list[RawBlock], list[tuple[float, float]]]:
    from docling_core.types.doc import ContentLayer

    pages = sorted(doc.pages.items())
    sizes = [(p.size.width, p.size.height) for _, p in pages]
    blocks: list[RawBlock] = []
    for item, _level in doc.iterate_items(included_content_layers={ContentLayer.BODY, ContentLayer.FURNITURE}):
        label = str(getattr(item, "label", "text")).split(".")[-1].lower()
        btype = LABEL_MAP.get(label, "other")
        provs = []
        for p in getattr(item, "prov", None) or []:
            pi = p.page_no - 1
            provs.append((pi, _bbox_tl(p, sizes[pi][1])))
        if not provs:
            continue
        text = getattr(item, "text", "") or ""
        rb = RawBlock(type=btype, page=provs[0][0], bbox=provs[0][1], text=text, provs=provs, ref=item.self_ref)
        if btype == "equation":
            rb.latex = text
            rb.text = getattr(item, "orig", "") or text
        if btype in ("figure", "table"):
            rb.caption_refs = [c.cref for c in getattr(item, "captions", []) or []]
        blocks.append(rb)
    return blocks, sizes


# ---------------------------------------------------------------------------------------------
# Structural heuristics


def apply_heuristics(blocks: list[RawBlock], pdftext: PdfText) -> dict:
    meta: dict[str, Any] = {"title": "", "authors": []}
    springer = sum(b.text.count("ð") + b.text.count("Þ") for b in blocks) >= 6
    meta["springer_glyphs"] = springer

    # Junk: blocks without letters or digits worth reading (e.g. hidden "1234567890():,;" strips).
    for b in blocks:
        w = b.bbox[2] - b.bbox[0]
        if b.type in ("paragraph", "list_item", "other") and (w < 15 or not re.search(r"[A-Za-z]{2,}", b.text)):
            b.skip_reason = "junk"

    # Heading font sizes (for title and levels).
    for b in blocks:
        if b.type in ("heading", "title"):
            chars = pdftext.chars_in(b.page, b.bbox)
            b.heading_size = median([c.size for c in chars]) if chars else 0.0

    # Title: explicit title, else the largest heading on the first page.
    title_idx = next((i for i, b in enumerate(blocks) if b.type == "title"), None)
    if title_idx is None:
        cands = [(b.heading_size, -i, i) for i, b in enumerate(blocks) if b.type == "heading" and b.page == 0]
        if cands:
            title_idx = max(cands)[2]
            blocks[title_idx].type = "title"
    if title_idx is not None:
        meta["title"] = re.sub(r"\s+", " ", blocks[title_idx].text).strip()
        # Front matter before the title on page 1 ("ARTICLE", DOI line, journal name).
        for b in blocks[:title_idx]:
            if b.page == 0 and b.type in ("paragraph", "other", "heading", "list_item"):
                b.skip_reason = b.skip_reason or "front_matter"

    # Authors / affiliations: page-1 blocks after the title and before the abstract or first heading.
    start = (title_idx + 1) if title_idx is not None else 0
    abstract_found = False
    for i in range(start, len(blocks)):
        b = blocks[i]
        if b.page > 0 or abstract_found:
            break
        if b.type == "heading":
            if ABSTRACT_HEADING.match(b.text):
                continue
            break
        if b.type not in ("paragraph", "other", "list_item", "footnote"):
            continue
        txt = b.text.strip()
        if len(txt) > 350 and not AFFILIATION.search(txt[:120]):
            b.type = "abstract"
            abstract_found = True
            break
        if AFFILIATION.search(txt):
            b.skip_reason = "affiliation"
        elif txt.count(",") >= 1 or " and " in txt or "&" in txt:
            b.skip_reason = "authors"
            if not meta["authors"]:
                names = re.sub(r"[\d*†‡§✉]+", "", txt)
                meta["authors"] = [n.strip() for n in re.split(r",|\band\b|&", names) if len(n.strip()) > 2][:30]
        else:
            b.skip_reason = "front_matter"
    if not abstract_found:
        # An explicit "Abstract" heading: mark the next paragraph.
        for i, b in enumerate(blocks):
            if b.type == "heading" and ABSTRACT_HEADING.match(b.text):
                nxt = next((x for x in blocks[i + 1:] if x.type == "paragraph"), None)
                if nxt:
                    nxt.type = "abstract"
                break

    # Page-1 affiliations anywhere (e.g. as footnotes).
    for b in blocks:
        if b.page == 0 and b.type in ("paragraph", "footnote", "other") and b.skip_reason is None:
            if AFFILIATION.search(b.text[:200]) and len(b.text) < 900 and b.type != "abstract":
                if re.search(r"universit|institut|department|laborator|@", b.text, re.I):
                    b.skip_reason = "affiliation"

    # References section: everything after a References heading until the next heading.
    in_refs = False
    for b in blocks:
        if b.type in ("heading", "title"):
            in_refs = bool(REFS_HEADING.match(b.text))
            continue
        if in_refs and b.type in ("list_item", "paragraph", "other", "bib_entry"):
            b.type = "bib_entry"

    # Publisher boilerplate.
    for b in blocks:
        if b.type in ("paragraph", "other", "footnote") and BACK_MATTER_SKIP.match(b.text):
            b.skip_reason = b.skip_reason or "boilerplate"

    # Text fixes.
    first_body = True
    for b in blocks:
        if b.type in ("paragraph", "abstract") and b.skip_reason is None and first_body and b.page <= 1:
            if b.type == "paragraph":
                b.text = DROP_CAP.sub(lambda m: m.group(1) + m.group(2), b.text, count=1)
                first_body = False

    # Default skip by type.
    for b in blocks:
        if b.skip_reason is None and b.type in SKIP_BY_TYPE:
            b.skip_reason = SKIP_BY_TYPE[b.type]

    # Heading levels from numbering, then font size.
    heads = [b for b in blocks if b.type == "heading"]
    sizes = [b.heading_size for b in heads if b.heading_size > 0]
    top = max(sizes) if sizes else 0
    for b in heads:
        m = re.match(r"^\s*(\d+(?:\.\d+)*)\.?\s+\S", b.text)
        if m:
            b.heading_size = -(m.group(1).count(".") + 1)  # encode level
        elif top and b.heading_size >= top - 0.6:
            b.heading_size = -1
        else:
            b.heading_size = -2
    return meta


# ---------------------------------------------------------------------------------------------
# Assembly


def build_document(
    doc: Any,
    pdf_path: str,
    doc_id: str,
    source: dict,
    progress: Progress | None = None,
) -> tuple[dict, dict]:
    """Return (document_json, speech_index): sentence id → {"drop": citation spans, "words": [[d0, d1, rects], ...]}."""
    say = progress or (lambda msg, frac: None)
    say("Reading the PDF text layer", 0.72)
    pdftext = PdfText(pdf_path)
    raw, sizes = docling_blocks(doc)
    meta = apply_heuristics(raw, pdftext)
    lexicon = get_lexicon()
    math = get_math_speech()

    out_blocks: list[dict] = []
    outline: list[dict] = []
    figures: list[dict] = []
    bibliography: list[dict] = []
    citations: list[dict] = []
    words: dict[str, list] = {}
    caption_of: dict[str, str] = {}
    ref_to_block: dict[str, str] = {}
    sentence_counter = 0
    section_id: str | None = None
    bib_counter = 0
    eq_counter = 0
    eq_boxes: dict[int, list] = {}
    for b in raw:
        if b.type == "equation":
            eq_boxes.setdefault(b.page, []).append(b.bbox)

    say("Building sentences", 0.78)
    for bi, b in enumerate(raw):
        block_id = f"b{bi}"
        ref_to_block[b.ref] = block_id
        block: dict[str, Any] = {
            "id": block_id,
            "type": b.type,
            "page": b.page,
            "bbox": [round(v, 1) for v in b.bbox],
            "section_id": section_id,
            "text": b.text,
            "sentences": [],
        }
        if b.skip_reason:
            block["skip_reason"] = b.skip_reason

        if b.type in ("heading", "title"):
            level = int(-b.heading_size) if b.heading_size < 0 else 1
            if b.type == "heading":
                section_id = f"sec{len(outline)}"
                block["section_id"] = section_id
                block["level"] = level
                outline.append({"id": section_id, "title": re.sub(r"\s+", " ", b.text).strip(), "level": level, "block_id": block_id})

        if b.type == "equation":
            latex_raw = b.latex or ""
            latex_nonum, number = extract_equation_number(latex_raw)
            eq_label, latex = split_label(clean_latex(latex_nonum), b.text)
            if number is None:
                m = re.search(r"\((\d{1,3}[a-z]?)\)\s*$", b.text.translate(SPRINGER_GLYPHS))
                number = m.group(1) if m else None
            if is_fragment(number, eq_label, latex, b.bbox, [o for o in eq_boxes[b.page] if o is not b.bbox]):
                block["skip_reason"] = "junk"  # not read, no badge, not checked
            else:
                eq_counter += 1
            block["latex"] = latex
            block["latex_raw"] = latex_raw
            block["eq_number"] = number
            block["eq_label"] = eq_label
            speech = math.speak(latex) if latex_has_content(latex) else None
            block["speech_rules"] = speech
            intro = equation_intro(number, eq_label)
            spoken = f"{intro}: {speech}." if speech else f"{intro}."
            sid = f"s{sentence_counter}"
            sentence_counter += 1
            block["sentences"].append({
                "id": sid, "text": latex, "spoken": spoken,
                "rects": [[pi, *[round(v, 1) for v in bb]] for pi, bb in b.provs],
                "kind": "equation",
            })
            words[sid] = {"drop": [], "words": []}
            out_blocks.append(block)
            continue

        if b.type in ("figure", "table"):
            fig_id = f"fig{len(figures)}"
            block["figure_id"] = fig_id
            figures.append({"id": fig_id, "kind": b.type, "label": None, "number": None, "page": b.page,
                            "bbox": block["bbox"], "caption_block_id": None, "_caption_refs": b.caption_refs})
            for cref in b.caption_refs:
                caption_of[cref] = fig_id
            out_blocks.append(block)
            continue

        # Text-like blocks: align to PDF characters across all provenance boxes.
        text = re.sub(r"\s+", " ", b.text).strip()
        mapped: list[PdfChar | None] = []
        pdf_chars: list[PdfChar] = []
        for pi, bb in b.provs:
            pdf_chars.extend(pdftext.chars_in(pi, bb))
        mapped = align(text, pdf_chars)
        text, mapped = restore_hyphens(text, mapped, pdf_chars, _compound)
        if meta.get("springer_glyphs"):
            text = SPRINGER_DECIMAL.sub(r"\1.\2", text.translate(SPRINGER_GLYPHS))
            text, mapped = repair_springer_math(text, mapped)
        block["text"] = text

        sup = (superscript_mask(mapped) if b.type in ("paragraph", "abstract", "list_item", "caption") and not b.skip_reason
               else [False] * len(text))
        sup_cites = _superscript_citations(text, sup)

        if b.type == "bib_entry":
            bib_counter += 1
            m = re.match(r"^\s*\[?(\d{1,3})[\].]\s+", text)
            label = m.group(1) if m else str(bib_counter)
            entry = {"id": f"bib{label}", "label": label, "text": text, "block_id": block_id}
            d = DOI.search(text)
            if d:
                entry["doi"] = d.group(0)
            a = ARXIV.search(text)
            if a:
                entry["arxiv"] = a.group(1)
            bibliography.append(entry)

        spans = split_sentences(text) if text else []
        if b.type in ("heading", "title") and len(spans) > 1:
            spans = [(0, len(text))]
        for s0, s1 in spans:
            sid = f"s{sentence_counter}"
            sentence_counter += 1
            stext = text[s0:s1]
            drop: list[tuple[int, int]] = []
            for c0, c1, nums in find_citations(stext):
                drop.append((c0, c1))
                if nums:
                    citations.append({"sentence_id": sid, "span": [c0, c1], "bib_ids": [f"bib{n}" for n in nums],
                                      "rects": _rects(mapped, s0 + c0, s0 + c1)})
            for c0, c1, nums in sup_cites:
                if s0 <= c0 and c1 <= s1:
                    drop.append((c0 - s0, c1 - s0))
                    citations.append({"sentence_id": sid, "span": [c0 - s0, c1 - s0], "bib_ids": [f"bib{n}" for n in nums],
                                      "rects": _rects(mapped, c0, c1)})
            if b.skip_reason is None or b.type == "caption":
                norm = speak(stext, drop, lexicon)
                spoken = norm.spoken
            else:
                spoken = stext
            if b.type == "heading":
                spoken = spoken.rstrip(".") + "."
            rects = _rects(mapped, s0, s1) or [[b.page, *[round(v, 1) for v in b.bbox]]]
            sentence = {"id": sid, "text": stext, "spoken": spoken, "rects": rects}
            block["sentences"].append(sentence)
            words[sid] = {"drop": sorted(drop), "words": _word_boxes(stext, mapped, s0)}
        out_blocks.append(block)

    # Captions → figures; figure labels.
    for blk, b in zip(out_blocks, raw):
        if b.type == "caption":
            fig_id = caption_of.get(b.ref)
            if fig_id:
                blk["figure_id"] = fig_id
                fig = next(f for f in figures if f["id"] == fig_id)
                fig["caption_block_id"] = blk["id"]
                m = FIG_LABEL.match(blk["text"])
                if m:
                    kind = "Table" if m.group(1).lower().startswith("tab") else "Figure"
                    fig["label"] = f"{kind} {m.group(2)}"
                    fig["number"] = m.group(2)
    for f in figures:
        f.pop("_caption_refs", None)

    pages = [{"index": i, "width": round(w, 2), "height": round(h, 2)} for i, (w, h) in enumerate(sizes)]
    document = {
        "version": 1,
        "id": doc_id,
        "title": meta.get("title") or source.get("name", "Untitled"),
        "authors": meta.get("authors", []),
        "source": source,
        "pages": pages,
        "outline": outline,
        "blocks": out_blocks,
        "figures": figures,
        "bibliography": bibliography,
        "citations": citations,
        "ocr": sum(len(c) for c in pdftext.pages) < 40 * max(1, len(pdftext.pages)),
        "stats": {
            "blocks": len(out_blocks),
            "sentences": sentence_counter,
            "equations": eq_counter,
            "types": dict(Counter(b["type"] for b in out_blocks)),
        },
    }
    pdftext.close()
    return document, words


def _rects(mapped: list[PdfChar | None], s0: int, s1: int) -> list[list[float]]:
    """Rectangles (one per line, split at page changes) for characters [s0, s1)."""
    out: list[list[float]] = []
    run_start, cur = s0, None
    for i in range(s0, s1):
        c = mapped[i]
        if c is None:
            continue
        if cur is None:
            cur, run_start = c.page, i
        elif c.page != cur:
            out.extend(rects_for_span(mapped, run_start, i, cur))
            cur, run_start = c.page, i
    if cur is not None:
        out.extend(rects_for_span(mapped, run_start, s1, cur))
    return out


def _word_boxes(stext: str, mapped: list[PdfChar | None], s0: int) -> list:
    out = []
    for m in re.finditer(r"\S+", stext):
        rects = _rects(mapped, s0 + m.start(), s0 + m.end())
        if rects:
            out.append([m.start(), m.end(), rects])
    return out


def _superscript_citations(text: str, sup: list[bool]) -> list[tuple[int, int, list[int]]]:
    """Runs of superscripted digits/commas/dashes (e.g. 'printing12,13' or 'level 18 .') → citation spans."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        if sup[i] and text[i].isdigit():
            j = i
            while j < n and (sup[j] and (text[j].isdigit() or text[j] in ",–-") or (text[j] == " " and j + 1 < n and sup[j + 1])):
                j += 1
            run = text[i:j].strip(" ,–-")
            nums = expand_numbers(run.replace(" ", ""))
            if nums and all(0 < x < 1000 for x in nums):
                a = i
                if a > 0 and text[a - 1] == " ":
                    a -= 1  # take the space Docling inserted before the marker
                b = j
                if b + 1 < n and text[b] == " " and text[b + 1] in ".,;:)":
                    b += 1  # and the one it left before the following punctuation
                out.append((a, b, nums))
            i = j
        else:
            i += 1
    return out
