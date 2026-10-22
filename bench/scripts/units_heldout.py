"""SciSpeech-Bench, units and chemistry by sound on held-out text (snippets we did not write).

The original units test (units.py) uses 99 snippets written by the people who wrote the normalizer. This one
samples snippets automatically from the PDF text layer of the benchmark papers that are neither app samples
nor math papers (reference lists cut off, since SciReader skips them): a number followed by something that
is not an English word (a unit), or a chemical formula. Reference readings are written by phi4:14b (a model
the normalizer never sees); clear errors in them are corrected by hand in `units_heldout_fixes.json`, judged
from the snippet and the reference only, before scoring. Chemical formulas count as right in either
convention, compound name ("lithium carbonate") or symbols ("L I 2 C O 3"), for both readers. Scoring is the
same as units.py: phoneme distance with the voice's own G2P; > 0.25 counts as mispronounced.

Two samples: `dev` (seed 2026) was used to find and fix normalizer gaps; `test` (seed 2027, disjoint from
dev) was scored once, after the fixes.

Usage: uv run --directory backend python ../bench/scripts/units_heldout.py test --golds   (write references)
       uv run --directory backend python ../bench/scripts/units_heldout.py test           (score)
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "bench" / "scripts"))

from units import edit  # noqa: E402

APP_SAMPLES = {"2209.13557", "2307.10139", "2511.23306", "2512.08896"}
PDF_DIR = ROOT / "bench" / "raw" / "pdf"
PER_PAPER = 5
JUDGE = "phi4:14b"

ELEMENTS = set("""H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr
Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re
Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu""".split())
SI_LETTERS = set("KVAWJNTCFLsmgh")
LOWER_UNITS = {"min", "mol", "atm", "rpm", "ppm", "ppb", "sec", "hrs", "wt", "vol", "cal", "kcal", "mmol", "nmol",
               "mbar", "kbar"}
SEEDS = {"dev": 2026, "test": 2027}
NUM = r"(?<![\w.])\d+(?:\.\d+)?(?:\s?[×x]\s?10[−-]?\d+)?"
UNIT = r"(?:[A-Za-zµμΩÅ°%][A-Za-zµμΩÅ°]{0,5}(?:[−-]?[123])?)"
UNIT_EXPR = re.compile(NUM + r"\s?(" + UNIT + r"(?:\s?[/·⋅]\s?" + UNIT + r"|\s" + UNIT + r"[−-][123]){0,3})(?![\w])")
FORMULA = re.compile(r"(?<![\w-])((?:[A-Z][a-z]?\d{0,3}){2,6})(?![\w-])")

PROMPT = (
    "You read scientific text aloud to a scientist. Rewrite the snippet exactly as it should be spoken: say "
    "unit symbols, chemical formulas, symbols and abbreviations the way a scientist says them, in words "
    "(for example 'MPa' -> 'megapascals', 'H2O' -> 'H 2 O'). Keep digits as digits and keep every other "
    "word unchanged. Output only the rewritten snippet."
)


def fetch(aid: str) -> Path | None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    p = PDF_DIR / f"{aid}.pdf"
    if not p.exists():
        # httpx trusts certifi; urllib's default context on Windows took the leaked eMudhra CAs (Oct 2026)
        try:
            r = httpx.get(f"https://arxiv.org/pdf/{aid}", headers={"User-Agent": "SciSpeech-Bench"},
                          follow_redirects=True, timeout=60)
            r.raise_for_status()
            p.write_bytes(r.content)
        except Exception as exc:  # noqa: BLE001
            print("  fetch failed", aid, exc)
            return None
    return p


def pdf_text(path: Path) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        text = " ".join(page.get_textpage().get_text_range() for page in pdf)
    finally:
        pdf.close()
    text = re.sub(r"\s+", " ", text)
    refs = list(re.finditer(r"\b(?:References|REFERENCES|Bibliography)\b", text))
    return text[: refs[-1].start()] if refs and refs[-1].start() > len(text) // 2 else text


def candidates(text: str, known) -> list[tuple[str, str]]:
    out = []
    for m in UNIT_EXPR.finditer(text):
        unit = m.group(1)
        first = re.match(r"[A-Za-zµμΩÅ°%]+", unit)
        token = first.group(0) if first else unit
        if len(token) == 1 and token.isalpha() and token not in SI_LETTERS:
            continue
        if len(token) > 1 and token.isalpha() and known(token):
            continue  # an English word ("3 times"), not a unit
        if len(token) >= 3 and token.islower() and token not in LOWER_UNITS:
            continue  # a word split by a line number ("41 eling"), not a unit
        if token in ("st", "nd", "rd", "th") or re.search(r"\b(?:Fig|Figs|Figure|Table|Eq|Eqs|Sec|Section|Ref)\.?\s*$", text[max(0, m.start() - 12):m.start()]):
            continue  # ordinals and panel references ("Figure 1A") are not units
        out.append(("units", m.start(), m.end()))
    for m in FORMULA.finditer(text):
        f = m.group(1)
        parts = re.findall(r"[A-Z][a-z]?\d{0,3}", f)
        postcode = re.match(r"\s\d[A-Z]{2}\b", text[m.end():m.end() + 5])  # "CB3 0WA"
        if any(ch.isdigit() for ch in f) and all(re.sub(r"\d", "", x) in ELEMENTS for x in parts) and not postcode:
            out.append(("chem", m.start(), m.end()))
    snippets = []
    for cat, a, b in out:
        left = " ".join(text[:a].split(" ")[-3:])
        right = " ".join(text[b:].split(" ")[:2])
        snip = re.sub(r"\s+", " ", f"{left}{text[a:b]} {right}").strip()
        # Prose only: at least two English words around the match, no table rows or math typesetting.
        prose = sum(1 for w in re.findall(r"[A-Za-z]{3,}", f"{left} {right}") if known(w))
        if (8 <= len(snip) <= 90 and prose >= 2
                and not re.search(r"https?\s?:|://|doi|arXiv|\[\d|[∥∇∂∑∫⟨⟩⩽#]|[a-z]- \d|Switzerland|University", snip)
                and len(re.findall(r"\d+(?:\.\d+)?", snip)) <= 3):
            snippets.append((cat, snip))
    return snippets


def spell_formulas(text: str) -> str:
    """The symbol convention for chemistry: "Li2CO3" -> "L I 2 C O 3"."""
    def spell(m: re.Match) -> str:
        parts = re.findall(r"[A-Z][a-z]?|\d+", m.group(1))
        if not all(x.isdigit() or x in ELEMENTS for x in parts):
            return m.group(0)
        return " ".join(" ".join(x.upper()) if not x.isdigit() else x for x in parts)
    return FORMULA.sub(spell, text)


def sample(name: str) -> list[dict]:
    from scireader.speech.review import _known

    papers = [p for p in json.loads((ROOT / "bench" / "data" / "papers.json").read_text(encoding="utf-8"))
              if p["arxiv"] not in APP_SAMPLES and p["field"] != "math"]
    seen = set()
    for other in SEEDS:
        f = ROOT / "bench" / "data" / f"units_heldout_{other}.jsonl"
        if other != name and f.exists():
            seen |= {json.loads(line)["text"] for line in f.read_text(encoding="utf-8").splitlines() if line.strip()}
    rng = random.Random(SEEDS[name])
    picked = []
    for p in papers:
        path = fetch(p["arxiv"])
        if path is None:
            continue
        cands = [c for c in dict.fromkeys(candidates(pdf_text(path), _known)) if c[1] not in seen]
        rng.shuffle(cands)
        chem = [c for c in cands if c[0] == "chem"][:2]
        units = [c for c in cands if c[0] == "units"][: PER_PAPER - len(chem)]
        for cat, snip in chem + units:
            picked.append({"arxiv": p["arxiv"], "field": p["field"], "category": cat, "text": snip})
    return picked


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "test"
    data = ROOT / "bench" / "data" / f"units_heldout_{name}.jsonl"
    fixes_path = ROOT / "bench" / "data" / "units_heldout_fixes.json"
    fixes = json.loads(fixes_path.read_text(encoding="utf-8")) if fixes_path.exists() else {}

    if "--golds" in sys.argv:
        from scireader.llm import ollama

        picked = sample(name)
        for it in picked:
            it["gold_llm"] = ollama.chat(JUDGE, [{"role": "system", "content": PROMPT},
                                                 {"role": "user", "content": it["text"]}],
                                         num_predict=120).strip().strip('"')
        ollama.unload(JUDGE)
        data.write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in picked), encoding="utf-8")
        for i, it in enumerate(picked):  # for the reference review, before any scoring
            print(f"{i:2} {it['text']}  =>  {it['gold_llm']}")
        return 0

    from misaki import en, espeak

    from scireader.speech.pipeline import base_lexicon, speak

    picked = [json.loads(line) for line in data.read_text(encoding="utf-8").splitlines() if line.strip()]
    picked = [it for it in picked if not (it["text"] in fixes and fixes[it["text"]] is None)]
    g2p = en.G2P(trf=False, british=False, fallback=espeak.EspeakFallback(british=False))

    def ph(text: str) -> str:
        p, _ = g2p(text)
        return p.replace(" ", "")

    for it in picked:
        it["gold"] = fixes.get(it["text"], it.get("gold") or it["gold_llm"])
        golds = [it["gold"]] + ([spell_formulas(it["text"])] if it["category"] == "chem" else [])
        ours = speak(it["text"], lexicon=base_lexicon()).spoken  # the base list, not a user's own dataset
        p_raw, p_ours = ph(it["text"]), ph(ours)
        p_golds = [ph(g) for g in golds]
        it["scireader"] = ours
        it["dist_raw"] = round(min(edit(p_raw, g) / max(1, len(g)) for g in p_golds), 3)
        it["dist_scireader"] = round(min(edit(p_ours, g) / max(1, len(g)) for g in p_golds), 3)
        it["wrong_raw"], it["wrong_scireader"] = it["dist_raw"] > 0.25, it["dist_scireader"] > 0.25

    with open(ROOT / "bench" / "results" / f"units_heldout_{name}.jsonl", "w", encoding="utf-8") as f:
        for it in picked:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    n = len(picked)
    wr = sum(it["wrong_raw"] for it in picked)
    wo = sum(it["wrong_scireader"] for it in picked)
    print(f"{name}: {n} held-out snippets: generic reader mispronounces {wr} ({wr / max(1, n):.0%}), "
          f"SciReader {wo} ({wo / max(1, n):.0%})")
    for it in picked:
        if it["wrong_scireader"] or it["wrong_raw"]:
            flag = ("R" if it["wrong_raw"] else ".") + ("S" if it["wrong_scireader"] else ".")
            print(f"  {flag} {it['text']} | ref: {it['gold']} | ours: {it['scireader']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
