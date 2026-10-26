import { NextRequest, NextResponse } from "next/server";
import { backendUrl, failure, sameOrigin, SESSION_COOKIE } from "@/lib/server-api";
import { boundedJson, InputLimit, InvalidJson } from "@/lib/ingress";

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return failure("Request origin not allowed.", 403);
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return failure("Sign in to save your brief.", 401);
  const key = request.headers.get("Idempotency-Key");
  if (!key || key.length < 8 || key.length > 128) return failure("Save request is invalid.", 400);
  try {
    const body = await boundedJson(request);
    const response = await fetch(backendUrl() + "/api/briefs", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, "Idempotency-Key": key }, body: JSON.stringify(body), cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000) });
    if (!response.ok) return failure(response.status === 401 ? "Sign in again to save your brief." : "Your brief could not be saved.", response.status);
    return NextResponse.json(await response.json(), { status: 201, headers: { "Cache-Control": "no-store" } });
  } catch (error) { if (error instanceof InputLimit) return failure("Request exceeds input limits.", 413);
    if (error instanceof InvalidJson) return failure("Request JSON is invalid.", 400);
    return failure("The save could not be confirmed. Please keep your form and try again.", 503); }
}
