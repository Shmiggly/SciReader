// Pronunciation review: terms in this paper the voice will probably say badly. Hear how each sounds now,
// type how it should sound, preview, save to your lexicon (applies everywhere at once). Export / import.
import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { clearSpeechCache, useStore } from "./store";

interface Term {
  term: string;
  count: number;
  kind: string;
  sentence_id: string;
  snippet: string;
  in_lexicon: boolean;
  say_as: string | null;
  source: string | null;
}
interface Conflict {
  term: string;
  mine: { say_as: string | null };
  theirs: { say_as: string | null };
}

export function Pronunciation({ onClose }: { onClose: () => void }) {
  const doc = useStore((s) => s.doc)!;
  const voice = useStore((s) => s.voice);
  const [terms, setTerms] = useState<Term[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<{ lexicon: unknown; list: Conflict[]; choice: Record<string, string> } | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = () => api.get<{ terms: Term[] }>(`/api/docs/${doc.id}/pronunciation`).then((r) => setTerms(r.terms), (e) => setMsg(String(e)));
  useEffect(() => {
    void load();
  }, [doc.id]);

  const say = async (key: string, text: string) => {
    setBusy(key);
    try {
      const r = await api.post<{ audio_url: string }>("/api/tts/say", { text, voice });
      audio.current?.pause();
      audio.current = new Audio(r.audio_url);
      await audio.current.play();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  };

  const preview = (t: Term) => {
    const d = drafts[t.term];
    if (!d) return;
    const re = new RegExp(`(?<![\\w-])${t.term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w])`, "g");
    void say(`pv:${t.term}`, t.snippet.replace(re, d));
  };

  const save = async (t: Term) => {
    const d = drafts[t.term]?.trim();
    if (!d) return;
    setBusy(`save:${t.term}`);
    try {
      await api.put("/api/lexicon/user", { term: t.term, say_as: d, case_sensitive: true, tags: [], note: `from ${doc.title.slice(0, 60)}` });
      clearSpeechCache();
      setMsg(`Saved: ${t.term} → “${d}”. It now applies in every paper.`);
      await load();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  };

  const doImport = async (lexicon: unknown, decisions: Record<string, string> = {}) => {
    try {
      const r = await api.post<{ added: number; conflicts: Conflict[] }>("/api/lexicon/import", { lexicon, decisions });
      if (r.conflicts.length) {
        setConflicts({ lexicon, list: r.conflicts, choice: Object.fromEntries(r.conflicts.map((c) => [c.term, "mine"])) });
      } else {
        setConflicts(null);
        clearSpeechCache();
        setMsg(`Imported ${r.added} new pronunciations.`);
        await load();
      }
    } catch (e) {
      setMsg(String(e));
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Pronunciation">
        <div className="panel-head">
          <h2>Pronunciation</h2>
          <div className="row">
            <a className="button-like" href="/api/lexicon/export" download="scireader-lexicon.json">Export my lexicon</a>
            <button onClick={() => fileInput.current?.click()}>Import…</button>
            <input
              ref={fileInput}
              type="file"
              accept="application/json,.json"
              hidden
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                try {
                  void doImport(JSON.parse(await f.text()));
                } catch {
                  setMsg("That file isn't a lexicon (JSON) file.");
                }
              }}
            />
            <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
          </div>
        </div>
        <div className="muted small">
          Terms in this paper that the voice will probably say badly, most frequent first. ▶ hears it in context now; type how it should
          sound (plain respelling like “peg-dah”, or letters like “T G”), preview, and save. Saved terms go to your own lexicon, which
          overrides the shipped science lexicon and applies everywhere at once.
        </div>
        {msg && <div className="offline ok">{msg}</div>}
        {conflicts && (
          <div className="card">
            <b>Some imported terms differ from yours</b>
            {conflicts.list.map((c) => (
              <div key={c.term} className="row">
                <b>{c.term}</b>
                <label className="check">
                  <input type="radio" checked={conflicts.choice[c.term] === "mine"} onChange={() => setConflicts({ ...conflicts, choice: { ...conflicts.choice, [c.term]: "mine" } })} />
                  keep mine (“{c.mine.say_as}”)
                </label>
                <label className="check">
                  <input type="radio" checked={conflicts.choice[c.term] === "theirs"} onChange={() => setConflicts({ ...conflicts, choice: { ...conflicts.choice, [c.term]: "theirs" } })} />
                  take theirs (“{c.theirs.say_as}”)
                </label>
              </div>
            ))}
            <button className="primary" onClick={() => void doImport(conflicts.lexicon, conflicts.choice)}>Apply</button>
          </div>
        )}
        {!terms ? (
          <div className="muted">Finding terms…</div>
        ) : (
          <table className="pron-table">
            <thead>
              <tr>
                <th>Term</th>
                <th>Count</th>
                <th>How it sounds now</th>
                <th>Say it like</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {terms.map((t) => (
                <tr key={t.term}>
                  <td>
                    <b>{t.term}</b>
                    <div className="muted small">{t.kind}{t.in_lexicon ? ` · in ${t.source} lexicon: “${t.say_as}”` : ""}</div>
                  </td>
                  <td>{t.count}</td>
                  <td>
                    <button onClick={() => void say(`now:${t.term}`, t.snippet)} disabled={busy === `now:${t.term}`} title={t.snippet}>
                      {busy === `now:${t.term}` ? "…" : "▶"}
                    </button>{" "}
                    <span className="muted small">…{t.snippet.slice(0, 60)}…</span>
                  </td>
                  <td>
                    <input
                      value={drafts[t.term] ?? ""}
                      placeholder={t.say_as ?? "e.g. peg-dah"}
                      onChange={(e) => setDrafts({ ...drafts, [t.term]: e.target.value })}
                      onKeyDown={(e) => e.key === "Enter" && void save(t)}
                    />
                  </td>
                  <td className="nowrap">
                    <button onClick={() => preview(t)} disabled={!drafts[t.term]} title="Preview">▶</button>{" "}
                    <button className="primary" onClick={() => void save(t)} disabled={!drafts[t.term] || busy === `save:${t.term}`}>Save</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
