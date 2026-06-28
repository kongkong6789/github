import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

import { summarizeConfigHealth } from "./config-health";
import {
  collectArtifactLinks,
  summarizeConnectorRegistry,
  summarizeEmbeddingHealth,
  summarizeSensitiveFields,
  summarizeWikiKnowledgeHealth,
  summarizeWorkflowProgress,
  type ArtifactLink,
  type ConnectorRegistrySummary,
  type EmbeddingHealth,
  type SensitiveFieldSummary,
  type WikiKnowledgeHealth,
  type WikiKnowledgePageInput,
  type WorkflowProgress,
  type WorkflowTaskInput,
} from "./data-health";
import { loadDataSourcesState, type DataSourcesState } from "./data-sources";
import { loadLightRAGStatus, type LightRAGStatus } from "./lightrag-status";

export type DataHealthPaths = {
  workspaceDir: string;
  dataDir: string;
  docsDir: string;
  rawDir: string;
  warehouseDir: string;
  wikiDir: string;
  taskDir: string;
  lightragWorkingDir: string;
  duckdbPath: string;
  registryPath: string;
  connectorRegistryPath: string;
  sourceRegistryDir: string;
  sourceRegistryPath: string;
  sourceSnapshotManifestPath: string;
};

export type DataHealthState = {
  status: "ok";
  schema_version: "a2a_data_health_v1";
  generated_at: string;
  checked_at: string;
  source_files: {
    data_dir: string;
    raw_dir: string;
    warehouse_dir: string;
    duckdb_path: string;
    registry_path: string;
    connector_registry_path: string;
    source_registry_path: string;
    source_snapshot_manifest_path: string;
    wiki_dir: string;
    wiki_schema_path: string;
    wiki_index_path: string;
    wiki_log_path: string;
    task_dir: string;
    lightrag_doc_status_path: string;
  };
  warnings: string[];
  paths: {
    data_dir: string;
    raw_dir: string;
    warehouse_dir: string;
    duckdb_path: string;
    registry_path: string;
    connector_registry_path: string;
    source_registry_path: string;
    source_snapshot_manifest_path: string;
    wiki_dir: string;
  };
  duckdb: FileSummary;
  registry_file: FileSummary;
  registry: RegistrySummary;
  sensitive_fields: SensitiveFieldSummary;
  wiki_knowledge: WikiKnowledgeHealth;
  connector_registry_file: FileSummary;
  connectors: ConnectorRegistrySummary;
  sources: DataSourcesState;
  embedding_health: EmbeddingHealth;
  lightrag_status: LightRAGStatus;
  workflow_progress: WorkflowProgress;
  config_health: Awaited<ReturnType<typeof summarizeConfigHealth>>;
  artifact_links: ResolvedArtifactLink[];
  large_excel: LargeExcelSummary[];
  tasks: TaskSummary[];
};

type FileSummary = {
  exists: boolean;
  size_bytes: number;
  updated_at: string;
};

type RegistrySummary = {
  schema: string;
  updated_at: string;
  dataset_count: number;
  mart_count: number;
  semantic_count: number;
  datasets: Array<{
    slug: string;
    source: string;
    registered_at: string;
    sheet_count: number;
    row_count: number;
    mart_count: number;
    semantic_count: number;
    overview_page: string;
    wiki_pages: string[];
    derived_exports: string[];
  }>;
};

type TaskItem = {
  file: string;
  fileStatMtime: string;
  task: Record<string, unknown>;
};

type TaskSummary = {
  task_id: string;
  goal: string;
  status: string;
  updated_at: string;
  step_count: number;
  final_report: string;
  progress: WorkflowProgress;
};

type LargeExcelSummary = {
  slug: string;
  source: string;
  sheets: number;
  warnings: unknown[];
};

type ResolvedArtifactLink = ArtifactLink & {
  href: string;
  file_path: string;
  exists: boolean;
  size_bytes: number;
  updated_at: string;
};

