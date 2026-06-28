import { realpath, readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

export const EVIDENCE_GRAPH_SCHEMA = "a2a_evidence_graph_v1";
export const EVIDENCE_GRAPH_NODE_TYPES = [
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
] as const;
export const EVIDENCE_GRAPH_EDGE_TYPES = [
  "derived_from",
  "summarizes",
  "references",
  "affects",
  "belongs_to",
  "has_risk",
  "needs_confirmation",
  "uses_sensitive_field",
] as const;

export type EvidenceGraphNodeType = (typeof EVIDENCE_GRAPH_NODE_TYPES)[number];
export type EvidenceGraphEdgeType = (typeof EVIDENCE_GRAPH_EDGE_TYPES)[number];

export type EvidenceGraphNode = {
  id: string;
  type: EvidenceGraphNodeType;
  label: string;
  source_path: string;
  summary: string;
  risk_level: string;
  metadata: Record<string, unknown>;
};

export type EvidenceGraphEdge = {
  id: string;
  type: EvidenceGraphEdgeType;
  source: string;
  target: string;
  label: string;
  source_path: string;
  summary: string;
  risk_level: string;
  metadata: Record<string, unknown>;
};

export type EvidenceGraphState = {
  schema: typeof EVIDENCE_GRAPH_SCHEMA;
  generated_at: string;
  scope: string;
  source_files: {
    workspace_dir: string;
    data_dir: string;
    wiki_dir: string;
    task_dir: string;
    reports_dir: string;
    registry_path: string;
    audit_path: string;
    lightrag_index_path: string;
  };
  filters: {
    task_id: string;
    report_path: string;
    node_types: string[];
    edge_types: string[];
    limit: number;
  };
  counts: {
    nodes: number;
    edges: number;
    truncated: boolean;
  };
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
  warnings: string[];
};

export type LoadEvidenceGraphOptions = {
  workspaceDir?: string;
  dataDir?: string;
  wikiDir?: string;
  taskDir?: string;
  reportsDir?: string;
  registryPath?: string;
  auditPath?: string;
  lightragIndexPath?: string;
  scope?: "global" | "task" | "report" | string;
  taskId?: string;
  task_id?: string;
  reportPath?: string;
  report_path?: string;
  nodeTypes?: string[];
  edgeTypes?: string[];
  limit?: number;
};

type JsonRecord = Record<string, unknown>;
type SensitiveCategory = "" | "customer_pii" | "procurement_price" | "finance";

const NODE_TYPE_SET = new Set<string>(EVIDENCE_GRAPH_NODE_TYPES);
const EDGE_TYPE_SET = new Set<string>(EVIDENCE_GRAPH_EDGE_TYPES);
const KNOWN_BRANDS = ["UNOVE", "narka", "LABO-H", "Dr.BangGiWon", "AESTURA", "2AST"];
const CHANNEL_KEYWORDS = ["天猫", "淘宝", "抖音", "京东", "拼多多", "唯品会", "小红书", "线下", "外贸", "大贸", "ERP"];
const CONFIRMATION_WORDS = ["人工确认", "确认", "大额采购", "融资", "税务", "合同", "外发", "真实订单", "采购"];

function safeRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : {};
}

function safeArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeNumber(value: unknown, fallback: number) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function textArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(safeText).filter(Boolean);
  return safeText(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeLimit(value: unknown) {
  return Math.max(1, Math.min(safeNumber(value, 300), 1000));
}

function slug(value: string) {
  const normalized = value
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^a-zA-Z0-9\u4e00-\u9fff_.:/\\-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (normalized || String(value.length)).slice(0, 96).toLowerCase();
}

function nodeId(type: EvidenceGraphNodeType, key: string) {
  return `${type}:${slug(key)}`;
}

function edgeId(type: EvidenceGraphEdgeType, source: string, target: string) {
  return `${type}:${source}->${target}`;
}

function redactSensitiveText(value: string, fallback = "Sensitive evidence") {
  let text = safeText(value);
  if (!text) return "";
  text = text.replace(/1[3-9]\d{9}/g, "***REDACTED_PHONE***");
  text = text.replace(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g, "***REDACTED_EMAIL***");
  text = text.replace(/(身份证|id_card|ID)[：:=]?\s*[0-9Xx]{8,}/gi, "$1: ***REDACTED_ID***");
  text = text.replace(/(地址|收货地址)[：:=]?\s*[^,，;；\n]{4,}/g, "$1: ***REDACTED_ADDRESS***");
  text = text.replace(/(采购价|采购单价|进价|成本价|供应商报价)[：:=]?\s*\d+(?:\.\d+)?/g, "$1: ***REDACTED_PRICE***");
  if (text.includes("***REDACTED_") && text.length > 120) return fallback;
  return text.slice(0, 160);
}

function riskLevelFromText(value: string) {
  if (/(手机号|电话|地址|身份证)/.test(value)) return "high";
  if (/(采购价|采购单价|进价|成本价|毛利|利润|现金流)/.test(value)) return "medium";
  if (/(风险|缺失|失败|人工确认|确认)/.test(value)) return "medium";
  return "";
}

function classifyFieldName(field: string, samples: string[] = []): SensitiveCategory {
  const haystack = [field, ...samples].join(" ").toLowerCase();
  if (/(手机号|手机|电话|地址|收货地址|身份证|id_card|phone|mobile|address)/i.test(haystack)) {
    return "customer_pii";
  }
  if (/(采购价|采购单价|进价|成本价|供应商报价|purchase|cost_price)/i.test(haystack)) {
    return "procurement_price";
  }
  if (/(毛利|利润|现金流|应收|应付|finance|profit|cash)/i.test(haystack)) {
    return "finance";
  }
  return "";
}

function isNodeType(value: string): value is EvidenceGraphNodeType {
  return NODE_TYPE_SET.has(value);
}

function isEdgeType(value: string): value is EvidenceGraphEdgeType {
  return EDGE_TYPE_SET.has(value);
}

function pathToFileHref(pathValue: string) {
  if (!pathValue.startsWith("/")) return "";
  return `file://${pathValue.split("/").map(encodeURIComponent).join("/")}`;
}

function pathIsAtOrInside(parent: string, candidate: string) {
  const relative = path.relative(path.resolve(parent), path.resolve(candidate));
  return (
    relative === "" ||
    (Boolean(relative) &&
      !relative.startsWith("..") &&
      !path.isAbsolute(relative))
  );
}

async function realpathIfExists(targetPath: string) {
  try {
    return await realpath(targetPath);
  } catch {
    return path.resolve(targetPath);
  }
}

function resolveProjectPath(pathValue: string, paths: EvidenceGraphResolvedPaths) {
  if (!pathValue) return "";
  if (path.isAbsolute(pathValue)) {
    return pathIsAtOrInside(paths.workspaceDir, pathValue) ? pathValue : "";
  }
  if (pathValue.startsWith("wiki/")) return path.join(paths.workspaceDir, pathValue);
  if (pathValue.startsWith("data/")) return path.join(paths.workspaceDir, pathValue);
  return path.join(paths.workspaceDir, pathValue);
}

function validateTaskId(taskId: string) {
  if (!taskId) return "";
  let decoded = taskId;
  try {
    decoded = decodeURIComponent(taskId);
  } catch {
    throw new Error("taskId 无效");
  }
  if (
    decoded.includes("/") ||
    decoded.includes("\\") ||
    decoded.includes("..") ||
    decoded.includes("\0") ||
    !/^[a-zA-Z0-9\u4e00-\u9fff._-]+$/u.test(decoded)
  ) {
    throw new Error("taskId 无效");
  }
  return decoded.replace(/\.json$/i, "");
}

async function resolveAllowedEvidencePath(
  pathValue: string,
  paths: EvidenceGraphResolvedPaths,
  allowedRoots: string[],
) {
  const candidate = path.isAbsolute(pathValue)
    ? pathValue
    : resolveProjectPath(pathValue, paths);
  if (!candidate) throw new Error("路径超出允许的证据目录");
  const resolvedCandidate = await realpath(candidate);
  const resolvedRoots = await Promise.all(allowedRoots.map(realpathIfExists));
  if (
    !resolvedRoots.some((root) =>
      pathIsAtOrInside(root, resolvedCandidate),
    )
  ) {
    throw new Error("路径超出允许的证据目录");
  }
  return path.resolve(candidate);
}

function relativeReferenceKey(pathValue: string) {
  return pathValue.replaceAll("\\", "/");
}

async function readJson(filePath: string): Promise<JsonRecord | null> {
  try {
    return JSON.parse(await readFile(filePath, "utf8")) as JsonRecord;
  } catch {
    return null;
  }
}

async function readText(filePath: string) {
  try {
    return await readFile(filePath, "utf8");
  } catch {
    return "";
  }
}

async function fileExists(filePath: string) {
  try {
    const file = await stat(filePath);
    return file.isFile();
  } catch {
    return false;
  }
}

async function walkFiles(root: string, predicate: (filePath: string) => boolean): Promise<string[]> {
  try {
    const entries = await readdir(root, { withFileTypes: true });
    const nested = await Promise.all(
      entries.map(async (entry) => {
        const fullPath = path.join(root, entry.name);
        if (entry.isDirectory()) return walkFiles(fullPath, predicate);
        return predicate(fullPath) ? [fullPath] : [];
      }),
    );
    return nested.flat();
  } catch {
    return [];
  }
}

function markdownTitle(content: string, fallback: string) {
  return content.match(/^#\s+(.+)$/m)?.[1]?.trim() || fallback;
}

function excerpt(content: string) {
  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 3)
    .join(" ")
    .slice(0, 160);
}

type EvidenceGraphResolvedPaths = {
  workspaceDir: string;
  dataDir: string;
  wikiDir: string;
  taskDir: string;
  reportsDir: string;
  registryPath: string;
  auditPath: string;
  lightragIndexPath: string;
};

function resolvePaths(options: LoadEvidenceGraphOptions): EvidenceGraphResolvedPaths {
  const workspaceDir = options.workspaceDir
    ? path.resolve(options.workspaceDir)
    : path.resolve(process.cwd(), "..");
  const dataDir = options.dataDir
    ? path.resolve(options.dataDir)
    : process.env.A2A_DATA_DIR
      ? path.resolve(process.env.A2A_DATA_DIR)
      : path.join(workspaceDir, "data");
  const wikiDir = options.wikiDir
    ? path.resolve(options.wikiDir)
    : process.env.A2A_WIKI_DIR
      ? path.resolve(process.env.A2A_WIKI_DIR)
      : path.join(workspaceDir, "wiki");
  const taskDir = options.taskDir
    ? path.resolve(options.taskDir)
    : process.env.A2A_TASK_DIR
      ? path.resolve(process.env.A2A_TASK_DIR)
      : path.join(dataDir, "tasks");
  const registryPath = options.registryPath
    ? path.resolve(options.registryPath)
    : process.env.A2A_DATASET_REGISTRY
      ? path.resolve(process.env.A2A_DATASET_REGISTRY)
      : path.join(dataDir, "warehouse", "dataset_registry.json");
  const auditPath = options.auditPath
    ? path.resolve(options.auditPath)
    : process.env.A2A_AUDIT_LOG
      ? path.resolve(process.env.A2A_AUDIT_LOG)
      : path.join(dataDir, "audit", "events.jsonl");
  return {
    workspaceDir,
    dataDir,
    wikiDir,
    taskDir,
    registryPath,
    auditPath,
    reportsDir: options.reportsDir ? path.resolve(options.reportsDir) : path.join(dataDir, "reports"),
    lightragIndexPath: options.lightragIndexPath
      ? path.resolve(options.lightragIndexPath)
      : path.join(dataDir, "lightrag", "index.json"),
  };
}

class EvidenceGraphBuilder {
  nodes = new Map<string, EvidenceGraphNode>();
  edges = new Map<string, EvidenceGraphEdge>();
  warnings: string[] = [];

  addNode(
    type: EvidenceGraphNodeType,
    key: string,
    label: string,
    options: Partial<Omit<EvidenceGraphNode, "id" | "type" | "label">> = {},
  ) {
    const id = nodeId(type, key);
    const metadata = safeRecord(options.metadata);
    const sensitiveCategory = safeText(metadata.sensitive_category);
    const safeLabel =
      type === "field" && sensitiveCategory
        ? `Sensitive field: ${sensitiveCategory}`
        : redactSensitiveText(label, `${type} evidence`) || type;
    const nextNode: EvidenceGraphNode = {
      id,
      type,
      label: safeLabel,
      source_path: safeText(options.source_path),
      summary: redactSensitiveText(safeText(options.summary)),
      risk_level: safeText(options.risk_level) || riskLevelFromText(`${label} ${safeText(options.summary)}`),
      metadata,
    };
    const existing = this.nodes.get(id);
    if (!existing) {
      this.nodes.set(id, nextNode);
      return id;
    }
    existing.source_path ||= nextNode.source_path;
    existing.summary ||= nextNode.summary;
    existing.risk_level ||= nextNode.risk_level;
    existing.metadata = { ...nextNode.metadata, ...existing.metadata };
    return id;
  }

  addEdge(
    type: EvidenceGraphEdgeType,
    source: string,
    target: string,
    label: string,
    options: Partial<Omit<EvidenceGraphEdge, "id" | "type" | "source" | "target" | "label">> = {},
  ) {
    if (!source || !target || source === target) return "";
    const id = edgeId(type, source, target);
    const nextEdge: EvidenceGraphEdge = {
      id,
      type,
      source,
      target,
      label: redactSensitiveText(label) || type,
      source_path: safeText(options.source_path),
      summary: redactSensitiveText(safeText(options.summary)),
      risk_level: safeText(options.risk_level) || riskLevelFromText(`${label} ${safeText(options.summary)}`),
      metadata: safeRecord(options.metadata),
    };
    const existing = this.edges.get(id);
    if (!existing) {
      this.edges.set(id, nextEdge);
      return id;
    }
    existing.source_path ||= nextEdge.source_path;
    existing.summary ||= nextEdge.summary;
    existing.risk_level ||= nextEdge.risk_level;
    existing.metadata = { ...nextEdge.metadata, ...existing.metadata };
    return id;
  }

  toState(options: {
    paths: EvidenceGraphResolvedPaths;
    scope: string;
    taskId: string;
    reportPath: string;
    nodeTypes: string[];
    edgeTypes: string[];
    limit: number;
  }): EvidenceGraphState {
    const nodeTypeFilter = new Set(options.nodeTypes.filter(isNodeType));
    const edgeTypeFilter = new Set(options.edgeTypes.filter(isEdgeType));
    const sortedNodes = [...this.nodes.values()].sort((left, right) =>
      `${left.type}:${left.label}`.localeCompare(`${right.type}:${right.label}`, "zh-CN"),
    );
    const filteredNodes = sortedNodes.filter((node) => !nodeTypeFilter.size || nodeTypeFilter.has(node.type));
    const nodes = filteredNodes.slice(0, options.limit);
    const nodeIds = new Set(nodes.map((node) => node.id));
    const sortedEdges = [...this.edges.values()].sort((left, right) =>
      `${left.type}:${left.label}`.localeCompare(`${right.type}:${right.label}`, "zh-CN"),
    );
    const filteredEdges = sortedEdges.filter((edge) => {
      if (edgeTypeFilter.size && !edgeTypeFilter.has(edge.type)) return false;
      return nodeIds.has(edge.source) && nodeIds.has(edge.target);
    });
    const edges = filteredEdges.slice(0, options.limit);
    return {
      schema: EVIDENCE_GRAPH_SCHEMA,
      generated_at: new Date().toISOString(),
      scope: options.scope,
      source_files: {
        workspace_dir: options.paths.workspaceDir,
        data_dir: options.paths.dataDir,
        wiki_dir: options.paths.wikiDir,
        task_dir: options.paths.taskDir,
        reports_dir: options.paths.reportsDir,
        registry_path: options.paths.registryPath,
        audit_path: options.paths.auditPath,
        lightrag_index_path: options.paths.lightragIndexPath,
      },
      filters: {
        task_id: options.taskId,
        report_path: options.reportPath,
        node_types: options.nodeTypes,
        edge_types: options.edgeTypes,
        limit: options.limit,
      },
      counts: {
        nodes: nodes.length,
        edges: edges.length,
        truncated: filteredNodes.length > nodes.length || filteredEdges.length > edges.length,
      },
      nodes,
      edges,
      warnings: [...new Set(this.warnings)],
    };
  }
}

function datasetEntries(value: unknown): Array<[string, JsonRecord]> {
  if (Array.isArray(value)) {
    return value.map((item, index) => {
      const record = safeRecord(item);
      return [safeText(record.dataset_slug) || safeText(record.slug) || `dataset_${index + 1}`, record];
    });
  }
  return Object.entries(safeRecord(value)).map(([key, item]) => [key, safeRecord(item)]);
}

function sampleValues(profile: JsonRecord) {
  return [
    ...textArray(profile.sample_values),
    ...textArray(profile.samples),
    ...textArray(profile.example_values),
  ];
}

function firstUsefulSample(samples: string[]) {
  return samples.find((sample) => sample.length > 0 && sample.length <= 80) || "";
}

function addEntityForField(
  builder: EvidenceGraphBuilder,
  datasetId: string,
  field: string,
  samples: string[],
  sourcePath: string,
) {
  const haystack = [field, ...samples].join(" ");
  const sample = firstUsefulSample(samples);
  let nodeType: EvidenceGraphNodeType | "" = "";
  let label = sample;
  if (/(^|[^a-z])品牌|brand/i.test(field)) {
    nodeType = "brand";
    label = sample || KNOWN_BRANDS.find((brand) => haystack.includes(brand)) || "Brand";
  } else if (/渠道|店铺|平台|channel|platform/i.test(field)) {
    nodeType = "channel";
    label = sample || CHANNEL_KEYWORDS.find((channel) => haystack.includes(channel)) || "Channel";
  } else if (/sku|货号|商品编码|SKU编码/i.test(field)) {
    nodeType = "sku";
    label = sample || field;
  } else if (/仓库|warehouse/i.test(field)) {
    nodeType = "warehouse";
    label = sample || field;
  } else if (/供应商|supplier/i.test(field)) {
    nodeType = "supplier";
    label = sample || field;
  }
  if (nodeType) {
    const entityId = builder.addNode(nodeType, label, label, {
      source_path: sourcePath,
      summary: `${field} belongs to dataset evidence.`,
    });
    builder.addEdge("belongs_to", entityId, datasetId, `${label} belongs to dataset`, {
      source_path: sourcePath,
    });
  }

  const category = classifyFieldName(field, samples);
  if (category) {
    const fieldId = builder.addNode("field", `${category}:${field}`, field, {
      source_path: sourcePath,
      summary: "Sensitive field is available only as aggregate evidence.",
      risk_level: category === "customer_pii" ? "high" : "medium",
      metadata: { sensitive_category: category },
    });
    builder.addEdge("uses_sensitive_field", datasetId, fieldId, "uses sensitive aggregate field", {
      source_path: sourcePath,
      risk_level: category === "customer_pii" ? "high" : "medium",
      metadata: { sensitive_category: category },
    });
  }
}

function addBusinessEntitiesFromText(
  builder: EvidenceGraphBuilder,
  sourceId: string,
  sourcePath: string,
  text: string,
  edgeType: EvidenceGraphEdgeType = "affects",
) {
  for (const brand of KNOWN_BRANDS) {
    if (text.toLowerCase().includes(brand.toLowerCase())) {
      const brandId = builder.addNode("brand", brand, brand, { source_path: sourcePath });
      builder.addEdge(edgeType, sourceId, brandId, `${edgeType} ${brand}`, { source_path: sourcePath });
    }
  }
  for (const channel of CHANNEL_KEYWORDS) {
    if (text.includes(channel)) {
      const channelId = builder.addNode("channel", channel, channel, { source_path: sourcePath });
      builder.addEdge(edgeType, sourceId, channelId, `${edgeType} ${channel}`, { source_path: sourcePath });
    }
  }
}

async function addReferenceNodeForPath(
  builder: EvidenceGraphBuilder,
  referencePath: string,
  paths: EvidenceGraphResolvedPaths,
) {
  const sourcePath = resolveProjectPath(referencePath, paths);
  const key = relativeReferenceKey(referencePath);
  const lower = key.toLowerCase();
  if (lower.includes("wiki/decisions/") || lower.includes("/decisions/")) {
    const content = await readText(sourcePath);
    return builder.addNode("decision", key, markdownTitle(content, path.basename(referencePath)), {
      source_path: sourcePath,
      summary: excerpt(content),
    });
  }
  if (lower.includes("wiki/") || lower.endsWith(".md")) {
    const content = await readText(sourcePath);
    return builder.addNode("wiki_page", key, markdownTitle(content, path.basename(referencePath)), {
      source_path: sourcePath,
      summary: excerpt(content),
    });
  }
  if (lower.includes("/reports/") || lower.includes("data/reports/")) {
    const content = await readText(sourcePath);
    return builder.addNode("report", sourcePath, markdownTitle(content, path.basename(referencePath)), {
      source_path: sourcePath,
      summary: excerpt(content),
    });
  }
  if (lower.includes("duckdb") || lower.includes("mart") || lower.includes("warehouse")) {
    return builder.addNode("mart", key, path.basename(referencePath) || referencePath, {
      source_path: sourcePath,
      summary: "DuckDB or mart evidence reference.",
    });
  }
  return builder.addNode("field", key, referencePath, {
    source_path: sourcePath,
    summary: "Data gap or field-level evidence reference.",
  });
}

async function addRegistry(builder: EvidenceGraphBuilder, paths: EvidenceGraphResolvedPaths) {
  const registry = await readJson(paths.registryPath);
  if (!registry) {
    builder.warnings.push(`Dataset registry missing or invalid: ${paths.registryPath}`);
    return;
  }
  for (const [key, dataset] of datasetEntries(registry.datasets)) {
    const slugValue = safeText(dataset.dataset_slug) || safeText(dataset.slug) || key;
    const datasetId = builder.addNode("dataset", slugValue, slugValue, {
      source_path: paths.registryPath,
      summary: safeText(dataset.relative_source) || safeText(dataset.source),
      metadata: { dataset_slug: slugValue },
    });
    const wikiPages = safeRecord(dataset.wiki_pages);
    for (const [kind, value] of Object.entries(wikiPages)) {
      for (const reference of textArray(value)) {
        const targetId = await addReferenceNodeForPath(builder, reference, paths);
        builder.addEdge("references", datasetId, targetId, `${slugValue} references ${kind}`, {
          source_path: paths.registryPath,
          metadata: { registry_key: kind },
        });
      }
    }
    for (const mart of safeArray<JsonRecord>(dataset.mart_views)) {
      const martName = safeText(mart.view_name) || safeText(mart.name) || safeText(mart.category);
      if (!martName) continue;
      const martId = builder.addNode("mart", martName, martName, {
        source_path: paths.registryPath,
        summary: safeText(mart.category),
        metadata: { source_view: safeText(mart.source_view) },
      });
      builder.addEdge("derived_from", martId, datasetId, `${martName} derived from ${slugValue}`, {
        source_path: paths.registryPath,
      });
    }
    for (const sheet of safeArray<JsonRecord>(dataset.sheet_views)) {
      for (const field of textArray(sheet.headers)) {
        addEntityForField(builder, datasetId, field, [], paths.registryPath);
      }
      for (const profile of safeArray<JsonRecord>(sheet.field_profiles)) {
        addEntityForField(builder, datasetId, safeText(profile.field), sampleValues(profile), paths.registryPath);
      }
    }
  }
}

async function addWikiPages(builder: EvidenceGraphBuilder, paths: EvidenceGraphResolvedPaths) {
  const markdownFiles = await walkFiles(paths.wikiDir, (filePath) => filePath.endsWith(".md"));
  for (const filePath of markdownFiles) {
    const content = await readText(filePath);
    const relativePath = path.relative(paths.workspaceDir, filePath);
    const type: EvidenceGraphNodeType = filePath.includes(`${path.sep}decisions${path.sep}`)
      ? "decision"
      : "wiki_page";
    const nodeIdValue = builder.addNode(type, relativePath, markdownTitle(content, path.basename(filePath)), {
      source_path: filePath,
      summary: excerpt(content),
    });
    addBusinessEntitiesFromText(builder, nodeIdValue, filePath, content, type === "decision" ? "affects" : "references");
    if (CONFIRMATION_WORDS.some((word) => content.includes(word))) {
      const riskId = builder.addNode("risk", `${relativePath}:confirmation`, "Needs human confirmation", {
        source_path: filePath,
        summary: "Wiki or decision page mentions human confirmation.",
        risk_level: "medium",
      });
      builder.addEdge("needs_confirmation", nodeIdValue, riskId, "needs confirmation", {
        source_path: filePath,
        risk_level: "medium",
      });
    }
  }
}

function extractBacktickPaths(content: string) {
  return [...content.matchAll(/`([^`]+)`/g)]
    .map((match) => match[1]?.trim() || "")
    .filter((item) => item.includes("/") || item.includes("\\"));
}

function extractMissingData(content: string) {
  const items: string[] = [];
  for (const line of content.split(/\r?\n/)) {
    if (!/missing data|data gap|数据缺口|缺失/i.test(line)) continue;
    const [, tail = line] = line.split(/:|：/, 2);
    items.push(
      ...tail
        .split(/[,，、]/)
        .map((item) => item.replace(/[-*`]/g, "").trim())
        .filter(Boolean),
    );
  }
  return items;
}

