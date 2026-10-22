// App state (zustand) and the playback engine: per-sentence audio, prefetch, word timing, media keys.
import { create } from "zustand";
import { api, type Block, type Doc, type Rect, type Sentence, type TtsResult, type TtsWord } from "./api";
import type { EqResult } from "./Equations";

// "auto": natural wording, long equations as their AI summary; "full_all": natural wording at any length;
// "precise": the explicit wording the gate checks ("sub", "open paren"). A saved "full" (the old default) loads as "auto".
export type EqMode = "auto" | "full_all" | "precise" | "brief" | "skip";

// When playback stops at a figure mention to show the figure and describe it: "first": the first time playback reaches
// a mention of it, wherever reading started (each panel letter once, the whole figure once); "every": at every mention;
// "caption": like "first", but reads the caption, no AI; "off": never interrupts (captions are read where they are).
export type FigMode = "first" | "every" | "caption" | "off";
export const FIG_MODES: FigMode[] = ["first", "every", "caption", "off"];

export const SKIP_LABELS: Record<string, string> = {
  page_furniture: "Page headers, footers, page numbers",
  footnote: "Footnotes",
  bibliography: "Reference list",
  figure_body: "Figure bodies (captions are read)",
  table_body: "Table bodies",
  affiliation: "Affiliations and emails",
  authors: "Author list",
  front_matter: "Journal front matter",
  boilerplate: "Publisher boilerplate",
};

export const PRESETS: Record<string, { label: string; sentence: string; word: string; outline?: string }> = {
  sun: { label: "Sun", sentence: "rgba(255, 214, 10, 0.28)", word: "rgba(255, 170, 0, 0.55)" },
  mint: { label: "Mint", sentence: "rgba(52, 199, 140, 0.22)", word: "rgba(20, 160, 100, 0.45)" },
  sky: { label: "Sky", sentence: "rgba(64, 156, 255, 0.20)", word: "rgba(30, 110, 230, 0.42)" },
  contrast: { label: "High contrast", sentence: "rgba(255, 235, 0, 0.45)", word: "rgba(0, 0, 0, 0.0)", outline: "#000" },
};

export interface FigMention {
  sentence_id: string;
  span: [number, number];
  key: string;
  number: string;
  panels: string[];
  figure_id: string;
  first: boolean;
  /** The mention's boxes on the page (absent for OCR'd papers). */
  rects?: Rect[];
}

/** Where a popup opens: next to a mention or a sentence (the PDF page or the text view). */
export interface PopAnchor {
  sid: string;
  span: [number, number] | null;
  rects: Rect[] | null;
}

export interface FigPopup {
  key: string;
  figure_id: string;
  label: string;
  anchor: PopAnchor;
  description: string | null;
  caption: string | null;
  pinned: boolean;
  loading: boolean;
  /** "narration": opened by playback at a mention (closes with the next sentence unless pinned); "click": opened by
   * the reader (stays until closed, and "Hear it" returns to the reading position afterwards). */
  origin: "narration" | "click";
  captionOnly: boolean;
  /** Changes when a popup is opened anew (it is then placed next to its mention); narration that replaces the content
   * of an open popup keeps it, so a popup stays where it was dragged while it is open. */
  seq: number;
}

/** Figure targets described in this session: "3" for the whole figure, "3:b" per panel letter. */
const narrated = new Set<string>();
/** Figures described in this session (their captions are not read again where they are). */
const describedFigs = new Set<string>();
let figQueue: FigMention[] = [];
let figSeq = 0;

function figUnits(m: { number: string; panels: string[] }): string[] {
  return m.panels.length ? m.panels.map((p) => `${m.number}:${p}`) : [m.number];
}

export function figLabel(m: { number: string; panels: string[] }): string {
  return `Figure ${m.number}${m.panels.length ? `, panel${m.panels.length > 1 ? "s" : ""} ${m.panels.join(", ")}` : ""}`;
}

/** The figures to describe after a sentence ends, in the current mode (each target once per sentence). */
export function dueFigures(sid: string): FigMention[] {
  const st = get();
  if (st.figMode === "off") return [];
  const seen = new Set<string>();
  const out: FigMention[] = [];
  for (const m of st.figMentions.get(sid) ?? []) {
    if (seen.has(m.key)) continue;
    seen.add(m.key);
    if (st.figMode === "every" || figUnits(m).some((u) => !narrated.has(u))) out.push(m);
  }
  return out;
}