function defaultPaths(): DataHealthPaths {
  const dataDir = process.env.A2A_DATA_DIR
    ? path.resolve(process.env.A2A_DATA_DIR)
    : path.resolve(process.cwd(), "..", "data");
  const workspaceDir = path.resolve(dataDir, "..");
  const warehouseDir = path.join(dataDir, "warehouse");
  const rawDir = process.env.A2A_RAW_DIR
    ? path.resolve(process.env.A2A_RAW_DIR)
    : path.join(workspaceDir, "raw");
  const sourceRegistryDir = process.env.A2A_SOURCE_REGISTRY_DIR
    ? path.resolve(process.env.A2A_SOURCE_REGISTRY_DIR)
    : path.join(dataDir, "source_registry");
  const docsDir = process.env.A2A_DOCS_DIR
    ? path.resolve(process.env.A2A_DOCS_DIR)
    : path.join(workspaceDir, "docs");
  const wikiDir = process.env.A2A_WIKI_DIR
    ? path.resolve(process.env.A2A_WIKI_DIR)
    : path.join(workspaceDir, "wiki");
  const taskDir = process.env.A2A_TASK_DIR
    ? path.resolve(process.env.A2A_TASK_DIR)
    : path.join(dataDir, "tasks");
  const lightragWorkingDir = process.env.WORKING_DIR
    ? path.resolve(process.env.WORKING_DIR)
    : path.join(dataDir, "lightrag_official");
  return {
    workspaceDir,
    dataDir,
    docsDir,
    rawDir,
    warehouseDir,
    wikiDir,
    taskDir,
    lightragWorkingDir,
    duckdbPath: path.join(warehouseDir, "a2a.duckdb"),
    registryPath: path.join(warehouseDir, "dataset_registry.json"),
    connectorRegistryPath: process.env.A2A_CONNECTOR_REGISTRY
      ? path.resolve(process.env.A2A_CONNECTOR_REGISTRY)
      : path.join(warehouseDir, "connector_registry.json"),
    sourceRegistryDir,
    sourceRegistryPath: process.env.A2A_SOURCE_REGISTRY_PATH
      ? path.resolve(process.env.A2A_SOURCE_REGISTRY_PATH)
      : path.join(sourceRegistryDir, "sources.json"),
    sourceSnapshotManifestPath: process.env.A2A_SOURCE_SNAPSHOT_MANIFEST
      ? path.resolve(process.env.A2A_SOURCE_SNAPSHOT_MANIFEST)
      : path.join(sourceRegistryDir, "snapshots.jsonl"),
  };
}

function resolvePaths(paths: Partial<DataHealthPaths> = {}): DataHealthPaths {
  return { ...defaultPaths(), ...paths };
}

function safeArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function firstOverviewPage(dataset: Record<string, unknown>) {
  const explicit =
    safeText(dataset.wiki_overview_path) || safeText(dataset.overview_page);
  if (explicit) return explicit;
  return (
    datasetWikiPages(dataset).find((page) => page.endsWith("/overview.md")) ??
    ""
  );
}

function datasetWikiPages(dataset: Record<string, unknown>) {
  const wikiPages = dataset.wiki_pages;
  if (Array.isArray(wikiPages)) return wikiPages.map(safeText).filter(Boolean);
  return Object.values(
    wikiPages && typeof wikiPages === "object" ? wikiPages : {},
  )
    .map(safeText)
    .filter(Boolean);
}

