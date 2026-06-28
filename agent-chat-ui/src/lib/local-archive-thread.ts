import type { Message, Thread } from "@langchain/langgraph-sdk";

import { repairMissingToolResponsesInMessageOrder } from "./ensure-tool-responses";

export const LOCAL_ARCHIVE_THREAD_ID_PREFIX = "local-task-";
export const LOCAL_ARCHIVE_METADATA_SOURCE = "local_task_archive";
export const LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX = "local-archive-";
export const LOCAL_BROWSER_ARCHIVE_METADATA_SOURCE = "local_thread_archive";

export type ThreadValuesWithMessages = {
  messages: Message[];
  ui?: unknown[];
  [key: string]: unknown;
};

function getThreadTimestamp(thread: Pick<Thread, "updated_at" | "created_at">) {
  const source = thread.updated_at ?? thread.created_at;
  if (!source) return 0;
  const parsed = Date.parse(source);
  return Number.isNaN(parsed) ? 0 : parsed;
}

export function isLocalArchiveThreadId(
  threadId: string | null | undefined,
): boolean {
  return (
    typeof threadId === "string" &&
    (threadId.startsWith(LOCAL_ARCHIVE_THREAD_ID_PREFIX) ||
      threadId.startsWith(LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX))
  );
}

export function getRunnableThreadId(
  threadId: string | null | undefined,
): string | null {
  return isLocalArchiveThreadId(threadId) ? null : (threadId ?? null);
}

export function isLocalArchiveThread(
  thread: Pick<Thread, "thread_id" | "metadata"> | null | undefined,
): boolean {
  if (!thread) return false;
  if (isLocalArchiveThreadId(thread.thread_id)) return true;

  const metadata = thread.metadata;
  return (
    !!metadata &&
    typeof metadata === "object" &&
    "source" in metadata &&
    (metadata.source === LOCAL_ARCHIVE_METADATA_SOURCE ||
      metadata.source === LOCAL_BROWSER_ARCHIVE_METADATA_SOURCE)
  );
}

export function buildLocalBrowserArchiveThreadId(
  originalThreadId: string,
): string {
  return `${LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX}${encodeURIComponent(originalThreadId)}`;
}

export function getOriginalThreadIdFromArchiveId(
  threadId: string | null | undefined,
): string | null {
  if (!threadId) return null;
  if (threadId.startsWith(LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX)) {
    return decodeURIComponent(
      threadId.slice(LOCAL_BROWSER_ARCHIVE_THREAD_ID_PREFIX.length),
    );
  }
  return null;
}

function getCanonicalThreadId(thread: Pick<Thread, "thread_id" | "metadata">) {
  const metadata = thread.metadata;
  if (
    metadata &&
    typeof metadata === "object" &&
    "original_thread_id" in metadata &&
    typeof metadata.original_thread_id === "string" &&
    metadata.original_thread_id
  ) {
    return metadata.original_thread_id;
  }
  return thread.thread_id;
}

export function getThreadValuesWithMessages(
  values: unknown,
): ThreadValuesWithMessages | undefined {
  if (!values || typeof values !== "object" || !("messages" in values)) {
    return undefined;
  }

  const messages = (values as { messages?: unknown }).messages;
  if (!Array.isArray(messages)) return undefined;
  return values as ThreadValuesWithMessages;
}

export function isRenderableChatMessage(
  message: Pick<Message, "type"> | null | undefined,
): boolean {
  return !!message && message.type !== "system";
}

function getMessageText(message: Pick<Message, "content">): string {
  const content = message.content;
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => {
      if (typeof part === "string") return part;
      if (!part || typeof part !== "object") return "";
      if ("text" in part && typeof part.text === "string") return part.text;
      return "";
    })
    .filter(Boolean)
    .join("\n");
}

function isSupervisorFinalAiMessage(message: Message): boolean {
  const name = typeof message.name === "string" ? message.name : "";
  return (
    message.type === "ai" &&
    name.endsWith("_supervisor") &&
    (!Array.isArray(message.tool_calls) || message.tool_calls.length === 0)
  );
}

function normalizeAssistantText(text: string): string {
  return text
    .replace(/^现在作为[\s\S]{0,260}?最终呈现给用户。\s*/u, "")
    .replace(/^[\s\-—_]+/u, "")
    .replace(/\s+/g, " ")
    .trim();
}

