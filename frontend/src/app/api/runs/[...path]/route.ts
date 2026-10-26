import { NextRequest } from "next/server";
import { proxy, uuid } from "@/lib/proxy";
import { failure } from "@/lib/server-api";
type Context = { params: Promise<{ path: string[] }> };
export async function GET(request: NextRequest, context: Context) {
  const [id, action, ...rest] = (await context.params).path;
  if (!uuid.test(id) || rest.length || ![undefined, "events", "export", "versions"].includes(action)) return failure("Resource not found.", 404);
  const query = request.nextUrl.searchParams;
  if (action === "versions") {
    const offset = query.get("offset") || "0";
    if (!/^\d{1,8}$/.test(offset)) return failure("Invalid version cursor.", 400);
    return proxy(request, `/api/runs/${id}/versions?limit=100&offset=${offset}`);
  }
  if (action === "events") {
    const after = query.get("after") || "0";
    if (!/^\d{1,10}$/.test(after)) return failure("Invalid event cursor.", 400);
    return proxy(request, `/api/runs/${id}/events?after=${after}&limit=100`);
  }
  if (action === "export") {
    const format = query.get("format"); const report = query.get("report_id");
    if (!["html", "csv"].includes(format || "") || !report || !uuid.test(report)) return failure("Invalid export request.", 400);
    return proxy(request, `/api/runs/${id}/export?format=${format}&report_id=${report}`, false, true);
  }
  return proxy(request, `/api/runs/${id}`);
}
export async function POST(request: NextRequest, context: Context) {
  const [id, action, ...rest] = (await context.params).path;
  if (!uuid.test(id) || rest.length || !["shortlist-decision", "report-decision", "cancel", "resume"].includes(action)) return failure("Action not found.", 404);
  return proxy(request, `/api/runs/${id}/${action}`, true);
}
