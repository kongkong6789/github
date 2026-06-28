"use client";

import Link from "next/link";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  Clock,
  DatabaseZap,
  FileDown,
  FileJson,
  FilePlus2,
  FileText,
  Globe2,
  History,
  LoaderCircle,
  PauseCircle,
  RefreshCw,
  Server,
  Upload,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  WorkbenchCard,
  WorkbenchPanel,
  WorkbenchShell,
} from "@/components/workbench/shell";
import type {
  DataSourceSummary,
  DataSourcesState,
  SourceSnapshot,
} from "@/lib/data-sources";
import {
  getWorkbenchDataSources,
  syncWorkbenchDataSource,
} from "@/lib/workbench-client";
import { cn } from "@/lib/utils";

type FilterKey = "all" | "active" | "failed" | "stale";

type SourceForm = {
  source_id: string;
  display_name: string;
  source_type: string;
  uri: string;
  allowed_root: string;
  sync_mode: string;
  owner: string;
  freshness_sla: string;
  sensitivity_level: string;
  credential_env_keys: string;
  metadata: string;
};

const emptyForm: SourceForm = {
  source_id: "",
  display_name: "",
  source_type: "local_file",
  uri: "",
  allowed_root: "",
  sync_mode: "on_demand",
  owner: "",
  freshness_sla: "24h",
  sensitivity_level: "internal",
  credential_env_keys: "",
  metadata: "{}",
};

const sourceTypes = [
  "local_file",
  "local_folder",
  "manual_upload",
  "wecom_wedrive_file",
  "wecom_wedrive_folder",
  "wecom_smartsheet",
  "erp_readonly_snapshot",
  "api_pull",
  "mcp_readonly_tool",
  "agent_reach_public_web",
  "agent_reach_public_search",
  "agent_reach_public_video",
  "agent_reach_social",
];

const statusLabels: Record<string, string> = {
  active: "启用",
  fresh: "新鲜",
  success: "成功",
  failed: "失败",
  stale: "过期",
  never_synced: "未同步",
  paused: "暂停",
  disabled: "禁用",
  archived: "归档",
  skipped_unchanged: "无变化",
  changed: "有变化",
  unchanged: "无变化",
  unknown: "未知",
};

const filterLabels: Record<FilterKey, string> = {
  all: "全部",
  active: "启用",
  failed: "失败",
  stale: "过期",
};

const sourceTypeLabels: Record<string, string> = {
  local_file: "本地文件",
  local_folder: "本地文件夹",
  manual_upload: "手工上传",
  wecom_wedrive_file: "企业微信微盘文件",
  wecom_wedrive_folder: "企业微信微盘文件夹",
  wecom_smartsheet: "企业微信智能表格",
  erp_readonly_snapshot: "ERP 只读快照",
  api_pull: "API 拉取",
  mcp_readonly_tool: "MCP 只读工具",
  agent_reach_public_web: "公开网页",
  agent_reach_public_search: "公开搜索",
  agent_reach_public_video: "公开视频字幕",
  agent_reach_social: "需确认的社媒资料",
};

const syncModeLabels: Record<string, string> = {
  on_demand: "按需同步",
  manual: "手动同步",
  polling: "轮询同步",
  webhook_placeholder: "Webhook 占位",
};

const sensitivityLabels: Record<string, string> = {
  public: "公开",
  internal: "内部",
  confidential: "保密",
  restricted: "受限",
};

