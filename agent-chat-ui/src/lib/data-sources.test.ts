import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { loadDataSourcesState, validateSourcePathInput } from "./data-sources";

async function createDataSourcesFixture() {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-sources-"));
  const dataDir = path.join(root, "data");
  const registryDir = path.join(dataDir, "source_registry");
  const exportDir = path.join(root, "exports");
  const rawDir = path.join(root, "raw");
  await mkdir(registryDir, { recursive: true });
  await mkdir(exportDir, { recursive: true });
  await mkdir(rawDir, { recursive: true });
  const registryPath = path.join(registryDir, "sources.json");
  const snapshotManifestPath = path.join(registryDir, "snapshots.jsonl");
  const sourceFile = path.join(exportDir, "sales.csv");
  await writeFile(sourceFile, "date,sku,qty\n2026-05-30,A001,1\n", "utf8");
  await writeFile(
    registryPath,
    JSON.stringify(
      {
        schema: "a2a_source_registry_v1",
        updated_at: "2026-05-30T10:00:00Z",
        supported_source_types: ["local_file", "wecom_wedrive_file"],
        sources: {
          sales_daily: {
            source_id: "sales_daily",
            display_name: "销售日报",
            source_type: "local_file",
            uri: sourceFile,
            allowed_root: exportDir,
            sync_mode: "on_demand",
            owner: "ops",
            sensitivity_level: "internal",
            freshness_sla: "24h",
            status: "active",
            credential_env_keys: [],
          },
          wedrive_daily: {
            source_id: "wedrive_daily",
            display_name: "微盘日报",
            source_type: "wecom_wedrive_file",
            uri: "wecom-wedrive://space1/file/file1",
            allowed_root: "",
            sync_mode: "on_demand",
            owner: "ops",
            sensitivity_level: "internal",
            freshness_sla: "4h",
            status: "failed",
            credential_env_keys: [],
            metadata: {
              space_id: "space1",
              file_id: "file1",
              file_name: "sales.xlsx",
            },
          },
        },
      },
      null,
      2,
    ),
    "utf8",
  );
  await writeFile(
    snapshotManifestPath,
    [
      JSON.stringify({
        snapshot_id: "20260530-100000-aaa",
        source_id: "sales_daily",
        source_type: "local_file",
        observed_at: "2026-05-30T10:00:00Z",
        raw_snapshot_path: path.join(
          rawDir,
          "snapshots",
          "sales_daily",
          "20260530-100000-aaa",
          "original.csv",
        ),
        row_count: 1,
        schema_hash: "hash-a",
        schema: { sales: ["date", "sku", "qty"] },
        sheet_names: ["sales"],
        status: "success",
        duckdb_dataset_slug: "sales_daily_a",
      }),
      JSON.stringify({
        snapshot_id: "20260530-110000-bbb",
        source_id: "sales_daily",
        source_type: "local_file",
        observed_at: "2026-05-30T11:00:00Z",
        raw_snapshot_path: path.join(
          rawDir,
          "snapshots",
          "sales_daily",
          "20260530-110000-bbb",
          "original.csv",
        ),
        row_count: 2,
        schema_hash: "hash-b",
        schema: { sales: ["date", "sku", "qty", "gmv"] },
        sheet_names: ["sales"],
        status: "success",
        duckdb_dataset_slug: "sales_daily_b",
      }),
    ].join("\n"),
    "utf8",
  );
  return {
    root,
    paths: {
      workspaceDir: root,
      dataDir,
      rawDir,
      sourceRegistryDir: registryDir,
      sourceRegistryPath: registryPath,
      snapshotManifestPath,
    },
    exportDir,
    sourceFile,
  };
}

test("data sources loader summarizes sources, snapshots, freshness, and schema drift", async () => {
  const { paths } = await createDataSourcesFixture();

  const state = await loadDataSourcesState({ paths });

  assert.equal(state.schema, "a2a_data_sources_v1");
  assert.equal(state.counts.sources, 2);
  assert.equal(state.counts.failed_sources, 1);
  assert.equal(state.counts.snapshots, 2);
  assert.equal(state.sources[0].source_id, "sales_daily");
  assert.equal(
    state.sources[0].last_snapshot?.snapshot_id,
    "20260530-110000-bbb",
  );
  assert.equal(state.sources[0].snapshot_count, 2);
  assert.deepEqual(state.sources[0].schema_diff.added_fields, ["gmv"]);
  assert.equal(state.sources[1].status, "failed");
});

test("source path validator rejects workspace escape and accepts allowlisted roots", async () => {
  const { paths, exportDir, sourceFile } = await createDataSourcesFixture();

  const allowed = validateSourcePathInput({
    workspaceDir: paths.workspaceDir,
    sourcePath: sourceFile,
    allowedRoot: exportDir,
  });
  const denied = validateSourcePathInput({
    workspaceDir: paths.workspaceDir,
    sourcePath: path.join(paths.workspaceDir, "..", "outside.csv"),
    allowedRoot: exportDir,
  });

  assert.equal(allowed.ok, true);
  assert.equal(denied.ok, false);
  assert.equal(denied.code, "path_outside_allowed_root");
});
