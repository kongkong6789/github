import { validate } from "uuid";
import { getApiKey } from "@/lib/api-key";
import {
  isLocalArchiveThread,
  isLocalArchiveThreadId,
  mergeThreadLists,
} from "@/lib/local-archive-thread";
import { Thread } from "@langchain/langgraph-sdk";
import { useQueryState } from "nuqs";
import {
  createContext,
  useContext,
  ReactNode,
  useCallback,
  useState,
  Dispatch,
  SetStateAction,
} from "react";
import { createClient } from "./client";

interface ThreadContextType {
  getThreads: () => Promise<Thread[]>;
  deleteThread: (threadId: string) => Promise<void>;
  deleteAllThreads: () => Promise<void>;
  threads: Thread[];
  setThreads: Dispatch<SetStateAction<Thread[]>>;
  threadsLoading: boolean;
  setThreadsLoading: Dispatch<SetStateAction<boolean>>;
}

const ThreadContext = createContext<ThreadContextType | undefined>(undefined);

function getThreadSearchMetadata(
  assistantId: string,
): { graph_id: string } | { assistant_id: string } {
  if (validate(assistantId)) {
    return { assistant_id: assistantId };
  } else {
    return { graph_id: assistantId };
  }
}

async function getLocalArchivedThreads(): Promise<Thread[]> {
  try {
    const response = await fetch("/api/local-threads");
    if (!response.ok) return [];
    const data = (await response.json()) as { threads?: Thread[] };
    return Array.isArray(data.threads) ? data.threads : [];
  } catch {
    return [];
  }
}

async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  fallback: T,
): Promise<T> {
  return new Promise((resolve) => {
    const timeout = setTimeout(() => resolve(fallback), timeoutMs);
    promise
      .then((value) => {
        clearTimeout(timeout);
        resolve(value);
      })
      .catch(() => {
        clearTimeout(timeout);
        resolve(fallback);
      });
  });
}

async function localThreadMutationError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = (await response.json()) as {
      error?: unknown;
      message?: unknown;
    };
    if (typeof payload.error === "string" && payload.error) {
      return payload.error;
    }
    if (typeof payload.message === "string" && payload.message) {
      return payload.message;
    }
  } catch {
    // Non-JSON error bodies are common during local Next.js restarts.
  }
  return `${fallback} (HTTP ${response.status})`;
}

export function ThreadProvider({ children }: { children: ReactNode }) {
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined =
    process.env.NEXT_PUBLIC_ASSISTANT_ID;
  const envAuthScheme: string | undefined = process.env.NEXT_PUBLIC_AUTH_SCHEME;

  const [apiUrl] = useQueryState("apiUrl", {
    defaultValue: envApiUrl || "",
  });
  const [assistantId] = useQueryState("assistantId");
  const [authScheme] = useQueryState("authScheme", {
    defaultValue: envAuthScheme || "",
  });
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);

  const getThreads = useCallback(async (): Promise<Thread[]> => {
    const localArchivedThreadsPromise = getLocalArchivedThreads();
    const resolvedAssistantId = assistantId || envAssistantId;
    if (!apiUrl || !resolvedAssistantId) {
      return localArchivedThreadsPromise;
    }
    const client = createClient(
      apiUrl,
      getApiKey() ?? undefined,
      authScheme || undefined,
    );

    let remoteThreads: Thread[] = [];
    try {
      remoteThreads = await withTimeout(
        client.threads.search({
          metadata: {
            ...getThreadSearchMetadata(resolvedAssistantId),
          },
          limit: 30,
        }),
        2500,
        [],
      );
    } catch {
      remoteThreads = [];
    }

    const localArchivedThreads = await localArchivedThreadsPromise;
    return mergeThreadLists(remoteThreads, localArchivedThreads);
  }, [apiUrl, assistantId, authScheme, envAssistantId]);

  const deleteThread = useCallback(
    async (threadId: string): Promise<void> => {
      if (isLocalArchiveThreadId(threadId)) {
        const response = await fetch(
          `/api/local-threads?threadId=${encodeURIComponent(threadId)}`,
          {
            method: "DELETE",
          },
        );
        if (!response.ok) {
          throw new Error(
            await localThreadMutationError(
              response,
              "Local archived thread could not be deleted.",
            ),
          );
        }
        setThreads((prev) =>
          prev.filter((thread) => thread.thread_id !== threadId),
        );
        return;
      }

      if (!apiUrl) throw new Error("API URL is not configured.");
      const client = createClient(
        apiUrl,
        getApiKey() ?? undefined,
        authScheme || undefined,
      );
      await client.threads.delete(threadId);
      setThreads((prev) =>
        prev.filter((thread) => thread.thread_id !== threadId),
      );
    },
    [apiUrl, authScheme],
  );

  const deleteAllThreads = useCallback(async (): Promise<void> => {
    const currentThreads = threads.filter(
      (thread) => !isLocalArchiveThread(thread),
    );
    const localArchivedThreads = threads.filter((thread) =>
      isLocalArchiveThread(thread),
    );
    const failedThreadIds = new Set<string>();

    if (currentThreads.length) {
      if (!apiUrl) throw new Error("API URL is not configured.");
      const client = createClient(
        apiUrl,
        getApiKey() ?? undefined,
        authScheme || undefined,
      );
      const results = await Promise.allSettled(
        currentThreads.map((thread) => client.threads.delete(thread.thread_id)),
      );
      for (const [index, result] of results.entries()) {
        if (result.status === "rejected") {
          failedThreadIds.add(currentThreads[index].thread_id);
        }
      }
    }
    if (localArchivedThreads.length) {
      const response = await fetch("/api/local-threads?all=1&confirm=1", {
        method: "DELETE",
      });
      if (!response.ok) {
        for (const thread of localArchivedThreads) {
          failedThreadIds.add(thread.thread_id);
        }
      }
    }

    setThreads((prev) =>
      prev.filter((thread) => failedThreadIds.has(thread.thread_id)),
    );
    if (failedThreadIds.size) {
      throw new Error(
        `${failedThreadIds.size} thread(s) could not be deleted.`,
      );
    }
  }, [apiUrl, authScheme, threads]);

  const value = {
    getThreads,
    deleteThread,
    deleteAllThreads,
    threads,
    setThreads,
    threadsLoading,
    setThreadsLoading,
  };

  return (
    <ThreadContext.Provider value={value}>{children}</ThreadContext.Provider>
  );
}

export function useThreads() {
  const context = useContext(ThreadContext);
  if (context === undefined) {
    throw new Error("useThreads must be used within a ThreadProvider");
  }
  return context;
}
