// Reader layout: outline (left), PDF (center), side panel (right), playback bar (bottom).
import { useEffect, useState } from "react";
import { api, type PaperState, type Voice } from "./api";
import { AiPanel } from "./AiPanel";
import { ArxivSource } from "./ArxivSource";
import { AudiobookExport } from "./Audiobook";
import { useEquationChecks } from "./Equations";
import { ModelManager } from "./ModelManager";
import { PdfView } from "./PdfView";
import { ReflowSettings, ReflowView } from "./ReflowView";
import { Pronunciation } from "./Pronunciation";
import {
  type EqMode,
  type FigMention,
  citedEquations,
  figureDetail,
  readCitedEquation,
  PRESETS,
  SKIP_LABELS,
  isReadable,
  nextSection,
  playSentence,
  saveNow,
  sentenceAt,
  setSpeed,
  setVoiceOrMode,
  setVolume,
  step,
  stepParagraph,
  stop,
  togglePlay,
  useStore,
} from "./store";

export function Reader({ onClose }: { onClose: () => void }) {
  const doc = useStore((s) => s.doc)!;
  const [resume, setResume] = useState<PaperState["position"] | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showModels, setShowModels] = useState(false);
  const [showAi, setShowAi] = useState(false);
  const [showPron, setShowPron] = useState(false);
  const view = useStore((s) => s.view);

  // Restore per-paper settings and offer to continue.
  useEffect(() => {
    api.get<PaperState>(`/api/state/${doc.id}`).then(
      (st) => {
        const p: Partial<ReturnType<typeof useStore.getState>> = {};
        if (st.speed) p.speed = st.speed;
        if (st.voice) p.voice = st.voice;
        if (st.eq_mode) p.eqMode = st.eq_mode as EqMode;
        useStore.setState(p);
        if (st.position?.sentence_id && sentenceAt(st.position.sentence_id)) {
          setResume(st.position);
          useStore.setState({ current: st.position.sentence_id });
        }
        saveNow();
      },
      () => undefined,
    );
  }, [doc.id]);

  useKeyboard();
  useEquationChecks(doc.id);
  useEffect(() => {
    api.get<{ mentions: FigMention[] }>(`/api/docs/${doc.id}/figures`).then((r) => {
      const byS = new Map<string, FigMention[]>();
      for (const m of r.mentions) byS.set(m.sentence_id, [...(byS.get(m.sentence_id) ?? []), m]);
      useStore.setState({ figMentions: byS, mentionedFigs: new Set(r.mentions.map((m) => m.figure_id)) });
    }, () => undefined);
    void api.post(`/api/docs/${doc.id}/figures/prepare`).catch(() => undefined);
  }, [doc.id]);

  return (
    <div className="reader">
      <header className="topbar">
        <button className="ghost" onClick={() => { saveNow(); stop(); onClose(); }} title="Close paper">
          ← Papers
        </button>
        <div className="doc-title" title={doc.title}>{doc.title}</div>
        <button className="ghost" onClick={() => useStore.setState({ view: view === "pdf" ? "text" : "pdf" })} title="Switch between the PDF and a clean text view">{view === "pdf" ? "¶ Text view" : "▤ PDF view"}</button>
        <button className="ghost" onClick={() => setShowAi((v) => !v)} aria-pressed={showAi}>✦ AI</button>
        <button className="ghost" onClick={() => setShowPron(true)}>Aa Pronunciation</button>
        <button className="ghost" onClick={() => setShowModels(true)}>▦ Models</button>
        <button className="ghost" onClick={() => setShowSettings((v) => !v)} aria-pressed={showSettings}>
          ⚙ Reading settings
        </button>
      </header>
      {showModels && <ModelManager onClose={() => setShowModels(false)} />}
      {showPron && <Pronunciation onClose={() => setShowPron(false)} />}
      <div className="reader-body">
        <Outline />
        <main className="center">
          {doc.ocr && (
            <div className="resume-banner">
              <span>Scanned PDF: the text came from OCR, so highlights follow paragraphs rather than single words, and some words may be misread.</span>
            </div>
          )}
          {resume && (
            <div className="resume-banner">
              <span>
                Continue from <b>{resume.section_title || "where you stopped"}</b>: “{resume.snippet}…”
              </span>
              <button className="primary" onClick={() => { setResume(null); useStore.setState({ follow: true }); void playSentence(resume.sentence_id); }}>
                ▶ Continue
              </button>
              <button className="ghost" onClick={() => setResume(null)}>Dismiss</button>
            </div>
          )}
          {view === "text" ? <ReflowView /> : <PdfView />}
        </main>
        {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
        {showAi && !showSettings && <AiPanel onClose={() => setShowAi(false)} />}
      </div>
      <PlaybackBar />
    </div>
  );
}

