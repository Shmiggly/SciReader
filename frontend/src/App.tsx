// App shell: start screen (open a paper, recent papers, samples) or the reader.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Doc, type ParseStatus, type RecentPaper, type Sample } from "./api";
import { ModelManager } from "./ModelManager";
import { Reader } from "./Reader";
import { useStore } from "./store";

export default function App() {
  const doc = useStore((s) => s.doc);
  const [opening, setOpening] = useState<{ id: string; status: ParseStatus } | null>(null);

  const openDoc = useCallback(async (id: string) => {
    const d = await api.get<Doc>(`/api/docs/${id}`);
    useStore.getState().setDoc(d);
    setOpening(null);
    history.replaceState(null, "", `#doc=${id}`);
  }, []);

  // Poll parse status while a paper is being prepared.
  useEffect(() => {
    if (!opening) return;
    if (opening.status.state === "ready") {
      void openDoc(opening.id);
      return;
    }
    if (opening.status.state === "error") return;
    const t = window.setTimeout(async () => {
      try {
        const st = await api.get<ParseStatus>(`/api/docs/${opening.id}/status`);
        setOpening({ id: opening.id, status: st });
      } catch (err) {
        setOpening({ id: opening.id, status: { state: "error", message: String(err), progress: 0 } });
      }
    }, 600);
    return () => window.clearTimeout(t);
  }, [opening, openDoc]);

  // Reopen the paper from the URL hash after a reload.
  useEffect(() => {
    const m = location.hash.match(/doc=([0-9a-f]{16})/);
    if (m) setOpening({ id: m[1], status: { state: "queued", message: "Opening", progress: 0 } });
  }, []);

  if (doc) {
    return (
      <Reader
        onClose={() => {
          useStore.getState().setDoc(null);
          history.replaceState(null, "", "#");
        }}
      />
    );
  }
  return <StartScreen opening={opening} setOpening={setOpening} />;
}

function StartScreen({
  opening,
  setOpening,
}: {
  opening: { id: string; status: ParseStatus } | null;
  setOpening: (o: { id: string; status: ParseStatus } | null) => void;
}) {
  const [recent, setRecent] = useState<RecentPaper[]>([]);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [arxiv, setArxiv] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [showModels, setShowModels] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.get<RecentPaper[]>("/api/docs/recent").then(setRecent, () => undefined);
    api.get<Sample[]>("/api/samples").then(setSamples, () => undefined);
  }, []);

  const run = async (p: Promise<{ id: string; status: ParseStatus }>) => {
    setError(null);
    try {
      setOpening(await p);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const onFiles = (files: FileList | null) => {
    const f = files?.[0];
    if (f) void run(api.upload(f));
  };

  return (
    <div
      className={`start ${drag ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        onFiles(e.dataTransfer.files);
      }}
    >
      <div className="start-inner">
        <h1>
          <img src="/icon.svg" alt="" width={40} height={40} /> SciReader
        </h1>
        <button className="ghost models-link" onClick={() => setShowModels(true)}>▦ Models</button>
        {showModels && <ModelManager onClose={() => setShowModels(false)} />}
        <p className="tagline">Listen to scientific papers, with the real PDF in front of you. Equations, units and chemistry read like a scientist would. Fully offline.</p>

        {opening ? (
          <div className="card progress-card">
            <div className="progress-title">{opening.status.state === "error" ? "Couldn't prepare this paper" : "Preparing the paper…"}</div>
            <div className="progress-msg">{opening.status.message}</div>
            {opening.status.state !== "error" && (
              <div className="progress">
                <div className="progress-fill" style={{ width: `${Math.max(3, opening.status.progress * 100)}%` }} />
              </div>
            )}
            <div className="muted small">The first open of a paper takes about a minute (layout, equations, tables). After that it opens instantly.</div>
            {opening.status.state === "error" && <button onClick={() => setOpening(null)}>Back</button>}
          </div>
        ) : (
          <>
            <div className="card drop" onClick={() => fileInput.current?.click()} role="button" tabIndex={0}>
              <div className="drop-title">Drop a PDF here, or click to choose one</div>
              <div className="muted small">Your paper stays on this computer.</div>
              <input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => onFiles(e.target.files)} />
            </div>
            <form
              className="arxiv-row"
              onSubmit={(e) => {
                e.preventDefault();
                if (arxiv.trim()) void run(api.post("/api/docs/arxiv", { ref: arxiv.trim() }));
              }}
            >
              <input value={arxiv} onChange={(e) => setArxiv(e.target.value)} placeholder="…or paste an arXiv ID or link (needs internet)" />
              <button type="submit">Open</button>
            </form>
            {error && <div className="error-box">{error}</div>}

            {recent.length > 0 && (
              <section>
                <h2>Recent papers</h2>
                <ul className="list">
                  {recent.map((r) => (
                    <li key={r.id}>
                      <button className="list-item" onClick={() => setOpening({ id: r.id, status: { state: "ready", message: "", progress: 1 } })}>
                        <span className="li-title">{r.title || r.name}</span>
                        {r.position?.section_title && <span className="muted small">Stopped in {r.position.section_title}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {samples.length > 0 && (
              <section>
                <h2>Sample papers</h2>
                <ul className="list">
                  {samples.map((s) => (
                    <li key={s.id}>
                      <button className="list-item" onClick={() => void run(api.post(`/api/samples/${s.id}/open`))}>
                        <span className="li-title">{s.title}</span>
                        <span className="muted small">{s.license}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
