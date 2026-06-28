import { execFile } from "node:child_process";
import { access, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import {
  createDraftSkillFromSource,
  resolveGovernancePaths,
  type GovernancePaths,
} from "./governance";

export type SkillhubRunOptions = {
  cwd?: string;
  env?: NodeJS.ProcessEnv;
  timeout?: number;
  maxBuffer?: number;
};

export type SkillhubRunner = (
  command: string,
  args: string[],
  options?: SkillhubRunOptions,
) => Promise<{ stdout: string; stderr: string }>;

export type SkillhubSearchResult = {
  slug: string;
  name: string;
  description: string;
  version: string;
  source: string;
};

export type SkillhubCatalogSort =
  | "score"
  | "downloads"
  | "updated"
  | "installs";

export type SkillhubCatalogResult = SkillhubSearchResult & {
  homepage: string;
  icon_url: string;
  category: string;
  categories: string[];
  tags: string[];
  downloads: number;
  installs: number;
  stars: number;
  score: number;
  updated_at: number;
  requires_api_key: boolean;
  owner_name: string;
};

export type SkillhubJsonFetcher = (url: string) => Promise<unknown>;

const SKILLHUB_INSTALL_COMMAND =
  "curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/install.sh | bash -s -- --cli-only";
export const SKILLHUB_SEARCH_URL = "https://api.skillhub.cn/api/v1/search";
export const SKILLHUB_INDEX_URL =
  "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills.json";
const SKILLHUB_MAX_CATALOG_FETCH = 100;

const SKILLHUB_BOOTSTRAP_OPT_IN_ENV = "A2A_SKILLHUB_INSTALL_SHA256";

const execFileAsync = promisify(execFile);
const SKILLHUB_REF_PATTERN =
  /^(?:@[a-zA-Z0-9][a-zA-Z0-9_.-]*\/)?[a-zA-Z0-9][a-zA-Z0-9_.-]*(?:@[a-zA-Z0-9][a-zA-Z0-9_.+-]*)?$/;

function safeText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asTextArray(value: unknown) {
  return Array.isArray(value) ? value.map(safeText).filter(Boolean) : [];
}

function uniqueText(values: string[]) {
  return Array.from(
    new Set(values.map((value) => value.trim()).filter(Boolean)),
  );
}

function safeNumeric(value: unknown, fallback = 0) {
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return numeric;
  const text = safeText(value).toLowerCase();
  const compact = text.match(/^(\d+(?:\.\d+)?)\s*([km])$/);
  if (compact) {
    const amount = Number(compact[1]);
    const multiplier = compact[2] === "m" ? 1_000_000 : 1_000;
    return amount * multiplier;
  }
  return fallback;
}

function safeTimestamp(value: unknown) {
  const numeric = safeNumeric(value, 0);
  if (numeric > 0) return numeric;
  const parsed = Date.parse(safeText(value));
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeCatalogKey(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, "-");
}

function matchesCatalogCategory(
  item: SkillhubCatalogResult,
  categoryKey: string,
) {
  if (!categoryKey || categoryKey === "all") return true;
  return item.categories.some(
    (category) => normalizeCatalogKey(category) === categoryKey,
  );
}

function asSearchResult(value: unknown): SkillhubSearchResult {
  const record = asRecord(value);
  return {
    slug: safeText(record.slug),
    name: safeText(record.displayName) || safeText(record.name),
    description:
      safeText(record.summary) ||
      safeText(record.description_zh) ||
      safeText(record.description),
    version: safeText(record.version),
    source: safeText(record.source) || "community",
  };
}

function asCatalogResult(value: unknown): SkillhubCatalogResult {
  const record = asRecord(value);
  const labels = asRecord(record.labels);
  const category = safeText(record.category);
  const categories = uniqueText([...asTextArray(record.categories), category]);
  return {
    ...asSearchResult(record),
    homepage: safeText(record.homepage),
    icon_url: safeText(record.icon_url),
    category: categories[0] || category || "uncategorized",
    categories,
    tags: asTextArray(record.tags),
    downloads: safeNumeric(record.downloads),
    installs: safeNumeric(record.installs),
    stars: safeNumeric(record.stars),
    score: safeNumeric(record.score),
    updated_at: safeTimestamp(record.updatedAt || record.updated_at),
    requires_api_key:
      record.requires_api_key === true ||
      safeText(labels.requires_api_key).toLowerCase() === "true",
    owner_name: safeText(record.owner_name),
  };
}

function normalizeCatalogSort(value: string): SkillhubCatalogSort {
  if (
    value === "score" ||
    value === "downloads" ||
    value === "updated" ||
    value === "installs"
  ) {
    return value;
  }
  return "score";
}

function catalogSortValue(
  item: SkillhubCatalogResult,
  sort: SkillhubCatalogSort,
) {
  if (sort === "downloads") return item.downloads;
  if (sort === "updated") return item.updated_at;
  if (sort === "installs") return item.installs;
  return item.score;
}

function sortCatalogResults(
  items: SkillhubCatalogResult[],
  sort: SkillhubCatalogSort,
) {
  return [...items].sort((left, right) => {
    const valueDelta =
      catalogSortValue(right, sort) - catalogSortValue(left, sort);
    if (valueDelta !== 0) return valueDelta;
    return (left.name || left.slug).localeCompare(
      right.name || right.slug,
      "zh-CN",
    );
  });
}

function matchesCatalogSource(item: SkillhubCatalogResult, sourceKey: string) {
  const itemSourceKey = normalizeCatalogKey(item.source);
  return (
    !sourceKey ||
    sourceKey === "all" ||
    (sourceKey === "skillhub" &&
      (itemSourceKey === "community" || itemSourceKey === "clawhub")) ||
    itemSourceKey === sourceKey
  );
}

function filterCatalogResults(
  items: SkillhubCatalogResult[],
  category: string,
  source: string,
) {
  const categoryKey = normalizeCatalogKey(category);
  const sourceKey = normalizeCatalogKey(source);
  return items.filter((item) => {
    const matchesCategory = matchesCatalogCategory(item, categoryKey);
    const matchesSource = matchesCatalogSource(item, sourceKey);
    return matchesCategory && matchesSource;
  });
}

function safeInstallCommandHint(env: NodeJS.ProcessEnv = process.env): string {
  const sha256 = (env[SKILLHUB_BOOTSTRAP_OPT_IN_ENV] || "").trim();
  if (!sha256) {
    return `远程自动安装已禁用。请手动安装 SkillHub CLI 或设置环境变量 A2A_SKILLHUB_INSTALL_SHA256 以启用受保护的远程引导安装。`;
  }
  return `${SKILLHUB_INSTALL_COMMAND} (SHA256 校验已启用)`;
}

function skillhubEnv(env: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  return {
    ...env,
    SKILLHUB_SKIP_SELF_UPGRADE: "1",
    SKILLHUB_SKIP_WORKSPACE_SKILLS: "1",
  };
}

function defaultSkillhubCandidates(env: NodeJS.ProcessEnv = process.env) {
  return Array.from(
    new Set(
      [
        safeText(env.A2A_SKILLHUB_BIN),
        path.join(os.homedir(), ".local", "bin", "skillhub"),
        "skillhub",
      ].filter(Boolean),
    ),
  );
}

export const defaultSkillhubRunner: SkillhubRunner = async (
  command,
  args,
  options,
) => {
  const { stdout, stderr } = await execFileAsync(command, args, {
    cwd: options?.cwd,
    env: options?.env,
    timeout: options?.timeout ?? 20000,
    maxBuffer: options?.maxBuffer ?? 2 * 1024 * 1024,
  });
  return {
    stdout: String(stdout),
    stderr: String(stderr),
  };
};

function parseJsonPayload(stdout: string) {
  const trimmed = stdout.trim();
  if (!trimmed) return {};
  try {
    return JSON.parse(trimmed) as Record<string, unknown>;
  } catch (error) {
    throw new Error(
      `SkillHub 返回了非 JSON 输出：${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

function normalizeLimit(limit: number) {
  const numeric = Number(limit);
  if (!Number.isFinite(numeric)) return 20;
  return Math.min(100, Math.max(1, Math.round(numeric)));
}

export async function defaultSkillhubJsonFetcher(url: string) {
  const response = await fetch(url, {
    headers: { accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`SkillHub 目录请求失败：HTTP ${response.status}`);
  }
  return response.json() as Promise<unknown>;
}

export async function listSkillhubCatalog({
  query = "",
  category = "all",
  source = "all",
  sort = "score",
  limit = 50,
  fetchJson = defaultSkillhubJsonFetcher,
}: {
  query?: string;
  category?: string;
  source?: string;
  sort?: SkillhubCatalogSort | string;
  limit?: number;
  fetchJson?: SkillhubJsonFetcher;
}) {
  const normalizedQuery = query.trim();
  const normalizedLimit = normalizeLimit(limit);
  const normalizedSort = normalizeCatalogSort(sort);
  const upstreamLimit = SKILLHUB_MAX_CATALOG_FETCH;
  const url = normalizedQuery
    ? `${SKILLHUB_SEARCH_URL}?q=${encodeURIComponent(normalizedQuery)}&limit=${upstreamLimit}`
    : SKILLHUB_INDEX_URL;
  let payload = asRecord(await fetchJson(url));
  let rawItems = Array.isArray(payload.results)
    ? payload.results
    : Array.isArray(payload.skills)
      ? payload.skills
      : [];

  if (!normalizedQuery && rawItems.length === 0) {
    const fallbackUrl = `${SKILLHUB_SEARCH_URL}?limit=${upstreamLimit}`;
    payload = asRecord(await fetchJson(fallbackUrl));
    rawItems = Array.isArray(payload.results)
      ? payload.results
      : Array.isArray(payload.skills)
        ? payload.skills
        : [];
  }

  const catalogItems = rawItems
    .map(asCatalogResult)
    .filter((item) => item.slug);
  const sourceKey = normalizeCatalogKey(source);
  const sourceItems = catalogItems.filter((item) =>
    matchesCatalogSource(item, sourceKey),
  );
  const categories = uniqueText(sourceItems.flatMap((item) => item.categories))
    .sort((left, right) => left.localeCompare(right, "zh-CN"));
  const sources = uniqueText(catalogItems.map((item) => item.source)).sort(
    (left, right) => left.localeCompare(right, "zh-CN"),
  );
  const filtered = sortCatalogResults(
    filterCatalogResults(catalogItems, category, source),
    normalizedSort,
  );

  return {
    status: "success",
    query: normalizedQuery,
    category,
    source,
    sort: normalizedSort,
    count: filtered.length,
    total: safeNumeric(payload.total, catalogItems.length),
    limit: normalizedLimit,
    categories,
    sources,
    warnings: [] as string[],
    results: filtered.slice(0, normalizedLimit),
  };
}

export async function checkSkillhubStatus({
  candidates = defaultSkillhubCandidates(),
  runner = defaultSkillhubRunner,
  env = process.env,
  paths = resolveGovernancePaths(),
}: {
  candidates?: string[];
  runner?: SkillhubRunner;
  env?: NodeJS.ProcessEnv;
  paths?: GovernancePaths;
} = {}) {
  let lastError = "";
  for (const command of candidates.filter(Boolean)) {
    try {
      const result = await runner(command, ["-v"], {
        cwd: paths.workspaceDir,
        env: skillhubEnv(env),
        timeout: 5000,
        maxBuffer: 512 * 1024,
      });
      return {
        status: "ok",
        available: true,
        command,
        workspace_dir: paths.workspaceDir,
        skill_library_dir: paths.skillLibraryDir,
        install_command: safeInstallCommandHint(env),
        version: result.stdout.trim(),
        help: result.stdout.slice(0, 4000),
        error: "",
      };
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
  }

  return {
    status: "unavailable",
    available: false,
    command: candidates[0] || "skillhub",
    workspace_dir: paths.workspaceDir,
    skill_library_dir: paths.skillLibraryDir,
    install_command: safeInstallCommandHint(env),
    help: "",
    error: lastError || "SkillHub CLI 不可用",
  };
}

export async function searchSkillhubSkills({
  query,
  command = defaultSkillhubCandidates()[0] || "skillhub",
  runner = defaultSkillhubRunner,
  env = process.env,
  paths = resolveGovernancePaths(),
  limit = 20,
}: {
  query: string;
  command?: string;
  runner?: SkillhubRunner;
  env?: NodeJS.ProcessEnv;
  paths?: GovernancePaths;
  limit?: number;
}) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) throw new Error("请输入 SkillHub 搜索关键词");
  const normalizedLimit = normalizeLimit(limit);
  const args = [
    "search",
    normalizedQuery,
    "--json",
    "--search-limit",
    String(normalizedLimit),
  ];

  let result = await runner(command, args, {
    cwd: paths.workspaceDir,
    env: skillhubEnv(env),
    timeout: 25000,
    maxBuffer: 2 * 1024 * 1024,
  });
  if (
    /No skills found\./i.test(result.stdout) &&
    /search request failed/i.test(result.stderr)
  ) {
    result = await runner(command, args, {
      cwd: paths.workspaceDir,
      env: skillhubEnv(env),
      timeout: 25000,
      maxBuffer: 2 * 1024 * 1024,
    });
  }

  if (/No skills found\./i.test(result.stdout)) {
    return {
      status: "success",
      query: normalizedQuery,
      count: 0,
      limit: normalizedLimit,
      results: [] as SkillhubSearchResult[],
      warnings: [],
      raw_output: result.stdout,
    };
  }

  const payload = parseJsonPayload(result.stdout);
  const results = Array.isArray(payload.results)
    ? payload.results.map(asSearchResult).filter((item) => item.slug)
    : [];
  return {
    status: "success",
    query: safeText(payload.query) || normalizedQuery,
    count: Number(payload.count) || results.length,
    limit: normalizedLimit,
    results,
    warnings: asTextArray(payload.warnings),
    raw_output: result.stdout,
  };
}

function validateSkillhubRef(slug: string) {
  const normalized = slug.trim();
  if (!normalized) throw new Error("缺少 SkillHub 技能 slug");
  if (!SKILLHUB_REF_PATTERN.test(normalized)) {
    throw new Error(`SkillHub 技能 slug 不安全：${slug}`);
  }
  return normalized;
}

function skillhubRefToSkillId(slug: string) {
  let normalized = slug.trim();
  if (normalized.startsWith("@")) normalized = normalized.slice(1);
  const slashIndex = normalized.indexOf("/");
  if (slashIndex >= 0) normalized = normalized.replace("/", "-");
  const versionIndex = normalized.lastIndexOf("@");
  if (versionIndex > 0) normalized = normalized.slice(0, versionIndex);
  const safeSlug = normalized
    .replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return `skillhub-${safeSlug || "skill"}`;
}

function communitySlugFolder(slug: string) {
  const withoutOrg = slug.startsWith("@")
    ? slug.slice(slug.indexOf("/") + 1)
    : slug;
  const versionIndex = withoutOrg.lastIndexOf("@");
  return versionIndex > 0 ? withoutOrg.slice(0, versionIndex) : withoutOrg;
}

async function directoryHasSkillFile(directoryPath: string) {
  try {
    const file = await stat(path.join(directoryPath, "SKILL.md"));
    return file.isFile();
  } catch {
    return false;
  }
}

async function assertInstalledSkillDir(
  paths: GovernancePaths,
  targetDir: string,
) {
  const resolvedTarget = path.resolve(targetDir);
  const resolvedLibrary = path.resolve(paths.skillLibraryDir);
  const relative = path.relative(resolvedLibrary, resolvedTarget);
  if (
    relative.startsWith("..") ||
    path.isAbsolute(relative) ||
    relative === ""
  ) {
    throw new Error("SkillHub 安装目标必须位于项目 skills/ 目录下");
  }
  await access(resolvedTarget);
  if (!(await directoryHasSkillFile(resolvedTarget))) {
    throw new Error(`SkillHub 安装完成，但未找到 SKILL.md：${resolvedTarget}`);
  }
  return resolvedTarget;
}

export async function installSkillhubSkill({
  slug,
  command = defaultSkillhubCandidates()[0] || "skillhub",
  paths = resolveGovernancePaths(),
  runner = defaultSkillhubRunner,
  env = process.env,
  force = true,
}: {
  slug: string;
  command?: string;
  paths?: GovernancePaths;
  runner?: SkillhubRunner;
  env?: NodeJS.ProcessEnv;
  force?: boolean;
}) {
  const normalizedSlug = validateSkillhubRef(slug);
  const args = [
    "install",
    normalizedSlug,
    "--json",
    "--dir",
    paths.skillLibraryDir,
    ...(force ? ["--force"] : []),
  ];
  const result = await runner(command, args, {
    cwd: paths.workspaceDir,
    env: skillhubEnv(env),
    timeout: 60000,
    maxBuffer: 2 * 1024 * 1024,
  });
  const payload = parseJsonPayload(result.stdout);
  if (payload.success === false) {
    throw new Error(
      safeText(payload.error) || `SkillHub 安装失败：${normalizedSlug}`,
    );
  }

  const targetDir = await assertInstalledSkillDir(
    paths,
    safeText(payload.targetDir) ||
      path.join(paths.skillLibraryDir, communitySlugFolder(normalizedSlug)),
  );
  const draft = await createDraftSkillFromSource({
    sourcePath: targetDir,
    workspaceDir: paths.workspaceDir,
    wikiDir: paths.wikiDir,
    skillRegistryDir: paths.skillRegistryDir,
    templateDir: paths.templateDir,
    skillId: skillhubRefToSkillId(normalizedSlug),
    name: safeText(payload.name),
    createdBy: "skillhub",
  });

  return {
    status: "success",
    command,
    install: {
      slug: safeText(payload.slug) || normalizedSlug,
      name: safeText(payload.name),
      version: safeText(payload.version),
      source: safeText(payload.source) || "community",
      installed_at: safeText(payload.installedAt),
      target_dir: targetDir,
    },
    draft,
  };
}
