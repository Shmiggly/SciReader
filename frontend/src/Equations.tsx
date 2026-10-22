// Verified equation narration in the UI: background polling, badges on the PDF, and the detail popover.
import { useEffect, useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { api, type Block, type Doc } from "./api";
import { FloatingPanel } from "./Float";
import { hearEquationDescription, loadEquationDescription, playSentence, useStore } from "./store";

export interface EqAttempt { speech: string; back: string; result: string; diff: string }
/** Second reading of the page (backend llm/page_reading.py): which LaTeX is narrated, checked and read by rules. */
export interface EqSource {
  status: "agree" | "page" | "disputed" | "vision_only" | "single" | "unreadable" | "arxiv";
  used: "parser" | "vision" | "arxiv";
  parser?: string;
  vision?: string | null;
  off?: { parser: number | null; vision: number | null } | null;
  same_symbols?: boolean;
  model?: string;
  error?: string | null;
}
export interface EqResult {
  verdict: "verified" | "uncertain" | "fallback" | "unreadable" | "pending";
  speech_ai: string | null;
  brief: string | null;
  reason: string | null;
  attempts: EqAttempt[];
  models?: { reader: string; checker: string };
  source?: EqSource | null;
  latex?: string | null;
  speech_rules?: string | null;
}

/** The equation's LaTeX and rule-based reading after the second reading (the parser's until it has run). */
export function eqLatex(b: Block, res: EqResult | undefined): string {
  return res?.source ? res.latex ?? "" : b.latex ?? "";
}
function eqRules(b: Block, res: EqResult | undefined): string | null | undefined {
  return res?.source ? res.speech_rules : b.speech_rules;
}

function symbolsOff(n: number | null | undefined): string {
  return n === 1 ? "1 symbol" : `${n ?? "?"} symbols`;
}

/** One sentence on where the narrated LaTeX came from and whether the two readings agreed. */
function sourceNote(src: EqSource): string {
  const m = src.model ?? "the vision model";
  const off = src.off;
  switch (src.status) {
    case "agree":
      return `Two independent readings agree: the PDF parser's formula OCR and ${m} reading the page.`;
    case "page":
      return src.used === "vision"
        ? `The parser and ${m} read this differently. The PDF's text layer matches ${m}'s reading of the page better (${symbolsOff(off?.vision)} off, the parser's ${symbolsOff(off?.parser)}), so that reading is used.`
        : `The parser and ${m} read this differently. The PDF's text layer matches the parser's reading better (${symbolsOff(off?.parser)} off, ${m}'s ${symbolsOff(off?.vision)}), so it is used.`;
    case "disputed":
      return src.same_symbols
        ? `Uncertain: the parser and ${m} read the same symbols but a different structure (grouping, or what a root or fraction covers), which the PDF's text layer can't check. The parser's reading is used.`
        : `Uncertain: the parser and ${m} read this differently, and the PDF's text layer can't tell which is right. The parser's reading is used.`;
    case "vision_only":
      return `The parser's formula OCR was unusable; ${m} read this from the page, and the PDF's text layer backs that reading (${symbolsOff(off?.vision)} off).`;
    case "single":
      return `Only the parser's reading: the second reading of the page failed${src.error ? ` (${src.error})` : ""}.`;
    case "unreadable":
      return `Neither the parser nor ${m} produced a reading that the PDF's text layer backs.`;
    case "arxiv":
      return "The paper's own LaTeX (arXiv source), not OCR.";
  }
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
  if (!eqRules(b, res)) return "unreadable";
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
      title={`${name}: ${LABEL[st] ?? st}.${res?.source?.status === "disputed" ? " Source uncertain: two readings of the page disagree." : ""} Click for details.`}
    >
      {st === "checking" && <span className="spinner" />}
      {compact ? GLYPH[st] : LABEL[st] ?? st}
    </button>
  );
}

/** The "AI description" button of an equation (its popup, its details): spins while the local AI writes it. */
export function EquationAiButton({ blockId, primary = false }: { blockId: string; primary?: boolean }) {
  const busy = useStore((s) => s.aiBusy === `eq:${blockId}`);
  return (
    <button
      className={primary ? "primary" : undefined}
      onClick={() => hearEquationDescription(blockId)}
      disabled={busy}
      aria-busy={busy}
      title={busy ? "The local AI is writing the description…" : "Hear what this equation says and what its symbols stand for (AI), then go back to where you were"}
    >
      {busy ? <span className="spinner" /> : "▶ "}AI description
    </button>
  );
}

