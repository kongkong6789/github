import assert from "node:assert/strict";
import { test } from "node:test";

import { managementLinks, taskTemplates } from "./home-actions";

test("home action links keep tasks, logs, data health, and permissions visible on the empty composer", () => {
  assert.deepEqual(
    managementLinks.map((link) => [link.label, link.href]),
    [
      ["工作进度", "/tasks"],
      ["问题排查", "/logs"],
      ["资料体检", "/data-health"],
      ["工具权限", "/governance?tab=skills"],
    ],
  );
});

test("home task templates keep the core business prompts available", () => {
  const labels = taskTemplates.map((template) => template.label);

  assert.deepEqual(
    ["整理资料", "清洗表格", "库存风险", "经营分析", "同步知识库"].every(
      (label) => labels.includes(label),
    ),
    true,
  );
});

test("home task templates include the P5 ecommerce prompts from TODO", () => {
  const templatesByLabel = new Map(
    taskTemplates.map((template) => [template.label, template]),
  );

  for (const label of [
    "广告诊断",
    "商品内容优化",
    "供应商风险",
    "财务分析",
    "老板报告",
  ]) {
    const template = templatesByLabel.get(label);

    assert.ok(template, `${label} template should be available`);
    assert.match(template.prompt, /国内多平台|天猫|京东|抖音|拼多多|小红书/);
    assert.match(template.prompt, /DuckDB/);
    assert.match(template.prompt, /wiki|LightRAG/);
    assert.match(template.prompt, /人工确认|确认口径/);
    assert.doesNotMatch(template.prompt, /MOQ|最小起订量/);
  }
});
