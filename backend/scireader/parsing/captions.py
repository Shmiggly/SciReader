"""Numbering from the page: which caption belongs to which figure, and equation numbers the parser's text lost.

Docling links most captions to their figures, but not all: MDPI captions that came out as paragraphs, PA12 captions
behind a printout header ("Page 1 of 1 Printed by … Figure 3: …"), and on some MDPI pages every caption linked to the
figure below it instead of the one above. A paper puts its captions on the same side of its figures throughout, so
each labeled caption takes the nearest figure on that side; Docling's link is the fallback.
"""

from __future__ import annotations

import re

FIG_LABEL = re.compile(r"(fig(?:ure)?|table|scheme)\.?\s*(S?\d+[A-Za-z]?)", re.I)
# A paragraph that is really a caption: "Figure 4. Schematics of…" (not "Figure 4 shows…").
CAPTION_START = re.compile(r"((?i:fig(?:ure)?))\.?\s*(\d+)\s*[.:]\s+[A-Z(]")
# Furniture before a caption's label: running headers ("20 of 24", "Page 1 of 1", "Polymers 2021, 13, x FOR PEER
# REVIEW 7 of 25") and a printout's header line ("Printed by Materials Studio at 4:04:21 PM on 2/24/2023").
LEAD_MARK = re.compile(
    r"\s*(?:Page \d{1,3} of \d{1,3}|\d{1,3} of \d{1,3}"
    r"|[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3} (?:19|20)\d\d, \d{1,4}, (?:x|\d{1,6})(?: FOR PEER REVIEW)? \d{1,3} of \d{1,3}"
    r"|Printed by [^.\n]{1,80}? on \d{1,2}/\d{1,2}/\d{2,4})\b"
)
PRINTED_NUMBER = re.compile(r"\(((?:[A-Z]\.?)?\d{1,3}[a-z]?(?:,[a-z])*)\)")

MIN_FIGURE_AREA = 1500.0  # pt²: smaller pictures are logos and icons
MAX_GAP = 70.0  # pt between a figure and its caption
OVERLAP = 25.0  # pt a caption may overlap its figure's box


def _after_marks(text: str) -> int:
    pos = 0
    while m := LEAD_MARK.match(text, pos):
        if m.end() == pos:
            break
        pos = m.end()
    return pos


def caption_label(text: str) -> tuple[str, str, int] | None:
    """(kind, number, where the label starts) of a caption: at its start, once furniture before it is skipped
    (the text before the label is then not read)."""
    start = _after_marks(text)
    while start < len(text) and text[start].isspace():
        start += 1
    m = FIG_LABEL.match(text, start)
    if not m:
        return None
    kind = "table" if m.group(1).lower().startswith("tab") else "scheme" if m.group(1).lower().startswith("sch") else "figure"
    return kind, m.group(2), m.start(1)


def paragraph_caption(text: str) -> str | None:
    """The figure number of a paragraph that is really a figure caption, else None."""
    start = _after_marks(text)
    while start < len(text) and text[start].isspace():
        start += 1
    m = CAPTION_START.match(text, start)
    return m.group(2) if m else None


def _overlap_x(a: list[float], b: list[float]) -> float:
    return min(a[2], b[2]) - max(a[0], b[0])


def _side(fig: list[float], cap: list[float]) -> str | None:
    if fig[3] <= cap[1] + OVERLAP:
        return "above"  # the figure is above its caption
    if fig[1] >= cap[3] - OVERLAP:
        return "below"
    return None


def _gap(fig: list[float], cap: list[float], side: str) -> float:
    return cap[1] - fig[3] if side == "above" else fig[1] - cap[3]


