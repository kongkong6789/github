import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { dispatchWorkbench, resolveWorkbenchScope } from "./workbench-server";

async function createWorkbenchFixture() {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-workbench-"));
  const dataDir = path.join(root, "data");
  const taskDir = path.join(dataDir, "tasks");
  const auditPath = path.join(dataDir, "audit", "events.jsonl");
  const threadArchiveDir = path.join(dataDir, "thread_archive");
  const warehouseDir = path.join(dataDir, "warehouse");
  const reportsDir = path.join(dataDir, "reports");
  const wikiDir = path.join(root, "wiki");
  const taskId = "20260520-120000-workbench";
  const reportPath = path.join(reportsDir, "workbench-report.md");

  await mkdir(taskDir, { recursive: true });
  await mkdir(path.dirname(auditPath), { recursive: true });
  await mkdir(threadArchiveDir, { recursive: true });
  await mkdir(warehouseDir, { recursive: true });
  await mkdir(reportsDir, { recursive: true });
  await mkdir(path.join(wikiDir, "datasets", "demo"), { recursive: true });

  await writeFile(
    path.join(taskDir, `${taskId}.json`),
    JSON.stringify(
      {
        task_id: taskId,
        goal: "P9 workbench fixture",
        status: "success",
        created_at: "2026-05-20T12:00:00.000Z",
        updated_at: "2026-05-20T12:03:00.000Z",
        final_report: {
          saved_to: reportPath,
          evidence_chain: {
            wiki_pages: ["wiki/datasets/demo/overview.md"],
            report_paths: [reportPath],
          },
        },
        steps: [
          {
            task: "raw_discovery",
            status: "success",
            summary: "fixture task step",
            completed_at: "2026-05-20T12:01:00.000Z",
            evidence: ["wiki/datasets/demo/overview.md"],
          },
        ],
      },
      null,
      2,
    ),
    "utf8",
  );
  await writeFile(
    path.join(wikiDir, "datasets", "demo", "overview.md"),
    "# UNOVE demo dataset\n\n天猫渠道经营证据。",
    "utf8",
  );
  await writeFile(
    reportPath,
    "# Workbench Report\n\nEvidence Chain\n\n- `wiki/datasets/demo/overview.md`\n",
    "utf8",
  );
  await writeFile(
    auditPath,
    `${JSON.stringify({
      timestamp: "2026-05-20T12:02:00.000Z",
      created_at: "2026-05-20T12:02:00.000Z",
      event_type: "mcp_tool_called",
      actor: "agent",
      thread_id: "thread-1",
      task_id: taskId,
      agent_id: "data_agent",
      tool_name: "query_fact_layer",
      risk_level: "medium",
      summary: "fixture audit event",
      metadata: { tool_name: "query_fact_layer", risk_level: "medium" },
    })}\n`,
    "utf8",
  );
  await writeFile(
    path.join(root, "langgraph-server.log"),
    "2026-05-20T12:04:00.000Z INFO fixture log\n",
    "utf8",
  );
  await writeFile(
    path.join(warehouseDir, "dataset_registry.json"),
    JSON.stringify({
      schema: "a2a_dataset_registry_v1",
      datasets: {
        demo: {
          dataset_slug: "demo",
          wiki_pages: { overview: "wiki/datasets/demo/overview.md" },
          sheet_views: [
            {
              headers: ["品牌", "销售渠道"],
              field_profiles: [
                { field: "品牌", sample_values: ["UNOVE"] },
                { field: "销售渠道", sample_values: ["天猫"] },
              ],
            },
          ],
        },
      },
    }),
    "utf8",
  );
  await mkdir(path.join(dataDir, "source_registry"), { recursive: true });
  await writeFile(
    path.join(dataDir, "source_registry", "sources.json"),
    JSON.stringify({
      schema: "a2a_source_registry_v1",
      updated_at: "2026-05-30T10:00:00.000Z",
      sources: {
        sales_daily: {
          source_id: "sales_daily",
          display_name: "销售日报",
          source_type: "local_file",
          uri: path.join(root, "exports", "sales.csv"),
          allowed_root: path.join(root, "exports"),
          sync_mode: "on_demand",
          owner: "ops",
          freshness_sla: "24h",
          status: "active",
          credential_env_keys: [],
        },
      },
    }),
    "utf8",
  );
  await writeFile(
    path.join(dataDir, "source_registry", "snapshots.jsonl"),
    `${JSON.stringify({
      snapshot_id: "20260530-100000-aaa",
      source_id: "sales_daily",
      source_type: "local_file",
      observed_at: "2026-05-30T10:00:00.000Z",
      raw_snapshot_path: path.join(
        root,
        "raw",
        "snapshots",
        "sales_daily",
        "20260530-100000-aaa",
        "original.csv",
      ),
      row_count: 1,
      schema_hash: "hash-a",
      schema: { sales: ["date", "sku", "qty"] },
      sheet_names: ["sales"],
      status: "success",
      duckdb_dataset_slug: "sales_daily_a",
    })}\n`,
    "utf8",
  );

  return {
    root,
    paths: {
      workspaceDir: root,
      dataDir,
      taskDir,
      auditPath,
      threadArchiveDir,
      wikiDir,
      reportsDir,
      warehouseDir,
      duckdbPath: path.join(warehouseDir, "a2a.duckdb"),
      registryPath: path.join(warehouseDir, "dataset_registry.json"),
      connectorRegistryPath: path.join(warehouseDir, "connector_registry.json"),
      lightragWorkingDir: path.join(dataDir, "lightrag_official"),
      skillRegistryDir: path.join(dataDir, "skill_registry"),
      templateDir: path.join(dataDir, "agent_templates"),
      mcpPolicyPath: path.join(dataDir, "mcp", "tool_policy.json"),
      lightragIndexPath: path.join(dataDir, "lightrag", "index.json"),
      sourceRegistryDir: path.join(dataDir, "source_registry"),
      sourceRegistryPath: path.join(dataDir, "source_registry", "sources.json"),
      sourceSnapshotManifestPath: path.join(
        dataDir,
        "source_registry",
        "snapshots.jsonl",
      ),
    },
    taskId,
  };
}

