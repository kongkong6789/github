import { v4 as uuidv4 } from "uuid";
import { Message, ToolMessage } from "@langchain/langgraph-sdk";

export const DO_NOT_RENDER_ID_PREFIX = "do-not-render-";

export function ensureToolCallsHaveResponses(messages: Message[]): Message[] {
  const newMessages: ToolMessage[] = [];

  messages.forEach((message, index) => {
    if (message.type !== "ai" || message.tool_calls?.length === 0) {
      // If it's not an AI message, or it doesn't have tool calls, we can ignore.
      return;
    }
    const expectedIds = new Set(
      (message.tool_calls ?? []).map((tc) => tc.id ?? "").filter(Boolean),
    );
    const existingIds = new Set<string>();
    let lookaheadIndex = index + 1;
    while (messages[lookaheadIndex]?.type === "tool") {
      const toolMessage = messages[lookaheadIndex] as ToolMessage;
      if (expectedIds.has(toolMessage.tool_call_id)) {
        existingIds.add(toolMessage.tool_call_id);
      }
      lookaheadIndex += 1;
    }

    newMessages.push(
      ...((message.tool_calls ?? [])
        .filter((tc) => !existingIds.has(tc.id ?? ""))
        .map((tc) => buildSyntheticToolMessage(tc))),
    );
  });

  return newMessages;
}

function buildSyntheticToolMessage(toolCall: {
  id?: string;
  name?: string;
}): ToolMessage {
  return {
    type: "tool" as const,
    tool_call_id: toolCall.id ?? "",
    id: `${DO_NOT_RENDER_ID_PREFIX}${uuidv4()}`,
    name: toolCall.name,
    content: "Successfully handled tool call.",
  };
}

export function repairMissingToolResponsesInMessageOrder(
  messages: Message[],
): Message[] {
  const repairedMessages: Message[] = [];

  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index];
    if (message.type === "tool") {
      continue;
    }
    repairedMessages.push(message);

    if (message.type !== "ai" || message.tool_calls?.length === 0) {
      continue;
    }

    const expectedIds = new Set(
      (message.tool_calls ?? []).map((toolCall) => toolCall.id ?? ""),
    );
    const existingToolResponses = new Map<string, ToolMessage>();
    let lookaheadIndex = index + 1;
    while (messages[lookaheadIndex]?.type === "tool") {
      const toolMessage = messages[lookaheadIndex] as ToolMessage;
      if (
        expectedIds.has(toolMessage.tool_call_id) &&
        !existingToolResponses.has(toolMessage.tool_call_id)
      ) {
        existingToolResponses.set(toolMessage.tool_call_id, toolMessage);
      }
      lookaheadIndex += 1;
    }

    for (const toolCall of message.tool_calls ?? []) {
      const toolCallId = toolCall.id ?? "";
      repairedMessages.push(
        existingToolResponses.get(toolCallId) ??
          buildSyntheticToolMessage(toolCall),
      );
    }
    index = lookaheadIndex - 1;
  }

  return repairedMessages;
}
