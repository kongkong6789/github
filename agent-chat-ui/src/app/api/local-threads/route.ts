import { NextRequest, NextResponse } from "next/server";
import {
  mkdir,
  lstat,
  readdir,
  readFile,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import type { Message } from "@langchain/langgraph-sdk";

import { checkWorkbenchAuth } from "@/lib/api-auth";
import { workbenchAuthResponse } from "@/lib/api-route-auth";
import {
  buildLocalBrowserArchiveThreadId,
  LOCAL_ARCHIVE_METADATA_SOURCE,
  LOCAL_ARCHIVE_THREAD_ID_PREFIX,
  LOCAL_BROWSER_ARCHIVE_METADATA_SOURCE,
  LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX,
  shouldHydrateLocalArchiveMessages,
} from "@/lib/local-archive-thread";
import { repairMissingToolResponsesInMessageOrder } from "@/lib/ensure-tool-responses";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type WorkflowStep = {
  task?: string;
  status?: string;
  summary?: string;
  evidence?: string[];
  risks?: string[];
  missing_data?: string[];
  next_actions?: string[];
};

type WorkflowTask = {
  task_id?: string;
  goal?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  steps?: WorkflowStep[];
  final_report?: {
    saved_to?: string;
  };
};

type ArchiveMessage = {
  id?: string;
  type?: string;
  content?: unknown;
  name?: string;
  tool_call_id?: string;
  tool_calls?: unknown[];
  invalid_tool_calls?: unknown[];
};

type LocalArchivedThreadRecord = {
  original_thread_id: string;
  created_at?: string;
  updated_at?: string;
  assistant_id?: string;
  api_url?: string;
  values?: {
    messages?: ArchiveMessage[];
    ui?: unknown[];
  };
};

const DATA_DIR = process.env.A2A_DATA_DIR
  ? path.resolve(process.env.A2A_DATA_DIR)
  : path.resolve(process.cwd(), "..", "data");
const TASKS_DIR = process.env.A2A_TASK_DIR
  ? path.resolve(process.env.A2A_TASK_DIR)
  : path.join(DATA_DIR, "tasks");
const THREAD_ARCHIVE_DIR = process.env.A2A_THREAD_ARCHIVE_DIR
  ? path.resolve(process.env.A2A_THREAD_ARCHIVE_DIR)
  : path.join(DATA_DIR, "thread_archive");
const MAX_TASK_THREADS = 40;
const MAX_ARCHIVED_THREADS = 60;
const MAX_ARCHIVED_MESSAGES = 40;
const MAX_TEXT_CONTENT = 4000;
const REMOTE_THREAD_STATE_TIMEOUT_MS = 1500;

function safeText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function safeArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function redactSensitiveUrlQueries(text: string): string {
  const sensitiveKeys = new Set([
    "scode",
    "apikey",
    "access_token",
    "token",
    "secret",
    "key",
  ]);
  const redactUrl = (rawUrl: string) => {
    try {
      const parsed = new URL(rawUrl);
      let changed = false;
      parsed.searchParams.forEach((_, key) => {
        const lowerKey = key.toLowerCase();
        if (
          sensitiveKeys.has(lowerKey) ||
          [...sensitiveKeys].some((marker) => lowerKey.includes(marker))
        ) {
          parsed.searchParams.set(key, "***REDACTED***");
          changed = true;
        }
      });
      return changed ? parsed.toString() : rawUrl;
    } catch {
      return rawUrl;
    }
  };

  return text
    .replace(/https?:\/\/[^\s"'<>]+/g, redactUrl)
    .replace(
      /\b(scode|apikey|access_token|token|secret|key)=([^&\s"']+)/gi,
      "$1=***REDACTED***",
    );
}

function compactToolJsonContent(text: string): string {
  let payload: unknown;
  try {
    payload = JSON.parse(text);
  } catch {
    return text;
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return text;
  }
  const record = payload as Record<string, unknown>;
  const rowKey = ["rows", "records", "data"].find((key) =>
    Array.isArray(record[key]),
  );
  if (!rowKey) return text;

  const keepKeys = [
    "status",
    "mode",
    "transport",
    "source_id",
    "dataset",
    "row_count",
    "raw_total_count",
    "schema",
    "source_sheet_ids",
    "doc_url",
    "mcp_url",
    "warnings",
  ];
  const compacted: Record<string, unknown> = {};
  for (const key of keepKeys) {
    if (key in record) compacted[key] = record[key];
  }
  const rows = safeArray(record[rowKey]);
  compacted.sample_rows = rows.slice(0, 3);
  compacted.omitted_row_count = Math.max(0, rows.length - 3);
  compacted.archive_compacted = true;
  return JSON.stringify(compacted);
}

function sanitizeContent(content: unknown): unknown {
  if (typeof content === "string") {
    const redacted = redactSensitiveUrlQueries(content);
    return compactToolJsonContent(redacted).slice(0, MAX_TEXT_CONTENT);
  }
  if (Array.isArray(content)) {
    return content.slice(-20).map((item) => {
      if (!item || typeof item !== "object") return item;
      if ("text" in item && typeof item.text === "string") {
        return {
          ...item,
          text: redactSensitiveUrlQueries(item.text).slice(
            0,
            MAX_TEXT_CONTENT,
          ),
        };
      }
      return item;
    });
  }
  return content;
}

function sanitizeMessages(messages: unknown): ArchiveMessage[] {
  const sanitized = safeArray<ArchiveMessage>(messages)
    .filter((message) => message && typeof message === "object")
    .filter((message) => safeText(message.type) !== "system")
    .map((message) => ({
      id: safeText(message.id),
      type: safeText(message.type),
      content: sanitizeContent(message.content),
      name: safeText(message.name),
      tool_call_id: safeText(message.tool_call_id),
      tool_calls: safeArray(message.tool_calls),
      invalid_tool_calls: safeArray(message.invalid_tool_calls),
    }));
  return repairMissingToolResponsesInMessageOrder(
    sanitized as Message[],
  ).slice(-MAX_ARCHIVED_MESSAGES) as ArchiveMessage[];
}

function getRemoteApiUrl(record: LocalArchivedThreadRecord): string {
  return (
    safeText(record.api_url) ||
    safeText(process.env.NEXT_PUBLIC_API_URL) ||
    "http://127.0.0.1:2024"
  );
}

function isAllowedLocalBackendUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (
      url.protocol === "http:" &&
      ["127.0.0.1", "localhost", "::1"].includes(url.hostname)
    );
  } catch {
    return false;
  }
}

async function fetchRemoteThreadState(
  apiUrl: string,
  originalThreadId: string,
): Promise<LocalArchivedThreadRecord | null> {
  if (!isAllowedLocalBackendUrl(apiUrl)) return null;

  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    REMOTE_THREAD_STATE_TIMEOUT_MS,
  );
  try {
    const response = await fetch(
      `${apiUrl.replace(/\/$/, "")}/threads/${encodeURIComponent(originalThreadId)}/state`,
      {
        cache: "no-store",
        signal: controller.signal,
      },
    );
    if (!response.ok) return null;
    return (await response.json()) as LocalArchivedThreadRecord;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function hydrateArchivedThreadRecord(
  record: LocalArchivedThreadRecord,
): Promise<LocalArchivedThreadRecord> {
  const originalThreadId = safeText(record.original_thread_id);
  const localMessages = sanitizeMessages(record.values?.messages);
  if (!originalThreadId || !shouldHydrateLocalArchiveMessages(localMessages)) {
    return {
      ...record,
      values: {
        ...record.values,
        messages: localMessages,
        ui: safeArray(record.values?.ui),
      },
    };
  }

  const remoteState = await fetchRemoteThreadState(
    getRemoteApiUrl(record),
    originalThreadId,
  );
  const remoteMessages = sanitizeMessages(remoteState?.values?.messages);
  if (remoteMessages.length <= localMessages.length) {
    return {
      ...record,
      values: {
        ...record.values,
        messages: localMessages,
        ui: safeArray(record.values?.ui),
      },
    };
  }

  const hydratedRecord: LocalArchivedThreadRecord = {
    ...record,
    created_at:
      safeText(record.created_at) || safeText(remoteState?.created_at),
    updated_at:
      safeText(remoteState?.updated_at) ||
      safeText(remoteState?.created_at) ||
      safeText(record.updated_at),
    values: {
      ...record.values,
      messages: remoteMessages,
      ui: safeArray(record.values?.ui),
    },
  };
  const targetPath = archiveFilePath(originalThreadId);
  await assertWritableRegularPath(targetPath, THREAD_ARCHIVE_DIR);
  await writeFile(
    targetPath,
    JSON.stringify(hydratedRecord, null, 2),
    "utf8",
  );
  return hydratedRecord;
}

function contentToText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.map(contentToText).filter(Boolean).join("\n");
  }
  if (!content || typeof content !== "object") return "";
  const item = content as { text?: unknown; content?: unknown };
  return contentToText(item.text ?? item.content);
}

function extractTaskIdsFromMessages(messages: ArchiveMessage[] | undefined) {
  const taskIds = new Set<string>();
  for (const message of messages ?? []) {
    const text = contentToText(message.content);
    const matches = text.matchAll(/(?:任务ID|task[_ ]?id)[^`\n]*`([^`]+)`/gi);
    for (const match of matches) {
      if (match[1]) taskIds.add(match[1].trim());
    }
  }
  return taskIds;
}

function taskIdsInArchivedThreads(
  threads: Array<{ values?: { messages?: ArchiveMessage[] } }>,
) {
  const taskIds = new Set<string>();
  for (const thread of threads) {
    for (const taskId of extractTaskIdsFromMessages(thread.values?.messages)) {
      taskIds.add(taskId);
    }
  }
  return taskIds;
}

function extractOriginalUserText(task: WorkflowTask): string {
  const goal = safeText(task.goal);
  const marker = "用户原话：";
  const markerIndex = goal.lastIndexOf(marker);
  if (markerIndex === -1) return "";
  return goal.slice(markerIndex + marker.length).trim();
}

function buildSummary(task: WorkflowTask): string {
  const lines = [
    "📁 **本地归档工作记录**",
    "",
    `**任务ID：** \`${safeText(task.task_id)}\``,
    `**状态：** \`${safeText(task.status) || "unknown"}\``,
    `**创建时间：** ${safeText(task.created_at) || "-"}`,
    `**更新时间：** ${safeText(task.updated_at) || "-"}`,
    "",
    "## 子任务",
  ];

  for (const [index, step] of (task.steps ?? []).entries()) {
    lines.push(
      `${index + 1}. \`${safeText(step.task) || "unknown"}\` - ${safeText(step.status) || "unknown"}`,
    );
    if (step.summary) lines.push(`   - ${step.summary}`);
    for (const risk of step.risks?.slice(0, 3) ?? []) {
      lines.push(`   - 风险：${risk}`);
    }
    for (const missing of step.missing_data?.slice(0, 3) ?? []) {
      lines.push(`   - 缺失：${missing}`);
    }
  }

  if (task.final_report?.saved_to) {
    lines.push("", "## 最终报告", `- \`${task.final_report.saved_to}\``);
  }

  lines.push(
    "",
    "> 这是从本地 `data/tasks` 恢复的归档记录；原 LangGraph thread registry 已在后端重启后丢失。",
  );

  return lines.join("\n");
}

async function ensureArchiveDir() {
  await mkdir(THREAD_ARCHIVE_DIR, { recursive: true });
}

function archiveFilePath(originalThreadId: string) {
  return path.join(
    THREAD_ARCHIVE_DIR,
    `${encodeURIComponent(originalThreadId)}.json`,
  );
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

async function assertWritableRegularPath(filePath: string, rootPath: string) {
  const root = await safeRealRoot(rootPath);
  const resolvedParent = await safeRealRoot(path.dirname(filePath));
  if (!isPathUnder(resolvedParent, root)) {
    throw new Error("目标路径不在归档目录内。");
  }
  try {
    const fileStat = await lstat(filePath);
    if (fileStat.isSymbolicLink() || !fileStat.isFile()) {
      throw new Error("目标归档文件不是普通文件。");
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return;
    throw error;
  }
}

async function safeJsonFiles(directory: string) {
  const root = await safeRealRoot(directory);
  const files = await readdir(directory);
  const jsonFiles: Array<{
    file: string;
    fullPath: string;
    mtimeMs: number;
  }> = [];
  for (const file of files.filter((item) => item.endsWith(".json"))) {
    try {
      const fullPath = path.join(directory, file);
      const fileStat = await lstat(fullPath);
      if (fileStat.isSymbolicLink() || !fileStat.isFile()) continue;
      const resolved = await realpath(fullPath);
      if (!isPathUnder(resolved, root)) continue;
      jsonFiles.push({ file, fullPath: resolved, mtimeMs: fileStat.mtimeMs });
    } catch {
      // Skip files that disappear or become unreadable during local writes.
    }
  }
  return jsonFiles;
}

async function readTaskThreads(hiddenTaskIds = new Set<string>()) {
  try {
    const jsonFiles = await safeJsonFiles(TASKS_DIR);

    const threads = [];
    for (const item of jsonFiles
      .sort((left, right) => right.mtimeMs - left.mtimeMs)
      .slice(0, MAX_TASK_THREADS)) {
      let task: WorkflowTask;
      try {
        task = JSON.parse(
          await readFile(item.fullPath, "utf8"),
        ) as WorkflowTask;
      } catch {
        continue;
      }
      const taskId = safeText(task.task_id) || item.file.replace(/\.json$/, "");
      if (hiddenTaskIds.has(taskId)) continue;
      const goal = safeText(task.goal) || taskId;
      const displayPrompt = extractOriginalUserText(task) || goal;
      const threadId = `local-task-${encodeURIComponent(item.file.replace(/\.json$/, ""))}`;

      threads.push({
        thread_id: threadId,
        created_at: task.created_at ?? new Date(item.mtimeMs).toISOString(),
        updated_at: task.updated_at ?? new Date(item.mtimeMs).toISOString(),
        metadata: {
          graph_id: "ecommerce_agent",
          source: LOCAL_ARCHIVE_METADATA_SOURCE,
          task_id: taskId,
        },
        status: "idle",
        values: {
          messages: [
            {
              id: `${threadId}-human`,
              type: "human",
              content: [{ type: "text", text: displayPrompt }],
            },
            {
              id: `${threadId}-ai`,
              type: "ai",
              name: "local_task_archive",
              content: buildSummary(task),
              tool_calls: [],
              invalid_tool_calls: [],
            },
          ],
        },
      });
    }
    return threads;
  } catch {
    return [];
  }
}

async function readArchivedThreads() {
  await ensureArchiveDir();
  const archiveFiles = await safeJsonFiles(THREAD_ARCHIVE_DIR);

  const threads = [];
  for (const item of archiveFiles
    .sort((left, right) => right.mtimeMs - left.mtimeMs)
    .slice(0, MAX_ARCHIVED_THREADS)) {
    let record: LocalArchivedThreadRecord;
    try {
      record = JSON.parse(
        await readFile(item.fullPath, "utf8"),
      ) as LocalArchivedThreadRecord;
    } catch {
      continue;
    }
    let hydratedRecord = record;
    try {
      hydratedRecord = await hydrateArchivedThreadRecord(record);
    } catch {
      hydratedRecord = {
        ...record,
        values: {
          ...record.values,
          messages: sanitizeMessages(record.values?.messages),
          ui: safeArray(record.values?.ui),
        },
      };
    }
    const originalThreadId = safeText(hydratedRecord.original_thread_id);
    if (!originalThreadId) continue;
    threads.push({
      thread_id: buildLocalBrowserArchiveThreadId(originalThreadId),
      created_at:
        hydratedRecord.created_at ?? new Date(item.mtimeMs).toISOString(),
      updated_at:
        hydratedRecord.updated_at ?? new Date(item.mtimeMs).toISOString(),
      metadata: {
        source: LOCAL_BROWSER_ARCHIVE_METADATA_SOURCE,
        original_thread_id: originalThreadId,
        assistant_id: safeText(hydratedRecord.assistant_id),
        api_url: safeText(hydratedRecord.api_url),
      },
      status: "idle",
      values: {
        messages: sanitizeMessages(hydratedRecord.values?.messages),
        ui: safeArray(hydratedRecord.values?.ui),
      },
    });
  }
  return threads;
}

export async function GET(request: NextRequest) {
  const authResponse = workbenchAuthResponse(request, { protectRead: true });
  if (authResponse) return authResponse;
  const archivedThreads = await readArchivedThreads();
  const taskThreads = await readTaskThreads(
    taskIdsInArchivedThreads(archivedThreads),
  );

  const threads = [...archivedThreads, ...taskThreads].sort((left, right) => {
    const leftTime = Date.parse(left.updated_at ?? left.created_at ?? "") || 0;
    const rightTime =
      Date.parse(right.updated_at ?? right.created_at ?? "") || 0;
    return rightTime - leftTime;
  });

  return NextResponse.json({ threads });
}

export async function POST(request: NextRequest) {
  const auth = checkWorkbenchAuth(request);
  if (!auth.ok) {
    return NextResponse.json(
      { error: auth.error },
      { status: auth.status },
    );
  }

  try {
    const body = (await request.json()) as LocalArchivedThreadRecord;
    const originalThreadId = safeText(body.original_thread_id);
    if (!originalThreadId) {
      return NextResponse.json(
        { error: "缺少 original_thread_id" },
        { status: 400 },
      );
    }

    await ensureArchiveDir();
    const payload: LocalArchivedThreadRecord = {
      original_thread_id: originalThreadId,
      created_at: safeText(body.created_at) || new Date().toISOString(),
      updated_at: safeText(body.updated_at) || new Date().toISOString(),
      assistant_id: safeText(body.assistant_id),
      api_url: safeText(body.api_url),
      values: {
        messages: sanitizeMessages(body.values?.messages),
        ui: safeArray(body.values?.ui),
      },
    };
    const targetPath = archiveFilePath(originalThreadId);
    await assertWritableRegularPath(targetPath, THREAD_ARCHIVE_DIR);
    await writeFile(
      targetPath,
      JSON.stringify(payload, null, 2),
      "utf8",
    );

    return NextResponse.json({ status: "ok" });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  const auth = checkWorkbenchAuth(request);
  if (!auth.ok) {
    return NextResponse.json(
      { error: auth.error },
      { status: auth.status },
    );
  }

  try {
    await ensureArchiveDir();
    const threadId = request.nextUrl.searchParams.get("threadId");
    const clearAll = request.nextUrl.searchParams.get("all") === "1";

    if (clearAll) {
      const confirmAll = request.nextUrl.searchParams.get("confirm");
      if (confirmAll !== "1" && confirmAll !== "true") {
        return NextResponse.json(
          {
            error: "批量删除所有归档线程需要明确确认。请添加 confirm=1 参数。",
          },
          { status: 400 },
        );
      }
      const files = await readdir(THREAD_ARCHIVE_DIR);
      await Promise.all(
        files
          .filter((file) => file.endsWith(".json"))
          .map((file) =>
            rm(path.join(THREAD_ARCHIVE_DIR, file), {
              force: true,
            }),
          ),
      );
      return NextResponse.json({ status: "ok" });
    }

    if (!threadId) {
      return NextResponse.json(
        { error: "缺少 threadId" },
        { status: 400 },
      );
    }

    if (threadId.startsWith(LOCAL_ARCHIVE_THREAD_ID_PREFIX)) {
      const taskFileStem = decodeURIComponent(
        threadId.slice(LOCAL_ARCHIVE_THREAD_ID_PREFIX.length),
      );
      const taskFile = path.basename(`${taskFileStem}.json`);
      await rm(path.join(TASKS_DIR, taskFile), { force: true });
      return NextResponse.json({ status: "ok" });
    }

    const originalThreadId = decodeURIComponent(
      threadId.startsWith(LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX)
        ? threadId.slice(LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX.length)
        : threadId,
    );
    await rm(archiveFilePath(originalThreadId), { force: true });
    return NextResponse.json({ status: "ok" });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
