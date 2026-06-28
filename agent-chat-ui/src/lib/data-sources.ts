import { execFile } from "node:child_process";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export const DATA_SOURCES_SCHEMA = "a2a_data_sources_v1" as const;

export type DataSourcesPaths = {
  workspaceDir: string;
  dataDir: string;
  rawDir: string;
  sourceRegistryDir: string;
  sourceRegistryPath: string;
  sourceSnapshotManifestPath: string;
};

type DataSourcesPathInput = Partial<
  DataSourcesPaths & {
    snapshotManifestPath: string;
  }
>;

export type SourceRecord = {
  source_id?: string;
  display_name?: string;
  source_type?: string;
  uri?: string;
  allowed_root?: string;
  sync_mode?: string;
  owner?: string;
  sensitivity_level?: string;
  freshness_sla?: string;
  status?: string;
  credential_env_keys?: string[];
  format_hint?: string;
  metadata?: Record<string, unknown>;
  expected_schema?: Record<string, unknown> | string[];
  last_sync?: {
    status?: string;
    snapshot_id?: string;
    snapshot_at?: string;
    row_count?: number;
    schema_hash?: string;
    error?: string;
  };
};

export type SourceSnapshot = {
  record_schema?: string;
  snapshot_id: string;
  source_id: string;
  source_type: string;
  observed_at: string;
  source_mtime?: string;
  source_size?: number;
  sha256?: string;
  schema_hash?: string;
  schema?: Record<string, string[]>;
  row_count?: number;
  sheet_names?: string[];
  raw_snapshot_path?: string;
  duckdb_dataset_slug?: string;
  wiki_pages?: string[];
  lightrag_docs?: string[];
  task_id?: string;
  audit_event_id?: string;
  status?: string;
  quality_warnings?: string[];
  profile?: Record<string, unknown>;
};

export type SchemaDiff = {
  status: "new" | "unchanged" | "changed" | "unknown";
  added_fields: string[];
  removed_fields: string[];
  changed_sheets: string[];
  previous_schema_hash: string;
  current_schema_hash: string;
};

export type DataSourceSummary = {
  source_id: string;
  display_name: string;
  source_type: string;
  uri: string;
  allowed_root: string;
  sync_mode: string;
  owner: string;
  sensitivity_level: string;
  freshness_sla: string;
  status: string;
  credential_env_keys: string[];
  metadata: Record<string, unknown>;
  snapshot_count: number;
  latest_snapshot: SourceSnapshot | null;
  last_snapshot: SourceSnapshot | null;
  last_snapshot_at: string;
  last_row_count: number;
  last_schema_hash: string;
  freshness_status: "fresh" | "stale" | "failed" | "never_synced" | "paused";
  schema_diff: SchemaDiff;
};

export type DataSourcesState = {
  schema: typeof DATA_SOURCES_SCHEMA;
  generated_at: string;
  source_files: {
    data_dir: string;
    raw_dir: string;
    registry_dir: string;
    registry_path: string;
    snapshot_manifest_path: string;
  };
  counts: {
    sources: number;
    active_sources: number;
    failed_sources: number;
    stale_sources: number;
    paused_sources: number;
    snapshots: number;
    schema_drift_count: number;
  };
  supported_source_types: string[];
  workflow_steps: string[];
  sources: DataSourceSummary[];
  snapshots: SourceSnapshot[];
  warnings: string[];
};

export type SourceSyncResult = {
  status: string;
  source_id?: string;
  source_type?: string;
  snapshot_id?: string;
  changed?: boolean;
  raw_snapshot_path?: string;
  error_code?: string;
  error?: string;
  quality_warnings?: string[];
  next_actions?: string[];
};

export type RegisterSourceInput = {
  source_id: string;
  display_name: string;
  source_type: string;
  uri?: string;
  allowed_root?: string;
  sync_mode?: string;
  owner?: string;
  sensitivity_level?: string;
  freshness_sla?: string;
  status?: string;
  credential_env_keys?: string[];
  metadata?: Record<string, unknown>;
};

