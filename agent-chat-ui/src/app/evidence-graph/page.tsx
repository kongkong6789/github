"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  DatabaseZap,
  ExternalLink,
  FileText,
  Filter,
  GitBranch,
  LoaderCircle,
  Network,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { WorkbenchShell } from "@/components/workbench/shell";
import {
  EVIDENCE_GRAPH_NODE_TYPES,
  evidenceNodeHref,
  type EvidenceGraphEdge,
  type EvidenceGraphNode,
  type EvidenceGraphNodeType,
  type EvidenceGraphState,
} from "@/lib/evidence-graph-shared";
import { cn } from "@/lib/utils";
import { getWorkbenchEvidenceGraph } from "@/lib/workbench-client";

const NODE_TYPE_LABELS: Record<EvidenceGraphNodeType, string> = {
  brand: "品牌",
  channel: "渠道",
  sku: "SKU",
  warehouse: "仓库",
  supplier: "供应商",
  dataset: "数据集",
  mart: "Mart",
  wiki_page: "Wiki",
  report: "报告",
  decision: "决策",
  risk: "风险",
  field: "字段",
};

const NODE_TYPE_CLASS: Record<EvidenceGraphNodeType, string> = {
  brand: "border-emerald-200 bg-emerald-50 text-emerald-700",
  channel: "border-cyan-200 bg-cyan-50 text-cyan-700",
  sku: "border-sky-200 bg-sky-50 text-sky-700",
  warehouse: "border-slate-200 bg-slate-50 text-slate-700",
  supplier: "border-violet-200 bg-violet-50 text-violet-700",
  dataset: "border-blue-200 bg-blue-50 text-blue-700",
  mart: "border-indigo-200 bg-indigo-50 text-indigo-700",
  wiki_page: "border-teal-200 bg-teal-50 text-teal-700",
  report: "border-amber-200 bg-amber-50 text-amber-700",
  decision: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700",
  risk: "border-rose-200 bg-rose-50 text-rose-700",
  field: "border-gray-200 bg-gray-50 text-gray-700",
};

const EDGE_TYPE_LABELS: Record<string, string> = {
  derived_from: "来源",
  summarizes: "汇总",
  references: "引用",
  affects: "影响",
  belongs_to: "归属",
  has_risk: "风险",
  needs_confirmation: "需确认",
  uses_sensitive_field: "敏感字段",
};

const LAYERS: Array<{ key: string; title: string; types: EvidenceGraphNodeType[] }> = [
  { key: "business", title: "经营对象", types: ["brand", "channel", "sku", "warehouse", "supplier"] },
  { key: "evidence", title: "资料与报告", types: ["dataset", "mart", "wiki_page", "report"] },
  { key: "decision", title: "决策与风险", types: ["decision", "risk", "field"] },
];

function formatTime(value: string) {
  if (!value) return "-";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(parsed));
}

function riskClass(value: string) {
  if (value === "high") return "border-rose-300 bg-rose-50 text-rose-800";
  if (value === "medium") return "border-amber-300 bg-amber-50 text-amber-800";
  return "border-gray-200 bg-white text-gray-700";
}

function nodeTypeBadge(type: EvidenceGraphNodeType) {
  return (
    <span className={cn("inline-flex w-fit rounded border px-1.5 py-0.5 text-xs font-medium", NODE_TYPE_CLASS[type])}>
      {NODE_TYPE_LABELS[type]}
    </span>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-gray-950">{value}</div>
    </div>
  );
}

function NodeLink({ node }: { node: EvidenceGraphNode }) {
  const href = evidenceNodeHref(node);
  if (!href) return <span className="break-words">{node.label}</span>;
  if (href.startsWith("/")) {
    return (
      <Link className="inline-flex items-center gap-1 break-words font-medium text-blue-700 hover:underline" href={href}>
        {node.label}
        <ExternalLink className="size-3" />
      </Link>
    );
  }
  return (
    <a className="inline-flex items-center gap-1 break-words font-medium text-blue-700 hover:underline" href={href} target="_blank" rel="noreferrer">
      {node.label}
      <ExternalLink className="size-3" />
    </a>
  );
}

function EdgeRow({
  edge,
  nodeById,
}: {
  edge: EvidenceGraphEdge;
  nodeById: Map<string, EvidenceGraphNode>;
}) {
  const source = nodeById.get(edge.source);
  const target = nodeById.get(edge.target);
  return (
    <div className="grid gap-2 border-b border-gray-100 px-3 py-2 text-sm last:border-b-0 md:grid-cols-[1fr_120px_1fr]">
      <div className="min-w-0">
        {source ? <NodeLink node={source} /> : <span className="break-all font-mono text-xs">{edge.source}</span>}
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <GitBranch className="size-3.5" />
        <span className="rounded bg-gray-100 px-1.5 py-0.5">{EDGE_TYPE_LABELS[edge.type] ?? edge.type}</span>
      </div>
      <div className="min-w-0">
        {target ? <NodeLink node={target} /> : <span className="break-all font-mono text-xs">{edge.target}</span>}
      </div>
    </div>
  );
}