function areDuplicateSupervisorFinalMessages(
  previous: Message,
  current: Message,
): boolean {
  if (
    !isSupervisorFinalAiMessage(previous) ||
    !isSupervisorFinalAiMessage(current)
  ) {
    return false;
  }

  const previousText = normalizeAssistantText(getMessageText(previous));
  const currentText = normalizeAssistantText(getMessageText(current));
  if (!previousText || !currentText) return false;
  if (previousText === currentText) return true;

  const shorter =
    previousText.length <= currentText.length ? previousText : currentText;
  const longer =
    previousText.length > currentText.length ? previousText : currentText;
  if (shorter.length < 500) return false;

  const head = shorter.slice(0, Math.min(700, shorter.length));
  const tail = shorter.slice(Math.max(0, shorter.length - 700));
  return longer.includes(head) && longer.includes(tail);
}

export function getRenderableChatMessages(messages: Message[]): Message[] {
  const renderableMessages: Message[] = [];
  for (const message of messages) {
    if (!isRenderableChatMessage(message)) continue;

    const previous = renderableMessages[renderableMessages.length - 1];
    if (previous && areDuplicateSupervisorFinalMessages(previous, message)) {
      renderableMessages[renderableMessages.length - 1] = message;
      continue;
    }

    renderableMessages.push(message);
  }
  return renderableMessages;
}

export function shouldHydrateLocalArchiveMessages(
  messages: Array<{ type?: string; tool_calls?: unknown[] | null }>,
): boolean {
  const renderableMessages = messages.filter(
    (message) => message && message.type !== "system",
  );
  if (!renderableMessages.length) return true;
  if (!renderableMessages.some((message) => message.type === "ai")) return true;

  const lastMessage = renderableMessages[renderableMessages.length - 1];
  if (lastMessage.type !== "ai") return true;
  return (
    Array.isArray(lastMessage.tool_calls) && lastMessage.tool_calls.length > 0
  );
}

export function getSubmitMessagesForThread({
  currentMessages,
  newHumanMessage,
  isViewingLocalArchive,
}: {
  currentMessages: Message[];
  newHumanMessage: Message;
  isViewingLocalArchive: boolean;
}): Message[] {
  return [
    ...(isViewingLocalArchive
      ? repairMissingToolResponsesInMessageOrder(
          getRenderableChatMessages(currentMessages),
        )
      : []),
    newHumanMessage,
  ];
}

export function shouldUseLocalArchiveDisplayValues({
  isViewingLocalArchive,
  hasThreadSearchValues,
  isLoading,
  pendingCreatedThreadId,
}: {
  isViewingLocalArchive: boolean;
  hasThreadSearchValues: boolean;
  isLoading: boolean;
  pendingCreatedThreadId: string | null;
}): boolean {
  return (
    isViewingLocalArchive &&
    hasThreadSearchValues &&
    !isLoading &&
    pendingCreatedThreadId === null
  );
}

export function mergeThreadLists(
  remoteThreads: Thread[],
  localArchivedThreads: Thread[],
): Thread[] {
  const merged = new Map<string, Thread>();

  for (const thread of remoteThreads) {
    merged.set(getCanonicalThreadId(thread), thread);
  }

  for (const thread of localArchivedThreads) {
    const canonicalId = getCanonicalThreadId(thread);
    if (!merged.has(canonicalId)) {
      merged.set(canonicalId, thread);
    }
  }

  return [...merged.values()].sort(
    (left, right) => getThreadTimestamp(right) - getThreadTimestamp(left),
  );
}

export function resolveStreamThreadIdState({
  urlThreadId,
  currentStreamThreadId,
  pendingCreatedThreadId,
  isLoading,
}: {
  urlThreadId: string | null | undefined;
  currentStreamThreadId: string | null;
  pendingCreatedThreadId: string | null;
  isLoading: boolean;
}): {
  nextStreamThreadId: string | null;
  nextPendingCreatedThreadId: string | null;
} {
  if (isLocalArchiveThreadId(urlThreadId)) {
    return {
      nextStreamThreadId: null,
      nextPendingCreatedThreadId: null,
    };
  }

  const nextRunnableThreadId = getRunnableThreadId(urlThreadId);
  if (
    pendingCreatedThreadId &&
    pendingCreatedThreadId === nextRunnableThreadId &&
    isLoading
  ) {
    return {
      nextStreamThreadId: currentStreamThreadId,
      nextPendingCreatedThreadId: pendingCreatedThreadId,
    };
  }

  return {
    nextStreamThreadId: nextRunnableThreadId,
    nextPendingCreatedThreadId:
      pendingCreatedThreadId === nextRunnableThreadId
        ? null
        : pendingCreatedThreadId,
  };
}