type SourceRegistryFile = {
  schema?: string;
  updated_at?: string;
  supported_source_types?: string[];
  workflow_steps?: string[];
  sources?: Record<string, SourceRecord>;
};

type FileSummary = {
  exists: boolean;
  size_bytes: number;
  updated_at: string;
};

type PathValidationSuccess = {
  ok: true;
  sourcePath: string;
  allowedRoot: string;
  workspaceDir: string;
};

type PathValidationFailure = {
  ok: false;
  code:
    | "missing_source_path"
    | "missing_allowed_root"
    | "allowed_root_outside_workspace"
    | "path_outside_allowed_root";
  message: string;
  sourcePath: string;
  allowedRoot: string;
  workspaceDir: string;
};

export type PathValidationResult =
  | PathValidationSuccess
  | PathValidationFailure;

function defaultPaths(): DataSourcesPaths {
  const dataDir = process.env.A2A_DATA_DIR
    ? path.resolve(process.env.A2A_DATA_DIR)
    : path.resolve(process.cwd(), "..", "data");
  const workspaceDir = path.resolve(dataDir, "..");
  const rawDir = process.env.A2A_RAW_DIR
    ? path.resolve(process.env.A2A_RAW_DIR)
    : path.join(workspaceDir, "raw");
  const sourceRegistryDir = process.env.A2A_SOURCE_REGISTRY_DIR
    ? path.resolve(process.env.A2A_SOURCE_REGISTRY_DIR)
    : path.join(dataDir, "source_registry");
  return {
    workspaceDir,
    dataDir,
    rawDir,
    sourceRegistryDir,
    sourceRegistryPath: process.env.A2A_SOURCE_REGISTRY_PATH
      ? path.resolve(process.env.A2A_SOURCE_REGISTRY_PATH)
      : path.join(sourceRegistryDir, "sources.json"),
    sourceSnapshotManifestPath: process.env.A2A_SOURCE_SNAPSHOT_MANIFEST
      ? path.resolve(process.env.A2A_SOURCE_SNAPSHOT_MANIFEST)
      : path.join(sourceRegistryDir, "snapshots.jsonl"),
  };
}

export function resolveDataSourcePaths(
  paths: DataSourcesPathInput = {},
): DataSourcesPaths {
  const defaults = defaultPaths();
  const merged = { ...defaults, ...paths };
  const sourceSnapshotManifestPath =
    paths.sourceSnapshotManifestPath || paths.snapshotManifestPath;
  return {
    workspaceDir: path.resolve(merged.workspaceDir),
    dataDir: path.resolve(merged.dataDir),
    rawDir: path.resolve(merged.rawDir),
    sourceRegistryDir: path.resolve(merged.sourceRegistryDir),
    sourceRegistryPath: path.resolve(merged.sourceRegistryPath),
    sourceSnapshotManifestPath: path.resolve(
      sourceSnapshotManifestPath || merged.sourceSnapshotManifestPath,
    ),
  };
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function safeArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function safeRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function uniqueSorted(values: string[]) {
  return [...new Set(values.filter(Boolean))].sort((a, b) =>
    a.localeCompare(b),
  );
}

async function fileSummary(filePath: string): Promise<FileSummary> {
  try {
    const fileStat = await stat(filePath);
    return {
      exists: true,
      size_bytes: fileStat.size,
      updated_at: fileStat.mtime.toISOString(),
    };
  } catch {
    return { exists: false, size_bytes: 0, updated_at: "" };
  }
}

async function readJson<T>(filePath: string): Promise<T | null> {
  try {
    return JSON.parse(await readFile(filePath, "utf8")) as T;
  } catch {
    return null;
  }
}

async function readJsonLines<T>(filePath: string): Promise<T[]> {
  const text = await readFile(filePath, "utf8").catch(() => "");
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line) as T];
      } catch {
        return [];
      }
    });
}

