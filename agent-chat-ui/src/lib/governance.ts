import { execFile } from "node:child_process";
import {
  copyFile,
  mkdir,
  readFile,
  readdir,
  realpath,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import {
  checkAgentReachStatus,
  type AgentReachStatus,
} from "./agent-reach";

export type GovernancePaths = {
  workspaceDir: string;
  dataDir: string;
  wikiDir: string;
  skillLibraryDir: string;
  skillRegistryDir: string;
  templateDir: string;
  mcpPolicyPath: string;
  auditPath: string;
};

export type SkillRegistryItem = {
  skill_id: string;
  name: string;
  status: string;
  version: number;
  source_wiki_path: string;
  tool_count: number;
  updated_at: string;
  path?: string;
  source_type?: string;
  source_skill_path?: string;
  managed_skill_dir?: string;
  source_status?: string;
  source_exists?: boolean;
  managed_source_available?: boolean;
  asset_count?: number;
  scenarios?: string[];
  tool_allowlist?: string[];
  output_schema?: string[];
};

export type SkillLibraryItem = {
  folder_name: string;
  name: string;
  candidate_skill_id: string;
  source_path: string;
  skill_file_path: string;
  registered_skill_id: string;
  registered_status: string;
  managed_skill_dir: string;
  updated_at: string;
};

export type McpPolicyItem = {
  tool_name: string;
  description: string;
  action: string;
  read_only: boolean;
  requires_human_confirmation: boolean;
  external_write_enabled: boolean;
  risk_level: string;
  data_sources: string[];
  allowed_callers: string[];
  destructive_effects: string[];
  tool_registry_status?: string;
};

export type MarketplaceTemplateItem = {
  name: string;
  display_name: string;
  version: string;
  description: string;
  category: string;
  requires: string[];
  homepage: string;
  source_url: string;
  install_cmd: string;
  entry_point: string;
  execution_mode: string;
  read_only: boolean;
  requires_human_confirmation: boolean;
  risk_level: string;
  allowed_callers: string[];
  data_sources: string[];
  safety_contract: string[];
  path?: string;
};

type JsonRecord = Record<string, unknown>;

type SummaryInput = {
  skillRegistry?: JsonRecord | null;
  skillItems?: SkillRegistryItem[];
  skillLibraryItems?: SkillLibraryItem[];
  marketplaceTemplates?: MarketplaceTemplateItem[];
  mcpPolicy?: JsonRecord | null;
  toolRegistry?: JsonRecord | null;
  auditEvents?: GovernanceAuditEvent[];
  agentReach?: AgentReachStatus | null;
  paths?: Partial<GovernancePaths>;
};

export type ToolRegistryItem = {
  tool_name: string;
  handler: string;
  description: string;
  group: string;
  read_only: boolean;
  risk_level: string;
  requires_confirmation: boolean;
  data_sources: string[];
  max_result_size: number;
  availability_check: string;
  owner_module: string;
  visible_agents: string[];
  mcp_policy_status: string;
  recent_call_risk: string;
};

export type GovernanceAuditEvent = {
  event_type: string;
  actor: string;
  summary: string;
  created_at: string;
  thread_id?: string;
  task_id?: string;
  agent_id?: string;
  risk_level: string;
  tool_name: string;
  skill_id: string;
};

const SKILL_SCHEMA = "a2a_agent_skill_v1";
const REGISTRY_SCHEMA = "a2a_agent_skill_registry_v1";
const MCP_POLICY_SCHEMA = "a2a_mcp_tool_policy_v1";
const TOOL_REGISTRY_SCHEMA = "a2a_tool_registry_v2";
const VALID_SKILL_STATUSES = new Set([
  "draft",
  "active",
  "paused",
  "disabled",
  "archived",
]);
const READ_ONLY_SKILL_TOOLS = new Set([
  "assess_data_quality",
  "audit_fact_source_readiness",
  "get_erp_connector_health",
  "list_erp_connectors",
  "list_erp_live_query_capabilities",
  "list_fact_tables",
  "list_registered_datasets",
  "list_wiki_pages",
  "plan_fact_query",
  "preview_erp_connector_sync",
  "query_ads_history",
  "query_erp_live_snapshot",
  "query_fact_layer",
  "query_fact_layer_from_question",
  "query_finance_history",
  "query_inventory_cost_reference",
  "query_inventory_anomalies",
  "query_inventory_history",
  "query_inventory_snapshot",
  "query_lightrag",
  "query_official_lightrag",
  "query_sales_history",
  "read_wiki_page",
  "route_erp_live_query",
  "search_wiki",
  "summarize_brand_coverage",
  "summarize_business_data",
  "test_erp_live_connection",
  "verify_erp_supplier_terms_mapping",
]);

const DEFAULT_OUTPUT_SCHEMA = [
  "summary",
  "evidence",
  "data_gaps",
  "risks",
  "next_actions",
];
const execFileAsync = promisify(execFile);
const WRITE_ACTION_MARKERS = [
  "write",
  "external",
  "delete",
  "submit",
  "push",
  "save",
  "send",
  "create",
  "update",
];
const RISK_LEVELS = ["low", "medium", "high", "critical"] as const;
const KNOWN_MCP_ALLOWED_CALLERS = new Set([
  "top_company_brain_supervisor",
  "data_agent",
  "inventory_agent",
  "decision_agent",
  "company_strategy_agent",
  "auto_workflow_agent",
  "agent_factory_agent",
  "finance_agent",
  "financial_planning_agent",
  "knowledge_agent",
]);

const AGENT_REACH_READERS = [
  "top_company_brain_supervisor",
  "knowledge_agent",
  "data_agent",
  "decision_agent",
  "company_strategy_agent",
  "auto_workflow_agent",
  "agent_factory_agent",
];

const DEFAULT_MCP_TOOL_POLICY: Record<
  string,
  Omit<McpPolicyItem, "tool_name">
> = {
  query_erp_live_snapshot: {
    description: "吉客云/金蝶实时只读 ERP 查询。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["jackyun_erp", "kingdee_erp"],
    allowed_callers: [
      "data_agent",
      "decision_agent",
      "company_strategy_agent",
      "auto_workflow_agent",
      "agent_factory_agent",
    ],
    destructive_effects: [],
  },
  query_wecom_smartsheet_records: {
    description: "通过 WeDoc MCP 只读查询企业微信智能表记录。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["WeCom_smartsheet"],
    allowed_callers: [
      "top_company_brain_supervisor",
      "data_agent",
      "decision_agent",
      "company_strategy_agent",
      "auto_workflow_agent",
      "agent_factory_agent",
    ],
    destructive_effects: [],
  },
  list_wecom_smartsheet_sources: {
    description: "列出企业微信智能表系统连接配置。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["WeCom_smartsheet"],
    allowed_callers: [
      "top_company_brain_supervisor",
      "data_agent",
      "decision_agent",
      "company_strategy_agent",
      "auto_workflow_agent",
      "agent_factory_agent",
    ],
    destructive_effects: [],
  },
  test_wecom_smartsheet_connection: {
    description: "只读测试企业微信智能表 MCP 连接。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["WeCom_smartsheet"],
    allowed_callers: [
      "top_company_brain_supervisor",
      "data_agent",
      "decision_agent",
      "company_strategy_agent",
      "auto_workflow_agent",
      "agent_factory_agent",
    ],
    destructive_effects: [],
  },
  sync_wecom_smartsheet_snapshot: {
    description: "把企业微信智能表只读快照写入本地 staging/DuckDB。",
    action: "write_local_snapshot",
    read_only: false,
    requires_human_confirmation: true,
    external_write_enabled: false,
    risk_level: "medium",
    data_sources: ["local_staging", "duckdb", "WeCom_smartsheet"],
    allowed_callers: ["auto_workflow_agent"],
    destructive_effects: ["写入本地 WeCom snapshot 并注册 DuckDB fact layer。"],
  },
  sync_connector_dataset: {
    description: "把已获取的只读 ERP 快照注册进本地 staging/DuckDB。",
    action: "write_local_snapshot",
    read_only: false,
    requires_human_confirmation: true,
    external_write_enabled: false,
    risk_level: "medium",
    data_sources: ["local_staging", "duckdb"],
    allowed_callers: ["auto_workflow_agent"],
    destructive_effects: [
      "写入本地 connector snapshot 并注册 DuckDB fact layer。",
    ],
  },
  agent_reach_get_status: {
    description: "只读检查 Agent-Reach 外部公开资料能力状态。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["agent_reach"],
    allowed_callers: AGENT_REACH_READERS,
    destructive_effects: [],
  },
  agent_reach_read_public_web: {
    description: "通过 Agent-Reach 只读读取公开网页内容。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["agent_reach_public_web"],
    allowed_callers: AGENT_REACH_READERS,
    destructive_effects: [],
  },
  agent_reach_search_public_sources: {
    description: "通过 Agent-Reach 只读搜索公开网页、RSS、GitHub 和公开社区资料。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["agent_reach_public_search"],
    allowed_callers: AGENT_REACH_READERS,
    destructive_effects: [],
  },
  agent_reach_read_video_transcript: {
    description: "通过 Agent-Reach 只读提取公开视频字幕和播客转写。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["agent_reach_public_video"],
    allowed_callers: AGENT_REACH_READERS,
    destructive_effects: [],
  },
  agent_reach_read_logged_in_social: {
    description:
      "通过 Agent-Reach 读取需登录态的平台公开内容；仅在人工确认专用账号和 Cookie 边界后允许。",
    action: "read",
    read_only: true,
    requires_human_confirmation: true,
    external_write_enabled: false,
    risk_level: "medium",
    data_sources: ["agent_reach_social"],
    allowed_callers: AGENT_REACH_READERS,
    destructive_effects: [
      "需要专用账号或浏览器登录态，禁止使用主账号 Cookie，禁止发帖、评论、点赞或私信。",
    ],
  },
  create_purchase_order: {
    description: "创建采购单，当前只允许生成审批请求，不允许直接执行。",
    action: "write_external_erp",
    read_only: false,
    requires_human_confirmation: true,
    external_write_enabled: false,
    risk_level: "high",
    data_sources: ["erp"],
    allowed_callers: ["auto_workflow_agent"],
    destructive_effects: ["创建采购单会影响 ERP 业务单据。"],
  },
  update_ad_budget: {
    description: "修改广告预算，当前只允许生成审批请求，不允许直接执行。",
    action: "write_external_ad_platform",
    read_only: false,
    requires_human_confirmation: true,
    external_write_enabled: false,
    risk_level: "high",
    data_sources: ["ad_platform"],
    allowed_callers: ["auto_workflow_agent"],
    destructive_effects: ["修改广告预算会影响实际花费。"],
  },
  send_external_message: {
    description: "外发消息，当前只允许生成审批请求，不允许直接执行。",
    action: "write_external_message",
    read_only: false,
    requires_human_confirmation: true,
    external_write_enabled: false,
    risk_level: "high",
    data_sources: ["external_messaging"],
    allowed_callers: ["auto_workflow_agent"],
    destructive_effects: ["外发消息会触达外部人员或客户。"],
  },
  supermemory_profile: {
    description:
      "读取 Supermemory 用户/团队 profile；只做上下文，不作为经营证据。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["external_memory"],
    allowed_callers: ["top_company_brain_supervisor", "agent_factory_agent"],
    destructive_effects: [],
  },
  supermemory_recall: {
    description: "只读召回 Supermemory 记忆；结果不能写入 evidence 字段。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["external_memory"],
    allowed_callers: ["top_company_brain_supervisor", "agent_factory_agent"],
    destructive_effects: [],
  },
  supermemory_context: {
    description:
      "只读获取 Supermemory context；不替代 DuckDB/ERP/wiki/LightRAG。",
    action: "read",
    read_only: true,
    requires_human_confirmation: false,
    external_write_enabled: false,
    risk_level: "low",
    data_sources: ["external_memory"],
    allowed_callers: ["top_company_brain_supervisor", "agent_factory_agent"],
    destructive_effects: [],
  },
  supermemory_save_memory: {
    description: "写入 Supermemory 记忆请求，必须人工确认并经过敏感字段扫描。",
    action: "write_external_memory",
    read_only: false,
    requires_human_confirmation: true,
    external_write_enabled: false,
    risk_level: "high",
    data_sources: ["external_memory"],
    allowed_callers: ["top_company_brain_supervisor"],
    destructive_effects: ["会把用户确认后的长期记忆写入 hosted Supermemory。"],
  },
};

function nowIso() {
  return new Date().toISOString();
}

function safeRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : {};
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeBoolean(value: unknown): boolean {
  return value === true;
}

function safeNumber(value: unknown): number {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function safeArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asTextArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(safeText).filter(Boolean);
  return safeText(value)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function slugify(value: string, fallback: string) {
  const slug = value
    .replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (slug || fallback).slice(0, 96);
}

function titleFromMarkdown(content: string, fallback: string) {
  return content.match(/^#\s+(.+)$/m)?.[1]?.trim() || fallback;
}

function stableSkillId(value: string) {
  return slugify(value, "agent-skill").toLowerCase();
}

function relativeToWorkspace(workspaceDir: string, filePath: string) {
  try {
    const relative = path.relative(workspaceDir, filePath);
    return relative && !relative.startsWith("..") ? relative : filePath;
  } catch {
    return filePath;
  }
}

async function fileExists(filePath: string) {
  try {
    return (await stat(filePath)).isFile();
  } catch {
    return false;
  }
}

async function pathExists(filePath: string) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

function resolveWorkspacePath(paths: GovernancePaths, rawPath: string) {
  const cleanPath = safeText(rawPath);
  if (!cleanPath) return "";
  return path.isAbsolute(cleanPath)
    ? cleanPath
    : path.join(paths.workspaceDir, cleanPath);
}

function templatePath(templateDir: string, skillId: string) {
  return path.join(templateDir, `${slugify(skillId, "agent-skill")}.json`);
}

function skillPath(skillRegistryDir: string, skillId: string) {
  return path.join(
    skillRegistryDir,
    "skills",
    `${slugify(skillId, "agent-skill")}.json`,
  );
}

async function readJson<T>(filePath: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await readFile(filePath, "utf8")) as T;
  } catch {
    return fallback;
  }
}

async function writeJson(filePath: string, payload: JsonRecord) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, JSON.stringify(payload, null, 2), "utf8");
}

