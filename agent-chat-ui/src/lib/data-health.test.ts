import assert from "node:assert/strict";
import { test } from "node:test";

import {
  collectArtifactLinks,
  redactServiceHost,
  summarizeEmbeddingHealth,
  summarizeConnectorRegistry,
  summarizeSensitiveFields,
  summarizeWikiKnowledgeHealth,
  summarizeWorkflowProgress,
} from "./data-health";

test("workflow progress maps canonical pipeline steps to visible states", () => {
  const progress = summarizeWorkflowProgress({
    status: "running",
    steps: [
      { task: "raw_discovery", status: "success" },
      { task: "large_excel_pipeline", status: "success" },
      { task: "fact_layer_registration", status: "warning" },
      { task: "lightrag_index", status: "running" },
    ],
  });

  assert.equal(progress.completed, 3);
  assert.equal(progress.total, 7);
  assert.deepEqual(
    progress.stages.map((stage) => [stage.key, stage.status]),
    [
      ["raw_discovery", "success"],
      ["large_excel_pipeline", "success"],
      ["fact_layer_registration", "warning"],
      ["wiki_ingest", "pending"],
      ["lightrag_index", "running"],
      ["data_quality", "pending"],
      ["final_report", "pending"],
    ],
  );
});

test("artifact links include reports, wiki pages, DuckDB assets, registry, and LightRAG state", () => {
  const links = collectArtifactLinks({
    paths: {
      duckdb_path: "/tmp/data/warehouse/a2a.duckdb",
      registry_path: "/tmp/data/warehouse/dataset_registry.json",
    },
    registry: {
      datasets: [
        {
          slug: "inventory",
          wiki_pages: {
            overview: "wiki/datasets/inventory/overview.md",
            quality_report: "wiki/datasets/inventory/quality-report.md",
          },
          derived_exports: ["data/derived/inventory_current.csv"],
        },
      ],
    },
    tasks: [
      {
        final_report: { saved_to: "data/reports/final.md" },
        steps: [
          {
            task: "lightrag_index",
            evidence: ["data/lightrag/sync-state.json", "wiki/datasets/inventory/quality-report.md"],
          },
        ],
      },
    ],
  });

  const labels = links.map((link) => link.label);
  assert(labels.includes("DuckDB"));
  assert(labels.includes("Dataset Registry"));
  assert(labels.includes("inventory overview"));
  assert(labels.includes("Final Report"));
  assert(labels.includes("LightRAG State"));
});

test("embedding health surfaces config gaps and LightRAG failure root causes", () => {
  const health = summarizeEmbeddingHealth({
    env: {
      EMBEDDING_BINDING: "openai",
      EMBEDDING_MODEL: "text-embedding-3-small",
      EMBEDDING_BINDING_HOST: "https://api.openai.com/v1",
      EMBEDDING_BINDING_API_KEY: "",
    },
    statusRecords: [
      {
        status: "failed",
        error_msg: "Embedding func: Task forcefully terminated due to execution timeout (>75s)",
      },
      {
        status: "failed",
        error_msg: "Error code: 402 - Insufficient Balance",
      },
    ],
    timeoutMs: 3500,
    latencyMs: 82,
  });

  assert.equal(health.status, "failed");
  assert.equal(health.api_key_configured, false);
  assert.equal(health.failure_counts.embedding_timeout, 1);
  assert.equal(health.failure_counts.llm_insufficient_balance, 1);
  assert.equal(health.observed_latency_ms, 82);
  assert(health.warnings.some((warning) => warning.includes("EMBEDDING_BINDING_API_KEY")));
});

test("redactServiceHost strips query strings and fragments from provider URLs", () => {
  assert.equal(
    redactServiceHost(
      "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=secret-key&foo=bar",
    ),
    "https://qyapi.weixin.qq.com/mcp/robot-doc",
  );
  assert.equal(
    redactServiceHost("https://api.openai.com/v1#fragment"),
    "https://api.openai.com/v1",
  );
});

