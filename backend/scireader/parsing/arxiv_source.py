"""arXiv source mode: use the paper's own LaTeX for its display equations instead of OCR.

Fetches https://arxiv.org/src/<id> once (cached next to the document), extracts display equations with
simple macro expansion, aligns them in order to the parsed equation blocks by canonical-MathML token
similarity (allowing a block to match up to three consecutive rows of an align environment), and
replaces the block LaTeX. The OCR LaTeX is kept as `latex_ocr`.
"""

from __future__ import annotations

import difflib
import gzip
import io
import re
import tarfile
import xml.etree.ElementTree as ET

import httpx

from ..llm.verify import canon_tokens, to_mathml
from ..speech.math_speech import get_math_speech

UA = "SciReader/0.1 (open-source paper reader; https://github.com/Shmiggly/SciReader)"
ENV = re.compile(r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|eqnarray\*?|displaymath|flalign\*?)\}(.*?)\\end\{\1\}", re.S)
BRACKET = re.compile(r"(?<!\\)\\\[(.*?)\\\]", re.S)
DOLLARS = re.compile(r"(?<!\\)\$\$(.*?)\$\$", re.S)
NEWCMD = re.compile(r"\\(?:re)?newcommand\*?\s*\{?\\([A-Za-z]+)\}?\s*(?:\[(\d)\])?\s*(?:\[[^\]]*\])?\s*\{")
DEF = re.compile(r"\\def\\([A-Za-z]+)\s*\{")


def fetch_tex(arxiv_id: str) -> str | None:
    r = httpx.get(f"https://arxiv.org/src/{arxiv_id}", headers={"User-Agent": UA}, follow_redirects=True, timeout=120)
    if r.status_code != 200 or r.content.startswith(b"%PDF"):
        return None
    blob = r.content
    try:
        raw = gzip.decompress(blob)
    except OSError:
        raw = blob
    try:
        with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
            return "\n".join(
                tf.extractfile(m).read().decode("utf-8", "replace")
                for m in tf.getmembers() if m.isfile() and m.name.endswith((".tex", ".sty")) and m.size < 3_000_000
            )
    except tarfile.TarError:
        return raw.decode("utf-8", "replace")


def _balanced(s: str, start: int) -> int:
    depth, i = 1, start
    while i < len(s) and depth:
        if s[i] == "\\":
            i += 2
            continue
        depth += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    return i


def _macros(tex: str) -> dict[str, tuple[int, str]]:
    out = {}
    for rx in (NEWCMD, DEF):
        for m in rx.finditer(tex):
            end = _balanced(tex, m.end())
            out[m.group(1)] = (int(m.group(2)) if rx is NEWCMD and m.group(2) else 0, tex[m.end(): end - 1])
    return out


def _expand(latex: str, defs: dict[str, tuple[int, str]], depth: int = 0) -> str:
    if depth > 4 or not defs:
        return latex
    out, i = [], 0
    while i < len(latex):
        m = re.match(r"\\([A-Za-z]+)", latex[i:])
        if m and m.group(1) in defs:
            nargs, body = defs[m.group(1)]
            j = i + m.end()
            for n in range(1, nargs + 1):
                while j < len(latex) and latex[j] == " ":
                    j += 1
                if j < len(latex) and latex[j] == "{":
                    k = _balanced(latex, j + 1)
                    body = body.replace(f"#{n}", latex[j + 1: k - 1])
                    j = k
                elif j < len(latex):
                    body = body.replace(f"#{n}", latex[j])
                    j += 1
            out.append("{" + body + "}" if nargs else body + (" " if j < len(latex) and latex[j].isalpha() else ""))
            i = j
        elif m:
            out.append(m.group(0))
            i += m.end()
        else:
            out.append(latex[i])
            i += 1
    new = "".join(out)
    return new if new == latex else _expand(new, defs, depth + 1)


def source_equations(tex: str) -> list[str]:
    """Display-equation rows in document order (labels and alignment removed)."""
    defs = _macros(tex)
    body = tex.split("\\begin{document}", 1)[-1]
    spans = []
    for rx, grp in ((ENV, 2), (BRACKET, 1), (DOLLARS, 1)):
        for m in rx.finditer(body):
            spans.append((m.start(), m.group(grp)))
    rows = []
    for _, eq in sorted(spans):
        eq = re.sub(r"(?<!\\)%.*", "", _expand(eq, defs))
        eq = re.sub(r"\\(label|tag\*?)\{[^}]*\}|\\(nonumber|notag)\b", " ", eq)
        eq = re.sub(r"\\begin\{(split|aligned)\}|\\end\{(split|aligned)\}", " ", eq)
        parts = [eq] if "\\begin{cases}" in eq or "array" in eq else re.split(r"\\\\(?:\[[^\]]*\])?", eq)
        for r in parts:
            r = re.sub(r"\s+", " ", r.replace("&", " ") if "cases" not in r else r).strip().rstrip(",.;").strip()
            if len(r) >= 3:
                rows.append(r)
    return rows


def _tokens(latex: str) -> list[str] | None:
    ml, _ = to_mathml(latex)
    if not ml:
        return None
    try:
        return canon_tokens(ET.fromstring(ml), relaxed=True)
    except ET.ParseError:
        return None


def align(blocks: list[dict], rows: list[str]) -> dict[str, str]:
    """block id → source LaTeX, matched in order."""
    row_tokens = [_tokens(r) for r in rows]
    out: dict[str, str] = {}
    start = 0
    for b in blocks:
        ocr = _tokens(b.get("latex") or "")
        if not ocr:
            continue
        best = (0.0, None, None)
        for i in range(start, min(len(rows), start + 40)):
            for span in (1, 2, 3):
                toks: list[str] = []
                ok = True
                for k in range(i, min(len(rows), i + span)):
                    if row_tokens[k] is None:
                        ok = False
                        break
                    toks += row_tokens[k]
                if not ok or not toks:
                    continue
                r = difflib.SequenceMatcher(None, ocr, toks, autojunk=False).ratio()
                if r > best[0]:
                    best = (r, i, span)
        if best[1] is not None and best[0] >= 0.55:
            i, span = best[1], best[2]
            out[b["id"]] = " \\\\ ".join(rows[i: i + span]) if span > 1 else rows[i]
            start = i + span
    return out


def apply(doc: dict, mapping: dict[str, str]) -> int:
    math = get_math_speech()
    n = 0
    for b in doc["blocks"]:
        src = mapping.get(b["id"])
        if not src or b["type"] != "equation":
            continue
        speech = math.speak(src)
        if not speech:
            continue
        b.setdefault("latex_ocr", b.get("latex"))
        b["latex"] = src
        b["latex_source"] = "arxiv"
        b["speech_rules"] = speech
        number = b.get("eq_number")
        label = f"Equation {number}" if number else "Equation"
        for s in b["sentences"]:
            s["text"] = src
            s["spoken"] = f"{label}: {speech}."
        n += 1
    doc.setdefault("source_mode", {})["arxiv_equations"] = n
    return n
