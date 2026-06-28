"use client";

import { useEffect, useState } from "react";
import { Activity, ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getWorkbenchAgentTrace } from "@/lib/workbench-client";
import { cn } from "@/lib/utils";

type TraceEvent = {
  id: string;
  source: "message" | "task" | "audit";
  timestamp?: string;
  taskId?: string;
  agent?: string;
  kind: string;
  name: string;
  status?: string;
  summary?: string;
  args?: unknown;
  result?: unknown;
  evidence?: string[];
  risks?: string[];
};

type TraceResponse = {
  status: string;
  counts: { total: number; message: number; task: number; audit: number };
  events: TraceEvent[];
};

function compactJson(value: unknown) {
  if (value === undefined || value === null || value === "") return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

export function AgentTracePanel({ threadId }: { threadId: string | null }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TraceResponse | null>(null);
  const [error, setError] = useState("");

  async function load() {
    if (!threadId) return;
    setLoading(true);
    setError("");
    try {
      setData(
        (await getWorkbenchAgentTrace({
          thread_id: threadId,
          limit: 80,
        })) as TraceResponse,
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Workbench 请求失败。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setData(null);
    setError("");
    setOpen(false);
    if (threadId) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

  useEffect(() => {
    if (open && threadId) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, threadId]);

  if (!threadId || data?.counts.total === 0) return null;

  const events = data?.events ?? [];

  return (
    <div className="mx-auto w-full max-w-3xl rounded-md border border-gray-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm font-medium"
      >
        <span className="flex items-center gap-2">
          <Activity className="size-4" />
          Agent 执行 trace
          {data?.counts && (
            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
              {data.counts.total}
            </span>
          )}
        </span>
        {open ? (
          <ChevronUp className="size-4" />
        ) : (
          <ChevronDown className="size-4" />
        )}
      </button>
      {open && (
        <div className="border-t border-gray-100 p-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div className="text-xs text-gray-500">
              工具调用、后台任务、审计事件会聚合在这里。
            </div>
            <div className="flex items-center gap-2">
              <Button
                asChild
                size="sm"
                variant="outline"
              >
                <a href="/tasks">工作进度</a>
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={load}
                disabled={loading}
              >
                <RefreshCw
                  className={cn("size-3.5", loading && "animate-spin")}
                />
                刷新
              </Button>
            </div>
          </div>
          <div className="max-h-80 space-y-2 overflow-auto">
            {error ? (
              <div className="rounded bg-amber-50 p-3 text-sm text-amber-800">
                {error}
              </div>
            ) : events.length === 0 ? (
              <div className="rounded bg-gray-50 p-3 text-sm text-gray-500">
                暂无 trace 数据。
              </div>
            ) : (
              events.map((event) => (
                <div
                  key={event.id}
                  className="rounded border border-gray-100 bg-gray-50 p-2 text-xs"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-white px-1.5 py-0.5 font-medium">
                      {event.source}
                    </span>
                    <span className="font-semibold text-gray-900">
                      {event.name}
                    </span>
                    {event.status && (
                      <span className="text-gray-500">{event.status}</span>
                    )}
                    {event.agent && (
                      <span className="text-gray-500">{event.agent}</span>
                    )}
                  </div>
                  {event.summary && (
                    <div className="mt-1 line-clamp-3 text-gray-700">
                      {event.summary}
                    </div>
                  )}
                  {Boolean(event.args || event.result) && (
                    <pre className="mt-2 max-h-32 overflow-auto rounded bg-white p-2 text-[11px] text-gray-600">
                      {compactJson(event.args || event.result)}
                    </pre>
                  )}
                  {!!event.risks?.length && (
                    <div className="mt-1 text-amber-700">
                      风险：{event.risks.slice(0, 2).join("；")}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
