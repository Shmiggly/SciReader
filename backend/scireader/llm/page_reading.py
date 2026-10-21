"""Second reading of display equations from the page, with the PDF text layer as tiebreaker.

The parser's formula OCR (Docling) is the first reading of each display equation. The vision model (the reader
model) transcribes a crop of the rendered page: a second, independent reading. When the two agree (canonical
MathML, verify.compare), the source LaTeX is confirmed. When they disagree, the PDF text layer decides: its glyph
order is useless (scripts and fraction parts come out of order), but its symbols are what is printed, so each
reading is compared with it as a bag of letters, digits and a few operators. The reading with fewer symbols off
wins; on a tie the parser's reading is kept and the source is marked disputed.
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter

from ..parsing.latex import clean_latex, latex_has_content, split_label
from . import ollama
from .figures import crop_png
from .verify import VARIANTS, canon_tokens, compare, to_mathml

OCR_SYSTEM = (
    "You transcribe images of display equations from scientific papers into LaTeX. Output only the LaTeX of the "
    "equation itself, exactly as printed: keep every symbol, subscript, superscript, prime, minus sign and bracket; "
    "do not simplify, complete or correct it. Leave out the equation number, such as (12), and any word label before "
    "the equation, such as 'Momentum:'. No $ signs, no \\[ \\], no code fences, no explanation."
)

# Springer Nature equation glyphs (MathPi fonts; see builder.SPRINGER_GLYPHS): ¼ is =, = is /, þ is +, ð Þ ½ \x8a
# are brackets, Ã is ×, the NUL byte is a minus (or, followed by \x01, a pair of big parentheses set after their
# content), \x18 is ∼, 0 doubles as the prime and ϵ as ∈.
_SPRINGER_EQ = str.maketrans({"¼": "=", "=": "/", "þ": "+", "ð": "(", "Þ": ")", "½": "[", "\x8a": "]", "Ã": "×",
                              "\x00": "-", "\x18": "∼"})
_SPRINGER_HINTS = "¼ðÞþ"
# TeX's extensible delimiters (cmex) come out of text layers as their pieces: "0 B B @" and "1 C C A" are a tall
# ( and ), "2 6 6 4" and "3 7 7 5" a tall [ and ], "8 > < > :" and "9 > = > ;" a tall { and }.
_TALL_DELIMS = re.compile(
    r"(?<![\w.])(?:0(?:\s*B)+\s*@|1(?:\s*C)+\s*A|2(?:\s*6)+\s*4|3(?:\s*7)+\s*5"
    r"|8(?:\s*>)*\s*<(?:\s*>)*\s*:|9(?:\s*>)*\s*=(?:\s*>)*\s*;)(?![\w.])"
)
# Symbols both sides can be compared on. Brackets, commas and bars are left out: big delimiters, math commas
# and evaluation bars come out of the text layer as other glyphs.
_OPS = set("=+-/:'∈∼<>≤≥≈∝±∂∇∑∏∫∞")
_CONFUSABLE_SPRINGER = {"0": "0'", "'": "0'", "ε": "ε∈", "∈": "ε∈"}

_ENV = re.compile(
    r"\\begin\{(?:array|alignat\*?)\}\s*\{(?:[^{}]|\{[^{}]*\})*\}"
    r"|\\(?:begin|end)\{(?:equation|align|aligned|alignat|gather|gathered|split|multline|eqnarray|array|displaymath)\*?\}"
)
_NUM_WRAPPED = re.compile(r"\\(?:text|mathrm|textrm|rm|mbox)\s*\{\s*~?\s*(\(\s*(?:\d\s*){1,3}[a-z]?\s*\))\s*\}")
_SPACE_CMDS = r"(?:\\q?quad|\\hfill|&|~|\\[,;:! ])"


def transcribe(model: str, pdf_path: str, block: dict) -> str:
    """The vision model's LaTeX for an equation block (raw answer; cached by ollama.chat)."""
    x0, y0, x1, y1 = block["bbox"]
    png = crop_png(pdf_path, block["page"], [x0 - 3, y0 - 3, x1 + 3, y1 + 3], scale=3.0)
    return ollama.chat(model, [{"role": "system", "content": OCR_SYSTEM}, {"role": "user", "content": "Transcribe this equation."}],
                       images=[png], num_predict=700)


