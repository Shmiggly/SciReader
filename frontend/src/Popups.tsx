// Popups over the reading area (the PDF or the text view): the figure popup, the equation details and the cited
// equation (E). Each opens next to what it belongs to and can be dragged by its header inside the area.
import { useEffect, useState } from "react";
import { api, type Rect } from "./api";
import { EquationPopover } from "./Equations";
import { FloatingPanel } from "./Float";
import { type FigPopup, type PopAnchor, closeFigure, figureDetail, hearFigure, noteFigureReady, sentenceAt, useStore } from "./store";

export type View = "pdf" | "text";

/** A box on a PDF page (points) in viewport pixels. */
function pageBox(r: Rect): DOMRect | null {
  const page = document.querySelector<HTMLElement>(`.pdf-page[data-page="${r[0]}"]`);
  if (!page) return null;
  const p = page.getBoundingClientRect();
  const s = useStore.getState().scale;
  return new DOMRect(p.left + r[1] * s, p.top + r[2] * s, (r[3] - r[1]) * s, (r[4] - r[2]) * s);
}

function textBox(selector: string): DOMRect | null {
  return document.querySelector<HTMLElement>(`.reflow ${selector}`)?.getBoundingClientRect() ?? null;
}

/** The box to open next to: a mention (its last line, or first for "above") or else its sentence. */
function anchorBox(view: View, a: PopAnchor, prefer: "below" | "above"): DOMRect | null {
  if (view === "text") return (a.span && textBox(`[data-fig="${a.sid}:${a.span[0]}"]`)) || textBox(`[data-sid="${a.sid}"]`);
  const rects = a.rects?.length ? a.rects : (sentenceAt(a.sid)?.s.rects ?? []);
  const r = prefer === "above" ? rects[0] : rects[rects.length - 1];
  return r ? pageBox(r) : null;
}

export function Popups({ view }: { view: View }) {
  return (
    <div className="float-layer">
      <EquationDetails view={view} />
      <CitedEquation view={view} />
      <FigurePanel view={view} />
    </div>
  );
}

function EquationDetails({ view }: { view: View }) {
  const eqOpen = useStore((s) => s.eqOpen);
  const doc = useStore((s) => s.doc)!;
  const b = eqOpen ? doc.blocks.find((x) => x.id === eqOpen) : undefined;
  if (!b) return null;
  const a: PopAnchor = { sid: b.sentences[0].id, span: null, rects: [[b.page, ...b.bbox]] };
  return <EquationPopover b={b} anchor={() => anchorBox(view, a, "below")} />;
}

function CitedEquation({ view }: { view: View }) {
  const ref = useStore((s) => s.eqRef);
  const doc = useStore((s) => s.doc)!;
  const res = useStore((s) => (ref ? s.eqResults[ref.blockId] : undefined));
  const b = ref ? doc.blocks.find((x) => x.id === ref.blockId) : undefined;
  if (!ref || !b) return null;
  const [x0, y0, x1, y1] = b.bbox;
  const verdict = res?.verdict;
  return (
    <FloatingPanel
      className="eqref-pop"
      width={560}
      openKey={`${b.id}:${ref.sentenceId}`}
      anchorKey=""
      prefer="above"
      anchor={() => anchorBox(view, { sid: ref.sentenceId, span: null, rects: null }, "above")}
      label={`Equation ${b.eq_number}`}
      head={
        <>
          <b>Equation {b.eq_number} (page {b.page + 1})</b>
          {verdict && <span className={`eq-badge static ${verdict}`}>{verdict}</span>}
        </>
      }
    >
      <img
        src={`/api/docs/${doc.id}/crop?page=${b.page}&x0=${x0}&y0=${y0}&x1=${x1}&y1=${y1}`}
        alt={`Equation ${b.eq_number}`}
        style={{ aspectRatio: `${Math.max(1, x1 - x0 + 8)} / ${Math.max(1, y1 - y0 + 8)}` }}
      />
    </FloatingPanel>
  );
}

