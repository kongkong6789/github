import assert from "node:assert/strict";
import { test } from "node:test";
import type { Message, Thread } from "@langchain/langgraph-sdk";

import {
  buildLocalBrowserArchiveThreadId,
  getRunnableThreadId,
  getOriginalThreadIdFromArchiveId,
  getRenderableChatMessages,
  getSubmitMessagesForThread,
  getThreadValuesWithMessages,
  isRenderableChatMessage,
  isLocalArchiveThread,
  isLocalArchiveThreadId,
  mergeThreadLists,
  resolveStreamThreadIdState,
  shouldHydrateLocalArchiveMessages,
  shouldUseLocalArchiveDisplayValues,
} from "./local-archive-thread";

const archivedMessages = [
  {
    id: "local-task-demo-human",
    type: "human",
    content: [{ type: "text", text: "整理上周资料" }],
  },
  {
    id: "local-task-demo-ai",
    type: "ai",
    content: "归档摘要",
    tool_calls: [],
    invalid_tool_calls: [],
  },
] satisfies Message[];

const newHumanMessage = {
  id: "new-question",
  type: "human",
  content: [{ type: "text", text: "继续分析风险" }],
} satisfies Message;

test("local archive thread IDs are view-only and never sent to LangGraph runs", () => {
  assert.equal(isLocalArchiveThreadId("local-task-demo"), true);
  assert.equal(isLocalArchiveThreadId("local-archive-demo"), true);
  assert.equal(isLocalArchiveThreadId("local-task-%E6%B5%8B%E8%AF%95"), true);
  assert.equal(
    isLocalArchiveThreadId("3f75ef86-5ff9-4d36-85c7-0f4c3c05a30e"),
    false,
  );

  assert.equal(getRunnableThreadId("local-task-demo"), null);
  assert.equal(
    getRunnableThreadId("3f75ef86-5ff9-4d36-85c7-0f4c3c05a30e"),
    "3f75ef86-5ff9-4d36-85c7-0f4c3c05a30e",
  );
});

test("browser archive thread IDs preserve the original runnable thread ID", () => {
  const original = "019dfc7b-838c-7933-83f3-2e41368b442d";
  const archiveId = buildLocalBrowserArchiveThreadId(original);
  assert.equal(archiveId, `local-archive-${encodeURIComponent(original)}`);
  assert.equal(getOriginalThreadIdFromArchiveId(archiveId), original);
  assert.equal(getOriginalThreadIdFromArchiveId("real-thread"), null);
});

test("local archive threads are detected from metadata or generated ID prefix", () => {
  const archiveByMetadata = {
    thread_id: "archived-from-file",
    metadata: { source: "local_task_archive" },
  } as Thread;
  const archiveById = { thread_id: "local-task-demo", metadata: {} } as Thread;
  const realThread = {
    thread_id: "3f75ef86-5ff9-4d36-85c7-0f4c3c05a30e",
    metadata: {},
  } as Thread;

  assert.equal(isLocalArchiveThread(archiveByMetadata), true);
  assert.equal(isLocalArchiveThread(archiveById), true);
  assert.equal(isLocalArchiveThread(realThread), false);
});

test("thread values are usable as archive display state only when messages exist", () => {
  assert.deepEqual(
    getThreadValuesWithMessages({ messages: archivedMessages }),
    {
      messages: archivedMessages,
    },
  );
  assert.equal(
    getThreadValuesWithMessages({ messages: "not-an-array" }),
    undefined,
  );
  assert.equal(getThreadValuesWithMessages(null), undefined);
});

test("internal system messages are never rendered in chat history", () => {
  const messages = [
    {
      id: "internal-skill",
      type: "system",
      content: "Active Skill matched for this user request.",
    },
    {
      id: "human-question",
      type: "human",
      content: [{ type: "text", text: "使用吉客云查询库存" }],
    },
    {
      id: "assistant-answer",
      type: "ai",
      content: "查询结果",
      tool_calls: [],
      invalid_tool_calls: [],
    },
  ] satisfies Message[];

  assert.equal(isRenderableChatMessage(messages[0]), false);
  assert.deepEqual(
    getRenderableChatMessages(messages).map((message) => message.id),
    ["human-question", "assistant-answer"],
  );
});

