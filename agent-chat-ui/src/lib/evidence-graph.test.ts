import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import {
  evidenceNodeHref,
  loadEvidenceGraphState,
  type EvidenceGraphNode,
} from "./evidence-graph";

async function createEvidenceGraphFixture() {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-evidence-graph-"));
  const dataDir = path.join(root, "data");
  const wikiDir = path.join(root, "wiki");
  const registryPath = path.join(dataDir, "warehouse", "dataset_registry.json");
  const taskDir = path.join(dataDir, "tasks");
  const reportsDir = path.join(dataDir, "reports");
  const auditPath = path.join(dataDir, "audit", "events.jsonl");
  const taskId = "task-unove-growth";
  const reportPath = path.join(reportsDir, "unove-final.md");

  await mkdir(path.dirname(registryPath), { recursive: true });
  await mkdir(path.join(wikiDir, "datasets", "UNOVE_sales"), { recursive: true });
  await mkdir(path.join(wikiDir, "decisions"), { recursive: true });
  await mkdir(taskDir, { recursive: true });
  await mkdir(reportsDir, { recursive: true });
  await mkdir(path.dirname(auditPath), { recursive: true });

  await writeFile(
    path.join(wikiDir, "datasets", "UNOVE_sales", "overview.md"),
    "# UNOVE sales dataset\n\n天猫渠道 SKU 证据。",
    "utf8",
  );
  await writeFile(
    path.join(wikiDir, "decisions", "UNOVE-growth.md"),
    "# UNOVE 增长决策\n\n需要人工确认采购。",
    "utf8",
  );
  await writeFile(
    reportPath,
    [
      "# UNOVE 5月销售提升报告",
      "",
      "## Evidence Chain",
      "- `wiki/datasets/UNOVE_sales/overview.md`",
      "- DuckDB: `data/warehouse/a2a.duckdb`",
      "- Missing data: cash, supplier",
    ].join("\n"),
    "utf8",
  );
  await writeFile(
    registryPath,
    JSON.stringify(
      {
        schema: "a2a_dataset_registry_v1",
        datasets: {
          UNOVE_sales: {
            dataset_slug: "UNOVE_sales",
            relative_source: "raw/unove-sales.xlsx",
            wiki_pages: {
              overview: "wiki/datasets/UNOVE_sales/overview.md",
              decision: "wiki/decisions/UNOVE-growth.md",
            },
            mart_views: [
              {
                category: "fact_sales_daily",
                view_name: "fact_sales_daily__UNOVE_sales",
                source_view: "UNOVE_sales__sheet",
              },
            ],
            sheet_views: [
              {
                sheet: "天猫销售",
                headers: ["品牌", "销售渠道", "SKU编码", "仓库", "供应商", "客户手机号", "客户地址", "采购价明细"],
                field_profiles: [
                  { field: "品牌", sample_values: ["UNOVE"] },
                  { field: "销售渠道", sample_values: ["天猫"] },
                  { field: "SKU编码", sample_values: ["SKU-001"] },
                  { field: "仓库", sample_values: ["杭州仓"] },
                  { field: "供应商", sample_values: ["供应商A"] },
                  { field: "客户手机号", sample_values: ["13800138000"] },
                  { field: "客户地址", sample_values: ["上海市长宁区某路1号"] },
                  { field: "采购价明细", sample_values: ["采购价=19.90"] },
                ],
              },
            ],
          },
        },
      },
      null,
      2,
    ),
    "utf8",
  );
  await writeFile(
    path.join(taskDir, `${taskId}.json`),
    JSON.stringify(
      {
        task_id: taskId,
        goal: "分析 UNOVE 天猫 SKU 增长，输出采购确认项",
        status: "warning",
        final_report: {
          saved_to: reportPath,
          evidence_chain: {
            wiki_pages: ["wiki/datasets/UNOVE_sales/overview.md"],
            report_paths: [reportPath],
            duckdb_marts: [{ mart: "fact_sales_daily__UNOVE_sales", fields: ["SKU编码", "销售渠道"] }],
            data_gaps: ["cash", "supplier"],
          },
        },
        steps: [
          {
            task: "company_strategy",
            status: "warning",
            summary: "UNOVE 天猫 SKU 增长需要人工确认采购。",
            evidence: ["wiki/datasets/UNOVE_sales/overview.md", reportPath],
            risks: ["大额采购需要人工确认"],
            missing_data: ["cash", "supplier"],
          },
        ],
      },
      null,
      2,
    ),
    "utf8",
  );
  await writeFile(
    auditPath,
    `${JSON.stringify({
      timestamp: "2026-05-20T10:00:00.000Z",
      event_type: "sensitive_field_access",
      task_id: taskId,
      tool_name: "record_sensitive_field_access",
      risk_level: "medium",
      summary: "使用敏感字段生成聚合证据。",
      risks: ["必须脱敏客户手机号和地址，不展示采购价明细。"],
      metadata: {
        category: "customer_pii",
        fields: ["客户手机号", "客户地址", "采购价=19.90"],
      },
    })}\n`,
    "utf8",
  );

  return { root, dataDir, wikiDir, registryPath, taskDir, reportsDir, auditPath, taskId, reportPath };
}

