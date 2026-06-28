export type WorkflowStageStatus =
  | "success"
  | "warning"
  | "running"
  | "failed"
  | "pending"
  | "skipped";

export type WorkflowStageKey =
  | "raw_discovery"
  | "large_excel_pipeline"
  | "fact_layer_registration"
  | "wiki_ingest"
  | "lightrag_index"
  | "data_quality"
  | "final_report";

export type WorkflowStepInput = {
  task?: unknown;
  status?: unknown;
  summary?: unknown;
  evidence?: unknown;
};

export type WorkflowTaskInput = {
  status?: unknown;
  steps?: unknown;
  final_report?: unknown;
};

export type WorkflowStage = {
  key: WorkflowStageKey;
  label: string;
  status: WorkflowStageStatus;
  summary: string;
  evidence: string[];
};

export type WorkflowProgress = {
  status: WorkflowStageStatus;
  completed: number;
  total: number;
  percent: number;
  stages: WorkflowStage[];
};

export type ArtifactCategory =
  | "report"
  | "duckdb"
  | "registry"
  | "source_registry"
  | "source_snapshot"
  | "connector_registry"
  | "connector_snapshot"
  | "wiki"
  | "derived_export"
  | "lightrag_state"
  | "manifest";

export type ArtifactLink = {
  label: string;
  category: ArtifactCategory;
  path: string;
  source: string;
};

export type EmbeddingHealthStatus = "success" | "warning" | "failed";

export type EmbeddingHealth = {
  status: EmbeddingHealthStatus;
  binding: string;
  model: string;
  host: string;
  api_key_configured: boolean;
  recommended: {
    binding: string;
    model: string;
    host: string;
  };
  timeout_ms: number;
  observed_latency_ms: number | null;
  latency_source: string;
  failure_counts: Record<string, number>;
  warnings: string[];
};

export type ConnectorLastSync = {
  dataset: string;
  status: string;
  snapshot_path: string;
  dataset_slug: string;
  row_count: number;
  completed_at: string;
};

export type ConnectorSummaryItem = {
  connector_id: string;
  display_name: string;
  system: string;
  status: string;
  read_only: boolean;
  dataset_count: number;
  datasets: string[];
  last_sync: ConnectorLastSync | null;
};

export type ConnectorRegistrySummary = {
  registry_path: string;
  updated_at: string;
  connector_count: number;
  ready_count: number;
  registered_count: number;
  needs_config_count: number;
  missing_count: number;
  items: ConnectorSummaryItem[];
};

export type SensitiveFieldCategory =
  | "customer_pii"
  | "procurement_price"
  | "finance";

export type SensitiveFieldSummaryItem = {
  field: string;
  category: SensitiveFieldCategory;
  label: string;
  risk_level: "high" | "medium";
  handling: "mask_values" | "aggregate_or_audit";
};

export type SensitiveDatasetSummary = {
  slug: string;
  source: string;
  total_sensitive_fields: number;
  categories: Array<{
    category: SensitiveFieldCategory;
    count: number;
    label: string;
    risk_level: "high" | "medium";
    handling: "mask_values" | "aggregate_or_audit";
  }>;
  fields: SensitiveFieldSummaryItem[];
};

export type SensitiveFieldSummary = {
  total_sensitive_fields: number;
  masking_required_count: number;
  category_counts: Record<SensitiveFieldCategory, number>;
  datasets: SensitiveDatasetSummary[];
};

export type WikiKnowledgePageInput = {
  path: string;
  content: string;
};

export type WikiKnowledgeHealth = {
  status: "success" | "warning" | "failed";
  schema_present: boolean;
  index_present: boolean;
  log_present: boolean;
  page_count: number;
  indexed_count: number;
  log_entry_count: number;
  missing_frontmatter_count: number;
  unsourced_claim_count: number;
  orphan_count: number;
  missing_index_count: number;
  unresolved_link_count: number;
  stale_claim_count: number;
  contradicted_claim_count: number;
  warnings: string[];
  review_questions: string[];
  examples: {
    missing_frontmatter: string[];
    unsourced_claims: string[];
    orphans: string[];
    missing_index: string[];
    unresolved_links: string[];
  };
};

type StageDefinition = {
  key: WorkflowStageKey;
  label: string;
  aliases: string[];
};

type ArtifactLinkDraft = Omit<ArtifactLink, "source"> & {
  source?: string;
};