test("workbench scope helper only treats explicit global as global history access", () => {
  assert.deepEqual(resolveWorkbenchScope({}), {
    scope: "",
    thread_id: "",
    task_id: "",
    agent_id: "",
    tool_name: "",
    is_global: false,
    is_scoped: false,
  });
  assert.equal(resolveWorkbenchScope({ scope: "global" }).is_global, true);
  assert.equal(resolveWorkbenchScope({ task_id: "task-1" }).is_scoped, true);
  assert.equal(
    resolveWorkbenchScope({ threadId: "thread-1" }).thread_id,
    "thread-1",
  );
});

test("workbench blocks global task, trace, governance audit, and log history without scope", async () => {
  const { paths } = await createWorkbenchFixture();

  const tasks = await dispatchWorkbench("task.list", {}, { paths });
  assert.equal(tasks.data.tasks.length, 0);
  assert(tasks.warnings.some((warning) => warning.includes("scope=global")));

  const trace = await dispatchWorkbench("agent.trace", {}, { paths });
  assert.equal(trace.data.timeline.length, 0);
  assert.equal(trace.data.tool_calls.length, 0);
  assert.equal(trace.data.task_steps.length, 0);
  assert.equal(trace.data.audit_events.length, 0);

  const governance = await dispatchWorkbench(
    "governance.policy",
    {},
    { paths },
  );
  assert.equal(governance.data.audit_events.length, 0);
  assert(governance.warnings.some((warning) => warning.includes("audit")));

  const logs = await dispatchWorkbench("logs.tail", {}, { paths });
  assert.equal(logs.data.entries.length, 0);
  assert(logs.warnings.some((warning) => warning.includes("scope=global")));

  const evidence = await dispatchWorkbench("evidence.graph", {}, { paths });
  assert.equal(evidence.data.nodes.length, 0);
  assert(evidence.warnings.some((warning) => warning.includes("scope=global")));

  const sources = await dispatchWorkbench("source.list", {}, { paths });
  assert.equal(sources.data.sources.length, 0);
  assert(sources.warnings.some((warning) => warning.includes("scope=global")));
});

test("workbench returns typed control-plane data with explicit global scope", async () => {
  const { paths, taskId } = await createWorkbenchFixture();

  const tasks = await dispatchWorkbench(
    "task.list",
    { scope: "global" },
    { paths },
  );
  assert.equal(tasks.data.tasks[0].task_id, taskId);

  const trace = await dispatchWorkbench(
    "agent.trace",
    { scope: "global" },
    { paths },
  );
  assert.equal(trace.data.task_steps.length, 1);
  assert.equal(trace.data.audit_events.length, 1);
  assert.equal(trace.data.timeline.length, 2);

  const logs = await dispatchWorkbench(
    "logs.tail",
    { scope: "global" },
    { paths },
  );
  assert(logs.data.entries.some((entry) => entry.source === "audit"));
  assert(logs.data.entries.some((entry) => entry.source === "langgraph"));

  const health = await dispatchWorkbench(
    "data.health",
    { scope: "global" },
    { paths },
  );
  assert.equal(health.data.schema_version, "a2a_data_health_v1");
  assert.equal(health.data.source_files.registry_path, paths.registryPath);
  assert.equal(health.data.tasks[0].task_id, taskId);

  const governance = await dispatchWorkbench(
    "governance.policy",
    { scope: "global" },
    { paths },
  );
  assert.equal(governance.data.schema_version, "a2a_governance_state_v1");
  assert.equal(governance.data.audit_events.length, 1);

  const evidence = await dispatchWorkbench(
    "evidence.graph",
    { scope: "global" },
    { paths },
  );
  assert.equal(evidence.data.schema, "a2a_evidence_graph_v1");
  assert(evidence.data.nodes.some((node) => node.type === "dataset"));
  assert(evidence.data.edges.some((edge) => edge.type === "references"));

  const sources = await dispatchWorkbench(
    "source.list",
    { scope: "global" },
    { paths },
  );
  assert.equal(sources.data.schema, "a2a_data_sources_v1");
  assert.equal(sources.data.sources[0].source_id, "sales_daily");
  assert.equal(sources.data.sources[0].snapshot_count, 1);

  const taskEvidence = await dispatchWorkbench(
    "evidence.graph",
    {
      scope: "task",
      task_id: taskId,
      nodeTypes: ["decision"],
      limit: 5,
    },
    { paths },
  );
  assert(
    taskEvidence.data.nodes.some((node) => node.metadata.task_id === taskId),
  );
});

test("approval.submit only normalizes an Agent Inbox resume payload", async () => {
  const result = await dispatchWorkbench("approval.submit", {
    thread_id: "thread-1",
    decisions: [{ type: "approve" }],
  });

  assert.deepEqual(result.data, {
    status: "ready",
    thread_id: "thread-1",
    resume: { decisions: [{ type: "approve" }] },
    execution_mode: "approval_request_only",
  });
});