function normalizeSkillRegistryItem(raw: JsonRecord): SkillRegistryItem {
  return {
    skill_id: safeText(raw.skill_id),
    name: safeText(raw.name),
    status: safeText(raw.status) || "unknown",
    version: safeNumber(raw.version),
    source_wiki_path: safeText(raw.source_wiki_path),
    tool_count: safeNumber(raw.tool_count),
    updated_at: safeText(raw.updated_at),
    path: safeText(raw.path) || undefined,
    source_type: safeText(raw.source_type) || undefined,
    source_skill_path: safeText(raw.source_skill_path) || undefined,
    managed_skill_dir: safeText(raw.managed_skill_dir) || undefined,
    source_status: safeText(raw.source_status) || undefined,
    source_exists:
      typeof raw.source_exists === "boolean" ? raw.source_exists : undefined,
    managed_source_available:
      typeof raw.managed_source_available === "boolean"
        ? raw.managed_source_available
        : undefined,
    asset_count: safeNumber(raw.asset_count),
    scenarios: asTextArray(raw.scenarios),
    tool_allowlist: asTextArray(raw.tool_allowlist),
    output_schema: asTextArray(raw.output_schema),
  };
}

function normalizeMcpPolicyItem(
  toolName: string,
  raw: JsonRecord,
): McpPolicyItem {
  return {
    tool_name: toolName,
    description: safeText(raw.description),
    action:
      safeText(raw.action) || (safeBoolean(raw.read_only) ? "read" : "write"),
    read_only: safeBoolean(raw.read_only),
    requires_human_confirmation: safeBoolean(raw.requires_human_confirmation),
    external_write_enabled: safeBoolean(raw.external_write_enabled),
    risk_level: safeText(raw.risk_level) || "unknown",
    data_sources: asTextArray(raw.data_sources),
    allowed_callers: asTextArray(raw.allowed_callers),
    destructive_effects: asTextArray(raw.destructive_effects),
  };
}

function normalizeMarketplaceTemplate(
  raw: JsonRecord,
  templatePath = "",
): MarketplaceTemplateItem {
  const readOnly = raw.read_only !== false;
  return {
    name: safeText(raw.name),
    display_name: safeText(raw.display_name) || safeText(raw.name),
    version: safeText(raw.version),
    description: safeText(raw.description),
    category: safeText(raw.category) || "runtime_capability",
    requires: asTextArray(raw.requires),
    homepage: safeText(raw.homepage),
    source_url: safeText(raw.source_url),
    install_cmd: safeText(raw.install_cmd),
    entry_point: safeText(raw.entry_point),
    execution_mode: safeText(raw.execution_mode) || "cli_json",
    read_only: readOnly,
    requires_human_confirmation:
      raw.requires_human_confirmation === true || !readOnly,
    risk_level: safeText(raw.risk_level) || (readOnly ? "low" : "high"),
    allowed_callers: asTextArray(raw.allowed_callers),
    data_sources: asTextArray(raw.data_sources),
    safety_contract: asTextArray(raw.safety_contract),
    path: templatePath || undefined,
  };
}

