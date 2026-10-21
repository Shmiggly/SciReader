import pytest

from scireader.speech.splitter import split_sentences


def sents(text):
    return [text[a:b] for a, b in split_sentences(text)]


CASES = [
    ("One. Two.", ["One.", "Two."]),
    ("Is it? Yes! Done.", ["Is it?", "Yes!", "Done."]),
    ("No final period here", ["No final period here"]),
    ("  Padded sentence.   Next one.  ", ["Padded sentence.", "Next one."]),
    ("As shown in Fig. 3, it works. Next.", ["As shown in Fig. 3, it works.", "Next."]),
    ("See Figs. 2 and 3. Then.", ["See Figs. 2 and 3.", "Then."]),
    ("From Eq. 4 we get x. Then y.", ["From Eq. 4 we get x.", "Then y."]),
    ("Using Eqs. (3) and (4) gives z.", ["Using Eqs. (3) and (4) gives z."]),
    ("See Ref. 12 for details.", ["See Ref. 12 for details."]),
    ("As in Refs. 3-5 above.", ["As in Refs. 3-5 above."]),
    ("In Sec. 2 we show it.", ["In Sec. 2 we show it."]),
    ("Listed in Tab. 1 below.", ["Listed in Tab. 1 below."]),
    ("Sample No. 5 failed.", ["Sample No. 5 failed."]),
    ("Polymers, e.g. PLA, are common.", ["Polymers, e.g. PLA, are common."]),
    ("The modulus, i.e. E, rose.", ["The modulus, i.e. E, rose."]),
    ("Smith et al. (2020) found it.", ["Smith et al. (2020) found it."]),
    ("Smith et al. 2019 found it.", ["Smith et al. 2019 found it."]),
    ("Smith et al. reported it.", ["Smith et al. reported it."]),
    ("It was shown by Smith et al. The result held.", ["It was shown by Smith et al.", "The result held."]),
    ("PLA vs. ABS was tested.", ["PLA vs. ABS was tested."]),
    ("This is cf. Ref. 2 here.", ["This is cf. Ref. 2 here."]),
    ("It took ca. 5 min to cure.", ["It took ca. 5 min to cure."]),
    ("It is approx. 3 mm wide.", ["It is approx. 3 mm wide."]),
    ("Values were 2 and 3, resp. as noted.", ["Values were 2 and 3, resp. as noted."]),
    ("Dr. Smith and Prof. Jones met.", ["Dr. Smith and Prof. Jones met."]),
    ("Acme Inc. Supplied it. Then.", ["Acme Inc. Supplied it.", "Then."]),
    ("J. Smith wrote it.", ["J. Smith wrote it."]),
    ("A. B. Smith wrote it.", ["A. B. Smith wrote it."]),
    ("The value is 3.14 exactly.", ["The value is 3.14 exactly."]),
    ("Only .5 mm was used.", ["Only .5 mm was used."]),
    ("1. Introduction to polymers", ["1. Introduction to polymers"]),
    ("Steps: 2. Mix the resin", ["Steps: 2. Mix the resin"]),
    ("Wait... it worked. Done.", ["Wait... it worked.", "Done."]),
    ("Made in the U.S. by them.", ["Made in the U.S. by them."]),
    ("Used in 3D printing.12 The next one.", ["Used in 3D printing.12", "The next one."]),
    ("Used in 3D printing.¹² The next one.", ["Used in 3D printing.¹²", "The next one."]),
    ("Used in 3D printing [3]. The next one.", ["Used in 3D printing [3].", "The next one."]),
    ("He said “stop.” Then left.", ["He said “stop.”", "Then left."]),
    ("It was measured (see below). Next.", ["It was measured (see below).", "Next."]),
    ("The yield was 95%. 20 samples failed.", ["The yield was 95%.", "20 samples failed."]),
    ("It cured. (Data not shown.) Next.", ["It cured.", "(Data not shown.)", "Next."]),
    ("Heated to 300 K. The phase changed.", ["Heated to 300 K.", "The phase changed."]),
    ("The value was 5. The next was 6.", ["The value was 5.", "The next was 6."]),
    ("Para one.\n\nPara two", ["Para one.", "Para two"]),
    ("The α phase formed. Δ was small.", ["The α phase formed.", "Δ was small."]),
    ("", []),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_split(text, expected):
    assert sents(text) == expected


def test_spans_are_trimmed_ordered_and_within_text():
    text = "  First one.  Second one?  Third!  "
    spans = split_sentences(text)
    assert spans == sorted(spans)
    for a, b in spans:
        assert 0 <= a < b <= len(text)
        assert not text[a].isspace() and not text[b - 1].isspace()


def test_long_paragraph_speed():
    import time

    text = "The PEGDA resin was cured at 25 °C (Fig. 3b), cf. Ref. 12. " * 2000
    t0 = time.perf_counter()
    spans = split_sentences(text)
    assert time.perf_counter() - t0 < 1.0
    assert len(spans) == 2000