const WORKFLOW_STAGES: StageDefinition[] = [
  {
    key: "raw_discovery",
    label: "Raw Discovery",
    aliases: ["raw_discovery", "raw_ingest", "source_discovery"],
  },
  {
    key: "large_excel_pipeline",
    label: "Large Excel",
    aliases: ["large_excel_pipeline", "large_excel", "excel_cleaning"],
  },
  {
    key: "fact_layer_registration",
    label: "Fact Layer",
    aliases: [
      "fact_layer_registration",
      "fact_layer",
      "duckdb_registration",
      "dataset_registry",
    ],
  },
  {
    key: "wiki_ingest",
    label: "Wiki Ingest",
    aliases: ["wiki_ingest", "wiki_memory", "obsidian_sync"],
  },
  {
    key: "lightrag_index",
    label: "LightRAG Index",
    aliases: ["lightrag_index", "lightrag_sync", "lightrag_ingest"],
  },
  {
    key: "data_quality",
    label: "Data Quality",
    aliases: ["data_quality", "quality_report", "quality_check"],
  },
  {
    key: "final_report",
    label: "Final Report",
    aliases: ["final_report", "report_generation"],
  },
];

function safeArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeBoolean(value: unknown): boolean {
  return value === true;
}

function safeNumber(value: unknown): number {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function normalizeStatus(value: unknown): WorkflowStageStatus {
  const status = safeText(value).toLowerCase();
  if (
    ["success", "completed", "complete", "done", "ok", "ready"].includes(status)
  ) {
    return "success";
  }
  if (["warning", "warn", "partial", "degraded"].includes(status)) {
    return "warning";
  }
  if (["running", "in_progress", "processing", "active"].includes(status)) {
    return "running";
  }
  if (["failed", "failure", "error"].includes(status)) {
    return "failed";
  }
  if (["skipped", "skip"].includes(status)) {
    return "skipped";
  }
  return "pending";
}

function parseFrontmatter(content: string): Record<string, unknown> {
  if (!content.startsWith("---")) return {};
  const end = content.indexOf("\n---", 3);
  if (end < 0) return {};
  const frontmatter = content.slice(3, end).trim();
  const parsed: Record<string, unknown> = {};
  let currentListKey = "";
  for (const rawLine of frontmatter.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    if (!line.trim()) continue;
    if (line.startsWith("  - ") && currentListKey) {
      const value = line.slice(4).trim().replace(/^"|"$/g, "");
      if (!Array.isArray(parsed[currentListKey])) parsed[currentListKey] = [];
      (parsed[currentListKey] as string[]).push(value);
      continue;
    }
    const separator = line.indexOf(":");
    if (separator < 0) continue;
    const key = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    currentListKey = "";
    if (!value) {
      parsed[key] = [];
      currentListKey = key;
    } else {
      parsed[key] = value.replace(/^"|"$/g, "");
    }
  }
  return parsed;
}

function wikiPageType(
  path: string,
  frontmatter: Record<string, unknown>,
): string {
  const explicit = safeText(frontmatter.type);
  if (explicit) return explicit;
  const folder = path.split("/")[0] ?? "";
  const folderTypes: Record<string, string> = {
    brands: "brand",
    claims: "claim",
    contradictions: "contradiction",
    "data-dictionary": "dataset",
    datasets: "dataset",
    decisions: "decision",
    inventory: "warehouse",
    logs: "source",
    products: "brand",
    skus: "sku",
    sources: "source",
    suppliers: "supplier",
    warehouses: "warehouse",
  };
  return folderTypes[folder] ?? "source";
}

function wikiHasEvidence(
  content: string,
  frontmatter: Record<string, unknown>,
): boolean {
  const evidence = frontmatter.evidence;
  if (Array.isArray(evidence) && evidence.length > 0) return true;
  if (safeText(frontmatter.source)) return true;
  const lowered = content.toLowerCase();
  return [
    "## evidence",
    "## 关键证据",
    "数据源",
    "资料来源",
    "source:",
    "row_count",
    "live_read_only_fallback",
  ].some((token) => lowered.includes(token));
}

function wikiLinks(content: string): string[] {
  return [...content.matchAll(/\[\[([^|\]]+)(?:\|[^\]]+)?\]\]/g)]
    .map((match) => safeText(match[1]))
    .filter(Boolean);
}

function normalizeWikiTarget(target: string): string {
  const cleaned = safeText(target).split("#")[0];
  if (!cleaned) return "";
  return cleaned.endsWith(".md") ? cleaned : `${cleaned}.md`;
}