const statusClass: Record<string, string> = {
  active: "border-emerald-200 bg-emerald-50 text-emerald-700",
  fresh: "border-emerald-200 bg-emerald-50 text-emerald-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  failed: "border-rose-200 bg-rose-50 text-rose-700",
  stale: "border-amber-200 bg-amber-50 text-amber-700",
  never_synced: "border-amber-200 bg-amber-50 text-amber-700",
  paused: "border-blue-200 bg-blue-50 text-blue-700",
  disabled: "border-slate-200 bg-slate-50 text-slate-600",
  archived: "border-slate-200 bg-slate-50 text-slate-600",
  skipped_unchanged: "border-slate-200 bg-slate-50 text-slate-600",
  changed: "border-amber-200 bg-amber-50 text-amber-700",
  unchanged: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

const fieldClass =
  "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-blue-400 focus:ring-3 focus:ring-blue-100";
const monoFieldClass = cn(fieldClass, "font-mono");
const compactMonoFieldClass =
  "h-9 rounded-md border border-slate-300 bg-white px-3 font-mono text-xs text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:ring-3 focus:ring-blue-100";
const textareaClass =
  "min-h-24 w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-950 outline-none transition focus:border-blue-400 focus:ring-3 focus:ring-blue-100";

function formatTime(value: string | undefined) {
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

function truncateHash(value: string | undefined) {
  return value ? value.slice(0, 12) : "-";
}

function StatusIcon({ status }: { status: string }) {
  if (["active", "fresh", "success"].includes(status)) {
    return <CheckCircle2 className="size-3.5" />;
  }
  if (["paused", "disabled", "archived"].includes(status)) {
    return <PauseCircle className="size-3.5" />;
  }
  if (["failed"].includes(status)) return <XCircle className="size-3.5" />;
  return <CircleAlert className="size-3.5" />;
}

function Badge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium",
        statusClass[status] ?? statusClass.disabled,
      )}
    >
      <StatusIcon status={status} />
      {statusLabels[status] ?? (status || "未知")}
    </span>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  tone = "muted",
  icon,
}: {
  title: string;
  value: string | number;
  subtitle: string;
  tone?: "ok" | "warn" | "bad" | "muted" | "running";
  icon: ReactNode;
}) {
  return (
    <WorkbenchCard
      className={cn(
        "min-h-[7.5rem]",
        tone === "ok" && "border-emerald-200 bg-emerald-50",
        tone === "warn" && "border-amber-200 bg-amber-50",
        tone === "bad" && "border-rose-200 bg-rose-50",
        tone === "running" && "border-blue-200 bg-blue-50",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-slate-600">{title}</div>
        <div className="text-blue-300">{icon}</div>
      </div>
      <div className="mt-3 text-2xl leading-tight font-semibold break-words text-slate-950">
        {value}
      </div>
      <div className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">
        {subtitle}
      </div>
    </WorkbenchCard>
  );
}

function fieldSet(snapshot: SourceSnapshot | null) {
  return Object.entries(snapshot?.schema ?? {}).flatMap(([sheet, fields]) =>
    fields.map((field) => `${sheet}.${field}`),
  );
}

function SourceDetails({
  source,
  snapshots,
  syncing,
  onSync,
  onStatus,
  onRebind,
}: {
  source: DataSourceSummary | null;
  snapshots: SourceSnapshot[];
  syncing: boolean;
  onSync: (sourceId: string) => void;
  onStatus: (sourceId: string, status: string) => void;
  onRebind: (sourceId: string, uri: string, allowedRoot: string) => void;
}) {
  const [rebindUri, setRebindUri] = useState("");
  const [rebindRoot, setRebindRoot] = useState("");

  useEffect(() => {
    setRebindUri(source?.uri ?? "");
    setRebindRoot(source?.allowed_root ?? "");
  }, [source?.allowed_root, source?.source_id, source?.uri]);

  if (!source) {
    return (
      <WorkbenchPanel className="p-6 text-sm text-slate-400">
        尚未选择资料来源。
      </WorkbenchPanel>
    );
  }
  const sourceSnapshots = snapshots.filter(
    (snapshot) => snapshot.source_id === source.source_id,
  );
  const latest = source.last_snapshot;
  const datasetSlug = latest?.duckdb_dataset_slug ?? "";
  const fields = fieldSet(latest);
  const nextStatus = source.status === "active" ? "paused" : "active";
  return (
    <WorkbenchPanel>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 p-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-950">
              {source.display_name}
            </h2>
            <Badge status={source.status} />
            <Badge status={source.freshness_status} />
          </div>
          <div className="mt-1 text-sm break-all text-slate-400">
            {source.source_id} ·{" "}
            {sourceTypeLabels[source.source_type] ?? source.source_type} ·{" "}
            {source.owner || "未填写负责人"}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            asChild
            variant="outline"
          >
            <Link
              href={
                datasetSlug
                  ? `/data-health?dataset=${encodeURIComponent(datasetSlug)}`
                  : "/data-health"
              }
            >
              <DatabaseZap className="size-4" />
              最新数据集
            </Link>
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => onStatus(source.source_id, nextStatus)}
          >
            {nextStatus === "paused" ? (
              <PauseCircle className="size-4" />
            ) : (
              <CheckCircle2 className="size-4" />
            )}
            {nextStatus === "paused" ? "暂停" : "恢复"}
          </Button>
          <Button
            type="button"
            onClick={() => onSync(source.source_id)}
            disabled={syncing || source.status !== "active"}
          >
            {syncing ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}
            立即同步
          </Button>
        </div>
      </div>

      <div className="grid gap-3 p-4 md:grid-cols-4">
        <StatCard
          title="最新快照"
          value={latest?.snapshot_id ?? "-"}
          subtitle={formatTime(latest?.observed_at)}
          tone={latest ? "ok" : "warn"}
          icon={<History className="size-5" />}
        />
        <StatCard
          title="行数"
          value={latest?.row_count ?? 0}
          subtitle={`快照 ${source.snapshot_count}`}
          tone="muted"
          icon={<FileText className="size-5" />}
        />
        <StatCard
          title="架构"
          value={statusLabels[source.schema_diff.status] ?? source.schema_diff.status}
          subtitle={`+${source.schema_diff.added_fields.length} / -${source.schema_diff.removed_fields.length}`}
          tone={source.schema_diff.status === "changed" ? "warn" : "ok"}
          icon={<FileJson className="size-5" />}
        />
        <StatCard
          title="SLA"
          value={source.freshness_sla || "-"}
          subtitle={`模式 ${syncModeLabels[source.sync_mode] ?? source.sync_mode}`}
          tone={source.freshness_status === "stale" ? "warn" : "muted"}
          icon={<Clock className="size-5" />}
        />
      </div>

      <div className="grid gap-4 border-t border-slate-200 p-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <div className="mb-2 text-sm font-semibold text-slate-700">
            接入约束
          </div>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">资源地址</dt>
              <dd className="mt-1 font-mono text-xs break-all text-slate-800">
                {source.uri || "-"}
              </dd>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">允许根目录</dt>
              <dd className="mt-1 font-mono text-xs break-all text-slate-800">
                {source.allowed_root || "-"}
              </dd>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">敏感级别</dt>
              <dd className="mt-1 text-slate-800">
                {sensitivityLabels[source.sensitivity_level] ??
                  source.sensitivity_level}
              </dd>
            </div>
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">
                凭据环境变量
              </dt>
              <dd className="mt-1 font-mono text-xs break-all text-slate-800">
                {source.credential_env_keys.join(", ") || "-"}
              </dd>
            </div>
          </dl>
          <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <input
              value={rebindUri}
              onChange={(event) => setRebindUri(event.target.value)}
              className={compactMonoFieldClass}
              aria-label="更新资料来源资源地址"
            />
            <input
              value={rebindRoot}
              onChange={(event) => setRebindRoot(event.target.value)}
              className={compactMonoFieldClass}
              aria-label="更新允许根目录"
            />
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                onRebind(source.source_id, rebindUri.trim(), rebindRoot.trim())
              }
            >
              <FileDown className="size-4" />
              更新路径
            </Button>
          </div>
        </div>

        <div>
          <div className="mb-2 text-sm font-semibold text-slate-700">
            架构差异
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50">
            <div className="grid grid-cols-2 gap-0 border-b border-slate-200 text-sm">
              <div className="border-r border-slate-200 p-3">
                <div className="text-xs text-slate-500">新增字段</div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {source.schema_diff.added_fields.length ? (
                    source.schema_diff.added_fields.map((field) => (
                      <span
                        key={field}
                        className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700"
                      >
                        {field}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">-</span>
                  )}
                </div>
              </div>
              <div className="p-3">
                <div className="text-xs text-slate-500">移除字段</div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {source.schema_diff.removed_fields.length ? (
                    source.schema_diff.removed_fields.map((field) => (
                      <span
                        key={field}
                        className="rounded bg-rose-50 px-1.5 py-0.5 text-xs text-rose-700"
                      >
                        {field}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">-</span>
                  )}
                </div>
              </div>
            </div>
            <div className="p-3 text-xs leading-5 text-slate-400">
              <div>
                当前 {truncateHash(source.schema_diff.current_schema_hash)}
              </div>
              <div>
                上版 {truncateHash(source.schema_diff.previous_schema_hash)}
              </div>
              <div>
                表 {source.schema_diff.changed_sheets.join(", ") || "-"}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-200 p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm font-semibold text-slate-700">
            快照历史
          </div>
          <div className="text-xs text-slate-500">{fields.length} 个字段</div>
        </div>
        <div className="workbench-scrollbar overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs text-slate-500">
              <tr>
                <th className="px-2 py-2">快照</th>
                <th className="px-2 py-2">观测时间</th>
                <th className="px-2 py-2">行数</th>
                <th className="px-2 py-2">架构</th>
                <th className="px-2 py-2">原始路径</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {sourceSnapshots.map((snapshot) => (
                <tr key={snapshot.snapshot_id}>
                  <td className="px-2 py-2 font-mono text-xs">
                    {snapshot.snapshot_id}
                  </td>
                  <td className="px-2 py-2">
                    {formatTime(snapshot.observed_at)}
                  </td>
                  <td className="px-2 py-2">{snapshot.row_count ?? 0}</td>
                  <td className="px-2 py-2 font-mono text-xs">
                    {truncateHash(snapshot.schema_hash)}
                  </td>
                  <td className="max-w-[24rem] truncate px-2 py-2 font-mono text-xs">
                    {snapshot.raw_snapshot_path || "-"}
                  </td>
                </tr>
              ))}
              {!sourceSnapshots.length && (
                <tr>
                  <td
                    className="px-2 py-6 text-slate-500"
                    colSpan={5}
                  >
                    暂无快照。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </WorkbenchPanel>
  );
}

export default function DataSourcesPage() {
  const [state, setState] = useState<DataSourcesState | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [loading, setLoading] = useState(false);
  const [syncingId, setSyncingId] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<SourceForm>(emptyForm);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getWorkbenchDataSources();
      setState(next);
      setSelectedId((current) => current || next.sources[0]?.source_id || "");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "请求失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredSources = useMemo(() => {
    const sources = state?.sources ?? [];
    if (filter === "active") {
      return sources.filter((source) => source.status === "active");
    }
    if (filter === "failed") {
      return sources.filter(
        (source) =>
          source.status === "failed" || source.freshness_status === "failed",
      );
    }
    if (filter === "stale") {
      return sources.filter((source) =>
        ["stale", "never_synced"].includes(source.freshness_status),
      );
    }
    return sources;
  }, [filter, state]);

  const selected =
    state?.sources.find((source) => source.source_id === selectedId) ??
    filteredSources[0] ??
    null;

  async function syncSource(sourceId: string) {
    setSyncingId(sourceId);
    setError("");
    setNotice("");
    try {
      const result = await syncWorkbenchDataSource(sourceId);
      setState(result.state);
      setSelectedId(sourceId);
      setNotice(
        result.result.status === "success"
          ? `已同步 ${sourceId}：${result.result.snapshot_id}`
          : `${sourceId}: ${result.result.status}`,
      );
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : "同步失败。");
    } finally {
      setSyncingId("");
    }
  }

  async function setSourceStatus(sourceId: string, status: string) {
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/data-sources", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "status", source_id: sourceId, status }),
      });
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(
          payload.error || payload.result?.error || "状态更新失败。",
        );
      }
      setState(payload.state as DataSourcesState);
      setNotice(`${sourceId}：已切换为 ${statusLabels[status] ?? status}`);
    } catch (statusError) {
      setError(
        statusError instanceof Error ? statusError.message : "状态更新失败。",
      );
    }
  }

  async function rebindSource(
    sourceId: string,
    uri: string,
    allowedRoot: string,
  ) {
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/data-sources", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: "rebind",
          source_id: sourceId,
          uri,
          allowed_root: allowedRoot,
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(
          payload.error || payload.result?.error || "路径更新失败。",
        );
      }
      setState(payload.state as DataSourcesState);
      setNotice(`${sourceId}：路径已更新`);
    } catch (rebindError) {
      setError(
        rebindError instanceof Error ? rebindError.message : "路径更新失败。",
      );
    }
  }

  async function registerSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const metadata = form.metadata.trim() ? JSON.parse(form.metadata) : {};
      const response = await fetch("/api/data-sources", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          action: "register",
          source: {
            ...form,
            credential_env_keys: form.credential_env_keys
              .split(/[,;\s]+/)
              .map((item) => item.trim())
              .filter(Boolean),
            metadata,
          },
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || payload.result?.error || "注册失败。");
      }
      setState(payload.state as DataSourcesState);
      setSelectedId(form.source_id);
      setForm(emptyForm);
      setNotice(`已登记 ${form.source_id}`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "注册失败。");
    } finally {
      setSaving(false);
    }
  }

  function updateForm(key: keyof SourceForm, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  const counts = state?.counts;
  const sourceTone =
    (counts?.failed_sources ?? 0) > 0
      ? "bad"
      : (counts?.schema_drift_count ?? 0) > 0 ||
          (counts?.stale_sources ?? 0) > 0
        ? "warn"
        : (counts?.sources ?? 0) > 0
          ? "ok"
          : "muted";
  const sourceTypeOptions = useMemo(
    () =>
      Array.from(
        new Set([...(state?.supported_source_types ?? []), ...sourceTypes]),
      ),
    [state?.supported_source_types],
  );

  return (
    <WorkbenchShell
      title="导入资料"
      description="登记表格、文件夹、企业微信、ERP 或只读接口，让系统能持续读取业务资料。"
      status={
        <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700">
          {state ? "注册表就绪" : loading ? "读取中" : "等待数据"}
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
            <Link href="/data-health">
              <Activity className="size-4" />
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

        {(error || notice) && (
          <div
            className={cn(
              "mb-4 rounded-md border px-3 py-2 text-sm",
              error
                ? "border-amber-200 bg-amber-50 text-amber-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-700",
            )}
          >
            {error || notice}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <StatCard
            title="资料来源"
            value={counts?.sources ?? 0}
            subtitle={`启用 ${counts?.active_sources ?? 0} / 失败 ${counts?.failed_sources ?? 0}`}
            tone={sourceTone}
            icon={<DatabaseZap className="size-5" />}
          />
          <StatCard
            title="快照版本"
            value={counts?.snapshots ?? 0}
            subtitle={state?.source_files.snapshot_manifest_path ?? "-"}
            tone="muted"
            icon={<FileDown className="size-5" />}
          />
          <StatCard
            title="架构漂移"
            value={counts?.schema_drift_count ?? 0}
            subtitle={`过期 ${counts?.stale_sources ?? 0}`}
            tone={(counts?.schema_drift_count ?? 0) > 0 ? "warn" : "ok"}
            icon={<FileJson className="size-5" />}
          />
          <StatCard
            title="暂停"
            value={counts?.paused_sources ?? 0}
            subtitle="暂停 / 禁用 / 归档"
            tone={(counts?.paused_sources ?? 0) > 0 ? "running" : "muted"}
            icon={<PauseCircle className="size-5" />}
          />
          <StatCard
            title="注册表"
            value={state ? "就绪" : loading ? "读取中" : "-"}
            subtitle={state?.source_files.registry_path ?? "-"}
            tone={state ? "ok" : "muted"}
            icon={<Server className="size-5" />}
          />
          <StatCard
            title="原始区"
            value={state?.source_files.raw_dir ? "快照" : "-"}
            subtitle={state?.source_files.raw_dir ?? "-"}
            tone="muted"
            icon={<Upload className="size-5" />}
          />
        </div>

        <div className="mt-6 grid gap-5 xl:grid-cols-[24rem_1fr]">
          <WorkbenchPanel className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 p-3">
              <div className="text-sm font-semibold text-slate-950">
                资料来源总览
              </div>
              <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5">
                {(["all", "active", "failed", "stale"] as FilterKey[]).map(
                  (item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => setFilter(item)}
                      className={cn(
                        "rounded px-2 py-1 text-xs font-medium",
                        filter === item
                          ? "bg-blue-700 text-white"
                          : "text-slate-600 hover:bg-white hover:text-slate-950",
                      )}
                    >
                      {filterLabels[item]}
                    </button>
                  ),
                )}
              </div>
            </div>
            <div className="workbench-scrollbar max-h-[42rem] divide-y divide-slate-100 overflow-auto">
              {filteredSources.map((source) => (
                <button
                  key={source.source_id}
                  type="button"
                  onClick={() => setSelectedId(source.source_id)}
                  className={cn(
                    "block w-full p-3 text-left transition hover:bg-slate-50",
                    selected?.source_id === source.source_id &&
                      "bg-blue-50 ring-1 ring-blue-200 ring-inset",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-slate-950">
                        {source.display_name}
                      </div>
                      <div className="mt-1 truncate font-mono text-xs text-slate-500">
                        {source.source_id}
                      </div>
                    </div>
                    <Badge status={source.status} />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1">
                    <Badge status={source.freshness_status} />
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                      {sourceTypeLabels[source.source_type] ??
                        source.source_type}
                    </span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                      {source.snapshot_count} 个快照
                    </span>
                  </div>
                </button>
              ))}
              {!filteredSources.length && (
                <div className="p-5 text-sm text-slate-500">暂无资料来源。</div>
              )}
            </div>
          </WorkbenchPanel>

          <SourceDetails
            source={selected}
            snapshots={state?.snapshots ?? []}
            syncing={syncingId === selected?.source_id}
            onSync={syncSource}
            onStatus={setSourceStatus}
            onRebind={rebindSource}
          />
        </div>

        <WorkbenchPanel className="mt-6 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Globe2 className="size-4 text-blue-600" />
                <h2 className="text-lg font-semibold text-slate-950">
                  外部公开资料
                </h2>
              </div>
              <div className="mt-1 text-sm text-slate-500">
                登记网页、RSS、GitHub、公开视频字幕和需要人工确认的社媒公开内容；进入依据来源后再参与经营分析。
              </div>
            </div>
            <Button
              asChild
              variant="outline"
              className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            >
              <Link href="/governance?tab=mcp">
                <Server className="size-4" />
                系统连接
              </Link>
            </Button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            {[
              ["agent_reach_public_web", "网页/文章", "公开 URL，只读读取正文和标题。"],
              ["agent_reach_public_search", "公开搜索", "保存查询词、结果链接和采集时间。"],
              ["agent_reach_public_video", "视频字幕", "公开视频字幕或播客转写文本。"],
              ["agent_reach_social", "社媒资料", "登录态渠道需人工确认和专用账号。"],
            ].map(([type, title, summary]) => (
              <div
                key={type}
                className="rounded-md border border-slate-200 bg-slate-50 p-3"
              >
                <div className="text-sm font-semibold text-slate-950">
                  {title}
                </div>
                <div className="mt-1 text-xs leading-5 text-slate-500">
                  {summary}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setForm((current) => ({
                      ...current,
                      source_type: type,
                      sync_mode: "manual",
                      sensitivity_level:
                        type === "agent_reach_social"
                          ? "restricted"
                          : "public",
                    }))
                  }
                  className="mt-3 rounded border border-blue-200 bg-white px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50"
                >
                  填入类型
                </button>
              </div>
            ))}
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel className="mt-6 overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-200 p-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">
                登记资料来源
              </h2>
              <div className="text-sm text-slate-500">
                资料来源注册表 ·{" "}
                {sourceTypeOptions.length}{" "}
                种类型
              </div>
            </div>
            <FilePlus2 className="size-5 text-blue-400" />
          </div>
          <form
            onSubmit={registerSource}
            className="grid gap-3 p-4 lg:grid-cols-4"
          >
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                资料来源 ID
              </span>
              <input
                value={form.source_id}
                onChange={(event) =>
                  updateForm("source_id", event.target.value)
                }
                className={fieldClass}
                required
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                显示名称
              </span>
              <input
                value={form.display_name}
                onChange={(event) =>
                  updateForm("display_name", event.target.value)
                }
                className={fieldClass}
                required
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">类型</span>
              <select
                value={form.source_type}
                onChange={(event) =>
                  updateForm("source_type", event.target.value)
                }
                className={fieldClass}
              >
                {sourceTypeOptions.map((type) => (
                  <option
                    key={type}
                    value={type}
                  >
                    {sourceTypeLabels[type] ?? type}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                同步模式
              </span>
              <select
                value={form.sync_mode}
                onChange={(event) =>
                  updateForm("sync_mode", event.target.value)
                }
                className={fieldClass}
              >
                <option value="on_demand">按需同步</option>
                <option value="manual">手动同步</option>
                <option value="polling">轮询同步</option>
                <option value="webhook_placeholder">Webhook 占位</option>
              </select>
            </label>
            <label className="text-sm lg:col-span-2">
              <span className="mb-1 block font-medium text-slate-700">
                资源地址
              </span>
              <input
                value={form.uri}
                onChange={(event) => updateForm("uri", event.target.value)}
                className={monoFieldClass}
              />
            </label>
            <label className="text-sm lg:col-span-2">
              <span className="mb-1 block font-medium text-slate-700">
                允许根目录
              </span>
              <input
                value={form.allowed_root}
                onChange={(event) =>
                  updateForm("allowed_root", event.target.value)
                }
                className={monoFieldClass}
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                负责人
              </span>
              <input
                value={form.owner}
                onChange={(event) => updateForm("owner", event.target.value)}
                className={fieldClass}
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                新鲜度 SLA
              </span>
              <input
                value={form.freshness_sla}
                onChange={(event) =>
                  updateForm("freshness_sla", event.target.value)
                }
                className={fieldClass}
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                敏感级别
              </span>
              <select
                value={form.sensitivity_level}
                onChange={(event) =>
                  updateForm("sensitivity_level", event.target.value)
                }
                className={fieldClass}
              >
                <option value="internal">内部</option>
                <option value="confidential">保密</option>
                <option value="restricted">受限</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                凭据环境变量
              </span>
              <input
                value={form.credential_env_keys}
                onChange={(event) =>
                  updateForm("credential_env_keys", event.target.value)
                }
                className={monoFieldClass}
              />
            </label>
            <label className="text-sm lg:col-span-4">
              <span className="mb-1 block font-medium text-slate-700">
                元数据 JSON
              </span>
              <textarea
                value={form.metadata}
                onChange={(event) => updateForm("metadata", event.target.value)}
                className={textareaClass}
              />
            </label>
            <div className="flex flex-wrap items-center gap-2 lg:col-span-4">
              <Button
                type="submit"
                disabled={saving}
              >
                {saving ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <FilePlus2 className="size-4" />
                )}
                登记
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setForm(emptyForm)}
              >
                <XCircle className="size-4" />
                重置
              </Button>
            </div>
          </form>
        </WorkbenchPanel>
      </div>
    </WorkbenchShell>
  );
}
