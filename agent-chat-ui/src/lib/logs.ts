import { lstat, open, stat } from "node:fs/promises";
import path from "node:path";

export type LogLevel = "debug" | "info" | "warn" | "error" | "unknown";

export type LogFilters = Partial<
  Record<
    | "source"
    | "level"
    | "thread_id"
    | "task_id"
    | "agent_id"
    | "tool_name"
    | "risk_level",
    string
  >
>;

export type LogEntry = {
  id: string;
  source: string;
  source_label: string;
  level: LogLevel;
  timestamp: string;
  message: string;
  thread_id: string;
  task_id: string;
  agent_id: string;
  tool_name: string;
  risk_level: string;
  file_path: string;
};

export type LogSourceSummary = {
  source: string;
  label: string;
  path: string;
  status: "ok" | "missing" | "skipped" | "error";
  line_count: number;
  invalid_json_count: number;
  updated_at: string;
  error: string;
};

export type LogsState = {
  checked_at: string;
  limit: number;
  filters: LogFilters;
  sources: LogSourceSummary[];
  entries: LogEntry[];
};

type SourceDefinition = {
  source: string;
  label: string;
  file: string;
  kind: "text" | "audit";
};

type LoadLogsOptions = {
  workspaceDir?: string;
  dataDir?: string;
  limit?: number;
  filters?: LogFilters;
};

const LOG_SOURCES: SourceDefinition[] = [
  {
    source: "langgraph",
    label: "任务执行服务",
    file: "langgraph-server.log",
    kind: "text",
  },
  {
    source: "langgraph_error",
    label: "任务执行错误",
    file: "langgraph-server.err.log",
    kind: "text",
  },
  {
    source: "frontend_error",
    label: "前端错误",
    file: "frontend.err.log",
    kind: "text",
  },
  {
    source: "lightrag",
    label: "知识库服务",
    file: "lightrag-server.log",
    kind: "text",
  },
  {
    source: "lightrag_error",
    label: "知识库错误",
    file: "lightrag-server.err.log",
    kind: "text",
  },
];

const SENSITIVE_PATTERNS = [
  /(api[_-]?key|token|secret|password)\s*[:=]\s*['"]?[^,'"\s]+/gi,
  /\b(scode|apikey|access_token)=([^&\s"']+)/gi,
  /sk-[A-Za-z0-9_-]{12,}/g,
  /tp-[A-Za-z0-9_-]{12,}/g,
  /ghp_[A-Za-z0-9]{20,}/g,
];
const ANSI_PATTERN = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, "g");
const MAX_LOG_READ_BYTES = 512 * 1024;

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeNumber(value: unknown): number {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function sanitizePath(filePath: string, workspaceDir: string): string {
  if (!filePath) return "";
  try {
    const relative = path.relative(workspaceDir, filePath);
    if (relative && !relative.startsWith("..") && !path.isAbsolute(relative)) {
      return relative;
    }
    return path.basename(filePath);
  } catch {
    return path.basename(filePath);
  }
}

export function redactSensitiveText(value: string): string {
  return SENSITIVE_PATTERNS.reduce((current, pattern) => {
    return current.replace(pattern, (match) => {
      if (match.includes("=")) {
        return `${match.split("=", 1)[0]}=***REDACTED***`;
      }
      if (match.includes(":")) {
        const [key] = match.split(":", 1);
        return `${key}: ***REDACTED***`;
      }
      return "***REDACTED***";
    });
  }, value.replace(ANSI_PATTERN, ""));
}

function redactValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redactValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, redactValue(item)]),
    );
  }
  return typeof value === "string" ? redactSensitiveText(value) : value;
}

function normalizeLevel(value: string): LogLevel {
  const normalized = value.toLowerCase();
  if (["debug", "trace"].includes(normalized)) return "debug";
  if (["info", "notice", "ok", "success"].includes(normalized)) return "info";
  if (["warn", "warning"].includes(normalized)) return "warn";
  if (["error", "err", "fatal", "fail", "failed"].includes(normalized)) {
    return "error";
  }
  return "unknown";
}

function extractTimestamp(line: string) {
  return (
    line.match(/\d{4}-\d{2}-\d{2}[T ][0-9:.+-]+Z?/)?.[0] ||
    line.match(/\d{4}-\d{2}-\d{2} [0-9:]+/)?.[0] ||
    ""
  );
}