function wikiReviewQuestions(counts: {
  contradicted: number;
  missingFrontmatter: number;
  missingIndex: number;
  orphans: number;
  stale: number;
  unsourcedClaims: number;
  unresolvedLinks: number;
}): string[] {
  const questions = [
    "知识库复盘问题：本周新增结论是否都能追溯到 DuckDB、ERP 或 wiki 证据？",
  ];
  if (counts.unsourcedClaims > 0) {
    questions.push(
      "哪些 decision/claim 页面还缺少 evidence、row_count、查询时间或资料来源？",
    );
  }
  if (counts.orphans > 0) {
    questions.push(
      "哪些孤立页面应该链接到品牌、SKU、渠道、仓库或供应商实体页？",
    );
  }
  if (counts.missingIndex > 0) {
    questions.push(
      "是否需要刷新 wiki/index.md，让 Agent 查询前能发现最新页面？",
    );
  }
  if (counts.stale > 0 || counts.contradicted > 0) {
    questions.push("哪些过期或被推翻的 claim 需要更新经营建议或通知 PM？");
  }
  if (counts.missingFrontmatter > 0) {
    questions.push(
      "哪些旧 wiki 页面需要补 type、updated_at、source 和 evidence frontmatter？",
    );
  }
  if (counts.unresolvedLinks > 0) {
    questions.push("哪些 wikilink 指向的实体页还没有创建？");
  }
  return questions.slice(0, 12);
}

export function summarizeWikiKnowledgeHealth(input: {
  schemaPresent?: boolean;
  indexPresent?: boolean;
  indexedTargets?: string[];
  logEntries?: number;
  logPresent?: boolean;
  pages?: WikiKnowledgePageInput[];
}): WikiKnowledgeHealth {
  const pages = (input.pages ?? []).filter((page) => page.path && page.content);
  const pagePaths = new Set(pages.map((page) => page.path));
  const indexedTargets = new Set(
    (input.indexedTargets ?? []).map(normalizeWikiTarget).filter(Boolean),
  );
  const inbound = new Map<string, number>(pages.map((page) => [page.path, 0]));
  const unresolvedLinks = new Set<string>();
  for (const page of pages) {
    for (const link of wikiLinks(page.content)) {
      const target = normalizeWikiTarget(link);
      if (!target) continue;
      if (pagePaths.has(target)) {
        inbound.set(target, (inbound.get(target) ?? 0) + 1);
      } else {
        unresolvedLinks.add(target);
      }
    }
  }

  const records = pages.map((page) => {
    const frontmatter = parseFrontmatter(page.content);
    const type = wikiPageType(page.path, frontmatter);
    const hasEvidence = wikiHasEvidence(page.content, frontmatter);
    return {
      path: page.path,
      type,
      hasFrontmatter: Object.keys(frontmatter).length > 0,
      hasEvidence,
      status: safeText(frontmatter.status) || "current",
    };
  });
  const corePages = new Set(["AGENTS.md", "index.md", "log.md"]);
  const missingFrontmatter = records.filter(
    (record) => !corePages.has(record.path) && !record.hasFrontmatter,
  );
  const unsourcedClaims = records.filter(
    (record) =>
      ["claim", "decision"].includes(record.type) && !record.hasEvidence,
  );
  const orphans = records.filter(
    (record) =>
      !corePages.has(record.path) && (inbound.get(record.path) ?? 0) === 0,
  );
  const missingIndex = records.filter(
    (record) => !corePages.has(record.path) && !indexedTargets.has(record.path),
  );
  const staleClaims = records.filter(
    (record) => record.type === "claim" && record.status === "stale",
  );
  const contradictedClaims = records.filter(
    (record) => record.type === "claim" && record.status === "contradicted",
  );
  const warnings = [
    input.schemaPresent ? "" : "docs/wiki_schema.md is missing.",
    input.indexPresent ? "" : "wiki/index.md is missing.",
    input.logPresent ? "" : "wiki/log.md is missing.",
    missingFrontmatter.length
      ? `${missingFrontmatter.length} wiki pages are missing frontmatter.`
      : "",
    unsourcedClaims.length
      ? `${unsourcedClaims.length} decision/claim pages have no evidence.`
      : "",
    missingIndex.length
      ? `${missingIndex.length} wiki pages are not listed in index.md.`
      : "",
    unresolvedLinks.size
      ? `${unresolvedLinks.size} wikilinks point to missing pages.`
      : "",
    contradictedClaims.length
      ? `${contradictedClaims.length} claims are contradicted.`
      : "",
  ].filter(Boolean);
  const status: WikiKnowledgeHealth["status"] =
    !input.schemaPresent || !input.indexPresent || !input.logPresent
      ? "failed"
      : warnings.length > 0 || staleClaims.length > 0
        ? "warning"
        : "success";
  return {
    status,
    schema_present: Boolean(input.schemaPresent),
    index_present: Boolean(input.indexPresent),
    log_present: Boolean(input.logPresent),
    page_count: records.length,
    indexed_count: indexedTargets.size,
    log_entry_count: input.logEntries ?? 0,
    missing_frontmatter_count: missingFrontmatter.length,
    unsourced_claim_count: unsourcedClaims.length,
    orphan_count: orphans.length,
    missing_index_count: missingIndex.length,
    unresolved_link_count: unresolvedLinks.size,
    stale_claim_count: staleClaims.length,
    contradicted_claim_count: contradictedClaims.length,
    warnings,
    review_questions: wikiReviewQuestions({
      contradicted: contradictedClaims.length,
      missingFrontmatter: missingFrontmatter.length,
      missingIndex: missingIndex.length,
      orphans: orphans.length,
      stale: staleClaims.length,
      unsourcedClaims: unsourcedClaims.length,
      unresolvedLinks: unresolvedLinks.size,
    }),
    examples: {
      missing_frontmatter: missingFrontmatter
        .slice(0, 8)
        .map((record) => record.path),
      unsourced_claims: unsourcedClaims
        .slice(0, 8)
        .map((record) => record.path),
      orphans: orphans.slice(0, 8).map((record) => record.path),
      missing_index: missingIndex.slice(0, 8).map((record) => record.path),
      unresolved_links: [...unresolvedLinks].sort().slice(0, 8),
    },
  };
}

