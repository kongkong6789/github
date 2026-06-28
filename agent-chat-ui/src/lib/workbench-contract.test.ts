import assert from "node:assert/strict";
import { test } from "node:test";

import {
  createWorkbenchError,
  createWorkbenchSuccess,
  isWorkbenchMethod,
  WORKBENCH_METHODS,
} from "./workbench-contract";

test("workbench exposes the current control-plane method set", () => {
  assert.deepEqual(WORKBENCH_METHODS, [
    "task.list",
    "task.show",
    "agent.trace",
    "data.health",
    "governance.policy",
    "approval.submit",
    "logs.tail",
    "evidence.graph",
    "source.list",
    "source.show",
    "source.sync",
  ]);
  for (const method of WORKBENCH_METHODS) {
    assert.equal(isWorkbenchMethod(method), true);
  }
  assert.equal(isWorkbenchMethod("lightrag.status"), false);
});

test("workbench success envelope keeps method, request id, data, and warnings stable", () => {
  const envelope = createWorkbenchSuccess(
    "task.list",
    { tasks: [] },
    {
      requestId: "req_1",
      generatedAt: "2026-05-19T00:00:00.000Z",
      warnings: ["partial"],
    },
  );

  assert.deepEqual(envelope, {
    ok: true,
    method: "task.list",
    request_id: "req_1",
    generated_at: "2026-05-19T00:00:00.000Z",
    data: { tasks: [] },
    error: null,
    warnings: ["partial"],
  });
});

test("workbench error envelope redacts raw errors into a friendly shape", () => {
  const envelope = createWorkbenchError("task.show", {
    requestId: "req_2",
    code: "task_not_found",
    message: "Task not found",
    hint: "刷新任务列表后再试。",
    retryable: false,
    source: "tasks",
  });

  assert.equal(envelope.ok, false);
  assert.equal(envelope.error?.code, "task_not_found");
  assert.equal(envelope.error?.retryable, false);
  assert.equal(envelope.data, null);
});

test("workbench error envelope supports hints, details, and source metadata", () => {
  const envelope = createWorkbenchError("logs.tail", {
    requestId: "req_3",
    generatedAt: "2026-05-20T00:00:00.000Z",
    code: "scope_required",
    message: "需要指定 thread_id、task_id 或 scope=global。",
    hint: "在全局日志页请显式传入 scope=global。",
    retryable: false,
    source: "workbench_scope",
    details: { method: "logs.tail" },
    warnings: ["global history withheld"],
  });

  assert.deepEqual(envelope, {
    ok: false,
    method: "logs.tail",
    request_id: "req_3",
    generated_at: "2026-05-20T00:00:00.000Z",
    data: null,
    error: {
      code: "scope_required",
      message: "需要指定 thread_id、task_id 或 scope=global。",
      hint: "在全局日志页请显式传入 scope=global。",
      retryable: false,
      source: "workbench_scope",
      details: { method: "logs.tail" },
    },
    warnings: ["global history withheld"],
  });
});
