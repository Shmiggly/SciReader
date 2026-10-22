// A popup panel over the reading area (the PDF or the text view): opens next to what it belongs to, can be dragged by
// its header, and always stays inside the area (never over the top bar, the outline, the side panels or the playback
// bar). It keeps the place it was dragged to while it is open; a new one opens next to its own anchor.
import { type ReactNode, useEffect, useLayoutEffect, useRef } from "react";

const M = 8; // px between the panel and the edges of the area

export interface FloatProps {
  className: string;
  /** Width in px (capped to the area). */
  width: number;
  /** A new value opens the panel anew: placed next to its anchor, a drag forgotten. */
  openKey: string;
  /** A new value (same openKey) moves the panel to its new anchor, unless it was dragged. */
  anchorKey: string;
  /** The anchor's box in viewport pixels; null: top center of the area. */
  anchor: () => DOMRect | null;
  prefer?: "below" | "above";
  label: string;
  head: ReactNode;
  children: ReactNode;
}

interface Area {
  rect: DOMRect;
  w: number;
  h: number;
}

/** The area: the float layer the panel sits in, without the scroller's scrollbar. */
function areaOf(panel: HTMLElement): Area | null {
  const layer = panel.parentElement;
  if (!layer) return null;
  const sc = layer.parentElement?.querySelector<HTMLElement>(".pdf-scroller, .reflow-scroller");
  const bar = sc ? sc.offsetWidth - sc.clientWidth : 0;
  return { rect: layer.getBoundingClientRect(), w: layer.clientWidth - bar, h: layer.clientHeight };
}

/** Where to open: left-aligned with the anchor, below it (or above it) where it fits. */
export function placeNear(anchor: DOMRect | null, area: Area, pw: number, ph: number, prefer: "below" | "above") {
  if (!anchor) return { x: (area.w - pw) / 2, y: M, above: false };
  const below = anchor.bottom - area.rect.top + 8;
  const above = anchor.top - area.rect.top - 8 - ph;
  const fitsBelow = below + ph <= area.h - M;
  const fitsAbove = above >= M;
  const up = prefer === "above" ? fitsAbove || !fitsBelow : !fitsBelow && fitsAbove;
  return { x: anchor.left - area.rect.left, y: up ? above : below, above: up };
}

/** Keep a w × h panel at (x, y) inside the area (its top-left corner wins when it is too big). */
export function clampInto(x: number, y: number, pw: number, ph: number, area: { w: number; h: number }) {
  return { x: Math.max(M, Math.min(x, area.w - pw - M)), y: Math.max(M, Math.min(y, area.h - ph - M)) };
}

export function FloatingPanel({ className, width, openKey, anchorKey, anchor, prefer = "below", label, head, children }: FloatProps) {
  const el = useRef<HTMLDivElement>(null);
  const pos = useRef({ x: M, y: M });
  /** Placed above its anchor (and not dragged since): its bottom edge stays put as the content grows. */
  const bottom = useRef<number | null>(null);
  const placed = useRef<{ open: string; anchor: string } | null>(null);
  const dragged = useRef(false);
  const anchorFn = useRef(anchor);
  anchorFn.current = anchor;

  // Position is applied to the element directly (not through React state), so dragging doesn't re-render the content.
  const apply = () => {
    const node = el.current;
    const area = node && areaOf(node);
    if (!node || !area) return;
    const y = bottom.current !== null && !dragged.current ? bottom.current - node.offsetHeight : pos.current.y;
    pos.current = clampInto(pos.current.x, y, node.offsetWidth, node.offsetHeight, area);
    node.style.left = `${Math.round(pos.current.x)}px`;
    node.style.top = `${Math.round(pos.current.y)}px`;
  };
  const place = () => {
    const node = el.current;
    const area = node && areaOf(node);
    if (!node || !area) return;
    const p = placeNear(anchorFn.current(), area, node.offsetWidth, node.offsetHeight, prefer);
    pos.current = { x: p.x, y: p.y };
    bottom.current = p.above ? p.y + node.offsetHeight : null;
  };

  useLayoutEffect(() => {
    const p = placed.current;
    if (!p || p.open !== openKey) {
      dragged.current = false;
      place();
    } else if (p.anchor !== anchorKey && !dragged.current) place();
    placed.current = { open: openKey, anchor: anchorKey };
    apply();
  });

  // The panel's content or the area changing size: stay inside.
  useEffect(() => {
    const node = el.current;
    if (!node) return;
    const ro = new ResizeObserver(() => apply());
    ro.observe(node);
    if (node.parentElement) ro.observe(node.parentElement);
    return () => ro.disconnect();
  }, []);

  const onPointerDown = (ev: React.PointerEvent<HTMLDivElement>) => {
    if (ev.button !== 0 || (ev.target as HTMLElement).closest("button, a, input, select, textarea, summary")) return;
    const node = el.current;
    if (!node) return;
    ev.preventDefault();
    const handle = ev.currentTarget;
    handle.setPointerCapture(ev.pointerId);
    const sx = ev.clientX;
    const sy = ev.clientY;
    const { x: px, y: py } = pos.current;
    node.classList.add("dragging");
    const move = (e: PointerEvent) => {
      dragged.current = true;
      pos.current = { x: px + e.clientX - sx, y: py + e.clientY - sy };
      apply();
    };
    const up = () => {
      node.classList.remove("dragging");
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
      handle.removeEventListener("pointercancel", up);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
    handle.addEventListener("pointercancel", up);
  };

  return (
    <div
      className={`float-panel ${className}`}
      ref={el}
      role="dialog"
      aria-label={label}
      style={{ width: `min(${width}px, calc(100% - ${2 * M}px))` }}
      onClick={(ev) => ev.stopPropagation()}
    >
      <div className="float-head" onPointerDown={onPointerDown} title="Drag to move">
        <span className="grip" aria-hidden="true">⠿</span>
        {head}
      </div>
      <div className="float-body">{children}</div>
    </div>
  );
}
