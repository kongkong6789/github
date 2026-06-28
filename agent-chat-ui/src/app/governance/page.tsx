"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  FormEvent,
  InputHTMLAttributes,
  ReactNode,
  Suspense,
  useCallback,
  useEffect,
  useState,
} from "react";
import {
  ArrowLeft,
  Archive,
  BookOpenCheck,
  CheckCircle2,
  CircleAlert,
  Download,
  FilePlus2,
  FolderUp,
  Globe2,
  History,
  KeyRound,
  LoaderCircle,
  PauseCircle,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  ShieldAlert,
  SlidersHorizontal,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { WorkbenchShell } from "@/components/workbench/shell";
import { getWorkbenchGovernancePolicy } from "@/lib/workbench-client";
import { cn } from "@/lib/utils";

type SkillItem = {
  skill_id: string;
  name: string;
  status: string;
  version: number;
  source_wiki_path: string;
  source_type?: string;
  source_skill_path?: string;
  managed_skill_dir?: string;
  source_status?: string;
  source_exists?: boolean;
  managed_source_available?: boolean;
  asset_count?: number;
  tool_count: number;
  updated_at: string;
  scenarios: string[];
  tool_allowlist: string[];
  output_schema: string[];
};

type SkillLibraryItem = {
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

type McpItem = {
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

type MarketplaceTemplate = {
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

type SkillhubStatus = {
  status: string;
  available: boolean;
  command: string;
  workspace_dir: string;
  skill_library_dir: string;
  install_command: string;
  version?: string;
  error: string;
};

type SkillhubResult = {
  slug: string;
  name: string;
  description: string;
  version: string;
  source: string;
  homepage?: string;
  icon_url?: string;
  category?: string;
  categories?: string[];
  tags?: string[];
  downloads?: number;
  installs?: number;
  stars?: number;
  score?: number;
  updated_at?: number;
  requires_api_key?: boolean;
  owner_name?: string;
};

type SkillhubSearchData = {
  status: string;
  query: string;
  count: number;
  total?: number;
  limit: number;
  category?: string;
  source?: string;
  sort?: string;
  categories?: string[];
  sources?: string[];
  results: SkillhubResult[];
  warnings: string[];
};

type ToolRegistryItem = {
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

type AuditEvent = {
  event_type: string;
  actor: string;
  summary: string;
  created_at: string;
  risk_level: string;
  tool_name: string;
  skill_id: string;
};

type AgentReachChannel = {
  id: string;
  name: string;
  status: "ok" | "warn" | "off" | "error";
  message: string;
  tier: number;
  backends: string[];
  active_backend: string;
  access_scope: "public" | "login_or_key_required";
};

type AgentReachStatus = {
  status: "ok" | "warn" | "unavailable" | "error";
  available: boolean;
  command: string;
  checked_at: string;
  install_command: string;
  error: string;
  summary: {
    status: "ok" | "warn" | "fail";
    channel_count: number;
    available_count: number;
    warning_count: number;
    unavailable_count: number;
    public_ready_count: number;
    login_required_count: number;
    channels: AgentReachChannel[];
  };
};

type GovernanceData = {
  checked_at: string;
  skills: {
    skill_count: number;
    active_count: number;
    draft_count: number;
    disabled_count: number;
    items: SkillItem[];
  };
  skill_library: {
    library_path: string;
    item_count: number;
    registered_count: number;
    unregistered_count: number;
    items: SkillLibraryItem[];
  };
  marketplace: {
    template_count: number;
    read_count: number;
    write_count: number;
    confirmation_count: number;
    categories: string[];
    items: MarketplaceTemplate[];
  };
  mcp: {
    tool_count: number;
    read_count: number;
    write_count: number;
    confirmation_count: number;
    high_risk_count: number;
    items: McpItem[];
  };
  tool_registry: {
    status: string;
    error: string;
    tool_count: number;
    read_only_count: number;
    write_count: number;
    confirmation_count: number;
    high_risk_count: number;
    groups: string[];
    risk_levels: string[];
    data_sources: string[];
    agents: string[];
    policy_missing_count: number;
    policy_conflict_count: number;
    items: ToolRegistryItem[];
  };
  policy_validation: {
    status: "ok" | "warn" | "fail";
    ok_count: number;
    warn_count: number;
    fail_count: number;
    items: Array<{
      id: string;
      label: string;
      status: "ok" | "warn" | "fail";
      summary: string;
    }>;
  };
  audit_events: AuditEvent[];
  agent_reach?: AgentReachStatus;
};

type TabKey = "skills" | "marketplace" | "tools" | "mcp" | "audit";
type SkillPaneKey = "market" | "installed" | "registry";

type SkillFolderFile = File & { webkitRelativePath?: string };

function tabFromParam(value: string | null): TabKey {
  if (value === "mcp-api" || value === "mcp_api") return "mcp";
  if (
    value === "skills" ||
    value === "marketplace" ||
    value === "tools" ||
    value === "mcp" ||
    value === "audit"
  ) {
    return value;
  }
  return "skills";
}

const skillPaneTabs: Array<
  [SkillPaneKey, string, (data: GovernanceData | null) => number]
> = [
  ["market", "技能市场", () => 0],
  ["installed", "已安装", (data) => data?.skill_library.item_count ?? 0],
  ["registry", "已配置", (data) => data?.skills.skill_count ?? 0],
];

const skillhubSourceOptions = [
  ["all", "推荐"],
  ["skillhub", "SkillHub"],
  ["clawhub", "套件"],
] as const;

const skillhubSortOptions = [
  ["score", "综合评分"],
  ["downloads", "下载量"],
  ["updated", "最近更新"],
  ["installs", "安装量"],
] as const;

const directoryInputProps: InputHTMLAttributes<HTMLInputElement> & {
  webkitdirectory?: string;
  directory?: string;
} = {
  webkitdirectory: "",
  directory: "",
};

const skillStatusClass: Record<string, string> = {
  active: "border-emerald-200 bg-emerald-50 text-emerald-700",
  draft: "border-amber-200 bg-amber-50 text-amber-700",
  paused: "border-sky-200 bg-sky-50 text-sky-700",
  disabled: "border-gray-200 bg-gray-50 text-gray-600",
  archived: "border-rose-200 bg-rose-50 text-rose-700",
  source_missing: "border-amber-200 bg-amber-50 text-amber-700",
};

const riskClass: Record<string, string> = {
  low: "border-emerald-200 bg-emerald-50 text-emerald-700",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  high: "border-rose-200 bg-rose-50 text-rose-700",
  destructive: "border-red-300 bg-red-50 text-red-700",
  unknown: "border-gray-200 bg-gray-50 text-gray-600",
};

const statusLabel: Record<string, string> = {
  active: "启用",
  draft: "草稿",
  paused: "暂停",
  disabled: "禁用",
  archived: "归档",
  source_missing: "源缺失",
  ok: "正常",
  warn: "预警",
  fail: "失败",
  error: "异常",
  off: "未启用",
  unavailable: "未安装",
  not_required: "无需策略",
  missing: "缺失",
  conflict: "冲突",
  unknown: "未知",
};

const riskLabel: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  destructive: "破坏性",
  unknown: "未知",
};

function StatCard({
  title,
  value,
  subtitle,
  icon,
  tone = "muted",
}: {
  title: string;
  value: string | number;
  subtitle: string;
  icon: ReactNode;
  tone?: "ok" | "warn" | "bad" | "muted";
}) {
  return (
    <div
      className={cn(
        "rounded-md border p-4",
        tone === "ok" && "border-emerald-200 bg-emerald-50",
        tone === "warn" && "border-amber-200 bg-amber-50",
        tone === "bad" && "border-rose-200 bg-rose-50",
        tone === "muted" && "border-gray-200 bg-gray-50",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-gray-600">{title}</div>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-semibold text-gray-950">{value}</div>
      <div className="mt-1 text-xs text-gray-600">{subtitle}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium",
        skillStatusClass[status] ?? skillStatusClass.disabled,
      )}
    >
      {status === "active" ? (
        <CheckCircle2 className="size-3.5" />
      ) : status === "draft" ? (
        <CircleAlert className="size-3.5" />
      ) : status === "paused" ? (
        <PauseCircle className="size-3.5" />
      ) : (
        <XCircle className="size-3.5" />
      )}
      {statusLabel[status] ?? (status || "未知")}
    </span>
  );
}

function RiskBadge({ risk }: { risk: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium",
        riskClass[risk] ?? riskClass.unknown,
      )}
    >
      {risk === "high" ? (
        <ShieldAlert className="size-3.5" />
      ) : (
        <ShieldCheck className="size-3.5" />
      )}
      {riskLabel[risk] ?? (risk || "未知")}
    </span>
  );
}

function RegistryStatusBadge({ status }: { status: string }) {
  const tone =
    status === "ok"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "not_required"
        ? "border-gray-200 bg-gray-50 text-gray-600"
        : "border-amber-200 bg-amber-50 text-amber-700";
  return (
    <span
      className={cn("rounded border px-1.5 py-0.5 text-xs font-medium", tone)}
    >
      {statusLabel[status] ?? (status || "未知")}
    </span>
  );
}

function formatTime(value: string) {
  if (!value) return "-";
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function formatCompactNumber(value?: number) {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "0";
  return new Intl.NumberFormat("zh-CN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(numeric);
}

function formatDateFromTimestamp(value?: number) {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return "未知";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(numeric));
}

function splitList(value: string) {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function parseResponse(response: Response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.status === "error") {
    throw new Error(payload.error || `请求失败：${response.status}`);
  }
  return payload;
}

function GovernancePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const [data, setData] = useState<GovernanceData | null>(null);
  const [tab, setTab] = useState<TabKey>(() => tabFromParam(tabParam));
  const [skillPane, setSkillPane] = useState<SkillPaneKey>("market");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [rollbackVersion, setRollbackVersion] = useState<
    Record<string, string>
  >({});
  const [skillForm, setSkillForm] = useState({
    sourcePath: "",
    skillId: "",
    name: "",
    scenarios: "",
    toolAllowlist:
      "summarize_business_data, query_fact_layer, query_lightrag, read_wiki_page",
    outputSchema: "summary, evidence, data_gaps, risks, next_actions",
  });
  const [skillFolderFiles, setSkillFolderFiles] = useState<SkillFolderFile[]>(
    [],
  );
  const [folderInputKey, setFolderInputKey] = useState(0);
  const [mcpForm, setMcpForm] = useState({
    toolName: "",
    description: "",
    toolAction: "read",
    readOnly: true,
    requiresHumanConfirmation: false,
    riskLevel: "low",
    dataSources: "",
    allowedCallers: "agent_factory_agent",
    destructiveEffects: "",
  });
  const [toolFilters, setToolFilters] = useState({
    query: "",
    group: "all",
    risk: "all",
    agent: "all",
    dataSource: "all",
  });
  const [skillhubStatus, setSkillhubStatus] = useState<SkillhubStatus | null>(
    null,
  );
  const [skillhubQuery, setSkillhubQuery] = useState("");
  const [skillhubCategory, setSkillhubCategory] = useState("all");
  const [skillhubSource, setSkillhubSource] = useState("all");
  const [skillhubSort, setSkillhubSort] = useState("score");
  const [skillhubLimit, setSkillhubLimit] = useState("50");
  const [skillhubSearch, setSkillhubSearch] =
    useState<SkillhubSearchData | null>(null);

  async function load() {
    setLoading(true);
    try {
      setData((await getWorkbenchGovernancePolicy()) as GovernanceData);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const changeTab = useCallback(
    (nextTab: TabKey) => {
      setTab(nextTab);
      const params = new URLSearchParams(searchParams.toString());
      if (nextTab === "skills") {
        params.delete("tab");
      } else {
        params.set("tab", nextTab);
      }
      const query = params.toString();
      router.replace(query ? `/governance?${query}` : "/governance", {
        scroll: false,
      });
    },
    [router, searchParams],
  );

  useEffect(() => {
    setTab(tabFromParam(tabParam));
  }, [tabParam]);

  const loadSkillhubStatus = useCallback(async () => {
    try {
      setSkillhubStatus(
        (await parseResponse(await fetch("/api/skillhub"))) as SkillhubStatus,
      );
    } catch (error) {
      setSkillhubStatus({
        status: "unavailable",
        available: false,
        command: "skillhub",
        workspace_dir: "",
        skill_library_dir: "",
        install_command:
          "curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/install.sh | bash -s -- --cli-only",
        version: "",
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }, []);

  const loadSkillhubCatalog = useCallback(
    async (
      overrides: Partial<{
        query: string;
        category: string;
        source: string;
        sort: string;
        limit: string;
        silent: boolean;
      }> = {},
    ) => {
      setBusy("skillhub:search");
      try {
        const payload = (await parseResponse(
          await fetch("/api/skillhub", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              action: "catalog",
              query: overrides.query ?? skillhubQuery,
              category: overrides.category ?? skillhubCategory,
              source: overrides.source ?? skillhubSource,
              sort: overrides.sort ?? skillhubSort,
              limit: Number(overrides.limit ?? skillhubLimit),
            }),
          }),
        )) as SkillhubSearchData;
        setSkillhubSearch(payload);
        if (!overrides.silent) {
          setMessage(
            payload.results.length > 0
              ? `SkillHub 当前显示 ${payload.results.length} 个技能`
              : "SkillHub 没有找到匹配技能",
          );
        }
      } catch (error) {
        setMessage(error instanceof Error ? error.message : String(error));
      } finally {
        setBusy("");
      }
    },
    [
      skillhubCategory,
      skillhubLimit,
      skillhubQuery,
      skillhubSort,
      skillhubSource,
    ],
  );

  useEffect(() => {
    if (tab === "skills" && skillPane === "market") {
      if (!skillhubStatus) void loadSkillhubStatus();
      if (!skillhubSearch) void loadSkillhubCatalog({ silent: true });
    }
  }, [
    loadSkillhubCatalog,
    loadSkillhubStatus,
    skillPane,
    skillhubSearch,
    skillhubStatus,
    tab,
  ]);

  async function submitSkillhubSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await loadSkillhubCatalog();
  }

  async function installSkillhubResult(item: SkillhubResult) {
    setBusy(`skillhub:install:${item.slug}`);
    try {
      const payload = await parseResponse(
        await fetch("/api/skillhub", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            action: "install_skill",
            slug: item.slug,
            force: true,
          }),
        }),
      );
      await load();
      const skillId =
        payload?.draft?.skill?.skill_id || payload?.install?.slug || item.slug;
      setMessage(`${item.name || item.slug} 已安装并导入为草稿：${skillId}`);
      changeTab("skills");
      setSkillPane("installed");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy("");
    }
  }

  async function submitSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("skill");
    try {
      const commonPayload = {
        action: "import_skill",
        ...skillForm,
        scenarios: splitList(skillForm.scenarios),
        toolAllowlist: splitList(skillForm.toolAllowlist),
        outputSchema: splitList(skillForm.outputSchema),
      };
      if (skillFolderFiles.length > 0) {
        const formData = new FormData();
        formData.set("action", "import_skill");
        formData.set("sourcePath", skillForm.sourcePath);
        formData.set("skillId", skillForm.skillId);
        formData.set("name", skillForm.name);
        formData.set("scenarios", splitList(skillForm.scenarios).join(","));
        formData.set(
          "toolAllowlist",
          splitList(skillForm.toolAllowlist).join(","),
        );
        formData.set(
          "outputSchema",
          splitList(skillForm.outputSchema).join(","),
        );
        for (const [index, file] of skillFolderFiles.entries()) {
          const relativePath = file.webkitRelativePath || file.name;
          formData.append("skillFilePaths", relativePath);
          formData.append(
            "skillFiles",
            file,
            relativePath || `skill-file-${index}`,
          );
        }
        await parseResponse(
          await fetch("/api/governance", {
            method: "POST",
            body: formData,
          }),
        );
      } else {
        await parseResponse(
          await fetch("/api/governance", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(commonPayload),
          }),
        );
      }
      setMessage("技能草稿已导入/更新");
      setSkillForm((form) => ({
        ...form,
        sourcePath: "",
        skillId: "",
        name: "",
      }));
      setSkillFolderFiles([]);
      setFolderInputKey((key) => key + 1);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy("");
    }
  }

  async function submitMcp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("mcp");
    try {
      await parseResponse(
        await fetch("/api/governance", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            action: "upsert_mcp_policy",
            ...mcpForm,
            requiresHumanConfirmation:
              mcpForm.requiresHumanConfirmation || !mcpForm.readOnly,
            dataSources: splitList(mcpForm.dataSources),
            allowedCallers: splitList(mcpForm.allowedCallers),
            destructiveEffects: splitList(mcpForm.destructiveEffects),
          }),
        }),
      );
      setMessage("系统连接规则已保存");
      setMcpForm((form) => ({
        ...form,
        toolName: "",
        description: "",
        destructiveEffects: "",
      }));
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy("");
    }
  }

  async function changeSkillStatus(skillId: string, status: string) {
    setBusy(`${skillId}:${status}`);
    try {
      await parseResponse(
        await fetch("/api/governance", {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ action: "set_skill_status", skillId, status }),
        }),
      );
      setMessage(`${skillId} 已切换为 ${statusLabel[status] ?? status}`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy("");
    }
  }

  async function rollbackSkill(skillId: string) {
    const targetVersion = Number(rollbackVersion[skillId]);
    if (!Number.isFinite(targetVersion) || targetVersion <= 0) {
      setMessage("请输入要回滚的版本号");
      return;
    }
    setBusy(`${skillId}:rollback`);
    try {
      await parseResponse(
        await fetch("/api/governance", {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            action: "rollback_skill",
            skillId,
            targetVersion,
          }),
        }),
      );
      setMessage(`${skillId} 已回滚`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy("");
    }
  }

  function prepareSkillUpdate(skill: SkillItem) {
    setSkillForm({
      sourcePath: skill.source_skill_path || skill.source_wiki_path || "",
      skillId: skill.skill_id,
      name: skill.name || "",
      scenarios: skill.scenarios?.join(", ") || "",
      toolAllowlist: skill.tool_allowlist?.join(", ") || "",
      outputSchema: skill.output_schema?.join(", ") || "",
    });
    setSkillFolderFiles([]);
    setFolderInputKey((key) => key + 1);
    setMessage(`${skill.skill_id} 已填入导入表单`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function prepareSkillRebind(skill: SkillItem) {
    setSkillForm({
      sourcePath: "",
      skillId: skill.skill_id,
      name: skill.name || "",
      scenarios: skill.scenarios?.join(", ") || "",
      toolAllowlist: skill.tool_allowlist?.join(", ") || "",
      outputSchema: skill.output_schema?.join(", ") || "",
    });
    setSkillFolderFiles([]);
    setFolderInputKey((key) => key + 1);
    setMessage(
      `${skill.skill_id} 已填入导入表单，请选择新的技能文件夹或填写新路径`,
    );
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function restoreSkillSource(skill: SkillItem) {
    if (
      !window.confirm(
        `从受管副本恢复 ${skill.name || skill.skill_id} 到 skills/？现有同名文件夹不会被覆盖。`,
      )
    ) {
      return;
    }
    setBusy(`${skill.skill_id}:restore-source`);
    try {
      await parseResponse(
        await fetch("/api/governance", {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            action: "restore_skill_source",
            skillId: skill.skill_id,
          }),
        }),
      );
      setMessage(`${skill.skill_id} 已从受管副本恢复到 skills/`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy("");
    }
  }

  function prepareSkillLibraryImport(item: SkillLibraryItem) {
    setSkillForm((form) => ({
      ...form,
      sourcePath: item.source_path,
      skillId: item.registered_skill_id || item.candidate_skill_id,
      name: item.name || item.folder_name,
    }));
    setSkillFolderFiles([]);
    setFolderInputKey((key) => key + 1);
    setMessage(`${item.source_path} 已填入导入表单`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function prepareMarketplaceTemplate(item: MarketplaceTemplate) {
    setMcpForm({
      toolName: item.name,
      description: item.description,
      toolAction: item.read_only ? "read" : "write_external_tool",
      readOnly: item.read_only,
      requiresHumanConfirmation: item.requires_human_confirmation,
      riskLevel: item.risk_level || (item.read_only ? "low" : "high"),
      dataSources: item.data_sources.join(", "),
      allowedCallers: item.allowed_callers.join(", "),
      destructiveEffects: item.safety_contract.join(", "),
    });
    changeTab("mcp");
    setMessage(`${item.display_name || item.name} 已填入系统连接规则表单`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function deleteSkill(skill: SkillItem) {
    if (
      !window.confirm(
        `删除技能配置 ${skill.name || skill.skill_id}？这会删除配置记录、活跃模板和受管副本；原始 skills/ 文件夹不会被删除。`,
      )
    ) {
      return;
    }
    setBusy(`${skill.skill_id}:delete`);
    try {
      await parseResponse(
        await fetch("/api/governance", {
          method: "DELETE",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            skillId: skill.skill_id,
            deleteManagedFiles: true,
          }),
        }),
      );
      setMessage(`${skill.skill_id} 已删除`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy("");
    }
  }

  const skills = data?.skills.items ?? [];
  const skillLibrary = data?.skill_library;
  const skillLibraryItems = skillLibrary?.items ?? [];
  const marketplace = data?.marketplace;
  const marketplaceItems = marketplace?.items ?? [];
  const mcpTools = data?.mcp.items ?? [];
  const toolRegistry = data?.tool_registry;
  const registryTools = toolRegistry?.items ?? [];
  const agentReach = data?.agent_reach;
  const agentReachTone =
    !agentReach || !agentReach.available
      ? "warn"
      : agentReach.status === "ok"
        ? "ok"
        : "warn";
  const filteredRegistryTools = registryTools.filter((tool) => {
    const query = toolFilters.query.trim().toLowerCase();
    const matchesQuery =
      !query ||
      tool.tool_name.toLowerCase().includes(query) ||
      tool.description.toLowerCase().includes(query) ||
      tool.owner_module.toLowerCase().includes(query);
    return (
      matchesQuery &&
      (toolFilters.group === "all" || tool.group === toolFilters.group) &&
      (toolFilters.risk === "all" || tool.risk_level === toolFilters.risk) &&
      (toolFilters.agent === "all" ||
        tool.visible_agents.includes(toolFilters.agent)) &&
      (toolFilters.dataSource === "all" ||
        tool.data_sources.includes(toolFilters.dataSource))
    );
  });
  const auditEvents = data?.audit_events ?? [];
  const skillhubCategories = skillhubSearch?.categories ?? [];
  const skillhubCategoryOptions: Array<[string, string]> = [
    ["all", "全部"],
    ...skillhubCategories.map((category): [string, string] => [
      category,
      category,
    ]),
  ];

  return (
    <WorkbenchShell
      title="工具权限"
      description="管理技能市场、可用工具、系统连接、人工审批和审计记录。"
      actions={
        <>
          <Button
            type="button"
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
            onClick={load}
            disabled={loading}
          >
            <RefreshCw className={cn("size-4", loading && "animate-spin")} />
            刷新
          </Button>
          <Button
            asChild
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Link href="/logs">
              <History className="size-4" />
              问题排查
            </Link>
          </Button>
          <Button
            asChild
            variant="outline"
            className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          >
            <Link href="/data-health">
              <SlidersHorizontal className="size-4" />
              资料体检
            </Link>
          </Button>
          <Button
            asChild
            className="bg-blue-700 !text-white hover:bg-blue-800"
          >
            <Link href="/">
              <ArrowLeft className="size-4" />
              返回对话
            </Link>
          </Button>
        </>
      }
    >
      <div>
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-8">
          <StatCard
            title="技能"
            value={data?.skills.skill_count ?? 0}
            subtitle={`启用 ${data?.skills.active_count ?? 0} / 草稿 ${data?.skills.draft_count ?? 0}`}
            tone={(data?.skills.draft_count ?? 0) > 0 ? "warn" : "ok"}
            icon={<BookOpenCheck className="size-5" />}
          />
          <StatCard
            title="暂停/禁用"
            value={data?.skills.disabled_count ?? 0}
            subtitle="暂停 / 禁用 / 归档"
            icon={<PauseCircle className="size-5" />}
          />
          <StatCard
            title="工具清单"
            value={toolRegistry?.tool_count ?? 0}
            subtitle={`只读 ${toolRegistry?.read_only_count ?? 0} / 写入 ${toolRegistry?.write_count ?? 0}`}
            tone={(toolRegistry?.policy_missing_count ?? 0) > 0 ? "warn" : "ok"}
            icon={<KeyRound className="size-5" />}
          />
          <StatCard
            title="系统连接"
            value={data?.mcp.tool_count ?? 0}
            subtitle={`只读 ${data?.mcp.read_count ?? 0} / 写入 ${data?.mcp.write_count ?? 0}`}
            icon={<KeyRound className="size-5" />}
          />
          <StatCard
            title="互联网资料"
            value={
              agentReach?.available
                ? `${agentReach.summary.public_ready_count}/${agentReach.summary.channel_count}`
                : "未安装"
            }
            subtitle={
              agentReach?.available
                ? `可用 ${agentReach.summary.available_count} / 登录确认 ${agentReach.summary.login_required_count}`
                : "Agent-Reach 可选接入"
            }
            tone={agentReachTone}
            icon={<Globe2 className="size-5" />}
          />
          <StatCard
            title="模板市场"
            value={marketplace?.template_count ?? 0}
            subtitle={`只读 ${marketplace?.read_count ?? 0} / 确认 ${marketplace?.confirmation_count ?? 0}`}
            tone={(marketplace?.confirmation_count ?? 0) > 0 ? "warn" : "ok"}
            icon={<FolderUp className="size-5" />}
          />
          <StatCard
            title="人工确认"
            value={data?.mcp.confirmation_count ?? 0}
            subtitle="进入智能体收件箱"
            tone={(data?.mcp.confirmation_count ?? 0) > 0 ? "warn" : "ok"}
            icon={<ShieldCheck className="size-5" />}
          />
          <StatCard
            title="高风险"
            value={
              (toolRegistry?.high_risk_count ?? 0) +
              (data?.mcp.high_risk_count ?? 0)
            }
            subtitle={`工具 ${toolRegistry?.high_risk_count ?? 0} / 策略 ${data?.mcp.high_risk_count ?? 0}`}
            tone={
              (toolRegistry?.high_risk_count ?? 0) +
                (data?.mcp.high_risk_count ?? 0) >
              0
                ? "bad"
                : "ok"
            }
            icon={<ShieldAlert className="size-5" />}
          />
          <StatCard
            title="策略漂移"
            value={
              (toolRegistry?.policy_missing_count ?? 0) +
              (toolRegistry?.policy_conflict_count ?? 0)
            }
            subtitle={`缺失 ${toolRegistry?.policy_missing_count ?? 0} / 冲突 ${toolRegistry?.policy_conflict_count ?? 0}`}
            tone={
              (toolRegistry?.policy_missing_count ?? 0) +
                (toolRegistry?.policy_conflict_count ?? 0) >
              0
                ? "warn"
                : "ok"
            }
            icon={<ShieldAlert className="size-5" />}
          />
          <StatCard
            title="策略校验"
            value={
              statusLabel[data?.policy_validation?.status ?? ""] ?? "读取中"
            }
            subtitle={`正常 ${data?.policy_validation?.ok_count ?? 0} / 预警 ${data?.policy_validation?.warn_count ?? 0} / 失败 ${data?.policy_validation?.fail_count ?? 0}`}
            tone={
              data?.policy_validation?.status === "fail"
                ? "bad"
                : data?.policy_validation?.status === "warn"
                  ? "warn"
                  : "ok"
            }
            icon={<ShieldCheck className="size-5" />}
          />
          <StatCard
            title="审计"
            value={auditEvents.length}
            subtitle={
              data?.checked_at
                ? `检查 ${formatTime(data.checked_at)}`
                : "读取中"
            }
            icon={<History className="size-5" />}
          />
        </div>

        {message && (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {message}
          </div>
        )}

        <div className="mt-6 flex flex-wrap gap-2 border-b border-gray-200">
          {[
            ["skills", "技能管理"],
            ["marketplace", "模板市场"],
            ["tools", "工具清单"],
            ["mcp", "系统连接"],
            ["audit", "操作记录"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => changeTab(key as TabKey)}
              className={cn(
                "border-b-2 px-3 py-2 text-sm font-medium",
                tab === key
                  ? "border-blue-600 text-blue-700"
                  : "border-transparent text-gray-500 hover:text-gray-800",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "skills" && (
          <>
            <section className="mt-5">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold">技能管理</h2>
                  <div className="text-sm text-gray-500">
                    浏览 SkillHub、导入本地技能，并管理启停状态。
                  </div>
                </div>
                {skillPane === "market" && (
                  <form
                    onSubmit={submitSkillhubSearch}
                    className="flex w-full flex-wrap items-center gap-2 lg:w-auto"
                  >
                    <div className="relative min-w-[220px] flex-1 lg:w-80 lg:flex-none">
                      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-gray-400" />
                      <input
                        className="h-9 w-full rounded-md border border-gray-200 bg-gray-50 pr-3 pl-8 text-sm"
                        value={skillhubQuery}
                        onChange={(event) =>
                          setSkillhubQuery(event.currentTarget.value)
                        }
                        placeholder="搜索技能"
                      />
                    </div>
                    <Button
                      type="submit"
                      disabled={busy !== "" && busy !== "skillhub:search"}
                    >
                      {busy === "skillhub:search" ? (
                        <LoaderCircle className="size-4 animate-spin" />
                      ) : (
                        <Search className="size-4" />
                      )}
                      搜索
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                      disabled={busy !== ""}
                      onClick={() => setSkillPane("installed")}
                    >
                      <FilePlus2 className="size-4" />
                      添加技能
                    </Button>
                  </form>
                )}
              </div>

              <div className="mt-4 flex flex-wrap gap-2 border-b border-gray-200">
                {skillPaneTabs.map(([key, label, getCount]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setSkillPane(key)}
                    className={cn(
                      "flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium",
                      skillPane === key
                        ? "border-gray-950 text-gray-950"
                        : "border-transparent text-gray-500 hover:text-gray-800",
                    )}
                  >
                    {label}
                    {getCount(data) > 0 && (
                      <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
                        {getCount(data)}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </section>

            {skillPane === "market" && (
              <section className="mt-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2">
                    {skillhubSourceOptions.map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => {
                          setSkillhubSource(value);
                          void loadSkillhubCatalog({ source: value });
                        }}
                        className={cn(
                          "rounded-md px-3 py-1.5 text-sm",
                          skillhubSource === value
                            ? "border border-blue-200 bg-blue-50 text-blue-800"
                            : "border border-transparent bg-gray-100 text-gray-700 hover:bg-gray-200",
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
                    <a
                      className="inline-flex items-center gap-1 hover:text-gray-900"
                      href="https://skillhub.cn/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      skillhub.cn
                    </a>
                    <select
                      className="h-9 rounded-md border border-gray-300 bg-white px-2 text-sm text-gray-700"
                      value={skillhubSort}
                      onChange={(event) => {
                        const value = event.currentTarget.value;
                        setSkillhubSort(value);
                        void loadSkillhubCatalog({ sort: value });
                      }}
                      aria-label="SkillHub 排序"
                    >
                      {skillhubSortOptions.map(([value, label]) => (
                        <option
                          key={value}
                          value={value}
                        >
                          {label}
                        </option>
                      ))}
                    </select>
                    <select
                      className="h-9 rounded-md border border-gray-300 bg-white px-2 text-sm text-gray-700"
                      value={skillhubLimit}
                      onChange={(event) => {
                        const value = event.currentTarget.value;
                        setSkillhubLimit(value);
                        void loadSkillhubCatalog({ limit: value });
                      }}
                      aria-label="SkillHub 显示数量"
                    >
                      <option value="20">20 个</option>
                      <option value="50">50 个</option>
                      <option value="100">100 个</option>
                    </select>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={busy !== ""}
                      onClick={loadSkillhubStatus}
                    >
                      <RefreshCw className="size-3.5" />
                      检查 CLI
                    </Button>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {skillhubCategoryOptions.map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => {
                        setSkillhubCategory(value);
                        void loadSkillhubCatalog({ category: value });
                      }}
                      className={cn(
                        "rounded-md px-3 py-1.5 text-sm",
                        skillhubCategory === value
                          ? "border border-blue-200 bg-blue-50 text-blue-800"
                          : "border border-transparent bg-gray-100 text-gray-700 hover:bg-gray-200",
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500">
                  <div>
                    {skillhubSearch
                      ? `找到 ${skillhubSearch.count} 个技能，当前显示 ${skillhubSearch.results.length} 个`
                      : "正在准备技能市场"}
                  </div>
                  <div className="font-mono">
                    {skillhubStatus?.available
                      ? `${skillhubStatus.command} -> ${skillhubStatus.skill_library_dir || "skills/"}`
                      : "CLI 仅安装时需要"}
                  </div>
                </div>

                {skillhubStatus?.available === false &&
                  skillhubStatus.error && (
                    <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      {skillhubStatus.error}
                    </div>
                  )}

                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                  {skillhubSearch?.results.map((item) => {
                    const installing = busy === `skillhub:install:${item.slug}`;
                    const initial = (item.name || item.slug || "S")
                      .slice(0, 1)
                      .toUpperCase();
                    return (
                      <article
                        key={item.slug}
                        className="grid min-h-[150px] grid-cols-[auto_1fr_auto] gap-3 rounded-md border border-gray-200 p-3"
                      >
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-sm font-semibold text-slate-600">
                          {initial}
                        </div>
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-gray-950">
                            {item.name || item.slug}
                          </div>
                          <p className="mt-1 line-clamp-2 min-h-10 text-xs leading-5 text-gray-600">
                            {item.description || "-"}
                          </p>
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
                            <span>
                              {formatCompactNumber(item.downloads)} 下载
                            </span>
                            <span>{formatCompactNumber(item.stars)} 星标</span>
                            <span>
                              {formatCompactNumber(item.installs)} 安装
                            </span>
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-gray-500">
                            {(
                              item.categories?.slice(0, 2) ?? [
                                item.category || "未分类",
                              ]
                            ).map((category) => (
                              <span
                                key={category}
                                className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5"
                              >
                                {category}
                              </span>
                            ))}
                            <span>
                              更新 {formatDateFromTimestamp(item.updated_at)}
                            </span>
                          </div>
                        </div>
                        <Button
                          type="button"
                          size="icon"
                          variant="outline"
                          className="size-8 border-gray-200 bg-gray-50"
                          disabled={busy !== ""}
                          aria-label={`安装 ${item.name || item.slug}`}
                          title={`安装 ${item.name || item.slug}`}
                          onClick={() => installSkillhubResult(item)}
                        >
                          {installing ? (
                            <LoaderCircle className="size-4 animate-spin" />
                          ) : (
                            <Download className="size-4" />
                          )}
                        </Button>
                      </article>
                    );
                  })}
                </div>

                {busy === "skillhub:search" && !skillhubSearch && (
                  <div className="mt-8 text-center text-sm text-gray-500">
                    正在加载 SkillHub 技能市场
                  </div>
                )}
                {skillhubSearch && skillhubSearch.results.length === 0 && (
                  <div className="mt-8 text-center text-sm text-gray-500">
                    没有匹配的 SkillHub 技能
                  </div>
                )}
              </section>
            )}

            {skillPane === "installed" && (
              <>
                <section className="mt-5 rounded-md border border-gray-200 p-4">
                  <form onSubmit={submitSkill}>
                    <div className="mb-3 flex items-center gap-2">
                      <FilePlus2 className="size-4 text-gray-500" />
                      <h2 className="text-lg font-semibold">添加已有技能</h2>
                    </div>
                    <div className="grid gap-3 lg:grid-cols-6">
                      <label className="lg:col-span-3">
                        <span className="text-xs font-medium text-gray-600">
                          Markdown / SKILL.md / 技能文件夹路径
                        </span>
                        <input
                          className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                          value={skillForm.sourcePath}
                          onChange={(event) =>
                            setSkillForm((form) => ({
                              ...form,
                              sourcePath: event.target.value,
                            }))
                          }
                          placeholder="/Users/seven/Desktop/xxx 或 /Users/seven/Desktop/xxx/SKILL.md"
                        />
                      </label>
                      <label className="lg:col-span-2">
                        <span className="text-xs font-medium text-gray-600">
                          上传技能文件夹
                        </span>
                        <input
                          key={folderInputKey}
                          type="file"
                          multiple
                          className="mt-1 block h-9 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                          onChange={(event) =>
                            setSkillFolderFiles(
                              Array.from(
                                event.currentTarget.files ?? [],
                              ) as SkillFolderFile[],
                            )
                          }
                          {...directoryInputProps}
                        />
                        {skillFolderFiles.length > 0 && (
                          <span className="mt-1 block text-xs text-gray-500">
                            已选择 {skillFolderFiles.length} 个文件
                          </span>
                        )}
                      </label>
                      <div className="flex items-end">
                        <Button
                          type="submit"
                          disabled={
                            busy === "skill" ||
                            (!skillForm.sourcePath &&
                              skillFolderFiles.length === 0)
                          }
                        >
                          {busy === "skill" ? (
                            <LoaderCircle className="size-4 animate-spin" />
                          ) : skillFolderFiles.length > 0 ? (
                            <FolderUp className="size-4" />
                          ) : (
                            <Upload className="size-4" />
                          )}
                          导入/更新
                        </Button>
                      </div>
                      <label>
                        <span className="text-xs font-medium text-gray-600">
                          技能 ID
                        </span>
                        <input
                          className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                          value={skillForm.skillId}
                          onChange={(event) =>
                            setSkillForm((form) => ({
                              ...form,
                              skillId: event.target.value,
                            }))
                          }
                          placeholder="可选"
                        />
                      </label>
                      <label>
                        <span className="text-xs font-medium text-gray-600">
                          名称
                        </span>
                        <input
                          className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                          value={skillForm.name}
                          onChange={(event) =>
                            setSkillForm((form) => ({
                              ...form,
                              name: event.target.value,
                            }))
                          }
                          placeholder="可选"
                        />
                      </label>
                      <label>
                        <span className="text-xs font-medium text-gray-600">
                          场景
                        </span>
                        <input
                          className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                          value={skillForm.scenarios}
                          onChange={(event) =>
                            setSkillForm((form) => ({
                              ...form,
                              scenarios: event.target.value,
                            }))
                          }
                          placeholder="分销, 线下"
                        />
                      </label>
                      <label className="lg:col-span-3">
                        <span className="text-xs font-medium text-gray-600">
                          工具白名单
                        </span>
                        <textarea
                          className="mt-1 min-h-20 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                          value={skillForm.toolAllowlist}
                          onChange={(event) =>
                            setSkillForm((form) => ({
                              ...form,
                              toolAllowlist: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label className="lg:col-span-3">
                        <span className="text-xs font-medium text-gray-600">
                          输出结构
                        </span>
                        <textarea
                          className="mt-1 min-h-20 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                          value={skillForm.outputSchema}
                          onChange={(event) =>
                            setSkillForm((form) => ({
                              ...form,
                              outputSchema: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </div>
                  </form>
                </section>

                <section className="mt-5">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h2 className="text-lg font-semibold">技能资源库</h2>
                      <div className="font-mono text-xs text-gray-500">
                        {skillLibrary?.library_path || "skills/"}
                      </div>
                    </div>
                    <div className="text-xs text-gray-500">
                      已登记 {skillLibrary?.registered_count ?? 0} / 未登记{" "}
                      {skillLibrary?.unregistered_count ?? 0}
                    </div>
                  </div>
                  <div className="overflow-x-auto rounded-md border border-gray-200">
                    <table className="w-full min-w-[920px] text-left text-sm">
                      <thead className="bg-gray-50 text-xs text-gray-500">
                        <tr>
                          <th className="px-3 py-2">文件夹</th>
                          <th className="px-3 py-2">技能</th>
                          <th className="px-3 py-2">配置状态</th>
                          <th className="px-3 py-2">受管副本</th>
                          <th className="px-3 py-2">操作</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {skillLibraryItems.map((item) => (
                          <tr key={item.source_path}>
                            <td className="px-3 py-2">
                              <div className="font-medium">
                                {item.folder_name}
                              </div>
                              <div className="font-mono text-xs text-gray-500">
                                {item.source_path}
                              </div>
                            </td>
                            <td className="px-3 py-2">
                              <div>{item.name}</div>
                              <div className="font-mono text-xs text-gray-500">
                                {item.skill_file_path}
                              </div>
                            </td>
                            <td className="px-3 py-2">
                              <StatusBadge status={item.registered_status} />
                              <div className="mt-1 font-mono text-xs text-gray-500">
                                {item.registered_skill_id ||
                                  item.candidate_skill_id}
                              </div>
                            </td>
                            <td className="max-w-[260px] truncate px-3 py-2 font-mono text-xs text-gray-500">
                              {item.managed_skill_dir || "-"}
                            </td>
                            <td className="px-3 py-2">
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={busy !== ""}
                                onClick={() => prepareSkillLibraryImport(item)}
                              >
                                <Upload className="size-3.5" />
                                {item.registered_skill_id ? "更新" : "导入"}
                              </Button>
                            </td>
                          </tr>
                        ))}
                        {skillLibraryItems.length === 0 && (
                          <tr>
                            <td
                              className="px-3 py-8 text-center text-sm text-gray-500"
                              colSpan={5}
                            >
                              skills/ 下暂无技能文件夹
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}

            {skillPane === "registry" && (
              <section className="mt-5">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <h2 className="text-lg font-semibold">已配置技能</h2>
                  <div className="text-xs text-gray-500">
                    {skills.length} 项
                  </div>
                </div>
                <div className="overflow-x-auto rounded-md border border-gray-200">
                  <table className="w-full min-w-[1280px] text-left text-sm">
                    <thead className="bg-gray-50 text-xs text-gray-500">
                      <tr>
                        <th className="px-3 py-2">技能</th>
                        <th className="px-3 py-2">状态</th>
                        <th className="px-3 py-2">版本</th>
                        <th className="px-3 py-2">场景</th>
                        <th className="px-3 py-2">工具</th>
                        <th className="px-3 py-2">来源</th>
                        <th className="px-3 py-2">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {skills.map((skill) => (
                        <tr key={skill.skill_id}>
                          <td className="px-3 py-2">
                            <div className="font-medium">
                              {skill.name || skill.skill_id}
                            </div>
                            <div className="font-mono text-xs text-gray-500">
                              {skill.skill_id}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <StatusBadge status={skill.status} />
                          </td>
                          <td className="px-3 py-2">{skill.version}</td>
                          <td className="max-w-[180px] px-3 py-2 text-gray-600">
                            <div className="line-clamp-2">
                              {skill.scenarios?.join(" / ") || "-"}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <div>
                              {skill.tool_allowlist?.length || skill.tool_count}
                            </div>
                            <div className="max-w-[240px] truncate font-mono text-xs text-gray-500">
                              {skill.tool_allowlist?.join(", ") || "-"}
                            </div>
                          </td>
                          <td className="max-w-[260px] px-3 py-2 text-xs text-gray-500">
                            <div className="font-mono">
                              {skill.source_type || "wiki"}
                              {skill.asset_count
                                ? ` · ${skill.asset_count} 个文件`
                                : ""}
                            </div>
                            <div className="truncate font-mono">
                              {skill.source_skill_path ||
                                skill.source_wiki_path ||
                                "-"}
                            </div>
                            {skill.source_status === "source_missing" && (
                              <div className="mt-1 inline-flex rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 font-sans text-[11px] font-medium text-amber-700">
                                源缺失
                              </div>
                            )}
                            {skill.managed_skill_dir && (
                              <div className="truncate font-mono text-gray-400">
                                {skill.managed_skill_dir}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={busy !== ""}
                                onClick={() => prepareSkillUpdate(skill)}
                              >
                                <Upload className="size-3.5" />
                                更新
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={
                                  busy !== "" || skill.status === "active"
                                }
                                onClick={() =>
                                  changeSkillStatus(skill.skill_id, "active")
                                }
                              >
                                启用
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={
                                  busy !== "" || skill.status === "paused"
                                }
                                onClick={() =>
                                  changeSkillStatus(skill.skill_id, "paused")
                                }
                              >
                                暂停
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={
                                  busy !== "" || skill.status === "disabled"
                                }
                                onClick={() =>
                                  changeSkillStatus(skill.skill_id, "disabled")
                                }
                              >
                                禁用
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={
                                  busy !== "" || skill.status === "archived"
                                }
                                onClick={() =>
                                  changeSkillStatus(skill.skill_id, "archived")
                                }
                              >
                                <Archive className="size-3.5" />
                                归档
                              </Button>
                              <input
                                className="h-8 w-16 rounded-md border border-gray-300 px-2 text-xs"
                                value={rollbackVersion[skill.skill_id] ?? ""}
                                onChange={(event) =>
                                  setRollbackVersion((values) => ({
                                    ...values,
                                    [skill.skill_id]: event.target.value,
                                  }))
                                }
                                placeholder="版本"
                              />
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={busy !== ""}
                                onClick={() => rollbackSkill(skill.skill_id)}
                              >
                                <RotateCcw className="size-3.5" />
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="border-rose-200 text-rose-700 hover:bg-rose-50"
                                disabled={busy !== ""}
                                onClick={() => deleteSkill(skill)}
                              >
                                <Trash2 className="size-3.5" />
                                删除注册
                              </Button>
                              {skill.source_status === "source_missing" && (
                                <>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    disabled={busy !== ""}
                                    onClick={() => prepareSkillRebind(skill)}
                                  >
                                    重新绑定
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    disabled={
                                      busy !== "" ||
                                      !skill.managed_source_available
                                    }
                                    onClick={() => restoreSkillSource(skill)}
                                  >
                                    <RefreshCw className="size-3.5" />
                                    恢复文件夹
                                  </Button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                      {skills.length === 0 && (
                        <tr>
                          <td
                            className="px-3 py-8 text-center text-sm text-gray-500"
                            colSpan={7}
                          >
                            暂无技能
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}

        {tab === "marketplace" && (
          <section className="mt-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-lg font-semibold">模板市场</h2>
                <div className="text-xs text-gray-500">
                  {marketplaceItems.length} 个模板 /{" "}
                  {marketplace?.categories.join(", ") || "-"}
                </div>
              </div>
            </div>
            <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
              {marketplaceItems.map((item) => (
                <article
                  key={item.name}
                  className="rounded-md border border-gray-200 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-semibold">
                        {item.display_name || item.name}
                      </div>
                      <div className="mt-1 font-mono text-xs text-gray-500">
                        {item.name} · {item.version || "0.0.0"}
                      </div>
                    </div>
                    <RiskBadge risk={item.risk_level} />
                  </div>
                  <p className="mt-3 line-clamp-3 text-sm text-gray-600">
                    {item.description}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <span
                      className={cn(
                        "rounded border px-1.5 py-0.5 text-xs",
                        item.read_only
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-amber-200 bg-amber-50 text-amber-700",
                      )}
                    >
                      {item.read_only ? "只读" : "写入"}
                    </span>
                    {item.requires_human_confirmation && (
                      <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
                        需要确认
                      </span>
                    )}
                    <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-xs text-gray-600">
                      {item.category}
                    </span>
                    <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-xs text-gray-600">
                      {item.execution_mode}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-gray-500">
                    <div>
                      <span className="font-medium text-gray-600">
                        调用方：
                      </span>
                      <span className="font-mono">
                        {item.allowed_callers.join(", ") || "-"}
                      </span>
                    </div>
                    <div>
                      <span className="font-medium text-gray-600">来源：</span>
                      <span className="font-mono">
                        {item.data_sources.join(", ") || "-"}
                      </span>
                    </div>
                    <div>
                      <span className="font-medium text-gray-600">入口：</span>
                      <span className="font-mono">
                        {item.entry_point || "-"}
                      </span>
                    </div>
                  </div>
                  {item.safety_contract.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {item.safety_contract.slice(0, 3).map((rule) => (
                        <span
                          key={rule}
                          className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700"
                        >
                          {rule}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={busy !== ""}
                      onClick={() => prepareMarketplaceTemplate(item)}
                    >
                      <Upload className="size-3.5" />
                      填入策略
                    </Button>
                    {item.source_url && (
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                      >
                        <a
                          href={item.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <BookOpenCheck className="size-3.5" />
                          来源
                        </a>
                      </Button>
                    )}
                  </div>
                </article>
              ))}
              {marketplaceItems.length === 0 && (
                <div className="rounded-md border border-gray-200 px-3 py-8 text-center text-sm text-gray-500">
                  暂无 marketplace 模板
                </div>
              )}
            </div>
          </section>
        )}

        {tab === "tools" && (
          <section className="mt-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-lg font-semibold">工具清单</h2>
                <div className="text-xs text-gray-500">
                  显示 {filteredRegistryTools.length} / {registryTools.length}{" "}
                  个工具
                  {toolRegistry?.status === "unavailable" && toolRegistry.error
                    ? ` · ${toolRegistry.error}`
                    : ""}
                </div>
              </div>
            </div>
            <div className="mb-3 grid gap-2 md:grid-cols-5">
              <input
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={toolFilters.query}
                onChange={(event) =>
                  setToolFilters((filters) => ({
                    ...filters,
                    query: event.target.value,
                  }))
                }
                placeholder="搜索工具或模块"
              />
              <select
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={toolFilters.group}
                onChange={(event) =>
                  setToolFilters((filters) => ({
                    ...filters,
                    group: event.target.value,
                  }))
                }
              >
                <option value="all">全部分组</option>
                {toolRegistry?.groups.map((group) => (
                  <option
                    key={group}
                    value={group}
                  >
                    {group}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={toolFilters.risk}
                onChange={(event) =>
                  setToolFilters((filters) => ({
                    ...filters,
                    risk: event.target.value,
                  }))
                }
              >
                <option value="all">全部风险</option>
                {toolRegistry?.risk_levels.map((risk) => (
                  <option
                    key={risk}
                    value={risk}
                  >
                    {risk}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={toolFilters.agent}
                onChange={(event) =>
                  setToolFilters((filters) => ({
                    ...filters,
                    agent: event.target.value,
                  }))
                }
              >
                <option value="all">全部智能体</option>
                {toolRegistry?.agents.map((agent) => (
                  <option
                    key={agent}
                    value={agent}
                  >
                    {agent}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                value={toolFilters.dataSource}
                onChange={(event) =>
                  setToolFilters((filters) => ({
                    ...filters,
                    dataSource: event.target.value,
                  }))
                }
              >
                <option value="all">全部来源</option>
                {toolRegistry?.data_sources.map((source) => (
                  <option
                    key={source}
                    value={source}
                  >
                    {source}
                  </option>
                ))}
              </select>
            </div>
            <div className="overflow-x-auto rounded-md border border-gray-200">
              <table className="w-full min-w-[1280px] text-left text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500">
                  <tr>
                    <th className="px-3 py-2">工具</th>
                    <th className="px-3 py-2">分组</th>
                    <th className="px-3 py-2">模式</th>
                    <th className="px-3 py-2">风险</th>
                    <th className="px-3 py-2">确认</th>
                    <th className="px-3 py-2">策略</th>
                    <th className="px-3 py-2">智能体</th>
                    <th className="px-3 py-2">来源</th>
                    <th className="px-3 py-2">模块 / 最近</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredRegistryTools.map((tool) => (
                    <tr key={tool.tool_name}>
                      <td className="px-3 py-2">
                        <div className="font-medium">{tool.tool_name}</div>
                        <div className="line-clamp-1 max-w-[320px] text-xs text-gray-500">
                          {tool.description}
                        </div>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {tool.group}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "rounded border px-1.5 py-0.5 text-xs",
                            tool.read_only
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : "border-amber-200 bg-amber-50 text-amber-700",
                          )}
                        >
                          {tool.read_only ? "只读" : "写入"}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <RiskBadge risk={tool.risk_level} />
                      </td>
                      <td className="px-3 py-2">
                        {tool.requires_confirmation ? (
                          <span className="text-amber-700">需要</span>
                        ) : (
                          <span className="text-emerald-700">不需要</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <RegistryStatusBadge status={tool.mcp_policy_status} />
                      </td>
                      <td className="max-w-[240px] truncate px-3 py-2 font-mono text-xs text-gray-500">
                        {tool.visible_agents.join(", ") || "-"}
                      </td>
                      <td className="max-w-[180px] truncate px-3 py-2 font-mono text-xs text-gray-500">
                        {tool.data_sources.join(", ") || "-"}
                      </td>
                      <td className="max-w-[240px] px-3 py-2 text-xs text-gray-500">
                        <div className="font-mono">{tool.owner_module}</div>
                        <div>
                          {tool.recent_call_risk
                            ? `最近 ${tool.recent_call_risk}`
                            : tool.availability_check}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filteredRegistryTools.length === 0 && (
                    <tr>
                      <td
                        className="px-3 py-8 text-center text-sm text-gray-500"
                        colSpan={9}
                      >
                        没有匹配当前筛选的工具
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {tab === "mcp" && (
          <>
            <section className="mt-5 rounded-md border border-gray-200 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Globe2 className="size-4 text-blue-600" />
                    <h2 className="text-lg font-semibold">
                      互联网公开资料能力
                    </h2>
                  </div>
                  <div className="mt-1 text-sm text-gray-500">
                    Agent-Reach 只作为外部公开资料读取和搜索层，不能发帖、评论、点赞、私信或写入外部账号。
                  </div>
                </div>
                <span
                  className={cn(
                    "rounded border px-2 py-1 text-xs font-medium",
                    agentReach?.available
                      ? agentReach.status === "ok"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-amber-200 bg-amber-50 text-amber-700"
                      : "border-amber-200 bg-amber-50 text-amber-700",
                  )}
                >
                  {statusLabel[agentReach?.status ?? "unavailable"] ??
                    "未安装"}
                </span>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">命令</div>
                  <div className="mt-1 truncate font-mono text-sm">
                    {agentReach?.command || "agent-reach"}
                  </div>
                </div>
                <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">公开渠道</div>
                  <div className="mt-1 text-sm font-semibold">
                    {agentReach?.summary.public_ready_count ?? 0}
                  </div>
                </div>
                <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">可用渠道</div>
                  <div className="mt-1 text-sm font-semibold">
                    {agentReach?.summary.available_count ?? 0} /{" "}
                    {agentReach?.summary.channel_count ?? 0}
                  </div>
                </div>
                <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
                  <div className="text-xs text-gray-500">登录态确认</div>
                  <div className="mt-1 text-sm font-semibold">
                    {agentReach?.summary.login_required_count ?? 0}
                  </div>
                </div>
              </div>

              {!agentReach?.available && (
                <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  未检测到 Agent-Reach。建议先在终端手动安装并运行体检：
                  <span className="ml-1 font-mono">
                    {agentReach?.install_command ||
                      "python3 -m pip install --user agent-reach && agent-reach doctor --json"}
                  </span>
                </div>
              )}

              {(agentReach?.summary.channels.length ?? 0) > 0 && (
                <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {agentReach?.summary.channels.slice(0, 9).map((channel) => (
                    <div
                      key={channel.id}
                      className="rounded-md border border-gray-200 p-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">
                            {channel.name}
                          </div>
                          <div className="mt-1 truncate text-xs text-gray-500">
                            {channel.active_backend ||
                              channel.backends.join(" / ") ||
                              channel.id}
                          </div>
                        </div>
                        <span
                          className={cn(
                            "shrink-0 rounded border px-1.5 py-0.5 text-xs",
                            channel.status === "ok" &&
                              "border-emerald-200 bg-emerald-50 text-emerald-700",
                            channel.status === "warn" &&
                              "border-amber-200 bg-amber-50 text-amber-700",
                            channel.status !== "ok" &&
                              channel.status !== "warn" &&
                              "border-gray-200 bg-gray-50 text-gray-600",
                          )}
                        >
                          {statusLabel[channel.status] ?? channel.status}
                        </span>
                      </div>
                      <div className="mt-2 line-clamp-2 text-xs text-gray-500">
                        {channel.access_scope === "public"
                          ? "公开资料"
                          : "需要登录态或密钥确认"}
                        {channel.message ? ` · ${channel.message}` : ""}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="mt-5 rounded-md border border-gray-200 p-4">
              <form onSubmit={submitMcp}>
                <div className="mb-3 flex items-center gap-2">
                  <KeyRound className="size-4 text-gray-500" />
                  <h2 className="text-lg font-semibold">添加系统连接规则</h2>
                </div>
                <div className="grid gap-3 lg:grid-cols-6">
                  <label>
                    <span className="text-xs font-medium text-gray-600">
                      工具名称
                    </span>
                    <input
                      className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                      value={mcpForm.toolName}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          toolName: event.target.value,
                        }))
                      }
                      placeholder="query_platform_sales"
                    />
                  </label>
                  <label className="lg:col-span-2">
                    <span className="text-xs font-medium text-gray-600">
                      描述
                    </span>
                    <input
                      className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                      value={mcpForm.description}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          description: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    <span className="text-xs font-medium text-gray-600">
                      动作
                    </span>
                    <input
                      className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                      value={mcpForm.toolAction}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          toolAction: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    <span className="text-xs font-medium text-gray-600">
                      风险
                    </span>
                    <select
                      className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                      value={mcpForm.riskLevel}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          riskLevel: event.target.value,
                        }))
                      }
                    >
                      <option value="low">低风险</option>
                      <option value="medium">中风险</option>
                      <option value="high">高风险</option>
                    </select>
                  </label>
                  <div className="flex items-end">
                    <Button
                      type="submit"
                      disabled={busy === "mcp" || !mcpForm.toolName}
                    >
                      {busy === "mcp" && (
                        <LoaderCircle className="size-4 animate-spin" />
                      )}
                      保存
                    </Button>
                  </div>
                  <label className="flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2">
                    <input
                      type="checkbox"
                      checked={mcpForm.readOnly}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          readOnly: event.target.checked,
                          requiresHumanConfirmation: event.target.checked
                            ? form.requiresHumanConfirmation
                            : true,
                          riskLevel: event.target.checked
                            ? form.riskLevel
                            : "high",
                        }))
                      }
                    />
                    <span className="text-sm">只读</span>
                  </label>
                  <label className="flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2">
                    <input
                      type="checkbox"
                      checked={
                        mcpForm.requiresHumanConfirmation || !mcpForm.readOnly
                      }
                      disabled={!mcpForm.readOnly}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          requiresHumanConfirmation: event.target.checked,
                        }))
                      }
                    />
                    <span className="text-sm">需要确认</span>
                  </label>
                  <label className="lg:col-span-2">
                    <span className="text-xs font-medium text-gray-600">
                      数据来源
                    </span>
                    <input
                      className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                      value={mcpForm.dataSources}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          dataSources: event.target.value,
                        }))
                      }
                      placeholder="erp, duckdb"
                    />
                  </label>
                  <label className="lg:col-span-2">
                    <span className="text-xs font-medium text-gray-600">
                      允许调用方
                    </span>
                    <input
                      className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                      value={mcpForm.allowedCallers}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          allowedCallers: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="lg:col-span-6">
                    <span className="text-xs font-medium text-gray-600">
                      破坏性影响
                    </span>
                    <input
                      className="mt-1 h-9 w-full rounded-md border border-gray-300 px-2 text-sm"
                      value={mcpForm.destructiveEffects}
                      onChange={(event) =>
                        setMcpForm((form) => ({
                          ...form,
                          destructiveEffects: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
              </form>
            </section>

            <section className="mt-5">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h2 className="text-lg font-semibold">系统连接规则</h2>
                <div className="text-xs text-gray-500">
                  {mcpTools.length} 个工具
                </div>
              </div>
              <div className="overflow-x-auto rounded-md border border-gray-200">
                <table className="w-full min-w-[1000px] text-left text-sm">
                  <thead className="bg-gray-50 text-xs text-gray-500">
                    <tr>
                      <th className="px-3 py-2">工具</th>
                      <th className="px-3 py-2">模式</th>
                      <th className="px-3 py-2">确认</th>
                      <th className="px-3 py-2">风险</th>
                      <th className="px-3 py-2">工具清单</th>
                      <th className="px-3 py-2">来源</th>
                      <th className="px-3 py-2">允许调用方</th>
                      <th className="px-3 py-2">影响</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {mcpTools.map((tool) => (
                      <tr key={tool.tool_name}>
                        <td className="px-3 py-2">
                          <div className="font-medium">{tool.tool_name}</div>
                          <div className="line-clamp-1 max-w-[260px] text-xs text-gray-500">
                            {tool.description}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={cn(
                              "rounded border px-1.5 py-0.5 text-xs",
                              tool.read_only
                                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                : "border-amber-200 bg-amber-50 text-amber-700",
                            )}
                          >
                            {tool.read_only ? "只读" : tool.action || "写入"}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          {tool.requires_human_confirmation ? (
                            <span className="text-amber-700">需要</span>
                          ) : (
                            <span className="text-emerald-700">不需要</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <RiskBadge risk={tool.risk_level} />
                        </td>
                        <td className="px-3 py-2">
                          <RegistryStatusBadge
                            status={tool.tool_registry_status || "unknown"}
                          />
                        </td>
                        <td className="max-w-[180px] truncate px-3 py-2 font-mono text-xs text-gray-500">
                          {tool.data_sources.join(", ") || "-"}
                        </td>
                        <td className="max-w-[220px] truncate px-3 py-2 font-mono text-xs text-gray-500">
                          {tool.allowed_callers.join(", ") || "-"}
                        </td>
                        <td className="max-w-[260px] truncate px-3 py-2 text-xs text-gray-500">
                          {tool.destructive_effects.join(" / ") || "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}

        {tab === "audit" && (
          <section className="mt-5">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">最近操作记录</h2>
              <div className="text-xs text-gray-500">
                {auditEvents.length} 条事件
              </div>
            </div>
            <div className="overflow-x-auto rounded-md border border-gray-200">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500">
                  <tr>
                    <th className="px-3 py-2">时间</th>
                    <th className="px-3 py-2">类型</th>
                    <th className="px-3 py-2">操作者</th>
                    <th className="px-3 py-2">目标</th>
                    <th className="px-3 py-2">风险</th>
                    <th className="px-3 py-2">摘要</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {auditEvents.map((event, index) => (
                    <tr
                      key={`${event.created_at}-${event.event_type}-${index}`}
                    >
                      <td className="px-3 py-2 whitespace-nowrap text-gray-500">
                        {formatTime(event.created_at)}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {event.event_type}
                      </td>
                      <td className="px-3 py-2">{event.actor || "-"}</td>
                      <td className="max-w-[220px] truncate px-3 py-2 font-mono text-xs text-gray-500">
                        {event.skill_id || event.tool_name || "-"}
                      </td>
                      <td className="px-3 py-2">
                        {event.risk_level ? (
                          <RiskBadge risk={event.risk_level} />
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="max-w-xl truncate px-3 py-2 text-gray-600">
                        {event.summary}
                      </td>
                    </tr>
                  ))}
                  {auditEvents.length === 0 && (
                    <tr>
                      <td
                        className="px-3 py-8 text-center text-sm text-gray-500"
                        colSpan={6}
                      >
                        暂无操作记录
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </WorkbenchShell>
  );
}

export default function GovernancePage() {
  return (
    <Suspense fallback={null}>
      <GovernancePageContent />
    </Suspense>
  );
}
