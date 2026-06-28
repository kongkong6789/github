import { lstat, readdir, readFile, realpath, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  collectArtifactLinks,
  summarizeWorkflowProgress,
  type ArtifactCategory,
  type WorkflowProgress,
} from "./data-health";

export type TaskTimeRange = "today" | "7d" | "30d" | "all";
export type TaskAction = "cancel" | "recover";

export type TaskListOptions = {
  taskDir: string;
  auditPath?: string;
  status?: string;
  timeRange?: TaskTimeRange | string;
  type?: string;
  query?: string;
  limit?: number;
  now?: Date;
};

export type TaskDetailOptions = {
  taskDir: string;
  auditPath?: string;
  threadArchiveDir?: string;
};

export type ResolvedTaskArtifact = {
  label: string;
  category: ArtifactCategory;
  path: string;
  source: string;
};

export type TaskEvidence = {
  path: string;
  source: string;
  step: string;
};

export type TaskTimelineEvent = {
  id: string;
  source: "task" | "audit";
  timestamp: string;
  name: string;
  status: string;
  summary: string;
  agent_id: string;
  tool_name: string;
  risk_level: string;
};

export type TaskHandoff = {
  id: string;
  timestamp: string;
  status: string;
  summary: string;
  from_agent: string;
  to_agent: string;
  evidence_paths: string[];
  next_actions: string[];
};

export type TaskQaGate = {
  id: string;
  timestamp: string;
  status: string;
  verdict: "PASS" | "FAIL" | "ESCALATED" | "UNKNOWN";
  checked_by: string;
  summary: string;
  evidence_paths: string[];
  retry_count: number;
  next_actions: string[];
};

export type TaskError = {
  step: string;
  status: string;
  summary: string;
  risks: string[];
  missing_data: string[];
  next_actions: string[];
};

export type TaskSummary = {
  task_id: string;
  goal: string;
  original_user_text: string;
  status: string;
  task_type: string;
  created_at: string;
  updated_at: string;
  requested_by: string;
  steps_count: number;
  background_running: boolean;
  recoverable: boolean;
  cancel_requested: boolean;
  has_report: boolean;
  final_report: string;
  risk_count: number;
  artifact_count: number;
  progress: WorkflowProgress;
  file: string;
  invalid: false;
};

export type InvalidTaskSummary = {
  file: string;
  path: string;
  status: "invalid_json";
  error: string;
  invalid: true;
};

export type TaskListResult = {
  task_dir: string;
  filters: {
    status: string;
    timeRange: string;
    type: string;
    query: string;
    limit: number;
  };
  counts: {
    total: number;
    returned: number;
    invalid: number;
  };
  tasks: TaskSummary[];
  invalid_tasks: InvalidTaskSummary[];
};

export type TaskDetail = TaskSummary & {
  summary: {
    status: string;
    task_type: string;
    created_at: string;
    updated_at: string;
    requested_by: string;
    background_running: boolean;
    recoverable: boolean;
    cancel_requested: boolean;
  };
  stages: WorkflowProgress["stages"];
  steps: Array<Record<string, unknown>>;
  artifacts: ResolvedTaskArtifact[];
  evidence: TaskEvidence[];
  handoffs: TaskHandoff[];
  qa_gates: TaskQaGate[];
  timeline: TaskTimelineEvent[];
  errors: TaskError[];
  raw: Record<string, unknown>;
};

type TaskFile = {
  file: string;
  fullPath: string;
  mtimeMs: number;
  mtime: string;
};

