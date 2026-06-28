"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  CircleDashed,
  CircleAlert,
  Clock,
  DatabaseZap,
  ExternalLink,
  FileDown,
  FileJson,
  FileText,
  LoaderCircle,
  RefreshCw,
  Server,
  SlidersHorizontal,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { WorkbenchShell } from "@/components/workbench/shell";
import { getWorkbenchDataHealth } from "@/lib/workbench-client";
import { cn } from "@/lib/utils";

type WorkflowStageStatus =
  | "success"
  | "warning"
  | "running"
  | "failed"
  | "pending"
  | "skipped";

type WorkflowProgress = {
  status: WorkflowStageStatus;
  completed: number;
  total: number;
  percent: number;
  stages: Array<{
    key: string;
    label: string;
    status: WorkflowStageStatus;
    summary: string;
    evidence: string[];
  }>;
};

type ArtifactCategory =
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

type SensitiveFieldCategory = "customer_pii" | "procurement_price" | "finance";

type SensitiveFieldSummary = {
  total_sensitive_fields: number;
  masking_required_count: number;
  category_counts: Record<SensitiveFieldCategory, number>;
  datasets: Array<{
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
    fields: Array<{
      field: string;
      category: SensitiveFieldCategory;
      label: string;
      risk_level: "high" | "medium";
      handling: "mask_values" | "aggregate_or_audit";
    }>;
  }>;
};

type WikiKnowledgeHealth = {
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

type HealthData = {
  checked_at: string;
  duckdb: { exists: boolean; size_bytes: number; updated_at: string };
  registry_file: { exists: boolean; size_bytes: number; updated_at: string };
  connector_registry_file: {
    exists: boolean;
    size_bytes: number;
    updated_at: string;
  };
  config_health: {
    status: "ok" | "warn" | "fail";
    ok_count: number;
    warn_count: number;
    fail_count: number;
    items: Array<{
      id: string;
      label: string;
      status: "ok" | "warn" | "fail";
      summary: string;
      path: string;
    }>;
  };
  embedding_health: {
    status: "success" | "warning" | "failed";
    binding: string;
    model: string;
    host: string;
    api_key_configured: boolean;
    timeout_ms: number;
    observed_latency_ms: number | null;
    failure_counts: Record<string, number>;
    warnings: string[];
  };
  registry: {
    updated_at: string;
    dataset_count: number;
    mart_count: number;
    semantic_count: number;
    datasets: Array<{
      slug: string;
      source: string;
      sheet_count: number;
      row_count: number;
      mart_count: number;
      semantic_count: number;
      overview_page: string;
      wiki_pages: string[];
      derived_exports: string[];
    }>;
  };
  connectors: {
    registry_path: string;
    updated_at: string;
    connector_count: number;
    ready_count: number;
    registered_count: number;
    needs_config_count: number;
    missing_count: number;
    items: Array<{
      connector_id: string;
      display_name: string;
      system: string;
      status: string;
      read_only: boolean;
      dataset_count: number;
      datasets: string[];
      last_sync: {
        dataset: string;
        status: string;
        snapshot_path: string;
        dataset_slug: string;
        row_count: number;
        completed_at: string;
      } | null;
    }>;
  };
  sources: {
    counts: {
      sources: number;
      active_sources: number;
      failed_sources: number;
      stale_sources: number;
      snapshots: number;
      schema_drift_count: number;
    };
    sources: Array<{
      source_id: string;
      display_name: string;
      status: string;
      freshness_status: string;
      snapshot_count: number;
    }>;
    warnings: string[];
  };
  sensitive_fields: SensitiveFieldSummary;
  wiki_knowledge: WikiKnowledgeHealth;
  lightrag_status: LightRAGData;
  workflow_progress: WorkflowProgress;
  artifact_links: Array<{
    label: string;
    category: ArtifactCategory;
    path: string;
    source: string;
    href: string;
    file_path: string;
    exists: boolean;
    size_bytes: number;
    updated_at: string;
  }>;
  tasks: Array<{
    task_id: string;
    goal: string;
    status: string;
    updated_at: string;
    step_count: number;
    final_report: string;
    progress: WorkflowProgress;
  }>;
};

type LightRAGData = {
  status: "success" | "unavailable";
  status_counts?: {
    processed?: number;
    processing?: number;
    pending?: number;
    failed?: number;
    all?: number;
  };
  pipeline_busy?: boolean;
  error?: string;
};

function StatCard({
  title,
  value,
  subtitle,
  tone = "ok",
  icon,
}: {
  title: string;
  value: string | number;
  subtitle: string;
  tone?: "ok" | "warn" | "bad" | "running" | "muted";
  icon: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-md border p-4",
        tone === "ok" && "border-emerald-200 bg-emerald-50",
        tone === "warn" && "border-amber-200 bg-amber-50",
        tone === "bad" && "border-rose-200 bg-rose-50",
        tone === "running" && "border-sky-200 bg-sky-50",
        tone === "muted" && "border-gray-200 bg-gray-50",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-gray-600">{title}</div>
        {icon}
      </div>
      <div className="mt-2 text-xl leading-tight font-semibold break-words text-gray-950">
        {value}
      </div>
      <div className="mt-1 text-xs text-gray-600">{subtitle}</div>
    </div>
  );
}

const statusMeta: Record<
  WorkflowStageStatus,
  {
    label: string;
    tone: "ok" | "warn" | "bad" | "running" | "muted";
    className: string;
  }
> = {
  success: {
    label: "成功",
    tone: "ok",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  warning: {
    label: "预警",
    tone: "warn",
    className: "border-amber-200 bg-amber-50 text-amber-700",
  },
  running: {
    label: "运行中",
    tone: "running",
    className: "border-sky-200 bg-sky-50 text-sky-700",
  },
  failed: {
    label: "失败",
    tone: "bad",
    className: "border-rose-200 bg-rose-50 text-rose-700",
  },
  pending: {
    label: "等待",
    tone: "muted",
    className: "border-gray-200 bg-gray-50 text-gray-600",
  },
  skipped: {
    label: "跳过",
    tone: "muted",
    className: "border-gray-200 bg-gray-50 text-gray-600",
  },
};

function StatusIcon({ status }: { status: WorkflowStageStatus }) {
  if (status === "success") return <CheckCircle2 className="size-4" />;
  if (status === "warning") return <CircleAlert className="size-4" />;
  if (status === "running")
    return <LoaderCircle className="size-4 animate-spin" />;
  if (status === "failed") return <XCircle className="size-4" />;
  return <CircleDashed className="size-4" />;
}

function StatusPill({ status }: { status: WorkflowStageStatus }) {
  const meta = statusMeta[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium",
        meta.className,
      )}
    >
      <StatusIcon status={status} />
      {meta.label}
    </span>
  );
}