/** Fill in a popup's description and caption, and keep checking until the background job has described it. */
function useFigureTarget(pop: FigPopup | null): string | undefined {
  const docId = useStore((s) => s.doc?.id);
  const [job, setJob] = useState<string | undefined>();
  const key = pop?.key;
  const seq = pop?.seq;
  const need = !!pop && !pop.description;
  useEffect(() => {
    if (!docId || !key || !need) return;
    let live = true;
    let timer: number | undefined;
    let asked = false;
    const poll = async () => {
      try {
        const t = await api.get<{ description: string | null; caption_part: string | null; status: { state?: string } }>(`/api/docs/${docId}/figures/key/${key}`);
        if (!live) return;
        noteFigureReady(key, t.description);
        setJob(t.status?.state);
        useStore.setState((s) =>
          s.figPopup && s.figPopup.key === key && s.figPopup.seq === seq
            ? { figPopup: { ...s.figPopup, description: s.figPopup.captionOnly ? null : t.description, caption: t.caption_part, loading: s.figPopup.origin === "click" ? false : s.figPopup.loading } }
            : {},
        );
        if (t.description || useStore.getState().figPopup?.captionOnly) return;
        if (!asked) {
          asked = true; // this one next
          void api.post(`/api/docs/${docId}/figures/prepare?first=${key}`).catch(() => undefined);
        }
        if (t.status?.state === "unavailable" || t.status?.state === "error") return;
        timer = window.setTimeout(poll, 4000);
      } catch {
        if (live) timer = window.setTimeout(poll, 6000);
      }
    };
    void poll();
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [docId, key, seq, need]);
  return job;
}

function FigurePanel({ view }: { view: View }) {
  const pop = useStore((s) => s.figPopup);
  const doc = useStore((s) => s.doc)!;
  const job = useFigureTarget(pop);
  if (!pop) return null;
  const fig = doc.figures.find((f) => f.id === pop.figure_id);
  const [x0, y0, x1, y1] = fig?.bbox ?? [0, 0, 4, 3];
  const noAi = job === "unavailable" || job === "error";
  const waiting = pop.origin === "click" ? (noAi ? "Not available: the local AI (Ollama) isn't running." : "Being prepared…") : "Not ready yet: reading the caption only.";
  return (
    <FloatingPanel
      className="fig-pop"
      width={520}
      openKey={`fig:${pop.seq}`}
      anchorKey={`${pop.key}:${pop.anchor.sid}:${pop.anchor.span?.[0] ?? ""}`}
      anchor={() => anchorBox(view, pop.anchor, "below")}
      label={pop.label}
      head={
        <>
          <b>{pop.label}</b>
          {pop.origin === "click" && (
            <button className="primary" onClick={() => hearFigure()} title="Read it aloud, then go back to where you were">
              ▶ Hear it
            </button>
          )}
          <button className={pop.pinned ? "toggle on" : "toggle"} onClick={() => useStore.setState({ figPopup: { ...pop, pinned: !pop.pinned } })} title={pop.pinned ? "Kept open (click to close it with the next sentence)" : "Keep this open"} aria-pressed={pop.pinned}>
            📌
          </button>
          <button className="ghost" onClick={closeFigure} aria-label="Close">✕</button>
        </>
      }
    >
      <img
        src={`/api/docs/${doc.id}/figures/${pop.figure_id}/image`}
        alt={pop.label}
        style={{ aspectRatio: `${Math.max(1, x1 - x0 + 8)} / ${Math.max(1, y1 - y0 + 8)}` }}
      />
      {pop.captionOnly ? (
        <div className="fig-desc">
          <span className="cap-label">Caption</span> {pop.caption ?? "…"}
        </div>
      ) : (
        <>
          <div className="fig-desc">
            <span className="ai-label">AI description</span> {pop.description ?? (pop.loading ? "…" : waiting)}
          </div>
          {pop.caption && (
            <details className="fig-caption small">
              <summary>Caption</summary>
              {pop.caption}
            </details>
          )}
        </>
      )}
      <div className="eq-actions">
        <button onClick={figureDetail} title="A longer AI description (D)">More detail (D)</button>
      </div>
    </FloatingPanel>
  );
}
