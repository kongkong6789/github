import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { summarizeConfigHealth } from "./config-health";

test("config health surfaces Agent-Reach as an optional internet research capability", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-config-health-"));
  const dataDir = path.join(root, "data");
  await mkdir(path.join(dataDir, "warehouse"), { recursive: true });
  await mkdir(path.join(dataDir, "mcp"), { recursive: true });
  await mkdir(path.join(dataDir, "skill_registry"), { recursive: true });
  await writeFile(
    path.join(dataDir, "warehouse", "connector_registry.json"),
    JSON.stringify({ connectors: {} }),
    "utf8",
  );
  await writeFile(
    path.join(dataDir, "mcp", "tool_policy.json"),
    JSON.stringify({ tools: {} }),
    "utf8",
  );
  await writeFile(
    path.join(dataDir, "skill_registry", "registry.json"),
    JSON.stringify({ skills: {} }),
    "utf8",
  );

  const health = await summarizeConfigHealth({
    workspaceDir: root,
    dataDir,
    env: {
      OPENAI_API_KEY: "sk-test",
      OPENAI_MODEL: "test-model",
      OPENAI_BASE_URL: "https://example.test/v1",
      A2A_AGENT_REACH_BIN: "missing-agent-reach-cli",
    } as unknown as NodeJS.ProcessEnv,
  });

  const agentReach = health.items.find((item) => item.id === "agent_reach");
  assert.equal(agentReach?.label, "Agent-Reach");
  assert.equal(agentReach?.status, "warn");
  assert.match(agentReach?.summary ?? "", /未安装|不可用|未找到|missing/i);
});
