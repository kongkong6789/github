import { v4 as uuidv4 } from "uuid";
import {
  type ComponentType,
  ReactNode,
  useCallback,
  useEffect,
  useRef,
} from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";
import { useState, FormEvent } from "react";
import { Button } from "../ui/button";
import { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import {
  DO_NOT_RENDER_ID_PREFIX,
  ensureToolCallsHaveResponses,
} from "@/lib/ensure-tool-responses";
import {
  getRenderableChatMessages,
  getSubmitMessagesForThread,
  isLocalArchiveThreadId,
} from "@/lib/local-archive-thread";
import {
  toFriendlyStreamError,
  type FriendlyStreamError,
} from "@/lib/stream-errors";
import { TooltipIconButton } from "./tooltip-icon-button";
import {
  ArrowDown,
  BarChart3,
  BookOpen,
  BriefcaseBusiness,
  ClipboardList,
  DatabaseZap,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LoaderCircle,
  PanelRightOpen,
  PanelRightClose,
  SquarePen,
  XIcon,
  Plus,
  ScrollText,
  SendHorizontal,
  ShieldCheck,
} from "lucide-react";
import { useQueryState, parseAsBoolean } from "nuqs";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import ThreadHistory from "./history";
import { toast } from "sonner";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";
import { useFileUpload } from "@/hooks/use-file-upload";
import { ContentBlocksPreview } from "./ContentBlocksPreview";
import { AgentTracePanel } from "./agent-trace-panel";
import {
  useArtifactOpen,
  ArtifactContent,
  ArtifactTitle,
  useArtifactContext,
} from "./artifact";
import { workbenchNavItems } from "@/lib/workbench-nav";

function StickyToBottomContent(props: {
  content: ReactNode;
  footer?: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  const context = useStickToBottomContext();
  return (
    <div
      ref={context.scrollRef}
      style={{ width: "100%", height: "100%" }}
      className={props.className}
    >
      <div
        ref={context.contentRef}
        className={props.contentClassName}
      >
        {props.content}
      </div>

      {props.footer}
    </div>
  );
}

function ScrollToBottom(props: { className?: string }) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      className={props.className}
      onClick={() => scrollToBottom()}
    >
      <ArrowDown className="h-4 w-4" />
      <span>回到底部</span>
    </Button>
  );
}

type LightRAGStatusCounts = {
  processed?: number;
  processing?: number;
  pending?: number;
  failed?: number;
  all?: number;
};

type LightRAGStatus = {
  status: "idle" | "loading" | "success" | "unavailable";
  status_counts: LightRAGStatusCounts;
  pipeline_busy?: boolean;
  error?: string;
};

async function parseLightRAGStatusResponse(
  response: Response,
): Promise<LightRAGStatus> {
  const text = await response.text();
  try {
    return JSON.parse(text) as LightRAGStatus;
  } catch {
    return {
      status: "unavailable",
      status_counts: {},
      pipeline_busy: false,
      error: `知识库状态接口返回了非 JSON 响应（HTTP ${response.status}）。请刷新页面或查看 frontend.err.log。`,
    };
  }
}

function LightRAGStatusStrip() {
  const [status, setStatus] = useState<LightRAGStatus>({
    status: "idle",
    status_counts: {},
  });

  useEffect(() => {
    let cancelled = false;
    let requestSeq = 0;

    async function loadStatus() {
      const seq = ++requestSeq;
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 5000);
      setStatus((prev) => ({
        ...prev,
        status: prev.status === "idle" ? "loading" : prev.status,
      }));
      try {
        const response = await fetch("/api/lightrag-status", {
          cache: "no-store",
          signal: controller.signal,
        });
        const data = await parseLightRAGStatusResponse(response);
        if (!cancelled && seq === requestSeq) {
          setStatus({
            status:
              response.ok && data.status !== "unavailable"
                ? "success"
                : "unavailable",
            status_counts: data.status_counts ?? {},
            pipeline_busy: data.pipeline_busy,
            error: data.error,
          });
        }
      } catch (error) {
        if (!cancelled && seq === requestSeq) {
          setStatus({
            status: "unavailable",
            status_counts: {},
            error: error instanceof Error ? error.message : String(error),
          });
        }
      } finally {
        window.clearTimeout(timer);
      }
    }

    loadStatus();
    const timer = window.setInterval(loadStatus, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const counts = status.status_counts;
  const failed = counts.failed ?? 0;
  const isBusy =
    status.pipeline_busy ||
    (counts.pending ?? 0) > 0 ||
    (counts.processing ?? 0) > 0;
  const tone =
    status.status === "unavailable"
      ? "border-slate-200 bg-white text-slate-500"
      : failed > 0
        ? "border-rose-200 bg-rose-50 text-rose-700"
        : isBusy
          ? "border-blue-200 bg-blue-50 text-blue-700"
          : "border-emerald-200 bg-emerald-50 text-emerald-700";
  const visibleStatus =
    status.status === "unavailable"
      ? "知识库待连接"
      : failed > 0
        ? `${failed} 项待处理`
        : isBusy
          ? "资料处理中"
          : "知识库可用";

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "flex h-9 max-w-full items-center gap-2 rounded-full border px-3 text-xs font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]",
              tone,
            )}
          >
            <DatabaseZap className="size-4 shrink-0" />
            <span className="whitespace-nowrap">{visibleStatus}</span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top">
          <p className="max-w-[280px]">
            {status.status === "unavailable"
              ? `知识库状态暂时不可用：${status.error ?? "未知错误"}`
              : `已处理 ${counts.processed ?? 0}，处理中 ${
                  counts.processing ?? 0
                }，排队 ${counts.pending ?? 0}，失败 ${failed}，总计 ${
                  counts.all ?? 0
                }`}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function CompanyBrand(props: { compact?: boolean }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#004ac6] text-sm font-semibold text-white shadow-[0_12px_28px_rgba(0,74,198,0.22)]">
        A2A
      </div>
      {!props.compact && (
        <div className="min-w-0">
          <div className="truncate text-xl font-semibold tracking-tight text-[#191b23]">
            A2A 经营大脑
          </div>
          <div className="truncate text-xs text-[#5f6372]">
            经营工作台
          </div>
        </div>
      )}
    </div>
  );
}

