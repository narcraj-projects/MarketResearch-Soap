"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, displayDate, read, tones } from "@/lib/run-api";
import { changeLabels, evidenceGroups, historicalValue, reportVersionLink } from "@/lib/history-types";
import type { ChangeKind, DatedEvidence, HistoryDiff } from "@/lib/history-types";
import type { History } from "@/lib/run-types";
import type { LoadState } from "@/lib/use-workspace";
import { Badge, DataBoundary, Hero, SourceDialog, StateFooter } from "./ui";
import type { EvidenceSelection } from "./ui";
import { VersionPicker } from "./version-picker";
export function HistoryScreen({ initialBefore = "", initialAfter = "", initialBeforeVersion = "", initialAfterVersion = "" }: { initialBefore?: string; initialAfter?: string; initialBeforeVersion?: string; initialAfterVersion?: string }) {
  const [data, setData] = useState<History>({ entries: [], total: 0 });
  const [state, setState] = useState<LoadState>("loading"), [error, setError] = useState("");
  const [beforeRun, setBeforeRun] = useState(initialBefore), [afterRun, setAfterRun] = useState(initialAfter);
  const [beforeVersion, setBeforeVersion] = useState(initialBeforeVersion), [afterVersion, setAfterVersion] = useState(initialAfterVersion);
  const [result, setResult] = useState<{ key: string; diff: HistoryDiff } | null>(null);
  const [compareError, setCompareError] = useState(""), [busy, setBusy] = useState(false), [loadingMore, setLoadingMore] = useState(false);
  const [filter, setFilter] = useState<ChangeKind | "all">("all"), [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const request = useRef<AbortController | null>(null);
  const fingerprint = [beforeRun, afterRun, beforeVersion, afterVersion].join(":");
  const active = result?.key === fingerprint ? result.diff : null;
  const load = useCallback(async (offset = 0, signal?: AbortSignal) => {
    try {
      const value = await read<History>(`/api/history?offset=${offset}`, signal);
      if (signal?.aborted) return;
      setData(previous => ({ total: value.total, entries: offset ? [...previous.entries, ...value.entries.filter(row => !previous.entries.some(old => old.id === row.id))] : value.entries }));
      setState(value.total ? "ready" : "empty"); setError("");
      if (!offset) {
        const saved = value.entries.filter(row => row.saved_report_version && row.saved_as_of).sort((a, b) => Date.parse(b.saved_as_of!) - Date.parse(a.saved_as_of!));
        const later = saved.find(row => row.id === initialAfter) || saved[0];
        const earlier = later && saved.find(row => Date.parse(row.saved_as_of!) < Date.parse(later.saved_as_of!) && row.category === later.category && row.geography === later.geography);
        setAfterRun(previous => previous || later?.id || value.entries[0]?.id || ""); setBeforeRun(previous => previous || earlier?.id || "");
      }
    } catch (cause) { if (signal?.aborted) return; setState(cause instanceof ApiError && cause.status === 401 ? "auth" : "error"); setData({ entries: [], total: 0 }); setResult(null); setError(cause instanceof Error ? cause.message : "History is unavailable."); }
  }, [initialAfter]);
  useEffect(() => { const controller = new AbortController(); queueMicrotask(() => void load(0, controller.signal)); return () => { controller.abort(); request.current?.abort(); }; }, [load]);
  async function compare() {
    request.current?.abort(); const controller = new AbortController(); request.current = controller;
    setBusy(true); setCompareError(""); setResult(null);
    try {
      const query = new URLSearchParams({ before_run: beforeRun, after_run: afterRun, before_version: beforeVersion, after_version: afterVersion });
      const diff = await read<HistoryDiff>(`/api/history/diff?${query}`, controller.signal);
      if (!controller.signal.aborted) { setResult({ key: fingerprint, diff }); setFilter("all"); }
    } catch (cause) { if (!controller.signal.aborted) setCompareError(cause instanceof ApiError && cause.status === 409 ? "Choose approved saved versions from two different runs, with advancing evidence dates and matching category, geography and customer. Drafts and incompatible scopes cannot be compared." : "Comparison could not be loaded. The selected versions may be unavailable in your account."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  function open(refs: DatedEvidence[], side: string) { const ref = refs[0]; setEvidence({ title: `${side} - dated source evidence`, source: ref.source,
    quote: refs.map(item => item.quote).filter(Boolean).join("\n\n---\n\n") || undefined, hash: refs.map(item => item.quote_hash).filter(Boolean).join("; ") || undefined,
    locator: refs.map(item => item.locator).filter(Boolean).join("; ") || undefined, note: ref.source.access_status === "ok" ? "Individual stored excerpts are separated by rules; they are not one continuous quotation. Quote integrity is not independent verification of the assertion." : "Retrieval failed or access was restricted. This does not establish discontinuation." }); }
  const selected = data.entries.find(row => row.id === afterRun);
  return <div className="history-page"><Hero active="/history" eyebrow="Market watch - dated evidence" demo={active?.label === "DEMO" || selected?.label === "DEMO"} title={<>What moved since<br/><em>last time?</em></>} side={state === "ready" && <div className="history-totals">{(["new", "changed", "gone"] as const).map(kind => <div key={kind}><strong data-testid={`history-count-${kind}`}>{active ? active.counts[kind] : "--"}</strong><span>{kind === "new" ? "newly observed" : kind === "gone" ? "source says gone" : "changed fields"}</span></div>)}</div>}>{active ? <>{displayDate(active.before.as_of)} to {displayDate(active.after.as_of)} - both are historical snapshots.</> : "Compare two saved reports. Missing retrieval never establishes a discontinued product."}</Hero>
    <DataBoundary state={state} title="historical runs" error={error} retry={() => void load()}><main id="main" tabIndex={-1} className="container history-grid"><aside><h2>Runs</h2><p className="muted">Choose an earlier run from the timeline, then a later report to compare.</p><ol className="timeline">{data.entries.map(run => <li key={run.id}><i className={run.id === beforeRun || run.id === afterRun ? "active-dot" : ""}/><button aria-pressed={run.id === beforeRun || run.id === afterRun} onClick={() => { setBeforeRun(run.id); setBeforeVersion(""); }}><span><strong data-volatile>{displayDate(run.created_at)}</strong><b>{run.id === afterRun ? "Later selected" : run.status.replaceAll("_", " ")}</b></span><small>{run.competitors} competitors - {run.geography}{run.label === "DEMO" ? " - DEMO" : ""}<br/>{run.report_versions} report versions{run.saved_report_version ? `; saved v${run.saved_report_version}` : "; no approved saved report"}{run.saved_as_of && <><br/>Captured {displayDate(run.saved_as_of)}</>}</small></button></li>)}</ol>{data.entries.length < data.total && <button className="button outline" disabled={loadingMore} onClick={async () => { setLoadingMore(true); await load(data.entries.length); setLoadingMore(false); }}>Load more saved runs</button>}</aside>
    <section className="history-changes" aria-label="Report comparison"><section className="change-card history-selector" aria-labelledby="select-reports"><h2 id="select-reports">Compare report versions</h2><div className="form-grid">{[["Earlier", beforeRun], ["Later", afterRun]].map(([side, runId]) => <div key={side}><label>{side} run<select value={runId} onChange={event => { if (side === "Earlier") { setBeforeRun(event.target.value); setBeforeVersion(""); } else { setAfterRun(event.target.value); setAfterVersion(""); } }}><option value="">Choose a run</option>{!data.entries.some(row => row.id === runId) && runId && <option value={runId}>Selected {side.toLowerCase()} run</option>}{data.entries.map(run => <option key={run.id} value={run.id}>{displayDate(run.created_at)} - {run.geography} - {run.status} - {run.id.slice(0, 8)}</option>)}</select></label>{runId && <VersionPicker key={`${side}:${runId}`} runId={runId} side={side} value={side === "Earlier" ? beforeVersion : afterVersion} setValue={side === "Earlier" ? setBeforeVersion : setAfterVersion}/>}</div>)}</div><button className="button primary" disabled={!beforeRun || !afterRun || !beforeVersion || !afterVersion || busy} onClick={() => void compare()}>{busy ? "Comparing saved evidence..." : "Compare saved reports"}</button>{compareError && <p role="alert">{compareError}</p>}<p className="fine-print">Only approved saved versions contribute comparison counts. Earlier drafts remain available through the immutable version links.</p></section>
      {!active && !busy && <p className="limits">Select two report versions and compare. Counts stay unavailable until the evidence comparison succeeds.</p>}
      {active && <><div role="status" className="history-diff-status"><strong>Saved comparison - {active.before.version} to {active.after.version}</strong><p>{active.count_definition}</p><p>{active.counts.unknown} unknown - {active.counts.stale} stale - {active.counts.unchanged} unchanged on re-check</p><details><summary>Selected immutable hashes</summary><p>Earlier <code>{active.before.content_hash}</code><br/>Later <code>{active.after.content_hash}</code></p></details></div>
      <nav className="history-filters" aria-label="Filter historical differences">{(["all", "new", "changed", "gone", "unknown", "stale", "unchanged"] as const).map(kind => <button key={kind} className="button outline" aria-pressed={filter === kind} onClick={() => setFilter(kind)}>{kind === "all" ? "Changes and gaps" : `${changeLabels[kind]} (${active.counts[kind]})`}</button>)}</nav>
      {active.changes.filter(row => filter === "all" ? row.status !== "unchanged" : row.status === filter).map(row => <article className={`change-card historical-${row.status}`} key={row.change_id} data-testid={`history-diff-${row.status}`}><div className="change-heading"><Badge tone={row.color_index === null ? "stone" : tones[row.color_index]}>{row.color_index === null ? "?" : String.fromCharCode(65 + row.color_index)}</Badge><span className={`change-kind ${row.status}`}>{changeLabels[row.status]}</span><h3>{row.brand} - {row.product ? `${row.product} - ` : ""}{row.field.replaceAll("_", " ")}</h3></div><div className="before-after">{[["Earlier - historical", row.before], ["Later - captured evidence", row.after]].map(([label, item]) => { const value = item as typeof row.before; const side = String(label); return <div key={side}><b>{side}</b>{value.values.length ? value.values.map((value, index) => <p key={index}>{historicalValue(value)}</p>) : <p>Unavailable in this report</p>}<small>{value.kinds.join(" / ")}{!value.usable && ` - ${value.reason || "not re-checked"}`}</small>{evidenceGroups(value.evidence).map((refs, index) => { const ref = refs[0]; return <button className="citation history-evidence" key={`${ref.source.id}:${index}`} onClick={() => open(refs, side)}>Evidence - {displayDate(ref.source.retrieved_at)} - {ref.source.access_status}</button>; })}</div>; })}</div><p>{row.reason.replaceAll("_", " ")}</p><small>{row.caveat}</small><details><summary>Stable matching identifiers</summary><code>Brand: {row.brand_id || "unknown"}<br/>Product: {row.product_id || "brand-level / unknown"}</code></details></article>)}
      {active.changes.every(row => row.status === "unchanged") && filter === "all" && <p className="panel all-flags">No changed observations in the supported re-checks. Unchanged fields are available using the filter.</p>}
      <section className="limits"><h2>Comparison limits</h2><ul>{active.limitations.map(limit => <li key={limit}>{limit}</li>)}</ul></section><div className="end-actions"><Link className="button outline" href={reportVersionLink(active.before.run_id, active.before.version)}>Open earlier report v{active.before.version}</Link><Link className="button primary" href={reportVersionLink(active.after.run_id, active.after.version)}>Open later report v{active.after.version}</Link></div></>}
      <p className="muted fine-print">Showing {data.entries.length} of {data.total} saved runs. Dates describe captured evidence, never a guarantee of current availability.</p>
    </section></main></DataBoundary><StateFooter/><SourceDialog evidence={evidence} close={() => setEvidence(null)}/></div>;
}
