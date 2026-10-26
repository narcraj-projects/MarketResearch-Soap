import { NextRequest } from "next/server";
import { proxy } from "@/lib/proxy";
export async function POST(request: NextRequest) { return proxy(request, "/api/chaos/runs", true); }
