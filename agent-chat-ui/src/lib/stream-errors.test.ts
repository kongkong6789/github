import assert from "node:assert/strict";
import { test } from "node:test";

import {
  shouldSuppressStreamConsoleError,
  toFriendlyStreamError,
} from "./stream-errors";

test("tool role protocol errors are shown as recoverable chat history issues", () => {
  const error = new Error(
    "Messages with role 'tool' must be a response to a preceding message with 'tool_calls'",
  );

  const friendly = toFriendlyStreamError(error);

  assert.equal(friendly.title, "对话历史异常，系统已自动保护");
  assert.match(friendly.description, /旧对话/);
  assert.equal(shouldSuppressStreamConsoleError(error), true);
});

test("bad request stream errors are suppressed from the Next.js dev overlay", () => {
  const error = new Error("An internal error occurred");
  error.name = "BadRequestError";

  const friendly = toFriendlyStreamError(error);

  assert.equal(friendly.title, "后端执行中断");
  assert.equal(shouldSuppressStreamConsoleError(error), true);
});

test("model bad request errors still explain provider rejection", () => {
  const error = new Error("Bad request: invalid model payload");
  error.name = "BadRequestError";

  const friendly = toFriendlyStreamError(error);

  assert.equal(friendly.title, "请求被模型服务拒绝");
  assert.equal(shouldSuppressStreamConsoleError(error), true);
});

test("network stream errors are translated to backend connection guidance", () => {
  const friendly = toFriendlyStreamError("network error");

  assert.equal(friendly.title, "连接后端失败");
  assert.match(friendly.description, /LangGraph/);
  assert.equal(shouldSuppressStreamConsoleError("network error"), true);
});

test("failed fetch TypeErrors are suppressed from the Next.js dev overlay", () => {
  const error = new TypeError("Failed to fetch");

  const friendly = toFriendlyStreamError(error);

  assert.equal(friendly.title, "连接后端失败");
  assert.equal(shouldSuppressStreamConsoleError(error), true);
});