async function addReportFile(builder: EvidenceGraphBuilder, paths: EvidenceGraphResolvedPaths, reportPath: string) {
  const fullPath = await resolveAllowedEvidencePath(reportPath, paths, [
    paths.reportsDir,
    path.join(paths.wikiDir, "decisions"),
    path.join(paths.wikiDir, "datasets"),
  ]);
  if (!(await fileExists(fullPath))) return "";
  const content = await readText(fullPath);
  const reportId = builder.addNode("report", fullPath, markdownTitle(content, path.basename(fullPath)), {
    source_path: fullPath,
    summary: excerpt(content),
  });
  addBusinessEntitiesFromText(builder, reportId, fullPath, content, "affects");
  for (const reference of extractBacktickPaths(content)) {
    const targetId = await addReferenceNodeForPath(builder, reference, paths);
    builder.addEdge("references", reportId, targetId, "report references evidence", {
      source_path: fullPath,
    });
  }
  for (const gap of extractMissingData(content)) {
    const fieldId = builder.addNode("field", `data_gap:${gap}`, `Data gap: ${gap}`, {
      source_path: fullPath,
      summary: "Report evidence chain marks this as a missing field.",
      risk_level: "medium",
    });
    builder.addEdge("needs_confirmation", reportId, fieldId, "data gap needs confirmation", {
      source_path: fullPath,
      risk_level: "medium",
    });
  }
  if (CONFIRMATION_WORDS.some((word) => content.includes(word))) {
    const riskId = builder.addNode("risk", `${fullPath}:confirmation`, "Needs human confirmation", {
      source_path: fullPath,
      summary: "Report contains confirmation-sensitive actions.",
      risk_level: "medium",
    });
    builder.addEdge("has_risk", reportId, riskId, "report has confirmation risk", {
      source_path: fullPath,
      risk_level: "medium",
    });
  }
  return reportId;
}