interface Entry {
  s: Sentence;
  b: Block;
  idx: number;
}

interface State {
  doc: Doc | null;
  index: Map<string, Entry>;
  order: string[];
  current: string | null;
  tts: TtsResult | null;
  word: TtsWord | null;
  playing: boolean;
  loading: boolean;
  error: string | null;
  speed: number;
  voice: string;
  volume: number;
  eqMode: EqMode;
  focus: boolean;
  follow: boolean;
  preset: string;
  skips: Record<string, boolean>;
  announceSections: boolean;
  scale: number;
  /** Zoom follows the width of the PDF area (on until the user zooms by hand). */
  fitWidth: boolean;
  eqResults: Record<string, EqResult>;
  eqState: string;
  eqMessage: string;
  eqOpen: string | null;
  /** Figure mentions by sentence. */
  figMentions: Map<string, FigMention[]>;
  /** Figure id → reading-order index of the sentence with its last mention. */
  figLastMention: Map<string, number>;
  figPopup: FigPopup | null;
  /** The popup (detailKey) whose longer description ("More detail", D) is on its way: its button spins meanwhile. */
  figDetail: string | null;
  figMode: FigMode;
  /** The reading position's highlight and the focus dimming are hidden (a click beside the pages while paused). */
  highlightHidden: boolean;
  selection: string[] | null;
  eqRef: { blockId: string; sentenceId: string } | null;
  view: "pdf" | "text";
  autoPause: boolean;
  reflow: { font: string; size: number; lineHeight: number; width: number };
  setDoc: (doc: Doc | null) => void;
  set: (p: Partial<State>) => void;
}

export const useStore = create<State>((set) => ({
  doc: null,
  index: new Map(),
  order: [],
  current: null,
  tts: null,
  word: null,
  playing: false,
  loading: false,
  error: null,
  speed: 1,
  voice: "af_heart",
  volume: 1,
  eqMode: "auto",
  focus: true,
  follow: true,
  preset: "sun",
  skips: Object.fromEntries(Object.keys(SKIP_LABELS).map((k) => [k, true])),
  announceSections: true,
  scale: 1.4,
  fitWidth: true,
  eqResults: {},
  eqState: "idle",
  eqMessage: "",
  eqOpen: null,
  figMentions: new Map(),
  figLastMention: new Map(),
  figPopup: null,
  figDetail: null,
  figMode: "first",
  highlightHidden: false,
  selection: null,
  eqRef: null,
  view: "pdf",
  autoPause: false,
  reflow: { font: "atkinson", size: 19, lineHeight: 1.7, width: 70 },
  setDoc: (doc) => {
    const index = new Map<string, Entry>();
    const order: string[] = [];
    if (doc) {
      for (const b of doc.blocks) {
        for (const s of b.sentences) {
          index.set(s.id, { s, b, idx: order.length });
          order.push(s.id);
        }
      }
    }
    set({ doc, index, order, current: null, tts: null, word: null, playing: false, error: null, eqResults: {}, eqState: "idle", eqOpen: null, figMentions: new Map(), figLastMention: new Map(), figPopup: null, figDetail: null, highlightHidden: false, selection: null, fitWidth: true });
    narrated.clear();
    describedFigs.clear();
    figReady.clear();
    figOrder = [];
    lastWanted = "";
  },
  set: (p) => set(p),
}));

const get = () => useStore.getState();

// ---------------------------------------------------------------------------------------------
// Sequence: which sentences are read when playback flows on.

export function isReadable(b: Block): boolean {
  const st = get();
  if (b.type === "heading" && !st.announceSections) return false;
  if (b.type === "figure" || b.type === "table") return false;
  if (b.skip_reason === "junk") return false;
  if (b.type === "caption" && captionTakenOver(b)) return false;
  if (b.skip_reason && st.skips[b.skip_reason] !== false) return false;
  return b.sentences.length > 0;
}

/** A mentioned figure's caption isn't read where it is when the figure was described at a mention in this session, or
 * will be at a later one; otherwise (reading started after its mentions) it is, so no figure goes by unannounced. */
