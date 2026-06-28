import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

export type TraceEvent = {
  id: string;
  source: "message" | "task" | "audit";
  timestamp?: string;
  taskId?: string;
  agent?: string;
  kind: "tool_call" | "tool_result" | "task_step" | "audit_event";
  name: string;
  status?: string;
  summary?: string;
  args?: unknown;
  result?: unknown;
  evidence?: string[];
  risks?: string[];
};

export type AgentTracePaths = {
  taskDir: string;
  auditPath: string;
  threadArchiveDir: string;
};

export type AgentTraceOptions = {
  taskId?: string;
  threadId?: string;
  scope?: string;
  limit?: number;
  paths?: Partial<AgentTracePaths>;
};

export type AgentTraceResult = {
  status: "ok";
  schema_version: "a2a_agent_trace_v1";
  generated_at: string;
  filters: {
    taskId: string;
    threadId: string;
    scope: string;
    inferredTaskIds: string[];
    limit: number;
  };
  counts: {
    message: number;
    task: number;
    audit: number;
    total: number;
  };
  tool_calls: TraceEvent[];
  task_steps: TraceEvent[];
  audit_events: TraceEvent[];
  timeline: TraceEvent[];
  events: TraceEvent[];
  warnings: string[];
};

type TaskIndexItem = {
  file: string;
  fileStem: string;
  fullPath: string;
  mtimeMs: number;
  taskId: string;
};

const LOCAL_TASK_THREAD_ID_PREFIX = "local-task-";
const LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX = "local-archive-";

function defaultPaths(): AgentTracePaths {
  const dataDir = process.env.A2A_DATA_DIR
    ? path.resolve(process.env.A2A_DATA_DIR)
    : path.resolve(process.cwd(), "..", "data");
  return {
    taskDir: process.env.A2A_TASK_DIR
      ? path.resolve(process.env.A2A_TASK_DIR)
      : path.join(dataDir, "tasks"),
    auditPath: process.env.A2A_AUDIT_LOG
      ? path.resolve(process.env.A2A_AUDIT_LOG)
      : path.join(dataDir, "audit", "events.jsonl"),
    threadArchiveDir: process.env.A2A_THREAD_ARCHIVE_DIR
      ? path.resolve(process.env.A2A_THREAD_ARCHIVE_DIR)
      : path.join(dataDir, "thread_archive"),
  };
}

