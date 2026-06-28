import { NextRequest, NextResponse } from "next/server";
import path from "node:path";

import { workbenchAuthResponse } from "@/lib/api-route-auth";
import { loadTaskList } from "@/lib/tasks";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

const DATA_DIR = process.env.A2A_DATA_DIR
  ? path.resolve(process.env.A2A_DATA_DIR)
  : path.resolve(process.cwd(), "..", "data");
const TASKS_DIR = process.env.A2A_TASK_DIR
  ? path.resolve(process.env.A2A_TASK_DIR)
  : path.join(DATA_DIR, "tasks");
const AUDIT_LOG = process.env.A2A_AUDIT_LOG
  ? path.resolve(process.env.A2A_AUDIT_LOG)
  : path.join(DATA_DIR, "audit", "events.jsonl");

function positiveLimit(value: string | null) {
  const limit = Number(value || 60);
  return Number.isFinite(limit) ? limit : 60;
}

export async function GET(request: NextRequest) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  const params = request.nextUrl.searchParams;
  const result = await loadTaskList({
    taskDir: TASKS_DIR,
    auditPath: AUDIT_LOG,
    status: params.get("status") || "all",
    timeRange: params.get("timeRange") || "all",
    type: params.get("type") || "all",
    query: params.get("query") || "",
    limit: positiveLimit(params.get("limit")),
  });
  return NextResponse.json(result);
}
