// Model manager: voices (preview, download, delete, default), local LLMs via Ollama (pull with progress,
// delete, which model does which job, GPU fit), parser models, storage and "Ready offline".
import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { useStore } from "./store";

interface VoiceRow { id: string; name: string; gender: string; accent: string; grade: string; installed: boolean }
interface LlmRow { name: string; size_gb: number; params?: string; quant?: string; vram_gb?: number | null }
interface Overview {
  tts: { engine: { name: string; license: string; size_mb: number; gpu: string; quality: string }; weights_installed: boolean; ready: boolean; device: string; default_voice: string; voices: VoiceRow[] };
  parser: { repo: string; name: string; installed: boolean }[];
  math_speech: { installed: boolean };
  llm: { ollama: boolean; url: string; installed: LlmRow[]; loaded: string[]; catalog: { name: string; role: string; size_gb: number; installed: boolean; vram_gb?: number | null }[]; jobs: { reader: string; checker: string } };
  gpu: { name: string | null; total_gb: number | null; used_gb: number | null; kokoro_gb: number };
  storage: { data_dir: string; data_bytes: number; hf_cache: string; hf_bytes: number; ollama_models_dir: string; how_to_change: string };
  offline_ready: boolean;
  ai_ready: boolean;
}

const gb = (b: number) => `${(b / 1e9).toFixed(1)} GB`;

