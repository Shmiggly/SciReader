// Clean text view: the parsed paper as one readable column, synced with playback (same highlight,
// click-to-read, figure mentions that open their figure). Adjustable font (incl. dyslexia-friendly), size, line
// spacing and width.
import { type ReactNode, useEffect, useMemo, useRef } from "react";
import katex from "katex";
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "@fontsource/opendyslexic/400.css";
import type { Sentence } from "./api";
import { badgeState, eqLatex } from "./Equations";
import { Popups } from "./Popups";
import { type FigMention, figLabel, isReadable, openFigure, playSentence, useStore } from "./store";

export const REFLOW_FONTS: Record<string, string> = {
  serif: "Georgia, 'Times New Roman', serif",
  sans: "'Segoe UI', system-ui, sans-serif",
  atkinson: "'Atkinson Hyperlegible', 'Segoe UI', sans-serif",
  opendyslexic: "'OpenDyslexic', 'Segoe UI', sans-serif",
};

export function ReflowView() {
  const doc = useStore((s) => s.doc)!;
  const current = useStore((s) => s.current);
  const follow = useStore((s) => s.follow);
  const r = useStore((s) => s.reflow);
  const eqResults = useStore((s) => s.eqResults);
  const eqState = useStore((s) => s.eqState);
  const figMentions = useStore((s) => s.figMentions);
  const box = useRef<HTMLDivElement>(null);

  const blocks = useMemo(
    () => doc.blocks.filter((b) => b.sentences.length && b.type !== "title" && b.skip_reason !== "junk" && !["page_furniture", "front_matter", "boilerplate"].includes(b.skip_reason ?? "")),
    [doc],
  );

  useEffect(() => {
    if (!follow || !current) return;
    const el = box.current?.querySelector(`[data-sid="${current}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [current, follow]);

  const click = (sid: string) => {
    useStore.setState({ follow: true });
    void playSentence(sid);
  };

  return (
    <div className="reflow-wrap">
      <div className="reflow-scroller" ref={box}>
        <article
          className="reflow"
          style={{ fontFamily: REFLOW_FONTS[r.font], fontSize: `${r.size}px`, lineHeight: r.lineHeight, maxWidth: `${r.width}ch` }}
        >
          <h1>{doc.title}</h1>
          {blocks.map((b) => {
            const dim = !isReadable(b) ? " skipped" : "";
            if (b.type === "heading") {
              const s = b.sentences[0];
              return (
                <h2 key={b.id} data-sid={s.id} className={`${s.id === current ? "cur" : ""}${dim}`} onClick={() => click(s.id)}>
                  {s.text}
                </h2>
              );
            }
            if (b.type === "equation") {
              const s = b.sentences[0];
              let html = "";
              try {
                html = katex.renderToString(eqLatex(b, eqResults[b.id]), { displayMode: true, throwOnError: false, strict: "ignore" });
              } catch {
                html = "";
              }
              const st = badgeState(b, eqResults[b.id], eqState);
              return (
                <div key={b.id} data-sid={s.id} className={`reflow-eq ${s.id === current ? "cur" : ""}`} onClick={() => click(s.id)}>
                  <div dangerouslySetInnerHTML={{ __html: html }} />
                  <span className={`eq-badge static ${st}`}>{b.eq_number ? `(${b.eq_number}) ` : ""}{st}</span>
                </div>
              );
            }
            const cls = b.type === "caption" ? "reflow-caption" : b.type === "bib_entry" ? "reflow-bib" : b.type === "abstract" ? "reflow-abstract" : "";
            return (
              <p key={b.id} className={`${cls}${dim}`}>
                {b.sentences.map((s) => (
                  <span key={s.id} data-sid={s.id} className={s.id === current ? "cur" : undefined} onClick={() => click(s.id)} title={s.spoken !== s.text ? `Spoken as: ${s.spoken}` : undefined}>
                    {withFigureLinks(s, figMentions.get(s.id))}{" "}
                  </span>
                ))}
              </p>
            );
          })}
        </article>
      </div>
      <Popups view="text" />
    </div>
  );
}

/** A sentence's text with its figure mentions as links (one per stretch of text where "Figs. 2–4" overlaps). */
function withFigureLinks(s: Sentence, ms: FigMention[] | undefined): ReactNode {
  if (!ms?.length) return s.text;
  const out: ReactNode[] = [];
  let at = 0;
  for (const m of [...ms].sort((a, b) => a.span[0] - b.span[0] || a.span[1] - b.span[1])) {
    const [a, z] = m.span;
    if (a < at) continue;
    out.push(s.text.slice(at, a));
    out.push(
      <button
        key={a}
        type="button"
        className="fig-ref"
        data-fig={`${s.id}:${a}`}
        title={`${figLabel(m)}: show it and its AI description`}
        onClick={(ev) => {
          ev.stopPropagation();
          openFigure(m);
        }}
      >
        {s.text.slice(a, z)}
      </button>,
    );
    at = z;
  }
  out.push(s.text.slice(at));
  return out;
}

export function ReflowSettings() {
  const r = useStore((s) => s.reflow);
  const set = (p: Partial<typeof r>) => useStore.setState({ reflow: { ...r, ...p } });
  return (
    <section>
      <div className="panel-sub">Text view</div>
      <label className="row">
        Font
        <select value={r.font} onChange={(e) => set({ font: e.target.value })}>
          <option value="serif">Serif</option>
          <option value="sans">Sans</option>
          <option value="atkinson">Atkinson Hyperlegible</option>
          <option value="opendyslexic">OpenDyslexic</option>
        </select>
      </label>
      <label className="row">
        Size <input type="range" min={14} max={30} value={r.size} onChange={(e) => set({ size: Number(e.target.value) })} /> {r.size}px
      </label>
      <label className="row">
        Line spacing <input type="range" min={1.2} max={2.4} step={0.1} value={r.lineHeight} onChange={(e) => set({ lineHeight: Number(e.target.value) })} /> {r.lineHeight.toFixed(1)}
      </label>
      <label className="row">
        Width <input type="range" min={40} max={110} value={r.width} onChange={(e) => set({ width: Number(e.target.value) })} /> {r.width} ch
      </label>
    </section>
  );
}