function normalizeToolRegistryItem(
  toolName: string,
  raw: JsonRecord,
  visibleAgents: string[],
): ToolRegistryItem {
  const normalizedName = safeText(raw.name) || toolName;
  return {
    tool_name: normalizedName,
    handler: safeText(raw.handler) || normalizedName,
    description: safeText(raw.description),
    group: safeText(raw.group) || "unknown",
    read_only: raw.read_only !== false,
    risk_level: safeText(raw.risk_level) || "unknown",
    requires_confirmation:
      raw.requires_confirmation === true ||
      raw.requires_human_confirmation === true,
    data_sources: asTextArray(raw.data_sources),
    max_result_size: safeNumber(raw.max_result_size),
    availability_check: safeText(raw.availability_check) || "unknown",
    owner_module: safeText(raw.owner_module) || "unknown",
    visible_agents: asTextArray(raw.visible_agents).length
      ? asTextArray(raw.visible_agents)
      : visibleAgents,
    mcp_policy_status: "not_checked",
    recent_call_risk: "",
  };
}

function toolRegistryEntries(rawRegistry: JsonRecord): ToolRegistryItem[] {
  const agents = safeRecord(rawRegistry.agents);
  const agentsByTool = new Map<string, string[]>();
  for (const [agentName, tools] of Object.entries(agents)) {
    for (const toolName of asTextArray(tools)) {
      const current = agentsByTool.get(toolName) ?? [];
      current.push(agentName);
      agentsByTool.set(toolName, current);
    }
  }

  const rawTools = rawRegistry.tools;
  const entries = Array.isArray(rawTools)
    ? rawTools.map((item) => {
        const record = safeRecord(item);
        const toolName = safeText(record.name) || safeText(record.tool_name);
        return [toolName, record] as const;
      })
    : Object.entries(safeRecord(rawTools)).map(
        ([toolName, value]) => [toolName, safeRecord(value)] as const,
      );

  return entries
    .filter(([toolName]) => Boolean(toolName))
    .map(([toolName, record]) =>
      normalizeToolRegistryItem(
        toolName,
        record,
        agentsByTool.get(toolName) ?? [],
      ),
    )
    .sort((left, right) => left.tool_name.localeCompare(right.tool_name));
}

function uniqueSorted(items: string[]) {
  return Array.from(new Set(items.filter(Boolean))).sort((left, right) =>
    left.localeCompare(right),
  );
}

function isExternalRegistryTool(tool: ToolRegistryItem) {
  return (
    tool.group === "external_read" ||
    tool.group === "external_write_request" ||
    tool.data_sources.includes("ERP_live_readonly")
  );
}

function registryPolicyStatus(
  tool: ToolRegistryItem,
  policy: McpPolicyItem | undefined,
) {
  if (!isExternalRegistryTool(tool) && !policy) return "not_required";
  if (!policy) return "policy_missing";
  const confirmationMismatch =
    tool.requires_confirmation !== policy.requires_human_confirmation;
  const readOnlyMismatch =
    tool.read_only !== policy.read_only && isExternalRegistryTool(tool);
  return confirmationMismatch || readOnlyMismatch ? "policy_conflict" : "ok";
}

function buildSkillPermissionPreview(requestedTools: string[]) {
  const approvedTools = requestedTools.filter((tool) =>
    READ_ONLY_SKILL_TOOLS.has(tool),
  );
  const blockedTools = requestedTools.filter(
    (tool) => !READ_ONLY_SKILL_TOOLS.has(tool),
  );
  return {
    requires_human_confirmation: true,
    approved_tools: approvedTools,
    blocked_tools: blockedTools,
    tool_count: approvedTools.length,
    risks: [
      "new reusable skill requires human approval before activation",
      ...(blockedTools.length
        ? [
            "blocked tools removed because project skills currently admit read-only analysis tools",
          ]
        : []),
    ],
    confirmation_required_before: ["status=active", "skill_used_by_agent"],
  };
}

function buildPromptTemplate(skill: JsonRecord, wikiContent: string) {
  const body =
    wikiContent.length > 12000
      ? `${wikiContent.slice(0, 11800).trim()}\n\n... omitted from active skill prompt ...`
      : wikiContent.trim();
  return {
    template_id: safeText(skill.skill_id),
    status: safeText(skill.status),
    source_skill_id: safeText(skill.skill_id),
    source_version: safeNumber(skill.version),
    source_wiki_path: safeText(skill.source_wiki_path),
    saved_at: nowIso(),
    role: safeText(skill.role) || safeText(skill.name),
    goal: safeText(skill.goal),
    scenarios: asTextArray(skill.scenarios),
    tools: asTextArray(skill.tool_allowlist),
    output_schema: asTextArray(skill.output_schema),
    prompt: [
      `你是${safeText(skill.role) || safeText(skill.name) || "可复用 Agent Skill"}。`,
      `目标：${safeText(skill.goal)}`,
      `适用场景：${asTextArray(skill.scenarios).join(", ")}`,
      `允许工具：${asTextArray(skill.tool_allowlist).join(", ")}`,
      `输出字段：${asTextArray(skill.output_schema).join(", ")}`,
      "必须遵守下方业务规则；数据不足时列出缺口；实时 ERP 只作为只读兜底；高风险动作必须要求人工确认。",
      "",
      body,
    ].join("\n"),
  };
}

async function appendGovernanceAudit(
  paths: GovernancePaths,
  eventType: string,
  {
    actor,
    summary,
    metadata = {},
    risks = [],
  }: {
    actor: string;
    summary: string;
    metadata?: JsonRecord;
    risks?: string[];
  },
) {
  await mkdir(path.dirname(paths.auditPath), { recursive: true });
  const event = {
    event_type: eventType,
    actor,
    summary,
    created_at: nowIso(),
    risks,
    metadata,
  };
  const existing = await readFile(paths.auditPath, "utf8").catch(() => "");
  await writeFile(
    paths.auditPath,
    `${existing}${JSON.stringify(event)}\n`,
    "utf8",
  );
}

export function resolveGovernancePaths(
  env: NodeJS.ProcessEnv = process.env,
): GovernancePaths {
  const dataDir = env.A2A_DATA_DIR
    ? path.resolve(env.A2A_DATA_DIR)
    : path.resolve(process.cwd(), "..", "data");
  const workspaceDir = path.resolve(dataDir, "..");
  const wikiDir = env.A2A_WIKI_DIR
    ? path.resolve(env.A2A_WIKI_DIR)
    : path.join(workspaceDir, "wiki");
  const skillLibraryDir = env.A2A_SKILL_LIBRARY_DIR
    ? path.resolve(env.A2A_SKILL_LIBRARY_DIR)
    : path.join(workspaceDir, "skills");
  const skillRegistryDir = env.A2A_SKILL_REGISTRY_DIR
    ? path.resolve(env.A2A_SKILL_REGISTRY_DIR)
    : path.join(dataDir, "skill_registry");
  const templateDir = env.A2A_AGENT_TEMPLATE_DIR
    ? path.resolve(env.A2A_AGENT_TEMPLATE_DIR)
    : path.join(dataDir, "agent_templates");
  const mcpPolicyPath = env.A2A_MCP_POLICY_PATH
    ? path.resolve(env.A2A_MCP_POLICY_PATH)
    : path.join(dataDir, "mcp", "tool_policy.json");
  const auditPath = env.A2A_AUDIT_LOG
    ? path.resolve(env.A2A_AUDIT_LOG)
    : path.join(dataDir, "audit", "events.jsonl");
  return {
    workspaceDir,
    dataDir,
    wikiDir,
    skillLibraryDir,
    skillRegistryDir,
    templateDir,
    mcpPolicyPath,
    auditPath,
  };
}

