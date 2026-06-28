"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CircleAlert,
  Clock,
  DatabaseZap,
  FileText,
  Filter,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { WorkbenchShell } from "@/components/workbench/shell";
import { cn } from "@/lib/utils";
import { listWorkbenchTasks } from "@/lib/workbench-client";
import type { TaskListResult, TaskSummary } from "@/lib/tasks";

const STATUS_OPTIONS = [
  ["all", "全部状态"],
  ["created", "已创建"],
  ["queued", "排队中"],
  ["running", "运行中"],
  ["warning", "有预警"],
  ["success", "成功"],
  ["failed", "失败"],
  ["cancelled", "已取消"],
  ["recoverable", "可恢复"],
] as const;

const TIME_OPTIONS = [
  ["all", "全部时间"],
  ["today", "今天"],
  ["7d", "7 天"],
  ["30d", "30 天"],
] as const;

const TYPE_OPTIONS = [
  ["all", "全部类型"],
  ["资料整理", "资料整理"],
  ["表格清洗", "表格清洗"],
  ["LightRAG 同步", "LightRAG 同步"],
  ["经营分析", "经营分析"],
  ["老板报告", "老板报告"],
  ["ERP 只读查询", "ERP 只读查询"],
] as const;

const STATUS_CLASS: Record<string, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  running: "border-sky-200 bg-sky-50 text-sky-700",
  queued: "border-sky-200 bg-sky-50 text-sky-700",
  failed: "border-rose-200 bg-rose-50 text-rose-700",
  cancelled: "border-gray-200 bg-gray-50 text-gray-600",
  created: "border-gray-200 bg-gray-50 text-gray-600",
  unknown: "border-gray-200 bg-gray-50 text-gray-600",
};

const STATUS_LABEL: Record<string, string> = {
  success: "成功",
  warning: "有预警",
  running: "运行中",
  queued: "排队中",
  failed: "失败",
  cancelled: "已取消",
  created: "已创建",
  recoverable: "可恢复",
  unknown: "未知",
};

function formatTime(value: string) {
  if (!value) return "-";
  const parsed = Date.parse(value.includes("T") ? value : value.replace(" ", "T"));
  if (Number.isNaN(parsed)) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(parsed));
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium",
        STATUS_CLASS[status] ?? STATUS_CLASS.unknown,
      )}
    >
      {STATUS_LABEL[status] ?? (status || "未知")}
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

function progressColor(status: string) {
  if (status === "failed") return "bg-rose-500";
  if (status === "warning") return "bg-amber-500";
  if (status === "running" || status === "queued") return "bg-sky-500";
  if (status === "success") return "bg-emerald-500";
  return "bg-gray-300";
}

