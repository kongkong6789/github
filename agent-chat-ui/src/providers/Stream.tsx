import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useEffect,
  useMemo,
  useRef,
} from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { type Message } from "@langchain/langgraph-sdk";
import {
  uiMessageReducer,
  isUIMessage,
  isRemoveUIMessage,
  type UIMessage,
  type RemoveUIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LangGraphLogoSVG } from "@/components/icons/langgraph";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ArrowRight } from "lucide-react";
import { PasswordInput } from "@/components/ui/password-input";
import { getApiKey, storeApiKey } from "@/lib/api-key";
import {
  getRenderableChatMessages,
  getRunnableThreadId,
  resolveStreamThreadIdState,
  getThreadValuesWithMessages,
  isLocalArchiveThread,
  isLocalArchiveThreadId,
  shouldUseLocalArchiveDisplayValues,
} from "@/lib/local-archive-thread";
import { shouldSuppressStreamConsoleError } from "@/lib/stream-errors";
import { useThreads } from "./Thread";

export type StateType = { messages: Message[]; ui?: UIMessage[] };

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
      context?: Record<string, unknown>;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

type StreamContextType = ReturnType<typeof useTypedStream>;
const StreamContext = createContext<StreamContextType | undefined>(undefined);

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkGraphStatus(
  apiUrl: string,
  apiKey: string | null,
  authScheme?: string,
): Promise<boolean> {
  const headers = new Headers();
  if (apiKey) headers.set("X-Api-Key", apiKey);
  if (authScheme) headers.set("X-Auth-Scheme", authScheme);

  for (const endpoint of ["/ok", "/info"]) {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const res = await fetch(`${apiUrl}${endpoint}`, { headers });
        if (res.ok) return true;
      } catch {
        // Ignore transient local dev-server restarts; callers decide how to notify.
      }
      await sleep(800);
    }
  }
  return false;
}

