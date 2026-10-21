"""Character boxes from the PDF text layer (pypdfium2) and alignment to parsed block text.

Docling gives block text and block boxes; the reader needs sentence and word rectangles and
superscript detection (numeric citations like "printing^12"). We read every character with its
box and font size from PDFium, collect the characters inside a block's box, and align them to the
block text with a character-level diff (whitespace ignored).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from statistics import median

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

Box = tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points, origin top-left


@dataclass(slots=True)
class PdfChar:
    ch: str
    box: Box
    size: float  # font size
    base: float  # baseline y (top-left origin), larger = lower on the page
    page: int = 0


class PdfText:
    """All characters of a PDF, page by page."""

    def __init__(self, path: str):
        self.pdf = pdfium.PdfDocument(path)
        self.pages: list[list[PdfChar]] = []
        self.sizes: list[tuple[float, float]] = []
        for page in self.pdf:
            w, h = page.get_size()
            self.sizes.append((w, h))
            tp = page.get_textpage()
            chars: list[PdfChar] = []
            n = tp.count_chars()
            for i in range(n):
                code = pdfium_c.FPDFText_GetUnicode(tp.raw, i)
                if code == 0:
                    continue
                try:
                    ch = chr(code)
                except ValueError:
                    continue
                l, b, r, t = tp.get_charbox(i, loose=True)
                if r - l <= 0 and ch.isspace():
                    continue
                # Loose box height = effective font size (FPDFText_GetFontSize ignores the text matrix).
                size = t - b
                chars.append(PdfChar(ch, (l, h - t, r, h - b), size, h - b, len(self.pages)))
            self.pages.append(chars)
            tp.close()
            page.close()

    def close(self) -> None:
        self.pdf.close()

    def chars_in(self, page_index: int, bbox: Box, pad: float = 1.5) -> list[PdfChar]:
        x0, y0, x1, y1 = bbox
        out = []
        for c in self.pages[page_index]:
            cx = (c.box[0] + c.box[2]) / 2
            cy = (c.box[1] + c.box[3]) / 2
            if x0 - pad <= cx <= x1 + pad and y0 - pad <= cy <= y1 + pad and not c.ch.isspace():
                out.append(c)
        return out


_EQUIV = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}


def align(text: str, chars: list[PdfChar]) -> list[PdfChar | None]:
    """Map each character of `text` to a PDF character (or None)."""
    result: list[PdfChar | None] = [None] * len(text)
    if not chars or not text:
        return result
    t_idx = [i for i, ch in enumerate(text) if not ch.isspace()]
    t_str = "".join(text[i] for i in t_idx)
    # Expand ligatures on the PDF side so "ﬁ" matches "fi".
    p_list: list[PdfChar] = []
    p_str_parts: list[str] = []
    for c in chars:
        s = _EQUIV.get(c.ch, c.ch)
        for ch in s:
            p_list.append(c)
            p_str_parts.append(ch)
    p_str = "".join(p_str_parts)
    sm = difflib.SequenceMatcher(None, t_str, p_str, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            result[t_idx[a + k]] = p_list[b + k]
    return result


def superscript_mask(mapped: list[PdfChar | None]) -> list[bool]:
    """True for characters set noticeably smaller and raised relative to the block's body text."""
    sizes = [c.size for c in mapped if c is not None and c.size > 0]
    if not sizes:
        return [False] * len(mapped)
    body = median(sizes)
    mask = []
    for i, c in enumerate(mapped):
        if c is None or c.size <= 0:
            mask.append(False)
            continue
        small = c.size < 0.86 * body
        if not small:
            mask.append(False)
            continue
        # Raised: baseline above neighbours' baselines (find nearest full-size neighbour).
        ref = None
        for j in list(range(i - 1, max(-1, i - 12), -1)) + list(range(i + 1, min(len(mapped), i + 12))):
            n = mapped[j]
            if n is not None and n.size >= 0.9 * body:
                ref = n
                break
        raised = ref is not None and c.base < ref.base - 0.15 * body
        mask.append(raised)
    return mask


def rects_for_span(mapped: list[PdfChar | None], start: int, end: int, page: int) -> list[list[float]]:
    """Merge the boxes of mapped characters in [start, end) into one rectangle per text line."""
    lines: list[list[float]] = []
    for c in mapped[start:end]:
        if c is None:
            continue
        x0, y0, x1, y1 = c.box
        if lines:
            cur = lines[-1]
            same_line = abs(((y0 + y1) / 2) - ((cur[2] + cur[4]) / 2)) < max(2.0, 0.5 * (y1 - y0)) and x0 >= cur[1] - 2
            if same_line:
                cur[1] = min(cur[1], x0)
                cur[2] = min(cur[2], y0)
                cur[3] = max(cur[3], x1)
                cur[4] = max(cur[4], y1)
                continue
        lines.append([page, x0, y0, x1, y1])
    return [[p, round(a, 1), round(b, 1), round(c, 1), round(d, 1)] for p, a, b, c, d in lines]
