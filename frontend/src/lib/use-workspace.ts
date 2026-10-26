"use client";
import { useCallback, useEffect, useState } from "react";
import { ApiError, read } from "./run-api";
import type { Workspace } from "./run-types";
export type LoadState = "loading" | "ready" | "empty" | "auth" | "error";
export function useWorkspace(runId?: string, reportVersion?: string) {
  const [data, setData] = useState<Workspace | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const reload = useCallback(async (signal?: AbortSignal) => {
    try {
      const query = new URLSearchParams(); if (runId) query.set("run_id", runId); if (reportVersion) query.set("report_version", reportVersion);
      const result = await read<Workspace>(`/api/workspace${query.size ? `?${query}` : ""}`, signal);
      if (result.schema_version !== "run-view-1.0") throw new Error("Unsupported view");
      setData(result); setState(result.run ? "ready" : "empty"); setError("");
    } catch (cause) {
      if (signal?.aborted) return;
      setData(null); setState(cause instanceof ApiError && cause.status === 401 ? "auth" : "error");
      setError(cause instanceof Error ? cause.message : "Saved research is unavailable.");
    }
  }, [runId, reportVersion]);
  useEffect(() => { const controller = new AbortController(); queueMicrotask(() => void reload(controller.signal)); const focus = () => { void reload(controller.signal); }; window.addEventListener("focus", focus); return () => { controller.abort(); window.removeEventListener("focus", focus); }; }, [reload]);
  useEffect(() => {
    if (!data?.run || ["complete", "partial", "failed", "cancelled"].includes(data.run.status)) return;
    const controller = new AbortController(); let busy = false;
    const timer = setInterval(async () => {
      if (busy) return; busy = true;
      try { const events = await read<unknown[]>(`/api/runs/${data.run!.id}/events?after=${data.event_count}&limit=100`, controller.signal); if (events.length) await reload(controller.signal); }
      catch (cause) { if (cause instanceof ApiError && [401, 404].includes(cause.status)) await reload(controller.signal); }
      finally { busy = false; }
    }, 2000);
    return () => { clearInterval(timer); controller.abort(); };
  }, [data?.run, data?.event_count, reload]);
  return { data, state, error, reload };
}
