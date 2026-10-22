// Types for the backend's Document JSON (v1) and small fetch helpers.

export type Rect = [number, number, number, number, number]; // page, x0, y0, x1, y1 (PDF points, top-left origin)

export interface Sentence {
  id: string;
  text: string;
  spoken: string;
  rects: Rect[];
  kind?: "equation";
}

export interface Block {
  id: string;
  type: string;
  page: number;
  bbox: [number, number, number, number];
  section_id: string | null;
  text: string;
  latex?: string;
  eq_number?: string | null;
  eq_label?: string | null;
  speech_rules?: string | null;
  figure_id?: string;
  skip_reason?: string;
  level?: number;
  sentences: Sentence[];
}

export interface OutlineEntry {
  id: string;
  title: string;
  level: number;
  block_id: string;
}

export interface Doc {
  version: number;
  id: string;
  title: string;
  authors: string[];
  source: { type: string; ref: string };
  pages: { index: number; width: number; height: number }[];
  outline: OutlineEntry[];
  blocks: Block[];
  figures: { id: string; kind: string; label: string | null; number: string | null; page: number; bbox: number[]; caption_block_id: string | null }[];
  bibliography: { id: string; label: string; text: string; doi?: string; arxiv?: string }[];
  citations: { sentence_id: string; span: [number, number]; bib_ids: string[]; rects?: Rect[] }[];
  stats: { blocks: number; sentences: number; equations: number };
  ocr?: boolean;
}

export interface ParseStatus {
  state: "new" | "queued" | "parsing" | "ready" | "error";
  message: string;
  progress: number;
}

export interface TtsWord {
  start: number;
  end: number;
  rects: Rect[];
}

export interface TtsResult {
  sentence_id: string;
  audio_url: string;
  duration: number;
  spoken: string;
  words: TtsWord[];
}

export interface RecentPaper {
  id: string;
  title: string | null;
  name: string | null;
  last_opened: number;
  position?: { sentence_id: string; section_title?: string; snippet?: string } | null;
}

export interface Sample {
  id: string;
  title: string;
  role?: string;
  license?: string;
}

export interface Voice {
  id: string;
  name: string;
  gender: string;
  accent: string;
  grade: string;
}

export interface PaperState {
  position?: { sentence_id: string; section_title?: string; snippet?: string };
  speed?: number;
  voice?: string;
  eq_mode?: string;
  fig_mode?: string;
}

async function check<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      detail = j.detail || detail;
    } catch {
      /* not json */
    }
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  get: <T>(url: string) => fetch(url).then((r) => check<T>(r)),
  post: <T>(url: string, body?: unknown) =>
    fetch(url, {
      method: "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then((r) => check<T>(r)),
  put: <T>(url: string, body: unknown) =>
    fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) =>
      check<T>(r),
    ),
  del: <T>(url: string) => fetch(url, { method: "DELETE" }).then((r) => check<T>(r)),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/docs/upload", { method: "POST", body: fd }).then((r) => check<{ id: string; status: ParseStatus }>(r));
  },
};