const RECOVERABLE_STATUSES = new Set(["queued", "running"]);
const TASK_TYPE_RULES: Array<{ label: string; patterns: string[] }> = [
  { label: "LightRAG 同步", patterns: ["lightrag", "知识库", "同步"] },
  { label: "表格清洗", patterns: ["clean", "清洗", "excel", "表格"] },
  { label: "资料整理", patterns: ["raw", "资料", "整理", "入库"] },
  { label: "老板报告", patterns: ["老板", "报告", "final_report"] },
  { label: "ERP 只读查询", patterns: ["erp", "吉客云", "金蝶"] },
  { label: "经营分析", patterns: ["分析", "经营", "决策"] },
];

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeNumber(value: unknown): number {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function statusText(value: unknown) {
  return safeText(value).toLowerCase() || "unknown";
}

function parseTime(value: string) {
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const parsed = Date.parse(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function uniqueByPath(items: ResolvedTaskArtifact[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = item.path.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function taskFileStem(taskId: string) {
  return taskId.replace(/\.json$/, "");
}

function isPathUnder(child: string, root: string) {
  const relative = path.relative(root, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

async function safeRealRoot(directory: string) {
  try {
    return await realpath(directory);
  } catch {
    return path.resolve(directory);
  }
}

function originalUserText(goal: string) {
  const marker = "用户原话：";
  const index = goal.lastIndexOf(marker);
  return index === -1 ? "" : goal.slice(index + marker.length).trim();
}

function inferTaskType(task: Record<string, unknown>) {
  const haystack = [
    safeText(task.goal),
    safeText(safeRecord(task.final_report).saved_to),
    ...safeArray<Record<string, unknown>>(task.steps).map((step) =>
      [safeText(step.task), safeText(step.summary)].join(" "),
    ),
  ]
    .join(" ")
    .toLowerCase();

  for (const rule of TASK_TYPE_RULES) {
    if (
      rule.patterns.some((pattern) => haystack.includes(pattern.toLowerCase()))
    ) {
      return rule.label;
    }
  }
  return "经营任务";
}

function taskArtifacts(task: Record<string, unknown>): ResolvedTaskArtifact[] {
  const links = collectArtifactLinks({ tasks: [task] });
  return uniqueByPath(
    links.map((link) => ({
      label: link.label,
      category: link.category,
      path: link.path,
      source: link.source || "task",
    })),
  );
}

function taskEvidence(task: Record<string, unknown>): TaskEvidence[] {
  const items: TaskEvidence[] = [];
  for (const step of safeArray<Record<string, unknown>>(task.steps)) {
    const stepName = safeText(step.task) || "unknown";
    for (const evidence of safeArray(step.evidence)
      .map(safeText)
      .filter(Boolean)) {
      items.push({ path: evidence, source: "task_step", step: stepName });
    }
  }
  return items;
}

function taskErrors(task: Record<string, unknown>): TaskError[] {
  return safeArray<Record<string, unknown>>(task.steps)
    .filter((step) => ["failed", "warning"].includes(statusText(step.status)))
    .map((step) => ({
      step: safeText(step.task) || "unknown",
      status: statusText(step.status),
      summary: safeText(step.summary),
      risks: safeArray(step.risks).map(safeText).filter(Boolean),
      missing_data: safeArray(step.missing_data).map(safeText).filter(Boolean),
      next_actions: safeArray(step.next_actions).map(safeText).filter(Boolean),
    }));
}

function stepEventType(step: Record<string, unknown>) {
  const data = safeRecord(step.data);
  return (
    safeText(data.event_type) ||
    safeText(step.event_type) ||
    safeText(step.task)
  );
}

function stepEvidencePaths(step: Record<string, unknown>) {
  const data = safeRecord(step.data);
  const dataEvidence = safeArray(data.evidence_paths)
    .map(safeText)
    .filter(Boolean);
  if (dataEvidence.length > 0) return dataEvidence;
  return safeArray(step.evidence).map(safeText).filter(Boolean);
}

function stepNextActions(step: Record<string, unknown>) {
  const data = safeRecord(step.data);
  const dataNext = safeArray(data.next_actions).map(safeText).filter(Boolean);
  if (dataNext.length > 0) return dataNext;
  return safeArray(step.next_actions).map(safeText).filter(Boolean);
}

function taskHandoffs(task: Record<string, unknown>): TaskHandoff[] {
  return safeArray<Record<string, unknown>>(task.steps)
    .map((step, index) => {
      const eventType = stepEventType(step);
      if (eventType !== "handoff.created") return null;
      const data = safeRecord(step.data);
      return {
        id: `handoff-${index}`,
        timestamp: safeText(step.completed_at) || safeText(task.updated_at),
        status: statusText(step.status),
        summary: safeText(step.summary),
        from_agent: safeText(data.from_agent) || safeText(step.from_agent),
        to_agent: safeText(data.to_agent) || safeText(step.to_agent),
        evidence_paths: stepEvidencePaths(step),
        next_actions: stepNextActions(step),
      };
    })
    .filter((item): item is TaskHandoff => Boolean(item));
}

function qaVerdictFromEvent(
  eventType: string,
  rawVerdict: string,
): TaskQaGate["verdict"] {
  const verdict = rawVerdict.toUpperCase();
  if (verdict === "PASS" || verdict === "FAIL" || verdict === "ESCALATED")
    return verdict;
  if (eventType === "qa.pass") return "PASS";
  if (eventType === "qa.fail") return "FAIL";
  if (eventType === "qa.escalated") return "ESCALATED";
  return "UNKNOWN";
}

function taskQaGates(task: Record<string, unknown>): TaskQaGate[] {
  return safeArray<Record<string, unknown>>(task.steps)
    .map((step, index) => {
      const eventType = stepEventType(step);
      if (!eventType.startsWith("qa.")) return null;
      const data = safeRecord(step.data);
      return {
        id: `qa-${index}`,
        timestamp: safeText(step.completed_at) || safeText(task.updated_at),
        status: statusText(step.status),
        verdict: qaVerdictFromEvent(eventType, safeText(data.verdict)),
        checked_by: safeText(data.checked_by) || safeText(step.checked_by),
        summary: safeText(step.summary),
        evidence_paths: stepEvidencePaths(step),
        retry_count: safeNumber(data.retry_count ?? step.retry_count),
        next_actions: stepNextActions(step),
      };
    })
    .filter((item): item is TaskQaGate => Boolean(item));
}

function summarizeTask(
  task: Record<string, unknown>,
  fileInfo: Pick<TaskFile, "file" | "mtime">,
): TaskSummary {
  const taskId = safeText(task.task_id) || taskFileStem(fileInfo.file);
  const goal = safeText(task.goal);
  const status = statusText(task.status);
  const steps = safeArray<Record<string, unknown>>(task.steps);
  const finalReport = safeText(safeRecord(task.final_report).saved_to);
  const artifacts = taskArtifacts(task);
  const riskCount = steps.reduce(
    (count, step) => count + safeArray(step.risks).filter(Boolean).length,
    0,
  );

  return {
    task_id: taskId,
    goal,
    original_user_text: originalUserText(goal),
    status,
    task_type: inferTaskType(task),
    created_at: safeText(task.created_at),
    updated_at: safeText(task.updated_at) || fileInfo.mtime,
    requested_by: safeText(task.requested_by),
    steps_count: steps.length,
    background_running: Boolean(task.background_running),
    recoverable: Boolean(task.recoverable) || RECOVERABLE_STATUSES.has(status),
    cancel_requested: task.cancel_requested === true,
    has_report: finalReport.length > 0,
    final_report: finalReport,
    risk_count: riskCount,
    artifact_count: artifacts.length,
    progress: summarizeWorkflowProgress(task),
    file: fileInfo.file,
    invalid: false,
  };
}

async function taskFiles(taskDir: string): Promise<TaskFile[]> {
  try {
    const root = await safeRealRoot(taskDir);
    const files = await readdir(taskDir);
    const jsonFiles = (
      await Promise.all(
        files
          .filter((file) => file.endsWith(".json"))
          .map(async (file) => {
            try {
              const fullPath = path.join(taskDir, file);
              const fileStat = await lstat(fullPath);
              if (fileStat.isSymbolicLink() || !fileStat.isFile()) return null;
              const resolved = await realpath(fullPath);
              if (!isPathUnder(resolved, root)) return null;
              return {
                file,
                fullPath: resolved,
                mtimeMs: fileStat.mtimeMs,
                mtime: fileStat.mtime.toISOString(),
              };
            } catch {
              return null;
            }
          }),
      )
    ).filter((file): file is TaskFile => Boolean(file));
    return jsonFiles.sort((left, right) => right.mtimeMs - left.mtimeMs);
  } catch {
    return [];
  }
}

async function readTaskFile(file: TaskFile) {
  try {
    return {
      file,
      task: JSON.parse(await readFile(file.fullPath, "utf8")) as Record<
        string,
        unknown
      >,
      invalid: null,
    };
  } catch (error) {
    return {
      file,
      task: null,
      invalid: {
        file: file.file,
        path: file.fullPath,
        status: "invalid_json" as const,
        error: error instanceof Error ? error.message : String(error),
        invalid: true as const,
      },
    };
  }
}

function matchesStatus(task: TaskSummary, status: string) {
  if (!status || status === "all") return true;
  if (status === "recoverable") return task.recoverable;
  return task.status === status;
}

function matchesType(task: TaskSummary, type: string) {
  if (!type || type === "all") return true;
  return task.task_type === type;
}

function matchesQuery(task: TaskSummary, query: string) {
  if (!query) return true;
  const normalized = query.toLowerCase();
  return [
    task.task_id,
    task.goal,
    task.original_user_text,
    task.final_report,
    task.task_type,
    ...task.progress.stages.flatMap((stage) => [
      stage.key,
      stage.label,
      stage.summary,
      ...stage.evidence,
    ]),
  ].some((value) => value.toLowerCase().includes(normalized));
}

function matchesTimeRange(task: TaskSummary, timeRange: string, now: Date) {
  if (!timeRange || timeRange === "all") return true;
  const updatedAt = parseTime(task.updated_at);
  if (!updatedAt) return true;
  const nowMs = now.getTime();
  if (timeRange === "today") {
    const today = new Date(now);
    today.setHours(0, 0, 0, 0);
    return updatedAt >= today.getTime();
  }
  const days = timeRange === "7d" ? 7 : timeRange === "30d" ? 30 : 0;
  if (!days) return true;
  return updatedAt >= nowMs - days * 24 * 60 * 60 * 1000;
}

async function readAuditEvents(auditPath: string | undefined, taskId: string) {
  if (!auditPath) return [];
  try {
    const lines = (await readFile(auditPath, "utf8")).split(/\r?\n/);
    return lines.flatMap((line, index): TaskTimelineEvent[] => {
      if (!line.trim()) return [];
      try {
        const event = JSON.parse(line) as Record<string, unknown>;
        if (safeText(event.task_id) !== taskId) return [];
        return [
          {
            id: `audit-${index}`,
            source: "audit",
            timestamp: safeText(event.timestamp),
            name:
              safeText(event.event_type) ||
              safeText(event.tool_name) ||
              "audit_event",
            status: safeText(event.status),
            summary: safeText(event.summary),
            agent_id: safeText(event.agent_id),
            tool_name: safeText(event.tool_name),
            risk_level: safeText(event.risk_level),
          },
        ];
      } catch {
        return [];
      }
    });
  } catch {
    return [];
  }
}

function taskTimeline(
  task: Record<string, unknown>,
  taskId: string,
): TaskTimelineEvent[] {
  return safeArray<Record<string, unknown>>(task.steps).map((step, index) => ({
    id: `task-${taskId}-${index}`,
    source: "task",
    timestamp: safeText(step.completed_at) || safeText(task.updated_at),
    name: safeText(step.task) || `step_${index + 1}`,
    status: statusText(step.status),
    summary: safeText(step.summary),
    agent_id: "",
    tool_name: "",
    risk_level: "",
  }));
}

function sortTimeline(events: TaskTimelineEvent[]) {
  return events.sort(
    (left, right) => parseTime(left.timestamp) - parseTime(right.timestamp),
  );
}

async function findTask(taskId: string, taskDir: string) {
  const files = await taskFiles(taskDir);
  const decodedTaskId = decodeURIComponent(taskId);
  for (const file of files) {
    const stem = taskFileStem(file.file);
    if (stem !== decodedTaskId && file.file !== `${decodedTaskId}.json`)
      continue;
    const parsed = await readTaskFile(file);
    if (!parsed.task) return null;
    return parsed;
  }

  for (const file of files) {
    const parsed = await readTaskFile(file);
    if (parsed.task && safeText(parsed.task.task_id) === decodedTaskId)
      return parsed;
  }
  return null;
}

export async function loadTaskList(
  options: TaskListOptions,
): Promise<TaskListResult> {
  const limit = Math.max(1, Math.min(Number(options.limit || 60), 200));
  const status = safeText(options.status) || "all";
  const timeRange = safeText(options.timeRange) || "all";
  const type = safeText(options.type) || "all";
  const query = safeText(options.query);
  const now = options.now ?? new Date();

  const parsed = await Promise.all(
    (await taskFiles(options.taskDir)).map(readTaskFile),
  );
  const invalidTasks = parsed.flatMap((item) =>
    item.invalid ? [item.invalid] : [],
  );
  const summaries = parsed.flatMap((item) =>
    item.task ? [summarizeTask(item.task, item.file)] : [],
  );
  const filtered = summaries
    .filter((task) => matchesStatus(task, status))
    .filter((task) => matchesType(task, type))
    .filter((task) => matchesQuery(task, query))
    .filter((task) => matchesTimeRange(task, timeRange, now))
    .sort(
      (left, right) => parseTime(right.updated_at) - parseTime(left.updated_at),
    )
    .slice(0, limit);

  return {
    task_dir: options.taskDir,
    filters: { status, timeRange, type, query, limit },
    counts: {
      total: summaries.length,
      returned: filtered.length,
      invalid: invalidTasks.length,
    },
    tasks: filtered,
    invalid_tasks: invalidTasks,
  };
}

export async function loadTaskDetail(
  taskId: string,
  options: TaskDetailOptions,
): Promise<TaskDetail> {
  const found = await findTask(taskId, options.taskDir);
  if (!found?.task) {
    throw new Error(`未找到任务：${decodeURIComponent(taskId)}`);
  }
  const summary = summarizeTask(found.task, found.file);
  const audit = await readAuditEvents(options.auditPath, summary.task_id);
  const timeline = sortTimeline([
    ...taskTimeline(found.task, summary.task_id),
    ...audit,
  ]);

  return {
    ...summary,
    summary: {
      status: summary.status,
      task_type: summary.task_type,
      created_at: summary.created_at,
      updated_at: summary.updated_at,
      requested_by: summary.requested_by,
      background_running: summary.background_running,
      recoverable: summary.recoverable,
      cancel_requested: summary.cancel_requested,
    },
    stages: summary.progress.stages,
    steps: safeArray<Record<string, unknown>>(found.task.steps),
    artifacts: taskArtifacts(found.task),
    evidence: taskEvidence(found.task),
    handoffs: taskHandoffs(found.task),
    qa_gates: taskQaGates(found.task),
    timeline,
    errors: taskErrors(found.task),
    raw: found.task,
  };
}

function appendActionStep(
  task: Record<string, unknown>,
  action: TaskAction,
  timestamp: string,
) {
  const steps = safeArray<Record<string, unknown>>(task.steps);
  steps.push({
    task: action === "cancel" ? "cancel_requested" : "recovery_requested",
    status: action === "cancel" ? "warning" : "queued",
    summary:
      action === "cancel"
        ? "已从任务详情页请求取消；后台会在当前步骤结束后停止后续步骤。"
        : "已从任务详情页请求恢复；后端 recover_workflow_queue 可继续拾取 queued/running 任务。",
    completed_at: timestamp,
    evidence: [],
    risks: [],
    missing_data: [],
    next_actions:
      action === "cancel"
        ? ["等待当前后台步骤停止或查看日志。"]
        : ["运行后端恢复队列或等待后端启动时恢复。"],
    data: { requested_from: "tasks_page" },
  });
  task.steps = steps;
}

export async function updateTaskAction(
  taskId: string,
  action: TaskAction,
  options: TaskDetailOptions,
): Promise<TaskDetail> {
  const found = await findTask(taskId, options.taskDir);
  if (!found?.task)
    throw new Error(`未找到任务：${decodeURIComponent(taskId)}`);

  const timestamp = new Date().toISOString();
  if (action === "cancel") {
    found.task.cancel_requested = true;
    if (statusText(found.task.status) === "queued") {
      found.task.status = "cancelled";
    }
  } else {
    found.task.status = "queued";
    found.task.cancel_requested = false;
    found.task.recovery_requested = true;
    found.task.recovered_at = timestamp;
  }
  found.task.updated_at = timestamp;
  appendActionStep(found.task, action, timestamp);
  await writeFile(
    found.file.fullPath,
    JSON.stringify(found.task, null, 2),
    "utf8",
  );
  return loadTaskDetail(taskId, options);
}
