"""SciSpeech-Bench, units and chemistry scored by sound.

For each snippet we phonemize three texts with the voice's own G2P (misaki, the phonemizer Kokoro uses;
runs offline without the model): (1) the raw text a generic reader would send, (2) SciReader's normalized
text, (3) a hand-checked correct reading. Score = phoneme edit distance to (3), normalized by its length.
A snippet counts as mispronounced when the normalized distance exceeds 0.25.

Usage: uv run --directory backend python ../bench/scripts/units.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# (category, text as printed in a paper, correct reading). Written for this benchmark; CC BY 4.0.
SNIPPETS = [
    ("units", "The band gap is 1.12 eV at 300 K.", "The band gap is 1.12 electron volts at 300 kelvin."),
    ("units", "a tensile strength of 48 MPa", "a tensile strength of 48 megapascals"),
    ("units", "a modulus of 2.4 GPa", "a modulus of 2.4 gigapascals"),
    ("units", "layers of 50 µm", "layers of 50 micrometers"),
    ("units", "a 405 nm laser", "a 405 nanometer laser"),
    ("units", "an intensity of 10 mW/cm²", "an intensity of 10 milliwatts per square centimeter"),
    ("units", "an intensity of 10 mW cm−2", "an intensity of 10 milliwatts per square centimeter"),
    ("units", "cured for 30 s", "cured for 30 seconds"),
    ("units", "annealed for 2 h at 80 °C", "annealed for 2 hours at 80 degrees Celsius"),
    ("units", "a viscosity of 350 mPa·s", "a viscosity of 350 millipascal seconds"),
    ("units", "a peak at 1720 cm−1", "a peak at 1720 inverse centimeters"),
    ("units", "a peak at 1720 cm⁻¹", "a peak at 1720 inverse centimeters"),
    ("units", "an activation energy of 85 kJ/mol", "an activation energy of 85 kilojoules per mole"),
    ("units", "an activation energy of 85 kJ mol−1", "an activation energy of 85 kilojoules per mole"),
    ("units", "a concentration of 0.5 mol L−1", "a concentration of 0.5 moles per liter"),
    ("units", "a 2 mM solution", "a 2 millimolar solution"),
    ("units", "spun at 3000 rpm", "spun at 3000 revolutions per minute"),
    ("units", "a frequency of 1 Hz", "a frequency of 1 hertz"),
    ("units", "at 10 kHz", "at 10 kilohertz"),
    ("units", "a 20 kV bias", "a 20 kilovolt bias"),
    ("units", "a current of 5 mA", "a current of 5 milliamperes"),
    ("units", "a 3 mm nozzle", "a 3 millimeter nozzle"),
    ("units", "a lattice constant of 5.43 Å", "a lattice constant of 5.43 angstroms"),
    ("units", "a molar mass of 700 g/mol", "a molar mass of 700 grams per mole"),
    ("units", "a molar mass of 12 kDa", "a molar mass of 12 kilodaltons"),
    ("units", "a heating rate of 10 K/min", "a heating rate of 10 kelvin per minute"),
    ("units", "an acceleration of 9.81 m s−2", "an acceleration of 9.81 meters per second squared"),
    ("units", "a speed of 5 mm/s", "a speed of 5 millimeters per second"),
    ("units", "a dose of 20 mJ/cm²", "a dose of 20 millijoules per square centimeter"),
    ("units", "a conductivity of 1.2 S/cm", "a conductivity of 1.2 siemens per centimeter"),
    ("units", "a density of 1.05 g/cm³", "a density of 1.05 grams per cubic centimeter"),
    ("units", "with 5 wt% photoinitiator", "with 5 weight percent photoinitiator"),
    ("units", "with 20 vol% filler", "with 20 volume percent filler"),
    ("units", "a shift of 3 meV", "a shift of 3 millielectron volts"),
    ("units", "a 100 µL droplet", "a 100 microliter droplet"),
    ("units", "a resistance of 10 kΩ", "a resistance of 10 kilohms"),
    ("units", "a strain rate of 0.01 s−1", "a strain rate of 0.01 per second"),
    ("units", "thermal conductivity of 0.2 W m−1 K−1", "thermal conductivity of 0.2 watts per meter per kelvin"),
    ("notation", "a rate of 1.2 × 10−3 s−1", "a rate of 1.2 times 10 to the minus 3 per second"),
    ("notation", "a value of 3.4 × 10⁵", "a value of 3.4 times 10 to the 5"),
    ("notation", "a diffusion coefficient of 2e-9", "a diffusion coefficient of 2 times 10 to the minus 9"),
    ("notation", "about 1.5×10^-6", "about 1.5 times 10 to the minus 6"),
    ("notation", "a yield of 85 ± 3%", "a yield of 85 plus or minus 3 percent"),
    ("notation", "Tg ≈ 45 °C", "T G approximately 45 degrees Celsius"),
    ("notation", "between 5–10 K", "between 5 to 10 kelvin"),
    ("notation", "at 20–30 °C", "at 20 to 30 degrees Celsius"),
    ("notation", "for x ≤ 0.5", "for x less than or equal to 0.5"),
    ("notation", "with r ≥ 2", "with r greater than or equal to 2"),
    ("notation", "where σ ∝ T²", "where sigma proportional to T squared"),
    ("notation", "a ratio of ~3", "a ratio of about 3"),
    ("greek", "the shear rate γ̇", "the shear rate gamma dot"),
    ("greek", "the conversion α", "the conversion alpha"),
    ("greek", "the viscosity η", "the viscosity eta"),
    ("greek", "the surface tension σ", "the surface tension sigma"),
    ("greek", "a wavelength λ", "a wavelength lambda"),
    ("greek", "the strain ε", "the strain epsilon"),
    ("greek", "the angle θ", "the angle theta"),
    ("greek", "the change ΔH", "the change delta H"),
    ("greek", "the density ρ", "the density rho"),
    ("greek", "the time constant τ", "the time constant tau"),
    ("chem", "dissolved in H₂O", "dissolved in H 2 O"),
    ("chem", "dissolved in H2O", "dissolved in H 2 O"),
    ("chem", "under CO₂", "under C O 2"),
    ("chem", "TiO2 nanoparticles", "T I O 2 nanoparticles"),
    ("chem", "SiO₂ filler", "S I O 2 filler"),
    ("chem", "Fe₂O₃ particles", "F E 2 O 3 particles"),
    ("chem", "the NH₄⁺ ion", "the N H 4 plus ion"),
    ("chem", "Ca²⁺ crosslinking", "C A 2 plus crosslinking"),
    ("chem", "a ¹³C NMR spectrum", "a carbon 13 N M R spectrum"),
    ("chem", "in CH₂Cl₂", "in C H 2 C L 2"),
    ("chem", "ZnO nanorods", "Z N O nanorods"),
    ("chem", "Al₂O₃ substrate", "A L 2 O 3 substrate"),
    ("chem", "NaCl solution", "N A C L solution"),
    ("chem", "a Si wafer", "a silicon wafer"),
    ("chem", "Au nanoparticles", "gold nanoparticles"),
    ("polymers", "PEGDA hydrogels", "peg-dah hydrogels"),
    ("polymers", "a Tg of 60 °C", "a T G of 60 degrees Celsius"),
    ("polymers", "PA12 powder", "P A twelve powder"),
    ("polymers", "PLA filament", "P L A filament"),
    ("polymers", "PETG parts", "P E T G parts"),
    ("polymers", "TPU lattices", "T P U lattices"),
    ("polymers", "PDMS molds", "P D M S molds"),
    ("polymers", "PEEK implants", "P E E K implants"),
    ("polymers", "printed by DLP", "printed by D L P"),
    ("polymers", "printed by FDM", "printed by F D M"),
    ("polymers", "measured by DSC", "measured by D S C"),
    ("polymers", "measured by TGA", "measured by T G A"),
    ("polymers", "an FTIR spectrum", "an F T I R spectrum"),
    ("polymers", "XRD patterns", "X R D patterns"),
    ("polymers", "2PP lithography", "two P P lithography"),
    ("abbrev", "as shown in Fig. 3b", "as shown in Figure 3 b"),
    ("abbrev", "see Eq. (4)", "see Equation 4"),
    ("abbrev", "Smith et al. reported", "Smith et al reported"),
    ("abbrev", "polymers, e.g., PLA", "polymers, for example, P L A"),
    ("abbrev", "the modulus, i.e., stiffness", "the modulus, that is, stiffness"),
    ("abbrev", "ca. 20 min", "about 20 minutes"),
    ("abbrev", "DLP vs. SLA", "D L P versus S L A"),
    ("abbrev", "cf. Ref. 12", "compare Reference 12"),
    ("abbrev", "in Sec. 2", "in Section 2"),
]


def edit(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def run() -> int:
    from misaki import en

    from scireader.speech.pipeline import speak

    from misaki import espeak

    # Same setup as Kokoro's pipeline: out-of-dictionary words go through espeak-ng.
    g2p = en.G2P(trf=False, british=False, fallback=espeak.EspeakFallback(british=False))

    def ph(text: str) -> str:
        p, _ = g2p(text)
        return p.replace(" ", "")

    rows = []
    for i, (cat, text, gold) in enumerate(SNIPPETS):
        ours = speak(text).spoken
        p_raw, p_ours, p_gold = ph(text), ph(ours), ph(gold)
        d_raw = edit(p_raw, p_gold) / max(1, len(p_gold))
        d_ours = edit(p_ours, p_gold) / max(1, len(p_gold))
        rows.append({"id": i, "category": cat, "text": text, "gold": gold, "scireader": ours,
                     "ph_raw": p_raw, "ph_scireader": p_ours, "ph_gold": p_gold,
                     "dist_raw": round(d_raw, 3), "dist_scireader": round(d_ours, 3),
                     "wrong_raw": d_raw > 0.25, "wrong_scireader": d_ours > 0.25})
    out = ROOT / "bench" / "results" / "units.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "bench" / "data" / "units.jsonl").write_text(
        "".join(json.dumps({"category": c, "text": t, "gold": g}, ensure_ascii=False) + "\n" for c, t, g in SNIPPETS),
        encoding="utf-8")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = len(rows)
    wr = sum(r["wrong_raw"] for r in rows)
    wo = sum(r["wrong_scireader"] for r in rows)
    print(f"{n} snippets: generic reader mispronounces {wr} ({wr / n:.0%}), SciReader {wo} ({wo / n:.0%})")
    for r in rows:
        if r["wrong_scireader"]:
            print("  still off:", r["text"], "->", r["scireader"], f"({r['dist_scireader']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
