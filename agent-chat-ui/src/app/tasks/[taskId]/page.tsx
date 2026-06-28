"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  CircleAlert,
  Clock,
  DatabaseZap,
  ExternalLink,
  FileJson,
  FileText,
  LoaderCircle,
  Network,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  StopCircle,
  Wrench,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { WorkbenchShell } from "@/components/workbench/shell";
import { cn } from "@/lib/utils";
import { showWorkbenchTask, submitTaskAction } from "@/lib/workbench-client";
import type { TaskDetail, TaskTimelineEvent } from "@/lib/tasks";
import type { WorkflowStageStatus } from "@/lib/data-health";

const STATUS_CLASS: Record<string, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  running: "border-sky-200 bg-sky-50 text-sky-700",
  queued: "border-sky-200 bg-sky-50 text-sky-700",
  failed: "border-rose-200 bg-rose-50 text-rose-700",
  cancelled: "border-gray-200 bg-gray-50 text-gray-600",
  created: "border-gray-200 bg-gray-50 text-gray-600",
  pending: "border-gray-200 bg-gray-50 text-gray-600",
  skipped: "border-gray-200 bg-gray-50 text-gray-600",
  unknown: "border-gray-200 bg-gray-50 text-gray-600",
};

const CATEGORY_CLASS: Record<string, string> = {
  report: "bg-indigo-50 text-indigo-700",
  wiki: "bg-cyan-50 text-cyan-700",
  duckdb: "bg-emerald-50 text-emerald-700",
  registry: "bg-slate-100 text-slate-700",
  lightrag_state: "bg-amber-50 text-amber-700",
  manifest: "bg-gray-100 text-gray-700",
  derived_export: "bg-violet-50 text-violet-700",
};

const STATUS_LABEL: Record<string, string> = {
  success: "成功",
  warning: "有预警",
  running: "运行中",
  queued: "排队中",
  failed: "失败",
  cancelled: "已取消",
  created: "已创建",
  pending: "等待",
  skipped: "跳过",
  unknown: "未知",
};

const CATEGORY_LABEL: Record<string, string> = {
  report: "报告",
  wiki: "Wiki",
  duckdb: "DuckDB",
  registry: "注册表",
  lightrag_state: "LightRAG 状态",
  manifest: "清单",
  derived_export: "派生产物",
};

function taskIdParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

function formatTime(value: string) {
  if (!value) return "-";
  const parsed = Date.parse(
    value.includes("T") ? value : value.replace(" ", "T"),
  );
  if (Number.isNaN(parsed)) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(parsed));
}

function StatusIcon({ status }: { status: string }) {
  if (status === "success") return <CheckCircle2 className="size-4" />;
  if (status === "warning") return <CircleAlert className="size-4" />;
  if (status === "running" || status === "queued")
    return <LoaderCircle className="size-4 animate-spin" />;
  if (status === "failed") return <XCircle className="size-4" />;
  return <Clock className="size-4" />;
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium",
        STATUS_CLASS[status] ?? STATUS_CLASS.unknown,
      )}
    >
      <StatusIcon status={status} />
      {STATUS_LABEL[status] ?? (status || "未知")}
    </span>
  );
}

function QaVerdictBadge({ verdict }: { verdict: string }) {
  const status =
    verdict === "PASS" ? "success" : verdict === "FAIL" ? "failed" : "warning";
  return <StatusBadge status={status} />;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-lg font-semibold break-words text-gray-950">
        {value}
      </div>
    </div>
  );
}

function progressColor(status: WorkflowStageStatus | string) {
  if (status === "failed") return "bg-rose-500";
  if (status === "warning") return "bg-amber-500";
  if (status === "running" || status === "queued") return "bg-sky-500";
  if (status === "success") return "bg-emerald-500";
  return "bg-gray-300";
}

function fileHref(pathValue: string) {
  if (!pathValue.startsWith("/")) return "";
  return `file://${pathValue.split("/").map(encodeURIComponent).join("/")}`;
}

