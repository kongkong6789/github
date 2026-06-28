import { NextRequest, NextResponse } from "next/server";
import path from "node:path";

import { checkWorkbenchAuth } from "@/lib/api-auth";
import { workbenchAuthResponse } from "@/lib/api-route-auth";
import { loadTaskDetail, updateTaskAction, type TaskAction } from "@/lib/tasks";

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
const THREAD_ARCHIVE_DIR = process.env.A2A_THREAD_ARCHIVE_DIR
  ? path.resolve(process.env.A2A_THREAD_ARCHIVE_DIR)
  : path.join(DATA_DIR, "thread_archive");

type RouteContext = {
  params: Promise<{ taskId: string }>;
};

async function taskIdFromContext(context: RouteContext) {
  const params = await context.params;
  return params.taskId;
}

function errorResponse(error: unknown, status = 404) {
  return NextResponse.json(
    {
      status: "error",
      code: status === 404 ? "task_not_found" : "task_action_failed",
      message: error instanceof Error ? error.message : String(error),
      hint: status === 404 ? "刷新任务列表后再试。" : "查看任务详情和日志后再重试。",
    },
    { status },
  );
}

export async function GET(request: NextRequest, context: RouteContext) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  try {
    const taskId = await taskIdFromContext(context);
    return NextResponse.json(
      await loadTaskDetail(taskId, {
        taskDir: TASKS_DIR,
        auditPath: AUDIT_LOG,
        threadArchiveDir: THREAD_ARCHIVE_DIR,
      }),
    );
  } catch (error) {
    return errorResponse(error, 404);
  }
}

export async function PATCH(request: NextRequest, context: RouteContext) {
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

  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const action = typeof body.action === "string" ? body.action : "";
  if (action !== "cancel" && action !== "recover") {
    return NextResponse.json(
      {
        status: "error",
        code: "unsupported_task_action",
        message: `不支持的任务操作：${action || "空"}`,
        hint: "当前只支持 cancel 或 recover。",
      },
      { status: 400 },
    );
  }

  try {
    const taskId = await taskIdFromContext(context);
    return NextResponse.json(
      await updateTaskAction(taskId, action as TaskAction, {
        taskDir: TASKS_DIR,
        auditPath: AUDIT_LOG,
        threadArchiveDir: THREAD_ARCHIVE_DIR,
      }),
    );
  } catch (error) {
    return errorResponse(error, 400);
  }
}
