import { readFile } from "node:fs/promises";
import path from "node:path";

import { checkAgentReachStatus } from "./agent-reach";

export type ConfigHealthStatus = "ok" | "warn" | "fail";

export type ConfigHealthItem = {
  id: string;
  label: string;
  status: ConfigHealthStatus;
  summary: string;
  path: string;
};

export type ConfigHealthSummary = {
  status: ConfigHealthStatus;
  ok_count: number;
  warn_count: number;
  fail_count: number;
  items: ConfigHealthItem[];
};

type ConfigHealthOptions = {
  workspaceDir: string;
  dataDir: string;
  env?: NodeJS.ProcessEnv;
};

const REQUIRED_ENV_KEYS = ["OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"];

const INTEGRATION_CREDENTIAL_GROUPS: Array<{ label: string; keys: string[] }> = [
  { label: "Jackyun ERP", keys: ["JACKYUN_APP_KEY", "JACKYUN_APP_SECRET"] },
  {
    label: "Kingdee ERP",
    keys: ["KINGDEE_BASE_URL", "KINGDEE_ACCT_ID", "KINGDEE_USERNAME", "KINGDEE_PASSWORD"],
  },
  {
    label: "WeCom smart sheet MCP",
    keys: [
      "WECOM_SMARTSHEET_MCP_URL",
      "WEWORK_SMARTSHEET_MCP_URL",
      "WEDOC_MCP_URL",
      "WEWORK_WEDOC_MCP_URL",
    ],
  },
  {
    label: "LLM provider",
    keys: ["LLM_BINDING_API_KEY", "OPENAI_API_KEY"],
  },
  {
    label: "Embedding provider",
    keys: ["EMBEDDING_BINDING_API_KEY", "OPENAI_API_KEY"],
  },
];

function credentialPresenceSummary(env: Record<string, string>): string {
  const parts = INTEGRATION_CREDENTIAL_GROUPS.map(({ label, keys }) => {
    const configured = keys.some((key) => Boolean(env[key]));
    return `${label}: ${configured ? "configured" : "not configured"}`;
  });
  return parts.join("; ");
}

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

