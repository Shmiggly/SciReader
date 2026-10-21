import json

from scireader.speech.lexicon import SHIPPED_EN, Lexicon, LexiconEntry, read_entries, strip_markup


def _write(path, entries, name="test"):
    path.write_text(
        json.dumps({"version": 1, "language": "en", "name": name, "entries": entries}), encoding="utf-8"
    )


def test_shipped_lexicon_loads_and_has_required_entries():
    lex = Lexicon.load(SHIPPED_EN)
    assert len(lex) >= 50
    want = {
        "PEGDA": "peg-dah", "Tg": "T G", "Tm": "T M", "PA12": "P-A twelve", "wt%": "weight percent",
        "vol%": "volume percent", "2PP": "two P P", "PLA": "P-L-A", "FTIR": "F-T-I-R",
    }
    for term, say in want.items():
        assert lex.get(term).say_as == say
    for term in "PLA ABS PETG TPU PDMS PEEK SLA DLP FFF FDM SLS MJF DIW DSC TGA DMA FTIR GPC SEM XRD".split():
        assert lex.get(term) is not None, term
    for e in lex.entries:
        assert e.source == "shipped" and e.tags


def test_user_overrides_shipped(tmp_path):
    shipped = tmp_path / "s.json"
    user = tmp_path / "u.json"
    _write(shipped, [{"term": "PEGDA", "say_as": "peg-dah"}, {"term": "Tg", "say_as": "T G"}])
    _write(user, [{"term": "PEGDA", "say_as": "peg-D-A"}])
    lex = Lexicon.load(shipped, user)
    assert lex.get("PEGDA").say_as == "peg-D-A"
    assert lex.get("PEGDA").source == "user"
    assert lex.find("PEGDA and Tg") == [(0, 5, "peg-D-A"), (10, 12, "T G")]


def test_missing_user_file_is_empty(tmp_path):
    lex = Lexicon.load(SHIPPED_EN, tmp_path / "nope.json")
    assert lex.user_entries == []
    assert read_entries(tmp_path / "nope.json") == []


def test_find_whole_word_case_and_longest():
    lex = Lexicon(
        [
            LexiconEntry("PEG", "peg"),
            LexiconEntry("PEGDA", "peg-dah"),
            LexiconEntry("photoinitiator", "photo-initiator", case_sensitive=False),
            LexiconEntry("wt%", "weight percent"),
        ]
    )
    text = "PEGDA, PEG, peg, PEGs, Photoinitiator and 5 wt% PEG-based"
    found = [(text[a:b], s) for a, b, s in lex.find(text)]
    assert found == [
        ("PEGDA", "peg-dah"),
        ("PEG", "peg"),
        ("Photoinitiator", "photo-initiator"),
        ("wt%", "weight percent"),
        ("PEG", "peg"),
    ]


def test_add_save_user_and_reload(tmp_path):
    lex = Lexicon.load(SHIPPED_EN)
    lex.add(LexiconEntry("Mn", "M N", tags=["polymers"]))
    assert lex.find("the Mn value") == [(4, 6, "M N")]
    p = tmp_path / "user.json"
    lex.save_user(p)
    again = Lexicon.load(SHIPPED_EN, p)
    assert again.get("Mn").say_as == "M N"
    assert [e.term for e in again.user_entries] == ["Mn"]


def test_export_roundtrip(tmp_path):
    lex = Lexicon([LexiconEntry("Tg", "T G", source="shipped")], [LexiconEntry("Tm", "T M")])
    p = tmp_path / "export.json"
    lex.export(p, name="mine")
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["version"] == 1 and doc["language"] == "en" and doc["name"] == "mine"
    assert {e["term"] for e in doc["entries"]} == {"Tg", "Tm"}


def test_merge_adds_new_skips_same_reports_conflicts():
    mine = Lexicon([LexiconEntry("Tg", "T G"), LexiconEntry("PEGDA", "peg-dah")])
    theirs = Lexicon([LexiconEntry("Tg", "T G"), LexiconEntry("PEGDA", "peg-D-A"), LexiconEntry("PCL", "P-C-L")])
    conflicts = mine.merge(theirs)
    assert [c.term for c in conflicts] == ["PEGDA"]
    assert conflicts[0].mine.say_as == "peg-dah" and conflicts[0].theirs.say_as == "peg-D-A"
    assert mine.get("PEGDA").say_as == "peg-dah"  # not applied until the caller decides
    assert mine.get("PCL").say_as == "P-C-L"
    mine.add(conflicts[0].theirs)  # "take theirs"
    assert mine.get("PEGDA").say_as == "peg-D-A"


def test_ipa_entry_uses_misaki_markup_and_strip():
    e = LexiconEntry("PEGDA", ipa="pˈɛɡdə")
    assert e.spoken == "[PEGDA](/pˈɛɡdə/)"
    lex = Lexicon([e])
    assert lex.find("the PEGDA gel") == [(4, 9, "[PEGDA](/pˈɛɡdə/)")]
    assert strip_markup("the [PEGDA](/pˈɛɡdə/) gel and [Tg](/tˈi ʤˈi/)") == "the PEGDA gel and Tg"
    assert strip_markup("no markup [1] here") == "no markup [1] here"


def test_entry_dict_roundtrip():
    e = LexiconEntry("PA12", "P-A twelve", tags=["polymers"], source="shipped", note="polyamide 12")
    assert LexiconEntry.from_dict(e.to_dict()) == e


def test_remove_user_entry_restores_shipped():
    lex = Lexicon([LexiconEntry("Tg", "T G", source="shipped")])
    lex.add(LexiconEntry("Tg", "tee gee"))
    assert lex.find("Tg") == [(0, 2, "tee gee")]
    assert lex.remove("Tg")
    assert lex.find("Tg") == [(0, 2, "T G")]


def test_empty_lexicon_finds_nothing():
    assert Lexicon().find("anything at all") == []