function Outline() {
  const doc = useStore((s) => s.doc)!;
  const current = useStore((s) => s.current);
  const curSection = sentenceAt(current)?.b.section_id;
  const start = (blockId: string) => {
    const idx = doc.blocks.findIndex((b) => b.id === blockId);
    const st = useStore.getState();
    for (let i = idx; i < doc.blocks.length; i++) {
      const b = doc.blocks[i];
      if (isReadable(b) && b.sentences.length) {
        useStore.setState({ follow: true });
        void playSentence(b.sentences[0].id);
        return;
      }
    }
    void st;
  };
  return (
    <nav className="outline" aria-label="Sections">
      <div className="outline-title">Sections</div>
      {doc.outline.length === 0 && <div className="muted small">No headings found</div>}
      {doc.outline.map((o) => (
        <button
          key={o.id}
          className={`outline-item level-${Math.min(o.level, 3)} ${curSection === o.id ? "active" : ""}`}
          onClick={() => start(o.block_id)}
          title={`Read from “${o.title}”`}
        >
          {o.title}
        </button>
      ))}
      <div className="outline-stats muted small">
        {doc.stats.sentences} sentences · {doc.stats.equations} equations · {doc.pages.length} pages
      </div>
    </nav>
  );
}

function PlaybackBar() {
  const playing = useStore((s) => s.playing);
  const loading = useStore((s) => s.loading);
  const speed = useStore((s) => s.speed);
  const voice = useStore((s) => s.voice);
  const volume = useStore((s) => s.volume);
  const eqMode = useStore((s) => s.eqMode);
  const focus = useStore((s) => s.focus);
  const error = useStore((s) => s.error);
  const tts = useStore((s) => s.tts);
  const current = useStore((s) => s.current);
  const [voices, setVoices] = useState<Voice[]>([]);
  useEffect(() => {
    api.get<{ voices: Voice[] }>("/api/voices").then((r) => setVoices(r.voices), () => undefined);
  }, []);
  const e = sentenceAt(current);
  const spoken = tts && tts.sentence_id === current ? tts.spoken : e?.s.spoken;

  return (
    <footer className="playbar">
      <div className="transport">
        <button onClick={() => stepParagraph(-1)} title="Previous paragraph (Shift+←)">⏮</button>
        <button onClick={() => step(-1)} title="Previous sentence (←)">◀</button>
        <button className="play" onClick={togglePlay} title="Play / pause (Space)" aria-label={playing ? "Pause" : "Play"}>
          {loading ? "…" : playing ? "❚❚" : "▶"}
        </button>
        <button onClick={() => step(1)} title="Next sentence (→)">▶</button>
        <button onClick={() => stepParagraph(1)} title="Next paragraph (Shift+→)">⏭</button>
        <button onClick={nextSection} title="Next section">§›</button>
      </div>
      <div className="now-reading" title="Exactly what is being spoken">
        {citedEquations(current).length > 0 && (
          <button className="chip eq-hint" onClick={() => void readCitedEquation()} title="Hear the cited equation (E)">
            Eq. {citedEquations(current).map((b) => b.eq_number).join(", ")} · press E
          </button>
        )}
        {error ? <span className="error-text">{error}</span> : spoken ? <span>{spoken}</span> : <span className="muted">Click any sentence in the paper to start reading.</span>}
      </div>
      <div className="controls">
        <label title="Speed (+ / −)">
          <span className="ctl-label">Speed</span>
          <button onClick={() => setSpeed(speed - 0.1)}>−</button>
          <span className="speed">{speed.toFixed(1)}×</span>
          <button onClick={() => setSpeed(speed + 0.1)}>+</button>
        </label>
        <label>
          <span className="ctl-label">Voice</span>
          <select value={voice} onChange={(ev) => setVoiceOrMode({ voice: ev.target.value })}>
            {(voices.length ? voices : [{ id: voice, name: voice, gender: "", accent: "", grade: "" }]).map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} ({v.accent ? `${v.accent[0]}${v.gender[0]}` : ""}{v.grade ? `, ${v.grade}` : ""})
              </option>
            ))}
          </select>
        </label>
        <label title="How display equations are read">
          <span className="ctl-label">Equations</span>
          <select value={eqMode} onChange={(ev) => setVoiceOrMode({ eqMode: ev.target.value as EqMode })}>
            <option value="full">Full</option>
            <option value="brief">Brief (AI)</option>
            <option value="skip">Skip</option>
          </select>
        </label>
        <label title="Volume">
          <span className="ctl-label">Vol</span>
          <input type="range" min={0} max={1} step={0.05} value={volume} onChange={(ev) => setVolume(Number(ev.target.value))} />
        </label>
        <button className={focus ? "toggle on" : "toggle"} onClick={() => useStore.setState({ focus: !focus })} title="Focus mode (F)">
          Focus
        </button>
      </div>
    </footer>
  );
}

