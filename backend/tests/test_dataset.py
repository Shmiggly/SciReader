"""The pronunciation dataset: one file per user, the same structure for everyone, built over time."""

import json

from scireader.speech.dataset import FORMAT, Dataset, open_dataset, same_sound, update_dataset
from scireader.speech.lexicon import SHIPPED_EN, LexiconEntry
from scireader.speech.review import paper_view


def E(term, say=None, **kw):  # noqa: N802
    return LexiconEntry(term, say, **kw)


def test_reads_this_format_older_lexicons_and_bare_lists():
    ds = Dataset.from_json(json.loads(SHIPPED_EN.read_text(encoding="utf-8")), "base")
    assert len(ds.entries) >= 100 and {e.source for e in ds.entries} == {"base"}
    old = Dataset.from_json({"version": 1, "entries": [{"term": "Tg", "say_as": "T G", "source": "shipped"},
                                                        {"term": "Tm", "say_as": "T M", "source": "user"}, {"term": " "}]})
    assert [(e.term, e.source) for e in old.entries] == [("Tg", "base"), ("Tm", "me")]
    assert [e.term for e in Dataset.from_json([{"term": "PCL", "say_as": "P-C-L"}]).entries] == ["PCL"]
    data = ds.to_json()
    assert data["format"] == FORMAT and data["version"] == 2 and Dataset.from_json(data).entries == ds.entries
    for e in data["entries"]:  # every entry has every field: the same structure in every file
        assert set(e) == {"term", "say_as", "ipa", "case_sensitive", "tags", "source", "note", "kind", "checked", "added"}


def test_same_term_and_sound():
    ds = Dataset([E("Tg", "T G"), E("TG", "T-G-A"), E("photoinitiator", "photo-initiator", case_sensitive=False)])
    assert ds.first("Tg").say_as == "T G" and ds.first("TG").say_as == "T-G-A"  # different terms
    assert ds.first("Photoinitiator").say_as == "photo-initiator"  # the entry ignores case
    assert ds.group(E("Photoinitiator", case_sensitive=False)) == [2]
    assert same_sound(E("PLA", "P-L-A"), E("PLA", "P L A")) and not same_sound(E("PLA", "P-L-A"), E("PLA", "pla"))


def test_import_adds_new_skips_same_and_keeps_two_entries_that_differ():
    ds = Dataset([E("Tg", "T G", source="base"), E("PEGDA", "peg-dah", source="me")])
    r = ds.merge([E("Tg", "T-G"), E("PEGDA", "peg-D-A", checked=False), E("PCL", "P-C-L")], "import:Lab list")
    assert r == {"added": 1, "same": 1, "duplicates": 1}
    assert ds.duplicates() == [[1, 2]]
    assert ds.lexicon().find("PEGDA and PCL") == [(0, 5, "peg-dah"), (10, 13, "P-C-L")]  # the first is spoken
    assert ds.entries[2].source == "import:Lab list" and ds.entries[2].checked is False
    kept = ds.keep("PEGDA", 1)  # the user picks the imported one
    assert kept.say_as == "peg-D-A" and kept.checked and ds.duplicates() == []
    assert [e.term for e in ds.entries] == ["Tg", "PEGDA", "PCL"]


def test_giving_a_pronunciation_replaces_every_entry_for_the_term():
    ds = Dataset([E("PEGDA", "peg-dah", source="base"), E("PEGDA", "peg-D-A", source="import:x"), E("Tm", "T M")])
    e = ds.put(E("PEGDA", "peg-dee-ay", kind="acronym"))
    assert (e.source, e.checked, e.added is not None) == ("me", True, True)
    assert [(x.term, x.say_as) for x in ds.entries] == [("PEGDA", "peg-dee-ay"), ("Tm", "T M")]
    ds.put(E("GelMA", None, kind="molecule"))  # "sounds right": read as written
    assert ds.lexicon().find("GelMA") == [(0, 5, "GelMA")]