/** The details of an equation's check (badge click), in a panel that opens below the equation and can be dragged. */
export function EquationPopover({ b, anchor }: { b: Block; anchor: () => DOMRect | null }) {
  const res = useStore((s) => s.eqResults[b.id]);
  const eqState = useStore((s) => s.eqState);
  const description = useStore((s) => s.eqDescriptions[b.id]);
  useEffect(() => {
    void loadEquationDescription(b.id);
  }, [b.id]);
  const st = badgeState(b, res, eqState);
  let html = "";
  try {
    html = katex.renderToString(eqLatex(b, res), { displayMode: true, throwOnError: false, strict: "ignore" });
  } catch {
    html = "";
  }
  const label = (b.eq_number ? `Equation ${b.eq_number}` : "Equation") + (b.eq_label ? ` · ${b.eq_label}` : "");
  const used = st === "verified" ? res?.speech_ai : eqRules(b, res);
  // The words actually spoken in the current reading mode (natural wording, long equations summarized in Auto).
  const docId = useStore((s) => s.doc?.id);
  const eqMode = useStore((s) => s.eqMode);
  const [spoken, setSpoken] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    if (docId)
      api.get<{ spoken: string }>(`/api/docs/${docId}/equations/${b.id}/spoken?eq_mode=${eqMode}`).then(
        (r) => live && setSpoken(r.spoken),
        () => live && setSpoken(null),
      );
    return () => {
      live = false;
    };
  }, [docId, b.id, eqMode, res?.verdict, res?.speech_ai]);
  const last = res?.attempts?.[res.attempts.length - 1];
  const src = res?.source;
  return (
    <FloatingPanel
      className="eq-pop"
      width={460}
      openKey={b.id}
      anchorKey=""
      anchor={anchor}
      label={label}
      head={
        <>
          <b>{label}</b>
          <span className={`eq-badge static ${st}`}>{LABEL[st] ?? st}</span>
          <button className="ghost" onClick={() => useStore.setState({ eqOpen: null })} aria-label="Close">✕</button>
        </>
      }
    >
      <div className="eq-katex" dangerouslySetInnerHTML={{ __html: html }} />
      <div className="eq-field">
        <div className="eq-field-label">Spoken now {st === "verified" ? "(AI narration, checked)" : "(rule-based reading)"}</div>
        <div>{spoken ?? (used || "“" + label + "” only: no reading could be produced.")}</div>
      </div>
      {description && (
        <div className="fig-desc">
          <span className="ai-label">AI description</span> {description}
        </div>
      )}
      {st === "verified" && <div className="muted small">An independent model ({res?.models?.checker}) wrote this narration back as LaTeX, and it matched the equation exactly.</div>}
      {st === "uncertain" && (
        <div className="muted small">
          Not spoken: the AI narration (“{res?.speech_ai}”) was written back with the same symbols but a different grouping ({res?.reason}), and grouping is where AI readings go silently wrong. The rule-based reading is used instead.
        </div>
      )}
      {st === "fallback" && res && res.attempts.length > 0 && (
        <div className="muted small">The AI narration didn't survive the check ({res.reason || "mismatch"}), so the rule-based reading is used.</div>
      )}
      {src && <div className={`eq-source small ${src.status}`}><b>Source.</b> {sourceNote(src)}</div>}
      {(last || src) && (
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
          {src && src.status !== "arxiv" ? (
            <>
              <div className="small muted">
                PDF parser's reading{src.used === "parser" ? " (used)" : ""}: <code>{src.parser || "none"}</code>
              </div>
              <div className="small muted">
                {src.model ?? "Vision model"} reading the page{src.used === "vision" ? " (used)" : ""}: <code>{src.vision || "none"}</code>
              </div>
            </>
          ) : (
            <div className="small muted">Source LaTeX{src ? " (arXiv source)" : " (from the PDF parser)"}: <code>{eqLatex(b, res)}</code></div>
          )}
          {res?.brief && <div className="small">AI summary (Brief mode): {res.brief}</div>}
        </details>
      )}
      <div className="eq-actions">
        <EquationAiButton blockId={b.id} />
        <button className="primary" onClick={() => void playSentence(b.sentences[0].id)}>▶ Read it</button>
      </div>
    </FloatingPanel>
  );
}