export function ModelManager({ onClose }: { onClose: () => void }) {
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pulling, setPulling] = useState<{ name: string; status: string; frac: number } | null>(null);
  const [pullName, setPullName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const previewAudio = useRef<HTMLAudioElement | null>(null);

  const refresh = () => api.get<Overview>("/api/models").then(setOv, (e) => setError(String(e)));
  useEffect(() => {
    void refresh();
  }, []);

  const preview = async (voice: string) => {
    setBusy(`preview:${voice}`);
    try {
      const r = await api.get<{ audio_url: string }>(`/api/voices/${voice}/preview`);
      previewAudio.current?.pause();
      previewAudio.current = new Audio(r.audio_url);
      await previewAudio.current.play();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  };

  const act = async (key: string, fn: () => Promise<unknown>, confirmText?: string) => {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(key);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const pull = async (name: string) => {
    setError(null);
    setPulling({ name, status: "Starting…", frac: 0 });
    try {
      const r = await fetch("/api/models/llm/pull", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
      const reader = r.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const events = buf.split("\n\n");
        buf = events.pop() ?? "";
        for (const ev of events) {
          const line = ev.replace(/^data: /, "");
          try {
            const j = JSON.parse(line);
            if (j.error) throw new Error(j.error);
            const frac = j.total ? (j.completed ?? 0) / j.total : 0;
            setPulling({ name, status: j.status ?? "", frac });
          } catch (e) {
            if (e instanceof Error && !e.message.startsWith("Unexpected")) throw e;
          }
        }
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPulling(null);
    }
  };

  const fit = (model: string): string | null => {
    if (!ov?.gpu.total_gb) return null;
    const m = ov.llm.installed.find((x) => x.name === model) ?? ov.llm.catalog.find((x) => x.name === model);
    const need = m?.vram_gb;
    if (!need) return null;
    const other = Math.max(0, (ov.gpu.used_gb ?? 0) - (ov.llm.loaded.length ? 6 : 0));
    const total = need + ov.gpu.kokoro_gb + other;
    return total > ov.gpu.total_gb ? `Needs ~${need} GB; with the voice and other apps (~${total.toFixed(1)} GB) it won't fit in ${ov.gpu.total_gb} GB. It will run slower or swap.` : null;
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Models">
        <div className="panel-head">
          <h2>Models</h2>
          <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {error && <div className="error-box">{error}</div>}
        {!ov ? (
          <div className="muted">Loading…</div>
        ) : (
          <>
            <div className={ov.offline_ready ? "offline ok" : "offline"}>
              {ov.offline_ready ? "Ready offline ✓ Everything needed to read papers is on this computer." : "Not ready offline yet: download the items marked below."}
              {ov.ai_ready ? " AI features: ready." : " AI features: need Ollama and the reader model."}
            </div>

            <section>
              <h3>Voice engine</h3>
              <div className="row">
                <b>{ov.tts.engine.name}</b>
                <span className="muted small">{ov.tts.engine.license} · {ov.tts.engine.size_mb} MB · {ov.tts.engine.gpu}</span>
                <span className={ov.tts.ready ? "pill ok" : "pill"}>{ov.tts.ready ? `loaded on ${ov.tts.device.toUpperCase()}` : ov.tts.weights_installed ? "loading…" : "not downloaded"}</span>
              </div>
              <div className="voice-grid">
                {ov.tts.voices.map((v) => (
                  <div key={v.id} className={`voice ${v.id === ov.tts.default_voice ? "default" : ""}`}>
                    <div>
                      <b>{v.name}</b> <span className="muted small">{v.accent} {v.gender} · grade {v.grade}</span>
                    </div>
                    <div className="voice-actions">
                      {v.installed ? (
                        <>
                          <button onClick={() => void preview(v.id)} disabled={busy === `preview:${v.id}`} title="Preview">
                            {busy === `preview:${v.id}` ? "…" : "▶"}
                          </button>
                          {v.id === ov.tts.default_voice ? (
                            <span className="pill ok">default</span>
                          ) : (
                            <>
                              <button onClick={() => void act(`def:${v.id}`, async () => { await api.put("/api/models/voices/default", { voice: v.id }); useStore.setState({ voice: v.id }); })}>Set default</button>
                              <button className="ghost" onClick={() => void act(`del:${v.id}`, () => api.del(`/api/models/voices/${v.id}`), `Delete the ${v.name} voice from this computer?`)} title="Delete">🗑</button>
                            </>
                          )}
                        </>
                      ) : (
                        <button onClick={() => void act(`dl:${v.id}`, () => api.post(`/api/models/voices/${v.id}/download`))} disabled={busy === `dl:${v.id}`}>
                          {busy === `dl:${v.id}` ? "Downloading…" : "Download (0.5 MB)"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h3>Language models (local, through Ollama)</h3>
              {!ov.llm.ollama ? (
                <div className="muted">Ollama isn't running at {ov.llm.url}. The reader works without it; start Ollama for the AI features.</div>
              ) : (
                <>
                  <div className="jobs">
                    {(["reader", "checker"] as const).map((job) => (
                      <label key={job}>
                        <span className="ctl-label">{job === "reader" ? "Reader (narration, figures, explain, ask)" : "Checker (back-transcription)"}</span>
                        <select value={ov.llm.jobs[job]} onChange={(e) => void act(`job:${job}`, () => api.put("/api/models/llm/jobs", { [job]: e.target.value }))}>
                          {ov.llm.installed.map((m) => (
                            <option key={m.name} value={m.name}>{m.name}</option>
                          ))}
                        </select>
                        {job === "reader" && fit(ov.llm.jobs.reader) && <span className="warn small">⚠ {fit(ov.llm.jobs.reader)}</span>}
                      </label>
                    ))}
                  </div>
                  <table className="llm-table">
                    <tbody>
                      {ov.llm.installed.map((m) => (
                        <tr key={m.name}>
                          <td><b>{m.name}</b>{ov.llm.loaded.includes(m.name) && <span className="pill ok">in memory</span>}</td>
                          <td className="muted small">{m.params} {m.quant}</td>
                          <td className="small">{m.size_gb} GB on disk{m.vram_gb ? ` · ~${m.vram_gb} GB GPU` : ""}</td>
                          <td>
                            <button className="ghost" onClick={() => void act(`dllm:${m.name}`, () => api.del(`/api/models/llm/${m.name}`), `Delete ${m.name} from Ollama?`)} title="Delete">🗑</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="catalog">
                    {ov.llm.catalog.filter((c) => !c.installed).map((c) => (
                      <div key={c.name} className="row">
                        <b>{c.name}</b>
                        <span className="muted small">{c.role} · {c.size_gb} GB</span>
                        <button onClick={() => void pull(c.name)} disabled={!!pulling}>Download</button>
                      </div>
                    ))}
                    <form className="row" onSubmit={(e) => { e.preventDefault(); if (pullName.trim()) void pull(pullName.trim()); }}>
                      <input value={pullName} onChange={(e) => setPullName(e.target.value)} placeholder="Other Ollama model, e.g. qwen3.5:2b" />
                      <button type="submit" disabled={!!pulling}>Download</button>
                    </form>
                    {pulling && (
                      <div className="pull-progress">
                        <div className="small">{pulling.name}: {pulling.status} {pulling.frac ? `${Math.round(pulling.frac * 100)}%` : ""}</div>
                        <div className="progress"><div className="progress-fill" style={{ width: `${Math.max(2, pulling.frac * 100)}%` }} /></div>
                      </div>
                    )}
                  </div>
                </>
              )}
            </section>

            <section>
              <h3>Paper understanding</h3>
              {ov.parser.map((p) => (
                <div key={p.repo} className="row">
                  <span>{p.name}</span>
                  <span className={p.installed ? "pill ok" : "pill"}>{p.installed ? "downloaded" : "missing (run setup)"}</span>
                </div>
              ))}
              <div className="row">
                <span>Equation speech (Speech Rule Engine)</span>
                <span className={ov.math_speech.installed ? "pill ok" : "pill"}>{ov.math_speech.installed ? "installed" : "missing"}</span>
              </div>
            </section>

            <section>
              <h3>Storage</h3>
              <div className="small">Papers and audio cache: <code>{ov.storage.data_dir}</code> ({gb(ov.storage.data_bytes)})</div>
              <div className="small">Voice and parser models: <code>{ov.storage.hf_cache}</code> ({gb(ov.storage.hf_bytes)})</div>
              <div className="small">Language models: <code>{ov.storage.ollama_models_dir}</code></div>
              <div className="muted small">{ov.storage.how_to_change}</div>
              {ov.gpu.name && <div className="muted small">GPU: {ov.gpu.name}, {ov.gpu.used_gb} / {ov.gpu.total_gb} GB in use</div>}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