function taskName(step: WorkflowStepInput): string {
  return safeText(step.task).toLowerCase();
}

function findStepForStage(
  steps: WorkflowStepInput[],
  stage: StageDefinition,
): WorkflowStepInput | undefined {
  const exact = steps.find((step) => taskName(step) === stage.key);
  if (exact) return exact;
  return steps.find((step) => stage.aliases.includes(taskName(step)));
}

function finalReportSavedTo(task: WorkflowTaskInput): string {
  return safeText(safeRecord(task.final_report).saved_to);
}

function summarizeOverallStatus(stages: WorkflowStage[]): WorkflowStageStatus {
  if (stages.some((stage) => stage.status === "failed")) return "failed";
  if (stages.some((stage) => stage.status === "running")) return "running";
  if (stages.some((stage) => stage.status === "warning")) return "warning";
  if (stages.every((stage) => stage.status === "success")) return "success";
  return "pending";
}

export function summarizeWorkflowProgress(
  task: WorkflowTaskInput | null | undefined,
): WorkflowProgress {
  const workflow = safeRecord(task);
  const steps = safeArray<WorkflowStepInput>(workflow.steps).filter(
    (step) => step && typeof step === "object",
  );

  const stages = WORKFLOW_STAGES.map<WorkflowStage>((stage) => {
    const step = findStepForStage(steps, stage);
    const hasFinalReport =
      stage.key === "final_report" && finalReportSavedTo(workflow).length > 0;
    const status = hasFinalReport
      ? "success"
      : normalizeStatus(step?.status ?? "pending");

    return {
      key: stage.key,
      label: stage.label,
      status,
      summary: safeText(step?.summary),
      evidence: safeArray(step?.evidence).map(safeText).filter(Boolean),
    };
  });

  const completed = stages.filter((stage) =>
    ["success", "warning"].includes(stage.status),
  ).length;
  const total = stages.length;

  return {
    status: summarizeOverallStatus(stages),
    completed,
    total,
    percent: total > 0 ? Math.round((completed / total) * 100) : 0,
    stages,
  };
}

