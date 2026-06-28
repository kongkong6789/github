import path from "node:path";

import { loadAgentTraceState } from "./agent-traces";
import { loadDataHealthState, type DataHealthState } from "./data-health-state";
import {
  loadDataSourcesState,
  syncDataSourceNow,
  type DataSourcesState,
} from "./data-sources";
import {
  loadEvidenceGraphState,
  type EvidenceGraphState,
} from "./evidence-graph";
import {
  loadGovernanceState,
  type GovernanceAuditEvent,
  type GovernancePaths,
} from "./governance";
import { loadLogsState, type LogFilters } from "./logs";
import { loadTaskDetail, loadTaskList } from "./tasks";
import type {
  WorkbenchApprovalSubmitParams,
  WorkbenchApprovalSubmitResult,
  WorkbenchDataHealthParams,
  WorkbenchEvidenceGraphParams,
  WorkbenchGovernancePolicyParams,
  WorkbenchLogsTailParams,
  WorkbenchMethod,
  WorkbenchParamsFor,
  WorkbenchResponseFor,
  WorkbenchSourceListParams,
  WorkbenchSourceShowParams,
  WorkbenchSourceSyncParams,
  WorkbenchTaskListParams,
  WorkbenchTaskShowParams,
} from "./workbench-contract";
import type { Decision } from "../components/thread/agent-inbox/types";

export type WorkbenchPaths = GovernancePaths & {
  taskDir: string;
  threadArchiveDir: string;
  warehouseDir: string;
  duckdbPath: string;
  registryPath: string;
  connectorRegistryPath: string;
  lightragWorkingDir: string;
  reportsDir: string;
  lightragIndexPath: string;
  rawDir: string;
  sourceRegistryDir: string;
  sourceRegistryPath: string;
  sourceSnapshotManifestPath: string;
};

export type WorkbenchScope = {
  scope: string;
  thread_id: string;
  task_id: string;
  agent_id: string;
  tool_name: string;
  is_global: boolean;
  is_scoped: boolean;
};

export type WorkbenchDispatchResult<TData> = {
  data: TData;
  warnings: string[];
};

export type WorkbenchDispatchOptions = {
  paths?: Partial<WorkbenchPaths>;
};

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeNumber(value: unknown, fallback: number) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function textArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(safeText).filter(Boolean);
  const text = safeText(value);
  return text ? [text] : [];
}

