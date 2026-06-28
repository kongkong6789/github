import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { loadTaskDetail, loadTaskList, updateTaskAction } from "./tasks";

async function createFixture() {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-tasks-"));
  const taskDir = path.join(root, "tasks");
  const auditPath = path.join(root, "audit", "events.jsonl");
  await mkdir(taskDir, { recursive: true });
  await mkdir(path.dirname(auditPath), { recursive: true });

  const task = {
    task_id: "20260515-120000-UNOVE-analysis",
    goal: "分析 UNOVE 5/6 月销售提升决策并输出老板报告",
    requested_by: "frontend_background",
    status: "warning",
    created_at: "2026-05-15 12:00:00",
    updated_at: "2026-05-15 12:12:00",
    steps: [
      {
        task: "raw_discovery",
        status: "success",
        summary: "found raw files",
        completed_at: "2026-05-15 12:01:00",
        evidence: ["wiki/datasets/unove/overview.md"],
        risks: [],
        missing_data: [],
        next_actions: [],
      },
      {
        task: "lightrag_index",
        status: "failed",
        summary: "embedding timeout",
        completed_at: "2026-05-15 12:05:00",
        evidence: ["data/lightrag/sync-state.json"],
        risks: ["LightRAG pending"],
        missing_data: ["embedding quota"],
        next_actions: ["retry LightRAG"],
      },
    ],
    final_report: { saved_to: "data/reports/unove-final.md" },
  };

  await writeFile(
    path.join(taskDir, `${task.task_id}.json`),
    JSON.stringify(task, null, 2),
  );
  await writeFile(path.join(taskDir, "broken.json"), "{not valid json");
  await writeFile(
    auditPath,
    [
      JSON.stringify({
        timestamp: "2026-05-15 12:03:00",
        event_type: "tool_call",
        task_id: task.task_id,
        agent_id: "decision_agent",
        tool_name: "query_fact_layer",
        summary: "queried sales mart",
        risk_level: "low",
      }),
      JSON.stringify({
        timestamp: "2026-05-15 12:04:00",
        event_type: "tool_call",
        task_id: "other-task",
        tool_name: "ignore_me",
      }),
    ].join("\n"),
  );

  return { root, taskDir, auditPath, task };
}

test("task list tolerates invalid JSON and supports PM filters", async () => {
  const { taskDir, auditPath, task } = await createFixture();

  const result = await loadTaskList({
    taskDir,
    auditPath,
    status: "warning",
    type: "LightRAG 同步",
    query: "UNOVE",
    timeRange: "30d",
    now: new Date("2026-05-20T00:00:00Z"),
  });

  assert.equal(result.tasks.length, 1);
  assert.equal(result.invalid_tasks.length, 1);
  assert.equal(result.tasks[0].task_id, task.task_id);
  assert.equal(result.tasks[0].steps_count, 2);
  assert.equal(result.tasks[0].artifact_count, 3);
  assert.equal(result.tasks[0].risk_count, 1);
  assert.equal(result.tasks[0].has_report, true);
  assert.equal(result.tasks[0].task_type, "LightRAG 同步");
});

test("task detail exposes stages, artifacts, evidence, errors, and merged timeline", async () => {
  const { taskDir, auditPath, task } = await createFixture();

  const detail = await loadTaskDetail(task.task_id, { taskDir, auditPath });

  assert.equal(detail.task_id, task.task_id);
  assert.equal(detail.summary.status, "warning");
  assert(
    detail.stages.some(
      (stage) => stage.key === "lightrag_index" && stage.status === "failed",
    ),
  );
  assert(
    detail.artifacts.some(
      (artifact) => artifact.path === "data/reports/unove-final.md",
    ),
  );
  assert(
    detail.evidence.some(
      (item) => item.path === "wiki/datasets/unove/overview.md",
    ),
  );
  assert.equal(detail.errors[0].step, "lightrag_index");
  assert.deepEqual(
    detail.timeline.map((event) => event.source),
    ["task", "audit", "task"],
  );
});

test("task detail extracts P17 handoff and QA gate evidence", async () => {
  const { taskDir, auditPath, task } = await createFixture();
  (task.steps as Array<Record<string, unknown>>).push(
    {
      task: "handoff.created",
      status: "success",
      summary: "数据归并完成，交给库存 Agent。",
      completed_at: "2026-05-15 12:06:00",
      evidence: ["wiki/datasets/handoff.md"],
      risks: [],
      missing_data: [],
      next_actions: ["检查断货风险"],
      data: {
        event_type: "handoff.created",
        from_agent: "data_agent",
        to_agent: "inventory_agent",
        evidence_paths: ["wiki/datasets/handoff.md"],
      },
    },
    {
      task: "qa.fail",
      status: "failed",
      summary: "缺少 ERP 查询时间和过滤条件。",
      completed_at: "2026-05-15 12:07:00",
      evidence: ["data/reports/unove-final.md"],
      risks: ["证据不完整"],
      missing_data: ["ERP 查询时间"],
      next_actions: ["补 query_erp_live_snapshot 证据"],
      data: {
        event_type: "qa.fail",
        verdict: "FAIL",
        checked_by: "qa_agent",
        retry_count: 2,
        evidence_paths: ["data/reports/unove-final.md"],
      },
    },
  );
  await writeFile(
    path.join(taskDir, `${task.task_id}.json`),
    JSON.stringify(task, null, 2),
  );

  const detail = await loadTaskDetail(task.task_id, { taskDir, auditPath });

  assert.equal(detail.handoffs.length, 1);
  assert.equal(detail.handoffs[0].from_agent, "data_agent");
  assert.equal(detail.handoffs[0].to_agent, "inventory_agent");
  assert.deepEqual(detail.handoffs[0].next_actions, ["检查断货风险"]);
  assert.equal(detail.qa_gates.length, 1);
  assert.equal(detail.qa_gates[0].verdict, "FAIL");
  assert.equal(detail.qa_gates[0].retry_count, 2);
  assert.deepEqual(detail.qa_gates[0].evidence_paths, [
    "data/reports/unove-final.md",
  ]);
});

test("task actions mark cancellation and recovery requests without starting workers", async () => {
  const { taskDir, auditPath, task } = await createFixture();

  const cancelResult = await updateTaskAction(task.task_id, "cancel", {
    taskDir,
    auditPath,
  });
  assert.equal(cancelResult.status, "warning");
  assert.equal(cancelResult.cancel_requested, true);

  const recoverResult = await updateTaskAction(task.task_id, "recover", {
    taskDir,
    auditPath,
  });
  assert.equal(recoverResult.status, "queued");
  assert.equal(recoverResult.recoverable, true);

  const detail = await loadTaskDetail(task.task_id, { taskDir, auditPath });
  assert(detail.timeline.some((event) => event.name === "recovery_requested"));
});
