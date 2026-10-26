// Imported exclusively by server route handlers. No token/key is sent to client JS.
import { NextRequest, NextResponse } from "next/server";
export const SESSION_COOKIE = "lather_session";

export function sameOrigin(request: NextRequest): boolean {
  // NextRequest normalizes loopback IPs in its URL. The browser's Host header
  // retains the actual authority; arbitrary forwarded headers are not trusted.
  const host = request.headers.get("host");
  return !!host && request.headers.get("origin") === `${request.nextUrl.protocol}//${host}`;
}
export function backendUrl(): string {
  const value = new URL(process.env.LATHER_API_BASE_URL || "http://127.0.0.1:8000");
  if (!["http:", "https:"].includes(value.protocol) || value.username || value.password) throw new Error("invalid_api_origin");
  if (value.search || value.hash || value.pathname !== '/' || (value.protocol !== 'https:' && !['127.0.0.1', 'localhost', '[::1]'].includes(value.hostname))) throw new Error("invalid_api_origin");
  return value.origin;
}
export function authConfig(): { url: string; key: string } | null {
  const key = process.env.LATHER_SUPABASE_PUBLISHABLE_KEY;
  const rawUrl = process.env.LATHER_SUPABASE_URL;
  if (!key || !rawUrl) return null;
  try {
    const url = new URL(rawUrl);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') return null;
    if (url.protocol !== 'https:' && !(process.env.LATHER_ENVIRONMENT !== 'production' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname))) return null;
    const legacy = key.split(".");
    const publicKey = key.startsWith("sb_publishable_") || (legacy.length === 3 && JSON.parse(Buffer.from(legacy[1], "base64url").toString()).role === "anon");
    return publicKey ? { url: url.origin, key } : null;
  } catch { return null; }
}
export function failure(message: string, status: number) {
  return NextResponse.json({ message }, { status, headers: { "Cache-Control": "no-store" } });
}
