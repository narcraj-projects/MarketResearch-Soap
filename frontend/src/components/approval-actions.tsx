"use client";
import { useRef, useState } from "react";
import { command } from "@/lib/run-api";
export function ApprovalActions({ runId, gate, requestId, version, hash, runVersion, enabled, reload }: { runId: string; gate: "shortlist" | "report"; requestId: string | null; version: number; hash: string; runVersion: number; enabled: boolean; reload: () => Promise<void> }) {
  const keys = useRef<Record<string, string>>({}); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function decide(decision: string) {
    if (!requestId) return; setBusy(true); setError("");
    const fingerprint = `${requestId}:${hash}:${decision}`;
    const key = keys.current[fingerprint] ||= crypto.randomUUID();
    try { await command(`/api/runs/${runId}/${gate}-decision`, { request_id: requestId, artifact_version: version, artifact_hash: hash, expected_run_version: runVersion, decision }, key); await reload(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Decision could not be confirmed."); }
    finally { setBusy(false); }
  }
  return <div className="approval-controls"><div className="actions"><button className="button outline" disabled={!enabled || busy} onClick={() => void decide("request_changes")}>Request changes</button><button className="button outline" disabled={!enabled || busy} onClick={() => void decide("reject")}>Reject</button><button className="button primary" disabled={!enabled || busy} onClick={() => void decide("approve")}>{busy ? "Recording decision..." : gate === "report" ? "Approve report" : "Approve shortlist"}</button></div>{error && <p role="alert" className="form-error">{error}</p>}</div>;
}
