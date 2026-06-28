import { NextResponse } from "next/server";
import path from "node:path";

import { workbenchAuthResponse } from "@/lib/api-route-auth";
import { loadLogsState, type LogFilters } from "@/lib/logs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

const DATA_DIR = process.env.A2A_DATA_DIR
  ? path.resolve(process.env.A2A_DATA_DIR)
  : path.resolve(process.cwd(), "..", "data");
const WORKSPACE_DIR = path.resolve(DATA_DIR, "..");

function filterFromSearchParams(searchParams: URLSearchParams): LogFilters {
  const filters: LogFilters = {};
  for (const key of [
    "source",
    "level",
    "thread_id",
    "task_id",
    "agent_id",
    "tool_name",
    "risk_level",
  ] as const) {
    const value = searchParams.get(key)?.trim();
    if (value) filters[key] = value;
  }
  return filters;
}

export async function GET(request: Request) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  const url = new URL(request.url);
  return NextResponse.json(
    await loadLogsState({
      workspaceDir: WORKSPACE_DIR,
      dataDir: DATA_DIR,
      limit: Number(url.searchParams.get("limit") || 200),
      filters: filterFromSearchParams(url.searchParams),
    }),
  );
}