function extractLevel(line: string): LogLevel {
  const match = line.match(/\b(DEBUG|TRACE|INFO|NOTICE|WARN|WARNING|ERROR|ERR|FATAL|FAILED?)\b/i);
  return normalizeLevel(match?.[1] ?? "");
}

function sortTimestamp(value: string) {
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : 0;
}

function matchesFilters(entry: LogEntry, filters: LogFilters) {
  return Object.entries(filters).every(([key, value]) => {
    if (!value) return true;
    const actual = entry[key as keyof LogFilters] ?? "";
    return String(actual).toLowerCase() === value.toLowerCase();
  });
}

async function readLines(filePath: string) {
  const file = await open(filePath, "r");
  try {
    const fileStat = await file.stat();
    const length = Math.min(fileStat.size, MAX_LOG_READ_BYTES);
    const buffer = Buffer.alloc(length);
    await file.read(buffer, 0, length, Math.max(0, fileStat.size - length));
    const content = buffer.toString("utf8");
    const lines = content.split(/\r?\n/);
    return (fileStat.size > length ? lines.slice(1) : lines).filter(Boolean);
  } finally {
    await file.close();
  }
}

async function sourceStat(filePath: string) {
  try {
    const linkStat = await lstat(filePath);
    if (linkStat.isSymbolicLink()) {
      return {
        exists: true,
        updated_at: linkStat.mtime.toISOString(),
        symlink: true,
      };
    }
    const fileStat = await stat(filePath);
    return {
      exists: true,
      updated_at: fileStat.mtime.toISOString(),
      symlink: false,
    };
  } catch {
    return { exists: false, updated_at: "", symlink: false };
  }
}

async function loadTextSource(
  definition: SourceDefinition,
  workspaceDir: string,
): Promise<{ summary: LogSourceSummary; entries: LogEntry[] }> {
  const filePath = path.join(workspaceDir, definition.file);
  const sanitizedPath = sanitizePath(filePath, workspaceDir);
  const file = await sourceStat(filePath);
  if (!file.exists) {
    return {
      summary: {
        source: definition.source,
        label: definition.label,
        path: sanitizedPath,
        status: "missing",
        line_count: 0,
        invalid_json_count: 0,
        updated_at: "",
        error: "",
      },
      entries: [],
    };
  }
  if (file.symlink) {
    return {
      summary: {
        source: definition.source,
        label: definition.label,
        path: sanitizedPath,
        status: "error",
        line_count: 0,
        invalid_json_count: 0,
        updated_at: file.updated_at,
        error: "Log source is a symbolic link and was not read.",
      },
      entries: [],
    };
  }

  try {
    const lines = await readLines(filePath);
    return {
      summary: {
        source: definition.source,
        label: definition.label,
        path: sanitizedPath,
        status: "ok",
        line_count: lines.length,
        invalid_json_count: 0,
        updated_at: file.updated_at,
        error: "",
      },
      entries: lines.map((line, index) => ({
        id: `${definition.source}:${index}`,
        source: definition.source,
        source_label: definition.label,
        level: extractLevel(line),
        timestamp: extractTimestamp(line),
        message: redactSensitiveText(line),
        thread_id: "",
        task_id: "",
        agent_id: "",
        tool_name: "",
        risk_level: "",
        file_path: sanitizedPath,
      })),
    };
  } catch (error) {
    return {
      summary: {
        source: definition.source,
        label: definition.label,
        path: sanitizedPath,
        status: "error",
        line_count: 0,
        invalid_json_count: 0,
        updated_at: file.updated_at,
        error: error instanceof Error ? error.message : String(error),
      },
      entries: [],
    };
  }
}