def test_base_list_updates_flow_in_but_never_over_the_users_choices():
    ds = Dataset([E("Tg", "T G", source="base"), E("PLA", "pla", source="me")])
    ds.sync_base([E("Tg", "tee gee"), E("PLA", "P-L-A"), E("PCL", "P-C-L"), E("ABS", "A-B-S")], "h1")
    assert [(e.term, e.say_as, e.source) for e in ds.entries] == [
        ("Tg", "tee gee", "base"), ("PLA", "pla", "me"), ("PCL", "P-C-L", "base"), ("ABS", "A-B-S", "base")]
    assert ds.remove("ABS") == 1 and ds.removed == ["ABS"]
    ds.sync_base([E("ABS", "A-B-S"), E("PEEK", "peek")], "h2")
    assert [e.term for e in ds.entries] == ["Tg", "PLA", "PCL", "PEEK"]  # a removed term stays out
    ds.put(E("ABS", "abs"))  # ...until the user gives it again
    assert ds.removed == [] and ds.first("ABS").say_as == "abs"
    assert ds.remove("PEEK", index=0) == 1 and ds.removed == []  # removing one of two entries is no removal


def test_personal_file_starts_from_the_base_list_and_only_changes_are_saved(tmp_path):
    base, mine, old = tmp_path / "base.json", tmp_path / "pronunciations.json", tmp_path / "lexicon.user.json"
    base.write_text(json.dumps({"entries": [{"term": "Tg", "say_as": "T G"}, {"term": "PLA", "say_as": "P-L-A"}]}), encoding="utf-8")
    old.write_text(json.dumps({"version": 1, "entries": [{"term": "PLA", "say_as": "pla", "source": "user"}]}), encoding="utf-8")
    paths = (mine, base, old)
    ds = open_dataset(paths)
    assert [(e.term, e.say_as, e.source) for e in ds.entries] == [("PLA", "pla", "me"), ("Tg", "T G", "base")]
    assert not mine.exists()  # reading never writes
    update_dataset(lambda d: d.put(E("PCL", "P-C-L")), paths)
    saved = json.loads(mine.read_text(encoding="utf-8"))
    assert saved["format"] == FORMAT and [e["term"] for e in saved["entries"]] == ["PLA", "Tg", "PCL"]
    base.write_text(json.dumps({"entries": [{"term": "Tg", "say_as": "T G"}, {"term": "PEEK", "say_as": "peek"}]}), encoding="utf-8")
    assert [e.term for e in open_dataset(paths).entries] == ["PLA", "Tg", "PCL", "PEEK"]  # the update, in memory


def _doc(*texts):
    return {"blocks": [{"type": "paragraph", "sentences": [{"id": f"s{i}", "text": t, "spoken": t, "rects": []}
                                                           for i, t in enumerate(texts)]}]}


def test_paper_view_splits_suggested_known_and_duplicates():
    ds = Dataset([E("PEGDA", "peg-dah", source="base"), E("PEGDA", "peg-D-A", source="import:x"), E("Tg", "T G")])
    doc = _doc("The PEGDA resin has a Tg of 40 C.", "Cured PEGDA and HDDA gels; HDDA is stiffer.", "Measured with DMTA.")
    v = paper_view(doc, ds)
    assert [(s["term"], s["count"], s["kind"]) for s in v["suggested"]] == [("HDDA", 2, "acronym"), ("DMTA", 1, "acronym")]
    assert [(k["term"], k["count"], k["duplicate"], k["entry"]["say_as"]) for k in v["known"]] == [
        ("PEGDA", 2, True, "peg-dah"), ("Tg", 1, False, "T G")]
    assert v["duplicates"][0]["term"] == "PEGDA" and v["duplicates"][0]["in_paper"]
    assert [x["say_as"] for x in v["duplicates"][0]["entries"]] == ["peg-dah", "peg-D-A"]
    assert v["dataset"] == {"entries": 3, "mine": 1, "unchecked": 0, "duplicates": 1}
    assert v["suggested"][0]["snippet"].startswith("Cured PEGDA and HDDA")
