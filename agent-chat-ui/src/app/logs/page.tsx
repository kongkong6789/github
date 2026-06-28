"use client";

import Link from "next/link";
import {
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  FileText,
  Filter,
  LoaderCircle,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { WorkbenchShell } from "@/components/workbench/shell";
import { tailWorkbenchLogs } from "@/lib/workbench-client";
import { cn } from "@/lib/utils";

type LogEntry = {
  id: string;
  source: string;
  source_label: string;
  level: "debug" | "info" | "warn" | "error" | "unknown";
  timestamp: string;
  message: string;
  thread_id: string;
  task_id: string;
  agent_id: string;
  tool_name: string;
  risk_level: string;
  file_path: string;
};

type LogSource = {
  source: string;
  label: string;
  path: string;
  status: "ok" | "missing" | "skipped" | "error";
  line_count: number;
  invalid_json_count: number;
  updated_at: string;
  error: string;
};

type LogsState = {
  checked_at: string;
  limit: number;
  filters: Record<string, string>;
  sources: LogSource[];
  entries: LogEntry[];
};

type Filters = {
  source: string;
  level: string;
  thread_id: string;
  task_id: string;
  agent_id: string;
  tool_name: string;
  risk_level: string;
};

const emptyFilters: Filters = {
  source: "",
  level: "",
  thread_id: "",
  task_id: "",
  agent_id: "",
  tool_name: "",
  risk_level: "",
};

const levelClass: Record<LogEntry["level"], string> = {
  debug: "border-gray-200 bg-gray-50 text-gray-600",
  info: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warn: "border-amber-200 bg-amber-50 text-amber-700",
  error: "border-rose-200 bg-rose-50 text-rose-700",
  unknown: "border-gray-200 bg-gray-50 text-gray-600",
};

const levelLabel: Record<LogEntry["level"], string> = {
  debug: "调试",
  info: "信息",
  warn: "预警",
  error: "错误",
  unknown: "未知",
};

const filterLabels: Record<keyof Filters, string> = {
  source: "日志源",
  level: "级别",
  thread_id: "对话 ID",
  task_id: "任务 ID",
  agent_id: "Agent ID",
  tool_name: "工具名",
  risk_level: "风险级别",
};

const sourceStatusLabel: Record<LogSource["status"], string> = {
  ok: "正常",
  missing: "缺失",
  skipped: "跳过",
  error: "错误",
};

function StatBand({
  title,
  value,
  subtitle,
  tone = "muted",
  icon,
}: {
  title: string;
  value: string | number;
  subtitle: string;
  tone?: "ok" | "warn" | "bad" | "muted";
  icon: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-md border px-4 py-3",
        tone === "ok" && "border-emerald-200 bg-emerald-50",
        tone === "warn" && "border-amber-200 bg-amber-50",
        tone === "bad" && "border-rose-200 bg-rose-50",
        tone === "muted" && "border-gray-200 bg-gray-50",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-gray-600">{title}</div>
        {icon}
      </div>
      <div className="mt-1 text-2xl font-semibold text-gray-950">{value}</div>
      <div className="mt-1 text-xs text-gray-600">{subtitle}</div>
    </div>
  );
}

function StatusIcon({ status }: { status: LogSource["status"] }) {
  if (status === "ok")
    return <CheckCircle2 className="size-4 text-emerald-600" />;
  if (status === "error") return <XCircle className="size-4 text-rose-600" />;
  return <CircleAlert className="size-4 text-amber-600" />;
}

function LevelBadge({ level }: { level: LogEntry["level"] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium",
        levelClass[level],
      )}
    >
      {levelLabel[level] ?? level}
    </span>
  );
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

function compact(value: string) {
  return value || "-";
}

