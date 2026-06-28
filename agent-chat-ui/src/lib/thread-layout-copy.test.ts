import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";

const threadPagePath = path.resolve(
  process.cwd(),
  "src",
  "components",
  "thread",
  "index.tsx",
);
const threadHistoryPath = path.resolve(
  process.cwd(),
  "src",
  "components",
  "thread",
  "history",
  "index.tsx",
);

test("conversation history never reserves a permanent second left rail", async () => {
  const source = await readFile(threadPagePath, "utf8");

  assert.doesNotMatch(
    source,
    /fixed inset-y-0 left-0[\s\S]{0,700}<ThreadHistory \/>/,
  );
  assert.doesNotMatch(
    source,
    /marginLeft:\s*chatHistoryOpen && isLargeScreen \? 300 : 0/,
  );
  assert.doesNotMatch(
    source,
    /marginLeft:\s*chatHistoryOpen \? \(isLargeScreen \? 300 : 0\) : 0/,
  );
  assert.doesNotMatch(source, /<ThreadHistory \/>/);
  assert.match(source, /<ThreadHistory variant="inline" \/>/);
  assert.match(source, /<ThreadHistory variant="overlay" \/>/);
});

test("inline conversation history closes history mode when opening a thread", async () => {
  const source = await readFile(threadHistoryPath, "utf8");

  assert.match(
    source,
    /variant="inline"[\s\S]{0,260}onThreadClick=\{\(\) => setChatHistoryOpen\(false\)\}/,
  );
});

test("active conversation composer stays compact for reading history", async () => {
  const source = await readFile(threadPagePath, "utf8");
  const activeConversation = source.slice(
    source.indexOf('return (\n    <div className="flex h-screen'),
  );

  assert.doesNotMatch(activeConversation, /managementLinks\.map/);
  assert.doesNotMatch(activeConversation, /taskTemplates\.map/);
  assert.match(activeConversation, /chatStarted \? "pb-44" : "pb-16"/);
});

test("home screen removes reference-only labels and fits the first viewport", async () => {
  const source = await readFile(threadPagePath, "utf8");
  const emptyHome = source.slice(
    source.indexOf("if (!chatStarted) {"),
    source.indexOf('return (\n    <div className="flex h-screen'),
  );

  assert.doesNotMatch(emptyHome, /Lee 老板/);
  assert.doesNotMatch(emptyHome, /输入经营目标后，任务会进入可追踪流程/);
  assert.doesNotMatch(emptyHome, /整理 raw 资料/);
  assert.doesNotMatch(emptyHome, /生成风险清单/);
  assert.doesNotMatch(emptyHome, /建议动作/);
  assert.doesNotMatch(emptyHome, /a2a-assistant-float/);
  assert.doesNotMatch(emptyHome, /min-h-\[52dvh\]/);
  assert.doesNotMatch(emptyHome, /sm:min-h-\[58dvh\]/);
  assert.match(emptyHome, /h-\[100dvh\] overflow-hidden/);
  assert.doesNotMatch(
    emptyHome,
    /<aside className="absolute top-4 right-0 hidden/,
  );
});
