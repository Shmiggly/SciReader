"""Figure mentions in running text (forms seen in the sample papers), mention boxes and the description queue."""

from scireader.llm.figures import caption_part, find_mentions, next_key, parse_refs, span_rects, split_key


def refs(text: str) -> list[tuple[str, str, str]]:
    """(matched text, figure number, panels) for each reference."""
    return [(text[a:z], n, "".join(sorted({c.lower() for c in p}))) for a, z, n, p in parse_refs(text)]


def test_case_and_style_variants():
    assert refs("as depicted in figure 1.") == [("figure 1", "1", "")]  # IOP writes it in lowercase
    assert refs("see FIG. 3 and Fig.4") == [("FIG. 3", "3", ""), ("Fig.4", "4", "")]
    assert refs("listed in Fig. 2A. Plotted in Fig. 3B)") == [("Fig. 2A", "2", "a"), ("Fig. 3B", "3", "b")]
    assert refs("in figure 4(a), and in figure 4(c), respectively") == [("figure 4(a)", "4", "a"), ("figure 4(c)", "4", "c")]
    assert refs("Figure 5 (a) , there was") == [("Figure 5 (a)", "5", "a")]


def test_panel_lists_and_ranges():
    assert refs("(Fig. 2a-c) with") == [("Fig. 2a-c", "2", "abc")]
    assert refs("Fig. 5a, b for the two") == [("Fig. 5a, b", "5", "ab")]
    assert refs("(Fig. 3 (b)-(e))") == [("Fig. 3 (b)-(e)", "3", "bcde")]
    assert refs("Fig. 1 (b) and (c) show") == [("Fig. 1 (b) and (c)", "1", "bc")]
    assert refs("As Fig. 4 (m-p) show") == [("Fig. 4 (m-p)", "4", "mnop")]
    assert refs("in Fig. 4ai-ii and Fig. 6aii, we") == [("Fig. 4ai-ii", "4", "a"), ("Fig. 6aii", "6", "a")]
    assert refs("Fig. 6a (upper left)") == [("Fig. 6a", "6", "a")]


def test_words_after_the_number_are_not_panels():
    assert refs("in Fig. 2 a clear trend") == [("Fig. 2", "2", "")]
    assert refs("Fig. 1a, which shows") == [("Fig. 1a", "1", "a")]
    assert refs("see Fig. 2 (top) and Fig. 3)") == [("Fig. 2", "2", ""), ("Fig. 3", "3", "")]
    assert refs("Fig. 2a and I think") == [("Fig. 2a", "2", "a")]
    assert refs("Figure 3D printing") == [("Figure 3D", "3", "d")]  # can't be told apart; papers write "3D-printed"


def test_plural_lists_and_ranges():
    assert refs("Figures 16 and 17 show") == [("Figures 16", "16", ""), ("17", "17", "")]
    assert refs("(Figures 9-10)") == [("Figures 9", "9", ""), ("10", "10", "")]
    assert [n for _, n, _ in refs("Figs. 2–4 and 6")] == ["2", "3", "4", "6"]
    assert refs("From figures 4(a), (c), and 5(a), (c), we") == [("figures 4(a), (c)", "4", "ac"), ("5(a), (c)", "5", "ac")]
    assert refs("In Fig. 2, 3 curves") == [("Fig. 2", "2", "")]  # a singular word lists one figure


def test_supplementary_and_non_references():
    assert refs("see Fig. S3b-d and Fig. S4 in the SI") == []
    assert refs("Supplementary Fig. 3 and Supplementary Information Figure 2") == []
    assert refs("a figure of merit 1.2, configure 3 nodes") == []
    assert refs("in Fig. 3.5 of the thesis") == []


def _doc() -> dict:
    sent = lambda sid, text: {"id": sid, "text": text, "spoken": text, "rects": []}  # noqa: E731
    return {
        "figures": [
            {"id": "fig0", "kind": "figure", "number": "1"},
            {"id": "fig1", "kind": "figure", "number": "2"},
            {"id": "fig2", "kind": "table", "number": "1"},
            {"id": "fig3", "kind": "figure", "number": None},
        ],
        "blocks": [
            {"type": "paragraph", "sentences": [sent("s0", "As shown in figure 1, the jet bends (Fig. 2a).")]},
            {"type": "caption", "sentences": [sent("s1", "Figure 1. The jet.")]},
            {"type": "paragraph", "sentences": [sent("s2", "Figure 2a, b and Figure 7 compare it with figure 1.")]},
            {"type": "paragraph", "skip_reason": "footnote", "sentences": [sent("s3", "Figure 2.")]},
        ],
    }


def test_find_mentions_first_flags_and_targets():
    ms = find_mentions(_doc())
    assert [(m["sentence_id"], m["key"], m["first"]) for m in ms] == [
        ("s0", "1", True), ("s0", "2a", True), ("s2", "2ab", True), ("s2", "1", False),
    ]  # captions and skipped blocks hold no mentions; Figure 7 doesn't exist
    assert ms[1]["figure_id"] == "fig1" and ms[1]["panels"] == ["a"] and ms[1]["span"] == [37, 44]
    assert "rects" not in ms[0]


def test_mention_boxes_from_word_boxes():
    # "As shown in figure 1, the jet": words "figure" and "1," on one line; a mention across a line break.
    entry = {"words": [[0, 2, [[0, 50, 100, 60, 110]]], [12, 18, [[0, 112, 100, 140, 110]]],
                       [19, 21, [[0, 142, 100, 150, 110]]], [22, 25, [[0, 50, 112, 66, 122]]]]}
    assert span_rects(entry, 12, 20) == [[0, 112, 100, 150, 110]]
    assert span_rects(entry, 19, 25) == [[0, 142, 100, 150, 110], [0, 50, 112, 66, 122]]
    assert span_rects(None, 0, 5) == []
    speech = {"s0": {"words": [[12, 18, [[0, 112, 100, 140, 110]]], [19, 21, [[0, 142, 100, 150, 110]]]]}}
    assert find_mentions(_doc(), speech)[0]["rects"] == [[0, 112, 100, 150, 110]]


def test_description_queue_order():
    keys = ["1", "2a", "3", "4b"]
    assert next_key(keys, set(), []) == "1"
    assert next_key(keys, {"1"}, ["4b", "3"]) == "4b"  # the reader's position goes first
    assert next_key(keys, {"1", "4b"}, ["4b", "3"]) == "3"
    assert next_key(keys, {"1"}, ["9z"]) == "2a"  # unknown targets are ignored
    assert next_key(keys, set(keys), ["3"]) is None


def test_keys_and_caption_parts():
    assert split_key("12") == ("12", []) and split_key("4mnop") == ("4", ["m", "n", "o", "p"])
    assert split_key("fig3") is None and split_key("3B") is None
    cap = "Figure 2: Breakdown of our data set. (A) The symbol and name of each property. (B) Counts per property."
    assert caption_part(cap, ["b"]) == "Breakdown of our data set. (B) Counts per property."
    assert caption_part("figure 3. Profiles. (a) Velocity. (b) Pressure.", ["a"]) == "Profiles. (a) Velocity."