function captionTakenOver(b: Block): boolean {
  const st = get();
  if (st.figMode === "off" || !b.figure_id) return false;
  const last = st.figLastMention.get(b.figure_id);
  if (last === undefined) return false;
  if (describedFigs.has(b.figure_id)) return true;
  return last > (st.index.get(b.sentences[0]?.id)?.idx ?? Infinity);
}

// ---------------------------------------------------------------------------------------------
// Figure mentions: loading, and preparing the descriptions the reader is about to reach first.

/** Mentions in reading order (reading-order index of their sentence). */
let figOrder: { idx: number; m: FigMention }[] = [];
/** Targets whose AI description is ready. */
const figReady = new Set<string>();
let lastWanted = "";

export async function loadFigures(docId: string) {
  try {
    const r = await api.get<{ mentions: FigMention[]; descriptions: Record<string, { description: string | null }> }>(`/api/docs/${docId}/figures`);
    const st = get();
    if (st.doc?.id !== docId) return;
    const byS = new Map<string, FigMention[]>();
    const last = new Map<string, number>();
    figOrder = [];
    for (const m of r.mentions) {
      byS.set(m.sentence_id, [...(byS.get(m.sentence_id) ?? []), m]);
      const idx = st.index.get(m.sentence_id)?.idx;
      if (idx === undefined) continue;
      figOrder.push({ idx, m });
      last.set(m.figure_id, Math.max(idx, last.get(m.figure_id) ?? -1));
    }
    for (const [k, d] of Object.entries(r.descriptions)) if (d.description) figReady.add(k);
    useStore.setState({ figMentions: byS, figLastMention: last });
    if (st.current) wantFiguresFrom(st.current);
  } catch {
    /* not parsed yet, or the backend is busy: no figure narration */
  }
}

/** Ask the background job to describe the next few targets from a sentence on first (reading may start anywhere). */
function wantFiguresFrom(sid: string) {
  const st = get();
  const at = st.index.get(sid)?.idx;
  if (!st.doc || at === undefined || st.figMode === "caption" || st.figMode === "off") return;
  const keys: string[] = [];
  for (const { idx, m } of figOrder) {
    if (idx < at || keys.includes(m.key) || figReady.has(m.key)) continue;
    if (st.figMode === "first" && figUnits(m).every((u) => narrated.has(u))) continue;
    keys.push(m.key);
    if (keys.length === 3) break;
  }
  const wanted = keys.join(",");
  if (!wanted || wanted === lastWanted) return;
  lastWanted = wanted;
  void api.post(`/api/docs/${st.doc.id}/figures/prepare?first=${wanted}`).catch(() => undefined);
}

export function noteFigureReady(key: string, description: string | null) {
  if (description) figReady.add(key);
}

function nextReadable(fromIdx: number, dir: 1 | -1): string | null {
  const { order, index } = get();
  for (let i = fromIdx + dir; i >= 0 && i < order.length; i += dir) {
    const e = index.get(order[i])!;
    if (isReadable(e.b)) return order[i];
  }
  return null;
}

// ---------------------------------------------------------------------------------------------
// Audio engine

const audio = new Audio();
audio.preload = "auto";
(audio as HTMLAudioElement & { preservesPitch: boolean }).preservesPitch = true;
const ttsCache = new Map<string, Promise<TtsResult>>();
let token = 0;
let raf = 0;

/** Forget fetched speech (e.g. after a lexicon change): the next play re-renders with the new pronunciations. */
export function clearSpeechCache() {
  ttsCache.clear();
}

function ttsUrl(sid: string): string {
  const { doc, voice, eqMode } = get();
  return `/api/tts/${doc!.id}/${sid}?voice=${encodeURIComponent(voice)}&eq_mode=${eqMode}`;
}

function fetchTts(sid: string): Promise<TtsResult> {
  const url = ttsUrl(sid);
  let p = ttsCache.get(url);
  if (!p) {
    p = api.get<TtsResult>(url).then((r) => {
      // Warm the browser cache with the audio itself.
      fetch(r.audio_url).catch(() => undefined);
      return r;
    });
    p.catch(() => ttsCache.delete(url));
    ttsCache.set(url, p);
  }
  return p;
}

