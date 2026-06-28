import { NextRequest, NextResponse } from "next/server";

import { checkWorkbenchAuth } from "@/lib/api-auth";
import {
  createWorkbenchError,
  createWorkbenchSuccess,
  isWorkbenchMethod,
  type WorkbenchMethod,
} from "@/lib/workbench-contract";
import { dispatchWorkbench, workbenchErrorMeta } from "@/lib/workbench-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeText(value: unknown) {
  return typeof value === "string" ? value : "";
}

function unsupportedMethod(method: string) {
  return createWorkbenchError("task.list", {
    code: "unsupported_workbench_method",
    message: "不支持的 Workbench 方法。",
    hint: `首批方法固定为 task.list、task.show、agent.trace、data.health、governance.policy、approval.submit、logs.tail、evidence.graph、source.list、source.show、source.sync；收到 ${method || "(empty)"}。`,
    retryable: false,
    source: "workbench",
    details: { method },
  });
}

export async function POST(request: NextRequest) {
  const auth = checkWorkbenchAuth(request);
  if (!auth.ok) {
    return NextResponse.json(
      createWorkbenchError("task.list", {
        code: "unauthorized",
        message: auth.error,
        hint: "",
        retryable: false,
        source: "workbench",
        details: {},
      }),
      { status: auth.status },
    );
  }

  const body = safeRecord(await request.json().catch(() => ({})));
  const method = safeText(body.method);
  const params = safeRecord(body.params);

  if (!isWorkbenchMethod(method)) {
    return NextResponse.json(unsupportedMethod(method), { status: 400 });
  }

  try {
    const result = await dispatchWorkbench(method as WorkbenchMethod, params);
    return NextResponse.json(
      createWorkbenchSuccess(method, result.data, {
        warnings: result.warnings,
      }),
    );
  } catch (error) {
    const meta = workbenchErrorMeta(method, error);
    return NextResponse.json(createWorkbenchError(method, meta), {
      status: meta.retryable ? 500 : 400,
    });
  }
}