const StreamSession = ({
  children,
  apiKey,
  apiUrl,
  assistantId,
  authScheme,
}: {
  children: ReactNode;
  apiKey: string | null;
  apiUrl: string;
  assistantId: string;
  authScheme?: string;
}) => {
  const [threadId, setThreadId] = useQueryState("threadId");
  const { getThreads, setThreads, threads } = useThreads();
  const [threadSearchValues, setThreadSearchValues] = useState<
    StateType | undefined
  >();
  const isViewingLocalArchive = isLocalArchiveThreadId(threadId);
  const [streamThreadId, setStreamThreadId] = useState<string | null>(() =>
    getRunnableThreadId(threadId),
  );
  const pendingCreatedThreadIdRef = useRef<string | null>(null);
  const lastArchivedSignatureRef = useRef<string>("");

  useEffect(() => {
    const originalConsoleError = console.error;
    console.error = (...args: unknown[]) => {
      if (args.some(shouldSuppressStreamConsoleError)) {
        return;
      }
      originalConsoleError(...args);
    };
    return () => {
      if (console.error !== originalConsoleError) {
        console.error = originalConsoleError;
      }
    };
  }, []);

  const externalThread = useMemo(
    () =>
      isViewingLocalArchive
        ? {
            data: threadSearchValues
              ? [
                  {
                    values: threadSearchValues,
                    next: [],
                    tasks: [],
                    metadata: null,
                    created_at: null,
                    checkpoint: null,
                    parent_checkpoint: null,
                    interrupts: [],
                  } as any,
                ]
              : [],
            error: undefined,
            isLoading: false,
            mutate: async () =>
              threadSearchValues
                ? ([
                    {
                      values: threadSearchValues,
                      next: [],
                      tasks: [],
                      metadata: null,
                      created_at: null,
                      checkpoint: null,
                      parent_checkpoint: null,
                      interrupts: [],
                    } as any,
                  ] as any)
                : [],
          }
        : undefined,
    [isViewingLocalArchive, threadSearchValues],
  );

  useEffect(() => {
    if (!isViewingLocalArchive) {
      setThreadSearchValues(undefined);
      return;
    }

    const archivedThread = threads.find(
      (thread) => thread.thread_id === threadId && isLocalArchiveThread(thread),
    );
    const values = getThreadValuesWithMessages(archivedThread?.values) as
      | StateType
      | undefined;
    if (values) {
      setThreadSearchValues(values);
    }
  }, [isViewingLocalArchive, threadId, threads]);

  useEffect(() => {
    if (!isViewingLocalArchive || !threadId) return;

    let cancelled = false;

    async function loadArchivedThread() {
      try {
        const response = await fetch("/api/local-threads", {
          cache: "no-store",
        });
        if (!response.ok) return;

        const data = (await response.json()) as {
          threads?: Array<{ thread_id?: string; values?: unknown }>;
        };
        const archivedThread = data.threads?.find(
          (thread) => thread.thread_id === threadId,
        );
        const values = getThreadValuesWithMessages(archivedThread?.values) as
          | StateType
          | undefined;
        if (!cancelled && values) {
          setThreadSearchValues(values);
        }
      } catch {
        // Local archive hydration is best-effort; the history panel will still
        // show whatever was already available.
      }
    }

    void loadArchivedThread();
    return () => {
      cancelled = true;
    };
  }, [isViewingLocalArchive, threadId]);

  const streamValue = useTypedStream({
    apiUrl,
    apiKey: apiKey ?? undefined,
    assistantId,
    ...(authScheme && {
      defaultHeaders: {
        "X-Auth-Scheme": authScheme,
      },
    }),
    threadId: streamThreadId,
    fetchStateHistory: true,
    initialValues: isViewingLocalArchive ? threadSearchValues : undefined,
    ...(externalThread ? { experimental_thread: externalThread } : {}),
    onCustomEvent: (event, options) => {
      if (isUIMessage(event) || isRemoveUIMessage(event)) {
        options.mutate((prev) => {
          const ui = uiMessageReducer(prev.ui ?? [], event);
          return { ...prev, ui };
        });
      }
    },
    onThreadId: (id) => {
      pendingCreatedThreadIdRef.current = id;
    },
  });

  const contextValue = useMemo(() => {
    if (
      shouldUseLocalArchiveDisplayValues({
        isViewingLocalArchive,
        hasThreadSearchValues: Boolean(threadSearchValues),
        isLoading: streamValue.isLoading,
        pendingCreatedThreadId: pendingCreatedThreadIdRef.current,
      }) &&
      threadSearchValues
    ) {
      return {
        ...streamValue,
        values: threadSearchValues,
        messages: threadSearchValues.messages,
      } as StreamContextType;
    }
    return streamValue;
  }, [isViewingLocalArchive, streamValue, threadSearchValues]);

  useEffect(() => {
    const { nextPendingCreatedThreadId, nextStreamThreadId } =
      resolveStreamThreadIdState({
        urlThreadId: threadId,
        currentStreamThreadId: streamThreadId,
        pendingCreatedThreadId: pendingCreatedThreadIdRef.current,
        isLoading: streamValue.isLoading,
      });

    pendingCreatedThreadIdRef.current = nextPendingCreatedThreadId;
    if (nextStreamThreadId !== streamThreadId) {
      setStreamThreadId(nextStreamThreadId);
    }
  }, [streamThreadId, streamValue.isLoading, threadId]);

  useEffect(() => {
    if (streamValue.isLoading || pendingCreatedThreadIdRef.current == null) {
      return;
    }

    const createdThreadId = pendingCreatedThreadIdRef.current;
    pendingCreatedThreadIdRef.current = null;
    setStreamThreadId(createdThreadId);
    setThreadId(createdThreadId);
    sleep().then(() =>
      getThreads()
        .then(setThreads)
        .catch(() => {}),
    );
  }, [getThreads, setThreadId, setThreads, streamValue.isLoading]);

  useEffect(() => {
    checkGraphStatus(apiUrl, apiKey, authScheme).then((ok) => {
      if (!ok) {
        // The chat surface will show request-specific failures when a user
        // sends a message. Avoid a persistent dev-only health-check toast here,
        // because local LangGraph restarts can fail this probe transiently.
      }
    });
  }, [apiKey, apiUrl, authScheme]);

  useEffect(() => {
    const archiveThreadId =
      streamThreadId ?? pendingCreatedThreadIdRef.current ?? null;
    const archivableMessages = getRenderableChatMessages(streamValue.messages);
    if (
      isViewingLocalArchive ||
      !archiveThreadId ||
      !archivableMessages.length ||
      isLocalArchiveThreadId(archiveThreadId)
    ) {
      return;
    }

    const signature = `${archiveThreadId}:${archivableMessages.length}:${
      archivableMessages[archivableMessages.length - 1]?.id ?? ""
    }`;
    if (lastArchivedSignatureRef.current === signature) {
      return;
    }
    lastArchivedSignatureRef.current = signature;

    const payload = {
      original_thread_id: archiveThreadId,
      updated_at: new Date().toISOString(),
      assistant_id: assistantId,
      api_url: apiUrl,
      values: {
        messages: archivableMessages,
      },
    };

    fetch("/api/local-threads", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    }).catch(() => {
      // Archive persistence is best-effort and should not break chat UX.
    });
  }, [
    apiUrl,
    assistantId,
    isViewingLocalArchive,
    streamValue.messages,
    streamThreadId,
  ]);

  return (
    <StreamContext.Provider value={contextValue}>
      {children}
    </StreamContext.Provider>
  );
};

// Default values for the form
const DEFAULT_API_URL = "http://localhost:2024";
const DEFAULT_ASSISTANT_ID = "agent";
const AGENT_BUILDER_AUTH_SCHEME = "langsmith-api-key";