function prefetch(fromSid: string, n = 4) {
  const e = get().index.get(fromSid);
  if (!e) return;
  let idx = e.idx;
  let sid: string | null = fromSid;
  for (let k = 0; k < n; k++) {
    sid = nextReadable(idx, 1);
    if (!sid) break;
    idx = get().index.get(sid)!.idx;
    void fetchTts(sid).catch(() => undefined);
  }
}

function tick() {
  const { tts, word } = get();
  if (kind !== "sentence") {
    // A detour or a figure description: no word of the paused sentence is being spoken.
    if (word) useStore.setState({ word: null });
  } else if (tts) {
    const t = audio.currentTime;
    let w: TtsWord | null = null;
    for (const x of tts.words) {
      if (t >= x.start && t < x.end + 0.05) {
        w = x;
        break;
      }
    }
    if (w !== word) useStore.setState({ word: w });
  }
  raf = requestAnimationFrame(tick);
}

audio.addEventListener("play", () => {
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(tick);
});
audio.addEventListener("pause", () => cancelAnimationFrame(raf));
audio.addEventListener("ended", () => {
  cancelAnimationFrame(raf);
  if (kind === "detour") {
    if (detour) endDetour();
    else useStore.setState({ playing: false, word: null });
    return;
  }
  if (kind === "say") {
    useStore.setState({ playing: false, word: null });
    return;
  }
  // Figure narration: after a sentence that mentions a figure (or panel) due in the Figures mode, show and describe it.
  const cur = get().current;
  if (kind === "sentence" && cur) figQueue = dueFigures(cur);
  continueReading();
});

/** After a sentence or a figure description: the next due figure, else the next sentence. */
function continueReading() {
  if (figQueue.length) {
    void playFigure(figQueue.shift()!);
    return;
  }
  const st = get();
  const cur = st.current;
  if (st.figPopup && !st.figPopup.pinned) useStore.setState({ figPopup: null });
  const e = cur ? st.index.get(cur) : undefined;
  const next = e ? nextReadable(e.idx, 1) : null;
  if (next && st.autoPause && e && st.index.get(next)!.b.id !== e.b.id) {
    // Auto-pause: stop at the end of each paragraph; Space continues with the next one.
    useStore.setState({ playing: false, word: null, current: next, tts: null });
    return;
  }
  if (next) void playSentence(next);
  else useStore.setState({ playing: false, word: null });
}

/** What the audio element holds: a sentence, a figure description in the reading flow, a detour (a cited equation, a
 * figure heard from its popup: reading resumes where it was afterwards) or AI text read once. */
type AudioKind = "sentence" | "figure" | "detour" | "say";
let kind: AudioKind = "sentence";
/** The sentence the loaded audio belongs to: play resumes it only while that sentence is current. */
let audioSid: string | null = null;
let detour: {
  src: string;
  time: number;
  tts: TtsResult | null;
  current: string | null;
  wasPlaying: boolean;
  kind: AudioKind;
  audioSid: string | null;
  queue: FigMention[];
} | null = null;
let eqRefCursor: { sid: string; i: number } | null = null;

/** Pause what is playing, play something else, then come back to the same spot (playing again if it was).
 * `detailFor`: the figure popup whose "More detail" this is (its button spins until the audio starts). */
async function startDetour(load: () => Promise<{ audio_url: string }>, detailFor: string | null = null): Promise<void> {
  const st = get();
  // A detour from a detour (E pressed again) keeps the original place.
  const d = detour ?? (detour = { src: audio.src, time: audio.currentTime, tts: st.tts, current: st.current, wasPlaying: st.playing, kind, audioSid, queue: figQueue });
  const my = ++token;
  audio.pause();
  kind = "detour";
  audioSid = d.current;
  figQueue = [];
  useStore.setState({ word: null, loading: true, error: null, figDetail: detailFor });
  try {
    const r = await load();
    if (my !== token) return;
    audio.src = r.audio_url;
    audio.playbackRate = get().speed;
    audio.volume = get().volume;
    await audio.play();
    if (my !== token) return;
    useStore.setState({ loading: false, playing: true });
  } catch (err) {
    if (my !== token) return;
    const msg = err instanceof Error ? err.message : String(err);
    endDetour();
    useStore.setState({ error: msg });
  } finally {
    detailDone(my);
  }
}

