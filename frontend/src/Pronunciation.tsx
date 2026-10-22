// Pronunciations: the user's own dataset, which starts as the SciReader list and grows with every pronunciation they
// give, confirm or import. Top: this paper's terms the voice will probably say badly that the dataset doesn't have yet
// (give one a pronunciation and it goes into the dataset at once, moving down); then terms with two entries to choose
// between; then this paper's terms already in the dataset; then the whole dataset. Export / import (file or link).
import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { clearSpeechCache, useStore } from "./store";

interface Entry {
  term: string;
  say_as: string | null;
  ipa: string | null;
  kind: string | null;
  case_sensitive: boolean;
  tags: string[];
  note: string | null;
  source: string;
  checked: boolean;
  added: string | null;
  duplicate?: boolean;
}
interface Suggested {
  term: string;
  count: number;
  sentence_id: string;
  snippet: string;
  kind: string;
}
interface Known {
  term: string;
  count: number;
  sentence_id: string;
  snippet: string;
  entry: Entry;
  duplicate: boolean;
}
interface DupGroup {
  term: string;
  in_paper: boolean;
  entries: Entry[];
}
interface View {
  suggested: Suggested[];
  known: Known[];
  duplicates: DupGroup[];
  dataset: { entries: number; mine: number; unchecked: number; duplicates: number };
}

const KINDS = ["acronym", "word", "molecule", "formula", "unit", "symbol", "name", "other"];

function sourceLabel(source: string): string {
  if (source === "base") return "SciReader list";
  if (source === "me") return "yours";
  return source.startsWith("import:") ? `imported: ${source.slice(7)}` : source;
}

/** The term in a snippet replaced by a pronunciation (to hear a draft in context). */
function withDraft(snippet: string, term: string, say: string): string {
  const re = new RegExp(`(?<![\\w-])${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w])`, "g");
  return snippet.replace(re, say);
}

