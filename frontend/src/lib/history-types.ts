import type { Json, Source } from "./run-types";
export type HistoricalVersion = { report_id: string; run_id: string; version: number; content_hash: string; created_at: string; as_of: string | null; approval: string; comparable: boolean; label: "DEMO" | null };
export type VersionList = { entries: HistoricalVersion[]; total: number };
export type DatedEvidence = { source: Source; quote: string | null; quote_hash: string | null; locator: string | null };
export type HistoricalValue = { values: Json[]; evidence: DatedEvidence[]; kinds: string[]; reason: string | null; usable: boolean };
export type ChangeKind = "new" | "changed" | "gone" | "unchanged" | "unknown" | "stale";
export type HistoricalChange = { change_id: string; brand_id: string | null; product_id: string | null; brand: string; product: string | null; color_index: number | null; field: string; status: ChangeKind; reason: string; before: HistoricalValue; after: HistoricalValue; caveat: string };
export type HistoryDiff = { schema_version: "history-diff-1.0"; identity_version: string; label: "DEMO"; before: HistoricalVersion; after: HistoricalVersion; counts: Record<ChangeKind, number>; changes: HistoricalChange[]; freshness_days: number; count_definition: string; limitations: string[] };
export const reportVersionLink = (run: string, version: number) => `/report?run=${encodeURIComponent(run)}&version=${version}`;
export function historicalValue(value: Json): string {
  if (value && !Array.isArray(value) && typeof value === "object" && "amount" in value && "currency" in value)
    return `${value.amount ?? "Price unavailable"} ${value.currency ?? "currency unknown"} / ${value.total_weight_g ?? "unknown"} g total; ${value.pack_qty ?? "unknown"} in pack; ${value.unit_price_100g ?? "unavailable"} per 100 g`;
  return value === null ? "Unavailable" : typeof value === "string" ? value : JSON.stringify(value);
}
export const changeLabels: Record<ChangeKind, string> = { new: "Newly observed", changed: "Changed", gone: "Gone - source reports discontinued", unchanged: "Unchanged on re-check", unknown: "Unknown", stale: "Stale / not re-checked" };
export function evidenceGroups(refs: DatedEvidence[]): DatedEvidence[][] {
  const groups = new Map<string, DatedEvidence[]>();
  for (const ref of refs) { const group = groups.get(ref.source.id) || []; group.push(ref); groups.set(ref.source.id, group); }
  return [...groups.values()];
}
