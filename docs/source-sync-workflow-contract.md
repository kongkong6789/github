# P16 Source Sync Workflow Contract

P16 source sync is a read-only, append-only workflow. It never writes back to ERP, platform exports, WeCom Wedrive, WeCom smartsheet, or any external source system.

## Workflow Steps

| Step | Owner | Input | Output | Failure Recovery |
| --- | --- | --- | --- | --- |
| `source_watcher` | `auto_workflow_agent` | `source_id` | source metadata, current freshness | Ask for source id or mark source missing |
| `snapshotter` | `data_cleaning_agent` | registered source | immutable raw snapshot or `skipped_unchanged` | Preserve old snapshots, write failed audit event |
| `schema_profiler` | `data_cleaning_agent` | raw snapshot | row count, sheet names, schema hash, field profile | Mark quality warning, keep snapshot evidence |
| `quality_gate` | `quality_gate_agent` | profile + previous snapshot | schema drift and review questions | Require human review for changed fields/sheets |
| `fact_registrar` | `data_cleaning_agent` | raw snapshot + profile | dataset registry entry with `source_id` and `snapshot_id` | Leave snapshot available for retry |
| `wiki_ingest` | `wiki_ingest_agent` | source + snapshot | `wiki/sources/<source_id>.md`, `wiki/log.md` entry | Write audit problem, retry after wiki path fix |
| `lightrag_sync` | `wiki_ingest_agent` | wiki source page | semantic evidence candidate | Keep DuckDB as numeric source of truth |
| `verifier` | `auto_workflow_agent` | task log + registry + manifest | final task status and remediation | Mark task failed/recoverable with next action |

## Agent Boundaries

- `auto_workflow_agent`, `data_cleaning_agent`, and `wiki_ingest_agent` may start source sync or ingest tools.
- `decision_agent` and `company_strategy_agent` may read source registry and snapshot history, but must not start source sync during read-only analysis.
- `sync_source` and `run_source_sync_workflow` are confirmation/background tools in Tool Registry. They are not visible to `decision_agent`.

## Acceptance Fields

Every completed source sync should leave:

- `data/source_registry/sources.json` updated with `last_sync`.
- `data/source_registry/snapshots.jsonl` appended for changed content.
- `raw/snapshots/<source_id>/<snapshot_id>/original.<ext>` for changed content.
- `data/warehouse/dataset_registry.json` entry with `source_id`, `snapshot_id`, and `source_snapshot_path`.
- `wiki/sources/<source_id>.md` and a `wiki/log.md` source snapshot entry.
- `data/tasks/<task_id>.json` if run via `run_source_sync_workflow`.
- `data/audit/events.jsonl` event with redacted metadata.

## Reference Pattern Absorption

This contract absorbs team-pattern ideas from [revfactory/harness](https://github.com/revfactory/harness): pipeline ownership, fan-out/fan-in review, producer-reviewer gates, supervisor handoff, and explicit validation. It does not add Harness as a runtime dependency and does not require Claude Code folder conventions.