/** The key "More detail" requests are tracked by: a popup as opened (its seq) and the target it shows. */
export function detailKey(p: FigPopup): string {
  return `${p.seq}:${p.key}`;
}

/** A request that may have been "More detail" is over (playing, failed): its button stops spinning. Requests that
 * replace it (a new token) set figDetail themselves. */
function detailDone(my: number) {
  if (my === token && get().figDetail) useStore.setState({ figDetail: null });
}

function endDetour(resume = true) {
  const d = detour!;
  detour = null;
  kind = d.kind;
  audioSid = d.audioSid;
  figQueue = d.queue;
  useStore.setState({ eqRef: null, tts: d.tts, current: d.current, loading: false });
  if (d.src) {
    audio.src = d.src;
    audio.currentTime = d.time;
    audio.playbackRate = get().speed;
  }
  if (resume && d.wasPlaying && d.src) {
    const my = token;
    void audio.play().then(
      () => my === token && useStore.setState({ playing: true }),
      () => my === token && useStore.setState({ playing: false }),
    );
  } else useStore.setState({ playing: false });
}

const EQ_REF = /\b(?:Eqs?\.|Eqn\.|Equations?)\s*\(?\s*(\d{1,3}[a-z]?)\s*\)?(?:\s*(?:and|,|–|-)\s*\(?(\d{1,3}[a-z]?)\)?)?/gi;

/** The numbers an equation answers to: "6"; a stacked "1a,b" also to "1a", "1b" and "1". */
function eqLabels(n: string | null | undefined): string[] {
  const m = n ? /^(\d+)([a-z](?:,[a-z])*)$/.exec(n) : null;
  return !n ? [] : m ? [n, ...m[2].split(",").map((l) => m[1] + l), m[1]] : [n];
}

/** Equation blocks cited by a sentence ("Eq. (3)", "Eqs. 4 and 5", IOP's "equation (9) and (10)"), in order. */
export function citedEquations(sid: string | null): Block[] {
  const st = get();
  const e = sid ? st.index.get(sid) : undefined;
  if (!e || !st.doc || e.b.type === "equation") return [];
  const eqs = st.doc.blocks.filter((x) => x.type === "equation" && x.eq_number);
  const out: Block[] = [];
  for (const m of e.s.text.matchAll(EQ_REF)) {
    for (const raw of [m[1], m[2]]) {
      if (!raw) continue;
      const n = raw.toLowerCase();
      const b = eqs.find((x) => x.eq_number === n) ?? eqs.find((x) => eqLabels(x.eq_number).includes(n));
      if (b && !out.includes(b)) out.push(b);
    }
  }
  return out;
}

/** `E`: pause, show the cited equation over the text, read it, then resume where reading was. */
export async function readCitedEquation() {
  const st = get();
  const refs = citedEquations(st.current);
  if (!refs.length || !st.current) return;
  const i = eqRefCursor && eqRefCursor.sid === st.current ? (eqRefCursor.i + 1) % refs.length : 0;
  eqRefCursor = { sid: st.current, i };
  const b = refs[i];
  useStore.setState({ eqRef: { blockId: b.id, sentenceId: st.current } });
  await startDetour(() => fetchTts(b.sentences[0].id));
}

/** Read arbitrary (AI) text aloud once, without continuing the paper afterwards. */
export async function sayText(text: string, label = "") {
  const my = ++token;
  audio.pause();
  detour = null;
  useStore.setState({ loading: true, word: null, figDetail: null });
  try {
    const r = await api.post<TtsResult>("/api/tts/say", { text, voice: get().voice, label });
    if (my !== token) return;
    kind = "say";
    audioSid = null;
    useStore.setState({ tts: null });
    audio.src = r.audio_url;
    audio.playbackRate = get().speed;
    await audio.play();
    useStore.setState({ loading: false, playing: true });
  } catch (err) {
    if (my !== token) return;
    useStore.setState({ loading: false, error: err instanceof Error ? err.message : String(err) });
  }
}

/** Jump to a sentence (citation chips): stop, highlight it and bring it into view. */
export function jumpTo(sid: string) {
  token++;
  audio.pause();
  kind = "sentence";
  detour = null;
  useStore.setState({ current: sid, word: null, playing: false, loading: false, follow: true, selection: null, eqRef: null, figDetail: null, highlightHidden: false });
}

