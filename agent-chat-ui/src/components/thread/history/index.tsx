import { Button } from "@/components/ui/button";
import { useThreads } from "@/providers/Thread";
import { isLocalArchiveThread } from "@/lib/local-archive-thread";
import { Thread } from "@langchain/langgraph-sdk";
import { MouseEvent, useEffect, useState } from "react";
import { cn } from "@/lib/utils";

import { getContentString } from "../utils";
import { useQueryState, parseAsBoolean } from "nuqs";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  LoaderCircle,
  PanelRightOpen,
  PanelRightClose,
  Trash2,
  XIcon,
} from "lucide-react";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { toast } from "sonner";

type ThreadHistoryVariant = "rail" | "inline" | "overlay";

function ThreadList({
  threads,
  onThreadClick,
  onDeleteThread,
  deletingThreadIds,
  variant = "rail",
}: {
  threads: Thread[];
  onThreadClick?: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  deletingThreadIds: Set<string>;
  variant?: ThreadHistoryVariant;
}) {
  const [threadId, setThreadId] = useQueryState("threadId");
  const cardList = variant === "inline" || variant === "overlay";

  if (!threads.length) {
    return (
      <div
        className={cn(
          "flex h-full w-full flex-col items-center justify-center gap-2 px-6 text-center text-sm text-gray-500",
          cardList && "min-h-[340px] rounded-xl border border-dashed bg-white",
        )}
      >
        <p className="font-medium text-gray-700">暂无对话历史</p>
        <p>发送一条消息后，系统会自动把聊天快照保存到本地归档。</p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "h-full w-full overflow-y-auto [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent",
        cardList
          ? "grid content-start gap-2"
          : "flex flex-col items-start justify-start gap-2",
      )}
    >
      {threads.map((t) => {
        let itemText = t.thread_id;
        if (
          typeof t.values === "object" &&
          t.values &&
          "messages" in t.values &&
          Array.isArray(t.values.messages) &&
          t.values.messages?.length > 0
        ) {
          const firstMessage = t.values.messages[0];
          itemText = getContentString(firstMessage.content);
        }
        const isArchive = isLocalArchiveThread(t);
        const isDeleting = deletingThreadIds.has(t.thread_id);
        return (
          <div
            key={t.thread_id}
            className={cn(
              "group flex w-full items-center gap-1",
              cardList
                ? "rounded-xl border border-slate-200 bg-white px-2 shadow-sm transition hover:border-slate-300 hover:bg-slate-50"
                : "px-1",
            )}
          >
            <Button
              variant="ghost"
              className={cn(
                "h-auto min-h-9 min-w-0 flex-1 items-start justify-start py-2 text-left font-normal",
                cardList && "min-h-14 hover:bg-transparent",
              )}
              onClick={(e) => {
                e.preventDefault();
                if (t.thread_id !== threadId) {
                  setThreadId(t.thread_id);
                }
                onThreadClick?.(t.thread_id);
              }}
            >
              <div className="flex min-w-0 flex-col items-start">
                <p
                  className={cn(
                    "max-w-full truncate text-ellipsis",
                    cardList && "text-sm font-medium text-slate-900",
                  )}
                >
                  {itemText}
                </p>
                {isArchive && (
                  <span className="text-xs text-gray-500">查看归档</span>
                )}
              </div>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8 shrink-0 text-gray-500 opacity-100 hover:bg-red-50 hover:text-red-600 lg:opacity-0 lg:group-hover:opacity-100"
              disabled={isDeleting}
              title={isArchive ? "删除这条归档" : "删除这条对话"}
              onClick={(event: MouseEvent<HTMLButtonElement>) => {
                event.preventDefault();
                event.stopPropagation();
                onDeleteThread(t.thread_id);
              }}
            >
              {isDeleting ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Trash2 className="size-4" />
              )}
            </Button>
          </div>
        );
      })}
    </div>
  );
}