function defaultWorkbenchPaths(): WorkbenchPaths {
  const dataDir = process.env.A2A_DATA_DIR
    ? path.resolve(process.env.A2A_DATA_DIR)
    : path.resolve(process.cwd(), "..", "data");
  const workspaceDir = path.resolve(dataDir, "..");
  const warehouseDir = path.join(dataDir, "warehouse");
  const rawDir = process.env.A2A_RAW_DIR
    ? path.resolve(process.env.A2A_RAW_DIR)
    : path.join(workspaceDir, "raw");
  const wikiDir = process.env.A2A_WIKI_DIR
    ? path.resolve(process.env.A2A_WIKI_DIR)
    : path.join(workspaceDir, "wiki");
  const taskDir = process.env.A2A_TASK_DIR
    ? path.resolve(process.env.A2A_TASK_DIR)
    : path.join(dataDir, "tasks");
  const auditPath = process.env.A2A_AUDIT_LOG
    ? path.resolve(process.env.A2A_AUDIT_LOG)
    : path.join(dataDir, "audit", "events.jsonl");
  const skillRegistryDir = process.env.A2A_SKILL_REGISTRY_DIR
    ? path.resolve(process.env.A2A_SKILL_REGISTRY_DIR)
    : path.join(dataDir, "skill_registry");
  const templateDir = process.env.A2A_AGENT_TEMPLATE_DIR
    ? path.resolve(process.env.A2A_AGENT_TEMPLATE_DIR)
    : path.join(dataDir, "agent_templates");
  return {
    workspaceDir,
    dataDir,
    wikiDir,
    taskDir,
    threadArchiveDir: process.env.A2A_THREAD_ARCHIVE_DIR
      ? path.resolve(process.env.A2A_THREAD_ARCHIVE_DIR)
      : path.join(dataDir, "thread_archive"),
    warehouseDir,
    rawDir,
    duckdbPath: path.join(warehouseDir, "a2a.duckdb"),
    registryPath: path.join(warehouseDir, "dataset_registry.json"),
    reportsDir: path.join(dataDir, "reports"),
    connectorRegistryPath: process.env.A2A_CONNECTOR_REGISTRY
      ? path.resolve(process.env.A2A_CONNECTOR_REGISTRY)
      : path.join(warehouseDir, "connector_registry.json"),
    lightragWorkingDir: process.env.WORKING_DIR
      ? path.resolve(process.env.WORKING_DIR)
      : path.join(dataDir, "lightrag_official"),
    lightragIndexPath: path.join(dataDir, "lightrag", "index.json"),
    sourceRegistryDir: process.env.A2A_SOURCE_REGISTRY_DIR
      ? path.resolve(process.env.A2A_SOURCE_REGISTRY_DIR)
      : path.join(dataDir, "source_registry"),
    sourceRegistryPath: process.env.A2A_SOURCE_REGISTRY_PATH
      ? path.resolve(process.env.A2A_SOURCE_REGISTRY_PATH)
      : path.join(dataDir, "source_registry", "sources.json"),
    sourceSnapshotManifestPath: process.env.A2A_SOURCE_SNAPSHOT_MANIFEST
      ? path.resolve(process.env.A2A_SOURCE_SNAPSHOT_MANIFEST)
      : path.join(dataDir, "source_registry", "snapshots.jsonl"),
    skillRegistryDir,
    skillLibraryDir: process.env.A2A_SKILL_LIBRARY_DIR
      ? path.resolve(process.env.A2A_SKILL_LIBRARY_DIR)
      : path.join(workspaceDir, "skills"),
    templateDir,
    mcpPolicyPath: process.env.A2A_MCP_POLICY_PATH
      ? path.resolve(process.env.A2A_MCP_POLICY_PATH)
      : path.join(dataDir, "mcp", "tool_policy.json"),
    auditPath,
  };
}

function resolvePaths(paths: Partial<WorkbenchPaths> = {}): WorkbenchPaths {
  return { ...defaultWorkbenchPaths(), ...paths };
}

export function resolveWorkbenchScope(
  params: Record<string, unknown>,
): WorkbenchScope {
  const scope = safeText(params.scope);
  const threadId = safeText(params.thread_id) || safeText(params.threadId);
  const taskId = safeText(params.task_id) || safeText(params.taskId);
  const agentId = safeText(params.agent_id) || safeText(params.agentId);
  const toolName = safeText(params.tool_name) || safeText(params.toolName);
  return {
    scope,
    thread_id: threadId,
    task_id: taskId,
    agent_id: agentId,
    tool_name: toolName,
    is_global: scope === "global",
    is_scoped: Boolean(threadId || taskId || agentId || toolName),
  };
}

function globalScopeWarning(surface: string) {
  return `${surface} global history withheld; pass scope=global or a thread_id/task_id scope.`;
}