/** A click beside the pages (or beside the text column): while paused or stopped, hide the highlight and the focus
 * dimming, keeping the reading position (Space, Continue or a click on a sentence bring them back). While reading it
 * does nothing, so a stray click never stops the voice or the auto-follow. */
export function hideHighlight() {
  const st = get();
  if (st.playing || st.loading || !st.current || st.highlightHidden) return;
  useStore.setState({ highlightHidden: true });
}

// The hidden highlight comes back as soon as anything plays, the reading position moves, or follow is switched back
// on ("Back to reading position").
useStore.subscribe((s, prev) => {
  if (s.highlightHidden && (s.current !== prev.current || (s.playing && !prev.playing) || (s.follow && !prev.follow))) {
    useStore.setState({ highlightHidden: false });
  }
});

/** Shift+click: select the sentences between the current one and the clicked one. */
export function selectRangeTo(sid: string) {
  const st = get();
  const a = st.current ? st.index.get(st.current) : undefined;
  const b = st.index.get(sid);
  if (!b) return;
  if (!a) {
    useStore.setState({ selection: [sid] });
    return;
  }
  const [lo, hi] = a.idx <= b.idx ? [a.idx, b.idx] : [b.idx, a.idx];
  useStore.setState({ selection: st.order.slice(lo, Math.min(hi + 1, lo + 40)) });
}

interface FigTts extends TtsResult {
  description: string | null;
  caption_part: string | null;
}

function figTtsUrl(key: string, detail: boolean, captionOnly: boolean): string {
  const { doc, voice } = get();
  return `/api/tts/${doc!.id}/figure/${key}?voice=${encodeURIComponent(voice)}${detail ? "&detail=true" : ""}${captionOnly ? "&caption_only=true" : ""}`;
}

function markDescribed(m: { number: string; panels: string[]; figure_id: string }) {
  for (const u of figUnits(m)) narrated.add(u);
  describedFigs.add(m.figure_id);
}

/** In the reading flow: show the figure where it was mentioned and describe it (playback never waits for the AI: the
 * caption is read if the description isn't ready). */
async function playFigure(m: FigMention, detail = false): Promise<void> {
  const my = ++token;
  const st = get();
  markDescribed(m);
  kind = "figure";
  audioSid = st.current;
  const captionOnly = st.figMode === "caption" && !detail;
  const prev = st.figPopup;
  const pop: FigPopup = {
    key: m.key, figure_id: m.figure_id, label: figLabel(m), anchor: { sid: m.sentence_id, span: m.span, rects: m.rects ?? null },
    description: prev?.key === m.key ? prev.description : null, caption: prev?.key === m.key ? prev.caption : null,
    pinned: prev?.pinned ?? false, loading: true, origin: "narration", captionOnly, seq: prev ? prev.seq : ++figSeq,
  };
  useStore.setState({ figPopup: pop, figDetail: detail ? detailKey(pop) : null, word: null, loading: true });
  try {
    const r = await api.get<FigTts>(figTtsUrl(m.key, detail, captionOnly));
    if (my !== token) return;
    if (!detail) noteFigureReady(m.key, r.description);
    useStore.setState((s) => ({
      figPopup: s.figPopup?.key === m.key ? { ...s.figPopup, description: captionOnly ? s.figPopup.description : r.description, caption: r.caption_part, loading: false } : s.figPopup,
      tts: null,
    }));
    audio.src = r.audio_url;
    audio.playbackRate = get().speed;
    audio.volume = get().volume;
    await audio.play();
    if (my !== token) return;
    useStore.setState({ loading: false, playing: true });
  } catch (err) {
    if (my !== token) return;
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("interrupted") || msg.includes("aborted")) return;
    useStore.setState((s) => ({ error: msg, loading: false, figPopup: s.figPopup ? { ...s.figPopup, loading: false } : null }));
    continueReading(); // a failing figure never stops the paper
  } finally {
    detailDone(my);
  }
}

/** The mention a popup was opened from, as a narration target. */
function popupMention(p: FigPopup): FigMention {
  const [, number = "", letters = ""] = /^(\d+)([a-z]*)$/.exec(p.key) ?? [];
  return { sentence_id: p.anchor.sid, span: p.anchor.span ?? [0, 0], key: p.key, number, panels: letters.split("").filter(Boolean), figure_id: p.figure_id, first: false, rects: p.anchor.rects ?? undefined };
}