def _number_pattern(number: str | None) -> str:
    if number:
        return r"\s*".join(re.escape(c) for c in number)
    return r"(?:\d\s*){1,3}[a-z]?"


def _strip_number(s: str, number: str | None) -> str:
    s = re.sub(r"\\(?:tag|label|eqno|leqno)\*?\s*(?:\{[^{}]*\}|\(?\d{1,3}[a-z]?\)?)|\\(?:nonumber|notag)\b", " ", s)
    s = _NUM_WRAPPED.sub(lambda m: " " + m.group(1), s)
    num = _number_pattern(number)
    # Set off by spacing or alignment, anywhere (a multi-line equation's number can sit on a middle line)...
    s = re.sub(_SPACE_CMDS + r"+\s*\(\s*" + num + r"\s*\)", " ", s)
    # ...or at the very end without spacing, only when it is the number the parser found (f(2) stays).
    if number:
        s = re.sub(r"\(\s*" + num + r"\s*\)\s*[.,]?\s*$", "", s)
    return s


def _cut_label(s: str, pdf_text: str) -> str:
    """Drop a word label the model kept ("\\mathrm{M o m e n t u m :}", "\\textbf{Continuity}\\!:"), also inside the
    braces some models wrap each line in, when the PDF shows that label before the equation."""
    head = re.match(r"\s*(?:\{\s*)*", s).end()
    body = re.sub(r"^\\(?:textbf|mathbf|textit|mathit|textrm|textsf|mathsf|mbox)\s*\{", r"\\text{", s[head:])
    label, rest = split_label(body, pdf_text)
    if not label:
        return s
    rest = re.sub(r"^(?:\s|\\[,;:!]|\\colon\b|:|\\q?quad\b)+", "", rest)
    return s[:head] + rest


def clean_transcription(raw: str, number: str | None, pdf_text: str) -> str:
    """The model's answer → the equation's LaTeX, cleaned like the parser's: no fences or delimiters, no alignment
    environments, line breaks or equation number, no word label."""
    s = raw.strip()
    m = re.search(r"```(?:latex|tex|math)?\s*(.*?)(?:```|$)", s, re.S)
    if m:
        s = m.group(1)
    for pat in (r"\$\$(.*?)\$\$", r"\\\[(.*?)\\\]", r"\\\((.*?)\\\)"):
        m = re.search(pat, s, re.S)
        if m and m.group(1).strip():
            s = m.group(1)
            break
    s = s.strip().strip("$").strip()
    s = s.replace("\\pmb", "\\boldsymbol")  # MathJax draws \pmb's argument twice, so it would never compare equal
    s = _ENV.sub(" ", s)
    s = _strip_number(s, number)
    s = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", s)
    s = re.sub(r"(?<!\\)&", " ", s).replace("\n", " ")
    s = _cut_label(s, pdf_text)
    s = re.sub(r"[.,;]\s*((?:\}\s*)*)$", r"\g<1>", s.rstrip())  # the sentence's period, also inside wrapping braces
    s = clean_latex(s)
    # "\mathrm { h i g h }" became "\mathrm { \mathrm{high} }" when the letters were joined.
    return re.sub(r"\\(?:mathrm|text|textrm|operatorname)\s*\{\s*(\\mathrm\{[A-Za-z]+\})\s*\}", r"\g<1>", s)


def is_springer(blocks: list[dict]) -> bool:
    """Springer Nature glyph encoding in the equations' text layer (as the builder decides for prose)."""
    return sum((b.get("text") or "").count(g) for b in blocks if b["type"] == "equation" for g in _SPRINGER_HINTS) >= 6


def _symbols(chars: str, springer: bool) -> list[str]:
    out = []
    for c in unicodedata.normalize("NFKC", chars):  # ligatures, ², µ, ϵ → ε
        c = VARIANTS.get(c, c)
        if c.isalnum() or c in _OPS:
            out.append(_CONFUSABLE_SPRINGER.get(c, c) if springer else c)
    return out


