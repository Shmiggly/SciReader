import { useLayoutEffect } from "react";
import type { RefObject } from "react";

/** Shift a popup anchored in page coordinates so it stays inside the visible part of the PDF scroller. */
export function fitInScroller(el: HTMLElement | null) {
  if (!el) return;
  el.style.transform = "";
  const scroller = el.closest(".pdf-scroller");
  if (!scroller) return;
  const view = scroller.getBoundingClientRect();
  const box = el.getBoundingClientRect();
  let dy = 0;
  if (box.bottom > view.bottom - 8) dy = view.bottom - 8 - box.bottom;
  if (box.top + dy < view.top + 8) dy = view.top + 8 - box.top;
  if (dy) el.style.transform = `translateY(${Math.round(dy)}px)`;
}

/** Re-fit after every render (content such as a description or an image can change the popup's height). */
export function useFitInScroller(ref: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => fitInScroller(ref.current));
}