async function addReports(builder: EvidenceGraphBuilder, paths: EvidenceGraphResolvedPaths, reportPath: string) {
  if (reportPath) {
    await addReportFile(builder, paths, reportPath);
    return;
  }
  const reportFiles = await walkFiles(paths.reportsDir, (filePath) => /\.(md|txt|json)$/i.test(filePath));
  for (const filePath of reportFiles.slice(0, 200)) {
    await addReportFile(builder, paths, filePath);
  }
}

async function addTaskFile(builder: EvidenceGraphBuilder, paths: EvidenceGraphResolvedPaths, taskPath: string) {
  const task = await readJson(taskPath);
  if (!task) return;
  const taskId = safeText(task.task_id) || path.basename(taskPath, ".json");
  const goal = safeText(task.goal) || taskId;
  const decisionId = builder.addNode("decision", taskId, goal, {
    source_path: taskPath,
    summary: safeText(task.status),
    risk_level: riskLevelFromText(goal),
    metadata: { task_id: taskId },
  });
  addBusinessEntitiesFromText(builder, decisionId, taskPath, goal, "affects");

  const finalReport = safeRecord(task.final_report);
  const savedTo = safeText(finalReport.saved_to);
  if (savedTo) {
    const reportId = await addReportFile(builder, paths, savedTo);
    if (reportId) {
      builder.addEdge("summarizes", reportId, decisionId, "report summarizes task decision", {
        source_path: taskPath,
        metadata: { task_id: taskId },
      });
    }
  }
  const evidenceChain = safeRecord(finalReport.evidence_chain);
  for (const reference of [
    ...textArray(evidenceChain.wiki_pages),
    ...textArray(evidenceChain.report_paths),
  ]) {
    const targetId = await addReferenceNodeForPath(builder, reference, paths);
    builder.addEdge("references", decisionId, targetId, "task decision references evidence", {
      source_path: taskPath,
      metadata: { task_id: taskId },
    });
  }
  for (const mart of safeArray<JsonRecord>(evidenceChain.duckdb_marts)) {
    const martName = safeText(mart.mart) || safeText(mart.name);
    if (!martName) continue;
    const martId = builder.addNode("mart", martName, martName, {
      source_path: taskPath,
      summary: textArray(mart.fields).join(", "),
    });
    builder.addEdge("references", decisionId, martId, "task decision references mart", {
      source_path: taskPath,
      metadata: { task_id: taskId },
    });
  }
  for (const gap of textArray(evidenceChain.data_gaps)) {
    const fieldId = builder.addNode("field", `data_gap:${gap}`, `Data gap: ${gap}`, {
      source_path: taskPath,
      summary: "Task evidence chain marks this as missing data.",
      risk_level: "medium",
    });
    builder.addEdge("needs_confirmation", decisionId, fieldId, "data gap needs confirmation", {
      source_path: taskPath,
      risk_level: "medium",
      metadata: { task_id: taskId },
    });
  }

  for (const step of safeArray<JsonRecord>(task.steps)) {
    const stepText = [safeText(step.task), safeText(step.summary)].join(" ");
    addBusinessEntitiesFromText(builder, decisionId, taskPath, stepText, "affects");
    for (const evidence of textArray(step.evidence)) {
      const targetId = await addReferenceNodeForPath(builder, evidence, paths);
      builder.addEdge("references", decisionId, targetId, "task step references evidence", {
        source_path: taskPath,
        metadata: { task_id: taskId, step: safeText(step.task) },
      });
    }
    for (const risk of textArray(step.risks)) {
      const riskId = builder.addNode("risk", `${taskId}:${risk}`, risk, {
        source_path: taskPath,
        summary: safeText(step.summary),
        risk_level: riskLevelFromText(risk) || "medium",
        metadata: { task_id: taskId, step: safeText(step.task) },
      });
      builder.addEdge("has_risk", decisionId, riskId, "task has risk", {
        source_path: taskPath,
        risk_level: riskLevelFromText(risk) || "medium",
        metadata: { task_id: taskId, step: safeText(step.task) },
      });
      if (CONFIRMATION_WORDS.some((word) => risk.includes(word))) {
        builder.addEdge("needs_confirmation", decisionId, riskId, "risk needs confirmation", {
          source_path: taskPath,
          risk_level: "medium",
          metadata: { task_id: taskId, step: safeText(step.task) },
        });
      }
    }
    for (const missing of textArray(step.missing_data)) {
      const fieldId = builder.addNode("field", `data_gap:${missing}`, `Data gap: ${missing}`, {
        source_path: taskPath,
        summary: "Task step marks this as missing data.",
        risk_level: "medium",
      });
      builder.addEdge("needs_confirmation", decisionId, fieldId, "step missing data needs confirmation", {
        source_path: taskPath,
        risk_level: "medium",
        metadata: { task_id: taskId, step: safeText(step.task) },
      });
    }
  }
}