export const StreamProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  // Get environment variables
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined =
    process.env.NEXT_PUBLIC_ASSISTANT_ID;
  const envAuthScheme: string | undefined = process.env.NEXT_PUBLIC_AUTH_SCHEME;

  // Use URL params with env var fallbacks
  const [apiUrl, setApiUrl] = useQueryState("apiUrl", {
    defaultValue: envApiUrl || "",
  });
  const [assistantId, setAssistantId] = useQueryState("assistantId", {
    defaultValue: envAssistantId || "",
  });
  const [authScheme, setAuthScheme] = useQueryState("authScheme", {
    defaultValue: envAuthScheme || "",
  });
  const [isAgentBuilder, setIsAgentBuilder] = useState(
    () =>
      (authScheme || envAuthScheme || "").toLowerCase() ===
      AGENT_BUILDER_AUTH_SCHEME,
  );

  // Keep the LangGraph API key session-scoped; env vars still provide defaults.
  const [apiKey, _setApiKey] = useState(() => {
    const storedKey = getApiKey();
    return storedKey || "";
  });

  const setApiKey = (key: string) => {
    storeApiKey(key);
    _setApiKey(key);
  };

  // Determine final values to use, prioritizing URL params then env vars
  const finalApiUrl = apiUrl || envApiUrl;
  const finalAssistantId = assistantId || envAssistantId;
  const finalAuthScheme = authScheme || envAuthScheme || "";

  // Show the form if we: don't have an API URL, or don't have an assistant ID
  if (!finalApiUrl || !finalAssistantId) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-4">
        <div className="animate-in fade-in-0 zoom-in-95 bg-background flex max-w-3xl flex-col rounded-lg border shadow-lg">
          <div className="mt-14 flex flex-col gap-2 border-b p-6">
            <div className="flex flex-col items-start gap-2">
              <LangGraphLogoSVG className="h-7" />
              <h1 className="text-xl font-semibold tracking-tight">
                Agent Chat
              </h1>
            </div>
            <p className="text-muted-foreground">
              Welcome to Agent Chat! Before you get started, you need to enter
              the URL of the deployment and the assistant / graph ID.
            </p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();

              const form = e.target as HTMLFormElement;
              const formData = new FormData(form);
              const apiUrl = formData.get("apiUrl") as string;
              const assistantId = formData.get("assistantId") as string;
              const apiKey = formData.get("apiKey") as string;

              setApiUrl(apiUrl);
              setApiKey(apiKey);
              setAssistantId(assistantId);
              setAuthScheme(isAgentBuilder ? AGENT_BUILDER_AUTH_SCHEME : "");

              form.reset();
            }}
            className="bg-muted/50 flex flex-col gap-6 p-6"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="apiUrl">
                Deployment URL<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                This is the URL of your LangGraph deployment. Can be a local, or
                production deployment.
              </p>
              <Input
                id="apiUrl"
                name="apiUrl"
                className="bg-background"
                defaultValue={apiUrl || DEFAULT_API_URL}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="assistantId">
                Assistant / Graph ID<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                This is the ID of the graph (can be the graph name), or
                assistant to fetch threads from, and invoke when actions are
                taken.
              </p>
              <Input
                id="assistantId"
                name="assistantId"
                className="bg-background"
                defaultValue={assistantId || DEFAULT_ASSISTANT_ID}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="apiKey">LangSmith API Key</Label>
              <p className="text-muted-foreground text-sm">
                This is <strong>NOT</strong> required if using a local LangGraph
                server. This value is stored in your browser's local storage and
                is only used to authenticate requests sent to your LangGraph
                server.
              </p>
              <PasswordInput
                id="apiKey"
                name="apiKey"
                defaultValue={apiKey ?? ""}
                className="bg-background"
                placeholder="lsv2_pt_..."
              />
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-4">
                <div className="flex flex-col gap-1">
                  <Label htmlFor="agentBuilderEnabled">
                    Built with Agent Builder
                  </Label>
                  <p className="text-muted-foreground text-sm">
                    Enable this for Agent Builder deployments.
                  </p>
                </div>
                <Switch
                  id="agentBuilderEnabled"
                  checked={isAgentBuilder}
                  onCheckedChange={setIsAgentBuilder}
                />
              </div>
            </div>

            <div className="mt-2 flex justify-end">
              <Button
                type="submit"
                size="lg"
              >
                Continue
                <ArrowRight className="size-5" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <StreamSession
      apiKey={apiKey}
      apiUrl={finalApiUrl}
      assistantId={finalAssistantId}
      authScheme={finalAuthScheme || undefined}
    >
      {children}
    </StreamSession>
  );
};

// Create a custom hook to use the context
export const useStreamContext = (): StreamContextType => {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error("useStreamContext must be used within a StreamProvider");
  }
  return context;
};

export default StreamContext;