async function existsWithSize(filePath: string): Promise<FileSummary> {
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

async function summarizeRegistry(
  registryPath: string,
): Promise<RegistrySummary> {
  const registry = await readJson<Record<string, unknown>>(registryPath);
  const datasetsRecord =
    registry && typeof registry.datasets === "object" && registry.datasets
      ? (registry.datasets as Record<string, Record<string, unknown>>)
      : {};
  const datasets = Object.values(datasetsRecord).map((dataset) => {
    const sheetViews = safeArray<Record<string, unknown>>(dataset.sheet_views);
    const martViews = safeArray<Record<string, unknown>>(dataset.mart_views);
    const semanticViews = safeArray<Record<string, unknown>>(
      dataset.semantic_views,
    );
    const wikiPages = datasetWikiPages(dataset);
    const derivedExports = safeArray(dataset.derived_exports)
      .map(safeText)
      .filter(Boolean);
    return {
      slug: safeText(dataset.dataset_slug) || safeText(dataset.slug),
      source: safeText(dataset.relative_source) || safeText(dataset.source),
      registered_at: safeText(dataset.registered_at),
      sheet_count: sheetViews.length,
      row_count: sheetViews.reduce(
        (sum, view) => sum + Number(view.rows || 0),
        0,
      ),
      mart_count: martViews.length,
      semantic_count: semanticViews.length,
      overview_page: firstOverviewPage(dataset),
      wiki_pages: wikiPages,
      derived_exports: derivedExports,
    };
  });

  return {
    schema: safeText(registry?.schema),
    updated_at: safeText(registry?.updated_at),
    dataset_count: datasets.length,
    mart_count: datasets.reduce((sum, dataset) => sum + dataset.mart_count, 0),
    semantic_count: datasets.reduce(
      (sum, dataset) => sum + dataset.semantic_count,
      0,
    ),
    datasets: datasets.slice(0, 40),
  };
}

async function readWorkflowTasks(taskDir: string): Promise<TaskItem[]> {
  try {
    const files = await readdir(taskDir);
    const items = await Promise.all(
      files
        .filter((file) => file.endsWith(".json"))
        .map(async (file) => {
          const fullPath = path.join(taskDir, file);
          const fileStat = await stat(fullPath);
          const task = await readJson<Record<string, unknown>>(fullPath);
          return {
            file,
            fileStatMtime: fileStat.mtime.toISOString(),
            task: task ?? {},
          };
        }),
    );
    return items.sort((a, b) => {
      const left = safeText(a.task.updated_at) || a.fileStatMtime;
      const right = safeText(b.task.updated_at) || b.fileStatMtime;
      return Date.parse(right) - Date.parse(left);
    });
  } catch {
    return [];
  }
}

function summarizeTaskItem(item: TaskItem): TaskSummary {
  const task = item.task;
  const finalReport =
    task.final_report && typeof task.final_report === "object"
      ? (task.final_report as Record<string, unknown>)
      : {};

  return {
    task_id: safeText(task.task_id) || item.file.replace(/\.json$/, ""),
    goal: safeText(task.goal).slice(0, 180),
    status: safeText(task.status) || "unknown",
    updated_at: safeText(task.updated_at) || item.fileStatMtime,
    step_count: safeArray(task.steps).length,
    final_report: safeText(finalReport.saved_to),
    progress: summarizeWorkflowProgress(task as WorkflowTaskInput),
  };
}

function resolveArtifactFilePath(paths: DataHealthPaths, artifactPath: string) {
  if (path.isAbsolute(artifactPath)) return artifactPath;
  if (artifactPath.startsWith("data/") || artifactPath.startsWith("wiki/")) {
    return path.join(paths.workspaceDir, artifactPath);
  }
  if (
    /^(warehouse|cleaned|derived|reports|lightrag|lightrag_official|staging)\//.test(
      artifactPath,
    )
  ) {
    return path.join(paths.dataDir, artifactPath);
  }
  if (
    /^(datasets|decisions|data-dictionary|cleaning-rules|logs|products|lightrag-auto-summary|lightrag-retry)\//.test(
      artifactPath,
    )
  ) {
    return path.join(paths.wikiDir, artifactPath);
  }
  return path.join(paths.workspaceDir, artifactPath);
}

function toFileHref(filePath: string) {
  return `file://${filePath.split(path.sep).map(encodeURIComponent).join("/")}`;
}

async function resolveArtifactLinks(
  paths: DataHealthPaths,
  links: ArtifactLink[],
): Promise<ResolvedArtifactLink[]> {
  const resolved = await Promise.all(
    links.map(async (link) => {
      const filePath = resolveArtifactFilePath(paths, link.path);
      const file = await existsWithSize(filePath);
      return {
        ...link,
        href: toFileHref(filePath),
        file_path: filePath,
        ...file,
      };
    }),
  );

  const seen = new Set<string>();
  return resolved.filter((link) => {
    const key = link.file_path.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

async function summarizeLargeExcel(
  warehouseDir: string,
): Promise<LargeExcelSummary[]> {
  const largeExcelDir = path.join(warehouseDir, "large_excel");
  try {
    const dirs = await readdir(largeExcelDir);
    const items = await Promise.all(
      dirs.map(async (dir) => {
        const manifest = await readJson<Record<string, unknown>>(
          path.join(largeExcelDir, dir, "manifest.json"),
        );
        const quality = await readJson<Record<string, unknown>>(
          path.join(largeExcelDir, dir, "quality_report.json"),
        );
        return {
          slug: dir,
          source: safeText(manifest?.source_file) || safeText(manifest?.source),
          sheets: safeArray(manifest?.sheets).length,
          warnings: safeArray(quality?.warnings).slice(0, 5),
        };
      }),
    );
    return items;
  } catch {
    return [];
  }
}

async function readLightRAGDocStatusRecords(lightragWorkingDir: string) {
  const status = await readJson<Record<string, unknown>>(
    path.join(lightragWorkingDir, "kv_store_doc_status.json"),
  );
  return Object.values(status ?? {});
}

async function readMarkdownFiles(
  rootDir: string,
): Promise<WikiKnowledgePageInput[]> {
  async function walk(dir: string): Promise<WikiKnowledgePageInput[]> {
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return [];
    }
    const nested = await Promise.all(
      entries.map(async (entry) => {
        if (entry.name === ".obsidian") return [];
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) return walk(fullPath);
        if (!entry.isFile() || !entry.name.endsWith(".md")) return [];
        try {
          return [
            {
              path: path.relative(rootDir, fullPath).split(path.sep).join("/"),
              content: await readFile(fullPath, "utf8"),
            },
          ];
        } catch {
          return [];
        }
      }),
    );
    return nested.flat();
  }
  return walk(rootDir);
}

function extractIndexedTargets(indexContent: string): string[] {
  return [...indexContent.matchAll(/\[\[([^|\]]+)(?:\|[^\]]+)?\]\]/g)]
    .map((match) => safeText(match[1]))
    .filter(Boolean);
}

