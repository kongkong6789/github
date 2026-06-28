import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { loadLogsState, redactSensitiveText } from "./logs";

test("logs state tails recent lines, normalizes audit fields, and redacts secrets", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-logs-"));
  const dataDir = path.join(root, "data");
  await mkdir(path.join(dataDir, "audit"), { recursive: true });

  const backendLines = Array.from({ length: 205 }, (_, index) =>
    `2026-05-20T10:${String(index % 60).padStart(2, "0")}:00Z INFO backend line ${index} token=secret-${index}`,
  ).join("\n");
  await writeFile(path.join(root, "langgraph-server.log"), backendLines, "utf8");
  await writeFile(
    path.join(root, "frontend.err.log"),
    "2026-05-20T11:00:00Z ERROR frontend password=front-secret\n",
    "utf8",
  );
  await writeFile(
    path.join(dataDir, "audit", "events.jsonl"),
    [
      JSON.stringify({
        timestamp: "2026-05-20T12:00:00.000Z",
        level: "warn",
        event_type: "mcp_tool_called",
        actor: "agent",
        agent_id: "data_agent",
        thread_id: "thread-1",
        task_id: "task-1",
        tool_name: "query_fact_layer",
        risk_level: "medium",
        metadata: { api_key: "sk-audit-secret-value" },
      }),
      "{not json",
    ].join("\n"),
    "utf8",
  );

  const state = await loadLogsState({
    workspaceDir: root,
    dataDir,
    limit: 200,
  });

  assert.equal(state.entries.length, 200);
  assert(state.sources.some((source) => source.source === "audit"));
  const serialized = JSON.stringify(state);
  assert(!serialized.includes("secret-204"));
  assert(!serialized.includes("front-secret"));
  assert(!serialized.includes("sk-audit-secret-value"));
  assert(serialized.includes("***REDACTED***"));

  const filtered = await loadLogsState({
    workspaceDir: root,
    dataDir,
    limit: 200,
    filters: {
      source: "audit",
      level: "warn",
      thread_id: "thread-1",
      task_id: "task-1",
      agent_id: "data_agent",
      tool_name: "query_fact_layer",
      risk_level: "medium",
    },
  });
  assert.equal(filtered.entries.length, 1);
  assert.equal(filtered.entries[0].source, "audit");
  assert.equal(filtered.entries[0].level, "warn");
  assert.equal(filtered.entries[0].tool_name, "query_fact_layer");
});

test("redactSensitiveText masks common key token secret and password shapes", () => {
  const redacted = redactSensitiveText(
    "OPENAI_API_KEY=sk-abc1234567890 token: raw-token password=abc secret=xyz",
  );

  assert(!redacted.includes("sk-abc1234567890"));
  assert(!redacted.includes("raw-token"));
  assert(!redacted.includes("password=abc"));
  assert(!redacted.includes("secret=xyz"));
  assert.match(redacted, /\*\*\*REDACTED\*\*\*/);
});

test("logs state sanitizes absolute filesystem paths to relative or basename", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-logs-paths-"));
  const dataDir = path.join(root, "data");
  await mkdir(path.join(dataDir, "audit"), { recursive: true });

  await writeFile(
    path.join(root, "langgraph-server.log"),
    "2026-05-20T10:00:00Z INFO test line\n",
    "utf8",
  );

  const state = await loadLogsState({
    workspaceDir: root,
    dataDir,
    limit: 10,
  });

  const serialized = JSON.stringify(state);
  assert(!serialized.includes(root), `response should not contain workspace root path: ${root}`);

  const langgraphSource = state.sources.find((s) => s.source === "langgraph");
  assert(langgraphSource);
  assert(!path.isAbsolute(langgraphSource.path), `source path should not be absolute: ${langgraphSource.path}`);

  if (state.entries.length > 0) {
    assert(!path.isAbsolute(state.entries[0].file_path), `entry file_path should not be absolute: ${state.entries[0].file_path}`);
  }
});
