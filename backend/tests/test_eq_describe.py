"""Equation mentions in running text (forms seen in the sample papers) and the cached AI descriptions of equations."""

from scireader.llm import eq_describe, ollama
from scireader.llm.eq_describe import find_mentions, labels, parse_refs, spoken_for, tidy
from scireader.store.docs import DocStore


def refs(text: str) -> list[tuple[str, str]]:
    """(matched text, equation number) for each reference."""
    return [(text[a:z], n) for a, z, n in parse_refs(text)]


def test_reference_styles_from_the_sample_papers():
    assert refs("From equation (6), τ is given by") == [("equation (6)", "6")]  # IOP
    assert refs("Equation (2) shows the initiator") == [("Equation (2)", "2")]  # MDPI
    assert refs("is given by Eq. (9).") == [("Eq. (9)", "9")]
    assert refs("according to Eq. 5, where (ρ0, Tg) is") == [("Eq. 5", "5")]  # OPC
    assert refs("as described in Equation(6).") == [("Equation(6)", "6")]  # PA12, glued by the text layer
    assert refs("(see Eq. 3) is determined:") == [("Eq. 3", "3")]
    assert refs("as in Eq. 1.") == [("Eq. 1", "1")]


def test_lists_give_one_reference_per_number():
    assert refs("using equation (9) and (10), we get") == [("equation (9)", "9"), ("(10)", "10")]
    assert refs("the equations (15), and (16) for the flow") == [("equations (15)", "15"), ("(16)", "16")]
    assert refs("using equations (13), (14) with") == [("equations (13)", "13"), ("(14)", "14")]
    assert refs("according to Eq. 1 and 2, is illustrated") == [("Eq. 1", "1"), ("2", "2")]
    assert refs("Eqs. (3)–(5) give") == [("Eqs. (3)", "3"), ("(5)", "5")]
    assert refs("Eq. (1a) and (1b)") == [("Eq. (1a)", "1a"), ("(1b)", "1b")]


def test_non_references():
    assert refs("Eq. (5) and 20 samples") == [("Eq. (5)", "5")]  # a list keeps the style of its first number
    assert refs("see Eq. S3 in the SI") == []
    assert refs("the inequation 3 holds") == []
    assert refs("in Eq. 2.5 of the thesis") == []
    assert refs("the governing equations are") == []


def test_labels_of_stacked_equations():
    assert labels("1a,b") == ["1a,b", "1a", "1b", "1"]
    assert labels("6") == ["6"]
    assert labels(None) == []


def _doc() -> dict:
    sent = lambda sid, text: {"id": sid, "text": text, "spoken": text, "rects": []}  # noqa: E731
    eq = lambda bid, number, **kw: {"id": bid, "type": "equation", "eq_number": number, "sentences": [sent(bid + "s", "")], **kw}  # noqa: E731
    return {
        "blocks": [
            {"id": "b0", "type": "paragraph", "sentences": [sent("s0", "Combining equation (1a) with Eq. (2) and (7) gives")]},
            eq("e1", "1a,b"),
            eq("e2", "2"),
            eq("ej", None, skip_reason="junk"),
            {"id": "b1", "type": "caption", "sentences": [sent("s1", "Fits of Equation 2 to the data.")]},
            {"id": "b2", "type": "paragraph", "skip_reason": "footnote", "sentences": [sent("s2", "See Eq. 1.")]},
            {"id": "b3", "type": "paragraph", "sentences": [sent("s3", "From Eq. 1, the rate.")]},
        ],
    }


def test_mentions_point_to_numbered_equations():
    ms = find_mentions(_doc())
    assert [(m["sentence_id"], m["number"], m["block_id"]) for m in ms] == [
        ("s0", "1a", "e1"), ("s0", "2", "e2"), ("s1", "2", "e2"), ("s3", "1", "e1"),
    ]  # there is no equation 7; footnotes hold no mentions; a stacked "1a,b" answers to "1a" and to "1"
    assert ms[0]["span"] == [10, 23] and "rects" not in ms[0]
    speech = {"s3": {"words": [[5, 8, [[0, 10, 20, 30, 28]]], [9, 11, [[0, 32, 20, 40, 28]]]]}}
    assert find_mentions(_doc(), speech)[-1]["rects"] == [[0, 10, 20, 40, 28]]