function isPathUnder(candidate: string, root: string) {
  const relative = path.relative(path.resolve(root), path.resolve(candidate));
  return (
    relative === "" ||
    (!relative.startsWith("..") && !path.isAbsolute(relative))
  );
}

function resolveUserPath(value: string, baseDir: string) {
  return path.resolve(
    path.isAbsolute(value) ? value : path.join(baseDir, value),
  );
}

export function validateSourcePathInput({
  workspaceDir,
  sourcePath,
  allowedRoot,
}: {
  workspaceDir: string;
  sourcePath: string;
  allowedRoot: string;
}): PathValidationResult {
  const workspace = path.resolve(workspaceDir);
  const source = safeText(sourcePath);
  const rootInput = safeText(allowedRoot);
  const resolvedSource = source ? resolveUserPath(source, workspace) : "";
  const resolvedRoot = rootInput ? resolveUserPath(rootInput, workspace) : "";
  const base = {
    sourcePath: resolvedSource,
    allowedRoot: resolvedRoot,
    workspaceDir: workspace,
  };

  if (!resolvedSource) {
    return {
      ok: false,
      code: "missing_source_path",
      message: "缺少 sourcePath。",
      ...base,
    };
  }
  if (!resolvedRoot) {
    return {
      ok: false,
      code: "missing_allowed_root",
      message: "缺少 allowedRoot。",
      ...base,
    };
  }
  if (!isPathUnder(resolvedRoot, workspace)) {
    return {
      ok: false,
      code: "allowed_root_outside_workspace",
      message: "allowedRoot 必须位于工作区内。",
      ...base,
    };
  }
  if (!isPathUnder(resolvedSource, resolvedRoot)) {
    return {
      ok: false,
      code: "path_outside_allowed_root",
      message: "sourcePath 必须位于 allowedRoot 内。",
      ...base,
    };
  }
  return { ok: true, ...base };
}

