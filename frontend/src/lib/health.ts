export type Health = {
  status: "alive" | "ready" | "not_ready";
  mode: "replay";
  database: "not_checked";
  external_calls_enabled: false;
};

export function parseHealth(value: unknown): Health {
  if (typeof value !== "object" || value === null) throw new Error("invalid_health_response");
  const data = value as Record<string, unknown>;
  if (typeof data.status !== "string" || !["alive", "ready", "not_ready"].includes(data.status) ||
      data.mode !== "replay" || data.database !== "not_checked" || data.external_calls_enabled !== false) {
    throw new Error("invalid_health_response");
  }
  return data as Health;
}