async function addTasks(builder: EvidenceGraphBuilder, paths: EvidenceGraphResolvedPaths, taskId: string) {
  if (taskId) {
    const safeTaskId = validateTaskId(taskId);
    await addTaskFile(builder, paths, path.join(paths.taskDir, `${safeTaskId}.json`));
    return;
  }
  const taskFiles = await walkFiles(paths.taskDir, (filePath) => filePath.endsWith(".json"));
  for (const taskPath of taskFiles.slice(0, 200)) {
    await addTaskFile(builder, paths, taskPath);
  }
}

async function addAudit(builder: EvidenceGraphBuilder, paths: EvidenceGraphResolvedPaths, taskId: string) {
  const content = await readText(paths.auditPath);
  if (!content) return;
  for (const [index, line] of content.split(/\r?\n/).entries()) {
    if (!line.trim()) continue;
    let event: JsonRecord;
    try {
      event = safeRecord(JSON.parse(line));
    } catch {
      builder.warnings.push(`审计 JSON 第 ${index + 1} 行无效`);
      continue;
    }
    const eventTaskId = safeText(event.task_id) || safeText(safeRecord(event.metadata).task_id);
    if (taskId && eventTaskId !== taskId) continue;
    const eventId = `audit:${index + 1}`;
    const sourceNode = builder.addNode("decision", eventTaskId || eventId, eventTaskId || safeText(event.event_type) || eventId, {
      source_path: paths.auditPath,
      summary: safeText(event.summary),
      risk_level: safeText(event.risk_level),
      metadata: { task_id: eventTaskId, audit_line: index + 1 },
    });
    for (const risk of textArray(event.risks)) {
      const riskId = builder.addNode("risk", `${eventId}:${risk}`, risk, {
        source_path: paths.auditPath,
        summary: safeText(event.summary),
        risk_level: safeText(event.risk_level) || riskLevelFromText(risk),
        metadata: { task_id: eventTaskId, audit_line: index + 1 },
      });
      builder.addEdge("has_risk", sourceNode, riskId, "audit event has risk", {
        source_path: paths.auditPath,
        risk_level: safeText(event.risk_level) || riskLevelFromText(risk),
        metadata: { task_id: eventTaskId, audit_line: index + 1 },
      });
    }
    const metadata = safeRecord(event.metadata);
    for (const field of textArray(metadata.fields)) {
      const category = classifyFieldName(field);
      const fieldId = builder.addNode("field", `${category || "sensitive"}:${field}`, field, {
        source_path: paths.auditPath,
        summary: "Audit event touched a sensitive field category.",
        risk_level: category === "customer_pii" ? "high" : "medium",
        metadata: { sensitive_category: category || safeText(metadata.category) || "sensitive" },
      });
      builder.addEdge("uses_sensitive_field", sourceNode, fieldId, "audit uses sensitive field", {
        source_path: paths.auditPath,
        risk_level: category === "customer_pii" ? "high" : "medium",
        metadata: { task_id: eventTaskId, audit_line: index + 1 },
      });
    }
  }
}