export function summarizeGovernanceState(input: SummaryInput) {
  const registrySkills = Object.values(
    safeRecord(input.skillRegistry?.skills),
  ).map((item) => normalizeSkillRegistryItem(safeRecord(item)));
  const detailedById = new Map(
    (input.skillItems ?? []).map((item) => [item.skill_id, item]),
  );
  const skills = registrySkills
    .map((item) => ({ ...item, ...(detailedById.get(item.skill_id) ?? {}) }))
    .filter((item) => item.skill_id)
    .sort((left, right) =>
      safeText(right.updated_at).localeCompare(safeText(left.updated_at)),
    );

  const toolsRecord = safeRecord(input.mcpPolicy?.tools);
  const mcpTools = Object.entries(toolsRecord)
    .map(([toolName, raw]) => normalizeMcpPolicyItem(toolName, safeRecord(raw)))
    .sort((left, right) => left.tool_name.localeCompare(right.tool_name));
  const mcpByName = new Map(mcpTools.map((tool) => [tool.tool_name, tool]));
  const latestAuditRiskByTool = new Map<string, string>();
  for (const event of input.auditEvents ?? []) {
    if (
      event.tool_name &&
      event.risk_level &&
      !latestAuditRiskByTool.has(event.tool_name)
    ) {
      latestAuditRiskByTool.set(event.tool_name, event.risk_level);
    }
  }
  const registryItems = toolRegistryEntries(safeRecord(input.toolRegistry)).map(
    (tool) => ({
      ...tool,
      mcp_policy_status: registryPolicyStatus(
        tool,
        mcpByName.get(tool.tool_name),
      ),
      recent_call_risk: latestAuditRiskByTool.get(tool.tool_name) ?? "",
    }),
  );
  const registryNames = new Set(registryItems.map((tool) => tool.tool_name));
  const mcpItems = mcpTools.map((tool) => ({
    ...tool,
    tool_registry_status: registryNames.has(tool.tool_name)
      ? "ok"
      : "registry_missing",
  }));
  const policyValidationItems = [
    {
      id: "external_writes_disabled",
      label: "External writes disabled",
      status: mcpTools.some((tool) => tool.external_write_enabled)
        ? "fail"
        : "ok",
      summary: mcpTools.some((tool) => tool.external_write_enabled)
        ? "One or more MCP policy tools enable external writes."
        : "MCP policy keeps external writes disabled.",
    },
    {
      id: "write_confirmation",
      label: "Write confirmation",
      status: mcpTools.some(
        (tool) => !tool.read_only && !tool.requires_human_confirmation,
      )
        ? "fail"
        : "ok",
      summary: mcpTools.some(
        (tool) => !tool.read_only && !tool.requires_human_confirmation,
      )
        ? "One or more write tools are missing human confirmation."
        : "Write tools require human confirmation.",
    },
    {
      id: "registry_policy_coverage",
      label: "Registry coverage",
      status: registryItems.some(
        (tool) => tool.mcp_policy_status === "policy_conflict",
      )
        ? "fail"
        : registryItems.some((tool) =>
              ["policy_missing", "registry_missing"].includes(
                tool.mcp_policy_status,
              ),
            ) ||
            mcpItems.some(
              (tool) => tool.tool_registry_status === "registry_missing",
            )
          ? "warn"
          : "ok",
      summary: `missing ${registryItems.filter((tool) => tool.mcp_policy_status === "policy_missing").length} / conflict ${registryItems.filter((tool) => tool.mcp_policy_status === "policy_conflict").length} / registry missing ${mcpItems.filter((tool) => tool.tool_registry_status === "registry_missing").length}`,
    },
  ];
  const policyFailCount = policyValidationItems.filter(
    (item) => item.status === "fail",
  ).length;
  const policyWarnCount = policyValidationItems.filter(
    (item) => item.status === "warn",
  ).length;
  const marketplaceItems = (input.marketplaceTemplates ?? [])
    .filter((item) => item.name)
    .sort((left, right) => left.name.localeCompare(right.name));

  return {
    status: "ok",
    schema_version: "a2a_governance_state_v1",
    generated_at: nowIso(),
    checked_at: nowIso(),
    source_files: {
      skill_registry_dir: safeText(input.paths?.skillRegistryDir),
      skill_library_dir: safeText(input.paths?.skillLibraryDir),
      mcp_policy_path: safeText(input.paths?.mcpPolicyPath),
      audit_path: safeText(input.paths?.auditPath),
    },
    paths: input.paths ?? {},
    skills: {
      registry_path:
        safeText(input.skillRegistry?.registry_path) ||
        safeText(input.paths?.skillRegistryDir),
      skill_count: skills.length,
      active_count: skills.filter((item) => item.status === "active").length,
      draft_count: skills.filter((item) => item.status === "draft").length,
      disabled_count: skills.filter((item) =>
        ["disabled", "paused", "archived"].includes(item.status),
      ).length,
      items: skills,
    },
    skill_library: {
      library_path: safeText(input.paths?.skillLibraryDir),
      item_count: input.skillLibraryItems?.length ?? 0,
      registered_count:
        input.skillLibraryItems?.filter((item) => item.registered_skill_id)
          .length ?? 0,
      unregistered_count:
        input.skillLibraryItems?.filter((item) => !item.registered_skill_id)
          .length ?? 0,
      items: input.skillLibraryItems ?? [],
    },
    marketplace: {
      template_count: marketplaceItems.length,
      read_count: marketplaceItems.filter((item) => item.read_only).length,
      write_count: marketplaceItems.filter((item) => !item.read_only).length,
      confirmation_count: marketplaceItems.filter(
        (item) => item.requires_human_confirmation,
      ).length,
      categories: uniqueSorted(marketplaceItems.map((item) => item.category)),
      items: marketplaceItems,
    },
    mcp: {
      policy_path:
        safeText(input.mcpPolicy?.policy_path) ||
        safeText(input.paths?.mcpPolicyPath),
      tool_count: mcpItems.length,
      read_count: mcpItems.filter((item) => item.read_only).length,
      write_count: mcpItems.filter((item) => !item.read_only).length,
      confirmation_count: mcpItems.filter(
        (item) => item.requires_human_confirmation,
      ).length,
      high_risk_count: mcpItems.filter((item) =>
        ["high", "destructive"].includes(item.risk_level),
      ).length,
      items: mcpItems,
    },
    tool_registry: {
      schema: safeText(input.toolRegistry?.schema) || TOOL_REGISTRY_SCHEMA,
      status: safeText(input.toolRegistry?.status) || "ok",
      error: safeText(input.toolRegistry?.error),
      tool_count: registryItems.length,
      read_only_count: registryItems.filter((item) => item.read_only).length,
      write_count: registryItems.filter((item) => !item.read_only).length,
      confirmation_count: registryItems.filter(
        (item) => item.requires_confirmation,
      ).length,
      high_risk_count: registryItems.filter((item) =>
        ["high", "destructive"].includes(item.risk_level),
      ).length,
      groups: uniqueSorted(registryItems.map((item) => item.group)),
      risk_levels: uniqueSorted(registryItems.map((item) => item.risk_level)),
      data_sources: uniqueSorted(
        registryItems.flatMap((item) => item.data_sources),
      ),
      agents: uniqueSorted(
        registryItems.flatMap((item) => item.visible_agents),
      ),
      policy_missing_count: registryItems.filter(
        (item) => item.mcp_policy_status === "policy_missing",
      ).length,
      policy_conflict_count: registryItems.filter(
        (item) => item.mcp_policy_status === "policy_conflict",
      ).length,
      items: registryItems,
    },
    policy_validation: {
      status:
        policyFailCount > 0 ? "fail" : policyWarnCount > 0 ? "warn" : "ok",
      ok_count: policyValidationItems.filter((item) => item.status === "ok")
        .length,
      warn_count: policyWarnCount,
      fail_count: policyFailCount,
      items: policyValidationItems,
    },
    audit_events: input.auditEvents ?? [],
    agent_reach:
      input.agentReach ?? {
        status: "unavailable",
        available: false,
        command: "agent-reach",
        checked_at: nowIso(),
        install_command:
          "python3 -m pip install --user agent-reach && agent-reach doctor --json",
        summary: {
          status: "fail",
          channel_count: 0,
          available_count: 0,
          warning_count: 0,
          unavailable_count: 0,
          public_ready_count: 0,
          login_required_count: 0,
          channels: [],
        },
        error: "未检测 Agent-Reach。",
      },
  };
}

async function loadSkillDetails(
  paths: GovernancePaths,
  registry: JsonRecord,
): Promise<SkillRegistryItem[]> {
  const registryItems = Object.values(safeRecord(registry.skills));
  const detailed = await Promise.all(
    registryItems.map(async (registryItem) => {
      const summary = normalizeSkillRegistryItem(safeRecord(registryItem));
      const recordPath =
        summary.path || skillPath(paths.skillRegistryDir, summary.skill_id);
      const record = await readJson<JsonRecord>(recordPath, {});
      const skill = safeRecord(record.skill);
      const detailedItem = normalizeSkillRegistryItem({
        ...summary,
        ...skill,
        path: recordPath,
        tool_count:
          asTextArray(skill.tool_allowlist ?? summary.tool_allowlist).length ||
          summary.tool_count,
      });
      const sourcePath = resolveWorkspacePath(
        paths,
        safeText(detailedItem.source_skill_path),
      );
      const sourceExists = sourcePath
        ? detailedItem.source_type === "skill_directory"
          ? (await pathExists(sourcePath)) &&
            (await fileExists(path.join(sourcePath, "SKILL.md")))
          : await fileExists(sourcePath)
        : false;
      const managedDir = resolveManagedSkillDir(
        paths,
        safeText(detailedItem.managed_skill_dir),
      );
      const managedSourceAvailable = managedDir
        ? await fileExists(path.join(managedDir, "SKILL.md"))
        : false;
      return {
        ...detailedItem,
        source_exists: sourceExists,
        source_status: sourcePath
          ? sourceExists
            ? "ok"
            : "source_missing"
          : "unknown",
        managed_source_available: managedSourceAvailable,
      };
    }),
  );
  return detailed;
}

