import time

import pytest

from scireader.speech.en.normalizer import normalize
from scireader.speech.lexicon import Lexicon, LexiconEntry
from scireader.speech.normalized import Normalized

CASES = [
    # ---- units after numbers (singular after exactly 1)
    ("The gap is 1.12 eV at 300 K.", "The gap is 1.12 electron volts at 300 kelvin."),
    ("at 1 K", "at 1 kelvin"),
    ("at 300K", "at 300 kelvin"),
    ("25 °C", "25 degrees Celsius"),
    ("25°C", "25 degrees Celsius"),
    ("1 °C", "1 degree Celsius"),
    ("100 °F", "100 degrees Fahrenheit"),
    ("5 meV and 2 keV", "5 millielectron volts and 2 kiloelectron volts"),
    ("3.5 Å", "3.5 angstroms"),
    ("1 Å", "1 angstrom"),
    ("500 nm", "500 nanometers"),
    ("5 µm", "5 micrometers"),
    ("5 μm", "5 micrometers"),
    ("2 mm and 3 cm", "2 millimeters and 3 centimeters"),
    ("1 m", "1 meter"),
    ("5 m", "5 meters"),
    ("2 km", "2 kilometers"),
    ("30 s", "30 seconds"),
    ("1 s", "1 second"),
    ("5 ms, 3 µs and 2 ns", "5 milliseconds, 3 microseconds and 2 nanoseconds"),
    ("5 min", "5 minutes"),
    ("1 min", "1 minute"),
    ("24 h", "24 hours"),
    ("1 h", "1 hour"),
    ("50 Hz, 20 kHz, 5 MHz, 2.4 GHz", "50 hertz, 20 kilohertz, 5 megahertz, 2.4 gigahertz"),
    ("100 Pa", "100 pascals"),
    ("101 kPa", "101 kilopascals"),
    ("45 MPa", "45 megapascals"),
    ("2.1 GPa", "2.1 gigapascals"),
    ("10 N and 5 mN", "10 newtons and 5 millinewtons"),
    ("4 J and 3 kJ", "4 joules and 3 kilojoules"),
    ("10 W and 5 mW", "10 watts and 5 milliwatts"),
    ("5 V, 10 kV, 3 mV", "5 volts, 10 kilovolts, 3 millivolts"),
    ("2 A and 5 mA", "2 amperes and 5 milliamperes"),
    ("2 mol and 3 mmol", "2 moles and 3 millimoles"),
    ("1 M NaOH", "1 molar N-A O H"),
    ("0.5 mM and 10 µM", "0.5 millimolar and 10 micromolar"),
    ("1 L and 5 mL and 10 µL", "1 liter and 5 milliliters and 10 microliters"),
    ("5 g, 2 mg, 1 kg", "5 grams, 2 milligrams, 1 kilogram"),
    ("5 wt% and 3 vol% and 2 mol%", "5 weight percent and 3 volume percent and 2 mole percent"),
    ("3000 rpm", "3000 revolutions per minute"),
    ("50 cP", "50 centipoise"),
    ("10 mPa·s and 2 Pa·s", "10 millipascal seconds and 2 pascal seconds"),
    ("60 dB", "60 decibels"),
    ("90° rotation", "90 degrees rotation"),
    ("5% of", "5 percent of"),
    ("10 ppm", "10 parts per million"),
    ("50 kDa and 300 Da", "50 kilodaltons and 300 daltons"),
    ("10 Ω and 5 kΩ", "10 ohms and 5 kiloohms"),
    # ---- compound units
    ("50 kJ/mol", "50 kilojoules per mole"),
    ("50 kJ mol−1", "50 kilojoules per mole"),
    ("8.314 J mol−1 K−1", "8.314 joules per mole per kelvin"),
    ("150 g/mol", "150 grams per mole"),
    ("150 g mol−1", "150 grams per mole"),
    ("100 mW/cm²", "100 milliwatts per square centimeter"),
    ("100 mW cm−2", "100 milliwatts per square centimeter"),
    ("5 J/cm²", "5 joules per square centimeter"),
    ("5 m/s", "5 meters per second"),
    ("5 m s−1", "5 meters per second"),
    ("9.8 m s−2", "9.8 meters per second squared"),
    ("9.8 m s⁻²", "9.8 meters per second squared"),
    ("1700 cm−1", "1700 inverse centimeters"),
    ("1700 cm⁻¹", "1700 inverse centimeters"),
    ("1700 cm-1", "1700 inverse centimeters"),
    ("0.1 mol L−1", "0.1 moles per liter"),
    ("0.1 mol L⁻¹", "0.1 moles per liter"),
    ("1 mol L−1", "1 mole per liter"),
    ("10 S/cm", "10 siemens per centimeter"),
    ("10 °C min−1", "10 degrees Celsius per minute"),
    ("10 °C/min", "10 degrees Celsius per minute"),
    ("8.3 J/(mol K)", "8.3 joules per mole per kelvin"),
    ("5 cm²", "5 square centimeters"),
    ("2 m³", "2 cubic meters"),
    ("10 cm3", "10 cubic centimeters"),
    # ---- bare multi-letter units
    ("Stress (MPa)", "Stress (megapascals)"),
    ("in GPa", "in gigapascals"),
    ("energies in eV", "energies in electron volts"),
    ("wavenumber (cm−1)", "wavenumber (inverse centimeters)"),
    ("in kJ/mol", "in kilojoules per mole"),
    ("in nm", "in nanometers"),
    # ---- scientific notation
    ("1.2 × 10⁻³", "1.2 times 10 to the minus 3"),
    ("1.2 × 10−3", "1.2 times 10 to the minus 3"),
    ("1.2×10^-3", "1.2 times 10 to the minus 3"),
    ("1.2e-3", "1.2 times 10 to the minus 3"),
    ("3E5", "3 times 10 to the 5"),
    ("10⁵", "10 to the 5"),
    ("10⁻⁶", "10 to the minus 6"),
    ("4 × 105 cells", "4 times 10 to the 5 cells"),
    ("1.2 × 10⁻³ mol L⁻¹", "1.2 times 10 to the minus 3 moles per liter"),
    ("a 10−6 M solution", "a 10 to the minus 6 molar solution"),
    ("10^3", "10 to the 3"),
    # ---- symbols
    ("25 ± 2 °C", "25 plus or minus 2 degrees Celsius"),
    ("x ∓ y", "x minus or plus y"),
    ("x ≈ 5", "x approximately 5"),
    ("~5 nm", "about 5 nanometers"),
    ("∼ 5 nm", "about 5 nanometers"),
    ("σ ∝ T", "sigma proportional to T"),
    ("p < 0.05", "p less than 0.05"),
    ("T > 300 K", "T greater than 300 kelvin"),
    ("0 ≤ x ≤ 1", "0 less than or equal to x less than or equal to 1"),
    ("x ≥ 2", "x greater than or equal to 2"),
    ("a ≠ b", "a not equal to b"),
    ("A → B", "A to B"),
    ("t → ∞", "t to infinity"),
    ("10 × 10 mm", "10 by 10 millimeters"),
    ("a 5× increase", "a 5 times increase"),
    ("θ = 30°", "theta equals 30 degrees"),
    ("at −20 °C", "at minus 20 degrees Celsius"),
    ("at -20 °C", "at minus 20 degrees Celsius"),
    ("5 ‰", "5 per mille"),
    ("a · b", "a dot b"),
    ("x′", "x prime"),
    # ---- ranges
    ("5–10 K", "5 to 10 kelvin"),
    ("20-30%", "20 to 30 percent"),
    ("5 – 10 nm", "5 to 10 nanometers"),
    ("Figs. 2–4", "Figures 2 to 4"),
    ("pp. 3–7", "pages 3 to 7"),
    ("in 2019–2020", "in 2019 to 2020"),
    ("an x−y plot", "an x−y plot"),
    ("a well-known fact", "a well-known fact"),
    ("ISO 527-2", "ISO 527-2"),
    ("the 2-methyl group", "the 2-methyl group"),
    # ---- Greek and math
    ("α-helix", "alpha-helix"),
    ("β and γ", "beta and gamma"),
    ("ΔH", "delta H"),
    ("Δ", "delta"),
    ("∇·u", "nabla dot u"),
    ("∂f", "partial f"),
    ("µ is the viscosity", "mu is the viscosity"),
    ("μ = 2", "mu equals 2"),
    ("𝑥 and 𝑘", "x and k"),
    ("𝛼", "alpha"),
    ("𝑘B𝑇", "k B T"),
    ("k_B T", "k B T"),
    ("µCT scans", "micro CT scans"),
    # ---- sub/superscripts
    ("x²", "x squared"),
    ("x³", "x cubed"),
    ("xⁿ", "x to the n"),
    ("x⁻¹", "x to the minus 1"),
    ("x₁ and x₂", "x 1 and x 2"),
    ("R² = 0.98", "R squared equals 0.98"),
    ("𝑥²", "x squared"),
    ("x^2", "x squared"),
    ("T_g", "T g"),
    ("in printing¹² and", "in printing and"),
    ("as reported.¹²,¹³ Next", "as reported. Next"),
    ("polymers¹⁻³ are", "polymers are"),
    # ---- chemistry
    ("H₂O", "H 2 O"),
    ("H2O", "H 2 O"),
    ("Fe₂O₃", "F-E 2 O 3"),
    ("CO₂", "C O 2"),
    ("CO2", "C O 2"),
    ("TiO2", "T-I O 2"),
    ("SiO2", "S-I O 2"),
    ("NH₄⁺", "N H 4 plus"),
    ("NH4+ ions", "N H 4 plus ions"),
    ("Ca²⁺", "C-A 2 plus"),
    ("Ca(OH)2", "C-A O H 2"),
    ("¹³C NMR", "carbon 13 NMR"),
    ("²H labeling", "deuterium labeling"),
    ("¹⁹F", "fluorine 19"),
    ("NaCl", "N-A C-L"),
    ("CO2-based", "C O 2-based"),
    # ---- ambiguity traps
    ("the min of the set", "the min of the set"),
    ("min(x)", "min(x)"),
    ("Si wafers", "Si wafers"),
    ("In this work", "In this work"),
    ("As shown, At low T, Be careful, He said, No way, Co workers", "As shown, At low T, Be careful, He said, No way, Co workers"),
    ("K is a constant", "K is a constant"),
    ("the m-th mode", "the m-th mode"),
    ("A sample", "A sample"),
    ("it's the 1990s", "it's the 1990s"),
    ("M is large", "M is large"),
    ("at pH 7", "at pH 7"),
    ("PLA and PETG and PEGDA and PA12", "PLA and PETG and PEGDA and PA12"),
    ("DFT, ML, MD, GNN, ANN", "DFT, ML, MD, GNN, ANN"),
    ("Fig. 5 A shows", "Figure 5 A shows"),
    ("S/N ratio", "S/N ratio"),
    ("NaN values", "NaN values"),
    ("mol fraction", "mol fraction"),
    # ---- abbreviations and references
    ("e.g. PLA", "for example PLA"),
    ("E.g., this", "For example, this"),
    ("i.e. the", "that is the"),
    ("Smith et al. showed", "Smith et al showed"),
    ("by Smith et al. The", "by Smith et al. The"),
    ("ca. 5 nm", "about 5 nanometers"),
    ("A vs. B", "A versus B"),
    ("cf. Ref. 5", "compare Reference 5"),
    ("approx. 3", "approximately 3"),
    ("2 and 3, resp.", "2 and 3, respectively."),
    ("No. 5", "number 5"),
    ("Eq. (3)", "Equation 3"),
    ("Eqs. (3) and (4)", "Equations 3 and 4"),
    ("Eq. 3", "Equation 3"),
    ("Fig. 3b", "Figure 3 B"),
    ("Figure 3(b)", "Figure 3 B"),
    ("Fig. 3a–c", "Figure 3 A to C"),  # panel letters as letter names: a lone "a" is read as the article
    ("additive manufacturing (AM) technologies", "additive manufacturing, AM, technologies"),
    ("known as melt electro-writing (MEW).", "known as melt electro-writing, MEW."),
    ("Stress (MPa)", "Stress (megapascals)"),
    ("most type-I photoinitiators", "most type-one photoinitiators"),
    ("Phase II and Class IV", "Phase two and Class four"),
    ("formula [-(CH2)11C(O)NH-]n as shown", "formula C H 2, 11, C, O, N H, n as shown"),
    ("Table 2", "Table 2"),
    ("Sec. 2.3", "Section 2.3"),
    ("as in Ref. [12]", "as in Reference [12]"),
    ("intensity (a.u.)", "intensity (arbitrary units)"),
    # ---- regressions found on real Docling text
    ("a dataset with 10K polymers", "a dataset with 10K polymers"),
    ("10 mW/cm 2 , for curves", "10 milliwatts per square centimeter , for curves"),
    ("point (Z ¼ 17.5) denoted", "point (Z equals 17.5) denoted"),
    ("the IDs of the ReLu layers", "the IDs of the ReLu layers"),
    ("vol. 11271, p. 112710A, SPIE", "vol. 11271, page 112710 A, SPIE"),
    ("Fig. 5A shows", "Figure 5 A shows"),
    ("GaAs and ZnO and HCl", "G-A A-S and Z-N O and H C-L"),
    ("HeLa cells", "HeLa cells"),
    ("a 5A sample", "a 5A sample"),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_normalize_cases(text, expected):
    r = normalize(text)
    assert r.spoken == expected
    _check_segments(r)


def _check_segments(r: Normalized) -> None:
    segs = r.segments
    if not r.display:
        assert r.spoken == ""
        return
    assert segs[0][0] == 0 and segs[0][2] == 0
    assert segs[-1][1] == len(r.display) and segs[-1][3] == len(r.spoken)
    for (a0, a1, b0, b1), (c0, c1, d0, d1) in zip(segs, segs[1:]):
        assert a1 == c0 and b1 == d0
    for d0, d1, s0, s1 in segs:
        assert d0 <= d1 and s0 <= s1
        assert d0 < d1 or s0 < s1


def test_unchanged_text_is_identity():
    t = "Plain prose with nothing to change."
    r = normalize(t)
    assert r.spoken == t
    assert r.segments == [(0, len(t), 0, len(t))]


def test_empty_text():
    r = normalize("")
    assert r.spoken == "" and r.segments == []


def test_segment_map_exact_for_units():
    t = "The gap is 1.12 eV at 300 K."
    r = normalize(t)
    s0 = r.spoken.index("electron volts")
    assert r.spoken_to_display(s0, s0 + len("electron volts")) == (t.index("eV"), t.index("eV") + 2)
    s0 = r.spoken.index("kelvin")
    assert r.spoken_to_display(s0, s0 + 6) == (t.index("K"), t.index("K") + 1)
    # identity word maps exactly
    s0 = r.spoken.index("gap")
    assert r.spoken_to_display(s0, s0 + 3) == (t.index("gap"), t.index("gap") + 3)
    # and back
    d0 = t.index("eV")
    assert r.display_to_spoken(d0, d0 + 2) == (r.spoken.index("electron"), r.spoken.index("volts") + 5)


def test_segment_map_word_inside_rewrite_maps_to_whole_rewrite():
    t = "Measured 9.8 m s−2 here"
    r = normalize(t)
    s0 = r.spoken.index("second")
    assert r.spoken_to_display(s0, s0 + 6) == (t.index("m s"), t.index("−2") + 2)


def test_segment_map_identity_roundtrip_every_char():
    t = "Using 5 wt% PEGDA, Tg rose (Fig. 3b) to ~60 °C; H₂O uptake was 1.2 × 10⁻³ mol L⁻¹."
    r = normalize(t)
    _check_segments(r)
    for seg in r.segments:
        d0, d1, s0, s1 = seg
        if r.is_identity_segment(seg):
            for k in range(d1 - d0):
                assert r.display_to_spoken(d0 + k, d0 + k + 1) == (s0 + k, s0 + k + 1)
                assert r.spoken_to_display(s0 + k, s0 + k + 1) == (d0 + k, d0 + k + 1)
        else:
            assert r.display_to_spoken(d0, d1) == (s0, s1) or d0 == d1
            if s0 < s1:
                assert r.spoken_to_display(s0, s1) == (d0, d1)


def test_protected_spans_emitted_as_given_and_deletion_tidies_spaces():
    t = "printing of PLA [12]. The K value"
    s = t.index("[12]")
    r = normalize(t, protected=[(s, s + 4, "")])
    assert r.spoken == "printing of PLA. The K value"
    _check_segments(r)
    # the deleted citation maps to an empty spoken span
    a, b = r.display_to_spoken(s, s + 4)
    assert a == b


def test_protected_span_text_untouched():
    t = "where x² + 5 K is"
    s = t.index("x²")
    r = normalize(t, protected=[(s, s + 2, "ex squared")])
    assert r.spoken == "where ex squared plus 5 kelvin is"
    s0 = r.spoken.index("ex squared")
    assert r.spoken_to_display(s0, s0 + 10) == (s, s + 2)


def test_protected_overlapping_raises():
    with pytest.raises(ValueError):
        normalize("abcdef", protected=[(0, 3, "x"), (2, 4, "y")])


def test_multiple_deletions_no_double_space():
    t = "as shown [1] [2] before"
    p = [(t.index("[1]"), t.index("[1]") + 3, ""), (t.index("[2]"), t.index("[2]") + 3, "")]
    r = normalize(t, protected=p)
    assert r.spoken == "as shown before"
    _check_segments(r)


def test_deletion_at_start():
    t = "[3] PLA is common"
    r = normalize(t, protected=[(0, 3, "")])
    assert r.spoken == "PLA is common"
    _check_segments(r)


def test_lexicon_applied_before_rules():
    lex = Lexicon(
        [
            LexiconEntry("PEGDA", "peg-dah", source="shipped"),
            LexiconEntry("Tg", "T G", source="shipped"),
            LexiconEntry("wt%", "weight percent", source="shipped"),
            LexiconEntry("PA12", "P-A twelve", source="shipped"),
        ]
    )
    r = normalize("5 wt% PEGDA raised Tg of PA12.", lexicon=lex)
    assert r.spoken == "5 weight percent peg-dah raised T G of P-A twelve."
    _check_segments(r)


def test_lexicon_does_not_override_protected():
    lex = Lexicon([LexiconEntry("PEGDA", "peg-dah")])
    t = "PEGDA and PEGDA"
    r = normalize(t, lexicon=lex, protected=[(0, 5, "PEGDA")])
    assert r.spoken == "PEGDA and peg-dah"


def test_lexicon_ipa_markup():
    lex = Lexicon([LexiconEntry("PEGDA", ipa="pˈɛɡdə")])
    r = normalize("the PEGDA resin", lexicon=lex)
    assert r.spoken == "the [PEGDA](/pˈɛɡdə/) resin"


def test_shipped_lexicon_with_normalizer():
    lex = Lexicon.load()
    r = normalize("PLA and PETG printed by FDM; Tg by DSC.", lexicon=lex)
    assert r.spoken == "P-L-A and P-E-T-G printed by F-D-M; T G by D-S-C."


def test_speed_400_sentences():
    sent = (
        "The PEGDA resin (5 wt%) was cured at 25 °C under 20 mW cm−2 for 30 s, "
        "giving E = 1.2 ± 0.1 GPa and Tg ≈ 60 °C (Fig. 3b), cf. Ref. 12. "
    )
    text = sent * 400
    t0 = time.perf_counter()
    r = normalize(text)
    assert time.perf_counter() - t0 < 1.0
    assert "gigapascals" in r.spoken


@pytest.mark.parametrize(
    "text, expected",
    [
        ("additive manufacturing (AM) technologies", "additive manufacturing, A-M, technologies"),
        ("a (meth)acrylate monomer", "a methacrylate monomer"),
        ("SMILES strings in log10Hz at 50 Hz", "smiles strings in log ten hertz at 50 hertz"),
        ("NVK = N-vinylcarbazole", "NVK equals N vinyl carbazole"),
    ],
)
def test_shipped_lexicon_cases(text, expected):
    from scireader.speech.lexicon import Lexicon

    assert normalize(text, lexicon=Lexicon.load()).spoken == expected
