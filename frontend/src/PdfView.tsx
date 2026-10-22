// The PDF, exactly as published (pdf.js canvas), with overlays: sentence/word highlight, focus dimming,
// click-to-read hit testing, "spoken text" on hover, and figure mentions that open their figure when clicked.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { Doc, Rect } from "./api";
import { type BadgeLayout, EquationBadge, layoutBadges } from "./Equations";
import { Popups } from "./Popups";
import { type FigMention, PRESETS, figLabel, openFigure, playSentence, selectRangeTo, sentenceAt, useStore } from "./store";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

interface HitRect {
  sid: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

interface FigHit {
  m: FigMention;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

let programmaticScrollUntil = 0;

export function PdfView() {
  const doc = useStore((s) => s.doc)!;
  const scale = useStore((s) => s.scale);
  const follow = useStore((s) => s.follow);
  const current = useStore((s) => s.current);
  const playing = useStore((s) => s.playing);
  useStore((s) => s.fitWidth); // re-render, and so refit, when "Fit" is switched back on
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    let cancelled = false;
    setPdf(null);
    const task = pdfjs.getDocument({
      url: `/api/docs/${doc.id}/pdf`,
      cMapUrl: "/pdfjs/cmaps/",
      cMapPacked: true,
      standardFontDataUrl: "/pdfjs/standard_fonts/",
    });
    task.promise.then(
      (p) => {
        if (!cancelled) setPdf(p);
      },
      (err) => {
        if (!cancelled) setLoadError(String(err));
      },
    );
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [doc.id]);