async function readJson(filePath: string): Promise<{
  value: Record<string, unknown> | null;
  error: string;
}> {
  try {
    return {
      value: JSON.parse(await readFile(filePath, "utf8")) as Record<string, unknown>,
      error: "",
    };
  } catch (error) {
    return {
      value: null,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function readEnvFile(filePath: string) {
  const values: Record<string, string> = {};
  try {
    const content = await readFile(filePath, "utf8");
    for (const line of content.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) {
        continue;
      }
      const [key, ...parts] = trimmed.split("=");
      values[key.trim()] = parts.join("=").trim().replace(/^['"]|['"]$/g, "");
    }
  } catch {
    return values;
  }
  return values;
}

function item(
  id: string,
  label: string,
  status: ConfigHealthStatus,
  summary: string,
  filePath: string,
): ConfigHealthItem {
  return { id, label, status, summary, path: filePath };
}

async function envHealth(workspaceDir: string, env: NodeJS.ProcessEnv) {
  const envPath = path.join(workspaceDir, ".env");
  const fileValues = await readEnvFile(envPath);
  const merged = { ...fileValues, ...env };
  const missing = REQUIRED_ENV_KEYS.filter((key) => !merged[key]);
  if (missing.length) {
    return item(
      "env",
      ".env",
      "fail",
      `Missing required keys: ${missing.join(", ")}. Sensitive values are not exposed.`,
      envPath,
    );
  }
  return item(
    "env",
    ".env",
    "ok",
    `Required env keys are present. ${credentialPresenceSummary(merged)}.`,
    envPath,
  );
}

async function connectorHealth(filePath: string) {
  const { value, error } = await readJson(filePath);
  if (!value) {
    return item("connector_registry", "Connector registry", "warn", `Unavailable or invalid: ${error}`, filePath);
  }
  const connectors = safeRecord(value.connectors);
  const unsafe = Object.entries(connectors)
    .filter(([, raw]) => safeRecord(raw).external_write_enabled === true)
    .map(([connectorId]) => connectorId);
  if (unsafe.length) {
    return item(
      "connector_registry",
      "Connector registry",
      "fail",
      `External writes enabled for: ${unsafe.join(", ")}.`,
      filePath,
    );
  }
  return item(
    "connector_registry",
    "Connector registry",
    "ok",
    `${Object.keys(connectors).length} connector(s), external writes disabled.`,
    filePath,
  );
}

async function mcpHealth(filePath: string) {
  const { value, error } = await readJson(filePath);
  if (!value) {
    return item("mcp_policy", "MCP policy", "warn", `Unavailable or invalid: ${error}`, filePath);
  }
  const tools = safeRecord(value.tools);
  const unsafe = Object.entries(tools)
    .filter(([, raw]) => safeRecord(raw).external_write_enabled === true)
    .map(([toolName]) => toolName);
  const missingConfirmation = Object.entries(tools)
    .filter(([, raw]) => {
      const tool = safeRecord(raw);
      return tool.read_only === false && tool.requires_human_confirmation !== true;
    })
    .map(([toolName]) => toolName);
  if (unsafe.length || missingConfirmation.length) {
    return item(
      "mcp_policy",
      "MCP policy",
      "fail",
      [
        unsafe.length ? `external writes: ${unsafe.join(", ")}` : "",
        missingConfirmation.length ? `missing confirmation: ${missingConfirmation.join(", ")}` : "",
      ]
        .filter(Boolean)
        .join("; "),
      filePath,
    );
  }
  return item("mcp_policy", "MCP policy", "ok", `${Object.keys(tools).length} tool policy item(s).`, filePath);
}

async function skillHealth(registryPath: string, templateDir: string) {
  const { value, error } = await readJson(registryPath);
  if (!value) {
    return item("skill_registry", "Skill registry", "warn", `Unavailable or invalid: ${error}`, registryPath);
  }
  const skills = safeRecord(value.skills);
  const missingTemplates: string[] = [];
  for (const [skillId, raw] of Object.entries(skills)) {
    const skill = safeRecord(raw);
    const normalizedId = safeText(skill.skill_id) || skillId;
    if (skill.status === "active") {
      const templatePath = path.join(templateDir, `${normalizedId}.json`);
      const template = await readJson(templatePath);
      if (!template.value) missingTemplates.push(normalizedId);
    }
  }
  if (missingTemplates.length) {
    return item(
      "skill_registry",
      "Skill registry",
      "fail",
      `Active Skill missing template: ${missingTemplates.join(", ")}.`,
      registryPath,
    );
  }
  return item("skill_registry", "Skill registry", "ok", `${Object.keys(skills).length} skill(s).`, registryPath);
}

async function lightragHealth(dataDir: string, env: NodeJS.ProcessEnv) {
  const workingDir = env.WORKING_DIR
    ? path.resolve(env.WORKING_DIR)
    : path.join(dataDir, "lightrag_official");
  const apiUrl = env.LIGHTRAG_API_URL || `http://127.0.0.1:${env.LIGHTRAG_PORT || "9621"}`;
  const docStatus = await readJson(path.join(workingDir, "kv_store_doc_status.json"));
  return item(
    "lightrag_settings",
    "LightRAG settings",
    docStatus.value ? "ok" : "warn",
    `${apiUrl}; doc status ${docStatus.value ? "available" : "not available yet"}.`,
    path.join(workingDir, "kv_store_doc_status.json"),
  );
}

async function agentReachHealth(env: NodeJS.ProcessEnv) {
  const command = safeText(env.A2A_AGENT_REACH_BIN) || "agent-reach";
  const status = await checkAgentReachStatus({
    commandCandidates: [command],
  });
  if (!status.available) {
    return item(
      "agent_reach",
      "Agent-Reach",
      "warn",
      `互联网公开资料能力未安装或不可用：${status.error || status.install_command}`,
      command,
    );
  }
  return item(
    "agent_reach",
    "Agent-Reach",
    status.status === "error" ? "warn" : status.summary.status,
    `公开渠道 ${status.summary.public_ready_count} / 可用 ${status.summary.available_count} / 总计 ${status.summary.channel_count}；登录态待确认 ${status.summary.login_required_count}`,
    status.command,
  );
}

export async function summarizeConfigHealth({
  workspaceDir,
  dataDir,
  env = process.env,
}: ConfigHealthOptions): Promise<ConfigHealthSummary> {
  const items = await Promise.all([
    envHealth(workspaceDir, env),
    connectorHealth(
      env.A2A_CONNECTOR_REGISTRY
        ? path.resolve(env.A2A_CONNECTOR_REGISTRY)
        : path.join(dataDir, "warehouse", "connector_registry.json"),
    ),
    mcpHealth(
      env.A2A_MCP_POLICY_PATH
        ? path.resolve(env.A2A_MCP_POLICY_PATH)
        : path.join(dataDir, "mcp", "tool_policy.json"),
    ),
    skillHealth(
      path.join(
        env.A2A_SKILL_REGISTRY_DIR
          ? path.resolve(env.A2A_SKILL_REGISTRY_DIR)
          : path.join(dataDir, "skill_registry"),
        "registry.json",
      ),
      env.A2A_AGENT_TEMPLATE_DIR
        ? path.resolve(env.A2A_AGENT_TEMPLATE_DIR)
        : path.join(dataDir, "agent_templates"),
    ),
    lightragHealth(dataDir, env),
    agentReachHealth(env),
  ]);

  const failCount = items.filter((check) => check.status === "fail").length;
  const warnCount = items.filter((check) => check.status === "warn").length;
  return {
    status: failCount > 0 ? "fail" : warnCount > 0 ? "warn" : "ok",
    ok_count: items.filter((check) => check.status === "ok").length,
    warn_count: warnCount,
    fail_count: failCount,
    items,
  };
}