function ThreadHistoryLoading({
  variant = "rail",
}: {
  variant?: ThreadHistoryVariant;
}) {
  const cardList = variant === "inline" || variant === "overlay";
  return (
    <div
      className={cn(
        "h-full w-full overflow-y-auto [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent",
        cardList
          ? "grid content-start gap-2"
          : "flex flex-col items-start justify-start gap-2",
      )}
    >
      {Array.from({ length: cardList ? 10 : 30 }).map((_, i) => (
        <Skeleton
          key={`skeleton-${i}`}
          className={cn("h-10", cardList ? "w-full rounded-xl" : "w-[280px]")}
        />
      ))}
    </div>
  );
}

export default function ThreadHistory({
  variant = "rail",
}: {
  variant?: ThreadHistoryVariant;
} = {}) {
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );

  const { getThreads, threads, setThreads, threadsLoading, setThreadsLoading } =
    useThreads();
  const { deleteThread, deleteAllThreads } = useThreads();
  const [threadId, setThreadId] = useQueryState("threadId");
  const [deletingThreadIds, setDeletingThreadIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [clearAllLoading, setClearAllLoading] = useState(false);
  const hasDeletableThreads = threads.length > 0;

  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;

    const loadThreads = async () => {
      setThreadsLoading(true);
      try {
        const localResponse = await fetch("/api/local-threads");
        if (localResponse.ok) {
          const localData = (await localResponse.json()) as {
            threads?: Thread[];
          };
          if (
            !cancelled &&
            Array.isArray(localData.threads) &&
            localData.threads.length
          ) {
            setThreads(localData.threads);
            setThreadsLoading(false);
          }
        }
      } catch {
        // Ignore local archive prefetch failures; the combined fetch below is authoritative.
      }

      try {
        const mergedThreads = await getThreads();
        if (!cancelled) {
          setThreads(mergedThreads);
        }
      } catch {
        if (!cancelled) {
          setThreads([]);
        }
      } finally {
        if (!cancelled) {
          setThreadsLoading(false);
        }
      }
    };

    void loadThreads();
    return () => {
      cancelled = true;
    };
  }, [getThreads, setThreads, setThreadsLoading]);

  const refreshThreads = () => {
    setThreadsLoading(true);
    getThreads()
      .then(setThreads)
      .catch(() => setThreads([]))
      .finally(() => setThreadsLoading(false));
  };

  const handleDeleteThread = async (targetThreadId: string) => {
    const targetThread = threads.find(
      (thread) => thread.thread_id === targetThreadId,
    );
    const confirmMessage = isLocalArchiveThread(targetThread)
      ? "确定删除这条本地归档吗？"
      : "确定删除这条对话历史吗？";
    if (!window.confirm(confirmMessage)) return;
    setDeletingThreadIds((prev) => new Set(prev).add(targetThreadId));
    try {
      await deleteThread(targetThreadId);
      if (targetThreadId === threadId) {
        setThreadId(null);
      }
      toast.success("对话已删除");
    } catch (error) {
      toast.error("删除失败", {
        description: error instanceof Error ? error.message : String(error),
      });
      refreshThreads();
    } finally {
      setDeletingThreadIds((prev) => {
        const next = new Set(prev);
        next.delete(targetThreadId);
        return next;
      });
    }
  };

  const handleClearAllThreads = async () => {
    if (!hasDeletableThreads) return;
    if (!window.confirm("确定清空所有对话历史吗？这个操作不能撤销。")) return;
    setClearAllLoading(true);
    try {
      await deleteAllThreads();
      setThreadId(null);
      toast.success("历史记录已清空");
    } catch (error) {
      toast.error("部分历史删除失败", {
        description: error instanceof Error ? error.message : String(error),
      });
      refreshThreads();
    } finally {
      setClearAllLoading(false);
    }
  };

  if (variant === "inline") {
    return (
      <section className="mx-auto flex h-full w-full max-w-5xl flex-col py-8">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-blue-700">聊天归档</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-normal text-slate-950">
              历史记录
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              这里显示本地保存的聊天内容；任务进度、报告和恢复入口在工作进度里。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              asChild
              variant="outline"
              className="h-9 rounded-lg border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 shadow-none hover:bg-slate-50"
            >
              <a href="/">开始工作</a>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-9 text-gray-500 hover:bg-red-50 hover:text-red-600"
              disabled={clearAllLoading || !hasDeletableThreads}
              title="清空全部对话"
              onClick={handleClearAllThreads}
            >
              {clearAllLoading ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Trash2 className="size-4" />
              )}
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 rounded-2xl border border-slate-200 bg-white/75 p-3 shadow-[0_20px_60px_rgba(15,23,42,0.06)]">
          {threadsLoading ? (
            <ThreadHistoryLoading variant="inline" />
          ) : (
            <ThreadList
              threads={threads}
              onThreadClick={() => setChatHistoryOpen(false)}
              onDeleteThread={handleDeleteThread}
              deletingThreadIds={deletingThreadIds}
              variant="inline"
            />
          )}
        </div>
      </section>
    );
  }

  if (variant === "overlay") {
    return (
      <section className="flex h-full min-h-0 w-full flex-col overflow-hidden">
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs font-medium text-blue-700">聊天归档</p>
            <h1 className="mt-1 text-xl font-semibold tracking-normal text-slate-950">
              历史记录
            </h1>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              选择一条历史记录查看，当前聊天会保留在后方。
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-8 text-gray-500 hover:bg-red-50 hover:text-red-600"
              disabled={clearAllLoading || !hasDeletableThreads}
              title="清空全部对话"
              onClick={handleClearAllThreads}
            >
              {clearAllLoading ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Trash2 className="size-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8 text-gray-500 hover:bg-slate-100"
              title="关闭历史记录"
              onClick={() => setChatHistoryOpen(false)}
            >
              <XIcon className="size-4" />
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 p-3">
          {threadsLoading ? (
            <ThreadHistoryLoading variant="overlay" />
          ) : (
            <ThreadList
              threads={threads}
              onThreadClick={() => setChatHistoryOpen(false)}
              onDeleteThread={handleDeleteThread}
              deletingThreadIds={deletingThreadIds}
              variant="overlay"
            />
          )}
        </div>
      </section>
    );
  }

  return (
    <>
      <div className="shadow-inner-right hidden h-screen w-[300px] shrink-0 flex-col items-start justify-start gap-6 border-r-[1px] border-slate-300 lg:flex">
        <div className="flex w-full items-center justify-between gap-2 px-4 pt-1.5">
          <Button
            className="hover:bg-gray-100"
            variant="ghost"
            onClick={() => setChatHistoryOpen((p) => !p)}
          >
            {chatHistoryOpen ? (
              <PanelRightOpen className="size-5" />
            ) : (
              <PanelRightClose className="size-5" />
            )}
          </Button>
          <h1 className="text-xl font-semibold tracking-tight">对话历史</h1>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 text-gray-500 hover:bg-red-50 hover:text-red-600"
            disabled={clearAllLoading || !hasDeletableThreads}
            title="清空全部对话"
            onClick={handleClearAllThreads}
          >
            {clearAllLoading ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <Trash2 className="size-4" />
            )}
          </Button>
        </div>
        {threadsLoading ? (
          <ThreadHistoryLoading />
        ) : (
          <ThreadList
            threads={threads}
            onDeleteThread={handleDeleteThread}
            deletingThreadIds={deletingThreadIds}
          />
        )}
      </div>
      <div className="lg:hidden">
        <Sheet
          open={!!chatHistoryOpen && !isLargeScreen}
          onOpenChange={(open) => {
            if (isLargeScreen) return;
            setChatHistoryOpen(open);
          }}
        >
          <SheetContent
            side="left"
            className="flex lg:hidden"
          >
            <SheetHeader>
              <div className="flex items-center justify-between gap-2">
                <div>
                  <SheetTitle>对话历史</SheetTitle>
                  <SheetDescription className="sr-only">
                    查看、打开或删除本地保存的对话记录。
                  </SheetDescription>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 text-gray-500 hover:bg-red-50 hover:text-red-600"
                  disabled={clearAllLoading || !hasDeletableThreads}
                  title="清空全部对话"
                  onClick={handleClearAllThreads}
                >
                  {clearAllLoading ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Trash2 className="size-4" />
                  )}
                </Button>
              </div>
            </SheetHeader>
            <ThreadList
              threads={threads}
              onThreadClick={() => setChatHistoryOpen(false)}
              onDeleteThread={handleDeleteThread}
              deletingThreadIds={deletingThreadIds}
            />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
