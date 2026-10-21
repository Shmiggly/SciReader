// Export the paper as an audiobook (one MP3 per section, zipped with a playlist) to listen away from the screen.
import { useEffect, useState } from "react";
import { api } from "./api";
import { useStore } from "./store";

interface St { state: string; progress?: number; message?: string }

export function AudiobookExport() {
  const doc = useStore((s) => s.doc)!;
  const voice = useStore((s) => s.voice);
  const eqMode = useStore((s) => s.eqMode);
  const [st, setSt] = useState<St>({ state: "idle" });

  useEffect(() => {
    let t: number | undefined;
    const poll = async () => {
      const r = await api.get<St>(`/api/docs/${doc.id}/audiobook/status`).catch(() => ({ state: "idle" }));
      setSt(r);
      if (r.state === "running") t = window.setTimeout(poll, 1500);
    };
    void poll();
    return () => window.clearTimeout(t);
  }, [doc.id, st.state === "running"]);

  const start = async () => {
    setSt(await api.post<St>(`/api/docs/${doc.id}/audiobook?voice=${encodeURIComponent(voice)}&eq_mode=${eqMode}`));
  };

  return (
    <section>
      <div className="panel-sub">Audiobook</div>
      <div className="muted small">One MP3 per section with a playlist, using the current voice and equation mode.</div>
      <div className="row">
        <button onClick={() => void start()} disabled={st.state === "running"}>
          {st.state === "running" ? "Exporting…" : st.state === "done" ? "Export again" : "⤓ Export audiobook"}
        </button>
        {st.state === "done" && <a className="button-like" href={`/api/docs/${doc.id}/audiobook/download`}>Download .zip</a>}
      </div>
      {st.state === "running" && (
        <>
          <div className="progress"><div className="progress-fill" style={{ width: `${Math.max(3, (st.progress ?? 0) * 100)}%` }} /></div>
          <div className="muted small">{st.message}</div>
        </>
      )}
      {st.state === "error" && <div className="error-box">{st.message}</div>}
    </section>
  );
}