def test_context_skips_other_equations_but_not_headings():
    blocks = [
        {"type": "heading", "sentences": [{"text": "2. Model"}]},
        {"type": "paragraph", "sentences": [{"text": "A."}, {"text": "B."}, {"text": "C."}]},
        {"type": "equation", "sentences": []},
        {"type": "equation", "sentences": []},
        {"type": "paragraph", "skip_reason": "page_furniture", "sentences": [{"text": "5 of 24"}]},
        {"type": "paragraph", "sentences": [{"text": "where x is the strain."}, {"text": "D."}, {"text": "E."}]},
        {"type": "heading", "sentences": [{"text": "3. Results"}]},
    ]
    assert eq_describe._text_near(blocks, 3, -1) == "B. C."
    assert eq_describe._text_near(blocks, 3, 1) == "where x is the strain. D."
    assert eq_describe._text_near(blocks, 1, -1) == ""  # a heading right before: nothing from the section before


def _eq_doc(latex: str) -> dict:
    return {"blocks": [
        {"id": "p0", "type": "paragraph", "sentences": [{"id": "s0", "text": "The jet radius follows"}]},
        {"id": "e1", "type": "equation", "eq_number": "3", "latex": latex, "page": 0, "bbox": [0, 0, 10, 10], "sentences": []},
        {"id": "p1", "type": "paragraph", "sentences": [{"id": "s1", "text": "where a is the growth rate."}]},
    ]}


def test_description_is_made_once_per_narrated_latex(tmp_path, monkeypatch):
    store = DocStore(tmp_path)
    (tmp_path / "d1").mkdir()
    doc = _eq_doc("R = a t")
    calls: list[list[dict]] = []
    monkeypatch.setattr(ollama, "models_for_jobs", lambda: {"reader": "m", "checker": "c"})
    monkeypatch.setattr(ollama, "chat", lambda model, msgs, **kw: calls.append(msgs) or "  The radius grows\n linearly.  ")
    e = eq_describe.describe(store, "d1", doc, doc["blocks"][1])
    assert e == {"description": "The radius grows linearly.", "latex": "R = a t", "model": "m"}
    user = calls[0][1]["content"]
    assert "The jet radius follows" in user and "where a is the growth rate." in user and "LaTeX: R = a t" in user
    eq_describe.describe(store, "d1", doc, doc["blocks"][1])
    assert len(calls) == 1  # cached
    # The second reading of the page chose other LaTeX: the description is made again from it.
    store.write_json("d1", "equations.json", {"e1": {"latex": "R = b t", "source": {"status": "page"}}})
    assert eq_describe.cached(store, "d1", doc["blocks"][1], {"latex": "R = b t", "source": {}}) is None
    eq_describe.describe(store, "d1", doc, doc["blocks"][1])
    assert len(calls) == 2 and "LaTeX: R = b t" in calls[1][1]["content"]
    assert spoken_for(doc["blocks"][1], "It grows.") == "Equation 3. AI description: It grows."


def test_descriptions_start_with_it():
    assert tidy("This equation calculates the shear stress,\n  represented by tau.") == "It calculates the shear stress, represented by tau."
    assert tidy("The equation balances forces.") == "It balances forces."
    assert tidy("This equation, which follows from (8), gives") == "This equation, which follows from (8), gives"
    assert tidy("Shear stress equals") == "Shear stress equals"


def test_without_latex_the_model_reads_the_page(tmp_path, monkeypatch):
    store = DocStore(tmp_path)
    (tmp_path / "d1").mkdir()
    doc = _eq_doc("")
    seen: dict = {}
    monkeypatch.setattr(ollama, "models_for_jobs", lambda: {"reader": "m", "checker": "c"})
    monkeypatch.setattr(ollama, "chat", lambda model, msgs, **kw: seen.update(kw, msgs=msgs) or "It sums the rates.")
    monkeypatch.setattr(eq_describe, "crop_png", lambda *a, **k: b"png")
    assert eq_describe.describe(store, "d1", doc, doc["blocks"][1])["description"] == "It sums the rates."
    assert seen["images"] == [b"png"] and "The equation is in the image." in seen["msgs"][1]["content"]