async function addLightRagIndex(builder: EvidenceGraphBuilder, paths: EvidenceGraphResolvedPaths) {
  const index = await readJson(paths.lightragIndexPath);
  if (!index) return;
  for (const doc of safeArray<JsonRecord>(index.docs) || safeArray<JsonRecord>(index.documents)) {
    const docPath = safeText(doc.path) || safeText(doc.file_path) || safeText(doc.source_path);
    if (!docPath) continue;
    const docId = await addReferenceNodeForPath(builder, docPath, paths);
    addBusinessEntitiesFromText(builder, docId, resolveProjectPath(docPath, paths), safeText(doc.title) || safeText(doc.summary), "references");
  }
  for (const entity of safeArray<JsonRecord>(index.entities)) {
    const name = safeText(entity.name) || safeText(entity.entity);
    const typeText = safeText(entity.type).toLowerCase();
    if (!name) continue;
    const type: EvidenceGraphNodeType = typeText.includes("sku")
      ? "sku"
      : typeText.includes("channel")
        ? "channel"
        : "brand";
    builder.addNode(type, name, name, {
      source_path: paths.lightragIndexPath,
      summary: safeText(entity.description) || "LightRAG entity reference.",
    });
  }
}

export async function loadEvidenceGraphState(
  options: LoadEvidenceGraphOptions = {},
): Promise<EvidenceGraphState> {
  const paths = resolvePaths(options);
  const scope = safeText(options.scope) || "global";
  const taskId = validateTaskId(safeText(options.taskId) || safeText(options.task_id));
  const reportPath = safeText(options.reportPath) || safeText(options.report_path);
  const limit = normalizeLimit(options.limit);
  const builder = new EvidenceGraphBuilder();

  await addRegistry(builder, paths);
  await addWikiPages(builder, paths);
  if (scope === "report") {
    await addReports(builder, paths, reportPath);
  } else {
    await addReports(builder, paths, "");
  }
  if (scope === "task") {
    await addTasks(builder, paths, taskId);
  } else {
    await addTasks(builder, paths, "");
  }
  await addAudit(builder, paths, scope === "task" ? taskId : "");
  await addLightRagIndex(builder, paths);

  return builder.toState({
    paths,
    scope,
    taskId,
    reportPath,
    nodeTypes: options.nodeTypes ?? [],
    edgeTypes: options.edgeTypes ?? [],
    limit,
  });
}

export async function listEvidenceGraphNodes(options: LoadEvidenceGraphOptions = {}) {
  const graph = await loadEvidenceGraphState(options);
  return {
    schema: graph.schema,
    generated_at: graph.generated_at,
    filters: graph.filters,
    counts: graph.counts,
    nodes: graph.nodes,
    warnings: graph.warnings,
  };
}

export async function listEvidenceGraphEdges(options: LoadEvidenceGraphOptions = {}) {
  const graph = await loadEvidenceGraphState(options);
  return {
    schema: graph.schema,
    generated_at: graph.generated_at,
    filters: graph.filters,
    counts: graph.counts,
    edges: graph.edges,
    warnings: graph.warnings,
  };
}

export function evidenceNodeHref(node: EvidenceGraphNode) {
  const taskId = safeText(node.metadata.task_id);
  if (taskId && node.type === "decision") return `/tasks/${encodeURIComponent(taskId)}`;
  if (node.type === "dataset" || node.type === "mart" || node.type === "field") {
    return "/data-health";
  }
  if ((node.type === "report" || node.type === "wiki_page" || node.type === "decision") && node.source_path) {
    return pathToFileHref(node.source_path);
  }
  return "";
}
