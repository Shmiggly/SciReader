"""Reload (a new build of a parsed paper): when it runs, and which equation checks survive it."""

from scireader.api import jobs
from scireader.api.jobs import changed_equations
from scireader.llm import equations
from scireader.store.docs import DocStore


def test_reload_waits_for_running_equation_checks(tmp_path, monkeypatch):
    store = DocStore(tmp_path)
    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "document.json").write_text("{}", encoding="utf-8")
    assert jobs.start_parse("d1", store)["state"] == "ready"  # already parsed: opening it doesn't parse again
    monkeypatch.setattr(equations, "status", lambda doc_id: {"state": "running"})
    st = jobs.start_parse("d1", store, rebuild=True)
    assert st["state"] == "error" and "still running" in st["message"]


def _eq(bid: str, latex: str, number: str | None = None, page: int = 0, bbox: list | None = None) -> dict:
    return {"id": bid, "type": "equation", "latex": latex, "page": page, "bbox": bbox or [1, 2, 3, 4], "eq_number": number}


def test_only_equations_that_changed_lose_their_checks():
    old = {"blocks": [_eq("b1", "a=b"), _eq("b2", "c=d"), _eq("b3", "e=f"), _eq("b5", "g=h"), {"id": "b4", "type": "paragraph"}]}
    new = {"blocks": [
        _eq("b1", "a=b", number="1"),  # newly numbered: same formula, its check stays
        _eq("b2", "c=d+1"),  # the LaTeX cleanup changed it
        {"id": "b3", "type": "paragraph"},  # the id now holds text
        _eq("b5", "g=h", bbox=[1, 2, 3, 9]),  # another place on the page
        _eq("b6", "x=y"),  # new: it has no check yet anyway
    ]}
    assert changed_equations(old, new) == {"b2", "b3", "b5"}
    assert changed_equations(old, old) == set()
