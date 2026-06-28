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

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function pathToFileHref(pathValue: string) {
  if (!pathValue.startsWith("/")) return "";
  return `file://${pathValue.split("/").map(encodeURIComponent).join("/")}`;
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