function snapshotTime(snapshot: SourceSnapshot) {
  const parsed = Date.parse(snapshot.observed_at || "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function sourceTime(source: DataSourceSummary) {
  const parsed = Date.parse(source.last_snapshot_at || "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function flattenSchema(schema: Record<string, string[]> = {}) {
  return Object.entries(schema).flatMap(([sheet, fields]) =>
    safeArray<string>(fields).map((field) => ({ sheet, field })),
  );
}

function schemaDiff(
  latest: SourceSnapshot | null,
  previous: SourceSnapshot | null,
): SchemaDiff {
  if (!latest) {
    return {
      status: "unknown",
      added_fields: [],
      removed_fields: [],
      changed_sheets: [],
      previous_schema_hash: "",
      current_schema_hash: "",
    };
  }
  if (!previous) {
    return {
      status: "new",
      added_fields: [],
      removed_fields: [],
      changed_sheets: Object.keys(latest.schema ?? {}),
      previous_schema_hash: "",
      current_schema_hash: safeText(latest.schema_hash),
    };
  }
  const latestFields = flattenSchema(latest.schema);
  const previousFields = flattenSchema(previous.schema);
  const latestFieldNames = new Set(latestFields.map((item) => item.field));
  const previousFieldNames = new Set(previousFields.map((item) => item.field));
  const addedFields = uniqueSorted(
    [...latestFieldNames].filter((field) => !previousFieldNames.has(field)),
  );
  const removedFields = uniqueSorted(
    [...previousFieldNames].filter((field) => !latestFieldNames.has(field)),
  );
  const changedSheets = uniqueSorted(
    Object.keys({
      ...(latest.schema ?? {}),
      ...(previous.schema ?? {}),
    }).filter(
      (sheet) =>
        JSON.stringify(latest.schema?.[sheet] ?? []) !==
        JSON.stringify(previous.schema?.[sheet] ?? []),
    ),
  );
  const unchanged =
    addedFields.length === 0 &&
    removedFields.length === 0 &&
    changedSheets.length === 0 &&
    safeText(latest.schema_hash) === safeText(previous.schema_hash);
  return {
    status: unchanged ? "unchanged" : "changed",
    added_fields: addedFields,
    removed_fields: removedFields,
    changed_sheets: changedSheets,
    previous_schema_hash: safeText(previous.schema_hash),
    current_schema_hash: safeText(latest.schema_hash),
  };
}

function parseSlaMs(value: string) {
  const match = safeText(value).match(/^(\d+)\s*(m|h|d)$/i);
  if (!match) return 0;
  const count = Number(match[1]);
  const unit = match[2].toLowerCase();
  if (unit === "m") return count * 60 * 1000;
  if (unit === "h") return count * 60 * 60 * 1000;
  return count * 24 * 60 * 60 * 1000;
}

function freshnessStatus(source: SourceRecord, latest: SourceSnapshot | null) {
  const sourceStatus = safeText(source.status) || "active";
  if (sourceStatus === "failed" || latest?.status === "failed") return "failed";
  if (["paused", "disabled", "archived"].includes(sourceStatus))
    return "paused";
  if (!latest) return "never_synced";
  const slaMs = parseSlaMs(safeText(source.freshness_sla));
  if (slaMs > 0 && Date.now() - snapshotTime(latest) > slaMs) return "stale";
  return "fresh";
}

function summarizeSource(
  sourceId: string,
  source: SourceRecord,
  snapshots: SourceSnapshot[],
): DataSourceSummary {
  const sourceSnapshots = snapshots
    .filter((snapshot) => snapshot.source_id === sourceId)
    .sort((a, b) => snapshotTime(a) - snapshotTime(b));
  const latest = sourceSnapshots.at(-1) ?? null;
  const previous = sourceSnapshots.at(-2) ?? null;
  const status = safeText(source.status) || "active";
  return {
    source_id: safeText(source.source_id) || sourceId,
    display_name: safeText(source.display_name) || sourceId,
    source_type: safeText(source.source_type) || "unknown",
    uri: safeText(source.uri),
    allowed_root: safeText(source.allowed_root),
    sync_mode: safeText(source.sync_mode) || "on_demand",
    owner: safeText(source.owner),
    sensitivity_level: safeText(source.sensitivity_level) || "internal",
    freshness_sla: safeText(source.freshness_sla),
    status,
    credential_env_keys: safeArray<string>(source.credential_env_keys),
    metadata: safeRecord(source.metadata),
    snapshot_count: sourceSnapshots.length,
    latest_snapshot: latest,
    last_snapshot: latest,
    last_snapshot_at: safeText(latest?.observed_at),
    last_row_count: Number(latest?.row_count ?? 0),
    last_schema_hash: safeText(latest?.schema_hash),
    freshness_status: freshnessStatus(source, latest),
    schema_diff: schemaDiff(latest, previous),
  };
}

function emptyState(
  paths: DataSourcesPaths,
  warnings: string[],
): DataSourcesState {
  return {
    schema: DATA_SOURCES_SCHEMA,
    generated_at: new Date().toISOString(),
    source_files: {
      data_dir: paths.dataDir,
      raw_dir: paths.rawDir,
      registry_dir: paths.sourceRegistryDir,
      registry_path: paths.sourceRegistryPath,
      snapshot_manifest_path: paths.sourceSnapshotManifestPath,
    },
    counts: {
      sources: 0,
      active_sources: 0,
      failed_sources: 0,
      stale_sources: 0,
      paused_sources: 0,
      snapshots: 0,
      schema_drift_count: 0,
    },
    supported_source_types: [],
    workflow_steps: [],
    sources: [],
    snapshots: [],
    warnings,
  };
}

export async function loadDataSourcesState({
  paths: partialPaths = {},
}: {
  paths?: DataSourcesPathInput;
} = {}): Promise<DataSourcesState> {
  const paths = resolveDataSourcePaths(partialPaths);
  const [registryFile, snapshotFile, registry, snapshots] = await Promise.all([
    fileSummary(paths.sourceRegistryPath),
    fileSummary(paths.sourceSnapshotManifestPath),
    readJson<SourceRegistryFile>(paths.sourceRegistryPath),
    readJsonLines<SourceSnapshot>(paths.sourceSnapshotManifestPath),
  ]);
  const warnings = [
    !registryFile.exists ? "Source registry is missing." : "",
    !snapshotFile.exists ? "Source snapshot manifest is missing." : "",
    registry && registry.schema && registry.schema !== "a2a_source_registry_v1"
      ? `Unexpected source registry schema: ${registry.schema}.`
      : "",
  ].filter(Boolean);

  if (!registry) return emptyState(paths, warnings);

  const records = registry.sources ?? {};
  const sources = Object.entries(records)
    .map(([sourceId, source]) => summarizeSource(sourceId, source, snapshots))
    .sort((a, b) => {
      if (a.status !== b.status) {
        if (a.status === "active") return -1;
        if (b.status === "active") return 1;
      }
      const recent = sourceTime(b) - sourceTime(a);
      return recent || a.source_id.localeCompare(b.source_id);
    });
  const schemaDriftCount = sources.filter((source) =>
    ["changed"].includes(source.schema_diff.status),
  ).length;

  return {
    schema: DATA_SOURCES_SCHEMA,
    generated_at: new Date().toISOString(),
    source_files: {
      data_dir: paths.dataDir,
      raw_dir: paths.rawDir,
      registry_dir: paths.sourceRegistryDir,
      registry_path: paths.sourceRegistryPath,
      snapshot_manifest_path: paths.sourceSnapshotManifestPath,
    },
    counts: {
      sources: sources.length,
      active_sources: sources.filter((source) => source.status === "active")
        .length,
      failed_sources: sources.filter(
        (source) =>
          source.status === "failed" || source.freshness_status === "failed",
      ).length,
      stale_sources: sources.filter((source) =>
        ["stale", "never_synced"].includes(source.freshness_status),
      ).length,
      paused_sources: sources.filter(
        (source) => source.freshness_status === "paused",
      ).length,
      snapshots: snapshots.length,
      schema_drift_count: schemaDriftCount,
    },
    supported_source_types: safeArray<string>(registry.supported_source_types),
    workflow_steps: safeArray<string>(registry.workflow_steps),
    sources,
    snapshots: [...snapshots].sort((a, b) => snapshotTime(b) - snapshotTime(a)),
    warnings,
  };
}

function pythonEnv(paths: DataSourcesPaths) {
  return {
    ...process.env,
    A2A_DATA_DIR: paths.dataDir,
    A2A_RAW_DIR: paths.rawDir,
    A2A_SOURCE_REGISTRY_DIR: paths.sourceRegistryDir,
    A2A_SOURCE_REGISTRY_PATH: paths.sourceRegistryPath,
    A2A_SOURCE_SNAPSHOT_MANIFEST: paths.sourceSnapshotManifestPath,
    A2A_WAREHOUSE_DIR:
      process.env.A2A_WAREHOUSE_DIR || path.join(paths.dataDir, "warehouse"),
    PYTHONPATH: [paths.workspaceDir, process.env.PYTHONPATH]
      .filter(Boolean)
      .join(path.delimiter),
  };
}

function pythonExecutable(paths: DataSourcesPaths) {
  return (
    process.env.A2A_PYTHON ||
    process.env.PYTHON ||
    path.join(paths.workspaceDir, ".venv", "bin", "python")
  );
}

function parsePythonJson(stdout: string) {
  const trimmed = stdout.trim();
  if (!trimmed) return {};
  try {
    return JSON.parse(trimmed) as Record<string, unknown>;
  } catch {
    const start = trimmed.lastIndexOf("{");
    if (start >= 0) {
      return JSON.parse(trimmed.slice(start)) as Record<string, unknown>;
    }
    throw new Error("Python tool returned non-JSON output.");
  }
}

export async function syncDataSourceNow({
  sourceId,
  requestedBy = "frontend",
  paths: partialPaths = {},
}: {
  sourceId: string;
  requestedBy?: string;
  paths?: DataSourcesPathInput;
}): Promise<SourceSyncResult> {
  const paths = resolveDataSourcePaths(partialPaths);
  const { stdout, stderr } = await execFileAsync(
    pythonExecutable(paths),
    [
      "-m",
      "src.a2a_ecommerce_demo.source_registry_tools",
      "sync-source",
      sourceId,
      "--requested-by",
      requestedBy,
    ],
    {
      cwd: paths.workspaceDir,
      env: pythonEnv(paths),
      maxBuffer: 1024 * 1024 * 8,
      timeout: 120_000,
    },
  );
  const payload = parsePythonJson(stdout) as SourceSyncResult;
  if (stderr.trim()) {
    payload.next_actions = [
      ...(payload.next_actions ?? []),
      `stderr: ${stderr.trim().slice(0, 300)}`,
    ];
  }
  return payload;
}

export async function registerDataSource({
  input,
  paths: partialPaths = {},
}: {
  input: RegisterSourceInput;
  paths?: DataSourcesPathInput;
}) {
  const paths = resolveDataSourcePaths(partialPaths);
  const args = [
    "-m",
    "src.a2a_ecommerce_demo.source_registry_tools",
    "register-source",
    "--source-id",
    input.source_id,
    "--display-name",
    input.display_name,
    "--source-type",
    input.source_type,
    "--uri",
    input.uri ?? "",
    "--allowed-root",
    input.allowed_root ?? "",
    "--sync-mode",
    input.sync_mode ?? "on_demand",
    "--owner",
    input.owner ?? "",
    "--sensitivity-level",
    input.sensitivity_level ?? "internal",
    "--freshness-sla",
    input.freshness_sla ?? "",
    "--status",
    input.status ?? "active",
    "--credential-env-keys",
    (input.credential_env_keys ?? []).join(","),
    "--metadata-json",
    JSON.stringify(input.metadata ?? {}),
  ];
  const { stdout } = await execFileAsync(pythonExecutable(paths), args, {
    cwd: paths.workspaceDir,
    env: pythonEnv(paths),
    maxBuffer: 1024 * 1024 * 8,
    timeout: 120_000,
  });
  return parsePythonJson(stdout);
}

export async function setDataSourceStatus({
  sourceId,
  status,
  paths: partialPaths = {},
}: {
  sourceId: string;
  status: string;
  paths?: DataSourcesPathInput;
}) {
  const paths = resolveDataSourcePaths(partialPaths);
  const { stdout } = await execFileAsync(
    pythonExecutable(paths),
    [
      "-m",
      "src.a2a_ecommerce_demo.source_registry_tools",
      "set-status",
      sourceId,
      status,
    ],
    {
      cwd: paths.workspaceDir,
      env: pythonEnv(paths),
      maxBuffer: 1024 * 1024 * 8,
      timeout: 120_000,
    },
  );
  return parsePythonJson(stdout);
}

export async function rebindDataSourcePath({
  sourceId,
  uri,
  allowedRoot,
  metadata = {},
  paths: partialPaths = {},
}: {
  sourceId: string;
  uri: string;
  allowedRoot: string;
  metadata?: Record<string, unknown>;
  paths?: DataSourcesPathInput;
}) {
  const paths = resolveDataSourcePaths(partialPaths);
  const { stdout } = await execFileAsync(
    pythonExecutable(paths),
    [
      "-m",
      "src.a2a_ecommerce_demo.source_registry_tools",
      "rebind-source",
      sourceId,
      "--uri",
      uri,
      "--allowed-root",
      allowedRoot,
      "--metadata-json",
      JSON.stringify(metadata),
    ],
    {
      cwd: paths.workspaceDir,
      env: pythonEnv(paths),
      maxBuffer: 1024 * 1024 * 8,
      timeout: 120_000,
    },
  );
  return parsePythonJson(stdout);
}
