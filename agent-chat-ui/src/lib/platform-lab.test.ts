import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { loadEvidenceGraphState } from "./evidence-graph";
import {
  buildScenarioPrompt,
  buildPlatformControlCenter,
  capabilityLanes,
  demoScripts,
  scenarioTemplates,
  workflowStages,
} from "./platform-lab";
import { createPlatformLabRun, listPlatformLabRuns } from "./platform-lab-server";
import { loadTaskDetail } from "./tasks";

async function createPlatformLabFixture() {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-platform-lab-"));
  const dataDir = path.join(root, "data");
  const taskDir = path.join(dataDir, "tasks");
  const auditPath = path.join(dataDir, "audit", "events.jsonl");
  const runLogPath = path.join(dataDir, "platform_lab", "runs.jsonl");
  const reportsDir = path.join(dataDir, "reports");
  const wikiDir = path.join(root, "wiki");
  const warehouseDir = path.join(dataDir, "warehouse");

  await mkdir(taskDir, { recursive: true });
  await mkdir(path.dirname(auditPath), { recursive: true });
  await mkdir(path.dirname(runLogPath), { recursive: true });
  await mkdir(reportsDir, { recursive: true });
  await mkdir(wikiDir, { recursive: true });
  await mkdir(warehouseDir, { recursive: true });
  await writeFile(path.join(wikiDir, "index.md"), "# 经营知识库\n\n人工确认边界。");
  await writeFile(
    path.join(warehouseDir, "dataset_registry.json"),
    JSON.stringify({
      schema: "a2a_dataset_registry_v1",
      datasets: {
        inventory: {
          dataset_slug: "inventory",
          wiki_pages: { overview: "wiki/index.md" },
          sheet_views: [{ headers: ["SKU", "仓库", "采购价"] }],
        },
      },
    }),
  );

  return {
    root,
    dataDir,
    taskDir,
    auditPath,
    runLogPath,
    reportsDir,
    wikiDir,
    registryPath: path.join(warehouseDir, "dataset_registry.json"),
    lightragIndexPath: path.join(dataDir, "lightrag", "index.json"),
  };
}

test("platform lab lands internal capability domains into A2A workbench surfaces", () => {
  assert.deepEqual(
    new Set(capabilityLanes.map((lane) => lane.source)),
    new Set(["governance", "workflow", "simulation", "demo"]),
  );

  assert(
    capabilityLanes.every((lane) => lane.inspiration && lane.currentLanding),
  );

  const surfaces = capabilityLanes.flatMap((lane) => lane.evidence);
  for (const href of [
    "/governance?tab=skills",
    "/governance?tab=mcp",
    "/data-health",
    "/data-sources",
    "/tasks",
    "/evidence-graph",
  ]) {
    assert.equal(
      surfaces.includes(href),
      true,
      `${href} should be part of the landing map`,
    );
  }
});

test("platform lab workflow keeps evidence and approval gates visible", () => {
  assert.deepEqual(
    workflowStages.map((stage) => stage.id),
    ["source", "fact-layer", "knowledge", "agent-work", "simulation"],
  );

  const gateText = workflowStages.flatMap((stage) => stage.gates).join(" ");
  assert.match(gateText, /依据|人工确认|外部写入/);
});

test("scenario prompts enforce evidence-backed scenario simulation", () => {
  const template = scenarioTemplates.find(
    (scenario) => scenario.id === "inventory-shock",
  );
  assert.ok(template);

  const prompt = buildScenarioPrompt(template, "销量提升 30%，交期延迟 5 天");
  assert.match(prompt, /数据表/);
  assert.match(prompt, /知识库|ERP/);
  assert.match(prompt, /保守、平衡、激进/);
  assert.match(prompt, /人工确认/);
  assert.match(prompt, /不得直接执行外部写入/);
  assert.match(prompt, /销量提升 30%/);
});

test("demo scripts provide productized ecommerce stories", () => {
  const labels = demoScripts.map((script) => script.label);
  assert.deepEqual(labels, [
    "老板周报演示",
    "新品上市推演演示",
    "供应商异常演练",
  ]);

  for (const script of demoScripts) {
    assert.match(script.openingPrompt, /经营|上市|供应商|周报|推演/);
    assert.equal(script.successEvidence.length >= 3, true);
  }
});