export default function EvidenceGraphPage() {
  const [graph, setGraph] = useState<EvidenceGraphState | null>(null);
  const [activeTypes, setActiveTypes] = useState<EvidenceGraphNodeType[]>([...EVIDENCE_GRAPH_NODE_TYPES]);
  const [taskId, setTaskId] = useState("");
  const [reportPath, setReportPath] = useState("");
  const [initialized, setInitialized] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const nodeById = useMemo(() => new Map((graph?.nodes ?? []).map((node) => [node.id, node])), [graph]);
  const countsByType = useMemo(() => {
    const counts = new Map<EvidenceGraphNodeType, number>();
    for (const node of graph?.nodes ?? []) counts.set(node.type, (counts.get(node.type) ?? 0) + 1);
    return counts;
  }, [graph]);
  const highRiskCount = useMemo(
    () => (graph?.nodes ?? []).filter((node) => node.risk_level === "high").length,
    [graph],
  );

  async function load() {
    setLoading(true);
    setError("");
    try {
      const filteredTypes =
        activeTypes.length === EVIDENCE_GRAPH_NODE_TYPES.length ? [] : activeTypes;
      setGraph(
        await getWorkbenchEvidenceGraph({
          scope: taskId ? "task" : reportPath ? "report" : "global",
          taskId,
          reportPath,
          nodeTypes: filteredTypes,
          limit: 360,
        }),
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  function toggleType(type: EvidenceGraphNodeType) {
    setActiveTypes((current) => {
      if (current.includes(type)) {
        return current.length === 1 ? current : current.filter((item) => item !== type);
      }
      return [...current, type];
    });
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const nextTaskId = params.get("taskId") || params.get("task_id") || "";
    const nextReportPath = params.get("reportPath") || params.get("report_path") || "";
    const nextTypes = (params.get("nodeTypes") || params.get("node_types") || "")
      .split(",")
      .map((item) => item.trim())
      .filter((item): item is EvidenceGraphNodeType => EVIDENCE_GRAPH_NODE_TYPES.includes(item as EvidenceGraphNodeType));
    setTaskId(nextTaskId);
    setReportPath(nextReportPath);
    if (nextTypes.length) setActiveTypes(nextTypes);
    setInitialized(true);
  }, []);

  useEffect(() => {
    if (initialized) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialized, taskId, reportPath, activeTypes.join(",")]);

  return (
    <WorkbenchShell
      title="依据来源"
      description={taskId || reportPath || "查看经营对象、资料、报告、决策和风险之间的引用关系。"}
      status={
        <span className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700">
          <Network className="size-3.5" />
          {graph?.scope || "全局"}
        </span>
      }
      actions={
        <>
          <Button
            type="button"
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            onClick={load}
            disabled={loading}
          >
            <RefreshCw className={cn("size-4", loading && "animate-spin")} />
            刷新
          </Button>
          <Button
            asChild
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Link href="/tasks">
              <ArrowLeft className="size-4" />
              工作进度
            </Link>
          </Button>
          <Button
            asChild
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Link href="/data-health">
              <DatabaseZap className="size-4" />
              资料体检
            </Link>
          </Button>
          <Button
            asChild
            className="bg-blue-700 !text-white hover:bg-blue-800"
          >
            <Link href="/">
              <ArrowLeft className="size-4" />
              返回对话
            </Link>
          </Button>
        </>
      }
    >
      <div>

        {error && (
          <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        <section className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Stat label="节点" value={graph?.counts.nodes ?? "-"} />
          <Stat label="关系" value={graph?.counts.edges ?? "-"} />
          <Stat label="高风险" value={highRiskCount} />
          <Stat label="范围" value={graph?.scope || "-"} />
          <Stat label="生成" value={graph ? formatTime(graph.generated_at) : "-"} />
        </section>

        <section className="mb-5 rounded-md border border-gray-200">
          <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
            <div className="flex items-center gap-2 font-semibold">
              <Filter className="size-4 text-gray-500" />
              内容类型
            </div>
            {graph?.counts.truncated && (
              <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
                已截断
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-2 p-3">
            {EVIDENCE_GRAPH_NODE_TYPES.map((type) => {
              const active = activeTypes.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium transition",
                    active ? NODE_TYPE_CLASS[type] : "border-gray-200 bg-white text-gray-500",
                  )}
                  onClick={() => toggleType(type)}
                >
                  {NODE_TYPE_LABELS[type]}
                  <span className="font-mono">{countsByType.get(type) ?? 0}</span>
                </button>
              );
            })}
          </div>
        </section>

        {loading && !graph && (
          <div className="rounded-md border border-gray-200 p-8 text-center text-sm text-gray-500">
            <LoaderCircle className="mx-auto mb-2 size-5 animate-spin" />
            正在读取依据关系...
          </div>
        )}

        {graph && (
          <>
            {graph.warnings.length > 0 && (
              <section className="mb-5 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                {graph.warnings.slice(0, 3).join(" / ")}
              </section>
            )}

            <section className="grid gap-4 lg:grid-cols-3">
              {LAYERS.map((layer) => (
                <div key={layer.key} className="rounded-md border border-gray-200">
                  <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                    <h2 className="font-semibold">{layer.title}</h2>
                    <span className="text-xs text-gray-500">
                      {graph.nodes.filter((node) => layer.types.includes(node.type)).length}
                    </span>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {graph.nodes
                      .filter((node) => layer.types.includes(node.type))
                      .slice(0, 16)
                      .map((node) => (
                        <div key={node.id} className={cn("px-3 py-2 text-sm", node.risk_level && riskClass(node.risk_level))}>
                          <div className="flex flex-wrap items-center gap-2">
                            {nodeTypeBadge(node.type)}
                            {node.risk_level && (
                              <span className="inline-flex items-center gap-1 rounded bg-white/70 px-1.5 py-0.5 text-xs">
                                <ShieldAlert className="size-3" />
                                {node.risk_level}
                              </span>
                            )}
                          </div>
                          <div className="mt-1 min-w-0">
                            <NodeLink node={node} />
                          </div>
                          {node.summary && <div className="mt-1 line-clamp-2 text-xs text-gray-600">{node.summary}</div>}
                        </div>
                      ))}
                    {graph.nodes.filter((node) => layer.types.includes(node.type)).length === 0 && (
                      <div className="px-3 py-6 text-center text-sm text-gray-500">暂无节点</div>
                    )}
                  </div>
                </div>
              ))}
            </section>

            <section className="mt-5 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-md border border-gray-200">
                <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                  <h2 className="font-semibold">关系</h2>
                  <GitBranch className="size-4 text-gray-500" />
                </div>
                <div>
                  {graph.edges.slice(0, 80).map((edge) => (
                    <EdgeRow key={edge.id} edge={edge} nodeById={nodeById} />
                  ))}
                  {graph.edges.length === 0 && (
                    <div className="px-3 py-6 text-center text-sm text-gray-500">暂无关系</div>
                  )}
                </div>
              </div>

              <div className="rounded-md border border-gray-200">
                <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                  <h2 className="font-semibold">风险与确认</h2>
                  <AlertTriangle className="size-4 text-gray-500" />
                </div>
                <div className="divide-y divide-gray-100">
                  {graph.nodes
                    .filter((node) => node.type === "risk" || node.risk_level)
                    .slice(0, 30)
                    .map((node) => (
                      <div key={node.id} className={cn("px-3 py-2 text-sm", riskClass(node.risk_level))}>
                        <div className="flex flex-wrap items-center gap-2">
                          {nodeTypeBadge(node.type)}
                          <span className="rounded bg-white/70 px-1.5 py-0.5 text-xs">{node.risk_level || "risk"}</span>
                        </div>
                        <div className="mt-1">
                          <NodeLink node={node} />
                        </div>
                        {node.summary && <div className="mt-1 text-xs text-gray-600">{node.summary}</div>}
                      </div>
                    ))}
                  {graph.nodes.filter((node) => node.type === "risk" || node.risk_level).length === 0 && (
                    <div className="px-3 py-6 text-center text-sm text-gray-500">暂无风险节点</div>
                  )}
                </div>
              </div>
            </section>

            <section className="mt-5 rounded-md border border-gray-200">
              <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                <h2 className="font-semibold">全部节点</h2>
                <FileText className="size-4 text-gray-500" />
              </div>
              <div className="divide-y divide-gray-100">
                {graph.nodes.map((node) => (
                  <div key={node.id} className="grid gap-2 px-3 py-2 text-sm md:grid-cols-[120px_1fr_1fr]">
                    <div>{nodeTypeBadge(node.type)}</div>
                    <div className="min-w-0">
                      <NodeLink node={node} />
                      {node.risk_level && (
                        <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
                          {node.risk_level}
                        </span>
                      )}
                    </div>
                    <div className="min-w-0 break-all font-mono text-xs text-gray-500">
                      {node.source_path || node.id}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="mt-5 grid gap-3 md:grid-cols-2">
              <div className="rounded-md border border-gray-200 p-3">
                <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <BookOpen className="size-4 text-gray-500" />
                  Wiki
                </div>
                <div className="break-all font-mono text-xs text-gray-500">{graph.source_files.wiki_dir}</div>
              </div>
              <div className="rounded-md border border-gray-200 p-3">
                <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <DatabaseZap className="size-4 text-gray-500" />
                  Registry
                </div>
                <div className="break-all font-mono text-xs text-gray-500">{graph.source_files.registry_path}</div>
              </div>
            </section>
          </>
        )}
      </div>
    </WorkbenchShell>
  );
}
