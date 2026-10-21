"""SciSpeech-Bench data collection: display equations from arXiv LaTeX sources (ground truth = source LaTeX).

Finds open arXiv papers through OpenAlex (polymers/materials first, then physics, chemistry, math),
downloads TeX sources politely (>= 3 s between arXiv requests, descriptive User-Agent), expands simple
\\newcommand macros, extracts display equations, keeps the ones MathJax can render, and writes
bench/data/papers.json + bench/data/equations.jsonl. Raw sources are cached in bench/raw/ (gitignored).

Usage: uv run --directory backend python ../bench/scripts/collect.py [--target 220]
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import random
import re
import sys
import tarfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench"
RAW = BENCH / "raw"
DATA = BENCH / "data"
UA = "SciReader-SciSpeechBench/0.1 (open benchmark of spoken math; https://github.com/Shmiggly/SciReader)"
ARXIV_SOURCE = "S4306400194"

QUERIES = [
    ("polymers", "polymer machine learning property prediction"),
    ("polymers", "polymer additive manufacturing 3D printing"),
    ("polymers", "photopolymerization kinetics resin"),
    ("polymers", "polymer molecular dynamics mechanical properties"),
    ("materials", "hydrogel mechanics constitutive model"),
    ("materials", "materials informatics graph neural network crystal"),
    ("physics", "fluid dynamics instability analytical model"),
    ("physics", "quantum many-body Hamiltonian"),
    ("chemistry", "electrochemistry kinetics battery electrolyte model"),
    ("chemistry", "density functional theory reaction energetics"),
    ("math", "partial differential equations existence uniqueness"),
    ("math", "stochastic processes Gaussian process regression theory"),
]
SAMPLES = [("polymers", "2209.13557"), ("polymers", "2307.10139"), ("polymers", "2511.23306"), ("polymers", "2512.08896")]

ENV = re.compile(
    r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|eqnarray\*?|displaymath|flalign\*?)\}(.*?)\\end\{\1\}", re.S
)
BRACKET = re.compile(r"(?<!\\)\\\[(.*?)\\\]", re.S)
DOLLARS = re.compile(r"(?<!\\)\$\$(.*?)\$\$", re.S)
NEWCMD = re.compile(r"\\(?:re)?newcommand\*?\s*\{?\\([A-Za-z]+)\}?\s*(?:\[(\d)\])?\s*(?:\[[^\]]*\])?\s*\{")
DEF = re.compile(r"\\def\\([A-Za-z]+)\s*\{")


def _balanced(s: str, start: int) -> int:
    """Index just past the brace group that opens at s[start-1] == '{'."""
    depth = 1
    i = start
    while i < len(s) and depth:
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
        i += 1
    return i


def macros(tex: str) -> dict[str, tuple[int, str]]:
    out = {}
    for rx in (NEWCMD, DEF):
        for m in rx.finditer(tex):
            end = _balanced(tex, m.end())
            body = tex[m.end(): end - 1]
            nargs = int(m.group(2)) if rx is NEWCMD and m.group(2) else 0
            out[m.group(1)] = (nargs, body)
    return out


def expand(latex: str, defs: dict[str, tuple[int, str]], depth: int = 0) -> str:
    if depth > 4 or not defs:
        return latex
    def repl_all(s: str) -> str:
        i = 0
        out = []
        while i < len(s):
            m = re.match(r"\\([A-Za-z]+)", s[i:])
            if m and m.group(1) in defs:
                name = m.group(1)
                nargs, body = defs[name]
                j = i + m.end()
                args = []
                for _ in range(nargs):
                    while j < len(s) and s[j] == " ":
                        j += 1
                    if j < len(s) and s[j] == "{":
                        k = _balanced(s, j + 1)
                        args.append(s[j + 1: k - 1])
                        j = k
                    elif j < len(s):
                        args.append(s[j])
                        j += 1
                for n, a in enumerate(args, 1):
                    body = body.replace(f"#{n}", a)
                out.append("{" + body + "}" if nargs else body + (" " if j < len(s) and s[j].isalpha() else ""))
                i = j
            elif m:
                out.append(m.group(0))
                i += m.end()
            else:
                out.append(s[i])
                i += 1
        return "".join(out)
    new = repl_all(latex)
    return new if new == latex else expand(new, defs, depth + 1)


def clean(eq: str) -> list[str]:
    eq = re.sub(r"(?<!\\)%.*", "", eq)
    eq = re.sub(r"\\(label|tag\*?|eqref|ref)\{[^}]*\}", "", eq)
    eq = re.sub(r"\\(nonumber|notag|displaystyle|qquad|quad|nonumber)\b", " ", eq)
    eq = re.sub(r"\\begin\{(split|aligned|cases)\}|\\end\{(split|aligned|cases)\}", lambda m: m.group(0) if "cases" in m.group(0) else " ", eq)
    rows = [eq] if "cases" in eq else re.split(r"\\\\(?:\[[^\]]*\])?", eq)
    out = []
    for r in rows:
        r = r.replace("&", " ") if "cases" not in r else r
        r = re.sub(r"\s+", " ", r).strip().rstrip(",.;").strip()
        if 12 <= len(re.sub(r"\s", "", r)) <= 260 and "=" in r or re.search(r"\\(le|ge|approx|propto|sim)\b", r):
            out.append(r)
    return out


def openalex(query: str, client: httpx.Client) -> list[dict]:
    r = client.get("https://api.openalex.org/works", params={
        "search": query, "filter": f"locations.source.id:{ARXIV_SOURCE},publication_year:2019-2026",
        "per-page": 25, "select": "id,title,ids,locations,publication_year"}, timeout=60)
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []):
        arx = None
        lic = None
        for loc in w.get("locations") or []:
            url = (loc.get("landing_page_url") or "") + " " + (loc.get("pdf_url") or "")
            m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", url)
            if m:
                arx = m.group(1)
                lic = loc.get("license") or lic
        if arx:
            out.append({"arxiv": arx, "title": w.get("title"), "license": lic, "year": w.get("publication_year")})
    return out


class Arxiv:
    def __init__(self) -> None:
        self.client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=120)
        self.last = 0.0

    def source(self, arxiv_id: str) -> bytes | None:
        RAW.mkdir(parents=True, exist_ok=True)
        cache = RAW / f"{arxiv_id}.src"
        if cache.exists():
            data = cache.read_bytes()
            return data or None
        wait = 3.2 - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        r = self.client.get(f"https://arxiv.org/src/{arxiv_id}")
        data = r.content if r.status_code == 200 and not r.content.startswith(b"%PDF") else b""
        cache.write_bytes(data)
        return data or None


def tex_files(blob: bytes) -> str:
    try:
        raw = gzip.decompress(blob)
    except OSError:
        raw = blob
    try:
        with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
            parts = []
            for m in tf.getmembers():
                if m.isfile() and m.name.endswith((".tex", ".sty")) and m.size < 3_000_000:
                    parts.append(tf.extractfile(m).read().decode("utf-8", "replace"))
            return "\n".join(parts)
    except tarfile.TarError:
        return raw.decode("utf-8", "replace")


def extract(tex: str) -> list[str]:
    defs = macros(tex)
    body = tex.split("\\begin{document}", 1)[-1]
    found = []
    for rx, grp in ((ENV, 2), (BRACKET, 1), (DOLLARS, 1)):
        for m in rx.finditer(body):
            found.extend(clean(expand(m.group(grp), defs)))
    seen, out = set(), []
    for e in found:
        k = re.sub(r"\s", "", e)
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=220)
    ap.add_argument("--per-paper", type=int, default=12)
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    from scireader.speech.math_speech import MathSpeech

    ms = MathSpeech(ROOT / "tools" / "math-speech")
    DATA.mkdir(parents=True, exist_ok=True)
    cand_path = BENCH / "raw" / "candidates.json"
    RAW.mkdir(parents=True, exist_ok=True)
    if cand_path.exists():
        cands = json.loads(cand_path.read_text(encoding="utf-8"))
    else:
        cands = [{"field": f, "arxiv": a, "title": None, "license": None} for f, a in SAMPLES]
        with httpx.Client(headers={"User-Agent": UA}) as c:
            for field, q in QUERIES:
                try:
                    for w in openalex(q, c):
                        cands.append({"field": field, **w})
                except httpx.HTTPError as exc:
                    print("openalex failed:", q, exc, flush=True)
                time.sleep(1)
        cand_path.write_text(json.dumps(cands, indent=1), encoding="utf-8")
    seen_ids: set[str] = set()
    ordered = []
    for c in cands:
        if c["arxiv"] not in seen_ids:
            seen_ids.add(c["arxiv"])
            ordered.append(c)
    rng = random.Random(7)
    ax = Arxiv()
    papers, items = [], []
    per_field = {"polymers": 0, "materials": 0, "physics": 0, "chemistry": 0, "math": 0}
    caps = {"polymers": 70, "materials": 45, "physics": 40, "chemistry": 35, "math": 30}
    for c in ordered:
        if len(items) >= args.target:
            break
        if per_field.get(c["field"], 0) >= caps.get(c["field"], 30):
            continue
        blob = ax.source(c["arxiv"])
        if not blob:
            print(f"skip {c['arxiv']}: no TeX source", flush=True)
            continue
        eqs = extract(tex_files(blob))
        valid = []
        for e in eqs:
            res = ms.run(e, display=True, speech=True)
            if res.get("error") or not res.get("speech"):
                continue
            valid.append((e, res["speech"]))
        rng.shuffle(valid)
        take = valid[: min(args.per_paper, caps[c["field"]] - per_field[c["field"]], args.target - len(items))]
        if not take:
            continue
        papers.append({"arxiv": c["arxiv"], "field": c["field"], "title": c.get("title"), "license": c.get("license"),
                       "url": f"https://arxiv.org/abs/{c['arxiv']}", "n_equations": len(take), "n_found": len(eqs)})
        for k, (e, sre) in enumerate(take):
            items.append({"id": f"{c['arxiv']}#{k}", "arxiv": c["arxiv"], "field": c["field"], "latex": e})
        per_field[c["field"]] += len(take)
        print(f"{c['arxiv']} [{c['field']}] {len(eqs)} found, {len(valid)} valid, took {len(take)} -> total {len(items)}", flush=True)
    (DATA / "papers.json").write_text(json.dumps(papers, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(DATA / "equations.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"DONE {len(items)} equations from {len(papers)} papers; per field {per_field}", flush=True)
    ms.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
