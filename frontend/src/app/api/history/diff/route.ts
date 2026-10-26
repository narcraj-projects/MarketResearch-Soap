import { NextRequest } from "next/server";
import { proxy, uuid } from "@/lib/proxy";
import { failure } from "@/lib/server-api";
export async function GET(request: NextRequest) {
  const input = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  for (const key of ["before_run", "after_run", "before_version", "after_version"]) {
    const value = input.get(key);
    if (!value || (key.endsWith("run") ? !uuid.test(value) : !/^[1-9]\d{0,8}$/.test(value))) return failure("Choose two saved report versions.", 400);
    query.set(key, value);
  }
  return proxy(request, `/api/history/diff?${query}`);
}