  // Fit to width: refit whenever the PDF area changes size until the user zooms by hand. Side panels change it in a
  // React render (checked after every render, so there is no frame at the old zoom); the window through the observer.
  const fitNow = () => {
    const el = scroller.current;
    if (!el || !useStore.getState().fitWidth) return;
    const s = Math.max(0.6, Math.min(2.5, (el.clientWidth - 48) / (doc.pages[0]?.width ?? 612)));
    if (Math.abs(s - useStore.getState().scale) > 0.004) useStore.setState({ scale: s });
  };
  useLayoutEffect(fitNow);
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const ro = new ResizeObserver(() => fitNow());
    ro.observe(el);
    return () => ro.disconnect();
  }, [doc]);

  // A zoom change keeps the sentence being read (if on screen), else the top of the view, at the same place on screen.
  // The spot is taken when the store changes, while the pages still have the old size.
  const anchor = useRef<{ page: number; y: number; at: number } | null>(null);
  useEffect(
    () =>
      useStore.subscribe((s, prev) => {
        const el = scroller.current;
        if (s.scale === prev.scale || !el) return;
        const view = el.scrollTop;
        const r = s.follow && s.current ? sentenceAt(s.current)?.s.rects[0] : undefined;
        const rPage = r ? pageRefs.current[r[0]] : null;
        if (r && rPage) {
          const at = rPage.offsetTop + r[2] * prev.scale - view;
          if (at >= 0 && at <= el.clientHeight) {
            anchor.current = { page: r[0], y: r[2], at };
            return;
          }
        }
        const pages = pageRefs.current;
        let i = 0;
        while (i + 1 < pages.length && (pages[i + 1]?.offsetTop ?? Infinity) <= view) i++;
        anchor.current = pages[i] ? { page: i, y: (view - pages[i]!.offsetTop) / prev.scale, at: 0 } : null;
      }),
    [],
  );
  useLayoutEffect(() => {
    const el = scroller.current;
    const a = anchor.current;
    anchor.current = null;
    const pageEl = a ? pageRefs.current[a.page] : null;
    if (el && a && pageEl) el.scrollTop = pageEl.offsetTop + a.y * scale - a.at;
  }, [scale]);

  const badges = useMemo(() => layoutBadges(doc, scale), [doc, scale]);

  // Hit-test index: page -> sentence rectangles.
  const hits = useMemo(() => {
    const m = new Map<number, HitRect[]>();
    for (const b of doc.blocks) {
      if (b.type === "figure" || b.type === "table" || b.skip_reason === "junk") continue;
      for (const s of b.sentences) {
        for (const r of s.rects) {
          const arr = m.get(r[0]) ?? [];
          arr.push({ sid: s.id, x0: r[1], y0: r[2], x1: r[3], y1: r[4] });
          m.set(r[0], arr);
        }
      }
    }
    return m;
  }, [doc]);

  const cites = useMemo(() => {
    const m = new Map<number, { x0: number; y0: number; x1: number; y1: number; bib: string[] }[]>();
    for (const c of doc.citations) {
      for (const r of c.rects ?? []) {
        const arr = m.get(r[0]) ?? [];
        arr.push({ x0: r[1], y0: r[2], x1: r[3], y1: r[4], bib: c.bib_ids });
        m.set(r[0], arr);
      }
    }
    return m;
  }, [doc]);

  // Figure mentions ("Fig. 3b"): page -> their boxes.
  const figMentions = useStore((s) => s.figMentions);
  const figs = useMemo(() => {
    const m = new Map<number, FigHit[]>();
    for (const ms of figMentions.values()) {
      for (const f of ms) {
        for (const r of f.rects ?? []) {
          const arr = m.get(r[0]) ?? [];
          arr.push({ m: f, x0: r[1], y0: r[2], x1: r[3], y1: r[4] });
          m.set(r[0], arr);
        }
      }
    }
    return m;
  }, [figMentions]);

  // Auto-follow: keep the current sentence in view.
  useLayoutEffect(() => {
    if (!follow || !current) return;
    const e = sentenceAt(current);
    const el = scroller.current;
    if (!e || !el) return;
    const r = e.s.rects[0];
    const pageEl = pageRefs.current[r[0]];
    if (!pageEl) return;
    const top = pageEl.offsetTop + r[2] * scale;
    const bottom = pageEl.offsetTop + r[4] * scale;
    const viewTop = el.scrollTop;
    const viewBottom = viewTop + el.clientHeight;
    if (top < viewTop + el.clientHeight * 0.12 || bottom > viewBottom - el.clientHeight * 0.25) {
      programmaticScrollUntil = Date.now() + 900;
      el.scrollTo({ top: Math.max(0, top - el.clientHeight * 0.3), behavior: "smooth" });
    }
    // Not on zoom changes: the anchor above keeps the place, and a paused reader who scrolled away stays there.
  }, [current, follow, pdf]);

  // Manual scrolling while reading stops following.
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const userScroll = () => {
      if (Date.now() < programmaticScrollUntil) return;
      const st = useStore.getState();
      if (st.follow && (st.playing || st.loading)) useStore.setState({ follow: false });
    };
    const onKey = (ev: KeyboardEvent) => {
      if (["PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown"].includes(ev.key)) userScroll();
    };
    el.addEventListener("wheel", userScroll, { passive: true });
    el.addEventListener("touchmove", userScroll, { passive: true });
    el.addEventListener("keydown", onKey);
    const onDown = (ev: MouseEvent) => {
      // Scrollbar drag: the click lands on the scroller itself, right of its content box.
      if (ev.target === el && ev.offsetX > el.clientWidth) userScroll();
    };
    el.addEventListener("mousedown", onDown);
    return () => {
      el.removeEventListener("wheel", userScroll);
      el.removeEventListener("touchmove", userScroll);
      el.removeEventListener("keydown", onKey);
      el.removeEventListener("mousedown", onDown);
    };
  }, []);

  // Ctrl+wheel zoom.
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const onWheel = (ev: WheelEvent) => {
      if (!ev.ctrlKey) return;
      ev.preventDefault();
      const s = useStore.getState().scale;
      useStore.setState({ scale: Math.max(0.5, Math.min(3, s * (ev.deltaY < 0 ? 1.1 : 1 / 1.1))), fitWidth: false });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  return (
    <div className="pdf-wrap">
      <div className="pdf-scroller" ref={scroller} tabIndex={-1}>
        {loadError && <div className="error-box">Couldn't open the PDF: {loadError}</div>}
        {doc.pages.map((p) => (
          <Page
            key={p.index}
            index={p.index}
            width={p.width}
            height={p.height}
            scale={scale}
            pdf={pdf}
            hits={hits.get(p.index) ?? []}
            cites={cites.get(p.index) ?? []}
            figs={figs.get(p.index) ?? []}
            badges={badges}
            setRef={(el) => (pageRefs.current[p.index] = el)}
          />
        ))}
      </div>
      <Popups view="pdf" />
      {!follow && current && (playing || true) && (
        <button className="back-to-reading" onClick={() => useStore.setState({ follow: true })}>
          ↓ Back to reading position
        </button>
      )}
    </div>
  );
}

/** Zoom controls (in the top bar, so they never cover the page). */
export function ZoomBar() {
  const scale = useStore((s) => s.scale);
  const fitWidth = useStore((s) => s.fitWidth);
  const set = (v: number) => useStore.setState({ scale: Math.max(0.5, Math.min(3, v)), fitWidth: false });
  return (
    <div className="zoom-bar" role="group" aria-label="Zoom">
      <button onClick={() => set(scale / 1.15)} title="Zoom out">−</button>
      <span>{Math.round(scale * 100)}%</span>
      <button onClick={() => set(scale * 1.15)} title="Zoom in">+</button>
      <button
        className={fitWidth ? "toggle on" : "toggle"}
        onClick={() => useStore.setState({ fitWidth: true })}
        aria-pressed={fitWidth}
        title="Fit the page to the width of the view (follows the window and side panels)"
      >
        Fit
      </button>
    </div>
  );
}

interface PageProps {
  index: number;
  width: number;
  height: number;
  scale: number;
  pdf: PDFDocumentProxy | null;
  hits: HitRect[];
  cites: { x0: number; y0: number; x1: number; y1: number; bib: string[] }[];
  figs: FigHit[];
  badges: BadgeLayout;
  setRef: (el: HTMLDivElement | null) => void;
}

function Page({ index, width, height, scale, pdf, hits, cites, figs, badges, setRef }: PageProps) {
  const div = useRef<HTMLDivElement | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [visible, setVisible] = useState(false);
  const [hover, setHover] = useState<{ sid: string; x: number; y: number } | null>(null);
  const [cite, setCite] = useState<{ bib: string[]; x: number; y: number } | null>(null);
  const [figHot, setFigHot] = useState<{ m: FigMention; x: number; y: number } | null>(null);
  const hoverTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const el = div.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => setVisible(entries[0].isIntersecting), { rootMargin: "1200px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!pdf || !visible || !canvas.current) return;
    let task: RenderTask | null = null;
    let cancelled = false;
    void pdf.getPage(index + 1).then((page) => {
      if (cancelled || !canvas.current) return;
      const dpr = window.devicePixelRatio || 1;
      const viewport = page.getViewport({ scale: scale * dpr });
      const c = canvas.current;
      c.width = Math.floor(viewport.width);
      c.height = Math.floor(viewport.height);
      task = page.render({ canvas: c, viewport });
      task.promise.catch(() => undefined);
    });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [pdf, visible, scale, index]);

  const hitTest = (ev: React.MouseEvent): string | null => {
    const rect = div.current!.getBoundingClientRect();
    const x = (ev.clientX - rect.left) / scale;
    const y = (ev.clientY - rect.top) / scale;
    let best: string | null = null;
    let bestDist = 6; // points of tolerance
    for (const h of hits) {
      const dx = x < h.x0 ? h.x0 - x : x > h.x1 ? x - h.x1 : 0;
      const dy = y < h.y0 ? h.y0 - y : y > h.y1 ? y - h.y1 : 0;
      const d = Math.hypot(dx, dy);
      if (d < bestDist) {
        bestDist = d;
        best = h.sid;
        if (d === 0) break;
      }
    }
    return best;
  };

  const onClick = (ev: React.MouseEvent) => {
    if (window.getSelection()?.toString()) return;
    const f = !ev.shiftKey && figAt(ev);
    if (f) {
      // The figure opens over the page; reading stays where it is.
      openFigure(f.m);
      return;
    }
    const c = citeAt(ev);
    if (c) {
      setCite(c);
      return;
    }
    const sid = hitTest(ev);
    if (sid && ev.shiftKey) {
      selectRangeTo(sid);
      return;
    }
    if (sid) {
      useStore.setState({ follow: true });
      void playSentence(sid);
    }
  };

  const citeAt = (ev: React.MouseEvent) => {
    const rect = div.current!.getBoundingClientRect();
    const x = (ev.clientX - rect.left) / scale;
    const y = (ev.clientY - rect.top) / scale;
    const c = cites.find((h) => x >= h.x0 - 1 && x <= h.x1 + 1 && y >= h.y0 - 1 && y <= h.y1 + 1);
    return c ? { bib: c.bib, x: ev.clientX - rect.left, y: ev.clientY - rect.top } : null;
  };

  /** The figure mention under the pointer (the smallest box wins where "Figs. 2–4" overlaps "Figs. 2"). */
  const figAt = (ev: React.MouseEvent) => {
    if (!figs.length) return null;
    const rect = div.current!.getBoundingClientRect();
    const x = (ev.clientX - rect.left) / scale;
    const y = (ev.clientY - rect.top) / scale;
    let best: FigHit | null = null;
    for (const h of figs) {
      if (x < h.x0 - 1 || x > h.x1 + 1 || y < h.y0 - 1 || y > h.y1 + 1) continue;
      if (!best || (h.x1 - h.x0) * (h.y1 - h.y0) < (best.x1 - best.x0) * (best.y1 - best.y0)) best = h;
    }
    return best ? { m: best.m, x: ev.clientX - rect.left, y: ev.clientY - rect.top } : null;
  };

  const onMove = (ev: React.MouseEvent) => {
    if ((ev.target as HTMLElement).closest(".cite-tip")) return;
    const f = figAt(ev);
    if (f) {
      if (figHot?.m !== f.m) setFigHot(f);
      window.clearTimeout(hoverTimer.current);
      setHover(null);
      setCite(null);
      return;
    }
    if (figHot) setFigHot(null);
    const c = citeAt(ev);
    if (c) {
      setCite(c);
      setHover(null);
      return;
    }
    if (cite) setCite(null);
    const sid = hitTest(ev);
    window.clearTimeout(hoverTimer.current);
    if (!sid) {
      setHover(null);
      return;
    }
    const rect = div.current!.getBoundingClientRect();
    const pos = { sid, x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    if (hover && hover.sid === sid) return;
    setHover(null);
    hoverTimer.current = window.setTimeout(() => setHover(pos), 900);
  };

  return (
    <div
      className="pdf-page"
      ref={(el) => {
        div.current = el;
        setRef(el);
      }}
      onClick={onClick}
      onMouseMove={onMove}
      onMouseLeave={() => {
        window.clearTimeout(hoverTimer.current);
        setHover(null);
        setCite(null);
        setFigHot(null);
      }}
      data-page={index}
      style={{ width: width * scale, height: height * scale, cursor: figHot ? "zoom-in" : undefined }}
    >
      <canvas ref={canvas} style={{ width: width * scale, height: height * scale }} />
      <Overlay page={index} scale={scale} />
      <EquationLayer page={index} scale={scale} badges={badges} />
      {figHot && <FigTip m={figHot.m} page={index} scale={scale} x={figHot.x} y={figHot.y} pageWidth={width * scale} />}
      {hover && <HoverTip sid={hover.sid} x={hover.x} y={hover.y} pageWidth={width * scale} />}
      {cite && <CiteTip bib={cite.bib} x={cite.x} y={cite.y} pageWidth={width * scale} />}
    </div>
  );
}

/** A hovered figure mention: outlined, with a hint that a click shows the figure. */
function FigTip({ m, page, scale, x, y, pageWidth }: { m: FigMention; page: number; scale: number; x: number; y: number; pageWidth: number }) {
  const left = Math.min(Math.max(8, x - 110), pageWidth - 240);
  return (
    <>
      {(m.rects ?? []).filter((r) => r[0] === page).map((r, i) => (
        <div key={i} className="fig-ref-hot" style={rectStyle(r, scale, 1)} />
      ))}
      <div className="hover-tip fig-tip" style={{ left, top: y + 18 }}>
        {figLabel(m)}: click to see it
      </div>
    </>
  );
}

function rectStyle(r: Rect, scale: number, pad = 1.5): React.CSSProperties {
  return {
    left: (r[1] - pad) * scale,
    top: (r[2] - pad) * scale,
    width: (r[3] - r[1] + 2 * pad) * scale,
    height: (r[4] - r[2] + 2 * pad) * scale,
  };
}

function Overlay({ page, scale }: { page: number; scale: number }) {
  const current = useStore((s) => s.current);
  const word = useStore((s) => s.word);
  const focus = useStore((s) => s.focus);
  const presetKey = useStore((s) => s.preset);
  const preset = PRESETS[presetKey] ?? PRESETS.sun;
  const e = sentenceAt(current);

  const selection = useStore((s) => s.selection);
  const selRects = selection ? selection.flatMap((sid) => sentenceAt(sid)?.s.rects ?? []).filter((r) => r[0] === page) : [];
  const sentenceRects = e ? e.s.rects.filter((r) => r[0] === page) : [];
  const wordRects = word ? word.rects.filter((r) => r[0] === page) : [];

  // Focus: the current paragraph stays bright, everything else is dimmed.
  let focusBox: React.CSSProperties | null = null;
  let dimWholePage = false;
  if (focus && e) {
    const rs = e.b.sentences.flatMap((s) => s.rects).filter((r) => r[0] === page);
    if (rs.length) {
      const x0 = Math.min(...rs.map((r) => r[1]));
      const y0 = Math.min(...rs.map((r) => r[2]));
      const x1 = Math.max(...rs.map((r) => r[3]));
      const y1 = Math.max(...rs.map((r) => r[4]));
      focusBox = rectStyle([page, x0, y0, x1, y1], scale, 4);
    } else {
      dimWholePage = true;
    }
  }

  return (
    <div className="overlay">
      {focusBox && (
        <>
          <div className="focus-hole" style={focusBox} />
          <div className="focus-bar" style={{ left: (focusBox.left as number) - 10, top: focusBox.top, height: focusBox.height }} />
        </>
      )}
      {dimWholePage && <div className="focus-dim-page" />}
      {selRects.map((r, i) => (
        <div key={`sel${i}`} className="hl-selection" style={rectStyle(r, scale)} />
      ))}
      {sentenceRects.map((r, i) => (
        <div key={`s${i}`} className="hl-sentence" style={{ ...rectStyle(r, scale), background: preset.sentence }} />
      ))}
      {wordRects.map((r, i) => (
        <div
          key={`w${i}`}
          className="hl-word"
          style={{
            ...rectStyle(r, scale, 1),
            background: preset.word,
            outline: preset.outline ? `2px solid ${preset.outline}` : undefined,
          }}
        />
      ))}
    </div>
  );
}

function HoverTip({ sid, x, y, pageWidth }: { sid: string; x: number; y: number; pageWidth: number }) {
  const e = sentenceAt(sid);
  if (!e) return null;
  const left = Math.min(Math.max(8, x - 160), pageWidth - 340);
  return (
    <div className="hover-tip" style={{ left, top: y + 18 }}>
      <div className="hover-tip-label">{e.b.skip_reason ? `Skipped by default (${e.b.skip_reason.replace("_", " ")})` : "Spoken as"}</div>
      <div>{e.s.spoken}</div>
    </div>
  );
}

function EquationLayer({ page, scale, badges }: { page: number; scale: number; badges: BadgeLayout }) {
  const doc = useStore((s) => s.doc)!;
  const eqOpen = useStore((s) => s.eqOpen);
  const [hot, setHot] = useState<string | null>(null);
  const eqs = useMemo(() => doc.blocks.filter((b) => b.type === "equation" && b.page === page && badges.pos.has(b.id)), [doc, page, badges]);
  if (!eqs.length) return null;
  const open = eqs.find((b) => b.id === eqOpen);
  // The equation a badge belongs to is outlined while the badge is hovered or its details are open (in Popups.tsx).
  const target = eqs.find((b) => b.id === hot) ?? open;
  return (
    <div className="eq-layer">
      {target && <div className="eq-target" style={rectStyle([page, ...target.bbox], scale, 3)} />}
      {eqs.map((b) => (
        <EquationBadge key={b.id} b={b} pos={badges.pos.get(b.id)!} compact={badges.compact} onHover={setHot} />
      ))}
    </div>
  );
}

function CiteTip({ bib, x, y, pageWidth }: { bib: string[]; x: number; y: number; pageWidth: number }) {
  const doc = useStore((s) => s.doc)!;
  const entries = bib.map((id) => doc.bibliography.find((b) => b.id === id)).filter(Boolean) as Doc["bibliography"];
  if (!entries.length) return null;
  const left = Math.min(Math.max(8, x - 180), pageWidth - 380);
  return (
    <div className="hover-tip cite-tip" style={{ left, top: y + 16, width: 370 }} onClick={(e) => e.stopPropagation()}>
      <div className="hover-tip-label">Reference{entries.length > 1 ? "s" : ""} (not read aloud)</div>
      {entries.slice(0, 4).map((b) => (
        <div key={b.id} className="cite-entry">
          <b>[{b.label}]</b> {b.text.slice(0, 260)}
          {b.doi && <> <a href={`https://doi.org/${b.doi}`} target="_blank" rel="noreferrer">DOI</a></>}
          {b.arxiv && <> <a href={`https://arxiv.org/abs/${b.arxiv}`} target="_blank" rel="noreferrer">arXiv</a></>}
        </div>
      ))}
      {entries.length > 4 && <div className="muted small">+{entries.length - 4} more</div>}
    </div>
  );
}
