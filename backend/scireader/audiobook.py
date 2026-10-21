"""Audiobook export: one MP3 chapter per section, zipped with an M3U playlist (for listening away from the screen)."""

from __future__ import annotations

import io
import re
import threading
import traceback
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

from .speech.pipeline import speak
from .store.docs import DocStore
from .tts.engine import audio_path, synth_cached

SR = 24000
_status: dict[str, dict] = {}
_lock = threading.Lock()


def status(doc_id: str) -> dict:
    with _lock:
        return dict(_status.get(doc_id, {"state": "idle"}))


def start(store: DocStore, doc_id: str, voice: str, eq_mode: str = "auto") -> dict:
    with _lock:
        if _status.get(doc_id, {}).get("state") == "running":
            return dict(_status[doc_id])
        _status[doc_id] = {"state": "running", "progress": 0.0, "message": "Starting"}
    threading.Thread(target=_run, args=(store, doc_id, voice, eq_mode), daemon=True).start()
    return status(doc_id)


def output_path(store: DocStore, doc_id: str) -> Path:
    return store.dir(doc_id) / "audiobook.zip"


def _chapters(doc: dict, speech: dict, eqs: dict, eq_mode: str) -> list[tuple[str, list[str]]]:
    from .api.tts import equation_spoken

    chapters: list[tuple[str, list[str]]] = [("Opening", [doc.get("title", "") + "."])]
    for b in doc["blocks"]:
        if b["type"] in ("figure", "table", "title") or (b.get("skip_reason") and b["type"] != "caption"):
            continue
        if b["type"] == "heading":
            title = b["sentences"][0]["text"] if b["sentences"] else "Section"
            chapters.append((title, [f"{title.rstrip('.')}."]))
            continue
        for s in b["sentences"]:
            if b["type"] == "equation":
                chapters[-1][1].append(equation_spoken(b, eq_mode, eqs.get(b["id"])))
            else:
                drop = [tuple(x) for x in speech.get(s["id"], {}).get("drop", [])]
                chapters[-1][1].append(speak(s["text"], drop).spoken)
    return [(t, lines) for t, lines in chapters if len(lines) > (0 if t == "Opening" else 1)]


def _run(store: DocStore, doc_id: str, voice: str, eq_mode: str) -> None:
    try:
        doc = store.document(doc_id)
        speech = store.read_json(doc_id, "speech.json") or {}
        eqs = store.read_json(doc_id, "equations.json") or {}
        chapters = _chapters(doc, speech, eqs, eq_mode)
        total = sum(len(lines) for _, lines in chapters)
        done = 0
        gap = np.zeros(int(0.28 * SR), dtype=np.float32)
        out = output_path(store, doc_id)
        tmp = out.with_suffix(".tmp")
        playlist = ["#EXTM3U"]
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as zf:
            for n, (title, lines) in enumerate(chapters, 1):
                parts = []
                for line in lines:
                    key, _ = synth_cached(line, voice)
                    data, _sr = sf.read(audio_path(key), dtype="float32")
                    parts.extend([data, gap])
                    done += 1
                    with _lock:
                        _status[doc_id].update(progress=round(done / max(1, total), 3), message=f"Chapter {n}/{len(chapters)}: {title[:40]}")
                audio = np.concatenate(parts) if parts else gap
                buf = io.BytesIO()
                sf.write(buf, audio, SR, format="MP3", subtype="MPEG_LAYER_III")
                name = f"{n:02d} - {re.sub(r'[^A-Za-z0-9 ,.()-]+', '', title)[:60].strip() or 'Section'}.mp3"
                zf.writestr(name, buf.getvalue())
                playlist += [f"#EXTINF:{int(len(audio) / SR)},{title}", name]
            zf.writestr("playlist.m3u", "\n".join(playlist) + "\n")
            zf.writestr("README.txt", (
                f"{doc.get('title', '')}\nAudiobook made by SciReader (offline, Kokoro voice '{voice}').\n"
                "Body text is read verbatim with science-aware normalization; citation markers, page furniture and "
                "the reference list are skipped. Equations use verified AI narration when it passed the check, "
                "otherwise a rule-based reading.\n"))
        tmp.replace(out)
        with _lock:
            _status[doc_id] = {"state": "done", "progress": 1.0, "message": f"{len(chapters)} chapters ready",
                               "chapters": len(chapters)}
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        with _lock:
            _status[doc_id] = {"state": "error", "progress": 0.0, "message": str(exc)}
