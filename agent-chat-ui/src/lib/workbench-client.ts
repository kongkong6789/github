import type { AgentTraceResult } from "./agent-traces";
import type { DataHealthState } from "./data-health-state";
import type {
  DataSourceSummary,
  DataSourcesState,
  SourceSyncResult,
} from "./data-sources";
import type { EvidenceGraphState } from "./evidence-graph-shared";
import type { GovernanceState } from "./governance";
import type { LogsState } from "./logs";
import type { TaskDetail, TaskListResult, TaskTimeRange } from "./tasks";
import type {
  WorkbenchApprovalSubmitParams,
  WorkbenchApprovalSubmitResult,
  WorkbenchEnvelope,
  WorkbenchMethod,
  WorkbenchParamsFor,
  WorkbenchResponseFor,
} from "./workbench-contract";
import { createWorkbenchError } from "./workbench-contract";

type TaskListParams = {
  status?: string;
  timeRange?: TaskTimeRange | string;
  type?: string;
  query?: string;
  limit?: number;
  scope?: string;
};

type LogsTailParams = {
  source?: string;
  level?: string;
  thread_id?: string;
  task_id?: string;
  agent_id?: string;
  tool_name?: string;
  risk_level?: string;
  limit?: number;
  scope?: string;
};

type AgentTraceParams = {
  thread_id?: string;
  task_id?: string;
  limit?: number;
  scope?: string;
};

type EvidenceGraphParams = {
  scope?: string;
  task_id?: string;
  taskId?: string;
  report_path?: string;
  reportPath?: string;
  nodeTypes?: string[];
  node_types?: string[] | string;
  edgeTypes?: string[];
  edge_types?: string[] | string;
  limit?: number;
};

export class WorkbenchClientError extends Error {
  code: string;
  hint: string;
  retryable: boolean;
  source: string;
  details?: unknown;

  constructor(envelope: WorkbenchEnvelope<unknown>) {
    const error = envelope.error;
    super(error?.message || "Workbench 请求失败。");
    this.name = "WorkbenchClientError";
    this.code = error?.code || "workbench_request_failed";
    this.hint = error?.hint || "请稍后重试。";
    this.retryable = Boolean(error?.retryable);
    this.source = error?.source || "workbench";
    this.details = error?.details;
  }
}

function responsePreview(text: string) {
  return text.replace(/\s+/g, " ").trim().slice(0, 240);
}

async function parseWorkbenchEnvelope<TMethod extends WorkbenchMethod>(
  method: TMethod,
  response: Response,
): Promise<WorkbenchEnvelope<WorkbenchResponseFor<TMethod>>> {
  const text = await response.text();
  try {
    return JSON.parse(text) as WorkbenchEnvelope<WorkbenchResponseFor<TMethod>>;
  } catch {
    throw new WorkbenchClientError(
      createWorkbenchError(method, {
        code: "workbench_non_json_response",
        message: `Workbench 接口返回了非 JSON 响应（HTTP ${response.status}）。`,
        hint: "前端 dev server 可能返回了 HTML 错误页；请重启前端，或查看 frontend.err.log。",
        retryable: true,
        source: "workbench_client",
        details: {
          status: response.status,
          statusText: response.statusText,
          contentType: response.headers.get("content-type") || "",
          preview: responsePreview(text),
        },
      }),
    );
  }
}

export async function callWorkbench<TMethod extends WorkbenchMethod>(
  method: TMethod,
  params: WorkbenchParamsFor<TMethod> | Record<string, unknown> = {},
): Promise<WorkbenchResponseFor<TMethod>> {
  const response = await fetch("/api/workbench", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ method, params }),
    cache: "no-store",
  });
  const envelope = await parseWorkbenchEnvelope(method, response);
  if (!envelope.ok) {
    throw new WorkbenchClientError(envelope);
  }
  return envelope.data;
}

export function listWorkbenchTasks(params: TaskListParams = {}) {
  return callWorkbench("task.list", {
    scope: "global",
    ...params,
  }) as Promise<TaskListResult>;
}

export function showWorkbenchTask(taskId: string) {
  return callWorkbench("task.show", { taskId }) as Promise<TaskDetail>;
}

export function getWorkbenchAgentTrace(params: AgentTraceParams) {
  return callWorkbench("agent.trace", params) as Promise<AgentTraceResult>;
}

export function getWorkbenchDataHealth() {
  return callWorkbench("data.health", {
    scope: "global",
  }) as Promise<DataHealthState>;
}

export function getWorkbenchGovernancePolicy() {
  return callWorkbench("governance.policy", {
    scope: "global",
  }) as Promise<GovernanceState>;
}

export function tailWorkbenchLogs(params: LogsTailParams = {}) {
  return callWorkbench("logs.tail", {
    scope: "global",
    limit: 200,
    ...params,
  }) as Promise<LogsState>;
}

export function getWorkbenchEvidenceGraph(params: EvidenceGraphParams = {}) {
  return callWorkbench("evidence.graph", {
    scope: "global",
    limit: 300,
    ...params,
  }) as Promise<EvidenceGraphState>;
}

export function getWorkbenchDataSources() {
  return callWorkbench("source.list", {
    scope: "global",
  }) as Promise<DataSourcesState>;
}

export function showWorkbenchDataSource(sourceId: string) {
  return callWorkbench("source.show", {
    scope: "global",
    sourceId,
  }) as Promise<DataSourceSummary>;
}

export function syncWorkbenchDataSource(sourceId: string) {
  return callWorkbench("source.sync", {
    scope: "global",
    sourceId,
  }) as Promise<{ result: SourceSyncResult; state: DataSourcesState }>;
}

export function submitWorkbenchApproval(params: WorkbenchApprovalSubmitParams) {
  return callWorkbench(
    "approval.submit",
    params,
  ) as Promise<WorkbenchApprovalSubmitResult>;
}

export async function submitTaskAction(
  taskId: string,
  action: "cancel" | "recover",
) {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ action }),
    cache: "no-store",
  });
  const payload = await response.json();
  if (!response.ok) {
    const message =
      typeof payload?.message === "string"
        ? payload.message
        : "Task action failed";
    throw new Error(message);
  }
  return payload as TaskDetail;
}