async function loadSkillLibraryItems(
  paths: GovernancePaths,
  skills: SkillRegistryItem[],
): Promise<SkillLibraryItem[]> {
  let entries: Array<{ isDirectory(): boolean; name: string }>;
  try {
    entries = await readdir(paths.skillLibraryDir, { withFileTypes: true });
  } catch {
    return [];
  }

  const bySourcePath = new Map<string, SkillRegistryItem>();
  for (const skill of skills) {
    const sourcePath = safeText(skill.source_skill_path);
    if (sourcePath) bySourcePath.set(sourcePath, skill);
  }

  const items = await Promise.all(
    entries
      .filter((entry) => entry.isDirectory())
      .map(async (entry): Promise<SkillLibraryItem | null> => {
        const skillDir = path.join(paths.skillLibraryDir, entry.name);
        const skillFile = path.join(skillDir, "SKILL.md");
        try {
          const [content, fileStat] = await Promise.all([
            readFile(skillFile, "utf8"),
            stat(skillFile),
          ]);
          const sourcePath = relativeToWorkspace(paths.workspaceDir, skillDir);
          const skillFilePath = relativeToWorkspace(
            paths.workspaceDir,
            skillFile,
          );
          const registered = bySourcePath.get(sourcePath);
          return {
            folder_name: entry.name,
            name: titleFromMarkdown(content, entry.name),
            candidate_skill_id: stableSkillId(entry.name),
            source_path: sourcePath,
            skill_file_path: skillFilePath,
            registered_skill_id: registered?.skill_id ?? "",
            registered_status: registered?.status ?? "unregistered",
            managed_skill_dir: registered?.managed_skill_dir ?? "",
            updated_at: fileStat.mtime.toISOString(),
          };
        } catch {
          return null;
        }
      }),
  );

  return items
    .filter((item): item is SkillLibraryItem => Boolean(item))
    .sort((left, right) => left.source_path.localeCompare(right.source_path));
}

async function loadMcpPolicy(paths: GovernancePaths): Promise<JsonRecord> {
  const policy = await readJson<JsonRecord>(paths.mcpPolicyPath, {});
  const tools = {
    ...Object.fromEntries(
      Object.entries(DEFAULT_MCP_TOOL_POLICY).map(([toolName, rule]) => [
        toolName,
        { ...rule },
      ]),
    ),
    ...safeRecord(policy.tools),
  };
  const nextPolicy = {
    schema: MCP_POLICY_SCHEMA,
    policy_path: paths.mcpPolicyPath,
    ...policy,
    tools,
  };
  await writeJson(paths.mcpPolicyPath, nextPolicy);
  return nextPolicy;
}

async function loadMarketplaceTemplates(
  paths: GovernancePaths,
): Promise<MarketplaceTemplateItem[]> {
  const templateDir = path.join(paths.dataDir, "mcp_marketplace", "templates");
  let files: string[];
  try {
    files = await readdir(templateDir);
  } catch {
    return [];
  }
  const items = await Promise.all(
    files
      .filter((file) => file.endsWith(".json"))
      .map(async (file) => {
        const templatePath = path.join(templateDir, file);
        const raw = await readJson<JsonRecord>(templatePath, {});
        return normalizeMarketplaceTemplate(raw, templatePath);
      }),
  );
  return items.filter((item) => item.name);
}