type HomeTaskAction = {
  label: string;
  description: string;
  prompt: string;
  icon: ComponentType<{ className?: string }>;
};

const homeTaskActions: HomeTaskAction[] = [
  {
    label: "整理资料",
    description: "把文件变成可查资料",
    icon: BookOpen,
    prompt:
      "我已经把资料放到 raw 目录了，请帮我整理成能查、能引用的资料库，并列出哪些内容需要我确认。",
  },
  {
    label: "经营分析",
    description: "结论、风险、下一步",
    icon: BriefcaseBusiness,
    prompt:
      "请基于现有资料和数据做一次经营分析，用老板和 PM 能看懂的话告诉我：关键结论、主要风险、下一步动作。",
  },
  {
    label: "广告诊断",
    description: "预算、转化、素材",
    icon: BarChart3,
    prompt:
      "请帮我诊断电商广告投放，指出预算浪费、转化异常、素材或人群问题，并给出可执行优化建议。",
  },
  {
    label: "库存风险",
    description: "缺货和积压预警",
    icon: ClipboardList,
    prompt:
      "请帮我看库存风险，哪些商品可能缺货或积压，并按优先级列出补货、调拨或清仓建议。",
  },
  {
    label: "老板报告",
    description: "周报和决策摘要",
    icon: FileText,
    prompt:
      "请生成一份老板能快速看懂的经营汇报，包含本周结论、异常风险、需要确认的问题和下周动作。",
  },
  {
    label: "同步资料",
    description: "更新知识库状态",
    icon: DatabaseZap,
    prompt:
      "我更新了业务资料，请帮我同步并检查资料是否可用于后续分析；如果有失败或缺口，请用清单告诉我。",
  },
];