function SettingsPanel({ onClose }: { onClose: () => void }) {
  const skips = useStore((s) => s.skips);
  const preset = useStore((s) => s.preset);
  const announce = useStore((s) => s.announceSections);
  return (
    <aside className="side-panel">
      <div className="panel-head">
        <b>Reading settings</b>
        <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
      </div>
      <section>
        <div className="panel-sub">Skip while reading</div>
        {Object.entries(SKIP_LABELS).map(([k, label]) => (
          <label key={k} className="check">
            <input type="checkbox" checked={skips[k] !== false} onChange={(ev) => useStore.setState({ skips: { ...skips, [k]: ev.target.checked } })} />
            {label}
          </label>
        ))}
        <div className="muted small">Inline citation markers ([12], superscripts, author–year) are never read.</div>
      </section>
      <section>
        <div className="panel-sub">Sections</div>
        <label className="check">
          <input type="checkbox" checked={announce} onChange={(ev) => useStore.setState({ announceSections: ev.target.checked })} />
          Announce section titles
        </label>
        <label className="check">
          <input type="checkbox" checked={useStore((s) => s.figuresOn)} onChange={(ev) => useStore.setState({ figuresOn: ev.target.checked })} />
          Describe figures at first mention (AI, labeled)
        </label>
        <label className="check">
          <input type="checkbox" checked={useStore((s) => s.autoPause)} onChange={(ev) => useStore.setState({ autoPause: ev.target.checked })} />
          Pause after each paragraph (Space continues)
        </label>
      </section>
      <ReflowSettings />
      <AudiobookExport />
      <ArxivSource />
      <section>
        <div className="panel-sub">Highlight colors</div>
        <div className="presets">
          {Object.entries(PRESETS).map(([k, p]) => (
            <button key={k} className={preset === k ? "preset on" : "preset"} onClick={() => useStore.setState({ preset: k })}>
              <span className="swatch" style={{ background: p.sentence, outline: p.outline ? `2px solid ${p.outline}` : undefined }} />
              {p.label}
            </button>
          ))}
        </div>
      </section>
      <section className="muted small">
        Keys: Space play/pause · ←/→ sentence · Shift+←/→ paragraph · +/− speed · F focus · E cited equation · D figure detail
      </section>
    </aside>
  );
}

function useKeyboard() {
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const t = ev.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
      switch (ev.key) {
        case " ":
          ev.preventDefault();
          togglePlay();
          break;
        case "ArrowRight":
          ev.preventDefault();
          if (ev.shiftKey) stepParagraph(1);
          else step(1);
          break;
        case "ArrowLeft":
          ev.preventDefault();
          if (ev.shiftKey) stepParagraph(-1);
          else step(-1);
          break;
        case "+":
        case "=":
          setSpeed(useStore.getState().speed + 0.1);
          break;
        case "-":
        case "_":
          setSpeed(useStore.getState().speed - 0.1);
          break;
        case "e":
        case "E":
          readCitedEquation();
          break;
        case "d":
        case "D":
          figureDetail();
          break;
        case "f":
        case "F":
          useStore.setState({ focus: !useStore.getState().focus });
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