async function loadToolRegistry(paths: GovernancePaths): Promise<JsonRecord> {
  const script = [
    "import json",
    "from src.a2a_ecommerce_demo.agent_tool_registry import export_tool_registry_payload",
    "print(json.dumps(export_tool_registry_payload(), ensure_ascii=False))",
  ].join("; ");
  const candidates = Array.from(
    new Set(
      [
        safeText(process.env.A2A_PYTHON_BIN),
        path.join(paths.workspaceDir, ".venv", "bin", "python"),
        path.join(paths.workspaceDir, ".venv", "Scripts", "python.exe"),
        "python3",
        "python",
      ].filter(Boolean),
    ),
  );
  let lastError = "";
  for (const pythonBin of candidates) {
    try {
      const { stdout } = await execFileAsync(pythonBin, ["-c", script], {
        cwd: paths.workspaceDir,
        env: { ...process.env, A2A_DATA_DIR: paths.dataDir },
        maxBuffer: 2 * 1024 * 1024,
      });
      return JSON.parse(stdout) as JsonRecord;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
  }
  return {
    schema: TOOL_REGISTRY_SCHEMA,
    status: "unavailable",
    error: lastError || "未找到用于导出工具注册表的 Python 运行时。",
    tools: {},
    agents: {},
  };
}

async function loadRecentAuditEvents(
  paths: GovernancePaths,
): Promise<GovernanceAuditEvent[]> {
  let content = "";
  try {
    content = await readFile(paths.auditPath, "utf8");
  } catch {
    return [];
  }
  return content
    .split(/\r?\n/)
    .filter(Boolean)
    .slice(-200)
    .map((line) => {
      try {
        return safeRecord(JSON.parse(line));
      } catch {
        return null;
      }
    })
    .filter((event): event is JsonRecord => Boolean(event))
    .filter((event) => {
      const type = safeText(event.event_type);
      return (
        type.startsWith("agent_skill_") ||
        type.startsWith("mcp_") ||
        type.startsWith("external_memory_") ||
        type.startsWith("platform_lab_")
      );
    })
    .slice(-30)
    .reverse()
    .map((event) => {
      const metadata = safeRecord(event.metadata);
      return {
        event_type: safeText(event.event_type),
        actor: safeText(event.actor),
        summary: safeText(event.summary),
        created_at: safeText(event.created_at) || safeText(event.timestamp),
        thread_id: safeText(event.thread_id) || safeText(metadata.thread_id),
        task_id: safeText(event.task_id) || safeText(metadata.task_id),
        agent_id: safeText(event.agent_id) || safeText(metadata.agent_id),
        risk_level:
          asTextArray(event.risks)[0] || safeText(metadata.risk_level),
        tool_name: safeText(event.tool_name) || safeText(metadata.tool_name),
        skill_id: safeText(metadata.skill_id) || safeText(event.task_id),
      };
    });
}

export type GovernanceState = ReturnType<typeof summarizeGovernanceState>;

export async function loadGovernanceState(paths = resolveGovernancePaths()) {
  const registryPath = path.join(paths.skillRegistryDir, "registry.json");
  const skillRegistry = await readJson<JsonRecord>(registryPath, {
    schema: REGISTRY_SCHEMA,
    registry_path: registryPath,
    skills: {},
  });
  const skillItems = await loadSkillDetails(paths, skillRegistry);
  const [
    skillLibraryItems,
    marketplaceTemplates,
    mcpPolicy,
    auditEvents,
    agentReach,
  ] =
    await Promise.all([
      loadSkillLibraryItems(paths, skillItems),
      loadMarketplaceTemplates(paths),
      loadMcpPolicy(paths),
      loadRecentAuditEvents(paths),
      checkAgentReachStatus(),
    ]);
  const toolRegistry = await loadToolRegistry(paths);
  return summarizeGovernanceState({
    skillRegistry,
    skillItems,
    skillLibraryItems,
    marketplaceTemplates,
    mcpPolicy,
    toolRegistry,
    auditEvents,
    agentReach,
    paths,
  });
}

async function saveSkillRecord(paths: GovernancePaths, record: JsonRecord) {
  const skill = safeRecord(record.skill);
  const skillId = safeText(skill.skill_id);
  if (!skillId) throw new Error("缺少 skill_id");
  const recordPath = skillPath(paths.skillRegistryDir, skillId);
  await writeJson(recordPath, record);

  const registryPath = path.join(paths.skillRegistryDir, "registry.json");
  const registry = await readJson<JsonRecord>(registryPath, {
    schema: REGISTRY_SCHEMA,
    skills: {},
  });
  const skills = safeRecord(registry.skills);
  skills[skillId] = {
    skill_id: skillId,
    name: safeText(skill.name),
    status: safeText(skill.status),
    version: safeNumber(skill.version),
    source_wiki_path: safeText(skill.source_wiki_path),
    source_type: safeText(skill.source_type),
    source_skill_path: safeText(skill.source_skill_path),
    managed_skill_dir: safeText(skill.managed_skill_dir),
    asset_count: safeNumber(skill.asset_count),
    tool_count: asTextArray(skill.tool_allowlist).length,
    updated_at: safeText(skill.updated_at),
    path: recordPath,
  };
  await writeJson(registryPath, {
    schema: REGISTRY_SCHEMA,
    registry_path: registryPath,
    updated_at: nowIso(),
    skills,
  });
  return recordPath;
}

async function realpathIfExists(targetPath: string) {
  try {
    return await realpath(targetPath);
  } catch {
    return path.resolve(targetPath);
  }
}

async function resolveSourcePath(sourcePath: string, paths: GovernancePaths) {
  const rawPath = sourcePath.trim();
  if (!rawPath) throw new Error("缺少 sourcePath");
  if (rawPath.includes("\0")) throw new Error("sourcePath 包含无效字符");
  const candidate = path.isAbsolute(rawPath)
    ? rawPath
    : path.join(paths.workspaceDir, rawPath);
  const resolvedCandidate = await realpath(candidate);
  const allowedRoots = [
    paths.wikiDir,
    paths.skillLibraryDir,
    path.join(paths.skillRegistryDir, "uploads"),
  ];
  const resolvedRoots = await Promise.all(allowedRoots.map(realpathIfExists));
  if (
    !resolvedRoots.some((root) => pathIsAtOrInside(root, resolvedCandidate))
  ) {
    throw new Error(
      "sourcePath 必须位于允许导入技能的目录内：wiki、skills 或治理上传目录",
    );
  }
  const base = path.basename(resolvedCandidate).toLowerCase();
  if (
    base === ".env" ||
    base === "config.py" ||
    base.includes("secret") ||
    base.includes("credential") ||
    base.startsWith("_tmp") ||
    base.startsWith("tmp_") ||
    [".zip", ".pyc", ".pyo"].includes(path.extname(base))
  ) {
    throw new Error(`拒绝导入不安全的技能源文件：${base}`);
  }
  return path.resolve(candidate);
}

async function sourceIsReadableMarkdown(sourcePath: string) {
  const file = await stat(sourcePath);
  if (!file.isFile()) throw new Error("sourcePath 必须指向 Markdown 文件");
  if (file.size > 1024 * 1024)
    throw new Error("sourcePath 指向的 Markdown 文件过大");
  const base = path.basename(sourcePath).toLowerCase();
  if (!base.endsWith(".md"))
    throw new Error("只能导入 Markdown 文件或 SKILL.md");
  if (base === ".env" || base.includes("secret"))
    throw new Error("拒绝导入疑似密钥文件");
}

type SkillSourceSnapshot = {
  source_type: "markdown_file" | "skill_file" | "skill_directory";
  source_root_path: string;
  source_skill_path: string;
  content: string;
  metadata?: JsonRecord;
};

const SKILL_IMPORT_SKIP_DIRS = new Set([
  ".git",
  ".hg",
  ".next",
  ".venv",
  "__pycache__",
  "build",
  "data",
  "dist",
  "node_modules",
  "output",
]);

function pathIsAtOrInside(parent: string, candidate: string) {
  const relative = path.relative(path.resolve(parent), path.resolve(candidate));
  return (
    relative === "" ||
    (Boolean(relative) &&
      !relative.startsWith("..") &&
      !path.isAbsolute(relative))
  );
}

function pathIsInside(parent: string, candidate: string) {
  const relative = path.relative(path.resolve(parent), path.resolve(candidate));
  return (
    Boolean(relative) &&
    !relative.startsWith("..") &&
    !path.isAbsolute(relative)
  );
}

function shouldSkipSkillImportEntry(entryName: string, isDirectory: boolean) {
  const lower = entryName.toLowerCase();
  if (isDirectory) return SKILL_IMPORT_SKIP_DIRS.has(lower);
  return (
    lower === ".ds_store" ||
    lower === ".env" ||
    lower === "config.py" ||
    lower.endsWith(".zip") ||
    lower.endsWith(".pyc") ||
    lower.endsWith(".pyo") ||
    lower.startsWith("_tmp") ||
    lower.startsWith("tmp_") ||
    lower.includes("secret") ||
    lower.includes("credential")
  );
}

async function readSkillSource(
  sourcePath: string,
): Promise<SkillSourceSnapshot> {
  const file = await stat(sourcePath);
  if (file.isDirectory()) {
    const skillFilePath = path.join(sourcePath, "SKILL.md");
    await sourceIsReadableMarkdown(skillFilePath);
    return {
      source_type: "skill_directory",
      source_root_path: sourcePath,
      source_skill_path: skillFilePath,
      content: await readFile(skillFilePath, "utf8"),
      metadata: safeRecord(
        await readJson<JsonRecord>(
          path.join(sourcePath, "skill.registry.json"),
          {},
        ),
      ),
    };
  }

  await sourceIsReadableMarkdown(sourcePath);
  const base = path.basename(sourcePath).toLowerCase();
  return {
    source_type: base === "skill.md" ? "skill_file" : "markdown_file",
    source_root_path: path.dirname(sourcePath),
    source_skill_path: sourcePath,
    content: await readFile(sourcePath, "utf8"),
  };
}

async function copySkillDirectory(sourceDir: string, targetDir: string) {
  const resolvedSource = path.resolve(sourceDir);
  const resolvedTarget = path.resolve(targetDir);
  if (resolvedSource === resolvedTarget) return 0;
  if (pathIsAtOrInside(resolvedSource, resolvedTarget)) {
    throw new Error(
      "Managed skill import directory cannot be nested inside sourcePath",
    );
  }

  await rm(resolvedTarget, { recursive: true, force: true });
  await mkdir(resolvedTarget, { recursive: true });
  let copiedFiles = 0;

  async function walk(currentSource: string, currentTarget: string) {
    const entries = await readdir(currentSource, { withFileTypes: true });
    for (const entry of entries) {
      if (shouldSkipSkillImportEntry(entry.name, entry.isDirectory())) continue;
      const nextSource = path.join(currentSource, entry.name);
      const nextTarget = path.join(currentTarget, entry.name);
      if (entry.isDirectory()) {
        await mkdir(nextTarget, { recursive: true });
        await walk(nextSource, nextTarget);
      } else if (entry.isFile()) {
        await mkdir(path.dirname(nextTarget), { recursive: true });
        await copyFile(nextSource, nextTarget);
        copiedFiles += 1;
      }
    }
  }

  await walk(resolvedSource, resolvedTarget);
  return copiedFiles;
}

export async function createDraftSkillFromSource({
  sourcePath,
  workspaceDir,
  wikiDir,
  skillRegistryDir,
  templateDir,
  skillId = "",
  name = "",
  scenarios = [],
  toolAllowlist = [],
  outputSchema = [],
  createdBy = "frontend",
}: {
  sourcePath: string;
  workspaceDir: string;
  wikiDir: string;
  skillRegistryDir: string;
  templateDir: string;
  skillId?: string;
  name?: string;
  scenarios?: string[];
  toolAllowlist?: string[];
  outputSchema?: string[];
  createdBy?: string;
}) {
  const paths: GovernancePaths = {
    workspaceDir,
    dataDir: path.join(workspaceDir, "data"),
    wikiDir,
    skillLibraryDir: path.join(workspaceDir, "skills"),
    skillRegistryDir,
    templateDir,
    mcpPolicyPath: path.join(workspaceDir, "data", "mcp", "tool_policy.json"),
    auditPath: path.join(workspaceDir, "data", "audit", "events.jsonl"),
  };
  const resolvedSource = await resolveSourcePath(sourcePath, paths);
  const source = await readSkillSource(resolvedSource);
  const content = source.content;
  const metadata = safeRecord(source.metadata);
  const metadataSkillId = safeText(metadata.skill_id);
  const metadataName = safeText(metadata.name);
  const metadataScenarios = asTextArray(metadata.scenarios);
  const metadataTools = asTextArray(metadata.tool_allowlist);
  const metadataOutputSchema = asTextArray(metadata.output_schema);
  const title = titleFromMarkdown(
    content,
    name || metadataName || path.basename(source.source_skill_path, ".md"),
  );
  const normalizedSkillId = slugify(
    skillId || metadataSkillId || stableSkillId(title),
    "agent-skill",
  );
  const sourceInsideWiki = pathIsAtOrInside(
    paths.wikiDir,
    source.source_skill_path,
  );
  const importedWikiPath = sourceInsideWiki
    ? source.source_skill_path
    : path.join(paths.wikiDir, "skills", "imported", `${normalizedSkillId}.md`);
  if (!sourceInsideWiki) {
    await mkdir(path.dirname(importedWikiPath), { recursive: true });
    await writeFile(
      importedWikiPath,
      [
        `# ${name || metadataName || title}`,
        "",
        `Imported from: ${
          source.source_type === "markdown_file"
            ? source.source_skill_path
            : source.source_root_path
        }`,
        "",
        content.trim(),
        "",
      ].join("\n"),
      "utf8",
    );
  }

  const managedSkillDirPath =
    source.source_type === "markdown_file"
      ? ""
      : path.join(paths.skillRegistryDir, "imports", normalizedSkillId);
  const assetCount = managedSkillDirPath
    ? await copySkillDirectory(source.source_root_path, managedSkillDirPath)
    : 0;
  const relativeWikiPath = `wiki/${path.relative(paths.wikiDir, importedWikiPath).split(path.sep).join("/")}`;
  const requestedTools = toolAllowlist.length
    ? toolAllowlist
    : metadataTools.length
      ? metadataTools
      : ["summarize_business_data", "query_fact_layer", "query_lightrag"];
  const preview = buildSkillPermissionPreview(requestedTools);
  const existingRecord = await readJson<JsonRecord>(
    skillPath(paths.skillRegistryDir, normalizedSkillId),
    {},
  );
  const existingSkill = safeRecord(existingRecord.skill);
  const existingVersions = safeArray(existingRecord.versions).map(safeRecord);
  const isUpdate = safeText(existingSkill.skill_id) === normalizedSkillId;
  const savedAt = nowIso();
  const skill = {
    skill_id: normalizedSkillId,
    name: name || metadataName || title,
    role: name || metadataName || title,
    goal: `复用 Skill《${title}》中的业务规则、口径和执行边界。`,
    status: "draft",
    version: isUpdate ? safeNumber(existingSkill.version) + 1 : 0,
    source_wiki_path: relativeWikiPath,
    source_type: source.source_type,
    source_skill_path: relativeToWorkspace(
      workspaceDir,
      source.source_type === "markdown_file"
        ? source.source_skill_path
        : source.source_root_path,
    ),
    managed_skill_dir: managedSkillDirPath
      ? relativeToWorkspace(workspaceDir, managedSkillDirPath)
      : "",
    asset_count: assetCount,
    scenarios: scenarios.length
      ? scenarios
      : metadataScenarios.length
        ? metadataScenarios
        : ["经营分析", "辅助决策"],
    tool_allowlist: preview.approved_tools,
    output_schema: outputSchema.length
      ? outputSchema
      : metadataOutputSchema.length
        ? metadataOutputSchema
        : DEFAULT_OUTPUT_SCHEMA,
    permission_preview: preview,
    created_by: safeText(existingSkill.created_by) || createdBy,
    created_at: safeText(existingSkill.created_at) || savedAt,
    updated_by: createdBy,
    updated_at: savedAt,
  };
  const record = {
    schema: SKILL_SCHEMA,
    skill,
    versions: isUpdate ? [...existingVersions, existingSkill] : [],
    wiki_content: content,
  };
  const registryPath = await saveSkillRecord(paths, record);
  await appendGovernanceAudit(
    paths,
    isUpdate ? "agent_skill_updated" : "agent_skill_imported",
    {
      actor: createdBy,
      summary: `${isUpdate ? "Updated" : "Imported"} draft agent skill: ${skill.name}`,
      risks: preview.risks,
      metadata: {
        skill_id: normalizedSkillId,
        source_path: relativeToWorkspace(workspaceDir, resolvedSource),
        source_type: source.source_type,
        source_wiki_path: relativeWikiPath,
        managed_skill_dir: skill.managed_skill_dir,
        asset_count: assetCount,
        blocked_tools: preview.blocked_tools,
        previous_version: isUpdate ? safeNumber(existingSkill.version) : null,
      },
    },
  );
  return {
    status: "draft",
    registry_path: registryPath,
    source_wiki_path: relativeWikiPath,
    skill,
  };
}

export async function setSkillStatus({
  paths,
  skillId,
  status,
  changedBy = "frontend",
}: {
  paths: GovernancePaths;
  skillId: string;
  status: string;
  changedBy?: string;
}) {
  const normalized = status.trim().toLowerCase();
  if (!VALID_SKILL_STATUSES.has(normalized))
    throw new Error(`技能状态无效：${status}`);
  const recordPath = skillPath(paths.skillRegistryDir, skillId);
  const record = await readJson<JsonRecord>(recordPath, {});
  const skill = safeRecord(record.skill);
  if (!safeText(skill.skill_id)) throw new Error(`未知技能：${skillId}`);
  skill.status = normalized;
  skill.status_changed_by = changedBy;
  skill.status_changed_at = nowIso();
  skill.updated_at = nowIso();
  record.skill = skill;
  const savedPath = await saveSkillRecord(paths, record);

  const activeTemplatePath = templatePath(paths.templateDir, skillId);
  if (normalized === "active") {
    await writeJson(
      activeTemplatePath,
      buildPromptTemplate(skill, safeText(record.wiki_content)),
    );
  } else {
    const template = await readJson<JsonRecord>(activeTemplatePath, {});
    if (Object.keys(template).length > 0) {
      template.status = normalized;
      template.status_changed_at = nowIso();
      await writeJson(activeTemplatePath, template);
    }
  }
  await appendGovernanceAudit(paths, "agent_skill_status_changed", {
    actor: changedBy,
    summary: `Changed agent skill status to ${normalized}: ${safeText(skill.name) || skillId}`,
    metadata: {
      skill_id: skillId,
      status: normalized,
      version: safeNumber(skill.version),
    },
  });
  return {
    status: "success",
    registry_path: savedPath,
    template_path: activeTemplatePath,
    skill,
  };
}

export async function rollbackSkillVersion({
  paths,
  skillId,
  targetVersion,
  changedBy = "frontend",
}: {
  paths: GovernancePaths;
  skillId: string;
  targetVersion: number;
  changedBy?: string;
}) {
  const recordPath = skillPath(paths.skillRegistryDir, skillId);
  const record = await readJson<JsonRecord>(recordPath, {});
  const versions = safeArray(record.versions).map(safeRecord);
  const target = versions.find(
    (version) => safeNumber(version.version) === targetVersion,
  );
  if (!target) throw new Error(`未找到 ${skillId} 的版本 ${targetVersion}`);
  const current = safeRecord(record.skill);
  target.status = "active";
  target.version = safeNumber(current.version) + 1;
  target.previous_version = targetVersion;
  target.rolled_back_by = changedBy;
  target.rolled_back_at = nowIso();
  target.updated_at = nowIso();
  record.skill = target;
  record.versions = [...versions, target];
  const savedPath = await saveSkillRecord(paths, record);
  const activeTemplatePath = templatePath(paths.templateDir, skillId);
  await writeJson(
    activeTemplatePath,
    buildPromptTemplate(target, safeText(record.wiki_content)),
  );
  await appendGovernanceAudit(paths, "agent_skill_rolled_back", {
    actor: changedBy,
    summary: `Rolled back agent skill to version ${targetVersion}: ${safeText(target.name) || skillId}`,
    metadata: {
      skill_id: skillId,
      target_version: targetVersion,
      new_version: safeNumber(target.version),
    },
  });
  return {
    status: "success",
    registry_path: savedPath,
    template_path: activeTemplatePath,
    skill: target,
  };
}

function resolveManagedSkillDir(
  paths: GovernancePaths,
  managedSkillDir: string,
) {
  const rawPath = safeText(managedSkillDir);
  if (!rawPath) return "";
  const candidate = path.isAbsolute(rawPath)
    ? rawPath
    : path.join(paths.workspaceDir, rawPath);
  const importsDir = path.join(paths.skillRegistryDir, "imports");
  return pathIsInside(importsDir, candidate) ? candidate : "";
}

export async function deleteSkillRegistration({
  paths,
  skillId,
  deleteManagedFiles = true,
  changedBy = "frontend",
}: {
  paths: GovernancePaths;
  skillId: string;
  deleteManagedFiles?: boolean;
  changedBy?: string;
}) {
  const normalizedSkillId = slugify(skillId, "agent-skill");
  if (!normalizedSkillId) throw new Error("缺少 skillId");
  const recordPath = skillPath(paths.skillRegistryDir, normalizedSkillId);
  const record = await readJson<JsonRecord>(recordPath, {});
  const skill = safeRecord(record.skill);
  if (!safeText(skill.skill_id))
    throw new Error(`未知技能：${normalizedSkillId}`);

  const activeTemplatePath = templatePath(paths.templateDir, normalizedSkillId);
  const managedSkillDir = resolveManagedSkillDir(
    paths,
    safeText(skill.managed_skill_dir),
  );
  const registryPath = path.join(paths.skillRegistryDir, "registry.json");
  const registry = await readJson<JsonRecord>(registryPath, {
    schema: REGISTRY_SCHEMA,
    skills: {},
  });
  const skills = safeRecord(registry.skills);
  delete skills[normalizedSkillId];

  await rm(recordPath, { force: true });
  await rm(activeTemplatePath, { force: true });
  if (deleteManagedFiles && managedSkillDir) {
    await rm(managedSkillDir, { recursive: true, force: true });
  }
  await writeJson(registryPath, {
    schema: REGISTRY_SCHEMA,
    registry_path: registryPath,
    updated_at: nowIso(),
    skills,
  });
  await appendGovernanceAudit(paths, "agent_skill_deleted", {
    actor: changedBy,
    summary: `删除智能体技能注册项：${safeText(skill.name) || normalizedSkillId}`,
    metadata: {
      skill_id: normalizedSkillId,
      version: safeNumber(skill.version),
      managed_skill_dir: safeText(skill.managed_skill_dir),
      managed_files_deleted: Boolean(deleteManagedFiles && managedSkillDir),
    },
  });

  return {
    status: "success",
    skill_id: normalizedSkillId,
    registry_path: registryPath,
    record_path: recordPath,
    template_path: activeTemplatePath,
    managed_skill_dir: managedSkillDir,
    managed_files_deleted: Boolean(deleteManagedFiles && managedSkillDir),
  };
}

function resolveRestoreSkillSourceDir(
  paths: GovernancePaths,
  skill: JsonRecord,
) {
  const sourcePath = resolveWorkspacePath(
    paths,
    safeText(skill.source_skill_path),
  );
  if (sourcePath && pathIsAtOrInside(paths.skillLibraryDir, sourcePath)) {
    return sourcePath;
  }
  return path.join(
    paths.skillLibraryDir,
    slugify(safeText(skill.skill_id), "agent-skill"),
  );
}

export async function restoreSkillSourceFromManagedCopy({
  paths,
  skillId,
  changedBy = "frontend",
}: {
  paths: GovernancePaths;
  skillId: string;
  changedBy?: string;
}) {
  const normalizedSkillId = slugify(skillId, "agent-skill");
  if (!normalizedSkillId) throw new Error("缺少 skillId");
  const recordPath = skillPath(paths.skillRegistryDir, normalizedSkillId);
  const record = await readJson<JsonRecord>(recordPath, {});
  const skill = safeRecord(record.skill);
  if (!safeText(skill.skill_id))
    throw new Error(`未知技能：${normalizedSkillId}`);

  const managedSkillDir = resolveManagedSkillDir(
    paths,
    safeText(skill.managed_skill_dir),
  );
  if (
    !managedSkillDir ||
    !(await fileExists(path.join(managedSkillDir, "SKILL.md")))
  ) {
    throw new Error(`未找到 ${normalizedSkillId} 的受管副本`);
  }

  const restoreTargetDir = resolveRestoreSkillSourceDir(paths, skill);
  if (await pathExists(restoreTargetDir)) {
    throw new Error(
      `源路径已存在：${relativeToWorkspace(paths.workspaceDir, restoreTargetDir)}`,
    );
  }

  const copiedFiles = await copySkillDirectory(
    managedSkillDir,
    restoreTargetDir,
  );
  skill.source_type = "skill_directory";
  skill.source_skill_path = relativeToWorkspace(
    paths.workspaceDir,
    restoreTargetDir,
  );
  skill.managed_skill_dir = relativeToWorkspace(
    paths.workspaceDir,
    managedSkillDir,
  );
  skill.asset_count = copiedFiles;
  skill.updated_by = changedBy;
  skill.updated_at = nowIso();
  record.skill = skill;

  const savedPath = await saveSkillRecord(paths, record);
  await appendGovernanceAudit(paths, "agent_skill_source_restored", {
    actor: changedBy,
    summary: `已从受管副本恢复智能体技能源文件夹：${safeText(skill.name) || normalizedSkillId}`,
    metadata: {
      skill_id: normalizedSkillId,
      source_skill_path: safeText(skill.source_skill_path),
      managed_skill_dir: safeText(skill.managed_skill_dir),
      copied_files: copiedFiles,
    },
  });

  return {
    status: "success",
    skill_id: normalizedSkillId,
    registry_path: savedPath,
    record_path: recordPath,
    source_skill_path: safeText(skill.source_skill_path),
    managed_skill_dir: safeText(skill.managed_skill_dir),
    copied_files: copiedFiles,
    skill,
  };
}

export async function upsertMcpToolPolicy({
  policyPath,
  auditPath = "",
  toolName,
  description,
  action,
  readOnly,
  requiresHumanConfirmation,
  riskLevel,
  dataSources,
  allowedCallers,
  destructiveEffects,
}: {
  policyPath: string;
  auditPath?: string;
  toolName: string;
  description: string;
  action: string;
  readOnly: boolean;
  requiresHumanConfirmation: boolean;
  riskLevel: string;
  dataSources: string[];
  allowedCallers: string[];
  destructiveEffects: string[];
}) {
  const normalizedName = slugify(toolName, "mcp_tool");
  if (!normalizedName) throw new Error("缺少 toolName");
  const normalizedAction = (action || (readOnly ? "read" : "write"))
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_:-]+/g, "_")
    .slice(0, 80);
  if (!/^[a-z][a-z0-9_:-]{0,79}$/.test(normalizedAction)) {
    throw new Error("MCP 策略动作无效");
  }
  const writeLikeAction = WRITE_ACTION_MARKERS.some((marker) =>
    normalizedAction.includes(marker),
  );
  const normalizedRisk = RISK_LEVELS.includes(
    riskLevel as (typeof RISK_LEVELS)[number],
  )
    ? riskLevel
    : "";
  const nextReadOnly = writeLikeAction ? false : readOnly;
  const nextRequiresConfirmation =
    writeLikeAction || requiresHumanConfirmation || !nextReadOnly;
  const nextRiskLevel = writeLikeAction
    ? "high"
    : normalizedRisk || (nextReadOnly ? "low" : "high");
  const nextAllowedCallers = allowedCallers.filter((caller) =>
    KNOWN_MCP_ALLOWED_CALLERS.has(caller),
  );
  const existing = await readJson<JsonRecord>(policyPath, {
    schema: MCP_POLICY_SCHEMA,
    tools: {},
  });
  const tools = safeRecord(existing.tools);
  const tool = {
    description: description || normalizedName,
    action: normalizedAction,
    read_only: nextReadOnly,
    requires_human_confirmation: nextRequiresConfirmation,
    external_write_enabled: false,
    risk_level: nextRiskLevel,
    data_sources: dataSources
      .map((source) => source.trim())
      .filter((source) => /^[a-zA-Z0-9_.:-]{1,80}$/.test(source)),
    allowed_callers: nextAllowedCallers,
    destructive_effects: destructiveEffects,
  };
  tools[normalizedName] = tool;
  const policy = {
    schema: MCP_POLICY_SCHEMA,
    policy_path: policyPath,
    updated_at: nowIso(),
    tools,
  };
  await writeJson(policyPath, policy);
  if (auditPath) {
    const paths: GovernancePaths = {
      workspaceDir: path.resolve(policyPath, "..", "..", ".."),
      dataDir: path.resolve(policyPath, "..", ".."),
      wikiDir: path.resolve(policyPath, "..", "..", "..", "wiki"),
      skillLibraryDir: path.resolve(policyPath, "..", "..", "..", "skills"),
      skillRegistryDir: path.resolve(policyPath, "..", "..", "skill_registry"),
      templateDir: path.resolve(policyPath, "..", "..", "agent_templates"),
      mcpPolicyPath: policyPath,
      auditPath,
    };
    await appendGovernanceAudit(paths, "mcp_tool_policy_upserted", {
      actor: "frontend",
      summary: `更新系统连接规则：${normalizedName}`,
      risks: [tool.risk_level],
      metadata: {
        tool_name: normalizedName,
        action: tool.action,
        read_only: tool.read_only,
        requires_human_confirmation: tool.requires_human_confirmation,
        risk_level: tool.risk_level,
        data_sources: tool.data_sources,
      },
    });
  }
  return {
    status: "success",
    policy_path: policyPath,
    tool_name: normalizedName,
    tool,
  };
}