/** Click on a figure mention: show the figure with its AI description, without moving the reading position. */
export function openFigure(m: FigMention) {
  const st = get();
  if (!st.doc) return;
  useStore.setState({
    figPopup: {
      key: m.key, figure_id: m.figure_id, label: figLabel(m), anchor: { sid: m.sentence_id, span: m.span, rects: m.rects ?? null },
      description: null, caption: null, pinned: true, loading: true, origin: "click", captionOnly: st.figMode === "caption", seq: ++figSeq,
    },
  });
}

/** "Hear it" in the figure popup (and `D` once its narration is over): read it, then go back to where reading was. */
export function hearFigure(detail = false) {
  const p = get().figPopup;
  if (!p || !get().doc) return;
  const captionOnly = p.captionOnly && !detail;
  markDescribed(popupMention(p));
  void startDetour(async () => {
    const r = await api.get<FigTts>(figTtsUrl(p.key, detail, captionOnly));
    if (!detail) noteFigureReady(p.key, r.description);
    useStore.setState((s) =>
      s.figPopup?.key === p.key
        ? { figPopup: { ...s.figPopup, description: captionOnly ? s.figPopup.description : r.description ?? s.figPopup.description, caption: r.caption_part ?? s.figPopup.caption, loading: false } }
        : {},
    );
    return r;
  }, detail ? detailKey(p) : null);
}

/** `D`: more detail on the figure currently shown (the local AI may take 5–15 s; pressing again meanwhile does nothing). */
export function figureDetail() {
  const p = get().figPopup;
  if (!p || get().figDetail === detailKey(p)) return;
  if (kind === "figure" && p.origin === "narration") {
    // While its description plays in the reading flow: the longer one replaces it, then reading goes on.
    figQueue = [];
    void playFigure(popupMention(p), true);
  } else hearFigure(true);
}

export function closeFigure() {
  useStore.setState({ figPopup: null });
}

export async function playSentence(sid: string): Promise<void> {
  const my = ++token;
  figQueue = [];
  kind = "sentence";
  audioSid = sid;
  detour = null;
  if (get().eqRef) useStore.setState({ eqRef: null });
  if (get().selection) useStore.setState({ selection: null });
  if (get().figPopup && !get().figPopup!.pinned) useStore.setState({ figPopup: null });
  const st = get();
  if (!st.doc || !st.index.has(sid)) return;
  audio.pause();
  useStore.setState({ current: sid, loading: true, word: null, error: null, playing: true, figDetail: null });
  saveSoon();
  wantFiguresFrom(sid);
  try {
    const r = await fetchTts(sid);
    if (my !== token) return;
    useStore.setState({ tts: r });
    audio.src = r.audio_url;
    audio.playbackRate = get().speed;
    audio.volume = get().volume;
    await audio.play();
    if (my !== token) return;
    useStore.setState({ loading: false, playing: true });
    prefetch(sid);
    updateMediaSession();
  } catch (err) {
    if (my !== token) return;
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("interrupted") || msg.includes("aborted")) return;
    useStore.setState({ loading: false, playing: false, error: msg });
  }
}

export function togglePlay() {
  const st = get();
  if (st.playing || st.loading) {
    token++;
    audio.pause();
    // Paused while a detour was still loading: drop it, back to where reading was.
    if (kind === "detour" && detour && st.loading) endDetour(false);
    useStore.setState({ playing: false, loading: false, figDetail: null });
    return;
  }
  const own = kind === "sentence" ? st.tts?.sentence_id === st.current : kind !== "say" && audioSid === st.current;
  if (st.current && audio.src && own && !audio.ended) {
    audio.playbackRate = st.speed;
    void audio.play().then(() => useStore.setState({ playing: true }));
    return;
  }
  if (kind === "figure" && own && st.figPopup?.origin === "narration") {
    // Paused before the description started: play it now (the sentence was already read).
    void playFigure(popupMention(st.figPopup));
    return;
  }
  const start = st.current ?? nextReadable(-1, 1);
  if (start) void playSentence(start);
}

