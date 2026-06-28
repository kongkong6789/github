import { NextRequest, NextResponse } from "next/server";
import path from "node:path";

import { checkWorkbenchAuth } from "@/lib/api-auth";
import { workbenchAuthResponse } from "@/lib/api-route-auth";
import {
  createPlatformLabRun,
  listPlatformLabRuns,
  type PlatformLabRunInput,
} from "@/lib/platform-lab-server";

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
const REPORTS_DIR = process.env.A2A_REPORTS_DIR
  ? path.resolve(process.env.A2A_REPORTS_DIR)
  : path.join(DATA_DIR, "reports");
const RUN_LOG = process.env.A2A_PLATFORM_LAB_RUN_LOG
  ? path.resolve(process.env.A2A_PLATFORM_LAB_RUN_LOG)
  : path.join(DATA_DIR, "platform_lab", "runs.jsonl");

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function paths() {
  return {
    taskDir: TASKS_DIR,
    auditPath: AUDIT_LOG,
    runLogPath: RUN_LOG,
    reportsDir: REPORTS_DIR,
  };
}

function errorResponse(error: unknown, status = 400) {
  return NextResponse.json(
    {
      status: "error",
      code: "platform_lab_run_failed",
      message: error instanceof Error ? error.message : String(error),
      hint: "检查场景 ID、demo ID、数据目录权限和审计日志路径。",
    },
    { status },
  );
}

export async function GET(request: NextRequest) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  const limit = Number(request.nextUrl.searchParams.get("limit") || 50);
  return NextResponse.json(
    await listPlatformLabRuns({
      runLogPath: RUN_LOG,
      limit: Number.isFinite(limit) ? limit : 50,
    }),
  );
}

export async function POST(request: NextRequest) {
  const auth = checkWorkbenchAuth(request);
  if (!auth.ok) {
    return NextResponse.json(
      {
        status: "error",
        code: "unauthorized",
        message: auth.error,
        hint: "配置 A2A_WORKBENCH_API_KEY 后，请在请求头中提供有效密钥。",
      },
      { status: auth.status },
    );
  }

  const body = safeRecord(await request.json().catch(() => ({})));
  const input: PlatformLabRunInput = {
    kind: safeText(body.kind) === "demo" ? "demo" : "scenario",
    templateId: safeText(body.templateId) || safeText(body.template_id),
    assumptions: safeText(body.assumptions),
    requestedBy: safeText(body.requestedBy) || safeText(body.requested_by),
  };

  try {
    return NextResponse.json(await createPlatformLabRun(input, paths()));
  } catch (error) {
    return errorResponse(error);
  }
}