def text_symbols(text: str, label: str | None, number: str | None, springer: bool) -> Counter:
    """The symbols printed in an equation's region, from the PDF text layer, without its label and number."""
    t = text or ""
    if label:
        t = re.sub(r"^\s*" + r"\s*".join(re.escape(c) for c in label if not c.isspace()) + r"\s*:?", "", t, flags=re.I)
    t = re.sub(r"[(ð]\s*" + _number_pattern(number) + r"\s*[)Þ]\s*[.,;]?\s*$", "", t.rstrip())
    # A radical's bar comes out as "ffiffiffi..."; in Springer PDFs the radical sign itself is a lone "r" after the
    # radicand. Bags don't care which lone "r" goes, so drop the first one after each bar.
    parts = re.split(r"f*(?:ffi){2,}f*", t)
    if springer:
        parts[1:] = [re.sub(r"(?<!\S)r(?!\S)", " ", p, count=1) for p in parts[1:]]
    t = " ".join(parts)
    t = _TALL_DELIMS.sub(" ", t)
    if springer:
        t = re.sub("\x00\\s*\x01", " ", t).translate(_SPRINGER_EQ)
        t = re.sub(r"(?<![\d:])0:(\d)", r"0.\g<1>", t)  # decimal points set as colons
    return Counter(_symbols(t, springer))


def latex_symbols(latex: str, springer: bool) -> Counter | None:
    """The same bag for a LaTeX reading (None when MathJax can't parse it)."""
    ml, _err = to_mathml(latex)
    if not ml:
        return None
    try:
        tokens = canon_tokens(ET.fromstring(ml))
    except ET.ParseError:
        return None
    return Counter(s for t in tokens if t[:2] in ("i:", "n:", "o:") for s in _symbols(t[2:], springer))


def distance(a: Counter, b: Counter) -> int:
    return sum((a - b).values()) + sum((b - a).values())


def decide(parser: str, vision: str | None, block: dict, springer: bool) -> dict:
    """Pick the source LaTeX: {"status", "used", "parser", "vision", "agree", "off": {"parser": n, "vision": n}}.

    status: agree (the two readings match) · page (they differ; the text layer picked one) · disputed (they differ
    and the text layer can't tell: the parser's is kept) · vision_only (the parser's reading is unusable; the vision
    reading matches the text layer) · single (no usable second reading) · unreadable (neither reading is usable)."""
    rec: dict = {"parser": parser, "vision": vision, "agree": None, "off": None}
    tb = text_symbols(block.get("text") or "", block.get("eq_label"), block.get("eq_number"), springer)
    ps = latex_symbols(parser, springer) if latex_has_content(parser) else None
    vs = latex_symbols(vision, springer) if vision and latex_has_content(vision) else None
    if ps is None and vs is None:
        return {**rec, "status": "unreadable", "used": "parser"}
    if vs is None:
        return {**rec, "status": "single", "used": "parser"}
    off_v = distance(vs, tb)
    if ps is None:
        # Only the vision model could read it: use that only if the page's own glyphs back it up.
        rec["off"] = {"parser": None, "vision": off_v}
        ok = sum(tb.values()) >= 3 and off_v <= max(2, 0.2 * sum(tb.values()))
        return {**rec, "status": "vision_only" if ok else "unreadable", "used": "vision" if ok else "parser"}
    rec["agree"] = compare(parser, vision).status
    off_p = distance(ps, tb)
    rec["off"] = {"parser": off_p, "vision": off_v}
    if rec["agree"] == "match":
        return {**rec, "status": "agree", "used": "parser"}
    if sum(tb.values()) >= 3 and off_v != off_p:
        return {**rec, "status": "page", "used": "vision" if off_v < off_p else "parser"}
    # Same symbols means only the structure differs (grouping, what a root or fraction covers): no text layer can tell.
    return {**rec, "status": "disputed", "used": "parser", "same_symbols": ps == vs}
