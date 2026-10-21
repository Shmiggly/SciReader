// The PDF, exactly as published (pdf.js canvas), with overlays: sentence/word highlight, focus dimming,
// click-to-read hit testing and "spoken text" on hover.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import type { Rect } from "./api";
import { PRESETS, playSentence, sentenceAt, useStore } from "./store";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

interface HitRect {
  sid: string;
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
        if (cancelled) return;
        setPdf(p);
        // Fit width on first open.
        const el = scroller.current;
        const w = doc.pages[0]?.width ?? 612;
        if (el) useStore.setState({ scale: Math.max(0.6, Math.min(2.5, (el.clientWidth - 48) / w)) });
      },
      (err) => setLoadError(String(err)),
    );
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [doc.id]);

  // Hit-test index: page -> sentence rectangles.
  const hits = useMemo(() => {
    const m = new Map<number, HitRect[]>();
    for (const b of doc.blocks) {
      if (b.type === "figure" || b.type === "table") continue;
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
  }, [current, follow, scale, pdf]);

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
      useStore.setState({ scale: Math.max(0.5, Math.min(3, s * (ev.deltaY < 0 ? 1.1 : 1 / 1.1))) });
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
            setRef={(el) => (pageRefs.current[p.index] = el)}
          />
        ))}
      </div>
      <ZoomBar />
      {!follow && current && (playing || true) && (
        <button className="back-to-reading" onClick={() => useStore.setState({ follow: true })}>
          ↓ Back to reading position
        </button>
      )}
    </div>
  );
}

function ZoomBar() {
  const scale = useStore((s) => s.scale);
  const set = (v: number) => useStore.setState({ scale: Math.max(0.5, Math.min(3, v)) });
  return (
    <div className="zoom-bar" aria-label="Zoom">
      <button onClick={() => set(scale / 1.15)} title="Zoom out">−</button>
      <span>{Math.round(scale * 100)}%</span>
      <button onClick={() => set(scale * 1.15)} title="Zoom in">+</button>
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
  setRef: (el: HTMLDivElement | null) => void;
}

function Page({ index, width, height, scale, pdf, hits, setRef }: PageProps) {
  const div = useRef<HTMLDivElement | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [visible, setVisible] = useState(false);
  const [hover, setHover] = useState<{ sid: string; x: number; y: number } | null>(null);
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
    const sid = hitTest(ev);
    if (sid) {
      useStore.setState({ follow: true });
      void playSentence(sid);
    }
  };

  const onMove = (ev: React.MouseEvent) => {
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
      style={{ width: width * scale, height: height * scale }}
      onClick={onClick}
      onMouseMove={onMove}
      onMouseLeave={() => {
        window.clearTimeout(hoverTimer.current);
        setHover(null);
      }}
      data-page={index}
    >
      <canvas ref={canvas} style={{ width: width * scale, height: height * scale }} />
      <Overlay page={index} scale={scale} />
      {hover && <HoverTip sid={hover.sid} x={hover.x} y={hover.y} pageWidth={width * scale} />}
    </div>
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
