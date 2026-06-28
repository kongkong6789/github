import assert from "node:assert/strict";
import { test } from "node:test";

import { isActiveWorkbenchPath, workbenchNavItems } from "./workbench-nav";

test("workbench navigation merges governance and skills into one clear entry", () => {
  assert.deepEqual(
    workbenchNavItems
      .filter((item) => item.href.startsWith("/governance"))
      .map((item) => [item.label, item.href]),
    [
      ["工具权限", "/governance?tab=skills"],
      ["系统连接", "/governance?tab=mcp"],
    ],
  );
});

test("workbench navigation exposes conversation history in the sidebar", () => {
  assert.deepEqual(
    workbenchNavItems
      .slice(0, 2)
      .map((item) => [item.label, item.href, item.description]),
    [
      ["开始工作", "/", "直接告诉我想做什么"],
      [
        "历史记录",
        "/?chatHistoryOpen=true",
        "找回以前聊过的内容和结果",
      ],
    ],
  );
});

test("workbench navigation exposes the platform lab between evidence and governance", () => {
  assert.deepEqual(
    workbenchNavItems
      .filter((item) =>
        ["/evidence-graph", "/platform-lab", "/governance?tab=skills"].includes(
          item.href,
        ),
      )
      .map((item) => [item.label, item.href, item.description]),
    [
      ["依据来源", "/evidence-graph", "每个结论从哪里来"],
      ["经营推演", "/platform-lab", "做假设、看方案、演练决策"],
      ["工具权限", "/governance?tab=skills", "管哪些工具能用、哪些要审批"],
    ],
  );
});

test("root query-backed history link is active only when history is open", () => {
  assert.equal(
    isActiveWorkbenchPath(
      "/",
      "/?chatHistoryOpen=true",
      "chatHistoryOpen=true",
    ),
    true,
  );
  assert.equal(isActiveWorkbenchPath("/", "/", "chatHistoryOpen=true"), false);
  assert.equal(isActiveWorkbenchPath("/", "/", ""), true);
  assert.equal(isActiveWorkbenchPath("/", "/?chatHistoryOpen=true", ""), false);
});

test("query-backed governance links only become active for their tab", () => {
  assert.equal(
    isActiveWorkbenchPath(
      "/governance",
      "/governance?tab=skills",
      "tab=skills",
    ),
    true,
  );
  assert.equal(
    isActiveWorkbenchPath("/governance", "/governance?tab=skills", ""),
    true,
  );
  assert.equal(
    isActiveWorkbenchPath("/governance", "/governance?tab=mcp", "tab=skills"),
    false,
  );
  assert.equal(
    isActiveWorkbenchPath("/governance", "/governance?tab=skills", "tab=mcp"),
    false,
  );
});