export function Pronunciation({ onClose }: { onClose: () => void }) {
  const doc = useStore((s) => s.doc)!;
  const voice = useStore((s) => s.voice);
  const [view, setView] = useState<View | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [moved, setMoved] = useState<string | null>(null);
  const [linkOpen, setLinkOpen] = useState(false);
  const [link, setLink] = useState("");
  const [browseKey, setBrowseKey] = useState(0);
  const [allSuggested, setAllSuggested] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const dupSection = useRef<HTMLElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = () => api.get<View>(`/api/docs/${doc.id}/pronunciation`).then(setView, (e) => setMsg(String(e)));
  useEffect(() => {
    void load();
  }, [doc.id]);
  useEffect(() => {
    if (!moved) return;
    document.querySelector(`[data-known="${CSS.escape(moved)}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
    const t = window.setTimeout(() => setMoved(null), 2500);
    return () => window.clearTimeout(t);
  }, [moved, view]);

  const changed = async () => {
    clearSpeechCache(); // the reader picks the new pronunciation up at once
    await load();
    setBrowseKey((k) => k + 1);
  };

  const say = async (key: string, text: string, raw = false) => {
    setBusy(key);
    try {
      const r = await api.post<{ audio_url: string }>("/api/tts/say", { text, voice, raw });
      audio.current?.pause();
      audio.current = new Audio(r.audio_url);
      await audio.current.play();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  };

  /** Give a term a pronunciation (empty: read as written): into the dataset at once. */
  const put = async (term: string, say_as: string | null, extra: Partial<Entry> = {}) => {
    setBusy(`put:${term}`);
    try {
      await api.put("/api/pronunciations/entry", { term, say_as, case_sensitive: true, tags: [], note: null, ...extra });
      setMsg(say_as ? `${term} → “${say_as}” is in your dataset now, for every paper.` : `${term} is in your dataset now: read as written.`);
      setMoved(term);
      await changed();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(null);
    }
  };
  const post = async (path: string, body: object, done: string) => {
    try {
      await api.post(path, body);
      setMsg(done);
      await changed();
    } catch (e) {
      setMsg(String(e));
    }
  };

  const imported = async (p: Promise<{ added: number; same: number; duplicates: number; name: string }>) => {
    try {
      const r = await p;
      setMsg(
        `Imported from ${r.name}: ${r.added} new pronunciation${r.added === 1 ? "" : "s"}` +
          (r.duplicates ? `, ${r.duplicates} that differ from yours (two entries, see below)` : "") +
          (r.same ? `, ${r.same} you already had` : "") + ".",
      );
      await changed();
    } catch (e) {
      setMsg(String(e));
    }
  };

  const ds = view?.dataset;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal pron" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Pronunciation">
        <div className="panel-head">
          <h2>Pronunciation</h2>
          <div className="row">
            <a className="button-like" href="/api/pronunciations/export" download="scireader-pronunciations.json" title="Your whole dataset, as one file anyone can import">
              Export my dataset
            </a>
            <button onClick={() => fileInput.current?.click()}>Import a file…</button>
            <button onClick={() => setLinkOpen((v) => !v)} aria-pressed={linkOpen}>Import from a link…</button>
            <input
              ref={fileInput}
              type="file"
              accept="application/json,.json"
              hidden
              onChange={async (e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (!f) return;
                let data: unknown;
                try {
                  data = JSON.parse(await f.text());
                } catch {
                  setMsg("That file isn't a pronunciation dataset (JSON).");
                  return;
                }
                void imported(api.post("/api/pronunciations/import", { dataset: data, name: f.name.replace(/\.json$/i, "") }));
              }}
            />
            <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
          </div>
        </div>
        {linkOpen && (
          <form
            className="row"
            onSubmit={(e) => {
              e.preventDefault();
              if (link.trim()) void imported(api.post("/api/pronunciations/import-url", { url: link.trim() }));
            }}
          >
            <input type="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://…/pronunciations.json (a dataset someone shared online)" />
            <button className="primary" type="submit" disabled={!link.trim()}>Import</button>
            <span className="muted small">Needs internet once; everything else stays offline.</span>
          </form>
        )}
        <div className="muted small">
          Your pronunciation dataset{ds ? `: ${ds.entries} terms, ${ds.mine} yours${ds.unchecked ? `, ${ds.unchecked} to check` : ""}` : ""}. It started as the
          SciReader list and grows with every term you give a pronunciation; it applies to every paper, and you can export it and import
          anyone's (same file for everyone). Type how a term should sound: a plain respelling like “peg-dah”, or letters like “T G”.
        </div>
        {msg && <div className="offline ok">{msg}</div>}
        {view && view.duplicates.length > 0 && !reviewing && (
          <button className="mk mk-dup dup-notice" onClick={() => dupSection.current?.scrollIntoView({ block: "start", behavior: "smooth" })}>
            ⚠ {view.duplicates.length} term{view.duplicates.length > 1 ? "s have" : " has"} two pronunciations: choose below
          </button>
        )}
        {view && view.dataset.unchecked > 0 && !reviewing && (
          <div className="row review-call">
            <span className="mk mk-check">to check</span>
            <span>{view.dataset.unchecked} pronunciation{view.dataset.unchecked > 1 ? "s" : ""} in your dataset nobody has listened to yet.</span>
            <button className="primary" onClick={() => setReviewing(true)}>Review them</button>
          </div>
        )}
        {reviewing ? (
          <Review
            say={say}
            onChange={changed}
            onClose={() => {
              setReviewing(false);
              void changed();
            }}
          />
        ) : !view ? (
          <div className="muted">Finding terms…</div>
        ) : (
          <>
            <section className="pron-section">
              <h3>
                Suggested for this paper <span className="mk mk-new">New</span> <span className="muted small">not in your dataset yet, most frequent first</span>
              </h3>
              <AddTerm busy={busy} onAdd={(term, sayAs, kind) => void put(term, sayAs, { kind })} />
              {view.suggested.length === 0 ? (
                <div className="muted small">Nothing to suggest: every term the voice might stumble on is in your dataset.</div>
              ) : (
                <>
                  <table className="pron-table">
                    <tbody>
                      {(allSuggested ? view.suggested : view.suggested.slice(0, 15)).map((t) => (
                        <SuggestedRow key={t.term} t={t} busy={busy} say={say} onPut={(sayAs) => void put(t.term, sayAs, { kind: t.kind })} />
                      ))}
                    </tbody>
                  </table>
                  {view.suggested.length > 15 && (
                    <button onClick={() => setAllSuggested((v) => !v)}>
                      {allSuggested ? "Show the first 15" : `Show all ${view.suggested.length} suggestions`}
                    </button>
                  )}
                </>
              )}
            </section>
            {view.duplicates.length > 0 && (
              <section className="pron-section" ref={dupSection}>
                <h3>
                  Two pronunciations for the same term <span className="mk mk-dup">⚠ 2 entries</span>{" "}
                  <span className="muted small">the first is spoken until you choose</span>
                </h3>
                {view.duplicates.map((g) => (
                  <DupRow
                    key={g.term}
                    g={g}
                    busy={busy}
                    say={say}
                    onKeep={(i) => void post("/api/pronunciations/keep", { term: g.term, index: i, case_sensitive: g.entries[0].case_sensitive }, `${g.term}: kept “${g.entries[i].say_as ?? g.term}”.`)}
                    onPut={(sayAs) => void put(g.term, sayAs, { kind: g.entries[0].kind, note: g.entries[0].note })}
                  />
                ))}
              </section>
            )}
            <section className="pron-section">
              <h3>
                In your dataset <span className="mk mk-in">✓ In dataset</span> <span className="muted small">the terms of this paper that it already has</span>
              </h3>
              {view.known.length === 0 ? (
                <div className="muted small">None of this paper's terms are in your dataset yet.</div>
              ) : (
                <table className="pron-table">
                  <tbody>
                    {view.known.map((k) => (
                      <EntryRow
                        key={k.term}
                        e={{ ...k.entry, duplicate: k.duplicate }}
                        count={k.count}
                        context={k.snippet}
                        moved={moved === k.term}
                        busy={busy}
                        say={say}
                        onPut={(sayAs) => void put(k.term, sayAs, { kind: k.entry.kind, tags: k.entry.tags, note: k.entry.note, case_sensitive: k.entry.case_sensitive })}
                        onCheck={() => void post("/api/pronunciations/check", { term: k.term, case_sensitive: k.entry.case_sensitive }, `${k.term}: checked.`)}
                        onRemove={() => void post("/api/pronunciations/remove", { term: k.term, case_sensitive: k.entry.case_sensitive }, `${k.term} removed from your dataset.`)}
                      />
                    ))}
                  </tbody>
                </table>
              )}
            </section>
            <DatasetBrowser
              key={browseKey}
              busy={busy}
              say={say}
              onPut={(e, sayAs) => void put(e.term, sayAs, { kind: e.kind, tags: e.tags, note: e.note, case_sensitive: e.case_sensitive })}
              onCheck={(e) => void post("/api/pronunciations/check", { term: e.term, case_sensitive: e.case_sensitive }, `${e.term}: checked.`)}
              onRemove={(e) => void post("/api/pronunciations/remove", { term: e.term, case_sensitive: e.case_sensitive }, `${e.term} removed from your dataset.`)}
            />
          </>
        )}
      </div>
    </div>
  );
}

function AddTerm({ busy, onAdd }: { busy: string | null; onAdd: (term: string, sayAs: string | null, kind: string) => void }) {
  const [term, setTerm] = useState("");
  const [sayAs, setSayAs] = useState("");
  const [kind, setKind] = useState("acronym");
  return (
    <form
      className="row add-term"
      onSubmit={(e) => {
        e.preventDefault();
        if (!term.trim()) return;
        onAdd(term.trim(), sayAs.trim() || null, kind);
        setTerm("");
        setSayAs("");
      }}
    >
      <span className="muted small">Add any term:</span>
      <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="term, word, molecule, acronym" aria-label="Term" />
      <input value={sayAs} onChange={(e) => setSayAs(e.target.value)} placeholder="say it like (empty: as written)" aria-label="Say it like" />
      <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Kind">
        {KINDS.map((k) => (
          <option key={k} value={k}>{k}</option>
        ))}
      </select>
      <button type="submit" disabled={!term.trim() || busy === `put:${term.trim()}`}>Add</button>
    </form>
  );
}

type Say = (key: string, text: string, raw?: boolean) => Promise<void>;

/** One "to check" entry at a time: it plays as it appears; Enter keeps it (or saves what you typed), and the next
 * one plays. "Without" plays the voice without the dataset, to hear what the entry changes. */
function Review({ say, onChange, onClose }: { say: Say; onChange: () => Promise<void>; onClose: () => void }) {
  const [queue, setQueue] = useState<Entry[] | null>(null);
  const [i, setI] = useState(0);
  const [draft, setDraft] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    api.get<{ entries: Entry[] }>("/api/pronunciations?filter=unchecked&limit=5000").then((r) => setQueue(r.entries), (e) => setErr(String(e)));
  }, []);
  const e = queue?.[i];
  useEffect(() => {
    if (!e) return;
    setDraft(e.say_as ?? "");
    input.current?.focus();
    void say(`rv:${e.term}`, e.term);
  }, [e?.term, i]);

  const next = () => setI((n) => n + 1);
  const act = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      void onChange();
      next();
    } catch (x) {
      setErr(String(x));
    }
  };
  const body = (x: Entry, say_as: string | null) => ({ term: x.term, say_as, kind: x.kind, tags: x.tags, note: x.note, case_sensitive: x.case_sensitive });
  const confirm = () => {
    if (!e) return;
    const d = draft.trim();
    if (d === (e.say_as ?? "")) void act(() => api.post("/api/pronunciations/check", { term: e.term, case_sensitive: e.case_sensitive }));
    else void act(() => api.put("/api/pronunciations/entry", body(e, d || null)));
  };

  if (err) return <div className="error-box">{err}</div>;
  if (!queue) return <div className="muted">Loading…</div>;
  return (
    <section className="pron-section review">
      <h3>
        Review <span className="mk mk-check">to check</span>{" "}
        <span className="muted small">{Math.min(i + 1, queue.length)} of {queue.length}</span>
        <button className="ghost" onClick={onClose}>Back to the lists</button>
      </h3>
      {!e ? (
        <div className="offline ok">All done: every entry in your dataset has been listened to.</div>
      ) : (
        <div className="review-card">
          <div className="review-term">{e.term}</div>
          <div className="muted small">{[e.kind, e.note, e.tags.join(", "), sourceLabel(e.source)].filter(Boolean).join(" · ")}</div>
          <div className="row">
            <button onClick={() => void say(`rv:${e.term}`, e.term)} title="Play it again, as the dataset says it">▶ Again</button>
            <button onClick={() => void say(`raw:${e.term}`, e.term, true)} title="How the voice says it without the dataset">▶ Without</button>
            <input
              ref={input}
              value={draft}
              onChange={(ev) => setDraft(ev.target.value)}
              onKeyDown={(ev) => {
                if (ev.key === "Enter") confirm();
              }}
              placeholder="as written"
              aria-label={`How to say ${e.term}`}
            />
            <button onClick={() => void say(`rvd:${e.term}`, draft.trim() || e.term, !draft.trim())} title="Hear what you typed">▶ Mine</button>
          </div>
          <div className="row">
            <button className="primary" onClick={confirm}>{draft.trim() === (e.say_as ?? "") ? "✓ Right (Enter)" : "Save (Enter)"}</button>
            <button onClick={() => void act(() => api.put("/api/pronunciations/entry", body(e, null)))} title="The voice gets it right without help">Sounds right as written</button>
            <button onClick={next} title="Decide later">Skip</button>
            <button className="ghost" onClick={() => void act(() => api.post("/api/pronunciations/remove", { term: e.term, case_sensitive: e.case_sensitive }))}>Remove</button>
          </div>
        </div>
      )}
    </section>
  );
}

function SuggestedRow({ t, busy, say, onPut }: { t: Suggested; busy: string | null; say: Say; onPut: (sayAs: string | null) => void }) {
  const [draft, setDraft] = useState("");
  return (
    <tr>
      <td>
        <b>{t.term}</b> <span className="mk mk-new">New</span>
        <div className="muted small">{t.kind} · {t.count}×</div>
      </td>
      <td>
        <button onClick={() => void say(`now:${t.term}`, t.snippet)} disabled={busy === `now:${t.term}`} title={`How it sounds now: ${t.snippet}`}>
          {busy === `now:${t.term}` ? "…" : "▶ now"}
        </button>{" "}
        <span className="muted small">…{t.snippet.slice(0, 70)}…</span>
      </td>
      <td>
        <input
          value={draft}
          placeholder="say it like…"
          aria-label={`How to say ${t.term}`}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && draft.trim() && onPut(draft.trim())}
        />
      </td>
      <td className="nowrap">
        <button onClick={() => void say(`pv:${t.term}`, withDraft(t.snippet, t.term, draft.trim()))} disabled={!draft.trim()} title="Hear it with your pronunciation">▶</button>{" "}
        <button className="primary" onClick={() => onPut(draft.trim())} disabled={!draft.trim() || busy === `put:${t.term}`} title="Add it to your dataset">Add</button>{" "}
        <button onClick={() => onPut(null)} disabled={busy === `put:${t.term}`} title="It already sounds right: add it, read as written">Sounds right</button>
      </td>
    </tr>
  );
}

function Markers({ e }: { e: Entry }) {
  return (
    <>
      {e.duplicate ? <span className="mk mk-dup">⚠ 2 entries</span> : <span className="mk mk-in">✓ In dataset</span>}{" "}
      <span className="mk mk-src">{sourceLabel(e.source)}</span>
      {!e.checked && <> <span className="mk mk-check">to check</span></>}
    </>
  );
}

function EntryRow({ e, count, context, moved, busy, say, onPut, onCheck, onRemove }: {
  e: Entry;
  count?: number;
  context?: string;
  moved?: boolean;
  busy: string | null;
  say: Say;
  onPut: (sayAs: string | null) => void;
  onCheck: () => void;
  onRemove: () => void;
}) {
  const [draft, setDraft] = useState(e.say_as ?? "");
  const edited = draft.trim() !== (e.say_as ?? "");
  return (
    <tr className={moved ? "moved" : undefined} data-known={e.term}>
      <td>
        <b>{e.term}</b> <Markers e={e} />
        <div className="muted small">{[e.kind, count ? `${count}×` : null, e.note].filter(Boolean).join(" · ")}</div>
      </td>
      <td>
        <button onClick={() => void say(`in:${e.term}`, context ?? e.term)} disabled={busy === `in:${e.term}`} title={context ? `As it sounds now: ${context}` : "As it sounds now"}>
          {busy === `in:${e.term}` ? "…" : "▶"}
        </button>{" "}
        {context && <span className="muted small">…{context.slice(0, 60)}…</span>}
      </td>
      <td>
        <input
          value={draft}
          placeholder="as written"
          aria-label={`How to say ${e.term}`}
          onChange={(ev) => setDraft(ev.target.value)}
          onKeyDown={(ev) => ev.key === "Enter" && edited && onPut(draft.trim() || null)}
        />
      </td>
      <td className="nowrap">
        {edited && (
          <>
            <button onClick={() => void say(`pv:${e.term}`, context ? withDraft(context, e.term, draft.trim() || e.term) : draft.trim() || e.term)} title="Hear your change">▶</button>{" "}
            <button className="primary" onClick={() => onPut(draft.trim() || null)} disabled={busy === `put:${e.term}`}>Save</button>{" "}
          </>
        )}
        {!e.checked && !edited && <><button onClick={onCheck} title="You heard it and it is right">✓ Right</button>{" "}</>}
        <button className="ghost" onClick={onRemove} title="Remove it from your dataset">Remove</button>
      </td>
    </tr>
  );
}

function DupRow({ g, busy, say, onKeep, onPut }: { g: DupGroup; busy: string | null; say: Say; onKeep: (i: number) => void; onPut: (sayAs: string | null) => void }) {
  const [draft, setDraft] = useState("");
  return (
    <div className="dup-group">
      <div>
        <b>{g.term}</b> <span className="mk mk-dup">⚠ {g.entries.length} entries</span>
        {g.in_paper && <span className="muted small"> · in this paper</span>}
      </div>
      {g.entries.map((e, i) => (
        <div key={i} className="row dup-entry">
          <button onClick={() => void say(`dup:${g.term}:${i}`, e.say_as ?? e.term)} disabled={busy === `dup:${g.term}:${i}`} title="Hear this one">▶</button>
          <span>“{e.say_as ?? e.term}”{e.say_as ? "" : " (as written)"}</span>
          <span className="mk mk-src">{sourceLabel(e.source)}</span>
          {i === 0 && <span className="muted small">spoken now</span>}
          <button className="primary" onClick={() => onKeep(i)}>Use this one</button>
        </div>
      ))}
      <div className="row dup-entry">
        <span className="muted small">or another:</span>
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="say it like…" aria-label={`Another way to say ${g.term}`} />
        <button onClick={() => onPut(draft.trim())} disabled={!draft.trim() || busy === `put:${g.term}`}>Use this</button>
      </div>
    </div>
  );
}

const FILTER_LABELS: Record<string, string> = {
  all: "All",
  mine: "Yours",
  base: "SciReader list",
  imported: "Imported",
  unchecked: "To check",
  duplicates: "Two entries",
};

function DatasetBrowser({ busy, say, onPut, onCheck, onRemove }: {
  busy: string | null;
  say: Say;
  onPut: (e: Entry, sayAs: string | null) => void;
  onCheck: (e: Entry) => void;
  onRemove: (e: Entry) => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [limit, setLimit] = useState(50);
  const [page, setPage] = useState<{ total: number; entries: Entry[]; counts: Record<string, number> } | null>(null);
  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => {
      api.get<typeof page>(`/api/pronunciations?q=${encodeURIComponent(q)}&filter=${filter}&limit=${limit}`).then(setPage, () => undefined);
    }, 200);
    return () => window.clearTimeout(t);
  }, [open, q, filter, limit]);
  return (
    <section className="pron-section">
      <h3>
        <button className="ghost" onClick={() => setOpen((v) => !v)} aria-expanded={open}>{open ? "▾" : "▸"} Your whole dataset</button>
        {page && <span className="muted small"> {page.counts.all} terms</span>}
      </h3>
      {open && (
        <>
          <div className="row">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search terms, pronunciations, notes" aria-label="Search the dataset" />
            <div className="chips">
              {Object.entries(FILTER_LABELS).map(([k, label]) => (
                <button key={k} className={filter === k ? "chip on" : "chip"} onClick={() => setFilter(k)} aria-pressed={filter === k}>
                  {label}{page ? ` ${page.counts[k] ?? 0}` : ""}
                </button>
              ))}
            </div>
          </div>
          {!page ? (
            <div className="muted small">Loading…</div>
          ) : (
            <>
              <table className="pron-table">
                <tbody>
                  {page.entries.map((e, i) => (
                    <EntryRow key={`${e.term}:${i}:${e.say_as}`} e={e} busy={busy} say={say} onPut={(s) => onPut(e, s)} onCheck={() => onCheck(e)} onRemove={() => onRemove(e)} />
                  ))}
                </tbody>
              </table>
              {page.total > page.entries.length && (
                <button onClick={() => setLimit((l) => l + 100)}>Show more ({page.total - page.entries.length} left)</button>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