function normalizeArtifactPath(value: unknown): string {
  const text = safeText(value);
  if (text.startsWith("file://")) return text.replace(/^file:\/\//, "");
  return text;
}

function filenameWithoutExtension(filePath: string): string {
  const fileName = filePath.split(/[\\/]/).filter(Boolean).at(-1) ?? filePath;
  return fileName.replace(/\.[^.]+$/, "");
}

function labelFromWikiPath(filePath: string): string {
  const datasetMatch = filePath.match(
    /(?:^|\/)datasets\/([^/]+)\/([^/]+)\.md$/,
  );
  if (datasetMatch) {
    const page = datasetMatch[2].replace(/-/g, " ");
    return `${datasetMatch[1]} ${page}`;
  }
  return filenameWithoutExtension(filePath).replace(/-/g, " ");
}

function inferArtifactLink(rawPath: unknown): ArtifactLinkDraft | null {
  const artifactPath = normalizeArtifactPath(rawPath);
  if (!artifactPath) return null;

  const lowerPath = artifactPath.toLowerCase();
  if (lowerPath.endsWith(".duckdb")) {
    return { label: "DuckDB", category: "duckdb", path: artifactPath };
  }
  if (lowerPath.includes("dataset_registry")) {
    return {
      label: "Dataset Registry",
      category: "registry",
      path: artifactPath,
    };
  }
  if (lowerPath.includes("lightrag")) {
    return {
      label: "LightRAG State",
      category: "lightrag_state",
      path: artifactPath,
    };
  }
  if (
    lowerPath.includes("/derived/") ||
    lowerPath.startsWith("data/derived/")
  ) {
    return {
      label: `${filenameWithoutExtension(artifactPath)} export`,
      category: "derived_export",
      path: artifactPath,
    };
  }
  if (lowerPath.includes("manifest.json")) {
    return {
      label: "Manifest",
      category: "manifest",
      path: artifactPath,
    };
  }
  if (
    lowerPath.includes("quality_report") ||
    lowerPath.includes("quality-report")
  ) {
    return {
      label: "Quality Report",
      category: "report",
      path: artifactPath,
    };
  }
  if (
    lowerPath.includes("/reports/") ||
    lowerPath.startsWith("data/reports/")
  ) {
    return { label: "Report", category: "report", path: artifactPath };
  }
  if (
    lowerPath.endsWith(".md") &&
    (lowerPath.includes("/wiki/") ||
      lowerPath.startsWith("wiki/") ||
      lowerPath.startsWith("datasets/") ||
      lowerPath.startsWith("decisions/") ||
      lowerPath.startsWith("data-dictionary/") ||
      lowerPath.startsWith("cleaning-rules/") ||
      lowerPath.startsWith("logs/") ||
      lowerPath.startsWith("products/"))
  ) {
    return {
      label: labelFromWikiPath(artifactPath),
      category: "wiki",
      path: artifactPath,
    };
  }

  return null;
}

function collectDatasets(registry: unknown): Record<string, unknown>[] {
  const datasets = safeRecord(registry).datasets;
  if (Array.isArray(datasets)) return datasets.map(safeRecord);
  return Object.values(safeRecord(datasets)).map(safeRecord);
}

const SENSITIVE_FIELD_RULES: Record<
  SensitiveFieldCategory,
  {
    label: string;
    risk_level: "high" | "medium";
    handling: "mask_values" | "aggregate_or_audit";
    patterns: string[];
  }
> = {
  customer_pii: {
    label: "客户个人信息",
    risk_level: "high",
    handling: "mask_values",
    patterns: [
      "手机号",
      "手机",
      "电话",
      "收货人",
      "客户姓名",
      "姓名",
      "地址",
      "身份证",
      "会员id",
      "会员_id",
      "openid",
      "买家账号",
      "收件人",
    ],
  },
  procurement_price: {
    label: "采购价/供应商报价",
    risk_level: "medium",
    handling: "aggregate_or_audit",
    patterns: [
      "采购单价",
      "采购价",
      "进价",
      "成本价",
      "供应商报价",
      "采购金额",
      "含税单价",
      "未税单价",
    ],
  },
  finance: {
    label: "财务数据",
    risk_level: "medium",
    handling: "aggregate_or_audit",
    patterns: [
      "毛利",
      "净利",
      "利润",
      "回款",
      "应收",
      "应付",
      "现金流",
      "账期",
      "收入",
      "费用",
      "成本",
    ],
  },
};

function normalizeFieldName(value: unknown): string {
  return safeText(value)
    .toLowerCase()
    .replace(/[\s_-]+/g, "");
}

function classifySensitiveField(
  field: string,
): SensitiveFieldSummaryItem | null {
  const normalized = normalizeFieldName(field);
  if (!normalized) return null;
  for (const [category, rule] of Object.entries(SENSITIVE_FIELD_RULES) as Array<
    [
      SensitiveFieldCategory,
      (typeof SENSITIVE_FIELD_RULES)[SensitiveFieldCategory],
    ]
  >) {
    const matched = rule.patterns.some((pattern) =>
      normalized.includes(normalizeFieldName(pattern)),
    );
    if (!matched) continue;
    return {
      field,
      category,
      label: rule.label,
      risk_level: rule.risk_level,
      handling: rule.handling,
    };
  }
  return null;
}

function sensitiveFieldProfiles(dataset: Record<string, unknown>): string[] {
  return safeArray(dataset.field_profiles)
    .map((profile) => safeText(safeRecord(profile).field))
    .filter(Boolean);
}

export function summarizeSensitiveFields(
  registry: unknown,
): SensitiveFieldSummary {
  const datasets = collectDatasets(registry);
  const categoryCounts: Record<SensitiveFieldCategory, number> = {
    customer_pii: 0,
    procurement_price: 0,
    finance: 0,
  };
  const datasetSummaries: SensitiveDatasetSummary[] = [];

  for (const dataset of datasets) {
    const seen = new Set<string>();
    const fields = sensitiveFieldProfiles(dataset).flatMap((field) => {
      const classified = classifySensitiveField(field);
      if (!classified) return [];
      const key = `${classified.category}:${classified.field}`;
      if (seen.has(key)) return [];
      seen.add(key);
      return [classified];
    });
    if (fields.length === 0) continue;

    const datasetCategoryCounts = new Map<SensitiveFieldCategory, number>();
    for (const field of fields) {
      categoryCounts[field.category] += 1;
      datasetCategoryCounts.set(
        field.category,
        (datasetCategoryCounts.get(field.category) ?? 0) + 1,
      );
    }

    datasetSummaries.push({
      slug: safeText(dataset.slug) || safeText(dataset.dataset_slug),
      source: safeText(dataset.relative_source) || safeText(dataset.source),
      total_sensitive_fields: fields.length,
      categories: Array.from(datasetCategoryCounts.entries())
        .map(([category, count]) => ({
          category,
          count,
          label: SENSITIVE_FIELD_RULES[category].label,
          risk_level: SENSITIVE_FIELD_RULES[category].risk_level,
          handling: SENSITIVE_FIELD_RULES[category].handling,
        }))
        .toSorted((left, right) => left.category.localeCompare(right.category)),
      fields,
    });
  }

  return {
    total_sensitive_fields: Object.values(categoryCounts).reduce(
      (sum, count) => sum + count,
      0,
    ),
    masking_required_count: categoryCounts.customer_pii,
    category_counts: categoryCounts,
    datasets: datasetSummaries.toSorted(
      (left, right) =>
        right.total_sensitive_fields - left.total_sensitive_fields ||
        left.slug.localeCompare(right.slug),
    ),
  };
}

function firstOverviewPage(dataset: Record<string, unknown>): string {
  const explicit =
    safeText(dataset.overview_page) || safeText(dataset.wiki_overview_path);
  if (explicit) return explicit;
  const wikiPages = datasetWikiPages(dataset);
  return wikiPages.find((page) => page.endsWith("/overview.md")) ?? "";
}

function datasetWikiPages(dataset: Record<string, unknown>): string[] {
  const wikiPages = dataset.wiki_pages;
  if (Array.isArray(wikiPages)) return wikiPages.map(safeText).filter(Boolean);
  return Object.values(safeRecord(wikiPages)).map(safeText).filter(Boolean);
}

function addArtifactLink(
  links: ArtifactLink[],
  seenPaths: Set<string>,
  draft: ArtifactLinkDraft | null,
  source: string,
) {
  if (!draft?.path) return;
  const key = draft.path.toLowerCase();
  if (seenPaths.has(key)) return;
  seenPaths.add(key);
  links.push({ ...draft, source: draft.source ?? source });
}

function collectConnectorRecords(
  connectors: unknown,
): Record<string, unknown>[] {
  const record = safeRecord(connectors);
  if (Array.isArray(record.items)) return record.items.map(safeRecord);
  const connectorMap = safeRecord(record.connectors);
  return Object.values(connectorMap).map(safeRecord);
}

function normalizeConnectorLastSync(value: unknown): ConnectorLastSync | null {
  const record = safeRecord(value);
  const snapshotPath = normalizeArtifactPath(record.snapshot_path);
  if (!snapshotPath && !safeText(record.dataset_slug)) return null;
  return {
    dataset: safeText(record.dataset),
    status: safeText(record.status) || "unknown",
    snapshot_path: snapshotPath,
    dataset_slug: safeText(record.dataset_slug),
    row_count: safeNumber(record.row_count),
    completed_at: safeText(record.completed_at),
  };
}

export function summarizeConnectorRegistry(
  input: unknown,
): ConnectorRegistrySummary {
  const registry = safeRecord(input);
  const items = collectConnectorRecords(registry).map<ConnectorSummaryItem>(
    (connector) => {
      const datasets = Object.keys(safeRecord(connector.datasets));
      return {
        connector_id: safeText(connector.connector_id),
        display_name: safeText(connector.display_name),
        system: safeText(connector.system),
        status: safeText(connector.status) || "unknown",
        read_only:
          safeBoolean(connector.read_only) ||
          safeBoolean(connector.read_only_default),
        dataset_count: datasets.length,
        datasets,
        last_sync: normalizeConnectorLastSync(connector.last_sync),
      };
    },
  );

  return {
    registry_path: normalizeArtifactPath(registry.registry_path),
    updated_at: safeText(registry.updated_at),
    connector_count: items.length,
    ready_count: items.filter((item) => item.status === "ready").length,
    registered_count: items.filter((item) => item.status === "registered")
      .length,
    needs_config_count: items.filter((item) => item.status === "needs_config")
      .length,
    missing_count: items.filter((item) => item.status === "missing_skill")
      .length,
    items,
  };
}

export function collectArtifactLinks(input: {
  paths?: unknown;
  registry?: unknown;
  tasks?: unknown;
  connectors?: unknown;
}): ArtifactLink[] {
  const links: ArtifactLink[] = [];
  const seenPaths = new Set<string>();
  const paths = safeRecord(input.paths);

  addArtifactLink(
    links,
    seenPaths,
    {
      label: "DuckDB",
      category: "duckdb",
      path: normalizeArtifactPath(paths.duckdb_path),
    },
    "paths",
  );
  addArtifactLink(
    links,
    seenPaths,
    safeText(paths.source_registry_path)
      ? {
          label: "Source Registry",
          category: "source_registry",
          path: normalizeArtifactPath(paths.source_registry_path),
        }
      : null,
    "paths",
  );
  addArtifactLink(
    links,
    seenPaths,
    safeText(paths.source_snapshot_manifest_path)
      ? {
          label: "Source Snapshot Manifest",
          category: "source_snapshot",
          path: normalizeArtifactPath(paths.source_snapshot_manifest_path),
        }
      : null,
    "paths",
  );

  const connectorSummary = summarizeConnectorRegistry(input.connectors);
  addArtifactLink(
    links,
    seenPaths,
    connectorSummary.registry_path
      ? {
          label: "Connector Registry",
          category: "connector_registry",
          path: connectorSummary.registry_path,
        }
      : null,
    "connectors",
  );
  for (const connector of connectorSummary.items) {
    if (!connector.last_sync?.snapshot_path) continue;
    addArtifactLink(
      links,
      seenPaths,
      {
        label: `${connector.display_name || connector.connector_id} ${connector.last_sync.dataset} snapshot`,
        category: "connector_snapshot",
        path: connector.last_sync.snapshot_path,
      },
      "connectors",
    );
  }
  addArtifactLink(
    links,
    seenPaths,
    {
      label: "Dataset Registry",
      category: "registry",
      path: normalizeArtifactPath(paths.registry_path),
    },
    "paths",
  );

  for (const dataset of collectDatasets(input.registry)) {
    const slug = safeText(dataset.slug) || safeText(dataset.dataset_slug);
    const overviewPage = firstOverviewPage(dataset);
    addArtifactLink(
      links,
      seenPaths,
      overviewPage
        ? {
            label: slug ? `${slug} overview` : labelFromWikiPath(overviewPage),
            category: "wiki",
            path: normalizeArtifactPath(overviewPage),
          }
        : null,
      "registry",
    );

    for (const wikiPage of datasetWikiPages(dataset)) {
      addArtifactLink(
        links,
        seenPaths,
        inferArtifactLink(wikiPage),
        "registry",
      );
    }

    for (const derivedExport of safeArray(dataset.derived_exports)) {
      addArtifactLink(
        links,
        seenPaths,
        {
          label: slug ? `${slug} derived export` : "Derived Export",
          category: "derived_export",
          path: normalizeArtifactPath(derivedExport),
        },
        "registry",
      );
    }

    for (const registryPath of [
      dataset.manifest_path,
      dataset.quality_report_path,
      dataset.duckdb_path,
    ]) {
      addArtifactLink(
        links,
        seenPaths,
        inferArtifactLink(registryPath),
        "registry",
      );
    }
  }

  for (const task of safeArray(input.tasks).map(safeRecord)) {
    const finalReport = safeRecord(task.final_report);
    addArtifactLink(
      links,
      seenPaths,
      safeText(finalReport.saved_to)
        ? {
            label: "Final Report",
            category: "report",
            path: normalizeArtifactPath(finalReport.saved_to),
          }
        : null,
      "task",
    );

    const evidenceChain = safeRecord(finalReport.evidence_chain);
    for (const chainPath of [
      evidenceChain.duckdb_path,
      evidenceChain.registry_path,
      ...safeArray(evidenceChain.report_paths),
      ...safeArray(evidenceChain.manifest_paths),
      ...safeArray(evidenceChain.wiki_pages),
    ]) {
      addArtifactLink(links, seenPaths, inferArtifactLink(chainPath), "task");
    }

    for (const step of safeArray(task.steps).map(safeRecord)) {
      for (const evidencePath of safeArray(step.evidence)) {
        addArtifactLink(
          links,
          seenPaths,
          inferArtifactLink(evidencePath),
          "task",
        );
      }
    }
  }

  return links;
}

function classifyLightRAGError(value: unknown): string {
  const text = safeText(value).toLowerCase();
  if (!text) return "unknown";
  if (
    text.includes("insufficient balance") ||
    text.includes("error code: 402")
  ) {
    return "llm_insufficient_balance";
  }
  if (text.includes("embedding") && text.includes("timeout")) {
    return "embedding_timeout";
  }
  if (text.includes("llm") && text.includes("timeout")) {
    return "llm_timeout";
  }
  if (text.includes("timeout")) {
    return "timeout";
  }
  if (
    text.includes("model") &&
    (text.includes("not found") || text.includes("unavailable"))
  ) {
    return "model_unavailable";
  }
  return "provider_api_error";
}

function incrementCounter(counter: Record<string, number>, key: string) {
  counter[key] = (counter[key] ?? 0) + 1;
}

export function summarizeEmbeddingHealth(input: {
  env?: Record<string, string | undefined>;
  statusRecords?: unknown[];
  timeoutMs?: number;
  latencyMs?: number | null;
  latencySource?: string;
}): EmbeddingHealth {
  const env = input.env ?? {};
  const binding = safeText(env.EMBEDDING_BINDING) || "openai";
  const host =
    safeText(env.EMBEDDING_BINDING_HOST) ||
    safeText(env.OPENAI_BASE_URL) ||
    "https://api.openai.com/v1";
  const model = safeText(env.EMBEDDING_MODEL) || "text-embedding-3-small";
  const apiKeyConfigured = Boolean(
    safeText(env.EMBEDDING_BINDING_API_KEY) || safeText(env.OPENAI_API_KEY),
  );
  const failureCounts: Record<string, number> = {};

  for (const record of safeArray(input.statusRecords).map(safeRecord)) {
    if (safeText(record.status).toLowerCase() !== "failed") continue;
    const error = safeText(record.error_msg) || safeText(record.error);
    incrementCounter(failureCounts, classifyLightRAGError(error));
  }

  const warnings: string[] = [];
  if (!apiKeyConfigured) {
    warnings.push(
      "EMBEDDING_BINDING_API_KEY is not configured; LightRAG embedding may fail.",
    );
  }
  if (failureCounts.embedding_timeout) {
    warnings.push(
      "Recent LightRAG failures include embedding timeouts; verify host/model/key and document size.",
    );
  }
  if (failureCounts.llm_insufficient_balance) {
    warnings.push(
      "Recent LightRAG failures include provider balance or quota errors before retrying.",
    );
  }
  if (binding !== "openai") {
    warnings.push(
      `Embedding binding is ${binding}; recommended local default is openai.`,
    );
  }

  const status: EmbeddingHealthStatus =
    !apiKeyConfigured || failureCounts.llm_insufficient_balance
      ? "failed"
      : failureCounts.embedding_timeout ||
          failureCounts.model_unavailable ||
          failureCounts.provider_api_error
        ? "warning"
        : "success";

  return {
    status,
    binding,
    model,
    host,
    api_key_configured: apiKeyConfigured,
    recommended: {
      binding: "openai",
      model: "text-embedding-3-small",
      host: "https://api.openai.com/v1",
    },
    timeout_ms: Number.isFinite(input.timeoutMs)
      ? Number(input.timeoutMs)
      : 3500,
    observed_latency_ms:
      typeof input.latencyMs === "number" && Number.isFinite(input.latencyMs)
        ? Math.round(input.latencyMs)
        : null,
    latency_source: input.latencySource ?? "local_doc_status_read",
    failure_counts: failureCounts,
    warnings,
  };
}