test("duplicate supervisor final reports collapse to the latest final answer", () => {
  const repeatedReport = [
    "## UNOVE 吉客云全仓库实时库存分析报告",
    "| 指标 | 数值 |",
    "|---|---|",
    "| 总库存 | 1,015,415 件 |",
    "| 可用库存 | 974,255 件 |",
    "### 仓库口径",
    "大贸=麦歌仓，跨境=韩国申通仓，保税=菜鸟仓，售后=宝鼎仓。",
    "### 数据缺口",
    "brandName 为空，costPrice 缺失，批次效期未批量提取。",
    "以上内容用于模拟子团队和顶层主管在多 Agent handoff 后输出的同一份长报告。",
  ]
    .join("\n")
    .repeat(8);
  const messages = [
    {
      id: "human-question",
      type: "human",
      content: [{ type: "text", text: "使用吉客云查询库存" }],
    },
    {
      id: "data-pipeline-final",
      type: "ai",
      name: "data_pipeline_supervisor",
      content: `现在作为 data_pipeline_supervisor，我已收到 data_agent 的完整数据。让我将结果整合并最终呈现给用户。\n\n${repeatedReport}`,
      tool_calls: [],
      invalid_tool_calls: [],
    },
    {
      id: "top-final",
      type: "ai",
      name: "top_company_brain_supervisor",
      content: repeatedReport,
      tool_calls: [],
      invalid_tool_calls: [],
    },
  ] satisfies Message[];

  assert.deepEqual(
    getRenderableChatMessages(messages).map((message) => message.id),
    ["human-question", "top-final"],
  );
});

test("distinct supervisor reports remain visible", () => {
  const messages = [
    {
      id: "data-pipeline-final",
      type: "ai",
      name: "data_pipeline_supervisor",
      content: "数据管道完成：已读取实时库存。",
      tool_calls: [],
      invalid_tool_calls: [],
    },
    {
      id: "top-final",
      type: "ai",
      name: "top_company_brain_supervisor",
      content: "最终建议：需要补充销量后计算周转。",
      tool_calls: [],
      invalid_tool_calls: [],
    },
  ] satisfies Message[];

  assert.deepEqual(
    getRenderableChatMessages(messages).map((message) => message.id),
    ["data-pipeline-final", "top-final"],
  );
});

test("local archives that only captured an in-flight run are eligible for remote hydration", () => {
  const onlyHuman = [
    {
      id: "human-question",
      type: "human",
      content: [{ type: "text", text: "使用吉客云查询库存" }],
    },
  ] satisfies Message[];

  const finished = [
    ...onlyHuman,
    {
      id: "assistant-answer",
      type: "ai",
      content: "查询结果",
      tool_calls: [],
      invalid_tool_calls: [],
    },
  ] satisfies Message[];

  const waitingForTool = [
    ...onlyHuman,
    {
      id: "assistant-tool-call",
      type: "ai",
      content: "",
      tool_calls: [{ id: "call-1", name: "query_erp_live_snapshot", args: {} }],
      invalid_tool_calls: [],
    },
  ] satisfies Message[];

  assert.equal(shouldHydrateLocalArchiveMessages(onlyHuman), true);
  assert.equal(shouldHydrateLocalArchiveMessages(waitingForTool), true);
  assert.equal(shouldHydrateLocalArchiveMessages(finished), false);
});

test("submitting from an archive carries archive messages into the new real thread", () => {
  const messages = getSubmitMessagesForThread({
    currentMessages: archivedMessages,
    newHumanMessage,
    isViewingLocalArchive: true,
  });

  assert.deepEqual(
    messages.map((message) => message.id),
    ["local-task-demo-human", "local-task-demo-ai", "new-question"],
  );
});

test("submitting from a real thread keeps the checkpoint-based payload small", () => {
  const messages = getSubmitMessagesForThread({
    currentMessages: archivedMessages,
    newHumanMessage,
    isViewingLocalArchive: false,
  });

  assert.deepEqual(
    messages.map((message) => message.id),
    ["new-question"],
  );
});

test("submitting from a real thread does not send orphaned synthetic tool responses", () => {
  const messages = getSubmitMessagesForThread({
    currentMessages: [
      {
        id: "human-before-tool",
        type: "human",
        content: [{ type: "text", text: "查一下库存" }],
      },
      {
        id: "ai-with-tool-call",
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "call-stock",
            name: "check_inventory",
            args: {},
          },
        ],
        invalid_tool_calls: [],
      },
    ] satisfies Message[],
    newHumanMessage,
    isViewingLocalArchive: false,
  });

  assert.deepEqual(
    messages.map((message) => message.id),
    ["new-question"],
  );
});