async function guardedTaskList(
  params: WorkbenchTaskListParams,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"task.list">>> {
  const limit = Math.max(1, Math.min(safeNumber(params.limit, 60), 200));
  if (!scope.is_global && !scope.is_scoped) {
    return {
      data: {
        task_dir: paths.taskDir,
        filters: {
          status: safeText(params.status) || "all",
          timeRange: safeText(params.timeRange) || "all",
          type: safeText(params.type) || "all",
          query: safeText(params.query),
          limit,
        },
        counts: { total: 0, returned: 0, invalid: 0 },
        tasks: [],
        invalid_tasks: [],
      },
      warnings: [globalScopeWarning("task.list")],
    };
  }

  return {
    data: await loadTaskList({
      taskDir: paths.taskDir,
      auditPath: paths.auditPath,
      status: safeText(params.status) || "all",
      timeRange: safeText(params.timeRange) || "all",
      type: safeText(params.type) || "all",
      query: safeText(params.query) || scope.task_id,
      limit,
    }),
    warnings: [],
  };
}

async function taskShow(
  params: WorkbenchTaskShowParams,
  paths: WorkbenchPaths,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"task.show">>> {
  const taskId = safeText(params.task_id) || safeText(params.taskId);
  if (!taskId) throw new Error("缺少 task_id");
  return {
    data: await loadTaskDetail(taskId, {
      taskDir: paths.taskDir,
      auditPath: paths.auditPath,
      threadArchiveDir: paths.threadArchiveDir,
    }),
    warnings: [],
  };
}

async function agentTrace(
  params: Record<string, unknown>,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"agent.trace">>> {
  const data = await loadAgentTraceState({
    limit: safeNumber(params.limit, 80),
    taskId: scope.task_id || undefined,
    threadId: scope.thread_id || undefined,
    scope: scope.scope,
    paths: {
      taskDir: paths.taskDir,
      auditPath: paths.auditPath,
      threadArchiveDir: paths.threadArchiveDir,
    },
  });
  return {
    data,
    warnings: data.warnings,
  };
}

function stripTaskHistory(data: DataHealthState): DataHealthState {
  return {
    ...data,
    tasks: [],
    artifact_links: data.artifact_links.filter(
      (link) => link.source !== "task",
    ),
    warnings: [...data.warnings, globalScopeWarning("data.health task")],
  };
}

async function dataHealth(
  _params: WorkbenchDataHealthParams,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"data.health">>> {
  const data = await loadDataHealthState({ paths });
  const scopedData =
    scope.is_global || scope.is_scoped ? data : stripTaskHistory(data);
  return { data: scopedData, warnings: scopedData.warnings };
}

function stripSourceHistory(data: DataSourcesState): DataSourcesState {
  return {
    ...data,
    counts: {
      sources: 0,
      active_sources: 0,
      failed_sources: 0,
      stale_sources: 0,
      paused_sources: 0,
      snapshots: 0,
      schema_drift_count: 0,
    },
    sources: [],
    snapshots: [],
    warnings: [...data.warnings, globalScopeWarning("source.list")],
  };
}

async function sourceList(
  _params: WorkbenchSourceListParams,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"source.list">>> {
  const data = await loadDataSourcesState({ paths });
  const scopedData =
    scope.is_global || scope.is_scoped ? data : stripSourceHistory(data);
  return { data: scopedData, warnings: scopedData.warnings };
}

async function sourceShow(
  params: WorkbenchSourceShowParams,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"source.show">>> {
  const sourceId = safeText(params.source_id) || safeText(params.sourceId);
  if (!sourceId) throw new Error("缺少 source_id");
  if (!scope.is_global && !scope.is_scoped) {
    throw new Error("source.show 需要 scope=global 或已授权上下文");
  }
  const data = await loadDataSourcesState({ paths });
  const source = data.sources.find((item) => item.source_id === sourceId);
  if (!source) throw new Error(`未找到资料来源：${sourceId}`);
  return { data: source, warnings: data.warnings };
}

async function sourceSync(
  params: WorkbenchSourceSyncParams,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"source.sync">>> {
  const sourceId = safeText(params.source_id) || safeText(params.sourceId);
  if (!sourceId) throw new Error("缺少 source_id");
  if (!scope.is_global && !scope.is_scoped) {
    throw new Error("source.sync 需要 scope=global 或已授权上下文");
  }
  const result = await syncDataSourceNow({
    sourceId,
    requestedBy: "workbench",
    paths,
  });
  const state = await loadDataSourcesState({ paths });
  return { data: { result, state }, warnings: state.warnings };
}

function matchesGovernanceScope(
  event: GovernanceAuditEvent,
  scope: WorkbenchScope,
) {
  if (
    scope.task_id &&
    event.task_id !== scope.task_id &&
    event.skill_id !== scope.task_id
  ) {
    return false;
  }
  if (scope.thread_id && event.thread_id !== scope.thread_id) return false;
  if (
    scope.agent_id &&
    event.agent_id !== scope.agent_id &&
    event.actor !== scope.agent_id
  ) {
    return false;
  }
  if (scope.tool_name && event.tool_name !== scope.tool_name) return false;
  return true;
}

async function governancePolicy(
  _params: WorkbenchGovernancePolicyParams,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"governance.policy">>> {
  const data = await loadGovernanceState(paths);
  if (scope.is_global) return { data, warnings: [] };
  if (scope.is_scoped) {
    return {
      data: {
        ...data,
        audit_events: data.audit_events.filter((event) =>
          matchesGovernanceScope(event, scope),
        ),
      },
      warnings: [],
    };
  }
  return {
    data: { ...data, audit_events: [] },
    warnings: [globalScopeWarning("governance audit")],
  };
}

function logFilters(
  params: WorkbenchLogsTailParams,
  scope: WorkbenchScope,
): LogFilters {
  return {
    source: safeText(params.source),
    level: safeText(params.level),
    thread_id: scope.thread_id,
    task_id: scope.task_id,
    agent_id: scope.agent_id,
    tool_name: scope.tool_name,
    risk_level: safeText(params.risk_level) || safeText(params.riskLevel),
  };
}

async function logsTail(
  params: WorkbenchLogsTailParams,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"logs.tail">>> {
  const data = await loadLogsState({
    workspaceDir: paths.workspaceDir,
    dataDir: paths.dataDir,
    limit: safeNumber(params.limit, 200),
    filters: logFilters(params, scope),
  });
  if (scope.is_global || scope.is_scoped) return { data, warnings: [] };
  return {
    data: { ...data, entries: [] },
    warnings: [globalScopeWarning("logs.tail")],
  };
}

function emptyEvidenceGraph(
  paths: WorkbenchPaths,
  params: WorkbenchEvidenceGraphParams,
  scope: WorkbenchScope,
  warning: string,
): EvidenceGraphState {
  const taskId =
    safeText(params.task_id) || safeText(params.taskId) || scope.task_id;
  const reportPath =
    safeText(params.report_path) || safeText(params.reportPath);
  return {
    schema: "a2a_evidence_graph_v1",
    generated_at: new Date().toISOString(),
    scope: scope.scope,
    source_files: {
      workspace_dir: paths.workspaceDir,
      data_dir: paths.dataDir,
      wiki_dir: paths.wikiDir,
      task_dir: paths.taskDir,
      reports_dir: paths.reportsDir,
      registry_path: paths.registryPath,
      audit_path: paths.auditPath,
      lightrag_index_path: paths.lightragIndexPath,
    },
    filters: {
      task_id: taskId,
      report_path: reportPath,
      node_types: textArray(params.nodeTypes ?? params.node_types),
      edge_types: textArray(params.edgeTypes ?? params.edge_types),
      limit: Math.max(1, Math.min(safeNumber(params.limit, 300), 1000)),
    },
    counts: { nodes: 0, edges: 0, truncated: false },
    nodes: [],
    edges: [],
    warnings: [warning],
  };
}

async function evidenceGraph(
  params: WorkbenchEvidenceGraphParams,
  paths: WorkbenchPaths,
  scope: WorkbenchScope,
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<"evidence.graph">>> {
  if (!scope.is_global && !scope.is_scoped) {
    const warning = globalScopeWarning("evidence.graph");
    return {
      data: emptyEvidenceGraph(paths, params, scope, warning),
      warnings: [warning],
    };
  }
  const taskId =
    safeText(params.task_id) || safeText(params.taskId) || scope.task_id;
  const reportPath =
    safeText(params.report_path) || safeText(params.reportPath);
  const graphScope =
    scope.scope || (taskId ? "task" : reportPath ? "report" : "global");
  const data = await loadEvidenceGraphState({
    workspaceDir: paths.workspaceDir,
    dataDir: paths.dataDir,
    wikiDir: paths.wikiDir,
    taskDir: paths.taskDir,
    reportsDir: paths.reportsDir,
    registryPath: paths.registryPath,
    auditPath: paths.auditPath,
    lightragIndexPath: paths.lightragIndexPath,
    scope: graphScope,
    taskId,
    reportPath,
    nodeTypes: textArray(params.nodeTypes ?? params.node_types),
    edgeTypes: textArray(params.edgeTypes ?? params.edge_types),
    limit: safeNumber(params.limit, 300),
  });
  return { data, warnings: data.warnings };
}

function normalizeDecisions(params: WorkbenchApprovalSubmitParams): Decision[] {
  const decisions = Array.isArray(params.decisions)
    ? params.decisions
    : params.decision
      ? [params.decision]
      : [];
  const normalized: Decision[] = [];
  for (const decision of decisions) {
    const record = safeRecord(decision);
    const type = safeText(record.type);
    if (type === "approve") {
      normalized.push({ type: "approve" });
      continue;
    }
    if (type === "reject") {
      normalized.push({ type: "reject", message: safeText(record.message) });
      continue;
    }
    if (type === "edit") {
      const editedAction = safeRecord(record.edited_action);
      const name = safeText(editedAction.name);
      if (name) {
        normalized.push({
          type: "edit",
          edited_action: {
            name,
            args: safeRecord(editedAction.args),
          },
        });
      }
    }
  }
  return normalized;
}

function approvalSubmit(
  params: WorkbenchApprovalSubmitParams,
  scope: WorkbenchScope,
): WorkbenchDispatchResult<WorkbenchApprovalSubmitResult> {
  const threadId = scope.thread_id;
  if (!threadId) throw new Error("缺少 thread_id");
  const decisions = normalizeDecisions(params);
  if (!decisions.length)
    throw new Error("至少需要一个审批决定");
  return {
    data: {
      status: "ready",
      thread_id: threadId,
      resume: { decisions },
      execution_mode: "approval_request_only",
    },
    warnings: [],
  };
}

export async function dispatchWorkbench<TMethod extends WorkbenchMethod>(
  method: TMethod,
  params: WorkbenchParamsFor<TMethod> | Record<string, unknown> = {},
  options: WorkbenchDispatchOptions = {},
): Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>> {
  const safeParams = safeRecord(params);
  const paths = resolvePaths(options.paths);
  const scope = resolveWorkbenchScope(safeParams);

  if (method === "task.list") {
    return guardedTaskList(
      safeParams as WorkbenchTaskListParams,
      paths,
      scope,
    ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
  }
  if (method === "task.show") {
    return taskShow(safeParams as WorkbenchTaskShowParams, paths) as Promise<
      WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>
    >;
  }
  if (method === "agent.trace") {
    return agentTrace(safeParams, paths, scope) as Promise<
      WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>
    >;
  }
  if (method === "data.health") {
    return dataHealth(
      safeParams as WorkbenchDataHealthParams,
      paths,
      scope,
    ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
  }
  if (method === "governance.policy") {
    return governancePolicy(
      safeParams as WorkbenchGovernancePolicyParams,
      paths,
      scope,
    ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
  }
  if (method === "logs.tail") {
    return logsTail(
      safeParams as WorkbenchLogsTailParams,
      paths,
      scope,
    ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
  }
  if (method === "evidence.graph") {
    return evidenceGraph(
      safeParams as WorkbenchEvidenceGraphParams,
      paths,
      scope,
    ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
  }
  if (method === "source.list") {
    return sourceList(
      safeParams as WorkbenchSourceListParams,
      paths,
      scope,
    ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
  }
  if (method === "source.show") {
    return sourceShow(
      safeParams as WorkbenchSourceShowParams,
      paths,
      scope,
    ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
  }
  if (method === "source.sync") {
    return sourceSync(
      safeParams as WorkbenchSourceSyncParams,
      paths,
      scope,
    ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
  }
  return Promise.resolve(
    approvalSubmit(safeParams as WorkbenchApprovalSubmitParams, scope),
  ) as Promise<WorkbenchDispatchResult<WorkbenchResponseFor<TMethod>>>;
}

export function workbenchErrorMeta(method: WorkbenchMethod, error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("required") || message.includes("缺少")) {
    return {
      code: "invalid_workbench_params",
      message: "Workbench 请求参数不完整。",
      hint: message,
      retryable: false,
      source: "workbench",
    };
  }
  if (
    method === "task.show" &&
    (message.includes("Task not found") || message.includes("未找到任务"))
  ) {
    return {
      code: "task_not_found",
      message: "没有找到对应任务。",
      hint: "刷新任务列表后再试。",
      retryable: false,
      source: "tasks",
    };
  }
  return {
    code: "workbench_method_failed",
    message: "Workbench 请求失败。",
    hint: "请检查本地数据目录、筛选条件和服务状态后重试。",
    retryable: true,
    source: method.split(".", 1)[0] || "workbench",
    details: {
      reason: message,
      scope_fields: ["thread_id", "task_id", "agent_id", "tool_name", "scope"],
      accepted_scope: ["global"],
      params_hint: textArray(message).join(", "),
    },
  };
}
