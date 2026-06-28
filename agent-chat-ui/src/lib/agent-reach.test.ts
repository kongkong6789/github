import assert from "node:assert/strict";
import { test } from "node:test";

import {
  checkAgentReachStatus,
  summarizeAgentReachDoctor,
} from "./agent-reach";

test("Agent-Reach doctor summary keeps public channels separate from login channels", () => {
  const summary = summarizeAgentReachDoctor({
    web: {
      status: "ok",
      name: "任意网页",
      message: "Jina Reader 可用",
      tier: 0,
      backends: ["Jina Reader"],
      active_backend: "Jina Reader",
    },
    rss: {
      status: "ok",
      name: "RSS/Atom 订阅源",
      message: "feedparser 可用",
      tier: 0,
      backends: ["feedparser"],
      active_backend: "feedparser",
    },
    xiaohongshu: {
      status: "warn",
      name: "小红书笔记",
      message: "需要登录态",
      tier: 1,
      backends: ["OpenCLI"],
    },
    twitter: {
      status: "off",
      name: "Twitter/X 推文",
      message: "未配置",
      tier: 1,
      backends: ["twitter-cli", "OpenCLI"],
    },
  });

  assert.equal(summary.status, "warn");
  assert.equal(summary.channel_count, 4);
  assert.equal(summary.available_count, 2);
  assert.equal(summary.public_ready_count, 2);
  assert.equal(summary.login_required_count, 2);
  assert.deepEqual(
    summary.channels.map((channel) => channel.id),
    ["web", "rss", "twitter", "xiaohongshu"],
  );
});

test("Agent-Reach status reports unavailable CLI without throwing", async () => {
  const status = await checkAgentReachStatus({
    commandCandidates: ["missing-agent-reach"],
    runner: async () => {
      const error = new Error("spawn missing-agent-reach ENOENT") as NodeJS.ErrnoException;
      error.code = "ENOENT";
      throw error;
    },
  });

  assert.equal(status.available, false);
  assert.equal(status.status, "unavailable");
  assert.equal(status.command, "missing-agent-reach");
  assert.match(status.install_command, /agent-reach/);
  assert.equal(status.summary.channel_count, 0);
});

test("Agent-Reach status parses doctor json and masks stderr noise", async () => {
  const status = await checkAgentReachStatus({
    commandCandidates: ["agent-reach"],
    runner: async (command, args) => {
      assert.equal(command, "agent-reach");
      assert.deepEqual(args, ["doctor", "--json"]);
      return {
        stdout: JSON.stringify({
          web: {
            status: "ok",
            name: "任意网页",
            message: "Jina Reader 可用",
            tier: 0,
            backends: ["Jina Reader"],
            active_backend: "Jina Reader",
          },
          github: {
            status: "warn",
            name: "GitHub 仓库和代码",
            message: "gh 未登录",
            tier: 0,
            backends: ["gh CLI"],
            active_backend: "gh CLI",
          },
        }),
        stderr: "debug details should not leak",
      };
    },
  });

  assert.equal(status.available, true);
  assert.equal(status.status, "warn");
  assert.equal(status.command, "agent-reach");
  assert.equal(status.summary.channel_count, 2);
  assert.equal(status.summary.available_count, 1);
  assert.equal(status.summary.channels[0].id, "web");
  assert.equal(status.error, "");
});

test("Agent-Reach status masks sensitive CLI failures", async () => {
  const status = await checkAgentReachStatus({
    commandCandidates: ["agent-reach"],
    runner: async () => {
      throw new Error("api_key=secret-token cookie=session-id");
    },
  });

  assert.equal(status.available, false);
  assert.equal(status.status, "error");
  assert.match(status.error, /api_key=\*\*\*/);
  assert.match(status.error, /cookie=\*\*\*/);
  assert.doesNotMatch(status.error, /secret-token|session-id/);
});