export default function TasksPage() {
  const [data, setData] = useState<TaskListResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("all");
  const [timeRange, setTimeRange] = useState("30d");
  const [type, setType] = useState("all");
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setData(
        await listWorkbenchTasks({
          status,
          timeRange,
          type,
          query: submittedQuery,
          limit: 80,
        }),
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, timeRange, type, submittedQuery]);

  const tasks = useMemo(() => data?.tasks ?? [], [data?.tasks]);
  const counts = useMemo(() => {
    const running = tasks.filter((task) => ["running", "queued"].includes(task.status)).length;
    const failed = tasks.filter((task) => task.status === "failed").length;
    const recoverable = tasks.filter((task) => task.recoverable).length;
    const reports = tasks.filter((task) => task.has_report).length;
    return { running, failed, recoverable, reports };
  }, [tasks]);

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    setSubmittedQuery(query.trim());
  }

  return (
    <WorkbenchShell
      title="工作进度"
      description="查看每个任务跑到哪一步、产出了什么报告，以及失败后能不能继续恢复。"
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

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Stat label="任务总数" value={data?.counts.returned ?? 0} />
          <Stat label="后台运行" value={counts.running} />
          <Stat label="可恢复" value={counts.recoverable} />
          <Stat label="报告" value={counts.reports} />
          <Stat label="异常 JSON" value={data?.counts.invalid ?? 0} />
        </div>

        <section className="mt-5 rounded-md border border-gray-200 p-3">
          <form className="flex flex-col gap-3 lg:flex-row lg:items-center" onSubmit={submitSearch}>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <Search className="size-4 shrink-0 text-gray-500" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索任务 ID、目标、报告名、知识库页面"
                className="min-w-0"
              />
              <Button type="submit" variant="outline">
                搜索
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Filter className="size-4 text-gray-500" />
              <select
                className="h-9 rounded-md border border-gray-200 bg-white px-2 text-sm"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              >
                {STATUS_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-md border border-gray-200 bg-white px-2 text-sm"
                value={timeRange}
                onChange={(event) => setTimeRange(event.target.value)}
              >
                {TIME_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-md border border-gray-200 bg-white px-2 text-sm"
                value={type}
                onChange={(event) => setType(event.target.value)}
              >
                {TYPE_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </form>
        </section>

        {error && (
          <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {(data?.invalid_tasks.length ?? 0) > 0 && (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            <div className="flex items-center gap-2 font-medium">
              <CircleAlert className="size-4" />
              有 {data?.invalid_tasks.length} 个任务 JSON 无法解析，已跳过。
            </div>
          </div>
        )}

        <section className="mt-5 overflow-hidden rounded-md border border-gray-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="px-3 py-2">任务</th>
                <th className="px-3 py-2">状态</th>
                <th className="px-3 py-2">类型</th>
                <th className="px-3 py-2">进度</th>
                <th className="px-3 py-2">风险/产物</th>
                <th className="px-3 py-2">更新时间</th>
                <th className="px-3 py-2">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tasks.map((task: TaskSummary) => (
                <tr key={task.task_id} className="align-top">
                  <td className="max-w-xl px-3 py-3">
                    <Link
                      href={`/tasks/${encodeURIComponent(task.task_id)}`}
                      className="font-medium text-blue-700 hover:underline"
                    >
                      {task.task_id}
                    </Link>
                    <div className="mt-1 line-clamp-2 text-gray-600">{task.original_user_text || task.goal}</div>
                    <div className="mt-1 text-xs text-gray-500">{task.requested_by || "-"}</div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-col gap-1">
                      <StatusBadge status={task.status} />
                      {task.recoverable && (
                        <span className="text-xs text-sky-700">可恢复</span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-3 text-gray-700">{task.task_type}</td>
                  <td className="min-w-36 px-3 py-3">
                    <div className="text-xs text-gray-500">
                      {task.progress.completed}/{task.progress.total} / {task.steps_count} 步骤
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100">
                      <div
                        className={cn("h-full rounded-full", progressColor(task.status))}
                        style={{ width: `${task.progress.percent}%` }}
                      />
                    </div>
                  </td>
                  <td className="px-3 py-3 text-gray-600">
                    <div>{task.risk_count} 个风险</div>
                    <div>{task.artifact_count} 个产物</div>
                    {task.has_report && <div className="text-emerald-700">报告</div>}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-gray-500">
                    <Clock className="mr-1 inline size-3.5" />
                    {formatTime(task.updated_at)}
                  </td>
                  <td className="px-3 py-3">
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/tasks/${encodeURIComponent(task.task_id)}`}>
                        <FileText className="size-4" />
                        详情
                      </Link>
                    </Button>
                  </td>
                </tr>
              ))}
              {!loading && tasks.length === 0 && (
                <tr>
                  <td className="px-3 py-10 text-center text-sm text-gray-500" colSpan={7}>
                    暂无任务。把资料放入项目 `raw/` 后，在对话页发起整理、清洗或经营分析任务。
                  </td>
                </tr>
              )}
              {loading && tasks.length === 0 && (
                <tr>
                  <td className="px-3 py-10 text-center text-sm text-gray-500" colSpan={7}>
                    正在读取工作进度...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        <div className="mt-4 flex items-center gap-2 text-xs text-gray-500">
          <SlidersHorizontal className="size-4" />
          任务页使用工作台协议：`task.list` / `task.show`。
        </div>
      </div>
    </WorkbenchShell>
  );
}
