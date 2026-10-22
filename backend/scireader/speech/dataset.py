"""Pronunciation dataset: one file per user that builds over time, in the same structure for everyone.

The repo ships the base list (``lexicons/science-en.json``). A user's dataset (``<data>/pronunciations.json``) starts as
a copy of it and grows with every pronunciation they give, confirm or import; entries added to the base list in an
update flow in, except ones the user removed, and entries the user changed are never overwritten. The base list, a
personal dataset, an export and a list shared online are the same format, so a dataset moves between users as one
file. Two entries for the same term that sound different (after an import, say) both stay until the user picks one;
until then the first is spoken.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from .lexicon import Lexicon, LexiconEntry

FORMAT = "scireader-pronunciations"
VERSION = 2
KINDS = ("acronym", "word", "molecule", "formula", "unit", "symbol", "name", "other")
T = TypeVar("T")


def today() -> str:
    return date.today().isoformat()


def same_term(a: LexiconEntry, b: LexiconEntry) -> bool:
    """Entries for the same thing: the same term ("Tg" is not "TG", unless either entry ignores case)."""
    if a.case_sensitive and b.case_sensitive:
        return a.term == b.term
    return a.term.lower() == b.term.lower()


def _sound(e: LexiconEntry) -> tuple[str, str]:
    return re.sub(r"[\s\-]+", " ", (e.say_as or e.term).strip().lower()), (e.ipa or "").strip()


def same_sound(a: LexiconEntry, b: LexiconEntry) -> bool:
    """Two entries say the term the same way ("P-L-A" = "P L A")."""
    return _sound(a) == _sound(b)


@dataclass
class Dataset:
    entries: list[LexiconEntry] = field(default_factory=list)
    name: str = "My SciReader pronunciations"
    language: str = "en"
    license: str | None = "CC BY 4.0"
    removed: list[str] = field(default_factory=list)  # base-list terms the user removed (updates don't bring them back)
    base_hash: str | None = None  # the base list this dataset last took updates from

    # ---------------------------------------------------------------- the file
    @classmethod
    def from_json(cls, data: Any, default_source: str = "import") -> "Dataset":
        """A dataset (this format), an older lexicon file ({"entries": [...]}) or a bare list of entries."""
        if isinstance(data, list):
            raw, meta = data, {}
        elif isinstance(data, dict) and isinstance(data.get("entries"), list):
            raw, meta = data["entries"], data
        else:
            raise ValueError("not a pronunciation dataset: expected a list of entries")
        entries = []
        for d in raw:
            if isinstance(d, dict) and str(d.get("term") or "").strip():
                entries.append(LexiconEntry.from_dict(d, default_source))
        return cls(entries=entries, name=str(meta.get("name") or cls.name), language=str(meta.get("language") or "en"),
                   license=meta.get("license", cls.license), removed=[str(t) for t in meta.get("removed") or []],
                   base_hash=meta.get("base_hash"))

    def to_json(self) -> dict:
        return {
            "format": FORMAT,
            "version": VERSION,
            "language": self.language,
            "name": self.name,
            "license": self.license,
            "updated": today(),
            "base_hash": self.base_hash,
            "removed": sorted(set(self.removed), key=str.lower),
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def read(cls, path: str | Path, default_source: str = "me") -> "Dataset":
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")), default_source)

    def write(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(p)

    # ---------------------------------------------------------------- lookups
    def group(self, entry: LexiconEntry) -> list[int]:
        """Indices of the entries for the same term as `entry`."""
        low = entry.term.lower()
        return [i for i, e in enumerate(self.entries) if e.term.lower() == low and same_term(e, entry)]

    def first(self, term: str) -> LexiconEntry | None:
        idx = self.group(LexiconEntry(term))
        return self.entries[idx[0]] if idx else None

    def duplicates(self) -> list[list[int]]:
        """Groups of entries for one term that sound different (the user picks one), in dataset order."""
        buckets: dict[str, list[int]] = {}
        for i, e in enumerate(self.entries):
            buckets.setdefault(e.term.lower(), []).append(i)
        out = []
        for idx in buckets.values():
            if len(idx) < 2:
                continue
            seen: list[list[int]] = []
            for i in idx:
                g = next((g for g in seen if same_term(self.entries[g[0]], self.entries[i])), None)
                if g is None:
                    seen.append([i])
                else:
                    g.append(i)
            out.extend(g for g in seen if len(g) > 1)
        return sorted(out)

    def lexicon(self) -> Lexicon:
        """What the voice uses: the first entry for each term."""
        chosen: list[LexiconEntry] = []
        for e in self.entries:
            if not any(same_term(c, e) for c in chosen if c.term.lower() == e.term.lower()):
                chosen.append(e)
        return Lexicon(chosen, language=self.language, name=self.name)

    # ---------------------------------------------------------------- changes
    def put(self, entry: LexiconEntry) -> LexiconEntry:
        """The user's pronunciation of a term: replaces every entry for it (a pick between duplicates, or an edit),
        at the place of the first one."""
        entry = replace(entry, source="me", checked=True, added=entry.added or today())
        idx = self.group(entry)
        if idx:
            self.entries[idx[0]] = entry
            for i in reversed(idx[1:]):
                del self.entries[i]
        else:
            self.entries.append(entry)
        self.removed = [t for t in self.removed if t.lower() != entry.term.lower()]
        return entry

    def keep(self, term: str, index: int, case_sensitive: bool = True) -> LexiconEntry | None:
        """Resolve duplicates: keep the `index`-th entry of the term's group, drop the others."""
        idx = self.group(LexiconEntry(term, case_sensitive=case_sensitive))
        if not 0 <= index < len(idx):
            return None
        kept = replace(self.entries[idx[index]], checked=True)
        for i in reversed(idx):
            del self.entries[i]
        self.entries.insert(idx[0], kept)
        return kept

    def check(self, term: str, case_sensitive: bool = True) -> bool:
        """The user heard an entry and confirmed it."""
        idx = self.group(LexiconEntry(term, case_sensitive=case_sensitive))
        for i in idx:
            self.entries[i] = replace(self.entries[i], checked=True)
        return bool(idx)

    def remove(self, term: str, index: int | None = None, case_sensitive: bool = True) -> int:
        """Remove a term (or one entry of its group); a removed base-list term stays out of updates."""
        idx = self.group(LexiconEntry(term, case_sensitive=case_sensitive))
        drop = idx if index is None else idx[index:index + 1]
        for i in reversed(drop):
            if self.entries[i].source == "base" and index is None:
                self.removed.append(self.entries[i].term)
            del self.entries[i]
        return len(drop)

    def merge(self, incoming: Iterable[LexiconEntry], source: str) -> dict:
        """Import entries: new terms are added, ones that sound the same are skipped, ones that sound different are
        added next to the existing entry (two entries for the term, for the user to resolve)."""
        added = same = duplicates = 0
        for e in incoming:
            idx = self.group(e)
            if any(same_sound(self.entries[i], e) for i in idx):
                same += 1
                continue
            self.entries.append(replace(e, source=source, added=today()))
            if idx:
                duplicates += 1
            else:
                added += 1
        return {"added": added, "same": same, "duplicates": duplicates}

    def sync_base(self, base: Iterable[LexiconEntry], base_hash: str) -> dict:
        """Take updates of the base list: new terms (unless the user removed them) and new pronunciations of entries
        still as the base list had them."""
        added = updated = 0
        removed = {t.lower() for t in self.removed}
        for b in base:
            b = replace(b, source="base")
            idx = self.group(b)
            if not idx:
                if b.term.lower() not in removed:
                    self.entries.append(replace(b, added=b.added or today()))
                    added += 1
                continue
            for i in idx:
                e = self.entries[i]
                if e.source == "base" and (not same_sound(e, b) or (e.note, e.tags, e.kind) != (b.note, b.tags, b.kind)):
                    self.entries[i] = replace(b, added=e.added, checked=e.checked or b.checked)
                    updated += 1
        self.base_hash = base_hash
        return {"added": added, "updated": updated}