function resolvePaths(paths: Partial<AgentTracePaths> = {}): AgentTracePaths {
  return { ...defaultPaths(), ...paths };
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function safeArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function contentPreview(value: unknown): string {
  if (typeof value === "string") return value.slice(0, 600);
  if (Array.isArray(value)) return value.map(contentPreview).filter(Boolean).join("\n").slice(0, 600);
  if (!value || typeof value !== "object") return "";
  const record = value as { text?: unknown; content?: unknown };
  return contentPreview(record.text ?? record.content);
}

function extractTaskIdsFromText(text: string): string[] {
  const taskIds = new Set<string>();
  const fencedMatches = text.matchAll(/(?:任务ID|task[_ ]?id)[^`\n]*`([^`]+)`/gi);
  for (const match of fencedMatches) {
    if (match[1]) taskIds.add(match[1].trim());
  }
  const plainMatches = text.matchAll(
    /(?:任务ID|task[_ ]?id)\s*[:：]?\s*([0-9]{8}-[^\s`，。；,;]+)/gi,
  );
  for (const match of plainMatches) {
    if (match[1]) taskIds.add(match[1].trim());
  }
  const lineMatches = text.matchAll(/(^|\n)([0-9]{8}-[^\n`]+)/g);
  for (const match of lineMatches) {
    if (match[2]) taskIds.add(match[2].trim());
  }
  return [...taskIds];
}

function extractTaskIdsFromMessages(messages: Array<Record<string, unknown>>): string[] {
  const taskIds = new Set<string>();
  for (const message of messages) {
    for (const taskId of extractTaskIdsFromText(contentPreview(message.content))) {
      taskIds.add(taskId);
    }
    for (const toolCall of safeArray<Record<string, unknown>>(message.tool_calls)) {
      for (const taskId of extractTaskIdsFromText(JSON.stringify(toolCall))) {
        taskIds.add(taskId);
      }
    }
  }
  return [...taskIds];
}

function originalThreadIdFromRequest(threadId: string): string {
  if (threadId.startsWith(LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX)) {
    return decodeURIComponent(threadId.slice(LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX.length));
  }
  return threadId;
}

function localTaskFileStemFromRequest(threadId: string): string | null {
  if (!threadId.startsWith(LOCAL_TASK_THREAD_ID_PREFIX)) return null;
  return decodeURIComponent(threadId.slice(LOCAL_TASK_THREAD_ID_PREFIX.length));
}

async function readJsonFile<T>(filePath: string): Promise<T | null> {
  try {
    return JSON.parse(await readFile(filePath, "utf8")) as T;
  } catch {
    return null;
  }
}

async function buildTaskIndex(taskDir: string): Promise<TaskIndexItem[]> {
  try {
    const files = await readdir(taskDir);
    const candidates = await Promise.all(
      files
        .filter((file) => file.endsWith(".json"))
        .map(async (file) => {
          const fullPath = path.join(taskDir, file);
          const fileStat = await stat(fullPath);
          const task = await readJsonFile<Record<string, unknown>>(fullPath);
          const fileStem = file.replace(/\.json$/, "");
          return {
            file,
            fileStem,
            fullPath,
            mtimeMs: fileStat.mtimeMs,
            taskId: safeText(task?.task_id) || fileStem,
          };
        }),
    );
    return candidates;
  } catch {
    return [];
  }
}

function resolveScopedTaskIds(rawTaskIds: Set<string>, taskIndex: TaskIndexItem[]): Set<string> {
  const resolved = new Set<string>();
  for (const rawTaskId of rawTaskIds) {
    if (!rawTaskId) continue;
    const exactMatches = taskIndex.filter(
      (item) => item.taskId === rawTaskId || item.fileStem === rawTaskId,
    );
    if (exactMatches.length > 0) {
      exactMatches.forEach((item) => resolved.add(item.taskId));
      continue;
    }

    const prefixMatches = taskIndex.filter((item) => item.taskId.startsWith(rawTaskId));
    if (prefixMatches.length === 1) {
      resolved.add(prefixMatches[0].taskId);
    }
  }
  return resolved;
}

async function taskEvents(
  limit: number,
  taskIds: Set<string>,
  taskFileStems: Set<string>,
  scoped: boolean,
  taskIndex: TaskIndexItem[],
): Promise<TraceEvent[]> {
  try {
    const events: TraceEvent[] = [];
    const candidates = taskIndex
      .filter((item) => {
        if (!scoped) return true;
        return taskIds.has(item.taskId) || taskFileStems.has(item.fileStem);
      })
      .sort((a, b) => b.mtimeMs - a.mtimeMs)
      .slice(0, limit);

    for (const item of candidates) {
      const task = await readJsonFile<Record<string, unknown>>(item.fullPath);
      if (!task) continue;
      const currentTaskId = item.taskId;
      safeArray<Record<string, unknown>>(task.steps).forEach((step, index) => {
        events.push({
          id: `task-${currentTaskId}-${index}`,
          source: "task",
          kind: "task_step",
          taskId: currentTaskId,
          timestamp: safeText(step.completed_at) || safeText(task.updated_at),
          name: safeText(step.task) || `step_${index + 1}`,
          status: safeText(step.status),
          summary: safeText(step.summary),
          evidence: safeArray<string>(step.evidence).slice(0, 6),
          risks: safeArray<string>(step.risks).slice(0, 6),
        });
      });
    }
    return events;
  } catch {
    return [];
  }
}

async function scopedAuditEvents(
  auditPath: string,
  limit: number,
  taskIds: Set<string>,
  scoped: boolean,
): Promise<TraceEvent[]> {
  if (scoped && taskIds.size === 0) return [];
  try {
    const lines = (await readFile(auditPath, "utf8")).split(/\r?\n/);
    return lines
      .slice(-limit * 5)
      .map((line) => {
        try {
          return JSON.parse(line) as Record<string, unknown>;
        } catch {
          return null;
        }
      })
      .filter((event): event is Record<string, unknown> => !!event)
      .filter((event) => !scoped || taskIds.has(safeText(event.task_id)))
      .slice(-limit)
      .map((event, index) => ({
        id: `audit-${index}-${safeText(event.timestamp)}`,
        source: "audit" as const,
        kind: "audit_event" as const,
        timestamp: safeText(event.timestamp) || safeText(event.created_at),
        taskId: safeText(event.task_id),
        agent: safeText(event.actor) || safeText(event.agent_id),
        name: safeText(event.event_type) || "audit_event",
        summary: safeText(event.summary),
        risks: safeArray<string>(event.risks).slice(0, 6),
        result: {
          paths: safeArray<string>(event.paths),
          metadata: event.metadata,
        },
      }));
  } catch {
    return [];
  }
}

async function messageEvents(
  threadArchiveDir: string,
  limit: number,
  threadId?: string,
): Promise<TraceEvent[]> {
  try {
    const files = await readdir(threadArchiveDir);
    const events: TraceEvent[] = [];
    for (const file of files.filter((name) => name.endsWith(".json")).slice(-limit)) {
      const record = await readJsonFile<Record<string, unknown>>(path.join(threadArchiveDir, file));
      if (!record) continue;
      const originalThreadId = safeText(record.original_thread_id);
      const requestedOriginalThreadId = threadId ? originalThreadIdFromRequest(threadId) : "";
      if (threadId && originalThreadId !== requestedOriginalThreadId) continue;
      const messages = safeArray<Record<string, unknown>>((record.values as Record<string, unknown> | undefined)?.messages);
      messages.forEach((message, index) => {
        const type = safeText(message.type);
        if (type === "ai") {
          safeArray<Record<string, unknown>>(message.tool_calls).forEach((toolCall, toolIndex) => {
            events.push({
              id: `msg-${originalThreadId}-${index}-${toolIndex}`,
              source: "message",
              kind: "tool_call",
              agent: safeText(message.name),
              name: safeText(toolCall.name) || "tool_call",
              args: toolCall.args,
              summary: contentPreview(message.content),
            });
          });
        }
        if (type === "tool") {
          events.push({
            id: `tool-${originalThreadId}-${index}`,
            source: "message",
            kind: "tool_result",
            agent: safeText(message.name),
            name: safeText(message.name) || "tool_result",
            result: contentPreview(message.content),
          });
        }
      });
    }
    return events.slice(-limit);
  } catch {
    return [];
  }
}

async function taskIdsForThread(
  threadArchiveDir: string,
  threadId: string | undefined,
): Promise<{ taskIds: Set<string>; taskFileStems: Set<string> }> {
  const taskIds = new Set<string>();
  const taskFileStems = new Set<string>();
  if (!threadId) return { taskIds, taskFileStems };

  const localTaskFileStem = localTaskFileStemFromRequest(threadId);
  if (localTaskFileStem) {
    taskFileStems.add(localTaskFileStem);
    taskIds.add(localTaskFileStem);
    return { taskIds, taskFileStems };
  }

  const requestedOriginalThreadId = originalThreadIdFromRequest(threadId);
  try {
    const files = await readdir(threadArchiveDir);
    for (const file of files.filter((name) => name.endsWith(".json"))) {
      const record = await readJsonFile<Record<string, unknown>>(path.join(threadArchiveDir, file));
      if (!record || safeText(record.original_thread_id) !== requestedOriginalThreadId) continue;
      const messages = safeArray<Record<string, unknown>>((record.values as Record<string, unknown> | undefined)?.messages);
      for (const taskId of extractTaskIdsFromMessages(messages)) {
        taskIds.add(taskId);
      }
      return { taskIds, taskFileStems };
    }
  } catch {
    return { taskIds, taskFileStems };
  }
  return { taskIds, taskFileStems };
}

function sortTimeline(events: TraceEvent[]) {
  return events.sort((left, right) => {
    const leftTime = Date.parse(left.timestamp ?? "");
    const rightTime = Date.parse(right.timestamp ?? "");
    const byTime = (Number.isFinite(leftTime) ? leftTime : 0) - (Number.isFinite(rightTime) ? rightTime : 0);
    return byTime || left.id.localeCompare(right.id);
  });
}

export async function loadAgentTraceState({
  taskId,
  threadId,
  scope = "",
  limit: rawLimit = 80,
  paths: partialPaths = {},
}: AgentTraceOptions = {}): Promise<AgentTraceResult> {
  const limit = Math.min(Math.max(Number(rawLimit || 80), 1), 160);
  const globalScope = scope === "global";
  const scoped = Boolean(taskId || threadId);
  const warnings: string[] = [];
  const paths = resolvePaths(partialPaths);

  if (!scoped && !globalScope) {
    warnings.push("No thread_id/task_id supplied; global trace history requires scope=global.");
    return {
      status: "ok",
      schema_version: "a2a_agent_trace_v1",
      generated_at: new Date().toISOString(),
      filters: { taskId: "", threadId: "", scope, inferredTaskIds: [], limit },
      counts: { message: 0, task: 0, audit: 0, total: 0 },
      tool_calls: [],
      task_steps: [],
      audit_events: [],
      timeline: [],
      events: [],
      warnings,
    };
  }

  const taskIndex = await buildTaskIndex(paths.taskDir);
  const { taskIds: rawTaskIds, taskFileStems } = await taskIdsForThread(paths.threadArchiveDir, threadId);
  if (taskId) rawTaskIds.add(taskId);
  const taskIds = scoped ? resolveScopedTaskIds(rawTaskIds, taskIndex) : new Set<string>();
  const [tasks, audits, messages] = await Promise.all([
    taskEvents(limit, taskIds, taskFileStems, scoped, taskIndex),
    scopedAuditEvents(paths.auditPath, limit, taskIds, scoped),
    messageEvents(paths.threadArchiveDir, limit, threadId),
  ]);

  const timeline = sortTimeline([...messages, ...tasks, ...audits]).slice(-limit);
  return {
    status: "ok",
    schema_version: "a2a_agent_trace_v1",
    generated_at: new Date().toISOString(),
    filters: {
      taskId: taskId ?? "",
      threadId: threadId ?? "",
      scope,
      inferredTaskIds: [...taskIds],
      limit,
    },
    counts: {
      message: messages.length,
      task: tasks.length,
      audit: audits.length,
      total: timeline.length,
    },
    tool_calls: messages,
    task_steps: tasks,
    audit_events: audits,
    timeline,
    events: timeline,
    warnings,
  };
}
