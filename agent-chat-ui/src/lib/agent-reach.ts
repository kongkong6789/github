import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export type AgentReachChannelStatus = "ok" | "warn" | "off" | "error";

type AgentReachDoctorChannelRaw = {
  status?: unknown;
  name?: unknown;
  message?: unknown;
  tier?: unknown;
  backends?: unknown;
  active_backend?: unknown;
};

export type AgentReachChannelSummary = {
  id: string;
  name: string;
  status: AgentReachChannelStatus;
  message: string;
  tier: number;
  backends: string[];
  active_backend: string;
  access_scope: "public" | "login_or_key_required";
};

export type AgentReachDoctorSummary = {
  status: "ok" | "warn" | "fail";
  channel_count: number;
  available_count: number;
  warning_count: number;
  unavailable_count: number;
  public_ready_count: number;
  login_required_count: number;
  channels: AgentReachChannelSummary[];
};

export type AgentReachStatus = {
  status: "ok" | "warn" | "unavailable" | "error";
  available: boolean;
  command: string;
  checked_at: string;
  install_command: string;
  summary: AgentReachDoctorSummary;
  error: string;
};

type AgentReachRunner = (
  command: string,
  args: string[],
) => Promise<{ stdout: string; stderr?: string }>;

type AgentReachStatusOptions = {
  commandCandidates?: string[];
  runner?: AgentReachRunner;
  timeoutMs?: number;
};

const DEFAULT_INSTALL_COMMAND =
  "python3 -m pip install --user agent-reach && agent-reach doctor --json";

const CHANNEL_ORDER = [
  "web",
  "rss",
  "github",
  "youtube",
  "bilibili",
  "v2ex",
  "exa_search",
  "twitter",
  "xiaohongshu",
  "reddit",
  "linkedin",
  "xueqiu",
  "xiaoyuzhou",
];

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeNumber(value: unknown): number {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function safeArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map(safeText).filter(Boolean)
    : safeText(value)
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function normalizeStatus(value: unknown): AgentReachChannelStatus {
  const status = safeText(value).toLowerCase();
  if (status === "ok" || status === "warn" || status === "off") {
    return status;
  }
  return "error";
}

function emptySummary(): AgentReachDoctorSummary {
  return {
    status: "fail",
    channel_count: 0,
    available_count: 0,
    warning_count: 0,
    unavailable_count: 0,
    public_ready_count: 0,
    login_required_count: 0,
    channels: [],
  };
}

function channelSortIndex(id: string) {
  const index = CHANNEL_ORDER.indexOf(id);
  return index >= 0 ? index : CHANNEL_ORDER.length;
}

export function summarizeAgentReachDoctor(
  doctor: Record<string, AgentReachDoctorChannelRaw>,
): AgentReachDoctorSummary {
  const channels = Object.entries(doctor)
    .map(([id, raw]) => {
      const tier = safeNumber(raw?.tier);
      const status = normalizeStatus(raw?.status);
      return {
        id,
        name: safeText(raw?.name) || id,
        status,
        message: safeText(raw?.message),
        tier,
        backends: safeArray(raw?.backends),
        active_backend: safeText(raw?.active_backend),
        access_scope: tier === 0 ? "public" : "login_or_key_required",
      } satisfies AgentReachChannelSummary;
    })
    .sort((left, right) => {
      const byOrder = channelSortIndex(left.id) - channelSortIndex(right.id);
      return byOrder || left.id.localeCompare(right.id);
    });
  const availableCount = channels.filter(
    (channel) => channel.status === "ok",
  ).length;
  const warningCount = channels.filter(
    (channel) => channel.status === "warn",
  ).length;
  const unavailableCount = channels.filter((channel) =>
    ["off", "error"].includes(channel.status),
  ).length;
  return {
    status:
      channels.length === 0
        ? "fail"
        : unavailableCount > 0 || warningCount > 0
          ? "warn"
          : "ok",
    channel_count: channels.length,
    available_count: availableCount,
    warning_count: warningCount,
    unavailable_count: unavailableCount,
    public_ready_count: channels.filter(
      (channel) => channel.access_scope === "public" && channel.status === "ok",
    ).length,
    login_required_count: channels.filter(
      (channel) =>
        channel.access_scope === "login_or_key_required" &&
        channel.status !== "ok",
    ).length,
    channels,
  };
}

function defaultCommandCandidates() {
  return Array.from(
    new Set(
      [safeText(process.env.A2A_AGENT_REACH_BIN), "agent-reach"].filter(
        Boolean,
      ),
    ),
  );
}

function isMissingExecutable(error: unknown) {
  const code = (error as NodeJS.ErrnoException)?.code;
  return code === "ENOENT" || code === "ENOTDIR";
}

function scrubError(value: unknown) {
  return String(value instanceof Error ? value.message : value)
    .replace(/:\/\/[^/\s:@]+:[^@\s/]+@/g, "://***:***@")
    .replace(/(api[_-]?key|token|cookie|password|secret)=([^;\s]+)/gi, "$1=***")
    .slice(0, 500);
}

export async function checkAgentReachStatus({
  commandCandidates = defaultCommandCandidates(),
  runner,
  timeoutMs = 8000,
}: AgentReachStatusOptions = {}): Promise<AgentReachStatus> {
  const checkedAt = new Date().toISOString();
  const run: AgentReachRunner =
    runner ??
    (async (command, args) => {
      const { stdout, stderr } = await execFileAsync(command, args, {
        timeout: timeoutMs,
        maxBuffer: 1024 * 1024,
      });
      return { stdout, stderr };
    });
  const candidates = commandCandidates.length
    ? commandCandidates
    : ["agent-reach"];
  let lastError = "";

  for (const command of candidates) {
    try {
      const { stdout } = await run(command, ["doctor", "--json"]);
      const parsed = JSON.parse(stdout || "{}") as Record<
        string,
        AgentReachDoctorChannelRaw
      >;
      const summary = summarizeAgentReachDoctor(parsed);
      return {
        status: summary.status === "fail" ? "error" : summary.status,
        available: true,
        command,
        checked_at: checkedAt,
        install_command: DEFAULT_INSTALL_COMMAND,
        summary,
        error: "",
      };
    } catch (error) {
      lastError = scrubError(error);
      if (isMissingExecutable(error)) continue;
      return {
        status: "error",
        available: false,
        command,
        checked_at: checkedAt,
        install_command: DEFAULT_INSTALL_COMMAND,
        summary: emptySummary(),
        error:
          error instanceof SyntaxError
            ? "Agent-Reach doctor 没有返回可解析的 JSON。"
            : lastError,
      };
    }
  }

  return {
    status: "unavailable",
    available: false,
    command: candidates[0] || "agent-reach",
    checked_at: checkedAt,
    install_command: DEFAULT_INSTALL_COMMAND,
    summary: emptySummary(),
    error: lastError || "未找到 Agent-Reach CLI。",
  };
}
