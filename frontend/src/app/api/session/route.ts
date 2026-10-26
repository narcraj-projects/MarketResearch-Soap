import { NextRequest, NextResponse } from "next/server";
import { authConfig, backendUrl, failure, sameOrigin, SESSION_COOKIE } from "@/lib/server-api";
import { boundedJson, InputLimit, InvalidJson, loginLimiter } from "@/lib/ingress";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return NextResponse.json({ authenticated: false }, { headers: { "Cache-Control": "no-store" } });
  try {
    const response = await fetch(backendUrl() + "/api/auth/me", { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(8000) });
    return NextResponse.json({ authenticated: response.ok }, { headers: { "Cache-Control": "no-store" } });
  } catch { return failure("Sign-in service is unavailable.", 503); }
}

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return failure("Request origin not allowed.", 403);
  if (!loginLimiter.allow()) return failure("Sign-in request limit reached; retry in a minute.", 429);
  const config = authConfig();
  if (!config) return failure("Sign-in is not configured yet.", 503);
  try {
    const value = await boundedJson(request);
    if (!value || typeof value !== 'object' || Array.isArray(value)) return failure("Enter your email and password.", 400);
    const body = value as Record<string, unknown>;
    if (typeof body.email !== "string" || body.email.length > 254 || typeof body.password !== "string" || !body.password || body.password.length > 1024) return failure("Enter your email and password.", 400);
    const response = await fetch(config.url + "/auth/v1/token?grant_type=password", { method: "POST", headers: { apikey: config.key, "Content-Type": "application/json" }, body: JSON.stringify({ email: body.email, password: body.password }), cache: "no-store", redirect: "error", signal: AbortSignal.timeout(8000) });
    if (!response.ok) return failure(response.status >= 500 ? "Sign-in service is unavailable." : "Email or password was not accepted.", response.status >= 500 ? 503 : 401);
    const session = await response.json();
    if (typeof session.access_token !== "string" || session.access_token.length > 8192 || typeof session.expires_in !== "number" || !Number.isFinite(session.expires_in) || session.expires_in <= 0) return failure("Sign-in could not be confirmed.", 503);
    const result = NextResponse.json({ authenticated: true }, { headers: { "Cache-Control": "no-store" } });
    result.cookies.set(SESSION_COOKIE, session.access_token, { httpOnly: true, secure: request.nextUrl.protocol === "https:", sameSite: "lax", path: "/", maxAge: Math.min(session.expires_in, 86400) });
    return result;
  } catch (error) { if (error instanceof InputLimit) return failure("Request exceeds input limits.", 413);
    if (error instanceof InvalidJson) return failure("Request JSON is invalid.", 400);
    return failure("Sign-in service is unavailable.", 503); }
}

export async function DELETE(request: NextRequest) {
  if (!sameOrigin(request)) return failure("Request origin not allowed.", 403);
  const result = NextResponse.json({ authenticated: false });
  result.cookies.delete(SESSION_COOKIE);
  return result;
}