test("loads evidence graph from registry, wiki, task, report, and audit without sensitive labels", async () => {
  const fixture = await createEvidenceGraphFixture();
  const graph = await loadEvidenceGraphState({
    workspaceDir: fixture.root,
    dataDir: fixture.dataDir,
    wikiDir: fixture.wikiDir,
    registryPath: fixture.registryPath,
    taskDir: fixture.taskDir,
    reportsDir: fixture.reportsDir,
    auditPath: fixture.auditPath,
    scope: "global",
    limit: 200,
  });

  assert.equal(graph.schema, "a2a_evidence_graph_v1");
  assert.equal(graph.source_files.registry_path, fixture.registryPath);
  assert.equal(graph.counts.truncated, false);
  assert(
    [
      "brand",
      "channel",
      "sku",
      "warehouse",
      "supplier",
      "dataset",
      "mart",
      "wiki_page",
      "report",
      "decision",
      "risk",
      "field",
    ].every((type) => graph.nodes.some((node) => node.type === type)),
  );
  assert(
    [
      "derived_from",
      "summarizes",
      "references",
      "affects",
      "belongs_to",
      "has_risk",
      "needs_confirmation",
      "uses_sensitive_field",
    ].every((type) => graph.edges.some((edge) => edge.type === type)),
  );
  for (const node of graph.nodes) {
    assert(!node.label.includes("13800138000"));
    assert(!node.label.includes("上海市长宁区"));
    assert(!node.label.includes("19.90"));
  }
});

test("applies task/report scope filters, node type filters, limit, and href routing", async () => {
  const fixture = await createEvidenceGraphFixture();
  const taskGraph = await loadEvidenceGraphState({
    workspaceDir: fixture.root,
    dataDir: fixture.dataDir,
    wikiDir: fixture.wikiDir,
    registryPath: fixture.registryPath,
    taskDir: fixture.taskDir,
    reportsDir: fixture.reportsDir,
    auditPath: fixture.auditPath,
    scope: "task",
    taskId: fixture.taskId,
    limit: 200,
  });
  const reportGraph = await loadEvidenceGraphState({
    workspaceDir: fixture.root,
    dataDir: fixture.dataDir,
    wikiDir: fixture.wikiDir,
    registryPath: fixture.registryPath,
    taskDir: fixture.taskDir,
    reportsDir: fixture.reportsDir,
    auditPath: fixture.auditPath,
    scope: "report",
    reportPath: fixture.reportPath,
    nodeTypes: ["report", "wiki_page", "risk"],
    limit: 2,
  });

  const taskNode = taskGraph.nodes.find((node) => node.type === "decision") as EvidenceGraphNode;
  assert(taskNode);
  assert.equal(taskNode.metadata.task_id, fixture.taskId);
  assert.equal(evidenceNodeHref(taskNode), `/tasks/${encodeURIComponent(fixture.taskId)}`);
  assert(reportGraph.nodes.every((node) => ["report", "wiki_page", "risk"].includes(node.type)));
  assert.equal(reportGraph.counts.truncated, true);

  const reportNode = taskGraph.nodes.find((node) => node.type === "report" && node.source_path === fixture.reportPath);
  assert(reportNode);
  assert.equal(evidenceNodeHref(reportNode), `file://${fixture.reportPath.split("/").map(encodeURIComponent).join("/")}`);
});

test("rejects evidence graph path traversal and workspace-external report paths", async () => {
  const fixture = await createEvidenceGraphFixture();
  const outside = path.join(await mkdtemp(path.join(tmpdir(), "a2a-evidence-outside-")), "report.md");
  await writeFile(outside, "# 外部报告\n\n不应读取。", "utf8");

  await assert.rejects(
    loadEvidenceGraphState({
      workspaceDir: fixture.root,
      dataDir: fixture.dataDir,
      wikiDir: fixture.wikiDir,
      registryPath: fixture.registryPath,
      taskDir: fixture.taskDir,
      reportsDir: fixture.reportsDir,
      auditPath: fixture.auditPath,
      scope: "task",
      taskId: "../secrets",
    }),
    /taskId 无效/,
  );

  await assert.rejects(
    loadEvidenceGraphState({
      workspaceDir: fixture.root,
      dataDir: fixture.dataDir,
      wikiDir: fixture.wikiDir,
      registryPath: fixture.registryPath,
      taskDir: fixture.taskDir,
      reportsDir: fixture.reportsDir,
      auditPath: fixture.auditPath,
      scope: "report",
      reportPath: outside,
    }),
    /允许的证据目录/,
  );
});
