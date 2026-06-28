import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";

const governancePagePath = path.resolve(
  process.cwd(),
  "src",
  "app",
  "governance",
  "page.tsx",
);

test("governance page uses clear user-facing labels instead of registry jargon", async () => {
  const source = await readFile(governancePagePath, "utf8");

  assert.doesNotMatch(source, /工具注册表|技能注册表/);
  assert.doesNotMatch(source, />注册表</);
  assert.match(source, /工具清单/);
  assert.match(source, /已配置技能/);
  assert.match(source, /配置状态/);
});