async function loadAuditSource(dataDir: string): Promise<{
  summary: LogSourceSummary;
  entries: LogEntry[];
}> {
  const filePath = path.join(dataDir, "audit", "events.jsonl");
  const workspaceDir = path.resolve(dataDir, "..");
  const sanitizedPath = sanitizePath(filePath, workspaceDir);
  const file = await sourceStat(filePath);
  if (!file.exists) {
    return {
      summary: {
        source: "audit",
        label: "审计记录",
        path: sanitizedPath,
        status: "missing",
        line_count: 0,
        invalid_json_count: 0,
        updated_at: "",
        error: "",
      },
      entries: [],
    };
  }
  if (file.symlink) {
    return {
      summary: {
        source: "audit",
        label: "审计记录",
        path: sanitizedPath,
        status: "error",
        line_count: 0,
        invalid_json_count: 0,
        updated_at: file.updated_at,
        error: "Audit source is a symbolic link and was not read.",
      },
      entries: [],
    };
  }

  let invalidJsonCount = 0;
  try {
    const lines = await readLines(filePath);
    const entries = lines
      .map((line, index) => {
        try {
          const raw = safeRecord(redactValue(JSON.parse(line)));
          const metadata = safeRecord(raw.metadata);
          const level =
            safeText(raw.level) ||
            (["high", "destructive"].includes(safeText(raw.risk_level))
              ? "warn"
              : "info");
          const eventType = safeText(raw.event_type);
          const summary = safeText(raw.summary);
          return {
            id: `audit:${index}`,
            source: "audit",
            source_label: "审计记录",
            level: normalizeLevel(level),
            timestamp: safeText(raw.timestamp) || safeText(raw.created_at),
            message: redactSensitiveText(
              summary || eventType || JSON.stringify(raw, null, 0),
            ),
            thread_id: safeText(raw.thread_id) || safeText(metadata.thread_id),
            task_id: safeText(raw.task_id) || safeText(metadata.task_id),
            agent_id: safeText(raw.agent_id) || safeText(metadata.agent_id),
            tool_name: safeText(raw.tool_name) || safeText(metadata.tool_name),
            risk_level:
              safeText(raw.risk_level) ||
              safeText(metadata.risk_level) ||
              safeText(Array.isArray(raw.risks) ? raw.risks[0] : ""),
            file_path: sanitizedPath,
          };
        } catch {
          invalidJsonCount += 1;
          return null;
        }
      })
      .filter((entry): entry is LogEntry => Boolean(entry));

    return {
      summary: {
        source: "audit",
        label: "审计记录",
        path: sanitizedPath,
        status: "ok",
        line_count: lines.length,
        invalid_json_count: invalidJsonCount,
        updated_at: file.updated_at,
        error: "",
      },
      entries,
    };
  } catch (error) {
    return {
      summary: {
        source: "audit",
        label: "审计记录",
        path: sanitizedPath,
        status: "error",
        line_count: 0,
        invalid_json_count: invalidJsonCount,
        updated_at: file.updated_at,
        error: error instanceof Error ? error.message : String(error),
      },
      entries: [],
    };
  }
}

function taskEventsPlaceholder(dataDir: string): LogSourceSummary {
  const workspaceDir = path.resolve(dataDir, "..");
  return {
    source: "task_events",
    label: "任务事件",
    path: sanitizePath(path.join(dataDir, "tasks", "tasks.sqlite"), workspaceDir),
    status: "skipped",
    line_count: 0,
    invalid_json_count: 0,
    updated_at: "",
    error: "SQLite task_events support is reserved for P12.",
  };
}

function normalizeLimit(value: unknown) {
  const number = safeNumber(value);
  if (number <= 0) return 200;
  return Math.min(Math.floor(number), 1000);
}

export async function loadLogsState({
  workspaceDir = path.resolve(process.cwd(), ".."),
  dataDir = path.join(workspaceDir, "data"),
  limit = 200,
  filters = {},
}: LoadLogsOptions = {}): Promise<LogsState> {
  const normalizedLimit = normalizeLimit(limit);
  const [audit, ...textSources] = await Promise.all([
    loadAuditSource(dataDir),
    ...LOG_SOURCES.map((definition) => loadTextSource(definition, workspaceDir)),
  ]);
  const sources = [
    ...textSources.map((item) => item.summary),
    audit.summary,
    taskEventsPlaceholder(dataDir),
  ];
  const entries = [...textSources.flatMap((item) => item.entries), ...audit.entries]
    .filter((entry) => matchesFilters(entry, filters))
    .sort((left, right) => {
      const byTime = sortTimestamp(left.timestamp) - sortTimestamp(right.timestamp);
      return byTime || left.id.localeCompare(right.id);
    })
    .slice(-normalizedLimit);

  return {
    checked_at: new Date().toISOString(),
    limit: normalizedLimit,
    filters,
    sources,
    entries,
  };
}
