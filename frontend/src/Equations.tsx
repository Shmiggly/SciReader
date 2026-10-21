// Verified equation narration in the UI: background polling, badges on the PDF, and the detail popover.
import { useEffect } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { api, type Block } from "./api";
import { playSentence, useStore } from "./store";

export interface EqAttempt { speech: string; back: string; result: string; diff: string }
export interface EqResult {
  verdict: "verified" | "uncertain" | "fallback" | "unreadable" | "pending";
  speech_ai: string | null;
  brief: string | null;
  reason: string | null;
  attempts: EqAttempt[];
  models?: { reader: string; checker: string };
}
interface EqStatus { state?: string; message?: string; done?: number; total?: number }

export function useEquationChecks(docId: string) {
  useEffect(() => {
    let stop = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const r = await api.get<{ status: EqStatus; results: Record<string, EqResult> }>(`/api/docs/${docId}/equations`);
        if (stop) return;
        useStore.setState({ eqResults: r.results, eqState: r.status.state ?? "idle", eqMessage: r.status.message ?? "" });
        if (r.status.state === "queued" || r.status.state === "running") timer = window.setTimeout(poll, 2500);
      } catch {
        /* backend busy; try later */
        timer = window.setTimeout(poll, 5000);
      }
    };
    void api.post(`/api/docs/${docId}/equations/verify`).catch(() => undefined).finally(poll);
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [docId]);
}

const LABEL: Record<string, string> = {
  verified: "✓ verified",
  uncertain: "? uncertain",
  fallback: "✗ rules",
  unreadable: "unreadable",
  checking: "checking…",
};

export function badgeState(b: Block, res: EqResult | undefined, eqState: string): string {
  if (res && res.verdict !== "pending") return res.verdict;
  if (!b.speech_rules) return "unreadable";
  if (eqState === "queued" || eqState === "running") return "checking";
  return "fallback";
}

export function EquationBadge({ b, scale }: { b: Block; scale: number }) {
  const res = useStore((s) => s.eqResults[b.id]);
  const eqState = useStore((s) => s.eqState);
  const st = badgeState(b, res, eqState);
  return (
    <button
      className={`eq-badge ${st}`}
      style={{ left: b.bbox[2] * scale + 4, top: b.bbox[1] * scale - 2 }}
      onClick={(e) => {
        e.stopPropagation();
        useStore.setState({ eqOpen: useStore.getState().eqOpen === b.id ? null : b.id });
      }}
      title="Equation reading: click for details"
    >
      {st === "checking" && <span className="spinner" />}
      {LABEL[st] ?? st}
    </button>
  );
}

export function EquationPopover({ b, scale, pageWidth }: { b: Block; scale: number; pageWidth: number }) {
  const res = useStore((s) => s.eqResults[b.id]);
  const eqState = useStore((s) => s.eqState);
  const st = badgeState(b, res, eqState);
  let html = "";
  try {
    html = katex.renderToString(b.latex || "", { displayMode: true, throwOnError: false, strict: "ignore" });
  } catch {
    html = "";
  }
  const label = b.eq_number ? `Equation ${b.eq_number}` : "Equation";
  const used = st === "verified" || st === "uncertain" ? res?.speech_ai : b.speech_rules;
  const left = Math.max(8, Math.min(b.bbox[0] * scale, pageWidth - 470));
  const last = res?.attempts?.[res.attempts.length - 1];
  return (
    <div className="eq-pop" style={{ left, top: b.bbox[3] * scale + 8 }} onClick={(e) => e.stopPropagation()}>
      <div className="eq-pop-head">
        <b>{label}</b>
        <span className={`eq-badge static ${st}`}>{LABEL[st] ?? st}</span>
        <button className="ghost" onClick={() => useStore.setState({ eqOpen: null })} aria-label="Close">✕</button>
      </div>
      <div className="eq-katex" dangerouslySetInnerHTML={{ __html: html }} />
      <div className="eq-field">
        <div className="eq-field-label">Spoken now {st === "verified" || st === "uncertain" ? "(AI narration, checked)" : "(rule-based reading)"}</div>
        <div>{used || "“" + label + "” only: no reading could be produced."}</div>
      </div>
      {st === "verified" && <div className="muted small">An independent model ({res?.models?.checker}) wrote this narration back as LaTeX, and it matched the equation exactly.</div>}
      {st === "uncertain" && <div className="muted small">The narration was transcribed back with the same symbols, but the grouping differs: {res?.reason}</div>}
      {st === "fallback" && res && (
        <div className="muted small">The AI narration didn't survive the check ({res.reason || "mismatch"}), so the rule-based reading is used.</div>
      )}
      {last && (
        <details>
          <summary className="small">Check details</summary>
          {res!.attempts.map((a, i) => (
            <div key={i} className="eq-attempt small">
              <div><b>Attempt {i + 1}</b> ({a.result})</div>
              <div>AI said: {a.speech}</div>
              <div>Written back: <code>{a.back}</code></div>
              {a.diff && <div className="muted">{a.diff}</div>}
            </div>
          ))}
          <div className="small muted">Source LaTeX (from the PDF parser): <code>{b.latex}</code></div>
          {res?.brief && <div className="small">AI summary (Brief mode): {res.brief}</div>}
        </details>
      )}
      <div className="eq-actions">
        <button className="primary" onClick={() => void playSentence(b.sentences[0].id)}>▶ Read it</button>
      </div>
    </div>
  );
}