function healthStatusLabel(status: string | undefined) {
  if (!status) return "读取中";
  return (
    statusMeta[status as WorkflowStageStatus]?.label ??
    ({ ok: "正常", warn: "预警", fail: "失败", unavailable: "不可用" }[
      status
    ] ||
      status)
  );
}

function artifactDisplayLabel(label: string) {
  return (
    {
      "Source Registry": "资料来源注册表",
      "Source Snapshot Manifest": "资料快照清单",
      "Dataset Registry": "数据集注册表",
      "Connector Registry": "系统连接注册表",
      "LightRAG Status": "知识库服务状态",
    }[label] ?? label
  );
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatTime(value: string) {
  if (!value) return "-";
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

const categoryMeta: Record<
  ArtifactCategory,
  { label: string; icon: ReactNode; className: string }
> = {
  report: {
    label: "报告",
    icon: <FileText className="size-4" />,
    className: "bg-indigo-50 text-indigo-700",
  },
  duckdb: {
    label: "本地数据仓库",
    icon: <DatabaseZap className="size-4" />,
    className: "bg-emerald-50 text-emerald-700",
  },
  registry: {
    label: "注册表",
    icon: <FileJson className="size-4" />,
    className: "bg-slate-100 text-slate-700",
  },
  source_registry: {
    label: "资料来源注册表",
    icon: <FileJson className="size-4" />,
    className: "bg-emerald-50 text-emerald-700",
  },
  source_snapshot: {
    label: "资料快照",
    icon: <FileDown className="size-4" />,
    className: "bg-cyan-50 text-cyan-700",
  },
  connector_registry: {
    label: "系统连接",
    icon: <Server className="size-4" />,
    className: "bg-sky-50 text-sky-700",
  },
  connector_snapshot: {
    label: "ERP 快照",
    icon: <FileDown className="size-4" />,
    className: "bg-teal-50 text-teal-700",
  },
  wiki: {
    label: "知识库页面",
    icon: <BookOpen className="size-4" />,
    className: "bg-cyan-50 text-cyan-700",
  },
  derived_export: {
    label: "派生产物",
    icon: <FileDown className="size-4" />,
    className: "bg-violet-50 text-violet-700",
  },
  lightrag_state: {
    label: "知识库服务",
    icon: <Activity className="size-4" />,
    className: "bg-amber-50 text-amber-700",
  },
  manifest: {
    label: "清单",
    icon: <FileJson className="size-4" />,
    className: "bg-gray-100 text-gray-700",
  },
};

export default function DataHealthPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [lightrag, setLightRAG] = useState<LightRAGData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const nextHealth = await getWorkbenchDataHealth();
      setHealth(nextHealth as HealthData);
      setLightRAG(nextHealth.lightrag_status as LightRAGData);
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : "Workbench 请求失败。",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const counts = lightrag?.status_counts ?? {};
  const failed = counts.failed ?? 0;
  const lightragTone =
    lightrag?.status === "unavailable" ? "muted" : failed > 0 ? "warn" : "ok";
  const workflow = health?.workflow_progress;
  const artifactLinks = health?.artifact_links ?? [];
  const connectorSummary = health?.connectors;
  const sourceSummary = health?.sources;
  const sensitive = health?.sensitive_fields;
  const wikiKnowledge = health?.wiki_knowledge;
  const workflowTone = workflow ? statusMeta[workflow.status].tone : "muted";
  const embedding = health?.embedding_health;
  const embeddingTone =
    embedding?.status === "failed"
      ? "bad"
      : embedding?.status === "warning"
        ? "warn"
        : embedding?.status === "success"
          ? "ok"
          : "muted";
  const sensitiveTone =
    (sensitive?.masking_required_count ?? 0) > 0
      ? "warn"
      : (sensitive?.total_sensitive_fields ?? 0) > 0
        ? "muted"
        : "ok";
  const configTone =
    health?.config_health?.status === "fail"
      ? "bad"
      : health?.config_health?.status === "warn"
        ? "warn"
        : health?.config_health?.status === "ok"
          ? "ok"
          : "muted";
  const wikiTone = wikiKnowledge
    ? statusMeta[wikiKnowledge.status].tone
    : "muted";
  const sourceTone =
    (sourceSummary?.counts.failed_sources ?? 0) > 0
      ? "bad"
      : (sourceSummary?.counts.schema_drift_count ?? 0) > 0 ||
          (sourceSummary?.counts.stale_sources ?? 0) > 0
        ? "warn"
        : (sourceSummary?.counts.sources ?? 0) > 0
          ? "ok"
          : "muted";

  return (
    <WorkbenchShell
      title="资料体检"
      description="检查资料是否完整、过期、缺字段或涉及敏感信息，判断能不能放心用于经营分析。"
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
            <Link href="/data-sources">
              <DatabaseZap className="size-4" />
              导入资料
            </Link>
          </Button>
          <Button
            asChild
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Link href="/logs">
              <FileJson className="size-4" />
              问题排查
            </Link>
          </Button>
          <Button
            asChild
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Link href="/tasks">
              <FileText className="size-4" />
              工作进度
            </Link>
          </Button>
          <Button
            asChild
            className="bg-blue-700 !text-white hover:bg-blue-800"
          >
            <Link href="/governance?tab=skills">
              <SlidersHorizontal className="size-4" />
              工具权限
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
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {error}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6 2xl:grid-cols-10">
          <StatCard
            title="处理流程"
            value={
              workflow ? `${workflow.completed}/${workflow.total}` : "读取中"
            }
            subtitle={
              workflow
                ? `${workflow.percent}% / ${healthStatusLabel(workflow.status)}`
                : "等待接口"
            }
            tone={workflowTone}
            icon={<Activity className="size-5" />}
          />
          <StatCard
            title="知识库服务"
            value={
              lightrag?.status === "unavailable" ? "不可用" : `失败 ${failed}`
            }
            subtitle={`已处理 ${counts.processed ?? 0} / 处理中 ${counts.processing ?? 0} / 排队 ${counts.pending ?? 0} / 总计 ${counts.all ?? 0}`}
            tone={lightragTone}
            icon={<DatabaseZap className="size-5" />}
          />
          <StatCard
            title="向量服务"
            value={embedding?.api_key_configured ? embedding.model : "缺少密钥"}
            subtitle={`超时 ${embedding?.failure_counts.embedding_timeout ?? 0} / 余额 ${embedding?.failure_counts.llm_insufficient_balance ?? 0} / ${embedding?.observed_latency_ms ?? "-"}ms`}
            tone={embeddingTone}
            icon={<Activity className="size-5" />}
          />
          <StatCard
            title="本地数据仓库"
            value={health?.duckdb.exists ? "就绪" : "缺失"}
            subtitle={health?.duckdb.updated_at || "未检测到文件"}
            tone={health?.duckdb.exists ? "ok" : "warn"}
            icon={
              health?.duckdb.exists ? (
                <CheckCircle2 className="size-5" />
              ) : (
                <CircleAlert className="size-5" />
              )
            }
          />
          <StatCard
            title="数据集"
            value={health?.registry.dataset_count ?? 0}
            subtitle={`宽表 ${health?.registry.mart_count ?? 0} / 语义 ${health?.registry.semantic_count ?? 0}`}
            icon={<Server className="size-5" />}
          />
          <StatCard
            title="资料来源"
            value={sourceSummary?.counts.sources ?? 0}
            subtitle={`启用 ${sourceSummary?.counts.active_sources ?? 0} / 失败 ${sourceSummary?.counts.failed_sources ?? 0} / 漂移 ${sourceSummary?.counts.schema_drift_count ?? 0}`}
            tone={sourceTone}
            icon={<DatabaseZap className="size-5" />}
          />
          <StatCard
            title="系统连接"
            value={connectorSummary?.connector_count ?? 0}
            subtitle={`就绪 ${connectorSummary?.ready_count ?? 0} / 已登记 ${connectorSummary?.registered_count ?? 0} / 待配置 ${connectorSummary?.needs_config_count ?? 0} / 缺失 ${connectorSummary?.missing_count ?? 0}`}
            tone={
              (connectorSummary?.missing_count ?? 0) > 0
                ? "bad"
                : (connectorSummary?.needs_config_count ?? 0) > 0
                  ? "warn"
                  : (connectorSummary?.registered_count ?? 0) > 0
                    ? "warn"
                    : (connectorSummary?.connector_count ?? 0) > 0
                      ? "ok"
                      : "muted"
            }
            icon={<Server className="size-5" />}
          />
          <StatCard
            title="敏感字段"
            value={sensitive?.total_sensitive_fields ?? 0}
            subtitle={`隐私 ${sensitive?.category_counts.customer_pii ?? 0} / 采购价 ${sensitive?.category_counts.procurement_price ?? 0} / 财务 ${sensitive?.category_counts.finance ?? 0}`}
            tone={sensitiveTone}
            icon={<CircleAlert className="size-5" />}
          />
          <StatCard
            title="知识库"
            value={healthStatusLabel(wikiKnowledge?.status)}
            subtitle={`页面 ${wikiKnowledge?.page_count ?? 0} / 证据缺口 ${wikiKnowledge?.unsourced_claim_count ?? 0} / 过期 ${wikiKnowledge?.stale_claim_count ?? 0}`}
            tone={wikiTone}
            icon={<BookOpen className="size-5" />}
          />
          <StatCard
            title="最近工作"
            value={health?.tasks.length ?? 0}
            subtitle={
              health?.checked_at ? `检查 ${health.checked_at}` : "读取中"
            }
            icon={<Clock className="size-5" />}
          />
          <StatCard
            title="系统配置"
            value={healthStatusLabel(health?.config_health?.status)}
            subtitle={`正常 ${health?.config_health?.ok_count ?? 0} / 预警 ${health?.config_health?.warn_count ?? 0} / 失败 ${health?.config_health?.fail_count ?? 0}`}
            tone={configTone}
            icon={<SlidersHorizontal className="size-5" />}
          />
          <StatCard
            title="结果文件"
            value={artifactLinks.length}
            subtitle={`${artifactLinks.filter((link) => link.exists).length} 就绪 / ${artifactLinks.filter((link) => !link.exists).length} 缺失`}
            tone={artifactLinks.some((link) => !link.exists) ? "warn" : "ok"}
            icon={<ExternalLink className="size-5" />}
          />
        </div>

        <section className="mt-6">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">处理进度</h2>
            {workflow && <StatusPill status={workflow.status} />}
          </div>
          <div className="mb-3 h-2 overflow-hidden rounded-full bg-gray-100">
            <div
              className={cn(
                "h-full rounded-full",
                workflow?.status === "failed" && "bg-rose-500",
                workflow?.status === "warning" && "bg-amber-500",
                workflow?.status === "running" && "bg-sky-500",
                workflow?.status === "success" && "bg-emerald-500",
                (!workflow || workflow.status === "pending") && "bg-gray-300",
              )}
              style={{ width: `${workflow?.percent ?? 0}%` }}
            />
          </div>
          <div className="grid gap-2 lg:grid-cols-7">
            {(workflow?.stages ?? []).map((stage) => (
              <div
                key={stage.key}
                className={cn(
                  "min-h-24 rounded-md border p-3",
                  statusMeta[stage.status].className,
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate text-xs font-semibold uppercase">
                    {stage.label}
                  </div>
                  <StatusIcon status={stage.status} />
                </div>
                <div className="mt-2 line-clamp-2 text-xs opacity-80">
                  {stage.summary || `${stage.evidence.length} 条证据`}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">知识库体检</h2>
            {wikiKnowledge && <StatusPill status={wikiKnowledge.status} />}
          </div>
          <div className="grid gap-3 lg:grid-cols-4">
            <div className="rounded-md border border-gray-200 p-3">
              <div className="text-xs font-medium text-gray-500 uppercase">
                生命周期文件
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {[
                  ["schema", wikiKnowledge?.schema_present],
                  ["index", wikiKnowledge?.index_present],
                  ["log", wikiKnowledge?.log_present],
                ].map(([label, ready]) => (
                  <span
                    key={String(label)}
                    className={cn(
                      "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs",
                      ready
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-amber-200 bg-amber-50 text-amber-700",
                    )}
                  >
                    {ready ? (
                      <CheckCircle2 className="size-3.5" />
                    ) : (
                      <CircleAlert className="size-3.5" />
                    )}
                    {label}
                  </span>
                ))}
              </div>
              <div className="mt-3 text-sm text-gray-600">
                {wikiKnowledge?.indexed_count ?? 0} 已索引 /{" "}
                {wikiKnowledge?.log_entry_count ?? 0} 条日志
              </div>
            </div>
            <div className="rounded-md border border-gray-200 p-3">
              <div className="text-xs font-medium text-gray-500 uppercase">
                覆盖缺口
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                <div>
                  元数据 {wikiKnowledge?.missing_frontmatter_count ?? 0}
                </div>
                <div>证据 {wikiKnowledge?.unsourced_claim_count ?? 0}</div>
                <div>孤立页 {wikiKnowledge?.orphan_count ?? 0}</div>
                <div>索引 {wikiKnowledge?.missing_index_count ?? 0}</div>
              </div>
            </div>
            <div className="rounded-md border border-gray-200 p-3">
              <div className="text-xs font-medium text-gray-500 uppercase">
                结论状态
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                <div>过期 {wikiKnowledge?.stale_claim_count ?? 0}</div>
                <div>冲突 {wikiKnowledge?.contradicted_claim_count ?? 0}</div>
                <div>链接 {wikiKnowledge?.unresolved_link_count ?? 0}</div>
                <div>页面 {wikiKnowledge?.page_count ?? 0}</div>
              </div>
            </div>
            <div className="rounded-md border border-gray-200 p-3">
              <div className="text-xs font-medium text-gray-500 uppercase">
                复核问题
              </div>
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                {(wikiKnowledge?.review_questions ?? [])
                  .slice(0, 3)
                  .map((question) => (
                    <li
                      key={question}
                      className="line-clamp-2"
                    >
                      {question}
                    </li>
                  ))}
                {(wikiKnowledge?.review_questions ?? []).length === 0 && (
                  <li>-</li>
                )}
              </ul>
            </div>
          </div>
          {(wikiKnowledge?.warnings.length ?? 0) > 0 && (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <div className="font-medium">预警</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {wikiKnowledge?.warnings.slice(0, 8).map((warning) => (
                  <span
                    key={warning}
                    className="rounded bg-white/70 px-1.5 py-0.5"
                  >
                    {warning}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="mt-6">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">业务系统连接</h2>
            <div className="text-xs text-gray-500">
              吉客云 / 金蝶只读接入、权限和同步产物
            </div>
          </div>
          <div className="overflow-hidden rounded-md border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-3 py-2">连接器</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">数据集</th>
                  <th className="px-3 py-2">最近同步</th>
                  <th className="px-3 py-2">快照</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(connectorSummary?.items ?? []).map((connector) => (
                  <tr key={connector.connector_id}>
                    <td className="px-3 py-2">
                      <div className="font-medium">
                        {connector.display_name || connector.connector_id}
                      </div>
                      <div className="text-xs text-gray-500">
                        {connector.system}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs",
                          connector.status === "ready" &&
                            "border-emerald-200 bg-emerald-50 text-emerald-700",
                          connector.status === "needs_config" &&
                            "border-amber-200 bg-amber-50 text-amber-700",
                          connector.status === "missing_skill" &&
                            "border-rose-200 bg-rose-50 text-rose-700",
                          !["ready", "needs_config", "missing_skill"].includes(
                            connector.status,
                          ) && "border-gray-200 bg-gray-50 text-gray-600",
                        )}
                      >
                        {connector.status === "ready" ? (
                          <CheckCircle2 className="size-3.5" />
                        ) : (
                          <CircleAlert className="size-3.5" />
                        )}
                        {connector.status}
                      </span>
                    </td>
                    <td className="px-3 py-2">{connector.dataset_count}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {connector.last_sync
                        ? `${connector.last_sync.dataset} / ${connector.last_sync.row_count} 行 / ${formatTime(connector.last_sync.completed_at)}`
                        : "-"}
                    </td>
                    <td className="max-w-md truncate px-3 py-2 font-mono text-xs text-gray-500">
                      {connector.last_sync?.snapshot_path || "-"}
                    </td>
                  </tr>
                ))}
                {(connectorSummary?.items ?? []).length === 0 && (
                  <tr>
                    <td
                      className="px-3 py-6 text-center text-sm text-gray-500"
                      colSpan={5}
                    >
                      暂无连接器注册表
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-6">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">字段级敏感数据</h2>
            <div className="text-xs text-gray-500">
              客户信息脱敏；采购价 / 财务数据按聚合和审计处理
            </div>
          </div>
          <div className="overflow-hidden rounded-md border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-3 py-2">数据集</th>
                  <th className="px-3 py-2">类别</th>
                  <th className="px-3 py-2">处理</th>
                  <th className="px-3 py-2">字段</th>
                  <th className="px-3 py-2">来源</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(sensitive?.datasets ?? []).map((dataset) => {
                  const requiresMasking = dataset.categories.some(
                    (category) => category.handling === "mask_values",
                  );
                  return (
                    <tr key={dataset.slug || dataset.source}>
                      <td className="px-3 py-2">
                        <div className="font-medium">{dataset.slug || "-"}</div>
                        <div className="text-xs text-gray-500">
                          {dataset.total_sensitive_fields} 个字段
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          {dataset.categories.map((category) => (
                            <span
                              key={category.category}
                              className={cn(
                                "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs",
                                category.risk_level === "high"
                                  ? "border-amber-200 bg-amber-50 text-amber-700"
                                  : "border-gray-200 bg-gray-50 text-gray-700",
                              )}
                            >
                              {category.label} {category.count}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs",
                            requiresMasking
                              ? "border-amber-200 bg-amber-50 text-amber-700"
                              : "border-gray-200 bg-gray-50 text-gray-600",
                          )}
                        >
                          {requiresMasking ? "需脱敏" : "需审计"}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex max-w-xl flex-wrap gap-1">
                          {dataset.fields.slice(0, 8).map((field) => (
                            <span
                              key={`${field.category}-${field.field}`}
                              className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[11px] text-gray-700"
                            >
                              {field.field}
                            </span>
                          ))}
                          {dataset.fields.length > 8 && (
                            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
                              +{dataset.fields.length - 8}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="max-w-md truncate px-3 py-2 text-gray-500">
                        {dataset.source || "-"}
                      </td>
                    </tr>
                  );
                })}
                {(sensitive?.datasets ?? []).length === 0 && (
                  <tr>
                    <td
                      className="px-3 py-6 text-center text-sm text-gray-500"
                      colSpan={5}
                    >
                      暂无敏感字段分类
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-6">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">结果文件</h2>
            <div className="text-xs text-gray-500">
              报告 / 本地数据仓库 / 注册表 / 知识库 / 派生产物 / 知识库服务
            </div>
          </div>
          <div className="overflow-hidden rounded-md border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-3 py-2">类型</th>
                  <th className="px-3 py-2">产物</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">更新时间</th>
                  <th className="px-3 py-2">路径</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {artifactLinks.map((artifact) => {
                  const meta = categoryMeta[artifact.category];
                  return (
                    <tr key={`${artifact.category}-${artifact.file_path}`}>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium",
                            meta.className,
                          )}
                        >
                          {meta.icon}
                          {meta.label}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-medium">
                        <a
                          href={artifact.href}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex max-w-xs items-center gap-1 truncate text-blue-700 hover:underline"
                        >
                          <ExternalLink className="size-3.5 shrink-0" />
                          <span className="truncate">
                            {artifactDisplayLabel(artifact.label)}
                          </span>
                        </a>
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs",
                            artifact.exists
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : "border-amber-200 bg-amber-50 text-amber-700",
                          )}
                        >
                          {artifact.exists ? (
                            <CheckCircle2 className="size-3.5" />
                          ) : (
                            <CircleAlert className="size-3.5" />
                          )}
                          {artifact.exists
                            ? formatBytes(artifact.size_bytes)
                            : "缺失"}
                        </span>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-gray-500">
                        {formatTime(artifact.updated_at)}
                      </td>
                      <td className="max-w-xl truncate px-3 py-2 font-mono text-xs text-gray-500">
                        {artifact.file_path}
                      </td>
                    </tr>
                  );
                })}
                {artifactLinks.length === 0 && (
                  <tr>
                    <td
                      className="px-3 py-6 text-center text-sm text-gray-500"
                      colSpan={5}
                    >
                      暂无产物链接
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-6">
          <h2 className="mb-2 text-lg font-semibold">数据集注册表</h2>
          <div className="overflow-hidden rounded-md border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-3 py-2">数据集</th>
                  <th className="px-3 py-2">工作表</th>
                  <th className="px-3 py-2">行数</th>
                  <th className="px-3 py-2">宽表</th>
                  <th className="px-3 py-2">导出</th>
                  <th className="px-3 py-2">Wiki</th>
                  <th className="px-3 py-2">来源</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(health?.registry.datasets ?? []).map((dataset) => (
                  <tr key={dataset.slug}>
                    <td className="px-3 py-2 font-medium">{dataset.slug}</td>
                    <td className="px-3 py-2">{dataset.sheet_count}</td>
                    <td className="px-3 py-2">{dataset.row_count}</td>
                    <td className="px-3 py-2">{dataset.mart_count}</td>
                    <td className="px-3 py-2">
                      {dataset.derived_exports.length}
                    </td>
                    <td className="px-3 py-2">{dataset.wiki_pages.length}</td>
                    <td className="max-w-md truncate px-3 py-2 text-gray-500">
                      {dataset.source}
                    </td>
                  </tr>
                ))}
                {(health?.registry.datasets ?? []).length === 0 && (
                  <tr>
                    <td
                      className="px-3 py-6 text-center text-sm text-gray-500"
                      colSpan={7}
                    >
                      暂无已登记数据集
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-6">
          <h2 className="mb-2 text-lg font-semibold">最近工作</h2>
          <div className="grid gap-2">
            {(health?.tasks ?? []).map((task) => (
              <div
                key={task.task_id}
                className="rounded-md border border-gray-200 p-3"
              >
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <FileText className="size-4" />
                  <Link
                    href={`/tasks/${encodeURIComponent(task.task_id)}`}
                    className="font-medium text-blue-700 hover:underline"
                  >
                    {task.task_id}
                  </Link>
                  <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
                    {task.status}
                  </span>
                  <span className="text-xs text-gray-500">
                    {task.progress.completed}/{task.progress.total}
                  </span>
                  <span className="text-xs text-gray-500">
                    {task.step_count} 步骤
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatTime(task.updated_at)}
                  </span>
                </div>
                <div className="mt-1 line-clamp-2 text-sm text-gray-600">
                  {task.goal}
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      task.progress.status === "failed" && "bg-rose-500",
                      task.progress.status === "warning" && "bg-amber-500",
                      task.progress.status === "running" && "bg-sky-500",
                      task.progress.status === "success" && "bg-emerald-500",
                      task.progress.status === "pending" && "bg-gray-300",
                    )}
                    style={{ width: `${task.progress.percent}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </WorkbenchShell>
  );
}
