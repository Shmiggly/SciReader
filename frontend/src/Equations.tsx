// Verified equation narration in the UI: background polling, badges on the PDF, and the detail popover.
import { useEffect, useRef } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { api, type Block, type Doc } from "./api";
import { useFitInScroller } from "./fit";
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
  checking: "checking",
};
const GLYPH: Record<string, string> = { verified: "✓", uncertain: "?", fallback: "✗", unreadable: "!" };

// Badge sizes in CSS px (see .eq-badge in styles.css): labelled pills have a fixed width so the layout is exact.
const PILL_W = 70;
const PILL_H = 19;
const ICON = 18;
const GAP = 3;
const NOT_TEXT = new Set(["page_header", "page_footer", "figure", "table"]);

export interface BadgePos {
  left?: number;
  right?: number;
  top: number;
}
export interface BadgeLayout {
  /** Icon-only badges: some page's margin is too narrow for the labelled pills at this zoom. */
  compact: boolean;
  pos: Map<string, BadgePos>;
}

/** Badge positions (px on the page) that never cover text or each other: right of the equation, or in the left margin
 * for a left-column equation on a two-column page (its right edge is the gutter); stacked downwards when crowded. */
export function layoutBadges(doc: Doc, scale: number): BadgeLayout {
  const plans: { id: string; page: number; pageW: number; inLeftMargin: boolean; edge: number; cy: number }[] = [];
  const byPage = new Map<number, Block[]>();
  for (const b of doc.blocks) {
    if (b.skip_reason === "junk") continue;
    const arr = byPage.get(b.page) ?? [];
    arr.push(b);
    byPage.set(b.page, arr);
  }
  for (const [page, blocks] of byPage) {
    const eqs = blocks.filter((b) => b.type === "equation");
    if (!eqs.length) continue;
    const text = blocks.filter((b) => !NOT_TEXT.has(b.type) && b.bbox[2] - b.bbox[0] > 40);
    const ref = text.length ? text : eqs;
    const left = Math.min(...ref.map((b) => b.bbox[0]));
    const mid = (left + Math.max(...ref.map((b) => b.bbox[2]))) / 2;
    const twoColumns = text.some((b) => b.bbox[2] < mid - 5) && text.some((b) => b.bbox[0] > mid + 5);
    for (const b of eqs) {
      const inLeftMargin = twoColumns && b.bbox[2] < mid + 5;
      plans.push({
        id: b.id,
        page,
        pageW: (doc.pages[page]?.width ?? 612) * scale,
        inLeftMargin,
        edge: inLeftMargin ? left * scale - GAP : b.bbox[2] * scale + GAP,
        cy: (b.bbox[1] + Math.min(b.bbox[3] - b.bbox[1], 14) / 2) * scale,
      });
    }
  }
  const compact = plans.some((p) => (p.inLeftMargin ? p.edge - PILL_W < 0 : p.edge + PILL_W > p.pageW));
  const w = compact ? ICON : PILL_W;
  const h = compact ? ICON : PILL_H;
  const pos: BadgeLayout["pos"] = new Map();
  const placed = new Map<number, number[][]>();
  plans.sort((a, b) => a.page - b.page || a.cy - b.cy);
  for (const p of plans) {
    const x = Math.max(0, Math.min(p.inLeftMargin ? p.edge - w : p.edge, p.pageW - w));
    const rects = placed.get(p.page) ?? [];
    let y = p.cy - h / 2;
    for (let moved = true; moved; ) {
      moved = false;
      for (const r of rects) {
        if (x < r[2] && x + w > r[0] && y < r[3] + 2 && y + h + 2 > r[1]) {
          y = r[3] + 2;
          moved = true;
        }
      }
    }
    rects.push([x, y, x + w, y + h]);
    placed.set(p.page, rects);
    pos.set(p.id, p.inLeftMargin ? { right: p.pageW - x - w, top: y } : { left: x, top: y });
  }
  return { compact, pos };
}

export function badgeState(b: Block, res: EqResult | undefined, eqState: string): string {
  if (res && res.verdict !== "pending") return res.verdict;
  if (!b.speech_rules) return "unreadable";
  if (eqState === "queued" || eqState === "running") return "checking";
  return "fallback";
}

export function EquationBadge({ b, pos, compact, onHover }: {
  b: Block;
  pos: BadgePos;
  compact: boolean;
  onHover: (id: string | null) => void;
}) {
  const res = useStore((s) => s.eqResults[b.id]);
  const eqState = useStore((s) => s.eqState);
  const st = badgeState(b, res, eqState);
  const name = b.eq_number ? `Equation ${b.eq_number}` : b.eq_label || "Equation";
  return (
    <button
      className={`eq-badge ${st}${compact ? " compact" : ""}`}
      style={pos}
      onClick={(e) => {
        e.stopPropagation();
        useStore.setState({ eqOpen: useStore.getState().eqOpen === b.id ? null : b.id });
      }}
      onMouseEnter={() => onHover(b.id)}
      onMouseLeave={() => onHover(null)}
      title={`${name}: ${LABEL[st] ?? st}. Click for details.`}
    >
      {st === "checking" && <span className="spinner" />}
      {compact ? GLYPH[st] : LABEL[st] ?? st}
    </button>
  );
}

export function EquationPopover({ b, scale, pageWidth }: { b: Block; scale: number; pageWidth: number }) {
  const res = useStore((s) => s.eqResults[b.id]);
  const eqState = useStore((s) => s.eqState);
  const ref = useRef<HTMLDivElement>(null);
  useFitInScroller(ref);
  const st = badgeState(b, res, eqState);
  let html = "";
  try {
    html = katex.renderToString(b.latex || "", { displayMode: true, throwOnError: false, strict: "ignore" });
  } catch {
    html = "";
  }
  const label = (b.eq_number ? `Equation ${b.eq_number}` : "Equation") + (b.eq_label ? ` · ${b.eq_label}` : "");
  const used = st === "verified" ? res?.speech_ai : b.speech_rules;
  const left = Math.max(8, Math.min(b.bbox[0] * scale, pageWidth - 470));
  const last = res?.attempts?.[res.attempts.length - 1];
  return (
    <div className="eq-pop" ref={ref} style={{ left, top: b.bbox[3] * scale + 8 }} onClick={(e) => e.stopPropagation()}>
      <div className="eq-pop-head">
        <b>{label}</b>
        <span className={`eq-badge static ${st}`}>{LABEL[st] ?? st}</span>
        <button className="ghost" onClick={() => useStore.setState({ eqOpen: null })} aria-label="Close">✕</button>
      </div>
      <div className="eq-katex" dangerouslySetInnerHTML={{ __html: html }} />
      <div className="eq-field">
        <div className="eq-field-label">Spoken now {st === "verified" ? "(AI narration, checked)" : "(rule-based reading)"}</div>
        <div>{used || "“" + label + "” only: no reading could be produced."}</div>
      </div>
      {st === "verified" && <div className="muted small">An independent model ({res?.models?.checker}) wrote this narration back as LaTeX, and it matched the equation exactly.</div>}
      {st === "uncertain" && (
        <div className="muted small">
          Not spoken: the AI narration (“{res?.speech_ai}”) was written back with the same symbols but a different grouping ({res?.reason}), and grouping is where AI readings go silently wrong. The rule-based reading is used instead.
        </div>
      )}
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