def link_captions(figures: list[dict], blocks: list[dict]) -> None:
    """Give figures their captions, labels and numbers (in place). Tables keep Docling's links."""
    by_id = {b["id"]: b for b in blocks}
    figs = [f for f in figures if f["kind"] == "figure"]
    caps: dict[str, str] = {}  # caption block id -> figure number
    for b in blocks:
        if b.get("skip_reason") == "junk":
            continue
        if b["type"] == "caption":
            lab = caption_label(b["text"])
            if lab and lab[0] == "figure":
                caps[b["id"]] = lab[1]
        elif b["type"] in ("paragraph", "other") and not b.get("skip_reason"):
            n = paragraph_caption(b["text"])
            if n:
                caps[b["id"]] = n
    docling = {f["id"]: f.get("caption_block_id") for f in figs}

    # Which side of their figures this paper's captions are on, from Docling's links (figures above their captions
    # unless clearly otherwise: some of those links are the wrong neighbour).
    votes = {"above": 0, "below": 0}
    for f in figs:
        cb = by_id.get(docling[f["id"]] or "")
        if cb and cb["id"] in caps and cb["page"] == f["page"]:
            s = _side(f["bbox"], cb["bbox"])
            if s:
                votes[s] += 1
    side = "below" if votes["below"] >= 2 and votes["below"] > 2 * votes["above"] else "above"

    # Each labeled caption takes the nearest free figure on that side of it (same page, same column).
    pairs = []
    for cid, _n in caps.items():
        cb = by_id[cid]
        for f in figs:
            fb = f["bbox"]
            if f["page"] != cb["page"] or (fb[2] - fb[0]) * (fb[3] - fb[1]) < MIN_FIGURE_AREA:
                continue
            if _overlap_x(fb, cb["bbox"]) < 0.3 * min(fb[2] - fb[0], cb["bbox"][2] - cb["bbox"][0]):
                continue
            if _side(fb, cb["bbox"]) != side:
                continue
            g = _gap(fb, cb["bbox"], side)
            if -OVERLAP <= g <= MAX_GAP:
                pairs.append((g, cid, f["id"]))
    link: dict[str, str] = {}  # figure id -> caption block id
    taken: set[str] = set()
    for _g, cid, fid in sorted(pairs):
        if fid not in link and cid not in taken:
            link[fid] = cid
            taken.add(cid)
    # Docling's link where geometry found nothing (a caption on the other side, or farther away).
    for f in figs:
        cid = docling[f["id"]]
        if f["id"] not in link and cid and cid not in taken:
            link[f["id"]] = cid
            taken.add(cid)

    for f in figs:
        old = by_id.get(docling[f["id"]] or "")
        if old is not None and old.get("figure_id") == f["id"]:
            old.pop("figure_id", None)
        f.update(caption_block_id=None, label=None, number=None)
    for fid, cid in link.items():
        f = next(x for x in figs if x["id"] == fid)
        by_id[cid]["figure_id"] = fid
        f["caption_block_id"] = cid
        if cid in caps:
            f["number"] = caps[cid]
            f["label"] = f"Figure {caps[cid]}"
    for cid in caps:
        by_id[cid]["type"] = "caption"  # paragraphs that are captions are read as captions (and hold no mentions)


def printed_equation_number(chars: list, bbox: list[float]) -> str | None:
    """The number printed at the right end of an equation's lines, "(6)" or "(1a,b)", read from the PDF's
    characters (IOP's text layer has it; the parser's copy of the equation lost the parentheses)."""
    x0, y0, x1, y1 = bbox
    inside = [c for c in chars if c.box[1] < y1 + 1 and c.box[3] > y0 - 1 and c.box[0] >= x0 - 1 and not c.ch.isspace()]
    if not inside:
        return None
    sizes = sorted(c.size for c in inside)
    body = sizes[len(sizes) // 2]
    closers = sorted((c for c in inside if c.ch == ")" and abs(c.box[2] - x1) <= 4), key=lambda c: -c.box[2])
    for close in closers:
        row = sorted((c for c in inside if abs(c.base - close.base) < 2.5 and c.box[2] <= close.box[2] + 0.5),
                     key=lambda c: c.box[0])
        number: list = []
        for c in reversed(row):
            number.insert(0, c)
            if c.ch == "(":
                break
        m = PRINTED_NUMBER.fullmatch("".join(c.ch for c in number))
        if not m or close.size < 0.8 * body:
            continue  # not a number, or a raised script such as x^(1)
        left = [c for c in inside if c not in number and c.box[2] <= number[0].box[0] + 0.5
                and c.box[1] < close.box[3] and c.box[3] > close.box[1]]
        if left and number[0].box[0] - max(c.box[2] for c in left) < 4:
            continue  # glued to the formula: part of it
        return m.group(1)
    return None
