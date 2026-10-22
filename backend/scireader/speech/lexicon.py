"""Pronunciation lexicon: shipped entries + user overrides, whole-word matching.

Spoken replacement of an entry:
- ``ipa`` set  → misaki inline-phoneme markup ``[term](/ipa/)`` (verified with misaki 0.9.4:
  ``"The [PEGDA](/pˈɛɡdə/) resin."`` → ``ðə pˈɛɡdə ɹˈɛzᵊn.``). Use :func:`strip_markup` for display.
- otherwise    → ``say_as`` (a respelling such as "peg-dah"), or the term itself.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

SHIPPED_EN = Path(__file__).resolve().parents[3] / "lexicons" / "science-en.json"

_MARKUP_RE = re.compile(r"\[([^\]\[]+)\]\(/[^)]*/\)")


def strip_markup(spoken: str) -> str:
    """Turn misaki inline phoneme markup ``[term](/ipa/)`` back into ``term``."""
    return _MARKUP_RE.sub(r"\1", spoken)


# Older files said "shipped" / "user" / "imported" for what the dataset calls "base" / "me" / "import".
_SOURCES = {"shipped": "base", "user": "me", "imported": "import"}


@dataclass
class LexiconEntry:
    term: str
    say_as: str | None = None  # None: read as written
    ipa: str | None = None
    case_sensitive: bool = True
    tags: list[str] = field(default_factory=list)
    source: str = "me"  # "base" (the SciReader list), "me", or "import:<dataset>"
    note: str | None = None
    kind: str | None = None  # acronym, word, molecule, formula, unit, symbol, name, other
    checked: bool = True  # False: proposed or imported, not yet heard and confirmed
    added: str | None = None  # date it entered the dataset (YYYY-MM-DD)

    @property
    def spoken(self) -> str:
        if self.ipa:
            return f"[{self.term}](/{self.ipa.strip('/')}/)"
        return self.say_as if self.say_as is not None else self.term

    def same_pronunciation(self, other: "LexiconEntry") -> bool:
        return (self.say_as, self.ipa, self.case_sensitive) == (other.say_as, other.ipa, other.case_sensitive)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any], default_source: str = "me") -> "LexiconEntry":
        if not d.get("term") or not str(d["term"]).strip():
            raise ValueError(f"lexicon entry without term: {d!r}")
        source = str(d.get("source") or default_source)
        return cls(
            term=str(d["term"]).strip(),
            say_as=(str(d["say_as"]).strip() or None) if d.get("say_as") is not None else None,
            ipa=d.get("ipa") or None,
            case_sensitive=bool(d.get("case_sensitive", True)),
            tags=[str(t) for t in d.get("tags") or []],
            source=_SOURCES.get(source, source),
            note=d.get("note") or None,
            kind=d.get("kind") or None,
            checked=bool(d.get("checked", True)),
            added=d.get("added") or None,
        )


@dataclass
class LexiconConflict:
    term: str
    mine: LexiconEntry
    theirs: LexiconEntry


def read_entries(path: str | Path, default_source: str = "user") -> list[LexiconEntry]:
    """Entries of a lexicon JSON file; a missing file is an empty lexicon."""
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    raw = data.get("entries", []) if isinstance(data, dict) else data
    return [LexiconEntry.from_dict(d, default_source) for d in raw]


def write_entries(path: str | Path, entries: Iterable[LexiconEntry], *, name: str = "", language: str = "en") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": 1,
        "language": language,
        "name": name,
        "entries": [e.to_dict() for e in sorted(entries, key=lambda e: e.term.lower())],
    }
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Lexicon:
    def __init__(
        self,
        shipped: Iterable[LexiconEntry] = (),
        user: Iterable[LexiconEntry] = (),
        *,
        language: str = "en",
        name: str = "",
    ) -> None:
        self.language = language
        self.name = name
        self._shipped: dict[str, LexiconEntry] = {e.term: e for e in shipped}
        self._user: dict[str, LexiconEntry] = {e.term: e for e in user}
        self._regex: re.Pattern[str] | None = None
        self._cs: dict[str, LexiconEntry] = {}
        self._ci: dict[str, LexiconEntry] = {}

    # ---------------------------------------------------------------- loading / saving
    @classmethod
    def load(cls, shipped_path: str | Path | None = SHIPPED_EN, user_path: str | Path | None = None) -> "Lexicon":
        shipped = read_entries(shipped_path, "shipped") if shipped_path else []
        user = read_entries(user_path, "user") if user_path else []
        name = ""
        if shipped_path and Path(shipped_path).exists():
            try:
                name = json.loads(Path(shipped_path).read_text(encoding="utf-8")).get("name", "")
            except (ValueError, AttributeError):
                name = ""
        return cls(shipped, user, name=name)

    def save_user(self, path: str | Path) -> None:
        write_entries(path, self._user.values(), name="user", language=self.language)

    def export(self, path: str | Path, *, name: str | None = None) -> None:
        """Write the merged lexicon (shipped + user overrides) for sharing."""
        write_entries(path, self.entries, name=name or self.name or "export", language=self.language)

    # ---------------------------------------------------------------- entries
    @property
    def entries(self) -> list[LexiconEntry]:
        merged = dict(self._shipped)
        merged.update(self._user)
        return list(merged.values())

    @property
    def user_entries(self) -> list[LexiconEntry]:
        return list(self._user.values())

    def get(self, term: str) -> LexiconEntry | None:
        return self._user.get(term) or self._shipped.get(term)

    def add(self, entry: LexiconEntry) -> None:
        """Add or replace a user entry (overrides a shipped entry with the same term)."""
        self._user[entry.term] = entry
        self._regex = None

    def remove(self, term: str) -> bool:
        removed = self._user.pop(term, None) is not None
        self._regex = None
        return removed

    def merge(self, other: "Lexicon | Iterable[LexiconEntry]") -> list[LexiconConflict]:
        """Import entries: new terms are added as user entries; identical ones are skipped;
        differing ones are NOT applied and returned as conflicts (the caller decides
        "keep mine" or "take theirs" via :meth:`add`)."""
        incoming = other.entries if isinstance(other, Lexicon) else list(other)
        conflicts: list[LexiconConflict] = []
        for e in incoming:
            mine = self.get(e.term)
            if mine is None:
                self.add(e)
            elif not mine.same_pronunciation(e):
                conflicts.append(LexiconConflict(e.term, mine, e))
        return conflicts

    # ---------------------------------------------------------------- matching
    def _compile(self) -> re.Pattern[str]:
        entries = self.entries
        self._cs = {e.term: e for e in entries if e.case_sensitive}
        self._ci = {e.term.lower(): e for e in entries if not e.case_sensitive}
        alts = []
        for e in sorted(entries, key=lambda e: len(e.term), reverse=True):
            t = re.escape(e.term)
            alts.append(t if e.case_sensitive else f"(?i:{t})")
        if not alts:
            pattern = r"(?!x)x"
        else:
            pattern = r"(?<![\w])(?:" + "|".join(alts) + r")(?![\w])"
        self._regex = re.compile(pattern)
        return self._regex

    def find(self, text: str) -> list[tuple[int, int, str]]:
        """Whole-word, longest-first matches → (start, end, spoken replacement)."""
        return [(a, b, e.spoken) for a, b, e in self.find_entries(text)]

    def find_entries(self, text: str) -> list[tuple[int, int, LexiconEntry]]:
        """Whole-word, longest-first matches → (start, end, entry)."""
        rx = self._regex or self._compile()
        out = []
        for m in rx.finditer(text):
            s = m.group()
            e = self._cs.get(s) or self._ci.get(s.lower())
            if e is not None:
                out.append((m.start(), m.end(), e))
        return out

    def __len__(self) -> int:
        return len(self.entries)