test("platform lab scenario run creates task, audit, run manifest, and evidence graph references", async () => {
  const paths = await createPlatformLabFixture();

  const run = await createPlatformLabRun(
    {
      kind: "scenario",
      templateId: "inventory-shock",
      assumptions: "销量提升 30%，交期延迟 5 天",
      requestedBy: "pm",
      now: "2026-06-14T08:00:00.000Z",
    },
    paths,
  );

  assert.equal(run.kind, "scenario");
  assert.equal(run.template_id, "inventory-shock");
  assert.match(run.task_id, /platform-lab-inventory-shock/);
  assert.equal(run.status, "queued");
  assert.equal(run.links.task, `/tasks/${encodeURIComponent(run.task_id)}`);
  assert.equal(
    run.links.evidence_graph,
    `/evidence-graph?taskId=${encodeURIComponent(run.task_id)}`,
  );

  const detail = await loadTaskDetail(run.task_id, {
    taskDir: paths.taskDir,
    auditPath: paths.auditPath,
  });
  assert.equal(detail.requested_by, "pm");
  assert.equal(detail.status, "queued");
  assert.equal(detail.has_report, true);
  assert.match(detail.goal, /库存冲击推演/);
  assert(detail.evidence.some((item) => item.path === "wiki/index.md"));
  assert(detail.evidence.some((item) => item.path.includes("dataset_registry")));
  assert(
    detail.qa_gates.some((gate) => gate.verdict === "ESCALATED"),
    "external-write guardrail should be represented as a QA escalation",
  );

  const audit = await readFile(paths.auditPath, "utf8");
  assert.match(audit, /platform_lab_run_created/);
  assert.match(audit, new RegExp(run.task_id));

  const runs = await listPlatformLabRuns({ runLogPath: paths.runLogPath });
  assert.equal(runs.counts.total, 1);
  assert.equal(runs.runs[0].task_id, run.task_id);

  const graph = await loadEvidenceGraphState({
    workspaceDir: paths.root,
    dataDir: paths.dataDir,
    wikiDir: paths.wikiDir,
    taskDir: paths.taskDir,
    reportsDir: paths.reportsDir,
    registryPath: paths.registryPath,
    auditPath: paths.auditPath,
    lightragIndexPath: paths.lightragIndexPath,
    scope: "task",
    taskId: run.task_id,
  });
  assert(
    graph.nodes.some(
      (node) =>
        node.type === "decision" && node.metadata.task_id === run.task_id,
    ),
  );
  assert(graph.edges.some((edge) => edge.type === "needs_confirmation"));
});

test("platform lab demo run can seed a productized demo task", async () => {
  const paths = await createPlatformLabFixture();

  const run = await createPlatformLabRun(
    {
      kind: "demo",
      templateId: "boss-weekly",
      requestedBy: "demo-owner",
      now: "2026-06-14T09:00:00.000Z",
    },
    paths,
  );

  const detail = await loadTaskDetail(run.task_id, {
    taskDir: paths.taskDir,
    auditPath: paths.auditPath,
  });
  assert.equal(run.label, "老板周报演示");
  assert.match(run.prompt, /老板周报/);
  assert.match(detail.goal, /老板周报演示/);
  assert.equal(detail.raw.platform_lab_run_id, run.run_id);
});

test("platform lab run ids do not collide when the same scenario is started twice in one second", async () => {
  const paths = await createPlatformLabFixture();
  const first = await createPlatformLabRun(
    {
      kind: "scenario",
      templateId: "channel-budget",
      requestedBy: "pm",
      now: "2026-06-14T10:00:00.000Z",
    },
    paths,
  );
  const second = await createPlatformLabRun(
    {
      kind: "scenario",
      templateId: "channel-budget",
      requestedBy: "pm",
      now: "2026-06-14T10:00:00.000Z",
    },
    paths,
  );

  assert.notEqual(first.task_id, second.task_id);
  const runs = await listPlatformLabRuns({ runLogPath: paths.runLogPath });
  assert.equal(runs.counts.total, 2);
  await loadTaskDetail(first.task_id, {
    taskDir: paths.taskDir,
    auditPath: paths.auditPath,
  });
  await loadTaskDetail(second.task_id, {
    taskDir: paths.taskDir,
    auditPath: paths.auditPath,
  });
});

test("platform control center aggregates existing workbench surfaces instead of only showing static inspiration", () => {
  const center = buildPlatformControlCenter({
    dataHealth: {
      counts: { datasets: 2, warnings: 1 },
      warnings: ["dataset_registry 缺少 1 个字段说明"],
    },
    governance: {
      skill_count: 3,
      mcp_policy_count: 14,
      high_risk_count: 2,
    },
    sources: {
      active_sources: 4,
      stale_sources: 1,
      failed_sources: 0,
    },
    runs: {
      total: 5,
      queued: 2,
      completed: 3,
    },
  });

  assert.deepEqual(
    center.sections.map((section) => section.id),
    ["model-tool-governance", "data-readiness", "source-operations", "platform-lab-runs"],
  );
  assert(center.sections.some((section) => section.status === "warning"));
  assert(center.summary.some((item) => item.label === "推演运行" && item.value === "5"));
});
