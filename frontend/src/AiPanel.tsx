// AI panel: Explain (selected sentences or the current one; colleague level, "Simpler") and Ask the paper.
// Answers are grounded with sentence citations (chips jump to and highlight the source) and can be read aloud.
import { useEffect, useState } from "react";
import { api } from "./api";
import { jumpTo, sayText, sentenceAt, useStore } from "./store";

interface Answer {
  answer: string;
  spoken: string;
  citations: string[];
  model: string;
  level?: string;
}
interface QA {
  q: string;
  a?: Answer;
  error?: string;
}

function Chips({ ids }: { ids: string[] }) {
  if (!ids.length) return null;
  return (
    <div className="chips">
      {ids.map((sid) => {
        const e = sentenceAt(sid);
        return (
          <button key={sid} className="chip" title={e?.s.text} onClick={() => jumpTo(sid)}>
            p.{e ? e.s.rects[0]?.[0] + 1 : "?"} “{e?.s.text.slice(0, 28)}…”
          </button>
        );
      })}
    </div>
  );
}

function AnswerView({ a, label }: { a: Answer; label: string }) {
  return (
    <div className="answer">
      <div>
        <span className="ai-label">AI</span> {a.spoken}
      </div>
      <Chips ids={a.citations} />
      <div className="answer-actions">
        <button onClick={() => sayText(a.spoken, label)}>▶ Read aloud</button>
        <span className="muted small">{a.model}, local</span>
      </div>
    </div>
  );
}

export function AiPanel({ onClose }: { onClose: () => void }) {
  const doc = useStore((s) => s.doc)!;
  const current = useStore((s) => s.current);
  const selection = useStore((s) => s.selection);
  const [ok, setOk] = useState<boolean | null>(null);
  const [explained, setExplained] = useState<{ ids: string[]; a?: Answer; error?: string; busy: boolean } | null>(null);
  const [q, setQ] = useState("");
  const [qa, setQa] = useState<QA[]>([]);
  const [asking, setAsking] = useState(false);
  const [summary, setSummary] = useState<{ a?: Answer; error?: string; busy: boolean; scope: string } | null>(null);
  const curSection = sentenceAt(current)?.b.section_id ?? null;
  const runSummary = async (section: string | null) => {
    const scope = section ? doc.outline.find((o) => o.id === section)?.title ?? "this section" : "the whole paper";
    setSummary({ busy: true, scope });
    try {
      const a = await api.post<Answer>(`/api/docs/${doc.id}/summary`, { section_id: section });
      setSummary({ a, busy: false, scope });
      sayText(a.spoken, `AI summary of ${scope}:`);
    } catch (e) {
      setSummary({ error: e instanceof Error ? e.message : String(e), busy: false, scope });
    }
  };

  useEffect(() => {
    api.get<{ ollama: boolean }>("/api/ai/status").then((r) => setOk(r.ollama), () => setOk(false));
  }, []);

  const target = selection?.length ? selection : current ? [current] : [];
  const targetText = target.map((sid) => sentenceAt(sid)?.s.text ?? "").join(" ");

  const runExplain = async (level: "colleague" | "simpler", ids = target) => {
    if (!ids.length) return;
    setExplained({ ids, busy: true });
    try {
      const a = await api.post<Answer>(`/api/docs/${doc.id}/explain`, { sentence_ids: ids, level });
      setExplained({ ids, a, busy: false });
    } catch (e) {
      setExplained({ ids, error: e instanceof Error ? e.message : String(e), busy: false });
    }
  };

  const runAsk = async () => {
    const question = q.trim();
    if (!question) return;
    setQ("");
    setAsking(true);
    const history = qa.filter((x) => x.a).map((x) => ({ q: x.q, a: x.a!.answer }));
    setQa((prev) => [...prev, { q: question }]);
    try {
      const a = await api.post<Answer>(`/api/docs/${doc.id}/ask`, { question, history });
      setQa((prev) => prev.map((x, i) => (i === prev.length - 1 ? { ...x, a } : x)));
    } catch (e) {
      setQa((prev) => prev.map((x, i) => (i === prev.length - 1 ? { ...x, error: e instanceof Error ? e.message : String(e) } : x)));
    } finally {
      setAsking(false);
    }
  };

  return (
    <aside className="side-panel ai-panel">
      <div className="panel-head">
        <b>✦ AI assistant</b>
        <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
      </div>
      {ok === false && <div className="error-box">Ollama isn't running: start it for Explain and Ask. Reading works without it.</div>}
      <section>
        <div className="panel-sub">Explain</div>
        <div className="muted small">
          {target.length
            ? `${selection?.length ? "Selected" : "Current"}: “${targetText.slice(0, 160)}${targetText.length > 160 ? "…" : ""}”`
            : "Click a sentence (Shift+click another to select a range), then Explain."}
        </div>
        <div className="row">
          <button className="primary" disabled={!target.length || explained?.busy} onClick={() => void runExplain("colleague")}>
            Explain
          </button>
          <button disabled={!explained?.a || explained.busy} onClick={() => void runExplain("simpler", explained!.ids)}>
            Simpler
          </button>
          {explained?.busy && <span className="muted small">thinking…</span>}
        </div>
        {explained?.error && <div className="error-box">{explained.error}</div>}
        {explained?.a && <AnswerView a={explained.a} label="AI explanation:" />}
      </section>
      <section>
        <div className="panel-sub">Listen to a summary (AI)</div>
        <div className="row">
          <button disabled={summary?.busy} onClick={() => void runSummary(null)}>▶ Whole paper</button>
          <button disabled={summary?.busy || !curSection} onClick={() => void runSummary(curSection)}>▶ This section</button>
          {summary?.busy && <span className="muted small">writing the summary of {summary.scope}…</span>}
        </div>
        {summary?.error && <div className="error-box">{summary.error}</div>}
        {summary?.a && <AnswerView a={summary.a} label={`AI summary of ${summary.scope}:`} />}
      </section>
      <section>
        <div className="panel-sub">Ask the paper</div>
        <div className="qa-list">
          {qa.map((x, i) => (
            <div key={i} className="qa">
              <div className="q">{x.q}</div>
              {x.a ? <AnswerView a={x.a} label="AI answer:" /> : x.error ? <div className="error-box">{x.error}</div> : <div className="muted small">reading the paper…</div>}
            </div>
          ))}
        </div>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            void runAsk();
          }}
        >
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Which kernel did they use, and why?" disabled={asking} />
          <button type="submit" disabled={asking || !q.trim()}>Ask</button>
        </form>
        <div className="muted small">Answers come only from this paper and cite the sentences they use. The first question takes ~10 s (the model reads the paper), later ones ~2 s.</div>
      </section>
    </aside>
  );
}
