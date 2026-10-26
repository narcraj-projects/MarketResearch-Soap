"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { read, displayDate } from "@/lib/run-api";
import { reportVersionLink } from "@/lib/history-types";
import type { VersionList } from "@/lib/history-types";
export function VersionPicker({ runId, side, value, setValue }: { runId: string; side: string; value: string; setValue: Dispatch<SetStateAction<string>> }) {
  const [versions, setVersions] = useState<VersionList>({ entries: [], total: 0 }), [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(async () => { try {
      const result = await read<VersionList>(`/api/runs/${runId}/versions`, controller.signal);
      if (controller.signal.aborted) return;
      setVersions(result); setValue(previous => previous || String(result.entries.find(entry => entry.comparable)?.version || ""));
    } catch { if (!controller.signal.aborted) setError("Report versions could not be loaded."); } });
    return () => controller.abort();
  }, [runId, setValue]);
  return <div className="version-picker"><label>{side} report version<select value={value} onChange={event => setValue(event.target.value)}><option value="">Choose an approved saved version</option>{versions.entries.map(entry => <option key={entry.report_id} value={entry.version} disabled={!entry.comparable}>v{entry.version} - {entry.approval.replaceAll("_", " ")}</option>)}</select></label>{error && <p role="alert">{error}</p>}
    <details><summary>{versions.total} immutable report versions</summary><ul>{versions.entries.map(entry => <li key={entry.report_id}><Link href={reportVersionLink(runId, entry.version)}>Read v{entry.version} - {entry.approval.replaceAll("_", " ")}</Link><small>As of {displayDate(entry.as_of)}<br/>SHA-256 <code>{entry.content_hash}</code></small></li>)}</ul>{versions.entries.length < versions.total && <button className="text-button" disabled={busy} onClick={async () => { setBusy(true); try { const more = await read<VersionList>(`/api/runs/${runId}/versions?offset=${versions.entries.length}`); setVersions(previous => ({ total: more.total, entries: [...previous.entries, ...more.entries] })); } catch { setError("Older versions could not be loaded."); } finally { setBusy(false); } }}>Load older report versions</button>}</details>
  </div>;
}
