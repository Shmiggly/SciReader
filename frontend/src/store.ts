// App state (zustand) and the playback engine: per-sentence audio, prefetch, word timing, media keys.
import { create } from "zustand";
import { api, type Block, type Doc, type Sentence, type TtsResult, type TtsWord } from "./api";
import type { EqResult } from "./Equations";

export type EqMode = "full" | "brief" | "skip";

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
}

export interface FigPopup {
  key: string;
  figure_id: string;
  sentence_id: string;
  label: string;
  description: string | null;
  pinned: boolean;
  loading: boolean;
}

const narrated = new Set<string>();
let figQueue: FigMention[] = [];

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
  eqResults: Record<string, EqResult>;
  eqState: string;
  eqMessage: string;
  eqOpen: string | null;
  figMentions: Map<string, FigMention[]>;
  mentionedFigs: Set<string>;
  figPopup: FigPopup | null;
  figuresOn: boolean;
  selection: string[] | null;
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
  eqMode: "full",
  focus: true,
  follow: true,
  preset: "sun",
  skips: Object.fromEntries(Object.keys(SKIP_LABELS).map((k) => [k, true])),
  announceSections: true,
  scale: 1.4,
  eqResults: {},
  eqState: "idle",
  eqMessage: "",
  eqOpen: null,
  figMentions: new Map(),
  mentionedFigs: new Set(),
  figPopup: null,
  figuresOn: true,
  selection: null,
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
    set({ doc, index, order, current: null, tts: null, word: null, playing: false, error: null, eqResults: {}, eqState: "idle", eqOpen: null, figMentions: new Map(), mentionedFigs: new Set(), figPopup: null, selection: null });
    narrated.clear();
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
  if (b.type === "caption" && st.figuresOn && b.figure_id && st.mentionedFigs.has(b.figure_id)) return false;
  if (b.skip_reason && st.skips[b.skip_reason] !== false) return false;
  return b.sentences.length > 0;
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
  if (tts) {
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
  const st = get();
  const cur = st.current;
  if (oneShot) {
    oneShot = false;
    useStore.setState({ playing: false, word: null });
    return;
  }
  // Figure narration: after the sentence that first mentions a figure (or panel), describe it.
  if (!figPlaying && cur && st.figuresOn) {
    const ms = (st.figMentions.get(cur) ?? []).filter((m) => m.first && !narrated.has(m.key));
    if (ms.length) figQueue = ms;
  }
  if (figQueue.length) {
    void playFigure(figQueue.shift()!);
    return;
  }
  figPlaying = false;
  if (st.figPopup && !st.figPopup.pinned) useStore.setState({ figPopup: null });
  const e = cur ? st.index.get(cur) : undefined;
  const next = e ? nextReadable(e.idx, 1) : null;
  if (next) void playSentence(next);
  else useStore.setState({ playing: false, word: null });
});

let figPlaying = false;
let oneShot = false;

/** Read arbitrary (AI) text aloud once, without continuing the paper afterwards. */
export async function sayText(text: string, label = "") {
  const my = ++token;
  audio.pause();
  useStore.setState({ loading: true, word: null });
  try {
    const r = await api.post<TtsResult>("/api/tts/say", { text, voice: get().voice, label });
    if (my !== token) return;
    oneShot = true;
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
  useStore.setState({ current: sid, word: null, playing: false, loading: false, follow: true, selection: null });
}

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

async function playFigure(m: FigMention, detail = false): Promise<void> {
  const my = ++token;
  const st = get();
  narrated.add(m.key);
  figPlaying = true;
  const label = `Figure ${m.number}${m.panels.length ? `, panel${m.panels.length > 1 ? "s" : ""} ${m.panels.join(", ")}` : ""}`;
  useStore.setState({
    figPopup: { key: m.key, figure_id: m.figure_id, sentence_id: m.sentence_id, label, description: null, pinned: st.figPopup?.pinned ?? false, loading: true },
    word: null,
    loading: true,
  });
  try {
    const r = await api.get<TtsResult & { description: string | null }>(
      `/api/tts/${st.doc!.id}/figure/${m.key}?voice=${encodeURIComponent(st.voice)}${detail ? "&detail=true" : ""}`,
    );
    if (my !== token) return;
    useStore.setState((s) => ({ figPopup: s.figPopup ? { ...s.figPopup, description: r.description, loading: false } : null, tts: null }));
    audio.src = r.audio_url;
    audio.playbackRate = get().speed;
    await audio.play();
    useStore.setState({ loading: false, playing: true });
  } catch (err) {
    if (my !== token) return;
    figPlaying = false;
    useStore.setState({ loading: false, error: err instanceof Error ? err.message : String(err) });
  }
}

/** `D`: more detail on the figure currently shown. */
export function figureDetail() {
  const p = get().figPopup;
  if (!p) return;
  const m: FigMention = { sentence_id: p.sentence_id, span: [0, 0], key: p.key, number: p.key.replace(/[a-h]+$/, ""), panels: p.key.replace(/^\d+/, "").split("").filter(Boolean), figure_id: p.figure_id, first: true };
  figQueue = [];
  void playFigure(m, true);
}

export function closeFigure() {
  useStore.setState({ figPopup: null });
}

export async function playSentence(sid: string): Promise<void> {
  const my = ++token;
  figQueue = [];
  figPlaying = false;
  oneShot = false;
  if (get().selection) useStore.setState({ selection: null });
  if (get().figPopup && !get().figPopup!.pinned) useStore.setState({ figPopup: null });
  const st = get();
  if (!st.doc || !st.index.has(sid)) return;
  audio.pause();
  useStore.setState({ current: sid, loading: true, word: null, error: null, playing: true });
  saveSoon();
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
  if (st.playing) {
    token++;
    audio.pause();
    useStore.setState({ playing: false, loading: false });
    return;
  }
  if (st.current && audio.src && st.tts?.sentence_id === st.current && !audio.ended) {
    audio.playbackRate = st.speed;
    void audio.play().then(() => useStore.setState({ playing: true }));
    return;
  }
  const start = st.current ?? nextReadable(-1, 1);
  if (start) void playSentence(start);
}

export function stop() {
  token++;
  audio.pause();
  audio.removeAttribute("src");
  useStore.setState({ playing: false, loading: false, word: null, tts: null });
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
