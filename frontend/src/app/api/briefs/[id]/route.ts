import { NextRequest, NextResponse } from "next/server";
import { backendUrl, failure, SESSION_COOKIE } from "@/lib/server-api";

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return failure("Sign in to read your saved brief.", 401);
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return failure("Brief not found.", 404);
  try {
    const response = await fetch(backendUrl() + `/api/briefs/${id}`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000) });
    if (!response.ok) return failure("Saved brief is unavailable.", response.status);
    return NextResponse.json(await response.json(), { headers: { "Cache-Control": "no-store" } });
  } catch { return failure("Saved brief is unavailable.", 503); }
}
