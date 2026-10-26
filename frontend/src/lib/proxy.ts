// Explicit BFF allowlists, HTTP-only credentials, sanitized errors and no caching.
import { NextRequest, NextResponse } from "next/server";
import { backendUrl, failure, sameOrigin, SESSION_COOKIE } from "./server-api";
import { boundedJson, InputLimit, InvalidJson } from "./ingress";
export const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export async function proxy(request: NextRequest, path: string, write = false, download = false) {
  if (write && !sameOrigin(request)) return failure("Request origin not allowed.", 403);
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return failure("Sign in to view your saved research.", 401);
  const key = request.headers.get("Idempotency-Key");
  if (write && (!key || key.length < 8 || key.length > 128)) return failure("A valid request key is required.", 400);
  try {
    const response = await fetch(backendUrl() + path, { method: write ? "POST" : "GET", headers: { Authorization: `Bearer ${token}`, ...(write ? { "Content-Type": "application/json", "Idempotency-Key": key! } : {}) },
      body: write ? JSON.stringify(await boundedJson(request)) : undefined, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000) });
    if (!response.ok) return failure(response.status === 409 ? "The saved state changed or this action is not allowed." : "Saved research is unavailable.", response.status);
    if (download) return new NextResponse(await response.arrayBuffer(), { headers: { "Content-Type": response.headers.get("content-type") || "application/octet-stream",
      "Content-Disposition": response.headers.get("content-disposition") || "attachment", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'" } });
    return NextResponse.json(await response.json(), { status: response.status, headers: { "Cache-Control": "no-store", Vary: "Cookie" } });
  } catch (error) { if (error instanceof InputLimit) return failure("Request exceeds input limits.", 413);
    if (error instanceof InvalidJson) return failure("Request JSON is invalid.", 400);
    return failure("Saved research is unavailable; no private upstream details displayed.", 503); }
}