function countWikiLogEntries(logContent: string): number {
  return logContent
    .split(/\r?\n/)
    .filter((line) => /^## \[\d{4}-\d{2}-\d{2}\]/.test(line)).length;
}

function buildWarnings({
  duckdb,
  registryFile,
  connectorRegistryFile,
  sources,
  embeddingHealth,
  configHealth,
  lightragStatus,
  wikiKnowledge,
}: {
  duckdb: FileSummary;
  registryFile: FileSummary;
  connectorRegistryFile: FileSummary;
  sources: DataSourcesState;
  embeddingHealth: EmbeddingHealth;
  configHealth: Awaited<ReturnType<typeof summarizeConfigHealth>>;
  lightragStatus: LightRAGStatus;
  wikiKnowledge: WikiKnowledgeHealth;
}) {
  return [
    !duckdb.exists ? "DuckDB file is missing." : "",
    !registryFile.exists ? "Dataset registry is missing." : "",
    !connectorRegistryFile.exists ? "Connector registry is missing." : "",
    ...sources.warnings,
    sources.counts.failed_sources > 0
      ? `${sources.counts.failed_sources} source registry item(s) failed.`
      : "",
    sources.counts.schema_drift_count > 0
      ? `${sources.counts.schema_drift_count} source schema drift item(s) need review.`
      : "",
    wikiKnowledge.status !== "success"
      ? `Wiki knowledge health is ${wikiKnowledge.status}.`
      : "",
    ...embeddingHealth.warnings,
    configHealth.status !== "ok"
      ? `Config health is ${configHealth.status}.`
      : "",
    lightragStatus.status !== "success"
      ? "LightRAG status endpoint is unavailable."
      : "",
  ].filter(Boolean);
}

export async function loadDataHealthState({
  paths: partialPaths = {},
  includeRemoteLightRagStatus = true,
}: {
  paths?: Partial<DataHealthPaths>;
  includeRemoteLightRagStatus?: boolean;
} = {}): Promise<DataHealthState> {
  const paths = resolvePaths(partialPaths);
  const generatedAt = new Date().toISOString();
  const lightragDocStatusPath = path.join(
    paths.lightragWorkingDir,
    "kv_store_doc_status.json",
  );
  const wikiSchemaPath = path.join(paths.docsDir, "wiki_schema.md");
  const wikiIndexPath = path.join(paths.wikiDir, "index.md");
  const wikiLogPath = path.join(paths.wikiDir, "log.md");
  const embeddingStarted = Date.now();
  const [
    duckdb,
    registryFile,
    registryRaw,
    registry,
    taskItems,
    largeExcel,
    lightragStatusRecords,
    configHealth,
    connectorRegistryFile,
    connectorRegistryRaw,
    sources,
    lightragStatus,
    wikiPages,
    wikiSchemaFile,
    wikiIndexFile,
    wikiLogFile,
    wikiIndexText,
    wikiLogText,
  ] = await Promise.all([
    existsWithSize(paths.duckdbPath),
    existsWithSize(paths.registryPath),
    readJson<Record<string, unknown>>(paths.registryPath),
    summarizeRegistry(paths.registryPath),
    readWorkflowTasks(paths.taskDir),
    summarizeLargeExcel(paths.warehouseDir),
    readLightRAGDocStatusRecords(paths.lightragWorkingDir),
    summarizeConfigHealth({
      workspaceDir: paths.workspaceDir,
      dataDir: paths.dataDir,
      env: process.env,
    }),
    existsWithSize(paths.connectorRegistryPath),
    readJson<Record<string, unknown>>(paths.connectorRegistryPath),
    loadDataSourcesState({ paths }),
    includeRemoteLightRagStatus
      ? loadLightRAGStatus()
      : Promise.resolve({
          status: "unavailable" as const,
          apiUrl: "",
          status_counts: {
            processed: 0,
            pending: 0,
            processing: 0,
            failed: 0,
            all: 0,
          },
          processed: 0,
          pending: 0,
          processing: 0,
          failed: 0,
          pipeline_busy: false,
          root_causes: [],
          checked_at: generatedAt,
        }),
    readMarkdownFiles(paths.wikiDir),
    existsWithSize(wikiSchemaPath),
    existsWithSize(wikiIndexPath),
    existsWithSize(wikiLogPath),
    readFile(wikiIndexPath, "utf8").catch(() => ""),
    readFile(wikiLogPath, "utf8").catch(() => ""),
  ]);
  const connectors = summarizeConnectorRegistry(
    connectorRegistryRaw ?? { registry_path: paths.connectorRegistryPath },
  );
  const embeddingLatencyMs = Date.now() - embeddingStarted;
  const tasks = taskItems.slice(0, 12).map(summarizeTaskItem);
  const workflowProgress = summarizeWorkflowProgress(
    (taskItems[0]?.task as WorkflowTaskInput | undefined) ?? null,
  );
  const artifactLinks = await resolveArtifactLinks(
    paths,
    collectArtifactLinks({
      paths: {
        data_dir: paths.dataDir,
        wiki_dir: paths.wikiDir,
        duckdb_path: paths.duckdbPath,
        registry_path: paths.registryPath,
        source_registry_path: paths.sourceRegistryPath,
        source_snapshot_manifest_path: paths.sourceSnapshotManifestPath,
      },
      registry,
      connectors,
      tasks: taskItems.map((item) => item.task),
    }),
  );
  const embeddingHealth = summarizeEmbeddingHealth({
    env: process.env,
    statusRecords: lightragStatusRecords,
    timeoutMs: Number(
      process.env.EMBEDDING_HEALTH_TIMEOUT_MS ??
        process.env.LIGHTRAG_STATUS_TIMEOUT_MS ??
        3500,
    ),
    latencyMs: embeddingLatencyMs,
    latencySource: "local_doc_status_read",
  });
  const wikiKnowledge = summarizeWikiKnowledgeHealth({
    schemaPresent: wikiSchemaFile.exists,
    indexPresent: wikiIndexFile.exists,
    logPresent: wikiLogFile.exists,
    pages: wikiPages,
    indexedTargets: extractIndexedTargets(wikiIndexText),
    logEntries: countWikiLogEntries(wikiLogText),
  });

  return {
    status: "ok",
    schema_version: "a2a_data_health_v1",
    generated_at: generatedAt,
    checked_at: generatedAt,
    source_files: {
      data_dir: paths.dataDir,
      raw_dir: paths.rawDir,
      warehouse_dir: paths.warehouseDir,
      duckdb_path: paths.duckdbPath,
      registry_path: paths.registryPath,
      connector_registry_path: paths.connectorRegistryPath,
      source_registry_path: paths.sourceRegistryPath,
      source_snapshot_manifest_path: paths.sourceSnapshotManifestPath,
      wiki_dir: paths.wikiDir,
      wiki_schema_path: wikiSchemaPath,
      wiki_index_path: wikiIndexPath,
      wiki_log_path: wikiLogPath,
      task_dir: paths.taskDir,
      lightrag_doc_status_path: lightragDocStatusPath,
    },
    paths: {
      data_dir: paths.dataDir,
      raw_dir: paths.rawDir,
      warehouse_dir: paths.warehouseDir,
      duckdb_path: paths.duckdbPath,
      registry_path: paths.registryPath,
      connector_registry_path: paths.connectorRegistryPath,
      source_registry_path: paths.sourceRegistryPath,
      source_snapshot_manifest_path: paths.sourceSnapshotManifestPath,
      wiki_dir: paths.wikiDir,
    },
    duckdb,
    registry_file: registryFile,
    registry,
    sensitive_fields: summarizeSensitiveFields(registryRaw ?? {}),
    wiki_knowledge: wikiKnowledge,
    connector_registry_file: connectorRegistryFile,
    connectors,
    sources,
    embedding_health: embeddingHealth,
    lightrag_status: lightragStatus,
    workflow_progress: workflowProgress,
    config_health: configHealth,
    artifact_links: artifactLinks,
    large_excel: largeExcel,
    tasks,
    warnings: buildWarnings({
      duckdb,
      registryFile,
      connectorRegistryFile,
      sources,
      embeddingHealth,
      configHealth,
      lightragStatus,
      wikiKnowledge,
    }),
  };
}
