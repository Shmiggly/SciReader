// arXiv source mode: replace OCR'd equations with the paper's own LaTeX (needs internet once).
import { useState } from "react";
import { api, type Doc } from "./api";
import { useStore } from "./store";

export function ArxivSource() {
  const doc = useStore((s) => s.doc)!;
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (doc.source?.type !== "arxiv") return null;
  const run = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.post<{ matched: number; equations: number }>(`/api/docs/${doc.id}/arxiv-source`);
      const fresh = await api.get<Doc>(`/api/docs/${doc.id}`);
      const cur = useStore.getState().current;
      useStore.getState().setDoc(fresh);
      useStore.setState({ current: cur });
      setMsg(`Using the exact LaTeX for ${r.matched} of ${r.equations} equations; re-checking narrations now.`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section>
      <div className="panel-sub">Equations from arXiv source</div>
      <div className="muted small">This paper is on arXiv ({doc.source.ref}). Use its LaTeX source for exact equations instead of OCR (internet needed once).</div>
      <button onClick={() => void run()} disabled={busy}>{busy ? "Fetching…" : "Use arXiv LaTeX"}</button>
      {msg && <div className="small">{msg}</div>}
    </section>
  );
}