# ---------------------------------------------------------------------------------------------
# The user's dataset on disk


_lock = threading.RLock()


def _paths() -> tuple[Path, Path, Path]:
    from ..config import get_settings

    s = get_settings()
    return s.pronunciations_path, s.lexicon_path, s.user_lexicon_path


def base_list(base_path: Path) -> tuple[list[LexiconEntry], str]:
    if not base_path.exists():
        return [], ""
    data = base_path.read_bytes()
    return Dataset.from_json(json.loads(data.decode("utf-8")), "base").entries, hashlib.sha256(data).hexdigest()[:16]


def open_dataset(paths: tuple[Path, Path, Path] | None = None) -> Dataset:
    """The user's dataset (personal file, base list, older user lexicon): until the user first changes it, the base
    list plus their entries from the older user lexicon file; brought up to date with the base list in memory (saved
    with the next change), so reading never writes."""
    p, b, u = paths or _paths()
    with _lock:
        base, h = base_list(b)
        if p.exists():
            ds = Dataset.read(p)
        else:
            ds = Dataset()
            if u.exists():
                for e in Dataset.read(u).entries:
                    ds.put(e)
        if ds.base_hash != h:
            ds.sync_base(base, h)
        return ds


def update_dataset(fn: Callable[[Dataset], T], paths: tuple[Path, Path, Path] | None = None) -> T:
    """Change the user's dataset and save it."""
    p = (paths or _paths())[0]
    with _lock:
        ds = open_dataset(paths)
        out = fn(ds)
        ds.write(p)
        return out