test("connector registry summary and artifact links surface ERP connector health", () => {
  const connectors = summarizeConnectorRegistry({
    registry_path: "/tmp/data/warehouse/connector_registry.json",
    connectors: {
      jackyun_erp: {
        connector_id: "jackyun_erp",
        display_name: "吉客云 ERP",
        status: "ready",
        read_only_default: true,
        updated_at: "2026-05-19T09:30:00.000Z",
        last_sync: {
          dataset: "inventory_stock",
          status: "success",
          snapshot_path: "/tmp/data/staging/connectors/jackyun_erp/inventory_stock.csv",
          dataset_slug: "jackyun_erp_inventory_stock",
          row_count: 12,
          completed_at: "2026-05-19T09:31:00.000Z",
        },
      },
      kingdee_erp: {
        connector_id: "kingdee_erp",
        display_name: "金蝶云星空",
        status: "needs_config",
        read_only_default: true,
      },
    },
  });

  assert.equal(connectors.connector_count, 2);
  assert.equal(connectors.ready_count, 1);
  assert.equal(connectors.needs_config_count, 1);
  assert.equal(connectors.items[0].connector_id, "jackyun_erp");

  const links = collectArtifactLinks({ connectors });
  assert(links.some((link) => link.category === "connector_registry"));
  assert(links.some((link) => link.category === "connector_snapshot"));
});

test("sensitive field summary classifies internal PM guardrail categories", () => {
  const summary = summarizeSensitiveFields({
    datasets: {
      orders: {
        dataset_slug: "orders",
        relative_source: "data/cleaned/orders.csv",
        field_profiles: [
          { field: "客户手机号" },
          { field: "收货地址" },
          { field: "采购单价" },
          { field: "毛利" },
          { field: "SKU" },
        ],
      },
      finance: {
        dataset_slug: "finance",
        source: "data/cleaned/finance.csv",
        field_profiles: [{ field: "现金流" }, { field: "应收账款" }],
      },
    },
  });

  assert.equal(summary.total_sensitive_fields, 6);
  assert.equal(summary.category_counts.customer_pii, 2);
  assert.equal(summary.category_counts.procurement_price, 1);
  assert.equal(summary.category_counts.finance, 3);
  assert.equal(summary.masking_required_count, 2);
  assert.equal(summary.datasets[0].slug, "orders");
  assert.deepEqual(
    summary.datasets[0].categories.map((category) => category.category),
    ["customer_pii", "finance", "procurement_price"],
  );
});

test("wiki knowledge health tracks schema, index, log, claims, and review questions", () => {
  const health = summarizeWikiKnowledgeHealth({
    schemaPresent: true,
    indexPresent: true,
    logPresent: true,
    pages: [
      {
        path: "products/UNOVE.md",
        content:
          "---\ntype: brand\nupdated_at: 2026-05-20T00:00:00Z\nevidence:\n  - wiki/decisions/unove.md\n---\n# UNOVE\n\n品牌页。",
      },
      {
        path: "decisions/unove.md",
        content: "# UNOVE 决策\n\n当前判断缺少证据。",
      },
      {
        path: "claims/unove-stock.md",
        content:
          "---\ntype: claim\nstatus: stale\nupdated_at: 2026-05-20T00:00:00Z\nevidence:\n  - data/warehouse/dataset_registry.json\n---\n# UNOVE 库存 claim",
      },
    ],
    indexedTargets: ["products/UNOVE.md", "claims/unove-stock.md"],
    logEntries: 2,
  });

  assert.equal(health.status, "warning");
  assert.equal(health.page_count, 3);
  assert.equal(health.missing_frontmatter_count, 1);
  assert.equal(health.unsourced_claim_count, 1);
  assert.equal(health.stale_claim_count, 1);
  assert.equal(health.missing_index_count, 1);
  assert(health.review_questions.some((question) => question.includes("evidence")));
});
