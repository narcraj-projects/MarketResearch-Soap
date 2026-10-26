import { NextRequest } from "next/server";
import { proxy } from "@/lib/proxy";
import { failure } from "@/lib/server-api";
export async function GET(request: NextRequest) {
  const offset = request.nextUrl.searchParams.get("offset") || "0";
  if (!/^\d{1,8}$/.test(offset)) return failure("Invalid history cursor.", 400);
  return proxy(request, `/api/history/view?limit=20&offset=${offset}`);
}