export function Thread() {
  const [artifactContext, setArtifactContext] = useArtifactContext();
  const [artifactOpen, closeArtifact] = useArtifactOpen();

  const [threadId, _setThreadId] = useQueryState("threadId");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );
  const [hideToolCalls, setHideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  const [input, setInput] = useState("");
  const {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    resetBlocks: _resetBlocks,
    dragOver,
    handlePaste,
  } = useFileUpload();
  const [firstTokenReceived, setFirstTokenReceived] = useState(false);
  const [friendlyStreamError, setFriendlyStreamError] =
    useState<FriendlyStreamError | null>(null);
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  const stream = useStreamContext();
  const messages = stream.messages;
  const renderableMessages = getRenderableChatMessages(messages);
  const isLoading = stream.isLoading;
  const isViewingLocalArchive = isLocalArchiveThreadId(threadId);

  const lastError = useRef<string | undefined>(undefined);

  const setThreadId = (id: string | null) => {
    _setThreadId(id);

    // close artifact and reset artifact context
    closeArtifact();
    setArtifactContext({});
  };

  const focusComposer = useCallback(() => {
    window.setTimeout(() => composerRef.current?.focus(), 0);
  }, []);

  const fillComposerPrompt = useCallback(
    (prompt: string) => {
      setInput(prompt);
      focusComposer();
    },
    [focusComposer],
  );

  const resetHomeTask = () => {
    setThreadId(null);
    setInput("");
    focusComposer();
  };

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      if (typeof detail === "string") {
        fillComposerPrompt(detail);
      }
    };
    window.addEventListener("a2a-fill-chat-input", handler);
    return () => window.removeEventListener("a2a-fill-chat-input", handler);
  }, [fillComposerPrompt]);

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      setFriendlyStreamError(null);
      return;
    }
    try {
      const friendlyError = toFriendlyStreamError(stream.error);
      const message = friendlyError.rawMessage;
      if (!message || lastError.current === message) {
        // Message has already been logged. do not modify ref, return early.
        return;
      }

      // Message is defined, and it has not been logged yet. Save it, and send the error
      lastError.current = message;
      setFriendlyStreamError(friendlyError);
      toast.error(friendlyError.title, {
        description: friendlyError.description,
        richColors: true,
        closeButton: true,
      });
    } catch {
      // no-op
    }
  }, [stream.error]);

  // TODO: this should be part of the useStream hook
  const prevMessageLength = useRef(0);
  useEffect(() => {
    if (
      messages.length !== prevMessageLength.current &&
      messages?.length &&
      messages[messages.length - 1].type === "ai"
    ) {
      setFirstTokenReceived(true);
    }

    prevMessageLength.current = messages.length;
  }, [messages]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if ((input.trim().length === 0 && contentBlocks.length === 0) || isLoading)
      return;
    setFirstTokenReceived(false);

    const newHumanMessage: Message = {
      id: uuidv4(),
      type: "human",
      content: [
        ...(input.trim().length > 0 ? [{ type: "text", text: input }] : []),
        ...contentBlocks,
      ] as Message["content"],
    };

    const toolMessages = ensureToolCallsHaveResponses(stream.messages);
    const submitMessages = getSubmitMessagesForThread({
      currentMessages: stream.messages,
      newHumanMessage,
      isViewingLocalArchive,
    });

    const archiveContext =
      isViewingLocalArchive && threadId
        ? {
            local_archive: {
              source_thread_id: threadId,
              carried_message_count: stream.messages.length,
            },
          }
        : undefined;
    const contextValues = {
      ...(Object.keys(artifactContext).length > 0 ? artifactContext : {}),
      ...(archiveContext ?? {}),
    };
    const context =
      Object.keys(contextValues).length > 0 ? contextValues : undefined;

    setFriendlyStreamError(null);
    stream.submit(
      { messages: submitMessages, context },
      {
        streamMode: ["values"],
        streamSubgraphs: true,
        streamResumable: true,
        optimisticValues: (prev) => ({
          ...prev,
          context,
          messages: [
            ...(prev.messages ?? []),
            ...toolMessages,
            newHumanMessage,
          ],
        }),
      },
    );

    setInput("");
    setContentBlocks([]);
  };

  const handleRegenerate = (
    parentCheckpoint: Checkpoint | null | undefined,
  ) => {
    if (isViewingLocalArchive) {
      toast.info("本地归档仅供查看，输入新问题会开启新对话。");
      return;
    }

    // Do this so the loading state is correct
    prevMessageLength.current = prevMessageLength.current - 1;
    setFirstTokenReceived(false);
    setFriendlyStreamError(null);
    stream.submit(undefined, {
      checkpoint: parentCheckpoint,
      streamMode: ["values"],
      streamSubgraphs: true,
      streamResumable: true,
    });
  };

  const chatStarted = !!threadId || !!messages.length;
  const hasNoAIOrToolMessages = !renderableMessages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const showInlineHistory = chatHistoryOpen && isLargeScreen;

  if (!chatStarted) {
    return (
      <div className="h-[100dvh] overflow-hidden bg-[#faf8ff] text-[#191b23]">
        {!isLargeScreen && (
          <div className="lg:hidden">
            <ThreadHistory variant="rail" />
          </div>
        )}

        <motion.div className="grid h-[100dvh] xl:grid-cols-[15rem_minmax(0,1fr)]">
          <aside className="relative hidden h-[100dvh] overflow-y-auto border-r border-[#d9dceb] bg-[#e4e1e6] px-3 py-6 xl:flex xl:flex-col">
            <a
              href="/"
              className="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-white/55"
              aria-label="返回 A2A 经营大脑"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#004ac6] text-sm font-black text-white shadow-[0_12px_24px_rgba(0,74,198,0.22)]">
                A2A
              </span>
              <span className="min-w-0">
                <span className="block truncate text-base font-semibold text-[#191b23]">
                  A2A 经营大脑
                </span>
                <span className="mt-0.5 block text-xs text-[#5f6372]">
                  经营工作台
                </span>
              </span>
            </a>

            <nav className="mt-7 grid gap-1">
              {workbenchNavItems.map((item) => {
                const opensHistory = item.href === "/?chatHistoryOpen=true";
                const active = opensHistory
                  ? !!chatHistoryOpen
                  : item.href === "/"
                    ? !chatHistoryOpen
                    : false;
                const Icon = item.icon;
                const className = cn(
                  "group flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition",
                  active
                    ? "bg-[#004ac6] font-medium text-white shadow-[0_10px_24px_rgba(0,74,198,0.2)]"
                    : "text-[#434655] hover:bg-white/55 hover:text-[#191b23]",
                );
                const content = (
                  <>
                    <span
                      className={cn(
                        "grid size-5 place-items-center",
                        active ? "text-white" : "text-[#5f6372]",
                      )}
                    >
                      <Icon className="size-4" />
                    </span>
                    <span className="min-w-0 truncate">
                      {item.label}
                    </span>
                  </>
                );

                if (item.href === "/") {
                  return (
                    <button
                      key={item.href}
                      type="button"
                      className={className}
                      onClick={() => {
                        setChatHistoryOpen(false);
                        resetHomeTask();
                      }}
                    >
                      {content}
                    </button>
                  );
                }

                if (opensHistory) {
                  return (
                    <button
                      key={item.href}
                      type="button"
                      className={className}
                      onClick={() => setChatHistoryOpen(true)}
                    >
                      {content}
                    </button>
                  );
                }

                return (
                  <a
                    key={item.href}
                    href={item.href}
                    title={`${item.label} - ${item.description}`}
                    aria-label={item.label}
                    className={className}
                  >
                    {content}
                  </a>
                );
              })}
            </nav>

            <div className="mt-auto rounded-xl border border-[#d9dceb] bg-white/65 p-3">
              <div className="flex items-center gap-2 text-[#004ac6]">
                <ShieldCheck className="size-5" />
                <span className="text-sm font-semibold">本地工作区</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-[#5f6372]">
                当前对话、资料和工具配置都在项目内处理。
              </p>
            </div>
          </aside>

          <main className="relative flex h-[100dvh] min-w-0 flex-col overflow-hidden">
            <header className="flex min-h-16 items-center gap-2 border-b border-[#d9dceb] bg-[#faf8ff]/92 px-4 py-2 backdrop-blur-xl sm:px-6 lg:px-7">
              <div className="flex items-center gap-2 xl:hidden">
                <span className="grid size-9 place-items-center rounded-lg bg-[#004ac6] text-sm font-semibold text-white">
                  A2A
                </span>
                <div>
                  <div className="text-sm font-semibold">A2A 经营大脑</div>
                  <div className="text-xs text-[#5f6372]">经营工作台</div>
                </div>
              </div>
              <div className="hidden items-center gap-4 xl:flex">
                <div className="text-sm font-semibold text-[#004ac6]">
                  A2A 电商经营大脑
                </div>
                <LightRAGStatusStrip />
              </div>
              <Button
                type="button"
                variant="outline"
                aria-label="历史记录"
                className="ml-auto h-9 rounded-lg border-[#d9dceb] bg-white px-3 text-sm font-medium text-[#434655] shadow-none hover:bg-[#f3f3fe] xl:ml-0"
                onClick={() => setChatHistoryOpen((p) => !p)}
              >
                {chatHistoryOpen ? (
                  <PanelRightOpen className="size-4" />
                ) : (
                  <PanelRightClose className="size-4" />
                )}
                <span className="hidden sm:inline">历史记录</span>
              </Button>
              <Button
                asChild
                variant="outline"
                className="hidden h-9 rounded-lg border-[#d9dceb] bg-white px-3 text-sm font-medium text-[#434655] shadow-none hover:bg-[#f3f3fe] lg:inline-flex"
              >
                <a href="/tasks">
                  <LayoutDashboard className="size-4" />
                  工作进度
                </a>
              </Button>
              <Button
                asChild
                variant="outline"
                className="hidden h-9 rounded-lg border-[#d9dceb] bg-white px-3 text-sm font-medium text-[#434655] shadow-none hover:bg-[#f3f3fe] lg:inline-flex"
              >
                <a href="/data-sources">
                  <DatabaseZap className="size-4" />
                  导入资料
                </a>
              </Button>
              <div className="ml-auto flex items-center gap-2">
                <div className="xl:hidden">
                  <LightRAGStatusStrip />
                </div>
                <Button
                  asChild
                  variant="outline"
                  className="hidden h-9 rounded-lg border-[#d9dceb] bg-white px-3 text-sm font-medium text-[#434655] shadow-none hover:bg-[#f3f3fe] sm:inline-flex"
                >
                  <a href="/logs">
                    <ScrollText className="size-4" />
                    问题排查
                  </a>
                </Button>
              </div>
            </header>

            {showInlineHistory ? (
              <section className="relative flex min-h-0 flex-1 px-4 pb-4 sm:px-6 lg:px-7">
                <ThreadHistory variant="inline" />
              </section>
            ) : (
              <section className="relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden px-4 py-6 sm:px-6 lg:px-8">
                <div className="w-full max-w-3xl text-center">
                  <h1 className="text-[30px] font-semibold leading-[38px] tracking-normal text-[#191b23] sm:text-[34px] sm:leading-[42px]">
                    准备开始下一项经营任务
                  </h1>
                  <p className="mt-3 text-base leading-7 text-[#5f6372]">
                    选择快捷任务，或直接描述你的经营目标。
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    {homeTaskActions.map((action) => {
                      const Icon = action.icon;
                      return (
                        <button
                          key={action.label}
                          type="button"
                          className="inline-flex shrink-0 items-center gap-2 rounded-full border border-[#d9dceb] bg-white px-4 py-2 text-sm font-medium text-[#434655] shadow-sm transition hover:-translate-y-0.5 hover:bg-[#f3f3fe] hover:text-[#004ac6]"
                          onClick={() => fillComposerPrompt(action.prompt)}
                          disabled={isLoading}
                          title={action.description}
                        >
                          <Icon className="size-4" />
                          {action.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="mt-8 w-full max-w-3xl">
                  <div
                    ref={dropRef}
                    className={cn(
                      "a2a-composer-glow rounded-[18px] border border-[#d9dceb] bg-white shadow-[0_16px_40px_rgba(25,27,35,0.06)] transition",
                      dragOver && "border-[#b4c5ff] ring-4 ring-[#dbe1ff]",
                    )}
                  >
                    <form
                      onSubmit={handleSubmit}
                      className="grid gap-2"
                    >
                      <ContentBlocksPreview
                        blocks={contentBlocks}
                        onRemove={removeBlock}
                      />
                      {friendlyStreamError && (
                        <div className="mx-4 mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="font-medium">
                                {friendlyStreamError.title}
                              </div>
                              <div className="mt-1 text-amber-800">
                                {friendlyStreamError.description}
                              </div>
                              <div className="mt-1 truncate text-xs text-amber-700">
                                {friendlyStreamError.rawMessage}
                              </div>
                            </div>
                            <button
                              type="button"
                              className="rounded p-1 text-amber-700 hover:bg-amber-100"
                              aria-label="关闭错误提示"
                              onClick={() => setFriendlyStreamError(null)}
                            >
                              <XIcon className="size-4" />
                            </button>
                          </div>
                        </div>
                      )}
                      <textarea
                        ref={composerRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onPaste={handlePaste}
                        onKeyDown={(e) => {
                          if (
                            e.key === "Enter" &&
                            !e.shiftKey &&
                            !e.metaKey &&
                            !e.nativeEvent.isComposing
                          ) {
                            e.preventDefault();
                            const el = e.target as HTMLElement | undefined;
                            const form = el?.closest("form");
                            form?.requestSubmit();
                          }
                        }}
                        placeholder="直接说业务目标，例如：帮我看本周广告花费为什么异常，并生成老板报告"
                        className="min-h-20 resize-none border-none bg-transparent px-4 pt-3 text-base text-[#191b23] shadow-none outline-none placeholder:text-[#8b90a0] focus:ring-0 focus:outline-none"
                      />

                      <div className="flex flex-wrap items-center gap-3 border-t border-[#e1e2ed] px-4 pt-3 pb-3">
                        <span className="hidden items-center gap-2 text-sm text-[#434655] sm:flex">
                          <ShieldCheck className="size-4" />
                          仅本地执行
                        </span>
                        <div className="flex items-center gap-2">
                          <Switch
                            id="render-tool-calls-home"
                            checked={hideToolCalls ?? false}
                            onCheckedChange={setHideToolCalls}
                          />
                          <Label
                            htmlFor="render-tool-calls-home"
                            className="text-sm text-[#434655]"
                          >
                            隐藏执行细节
                          </Label>
                        </div>
                        <Label
                          htmlFor="file-input-home"
                          className="flex min-h-10 cursor-pointer items-center gap-2 rounded-lg px-2 text-sm font-medium text-[#434655] transition hover:bg-[#f3f3fe] hover:text-[#004ac6]"
                        >
                          <FolderOpen className="size-4" />
                          上传资料
                        </Label>
                        <input
                          id="file-input-home"
                          type="file"
                          onChange={handleFileUpload}
                          multiple
                          accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                          className="hidden"
                        />
                        {stream.isLoading ? (
                          <Button
                            key="stop"
                            onClick={() => stream.stop()}
                            className="ml-auto min-h-10 rounded-lg bg-[#004ac6] px-4 text-white shadow-none hover:bg-[#003ea8]"
                          >
                            <LoaderCircle className="size-4 animate-spin" />
                            停止
                          </Button>
                        ) : (
                          <Button
                            type="submit"
                            className="ml-auto min-h-10 rounded-lg bg-[#004ac6] px-4 text-white shadow-none hover:bg-[#003ea8]"
                            disabled={
                              isLoading ||
                              (!input.trim() && contentBlocks.length === 0)
                            }
                          >
                            执行
                            <SendHorizontal className="size-4" />
                          </Button>
                        )}
                      </div>
                    </form>
                  </div>
                </div>
              </section>
            )}
          </main>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#faf8ff] text-[#191b23]">
      {chatHistoryOpen && isLargeScreen && (
        <div
          className="fixed inset-0 z-50 bg-[#191b23]/24 backdrop-blur-[2px]"
          onClick={() => setChatHistoryOpen(false)}
        >
          <div
            className="absolute top-20 left-1/2 h-[min(760px,calc(100vh-6rem))] w-[min(760px,calc(100vw-3rem))] -translate-x-1/2 overflow-hidden rounded-[18px] border border-[#d9dceb] bg-white shadow-[0_28px_90px_rgba(25,27,35,0.2)]"
            onClick={(event) => event.stopPropagation()}
          >
            <ThreadHistory variant="overlay" />
          </div>
        </div>
      )}
      {!isLargeScreen && (
        <div className="lg:hidden">
          <ThreadHistory variant="rail" />
        </div>
      )}

      <aside className="relative hidden h-screen overflow-y-auto border-r border-[#d9dceb] bg-[#e4e1e6] px-3 py-6 xl:flex xl:w-[15rem] xl:shrink-0 xl:flex-col">
        <button
          type="button"
          className="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-white/55"
          aria-label="返回 A2A 经营大脑"
          onClick={() => {
            setChatHistoryOpen(false);
            resetHomeTask();
          }}
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#004ac6] text-sm font-black text-white shadow-[0_12px_24px_rgba(0,74,198,0.22)]">
            A2A
          </span>
          <span className="min-w-0">
            <span className="block truncate text-base font-semibold text-[#191b23]">
              A2A 经营大脑
            </span>
            <span className="mt-0.5 block text-xs text-[#5f6372]">
              经营工作台
            </span>
          </span>
        </button>

        <nav className="mt-7 grid gap-1">
          {workbenchNavItems.map((item) => {
            const opensHistory = item.href === "/?chatHistoryOpen=true";
            const active = opensHistory
              ? !!chatHistoryOpen
              : item.href === "/"
                ? !chatHistoryOpen
                : false;
            const Icon = item.icon;
            const className = cn(
              "group flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition",
              active
                ? "bg-[#004ac6] font-medium text-white shadow-[0_10px_24px_rgba(0,74,198,0.2)]"
                : "text-[#434655] hover:bg-white/55 hover:text-[#191b23]",
            );
            const content = (
              <>
                <span
                  className={cn(
                    "grid size-5 place-items-center",
                    active ? "text-white" : "text-[#5f6372]",
                  )}
                >
                  <Icon className="size-4" />
                </span>
                <span className="min-w-0 truncate">{item.label}</span>
              </>
            );

            if (item.href === "/") {
              return (
                <button
                  key={item.href}
                  type="button"
                  className={className}
                  onClick={() => {
                    setChatHistoryOpen(false);
                    resetHomeTask();
                  }}
                >
                  {content}
                </button>
              );
            }

            if (opensHistory) {
              return (
                <button
                  key={item.href}
                  type="button"
                  className={className}
                  onClick={() => setChatHistoryOpen(true)}
                >
                  {content}
                </button>
              );
            }

            return (
              <a
                key={item.href}
                href={item.href}
                title={`${item.label} - ${item.description}`}
                aria-label={item.label}
                className={className}
              >
                {content}
              </a>
            );
          })}
        </nav>

        <div className="mt-auto rounded-xl border border-[#d9dceb] bg-white/65 p-3">
          <div className="flex items-center gap-2 text-[#004ac6]">
            <ShieldCheck className="size-5" />
            <span className="text-sm font-semibold">本地工作区</span>
          </div>
          <p className="mt-2 text-xs leading-5 text-[#5f6372]">
            当前对话、资料和工具配置都在项目内处理。
          </p>
        </div>
      </aside>

      <div
        className={cn(
          "grid min-w-0 flex-1 grid-cols-[1fr_0fr] transition-all duration-500",
          artifactOpen && "grid-cols-[3fr_2fr]",
        )}
      >
        <motion.div
          className={cn(
            "relative flex min-w-0 flex-1 flex-col overflow-hidden",
            !chatStarted && "grid-rows-[1fr]",
          )}
          layout={isLargeScreen}
        >
          {!chatStarted && (
            <div className="absolute top-0 left-0 z-10 flex w-full items-center justify-between gap-3 p-3 pl-4">
              <div>
                {(!chatHistoryOpen || !isLargeScreen) && (
                  <Button
                    className="hover:bg-slate-100"
                    variant="ghost"
                    onClick={() => setChatHistoryOpen((p) => !p)}
                  >
                    {chatHistoryOpen ? (
                      <PanelRightOpen className="size-5" />
                    ) : (
                      <PanelRightClose className="size-5" />
                    )}
                  </Button>
                )}
              </div>
            </div>
          )}
          {chatStarted && (
            <div className="relative z-10 flex min-h-16 items-center justify-between gap-3 border-b border-[#d9dceb] bg-[#faf8ff]/92 px-4 py-2 backdrop-blur-xl lg:px-6">
              <div className="relative flex items-center justify-start gap-2">
                <div className="absolute left-0 z-10">
                  <Button
                    className="rounded-lg text-[#434655] hover:bg-[#f3f3fe] hover:text-[#004ac6]"
                    variant="ghost"
                    onClick={() => setChatHistoryOpen((p) => !p)}
                  >
                    {chatHistoryOpen ? (
                      <PanelRightOpen className="size-5" />
                    ) : (
                      <PanelRightClose className="size-5" />
                    )}
                  </Button>
                </div>
                <motion.button
                  className="flex cursor-pointer items-center gap-2"
                  onClick={() => setThreadId(null)}
                  animate={{
                    marginLeft: 48,
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 300,
                    damping: 30,
                  }}
                >
                  <CompanyBrand />
                </motion.button>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  asChild
                  variant="outline"
                  className="hidden h-9 rounded-lg border-[#d9dceb] bg-white px-3 text-xs text-[#434655] shadow-none hover:bg-[#f3f3fe] sm:inline-flex"
                >
                  <a href="/tasks">工作进度</a>
                </Button>
                <Button
                  asChild
                  variant="outline"
                  className="hidden h-9 rounded-lg border-[#d9dceb] bg-white px-3 text-xs text-[#434655] shadow-none hover:bg-[#f3f3fe] sm:inline-flex"
                >
                  <a href="/data-health">资料体检</a>
                </Button>
                <Button
                  asChild
                  variant="outline"
                  className="hidden h-9 rounded-lg border-[#d9dceb] bg-white px-3 text-xs text-[#434655] shadow-none hover:bg-[#f3f3fe] lg:inline-flex"
                >
                  <a href="/data-sources">导入资料</a>
                </Button>
                <Button
                  asChild
                  variant="outline"
                  className="hidden h-9 rounded-lg border-[#d9dceb] bg-white px-3 text-xs text-[#434655] shadow-none hover:bg-[#f3f3fe] lg:inline-flex"
                >
                  <a href="/governance?tab=skills">工具权限</a>
                </Button>
                <LightRAGStatusStrip />
                <TooltipIconButton
                  size="lg"
                  className="rounded-lg p-4 text-[#434655] hover:bg-[#f3f3fe] hover:text-[#004ac6]"
                  tooltip="新建对话"
                  variant="ghost"
                  onClick={() => setThreadId(null)}
                >
                  <SquarePen className="size-5" />
                </TooltipIconButton>
              </div>
              <div className="absolute inset-x-0 top-full h-4 bg-gradient-to-b from-[#faf8ff] to-transparent" />
            </div>
          )}

          <StickToBottom className="relative flex-1 overflow-hidden">
            <StickyToBottomContent
              className={cn(
                "absolute inset-0 overflow-y-scroll px-4 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-[#c3c6d7] [&::-webkit-scrollbar-track]:bg-transparent",
                !chatStarted && "flex flex-col items-stretch pt-[18vh]",
                chatStarted && "grid grid-rows-[1fr_auto]",
              )}
              contentClassName={cn(
                "pt-8 max-w-4xl mx-auto flex flex-col gap-4 w-full",
                chatStarted ? "pb-44" : "pb-16",
              )}
              content={
                <>
                  {renderableMessages
                    .filter((m) => !m.id?.startsWith(DO_NOT_RENDER_ID_PREFIX))
                    .map((message, index) =>
                      message.type === "human" ? (
                        <HumanMessage
                          key={message.id || `${message.type}-${index}`}
                          message={message}
                          isLoading={isLoading}
                        />
                      ) : (
                        <AssistantMessage
                          key={message.id || `${message.type}-${index}`}
                          message={message}
                          isLoading={isLoading}
                          handleRegenerate={handleRegenerate}
                        />
                      ),
                    )}
                  {/* Special rendering case where there are no AI/tool messages, but there is an interrupt.
                    We need to render it outside of the messages list, since there are no messages to render */}
                  {hasNoAIOrToolMessages && !!stream.interrupt && (
                    <AssistantMessage
                      key="interrupt-msg"
                      message={undefined}
                      isLoading={isLoading}
                      handleRegenerate={handleRegenerate}
                    />
                  )}
                  {threadId && (
                    <AgentTracePanel
                      key={threadId}
                      threadId={threadId}
                    />
                  )}
                  {isLoading && !firstTokenReceived && (
                    <AssistantMessageLoading />
                  )}
                </>
              }
              footer={
                <div className="sticky bottom-0 flex flex-col items-center gap-3 bg-gradient-to-t from-[#faf8ff] via-[#faf8ff]/96 to-transparent pt-4">
                  {!chatStarted && (
                    <div className="flex items-center gap-3">
                      <CompanyBrand />
                    </div>
                  )}

                  <ScrollToBottom className="animate-in fade-in-0 zoom-in-95 absolute bottom-full left-1/2 mb-4 -translate-x-1/2" />

                  <div
                    ref={dropRef}
                    className={cn(
                      "relative z-10 mx-auto mb-4 w-full max-w-4xl rounded-[18px] border border-[#d9dceb] bg-white shadow-[0_16px_40px_rgba(25,27,35,0.06)] transition-all",
                      dragOver
                        ? "border-[#b4c5ff] ring-2 ring-[#dbe1ff]"
                        : "border-[#d9dceb]",
                    )}
                  >
                    <form
                      onSubmit={handleSubmit}
                      className="mx-auto grid max-w-3xl grid-rows-[auto_auto] gap-1"
                    >
                      <ContentBlocksPreview
                        blocks={contentBlocks}
                        onRemove={removeBlock}
                      />
                      {friendlyStreamError && (
                        <div className="mx-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="font-medium">
                                {friendlyStreamError.title}
                              </div>
                              <div className="mt-1 text-amber-800">
                                {friendlyStreamError.description}
                              </div>
                              <div className="mt-1 truncate text-xs text-amber-700">
                                {friendlyStreamError.rawMessage}
                              </div>
                            </div>
                            <button
                              type="button"
                              className="rounded p-1 text-amber-700 hover:bg-amber-100"
                              aria-label="关闭错误提示"
                              onClick={() => setFriendlyStreamError(null)}
                            >
                              <XIcon className="size-4" />
                            </button>
                          </div>
                        </div>
                      )}
                      <textarea
                        ref={composerRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onPaste={handlePaste}
                        onKeyDown={(e) => {
                          if (
                            e.key === "Enter" &&
                            !e.shiftKey &&
                            !e.metaKey &&
                            !e.nativeEvent.isComposing
                          ) {
                            e.preventDefault();
                            const el = e.target as HTMLElement | undefined;
                            const form = el?.closest("form");
                            form?.requestSubmit();
                          }
                        }}
                        placeholder="直接说业务目标，例如：我放了资料，帮我整理一下"
                        className="field-sizing-content max-h-32 min-h-14 resize-none border-none bg-transparent px-4 pt-3 pb-1 text-[#191b23] shadow-none ring-0 outline-none placeholder:text-[#8b90a0] focus:ring-0 focus:outline-none"
                      />

                      <div className="flex flex-wrap items-center gap-3 border-t border-[#e1e2ed] px-4 py-2">
                        <div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              id="render-tool-calls"
                              checked={hideToolCalls ?? false}
                              onCheckedChange={setHideToolCalls}
                            />
                            <Label
                              htmlFor="render-tool-calls"
                              className="text-sm text-[#434655]"
                            >
                              隐藏工具调用
                            </Label>
                          </div>
                        </div>
                        <Label
                          htmlFor="file-input"
                          className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-[#434655] transition hover:bg-[#f3f3fe] hover:text-[#004ac6]"
                        >
                          <Plus className="size-5" />
                          <span className="text-sm">
                            上传 PDF 或图片
                          </span>
                        </Label>
                        <input
                          id="file-input"
                          type="file"
                          onChange={handleFileUpload}
                          multiple
                          accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                          className="hidden"
                        />
                        {stream.isLoading ? (
                          <Button
                            key="stop"
                            onClick={() => stream.stop()}
                            className="ml-auto rounded-lg bg-[#004ac6] !text-white shadow-none hover:bg-[#003ea8]"
                          >
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                            停止
                          </Button>
                        ) : (
                          <Button
                            type="submit"
                            className="ml-auto rounded-lg bg-[#004ac6] !text-white shadow-none transition-all hover:bg-[#003ea8]"
                            disabled={
                              isLoading ||
                              (!input.trim() && contentBlocks.length === 0)
                            }
                          >
                            发送
                          </Button>
                        )}
                      </div>
                    </form>
                  </div>
                </div>
              }
            />
          </StickToBottom>
        </motion.div>
        <div className="relative flex flex-col border-l border-[#d9dceb] bg-white">
          <div className="absolute inset-0 flex min-w-[30vw] flex-col">
            <div className="grid grid-cols-[1fr_auto] border-b p-4">
              <ArtifactTitle className="truncate overflow-hidden" />
              <button
                onClick={closeArtifact}
                className="cursor-pointer"
              >
                <XIcon className="size-5" />
              </button>
            </div>
            <ArtifactContent className="relative flex-grow" />
          </div>
        </div>
      </div>
    </div>
  );
}
