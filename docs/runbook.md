# A2A Workbench Runbook

## Health Checks

Use these commands from the project root:

```bash
./scripts/health_backend.sh
./scripts/health_lightrag.sh
curl -s http://127.0.0.1:3000/api/lightrag-status
```

Expected LightRAG status for an idle system:

```text
pending: 0
processing: 0
failed: 0
pipeline_busy: false
```

`processed` is a moving count, not a fixed release number.

## When LightRAG Shows Pending Or Processing

Short-lived pending/processing during an explicit sync is normal. It is not normal for a plain existing-data analysis question to create new pending documents.

If it happens:

1. Check whether a background task was created in `data/tasks`.
2. Check `/api/lightrag-status`.
3. Ask the app to diagnose LightRAG failures before retrying.
4. Do not repeatedly click retry in LightRAG WebUI.

## LightRAG Cleanup Confirmation

LightRAG cleanup and timeout recovery are preview-first:

- `auto_recover_lightrag_timeouts()` returns `confirmation_required` with an approve/reject interrupt by default.
- `cleanup_confirmed_lightrag_failed_history()` returns `confirmation_required` by default.
- The frontend renders a confirmation card for tool results with `requires_confirmation=true`.
- No retry page is written, no LightRAG document is submitted, and no failed record is deleted until the user approves the interrupt or supplies the CLI confirmation token shown in the preview.

The confirmation only affects LightRAG failed records. It must not delete local `wiki/`, DuckDB, Parquet, or processed LightRAG documents.

## Background Task Rules

Use background workflow only when the user explicitly asks to process new material:

```text
我刚上传了 raw Excel，帮我清洗、入库并同步知识库
```

Existing-data analysis should stay read-only:

```text
基于所有已有数据，分析 5/6 月 UNOVE 销售提升决策
```

Background tasks are recoverable. Task JSON files live in `data/tasks`, and backend startup automatically calls `recover_workflow_queue()` unless `A2A_RECOVER_WORKFLOW_QUEUE_ON_STARTUP=0`.

Recovery behavior:

- `queued` tasks are re-enqueued.
- `running` tasks are treated as interrupted and re-enqueued with `recovered_from_interrupted_run=true`.
- Completed successful/warning subtasks are skipped when the workflow resumes.
- `success`, `completed` legacy tasks, `failed`, and `cancelled` tasks are not restarted automatically.

## Source Registry And Snapshots

Source Registry stores long-lived read sources in `data/source_registry/sources.json`.
Snapshot history is append-only in `data/source_registry/snapshots.jsonl`, and raw evidence lands under:

```text
raw/snapshots/<source_id>/<YYYYMMDD-HHMMSS>-<short_hash>/original.<ext>
```

First-time registration examples:

```bash
.venv/bin/python -m src.a2a_ecommerce_demo.source_registry_tools register-source \
  --source-id tmall_sales_daily \
  --display-name "天猫销售日报导出目录" \
  --source-type local_folder \
  --uri "$PWD/data/exports/tmall" \
  --allowed-root "$PWD/data/exports/tmall" \
  --owner ops \
  --freshness-sla 24h

.venv/bin/python -m src.a2a_ecommerce_demo.source_registry_tools register-source \
  --source-id wedrive_sales_file \
  --display-name "微盘销售日报" \
  --source-type wecom_wedrive_file \
  --owner ops \
  --freshness-sla 4h \
  --metadata-json '{"space_id":"","file_id":"","file_name":""}'
```

For enterprise WeCom Wedrive, keep `space_id` / `file_id` / admin credential env vars blank until the real tenant parameters are available. Do not paste temporary download URLs, `access_token`, `scode`, or API keys into registry fields.

Common operations:

```bash
.venv/bin/python -m src.a2a_ecommerce_demo.source_registry_tools list-sources
.venv/bin/python -m src.a2a_ecommerce_demo.source_registry_tools sync-source tmall_sales_daily
.venv/bin/python -m src.a2a_ecommerce_demo.source_registry_tools run-workflow tmall_sales_daily
.venv/bin/python -m src.a2a_ecommerce_demo.source_registry_tools set-status tmall_sales_daily paused
.venv/bin/python -m src.a2a_ecommerce_demo.source_registry_tools set-status tmall_sales_daily active
.venv/bin/python -m src.a2a_ecommerce_demo.source_registry_tools rebind-source tmall_sales_daily \
  --uri "$PWD/data/exports/tmall_next" \
  --allowed-root "$PWD/data/exports/tmall_next"
```

Schema drift handling:

- `schema_hash_changed` means the snapshot is recorded, but downstream interpretation needs review.
- Check `/data-sources` for added/removed fields, changed sheets, row count, and latest raw path.
- Confirm new field meanings before promoting the new dataset to recurring reports.

Rollback and cleanup:

- Old reports keep pointing at their original `source_id` + `snapshot_id`; do not edit old manifest rows.
- To rerun from an older snapshot, use its `raw_snapshot_path` as evidence and register a new derived dataset/report from that path.
- P16 does not auto-delete old snapshots. Cleanup must be preview-first and keep `snapshots.jsonl` history intact.

## Verification

Run the full local preflight before a real business trial:

```bash
git ls-files .env
.venv/bin/python scripts/doctor.py --json
.venv/bin/python -m unittest tests.test_source_registry tests.test_source_snapshots tests.test_source_sync_workflow
.venv/bin/python scripts/repair_thread_archives.py
bash -n scripts/common.sh scripts/query_fact_layer.sh
./scripts/query_fact_layer.sh --sql "SELECT 1 AS ok" --limit 1
find skills \( -name '.env' -o -name 'config.py' -o -name '_tmp*' -o -name '*.zip' -o -name '__pycache__' -o -name '.pytest_cache' \) -print
./scripts/verify_all.sh
```

Expected S0.5 result:

- `git ls-files .env` prints nothing.
- `doctor.py --json` has no `fail` checks; service-port warnings are acceptable when the stack is intentionally stopped.
- `repair_thread_archives.py` reports no orphan tool messages and no changed JSON archive files after repair.
- `find skills ...` prints nothing.
- `verify_all.sh` exits 0.

Credential rotation is an external control-plane action. After any real key has appeared in Git, docs, tests, terminal logs, or thread archives, the credential owner must rotate it in the relevant vendor console, then update only the local ignored `.env`.

Targeted Python verification:

```bash
./scripts/verify_python.sh
```

Targeted frontend type check:

```bash
cd agent-chat-ui
./node_modules/.bin/tsc --noEmit --pretty false
```
