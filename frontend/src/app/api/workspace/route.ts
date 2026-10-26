import { NextRequest } from "next/server";
import { proxy, uuid } from "@/lib/proxy";
import { failure } from "@/lib/server-api";
export async function GET(request: NextRequest) {
  const id = request.nextUrl.searchParams.get("run_id");
  if (id && !uuid.test(id)) return failure("Run not found.", 404);
  const version = request.nextUrl.searchParams.get("report_version");
  if (version !== null && (!id || !/^[1-9]\d{0,8}$/.test(version))) return failure("Invalid report version.", 400);
  const query = new URLSearchParams(); if (id) query.set("run_id", id); if (version) query.set("report_version", version);
  return proxy(request, `/api/workspace${query.size ? `?${query}` : ""}`);
}
