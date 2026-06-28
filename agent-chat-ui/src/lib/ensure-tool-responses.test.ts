import assert from "node:assert/strict";
import { test } from "node:test";
import type { Message } from "@langchain/langgraph-sdk";

import { repairMissingToolResponsesInMessageOrder } from "./ensure-tool-responses";

test("tool response repair keeps exact tool call matches and drops duplicates", () => {
  const repaired = repairMissingToolResponsesInMessageOrder([
    {
      id: "ai1",
      type: "ai",
      content: "",
      tool_calls: [
        { id: "call-a", name: "a", args: {} },
        { id: "call-b", name: "b", args: {} },
      ],
      invalid_tool_calls: [],
    },
    {
      id: "tool-b",
      type: "tool",
      tool_call_id: "call-b",
      content: "b",
    },
    {
      id: "tool-b-duplicate",
      type: "tool",
      tool_call_id: "call-b",
      content: "duplicate",
    },
    {
      id: "tool-wrong",
      type: "tool",
      tool_call_id: "call-x",
      content: "wrong",
    },
  ] as Message[]);

  assert.deepEqual(
    repaired.map((message) => message.type),
    ["ai", "tool", "tool"],
  );
  assert.deepEqual(
    repaired.map((message) => message.type === "tool" && message.tool_call_id),
    [false, "call-a", "call-b"],
  );
});

test("tool response repair removes orphan tool messages before archive replay", () => {
  const repaired = repairMissingToolResponsesInMessageOrder([
    {
      id: "orphan",
      type: "tool",
      tool_call_id: "old-call",
      content: "orphan",
    },
    {
      id: "human",
      type: "human",
      content: "hello",
    },
  ] as Message[]);

  assert.deepEqual(
    repaired.map((message) => message.id),
    ["human"],
  );
});