export default function LogsPage() {
  const [state, setState] = useState<LogsState | null>(null);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (nextFilters: Filters) => {
    setLoading(true);
    setError("");
    try {
      setState((await tailWorkbenchLogs(nextFilters)) as LogsState);
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : "Workbench 请求失败。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(emptyFilters);
  }, [load]);

  const sourceOptions = useMemo(
    () => state?.sources.map((source) => source.source) ?? [],
    [state],
  );
  const sourceIssues =
    state?.sources.filter((source) =>
      ["missing", "error"].includes(source.status),
    ).length ?? 0;
  const errorCount =
    state?.entries.filter((entry) => entry.level === "error").length ?? 0;
  const warnCount =
    state?.entries.filter((entry) => entry.level === "warn").length ?? 0;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void load(filters);
  }

  function updateFilter(key: keyof Filters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  return (
    <WorkbenchShell
      title="问题排查"
      description="集中查看后端、前端、任务、工具和审计记录，快速定位失败原因。"
      actions={
        <>
          <Button
            type="button"
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            onClick={() => load(filters)}
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
              <Server className="size-4" />
              资料体检
            </Link>
          </Button>
          <Button
            asChild
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Link href="/governance?tab=skills">
              <ShieldCheck className="size-4" />
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

        <div
          className="grid gap-3"
          style={{
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          }}
        >
          <StatBand
            title="最近记录"
            value={state?.entries.length ?? "读取中"}
            subtitle={`上限 ${state?.limit ?? 200}`}
            tone="ok"
            icon={<FileText className="size-5" />}
          />
          <StatBand
            title="预警"
            value={warnCount}
            subtitle="当前筛选范围"
            tone={warnCount > 0 ? "warn" : "ok"}
            icon={<CircleAlert className="size-5" />}
          />
          <StatBand
            title="错误"
            value={errorCount}
            subtitle="当前筛选范围"
            tone={errorCount > 0 ? "bad" : "ok"}
            icon={<XCircle className="size-5" />}
          />
          <StatBand
            title="记录来源异常"
            value={sourceIssues}
            subtitle={
              state?.checked_at
                ? `检查 ${formatTime(state.checked_at)}`
                : "读取中"
            }
            tone={sourceIssues > 0 ? "warn" : "ok"}
            icon={<Server className="size-5" />}
          />
        </div>

        <section className="mt-6">
          <form
            onSubmit={submit}
            className="grid gap-3 rounded-md border border-gray-200 bg-gray-50 p-3"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            }}
          >
            <label className="grid gap-1 text-xs font-medium text-gray-600">
              记录来源
              <select
                className="h-9 rounded-md border border-gray-300 bg-white px-2 text-sm text-gray-950"
                value={filters.source}
                onChange={(event) => updateFilter("source", event.target.value)}
              >
                <option value="">全部</option>
                {sourceOptions.map((source) => (
                  <option
                    key={source}
                    value={source}
                  >
                    {source}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-xs font-medium text-gray-600">
              级别
              <select
                className="h-9 rounded-md border border-gray-300 bg-white px-2 text-sm text-gray-950"
                value={filters.level}
                onChange={(event) => updateFilter("level", event.target.value)}
              >
                <option value="">全部</option>
                <option value="debug">调试</option>
                <option value="info">信息</option>
                <option value="warn">预警</option>
                <option value="error">错误</option>
              </select>
            </label>
            {(
              [
                "thread_id",
                "task_id",
                "agent_id",
                "tool_name",
                "risk_level",
              ] as const
            ).map((key) => (
              <label
                key={key}
                className="grid gap-1 text-xs font-medium text-gray-600"
              >
                {filterLabels[key]}
                <input
                  className="h-9 rounded-md border border-gray-300 bg-white px-2 text-sm text-gray-950"
                  value={filters[key]}
                  onChange={(event) => updateFilter(key, event.target.value)}
                />
              </label>
            ))}
            <div className="flex items-end gap-2">
              <Button
                type="submit"
                className="h-9"
              >
                <Search className="size-4" />
                筛选
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-9"
                onClick={() => {
                  setFilters(emptyFilters);
                  void load(emptyFilters);
                }}
              >
                <Filter className="size-4" />
                清空
              </Button>
            </div>
          </form>
        </section>

        <section className="mt-6">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">记录来源</h2>
            {loading && (
              <LoaderCircle className="size-4 animate-spin text-gray-500" />
            )}
          </div>
          <div
            className="grid gap-2"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            }}
          >
            {(state?.sources ?? []).map((source) => (
              <div
                key={source.source}
                className="rounded-md border border-gray-200 p-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-gray-950">
                      {source.label}
                    </div>
                    <div className="truncate text-xs text-gray-500">
                      {source.path}
                    </div>
                  </div>
                  <StatusIcon status={source.status} />
                </div>
                <div className="mt-2 text-xs text-gray-600">
                  行数 {source.line_count} / 异常 JSON{" "}
                  {source.invalid_json_count} /{" "}
                  {sourceStatusLabel[source.status]}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">最近记录</h2>
            <div className="text-xs text-gray-500">
              {state?.entries.length ?? 0} 行
            </div>
          </div>
          <div className="overflow-x-auto rounded-md border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-3 py-2 font-medium">时间</th>
                  <th className="px-3 py-2 font-medium">来源</th>
                  <th className="px-3 py-2 font-medium">级别</th>
                  <th className="px-3 py-2 font-medium">上下文</th>
                  <th className="px-3 py-2 font-medium">消息</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {(state?.entries ?? []).map((entry) => (
                  <tr
                    key={entry.id}
                    className="align-top"
                  >
                    <td className="px-3 py-2 text-xs whitespace-nowrap text-gray-600">
                      {formatTime(entry.timestamp)}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap text-gray-700">
                      {entry.source}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <LevelBadge level={entry.level} />
                    </td>
                    <td className="min-w-52 px-3 py-2 text-xs text-gray-600">
                      <div>对话 {compact(entry.thread_id)}</div>
                      <div>任务 {compact(entry.task_id)}</div>
                      <div>Agent {compact(entry.agent_id)}</div>
                      <div>工具 {compact(entry.tool_name)}</div>
                    </td>
                    <td className="max-w-3xl px-3 py-2">
                      <pre className="font-mono text-xs leading-5 break-words whitespace-pre-wrap text-gray-800">
                        {entry.message}
                      </pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </WorkbenchShell>
  );
}