test("submitting from an archive repairs missing tool responses next to their AI call", () => {
  const messages = getSubmitMessagesForThread({
    currentMessages: [
      {
        id: "human-before-tool",
        type: "human",
        content: [{ type: "text", text: "查一下库存" }],
      },
      {
        id: "ai-with-tool-call",
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "call-stock",
            name: "check_inventory",
            args: {},
          },
        ],
        invalid_tool_calls: [],
      },
      {
        id: "ai-after-tool-call",
        type: "ai",
        content: "继续分析",
        tool_calls: [],
        invalid_tool_calls: [],
      },
    ] satisfies Message[],
    newHumanMessage,
    isViewingLocalArchive: true,
  });

  assert.deepEqual(
    messages.map((message) => message.type),
    ["human", "ai", "tool", "ai", "human"],
  );
  assert.equal(messages[2].type, "tool");
  assert.equal(messages[2].tool_call_id, "call-stock");
});

test("remote threads and local archive threads are merged into one consistent list", () => {
  const merged = mergeThreadLists(
    [
      {
        thread_id: "real-thread",
        updated_at: "2026-05-06T16:55:00.000Z",
        created_at: "2026-05-06T16:54:00.000Z",
        metadata: {},
      } as Thread,
    ],
    [
      {
        thread_id: "local-task-demo",
        updated_at: "2026-05-06T16:54:30.000Z",
        created_at: "2026-05-06T16:53:30.000Z",
        metadata: { source: "local_task_archive" },
      } as Thread,
    ],
  );

  assert.deepEqual(
    merged.map((thread) => thread.thread_id),
    ["real-thread", "local-task-demo"],
  );
});

test("remote threads replace local browser archives that refer to the same original thread", () => {
  const remoteThread = {
    thread_id: "019dfc7b-838c-7933-83f3-2e41368b442d",
    created_at: "2026-05-06T16:54:30.000Z",
    updated_at: "2026-05-06T16:55:00.000Z",
    metadata: {},
    status: "idle",
    values: { messages: [] },
    interrupts: {},
  } as Thread;
  const archivedThread = {
    thread_id: buildLocalBrowserArchiveThreadId(
      "019dfc7b-838c-7933-83f3-2e41368b442d",
    ),
    created_at: "2026-05-06T16:53:30.000Z",
    updated_at: "2026-05-06T16:54:00.000Z",
    metadata: {
      source: "local_thread_archive",
      original_thread_id: "019dfc7b-838c-7933-83f3-2e41368b442d",
    },
    status: "idle",
    values: { messages: [] },
    interrupts: {},
  } as Thread;

  const merged = mergeThreadLists([remoteThread], [archivedThread]);
  assert.equal(merged.length, 1);
  assert.equal(merged[0].thread_id, remoteThread.thread_id);
});

test("stream thread ID adoption is deferred while a newly created thread is still streaming", () => {
  const stateWhileStreaming = resolveStreamThreadIdState({
    urlThreadId: "019dfc7b-838c-7933-83f3-2e41368b442d",
    currentStreamThreadId: null,
    pendingCreatedThreadId: "019dfc7b-838c-7933-83f3-2e41368b442d",
    isLoading: true,
  });

  assert.deepEqual(stateWhileStreaming, {
    nextStreamThreadId: null,
    nextPendingCreatedThreadId: "019dfc7b-838c-7933-83f3-2e41368b442d",
  });

  const stateAfterStreaming = resolveStreamThreadIdState({
    urlThreadId: "019dfc7b-838c-7933-83f3-2e41368b442d",
    currentStreamThreadId: null,
    pendingCreatedThreadId: "019dfc7b-838c-7933-83f3-2e41368b442d",
    isLoading: false,
  });

  assert.deepEqual(stateAfterStreaming, {
    nextStreamThreadId: "019dfc7b-838c-7933-83f3-2e41368b442d",
    nextPendingCreatedThreadId: null,
  });
});

test("archive display values do not hide a new run started from an archive", () => {
  assert.equal(
    shouldUseLocalArchiveDisplayValues({
      isViewingLocalArchive: true,
      hasThreadSearchValues: true,
      isLoading: false,
      pendingCreatedThreadId: null,
    }),
    true,
  );

  assert.equal(
    shouldUseLocalArchiveDisplayValues({
      isViewingLocalArchive: true,
      hasThreadSearchValues: true,
      isLoading: true,
      pendingCreatedThreadId: "019dfc7b-838c-7933-83f3-2e41368b442d",
    }),
    false,
  );

  assert.equal(
    shouldUseLocalArchiveDisplayValues({
      isViewingLocalArchive: true,
      hasThreadSearchValues: true,
      isLoading: false,
      pendingCreatedThreadId: "019dfc7b-838c-7933-83f3-2e41368b442d",
    }),
    false,
  );
});