export function stop() {
  token++;
  audio.pause();
  audio.removeAttribute("src");
  kind = "sentence";
  audioSid = null;
  detour = null;
  figQueue = [];
  useStore.setState({ playing: false, loading: false, word: null, tts: null, figDetail: null });
}

export function step(dir: 1 | -1) {
  const st = get();
  const e = st.current ? st.index.get(st.current) : undefined;
  const target = nextReadable(e ? e.idx : -1, dir);
  if (target) {
    if (st.playing || st.loading) void playSentence(target);
    else useStore.setState({ current: target, word: null });
  }
}

export function stepParagraph(dir: 1 | -1) {
  const st = get();
  const e = st.current ? st.index.get(st.current) : undefined;
  if (!e) return step(dir);
  let target: string | null = null;
  if (dir === 1) {
    let idx = e.idx;
    for (;;) {
      const n = nextReadable(idx, 1);
      if (!n) break;
      const ne = st.index.get(n)!;
      if (ne.b.id !== e.b.id) {
        target = n;
        break;
      }
      idx = ne.idx;
    }
  } else {
    const first = e.b.sentences[0].id;
    if (first !== e.s.id) target = first;
    else {
      const prev = nextReadable(e.idx, -1);
      if (prev) target = st.index.get(prev)!.b.sentences[0].id;
    }
  }
  if (target) {
    if (st.playing || st.loading) void playSentence(target);
    else useStore.setState({ current: target, word: null });
  }
}

export function nextSection() {
  const st = get();
  const e = st.current ? st.index.get(st.current) : undefined;
  for (let i = (e ? e.idx : -1) + 1; i < st.order.length; i++) {
    const ent = st.index.get(st.order[i])!;
    if (ent.b.type === "heading") {
      const target = st.announceSections ? ent.s.id : nextReadable(i, 1);
      if (target) void playSentence(target);
      return;
    }
  }
}

export function setSpeed(speed: number) {
  const s = Math.min(3, Math.max(0.5, Math.round(speed * 100) / 100));
  audio.playbackRate = s;
  useStore.setState({ speed: s });
  saveSoon();
}

export function setVolume(v: number) {
  audio.volume = v;
  useStore.setState({ volume: v });
}

export function setVoiceOrMode(p: { voice?: string; eqMode?: EqMode }) {
  useStore.setState(p);
  saveSoon();
  const cur = get().current;
  if (get().playing && cur) void playSentence(cur);
}

/** The Figures menu: takes effect at the next mention (nothing playing is interrupted). */
export function setFigMode(figMode: FigMode) {
  useStore.setState({ figMode });
  saveSoon();
  const cur = get().current;
  if (cur) wantFiguresFrom(cur);
}

export function sentenceAt(sid: string | null): Entry | undefined {
  return sid ? get().index.get(sid) : undefined;
}

// ---------------------------------------------------------------------------------------------
// Reading state persistence

let saveTimer: number | undefined;
function saveSoon() {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(saveNow, 1200);
}

export function saveNow() {
  const st = get();
  if (!st.doc) return;
  const e = st.current ? st.index.get(st.current) : undefined;
  const section = e ? st.doc.outline.find((o) => o.id === e.b.section_id) : undefined;
  void api
    .put(`/api/state/${st.doc.id}`, {
      sentence_id: st.current,
      section_title: section?.title ?? null,
      snippet: e ? (e.b.type === "equation" ? `Equation ${e.b.eq_number ?? ""}`.trim() : e.s.text.slice(0, 90)) : null,
      speed: st.speed,
      voice: st.voice,
      eq_mode: st.eqMode,
      fig_mode: st.figMode,
    })
    .catch(() => undefined);
}

// ---------------------------------------------------------------------------------------------
// Media Session (headset and keyboard media keys)

function updateMediaSession() {
  if (!("mediaSession" in navigator)) return;
  const st = get();
  navigator.mediaSession.metadata = new MediaMetadata({ title: st.doc?.title ?? "SciReader", artist: "SciReader" });
}

if ("mediaSession" in navigator) {
  navigator.mediaSession.setActionHandler("play", () => togglePlay());
  navigator.mediaSession.setActionHandler("pause", () => togglePlay());
  navigator.mediaSession.setActionHandler("nexttrack", () => step(1));
  navigator.mediaSession.setActionHandler("previoustrack", () => step(-1));
}
