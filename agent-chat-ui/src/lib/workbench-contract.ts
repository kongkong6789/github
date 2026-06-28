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
import type { Decision } from "../components/thread/agent-inbox/types";

export const WORKBENCH_METHODS = [
  "task.list",
  "task.show",
  "agent.trace",
  "data.health",
  "governance.policy",
  "approval.submit",
  "logs.tail",
  "evidence.graph",
  "source.list",
  "source.show",
  "source.sync",
] as const;

export const WORKBENCH_TASK_METHODS = ["task.list", "task.show"] as const;
export const WORKBENCH_SCOPE_FIELDS = [
  "thread_id",
  "task_id",
  "agent_id",
  "tool_name",
  "scope",
] as const;

export type WorkbenchMethod = (typeof WORKBENCH_METHODS)[number];
export type WorkbenchTaskMethod = (typeof WORKBENCH_TASK_METHODS)[number];
export type WorkbenchScopeField = (typeof WORKBENCH_SCOPE_FIELDS)[number];
export type WorkbenchScopeValue = "" | "global" | "thread" | "task" | string;

export type WorkbenchScopeParams = {
  thread_id?: string;
  threadId?: string;
  task_id?: string;
  taskId?: string;
  agent_id?: string;
  agentId?: string;
  tool_name?: string;
  toolName?: string;
  scope?: WorkbenchScopeValue;
};

export type WorkbenchTaskListParams = WorkbenchScopeParams & {
  status?: string;
  timeRange?: TaskTimeRange | string;
  type?: string;
  query?: string;
  limit?: number;
};

export type WorkbenchTaskShowParams = WorkbenchScopeParams & {
  task_id?: string;
  taskId?: string;
};

export type WorkbenchAgentTraceParams = WorkbenchScopeParams & {
  limit?: number;
};

export type WorkbenchDataHealthParams = WorkbenchScopeParams;
export type WorkbenchGovernancePolicyParams = WorkbenchScopeParams;

export type WorkbenchLogsTailParams = WorkbenchScopeParams & {
  source?: string;
  level?: string;
  risk_level?: string;
  riskLevel?: string;
  limit?: number;
};

export type WorkbenchEvidenceGraphParams = WorkbenchScopeParams & {
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

export type WorkbenchApprovalSubmitParams = WorkbenchScopeParams & {
  thread_id?: string;
  threadId?: string;
  decisions?: Decision[];
  decision?: Decision;
};

export type WorkbenchSourceListParams = WorkbenchScopeParams;

export type WorkbenchSourceShowParams = WorkbenchScopeParams & {
  source_id?: string;
  sourceId?: string;
};

export type WorkbenchSourceSyncParams = WorkbenchScopeParams & {
  source_id?: string;
  sourceId?: string;
};

export type WorkbenchApprovalSubmitResult = {
  status: "ready";
  thread_id: string;
  resume: {
    decisions: Decision[];
  };
  execution_mode: "approval_request_only";
};

export type WorkbenchRequestMap = {
  "task.list": WorkbenchTaskListParams;
  "task.show": WorkbenchTaskShowParams;
  "agent.trace": WorkbenchAgentTraceParams;
  "data.health": WorkbenchDataHealthParams;
  "governance.policy": WorkbenchGovernancePolicyParams;
  "approval.submit": WorkbenchApprovalSubmitParams;
  "logs.tail": WorkbenchLogsTailParams;
  "evidence.graph": WorkbenchEvidenceGraphParams;
  "source.list": WorkbenchSourceListParams;
  "source.show": WorkbenchSourceShowParams;
  "source.sync": WorkbenchSourceSyncParams;
};

export type WorkbenchResponseMap = {
  "task.list": TaskListResult;
  "task.show": TaskDetail;
  "agent.trace": AgentTraceResult;
  "data.health": DataHealthState;
  "governance.policy": GovernanceState;
  "approval.submit": WorkbenchApprovalSubmitResult;
  "logs.tail": LogsState;
  "evidence.graph": EvidenceGraphState;
  "source.list": DataSourcesState;
  "source.show": DataSourceSummary;
  "source.sync": {
    result: SourceSyncResult;
    state: DataSourcesState;
  };
};

export type WorkbenchResponseFor<TMethod extends WorkbenchMethod> =
  WorkbenchResponseMap[TMethod];

export type WorkbenchParamsFor<TMethod extends WorkbenchMethod> =
  WorkbenchRequestMap[TMethod];

export type WorkbenchError = {
  code: string;
  message: string;
  hint: string;
  retryable: boolean;
  source: string;
  details?: unknown;
};

export type WorkbenchEnvelope<TData = unknown> =
  | {
      ok: true;
      method: WorkbenchMethod;
      request_id: string;
      generated_at: string;
      data: TData;
      error: null;
      warnings: string[];
    }
  | {
      ok: false;
      method: WorkbenchMethod;
      request_id: string;
      generated_at: string;
      data: null;
      error: WorkbenchError;
      warnings: string[];
    };

type EnvelopeOptions = {
  requestId?: string;
  generatedAt?: string;
  warnings?: string[];
};

type ErrorOptions = EnvelopeOptions & WorkbenchError;

export function isWorkbenchMethod(value: unknown): value is WorkbenchMethod {
  return (
    typeof value === "string" &&
    (WORKBENCH_METHODS as readonly string[]).includes(value)
  );
}

function requestId() {
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function generatedAt(value?: string) {
  return value || new Date().toISOString();
}

export function createWorkbenchSuccess<TData>(
  method: WorkbenchMethod,
  data: TData,
  options: EnvelopeOptions = {},
): WorkbenchEnvelope<TData> {
  return {
    ok: true,
    method,
    request_id: options.requestId || requestId(),
    generated_at: generatedAt(options.generatedAt),
    data,
    error: null,
    warnings: options.warnings ?? [],
  };
}

export function createWorkbenchError(
  method: WorkbenchMethod,
  options: ErrorOptions,
): WorkbenchEnvelope<never> {
  return {
    ok: false,
    method,
    request_id: options.requestId || requestId(),
    generated_at: generatedAt(options.generatedAt),
    data: null,
    error: {
      code: options.code,
      message: options.message,
      hint: options.hint,
      retryable: options.retryable,
      source: options.source,
      details: options.details,
    },
    warnings: options.warnings ?? [],
  };
}