function EventRow({ event }: { event: TaskTimelineEvent }) {
  return (
    <div className="grid gap-2 border-b border-gray-100 px-3 py-2 text-sm last:border-b-0 md:grid-cols-[160px_110px_1fr]">
      <div className="text-xs text-gray-500">{formatTime(event.timestamp)}</div>
      <div>
        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
          {event.source || "事件"}
        </span>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{event.name}</span>
          {event.status && <StatusBadge status={event.status} />}
          {event.tool_name && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
              {event.tool_name}
            </span>
          )}
        </div>
        {event.summary && (
          <div className="mt-1 text-gray-600">{event.summary}</div>
        )}
      </div>
    </div>
  );
}

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = decodeURIComponent(taskIdParam(params.taskId));
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState("");
  const [error, setError] = useState("");

  async function load() {
    if (!taskId) return;
    setLoading(true);
    setError("");
    try {
      setTask(await showWorkbenchTask(taskId));
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : String(loadError),
      );
    } finally {
      setLoading(false);
    }
  }

  async function runAction(action: "cancel" | "recover") {
    if (!taskId) return;
    setActionLoading(action);
    setError("");
    try {
      setTask(await submitTaskAction(taskId, action));
    } catch (actionError) {
      setError(
        actionError instanceof Error
          ? actionError.message
          : String(actionError),
      );
    } finally {
      setActionLoading("");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  const reportArtifact = useMemo(
    () => task?.artifacts.find((artifact) => artifact.category === "report"),
    [task],
  );
  const wikiArtifact = useMemo(
    () => task?.artifacts.find((artifact) => artifact.category === "wiki"),
    [task],
  );
  const evidenceGraphHref = useMemo(() => {
    const params = new URLSearchParams();
    params.set("taskId", task?.task_id || taskId);
    if (reportArtifact?.path) params.set("reportPath", reportArtifact.path);
    return `/evidence-graph?${params.toString()}`;
  }, [reportArtifact?.path, task?.task_id, taskId]);

  return (
    <WorkbenchShell
      title="任务详情"
      description={taskId}
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
              任务列表
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

        {!task && loading && (
          <div className="rounded-md border border-gray-200 p-8 text-center text-sm text-gray-500">
            正在读取任务详情...
          </div>
        )}

        {!task && !loading && !error && (
          <div className="rounded-md border border-gray-200 p-8 text-center text-sm text-gray-500">
            请选择一个任务。
          </div>
        )}

        {task && (
          <>
            <section className="rounded-md border border-gray-200 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <StatusBadge status={task.summary.status} />
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
                      {task.summary.task_type}
                    </span>
                    {task.summary.recoverable && (
                      <span className="rounded bg-sky-50 px-1.5 py-0.5 text-xs text-sky-700">
                        可恢复
                      </span>
                    )}
                    {task.summary.cancel_requested && (
                      <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
                        已请求取消
                      </span>
                    )}
                  </div>
                  <div className="text-lg font-semibold">
                    {task.original_user_text || task.goal}
                  </div>
                  {task.original_user_text && (
                    <div className="mt-2 line-clamp-3 text-sm text-gray-600">
                      {task.goal}
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={
                      Boolean(actionLoading) ||
                      ["success", "failed", "cancelled"].includes(task.status)
                    }
                    onClick={() => void runAction("cancel")}
                  >
                    <StopCircle className="size-4" />
                    {actionLoading === "cancel" ? "请求中" : "取消"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={Boolean(actionLoading)}
                    onClick={() => void runAction("recover")}
                  >
                    <RotateCcw className="size-4" />
                    {actionLoading === "recover" ? "请求中" : "恢复"}
                  </Button>
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
                <Stat
                  label="创建"
                  value={formatTime(task.created_at)}
                />
                <Stat
                  label="更新"
                  value={formatTime(task.updated_at)}
                />
                <Stat
                  label="请求方"
                  value={task.requested_by || "-"}
                />
                <Stat
                  label="步骤"
                  value={task.steps_count}
                />
                <Stat
                  label="风险"
                  value={task.risk_count}
                />
                <Stat
                  label="产物"
                  value={task.artifact_count}
                />
              </div>
            </section>

            <section className="mt-5">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h2 className="text-lg font-semibold">阶段进度</h2>
                <div className="text-xs text-gray-500">
                  {task.progress.completed}/{task.progress.total} /{" "}
                  {task.progress.percent}%
                </div>
              </div>
              <div className="mb-3 h-2 overflow-hidden rounded-full bg-gray-100">
                <div
                  className={cn(
                    "h-full rounded-full",
                    progressColor(task.progress.status),
                  )}
                  style={{ width: `${task.progress.percent}%` }}
                />
              </div>
              <div className="grid gap-2 lg:grid-cols-7">
                {task.stages.map((stage) => (
                  <div
                    key={stage.key}
                    className={cn(
                      "min-h-24 rounded-md border p-3",
                      STATUS_CLASS[stage.status] ?? STATUS_CLASS.unknown,
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

            {(task.handoffs.length > 0 || task.qa_gates.length > 0) && (
              <section className="mt-5 grid gap-4 lg:grid-cols-2">
                <div className="rounded-md border border-gray-200">
                  <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                    <h2 className="font-semibold">Agent 交接</h2>
                    <Activity className="size-4 text-gray-500" />
                  </div>
                  <div className="divide-y divide-gray-100">
                    {task.handoffs.map((handoff) => (
                      <div
                        key={handoff.id}
                        className="px-3 py-3 text-sm"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                            {handoff.from_agent || "-"}
                          </span>
                          <span className="text-xs text-gray-400">to</span>
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                            {handoff.to_agent || "-"}
                          </span>
                          <StatusBadge status={handoff.status || "success"} />
                          <span className="text-xs text-gray-500">
                            {formatTime(handoff.timestamp)}
                          </span>
                        </div>
                        {handoff.summary && (
                          <div className="mt-1 text-gray-600">
                            {handoff.summary}
                          </div>
                        )}
                        {handoff.evidence_paths.length > 0 && (
                          <div className="mt-2 font-mono text-xs break-all text-gray-500">
                            {handoff.evidence_paths.slice(0, 2).join(" / ")}
                          </div>
                        )}
                        {handoff.next_actions.length > 0 && (
                          <div className="mt-2 text-xs text-sky-700">
                            {handoff.next_actions.slice(0, 3).join(" / ")}
                          </div>
                        )}
                      </div>
                    ))}
                    {task.handoffs.length === 0 && (
                      <div className="px-3 py-6 text-center text-sm text-gray-500">
                        暂无交接事件
                      </div>
                    )}
                  </div>
                </div>

                <div className="rounded-md border border-gray-200">
                  <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                    <h2 className="font-semibold">QA Gate</h2>
                    <CheckCircle2 className="size-4 text-gray-500" />
                  </div>
                  <div className="divide-y divide-gray-100">
                    {task.qa_gates.map((gate) => (
                      <div
                        key={gate.id}
                        className="px-3 py-3 text-sm"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <QaVerdictBadge verdict={gate.verdict} />
                          <span className="font-mono text-xs text-gray-500">
                            {gate.verdict}
                          </span>
                          {gate.checked_by && (
                            <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-700">
                              {gate.checked_by}
                            </span>
                          )}
                          <span className="text-xs text-gray-500">
                            {formatTime(gate.timestamp)}
                          </span>
                          <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
                            retry {gate.retry_count}
                          </span>
                        </div>
                        {gate.summary && (
                          <div className="mt-1 text-gray-600">
                            {gate.summary}
                          </div>
                        )}
                        {gate.evidence_paths.length > 0 && (
                          <div className="mt-2 font-mono text-xs break-all text-gray-500">
                            {gate.evidence_paths.slice(0, 2).join(" / ")}
                          </div>
                        )}
                        {gate.next_actions.length > 0 && (
                          <div className="mt-2 text-xs text-sky-700">
                            {gate.next_actions.slice(0, 3).join(" / ")}
                          </div>
                        )}
                      </div>
                    ))}
                    {task.qa_gates.length === 0 && (
                      <div className="px-3 py-6 text-center text-sm text-gray-500">
                        暂无 QA 事件
                      </div>
                    )}
                  </div>
                </div>
              </section>
            )}

            <section className="mt-5 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-md border border-gray-200">
                <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                  <h2 className="font-semibold">步骤明细</h2>
                  <Activity className="size-4 text-gray-500" />
                </div>
                <div className="divide-y divide-gray-100">
                  {task.steps.map((step, index) => {
                    const record = step as Record<string, unknown>;
                    const risks = Array.isArray(record.risks)
                      ? record.risks
                      : [];
                    const missing = Array.isArray(record.missing_data)
                      ? record.missing_data
                      : [];
                    const next = Array.isArray(record.next_actions)
                      ? record.next_actions
                      : [];
                    return (
                      <div
                        key={`${String(record.task)}-${index}`}
                        className="px-3 py-3 text-sm"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {String(record.task || `step_${index + 1}`)}
                          </span>
                          <StatusBadge
                            status={String(record.status || "unknown")}
                          />
                          <span className="text-xs text-gray-500">
                            {formatTime(String(record.completed_at || ""))}
                          </span>
                        </div>
                        {String(record.summary || "") && (
                          <div className="mt-1 text-gray-600">
                            {String(record.summary)}
                          </div>
                        )}
                        {(risks.length > 0 ||
                          missing.length > 0 ||
                          next.length > 0) && (
                          <div className="mt-2 grid gap-2 md:grid-cols-3">
                            <div>
                              <div className="text-xs font-medium text-gray-500">
                                风险
                              </div>
                              <ul className="mt-1 flex flex-col gap-1 text-xs text-rose-700">
                                {risks.slice(0, 4).map((item, itemIndex) => (
                                  <li key={itemIndex}>{String(item)}</li>
                                ))}
                              </ul>
                            </div>
                            <div>
                              <div className="text-xs font-medium text-gray-500">
                                缺失
                              </div>
                              <ul className="mt-1 flex flex-col gap-1 text-xs text-amber-700">
                                {missing.slice(0, 4).map((item, itemIndex) => (
                                  <li key={itemIndex}>{String(item)}</li>
                                ))}
                              </ul>
                            </div>
                            <div>
                              <div className="text-xs font-medium text-gray-500">
                                下一步
                              </div>
                              <ul className="mt-1 flex flex-col gap-1 text-xs text-sky-700">
                                {next.slice(0, 4).map((item, itemIndex) => (
                                  <li key={itemIndex}>{String(item)}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="flex flex-col gap-4">
                <div className="rounded-md border border-gray-200">
                  <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                    <h2 className="font-semibold">操作入口</h2>
                    <Wrench className="size-4 text-gray-500" />
                  </div>
                  <div className="flex flex-wrap gap-2 p-3">
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                    >
                      <Link href="/data-health">
                        <DatabaseZap className="size-4" />
                        资料体检
                      </Link>
                    </Button>
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                    >
                      <a
                        href={`/api/agent-traces?taskId=${encodeURIComponent(task.task_id)}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Activity className="size-4" />
                        调用轨迹
                      </a>
                    </Button>
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                    >
                      <Link href={evidenceGraphHref}>
                        <Network className="size-4" />
                        依据来源
                      </Link>
                    </Button>
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                    >
                      <Link href="/data-health">
                        <ShieldAlert className="size-4" />
                        LightRAG 诊断
                      </Link>
                    </Button>
                    <Button
                      asChild
                      variant="outline"
                      size="sm"
                    >
                      <Link href="/data-health">
                        <Wrench className="size-4" />
                        线程修复
                      </Link>
                    </Button>
                    {reportArtifact && fileHref(reportArtifact.path) && (
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                      >
                        <a
                          href={fileHref(reportArtifact.path)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <FileText className="size-4" />
                          查看报告
                        </a>
                      </Button>
                    )}
                    {wikiArtifact && fileHref(wikiArtifact.path) && (
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                      >
                        <a
                          href={fileHref(wikiArtifact.path)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <BookOpen className="size-4" />
                          打开 Wiki
                        </a>
                      </Button>
                    )}
                  </div>
                </div>

                <div className="rounded-md border border-gray-200">
                  <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                    <h2 className="font-semibold">错误和恢复线索</h2>
                    <CircleAlert className="size-4 text-gray-500" />
                  </div>
                  <div className="divide-y divide-gray-100">
                    {task.errors.map((item) => (
                      <div
                        key={`${item.step}-${item.summary}`}
                        className="px-3 py-2 text-sm"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{item.step}</span>
                          <StatusBadge status={item.status} />
                        </div>
                        {item.summary && (
                          <div className="mt-1 text-gray-600">
                            {item.summary}
                          </div>
                        )}
                        {item.next_actions.length > 0 && (
                          <div className="mt-1 text-xs text-sky-700">
                            {item.next_actions.join(" / ")}
                          </div>
                        )}
                      </div>
                    ))}
                    {task.errors.length === 0 && (
                      <div className="px-3 py-6 text-center text-sm text-gray-500">
                        暂无错误或告警步骤
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </section>

            <section className="mt-5 grid gap-4 lg:grid-cols-2">
              <div className="rounded-md border border-gray-200">
                <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                  <h2 className="font-semibold">产物链接</h2>
                  <ExternalLink className="size-4 text-gray-500" />
                </div>
                <div className="divide-y divide-gray-100">
                  {task.artifacts.map((artifact, artifactIndex) => (
                    <div
                      key={`${artifact.category}-${artifact.path}-${artifactIndex}`}
                      className="grid gap-2 px-3 py-2 text-sm md:grid-cols-[130px_1fr_auto]"
                    >
                      <span
                        className={cn(
                          "inline-flex w-fit items-center rounded px-1.5 py-0.5 text-xs font-medium",
                          CATEGORY_CLASS[artifact.category] ??
                            "bg-gray-100 text-gray-700",
                        )}
                      >
                        {CATEGORY_LABEL[artifact.category] ?? artifact.category}
                      </span>
                      <div className="min-w-0">
                        <div className="font-medium">{artifact.label}</div>
                        <div className="font-mono text-xs break-all text-gray-500">
                          {artifact.path}
                        </div>
                      </div>
                      {artifact.category === "report" ? (
                        <Button
                          asChild
                          variant="outline"
                          size="sm"
                        >
                          <Link
                            href={`/evidence-graph?taskId=${encodeURIComponent(task.task_id)}&reportPath=${encodeURIComponent(artifact.path)}`}
                          >
                            <Network className="size-4" />
                            依据来源
                          </Link>
                        </Button>
                      ) : (
                        <span />
                      )}
                    </div>
                  ))}
                  {task.artifacts.length === 0 && (
                    <div className="px-3 py-6 text-center text-sm text-gray-500">
                      暂无产物链接
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-md border border-gray-200">
                <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                  <h2 className="font-semibold">依据来源</h2>
                  <BookOpen className="size-4 text-gray-500" />
                </div>
                <div className="divide-y divide-gray-100">
                  {task.evidence.map((item, evidenceIndex) => (
                    <div
                      key={`${item.step}-${item.path}-${evidenceIndex}`}
                      className="grid gap-2 px-3 py-2 text-sm md:grid-cols-[130px_1fr]"
                    >
                      <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
                        {item.step}
                      </span>
                      <div className="font-mono text-xs break-all text-gray-600">
                        {item.path}
                      </div>
                    </div>
                  ))}
                  {task.evidence.length === 0 && (
                    <div className="px-3 py-6 text-center text-sm text-gray-500">
                      暂无依据来源
                    </div>
                  )}
                </div>
              </div>
            </section>

            <section className="mt-5 rounded-md border border-gray-200">
              <div className="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2">
                <h2 className="font-semibold">业务时间线</h2>
                <Clock className="size-4 text-gray-500" />
              </div>
              <div>
                {task.timeline.map((event) => (
                  <EventRow
                    key={event.id}
                    event={event}
                  />
                ))}
                {task.timeline.length === 0 && (
                  <div className="px-3 py-6 text-center text-sm text-gray-500">
                    暂无时间线
                  </div>
                )}
              </div>
            </section>

            <section className="mt-5 rounded-md border border-gray-200">
              <details>
                <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm font-medium">
                  <FileJson className="size-4" />
                  原始 JSON
                </summary>
                <pre className="max-h-96 overflow-auto border-t border-gray-100 bg-gray-50 p-3 text-xs">
                  {JSON.stringify(task.raw, null, 2)}
                </pre>
              </details>
            </section>
          </>
        )}
      </div>
    </WorkbenchShell>
  );
}
