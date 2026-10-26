import { describe, expect, it } from "vitest";
import { parseHealth } from "../src/lib/health";

describe("scaffold API health contract", () => {
  it("preserves not-ready status without claiming database health", () => {
    expect(parseHealth({ status: "not_ready", mode: "replay", database: "not_checked", external_calls_enabled: false }).status).toBe("not_ready");
  });
  it.each([null, {}, { status: "ready", mode: "live" }, { status: "ready", mode: "replay", database: "not_checked", external_calls_enabled: true }])("rejects malformed or live-enabled payloads", (value) => {
    expect(() => parseHealth(value)).toThrow("invalid_health_response");
  });
});
