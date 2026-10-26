export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export async function read<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { cache: "no-store", signal });
  if (!response.ok) throw new ApiError(response.status, response.status === 401 ? "Sign in to view your saved research." : response.status === 404 ? "This run is not available in your account." : "Saved research could not be loaded. Please retry.");
  return response.json();
}
export async function command<T>(url: string, body: unknown, key: string): Promise<T> {
  const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key }, body: JSON.stringify(body), cache: "no-store" });
  if (!response.ok) throw new ApiError(response.status, response.status === 401 ? "Sign in again before continuing." : response.status === 409 ? "The saved state changed or this action is not allowed. Refresh before retrying." : "The action could not be confirmed. Retry the same request.");
  return response.json();
}
export const runLink = (screen: string, id?: string | null) => id ? `${screen}?run=${encodeURIComponent(id)}` : screen;
export const tones = ["lavender", "turmeric", "rose", "mint", "stone"];
export const displayDate = (value?: string | null) => value ? new Date(value).toLocaleString("en-GB", { timeZone: "UTC", dateStyle: "medium", timeStyle: "short" }) + " UTC" : "Not recorded";
export const displayValue = (value: unknown): string => value === null || value === undefined ? "Unavailable" : typeof value === "string" ? value : JSON.stringify(value);
export const percent = (value: number | null) => value === null ? "—" : `${Math.round(value * 100)}%`;
export function barPercent(value: string | null, maximum: number): number | null {
  if (value === null || !Number.isFinite(Number(value)) || Number(value) < 0) return null;
  return maximum > 0 ? Math.min(100, Number(value) / maximum * 100) : 0;
}
export function eventSummary(kind: string, data: Record<string, unknown>): string {
  if (kind === "tool.retryable_failure") return `${data.tool}: ${data.code}; attempt ${data.attempt} recorded (limit ${data.retry_limit}).`;
  if (kind === "tool.recovered") return `${data.tool}: recovered on recorded attempt ${data.attempt}.`;
  if (kind === "model.output_invalid") return `Recorded model fixture failed JSON/schema validation on attempt ${data.attempt}.`;
  if (kind === "model.replay_validated") return data.repaired ? "Recorded model fixture repaired and validated; no provider call." : "Recorded model fixture validated; no provider call.";
  if (kind === "analysis.reviewed") return data.decision === "revise" ? "Independent Reviewer requested targeted correction." : data.decision === "unresolved" ? "Independent Reviewer flagged unresolved evidence." : "Independent mechanical review recorded; human approval still required.";
  if (kind === "chaos.armed") return `Separate DEMO scenario configured: ${data.scenario}.`;
  if (kind === "chaos.worker_interrupted") return "One research lane committed at the test interruption point.";
  if (kind === "chaos.worker_recovered") return `${data.preserved_lanes} saved lane reused; remaining research completed.`;
  if (kind === "worker.claimed" && data.recovered === true) return "Worker reclaimed an expired lease; resuming durable state.";
  if (kind === "workflow.node" && typeof data.node === "string") return `Completed ${data.node.replaceAll("_", " ")}.`;
  if (kind === "approval.pending") return `Waiting for ${data.gate === "shortlist" ? "shortlist" : "final report"} review.`;
  if (kind === "approval.decided") return `${data.gate === "shortlist" ? "Shortlist" : "Report"} decision recorded.`;
  if (kind === "run.completed") return "Approved report saved.";
  if (kind === "research.completed" && typeof data.lanes === "number") return `${data.lanes} independent research lanes persisted.`;
  if (kind === "research.competitor.completed") return "Competitor evidence persisted.";
  if (kind.startsWith("tool.") && typeof data.tool === "string") return `${data.tool.replaceAll(".", " ")}: ${typeof data.code === "string" ? data.code.replaceAll("_", " ") : kind.split(".").at(-1)}.`;
  return kind.replaceAll(".", " ").replaceAll("_", " ") + " recorded.";
}
