"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { command, read } from "@/lib/run-api";
type Capabilities = { enabled: boolean; label: "DEMO"; scenarios: { scenario: string; title: string }[] };
export function ChaosControls() {
  const router = useRouter();
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [selected, setSelected] = useState("timeout"), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const keys = useRef<Record<string, string>>({});
  useEffect(() => { const controller = new AbortController(); queueMicrotask(async () => { try { const value = await read<Capabilities>("/api/chaos/capabilities", controller.signal); if (!controller.signal.aborted) setCapabilities(value); } catch { if (!controller.signal.aborted) setCapabilities(null); } }); return () => controller.abort(); }, []);
  if (!capabilities?.enabled) return null;
  async function create() {
    setBusy(true); setError("");
    try {
      const result = await command<{ run_id: string }>("/api/chaos/runs", { scenario: selected }, keys.current[selected] ||= crypto.randomUUID());
      router.push(`/live?run=${encodeURIComponent(result.run_id)}`);
    } catch { setError("The server did not confirm a test run. Retry the same request; production cannot enable these controls."); }
    finally { setBusy(false); }
  }
  return <section className="chaos chaos-controls" aria-labelledby="chaos-title"><div className="section-heading"><h2 id="chaos-title">Chaos switches</h2><span className="fixture-label">DEMO - TEST ONLY</span></div><p>Choose one deterministic scenario for a separate recorded DEMO run. Its sources and responses are synthetic fixtures.</p>
    <fieldset disabled={busy}><legend>Test scenario</legend>{capabilities.scenarios.map(choice => <label className="chaos-choice" key={choice.scenario}><span>{choice.title}</span><input type="radio" name="chaos-scenario" value={choice.scenario} checked={selected === choice.scenario} onChange={() => setSelected(choice.scenario)}/></label>)}</fieldset>
    <button className="button lime-button" disabled={busy} onClick={() => void create()}>{busy ? "Queuing DEMO scenario..." : "Queue separate DEMO scenario"}</button>
    <p>A dedicated local test worker advances the run. Shortlist and final approvals still apply. Interrupting the worker saves one lane before process exit; another worker resumes after lease expiry.</p>{error && <p role="alert">{error}</p>}
  </section>;
}
