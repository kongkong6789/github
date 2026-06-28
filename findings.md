# P0/P1 Findings

## Initial Repository State

- The workspace is dirty and contains many modified/new files relevant to this task, including `src/a2a_ecommerce_demo/agent_tool_registry.py`, `agent-chat-ui/src/app/api/data-health/route.ts`, `agent-chat-ui/src/app/data-health/page.tsx`, and agent trace UI/API files.
- `TODO.md` confirms the same remaining P0/P1 items the user listed.
- Existing plans:
  - `docs/plans/2026-05-06-karpathy-fact-layer-design.md`
  - `docs/plans/2026-05-08-dynamic-agent-a2a-design.md`

## Design Direction

- P0 should extend the current DuckDB/Parquet fact layer rather than adding a parallel store.
- P0 front-end should build on existing `/api/data-health`, `/api/lightrag-status`, and trace panel surfaces.
- P1 should build on existing `agent_factory_tools.py`, `agent_tool_registry.py`, `permission_tools.py`, and `enterprise_audit_tools.py`.

## Code Findings

- `src/a2a_ecommerce_demo/fact_layer_tools.py` builds per-sheet marts in `_build_sheet_marts()` and global marts in `_refresh_global_marts()`.
- Existing global P0 marts already include `agg_sku_daily_sales`, `agg_warehouse_inventory`, `agg_inbound_outbound_daily`, and `agg_channel_sales`; missing inventory anomaly mart and explicit partition/index metadata.
- `tests/test_fact_layer_pipeline.py` has temporary-dir based integration tests and is the right place for inventory mart and partition tests.
- `agent-chat-ui/src/app/api/data-health/route.ts` already summarizes DuckDB, registry, large Excel outputs, and recent tasks; it can be extended to include workflow progress and artifact links.
- `agent-chat-ui/src/app/data-health/page.tsx` already uses Tailwind + shadcn-style `Button` and lucide icons, with a dense operational dashboard style.
- `src/a2a_ecommerce_demo/agent_tool_registry.py` is currently a static allowlist resolver; there is no persisted dynamic registry or lifecycle layer yet.
- `src/a2a_ecommerce_demo/agent_factory_tools.py` has deterministic template suggestions and saved prompt templates, so dynamic-agent creation can reuse its template library.

## Open Questions Resolved By Assumption

- No new git worktree will be created because relevant uncommitted changes are already present in the current workspace.
- Dynamic agent execution will start with deterministic/local-safe runtime paths if real LLM execution is unavailable in tests.

## ERP-First Connector Findings

- `TODO.md`, `README.md`, several docs, and `supervisor_app.py` still describe the product as cross-border/Amazon-oriented. P3 should be rewritten as domestic platform + ERP integration.
- The desktop 吉客云 package is a full business workflow skill plus Python API client. Hot-path A2A ingestion should use a narrow read-only adapter around its API/client modules, not the whole natural-language skill.
- The desktop 金蝶 package exposes K3 Cloud WebAPI login/query/view/save/submit/push flows. A2A should first reuse a session-based read-only client and gate all Save/Submit/Push actions behind approval.
- Existing `agent_tool_registry.py`, `enterprise_audit_tools.py`, `fact_layer_tools.py`, and `/api/data-health` are enough to land a connector governance layer without disrupting `business_tools.py`.
- Recommended flow: `connector adapter -> connector registry/audit/permission -> staging snapshot -> fact_layer_tools registration -> DuckDB marts -> business tools -> Agent`.

## P4 Sensitive Data Findings

- `enterprise_audit_tools.py` already redacts API keys, tokens, secrets, and passwords before writing `data/audit/events.jsonl`.
- `/api/data-health` already summarizes `dataset_registry.json`, recent tasks, connectors, and artifacts, making it the lowest-friction place to show whether sensitive field categories exist in registered datasets.
- Current need is not user-based access control. The useful internal guardrail is field-name classification plus customer PII value masking and audit metadata.
- Current local dataset registry does not yet expose matching sensitive field names, so `/api/data-health` correctly reports zero sensitive fields until customer /采购价 /财务字段 appear in registered datasets.

## P7 Engineering Guardrail Findings

- `scripts/repair_thread_archives.sh` had no PowerShell wrapper, and `scripts/reset_knowledge_state.ps1` had no Bash/macOS wrapper.
- `scripts/common.sh` had no PowerShell counterpart, so there was no reusable parity foundation for future Windows wrapper work.
- Remaining machine-specific markdown examples were concentrated in README and older docs: raw `D:\A2A`, fixed `C:\Program Files\nodejs`, and direct `.venv\Scripts` commands.
- P7 can be kept closed with one focused test: `python -m unittest tests.test_p7_engineering_guardrails`.

## P9 Workbench Findings

- The referenced previous conversation confirms P13 is complete and P9 was only a thin base with `task.list` / `task.show`.
- Existing route logic for `/api/data-health`, `/api/agent-traces`, and `/api/lightrag-status` lived directly inside route modules, so `/api/workbench` could not reuse it cleanly until loader helpers were extracted.
- The stable P9 contract should keep legacy API routes available for direct debugging while making frontend read paths use `workbench-client`.
- Scope protection belongs in the Workbench control plane: no `thread_id` / `task_id` / `agent_id` / `tool_name` means global task, audit, trace, and log history is withheld unless the caller passes `scope=global`.
- `approval.submit` can safely normalize Agent Inbox resume payloads, but actual resume submission still belongs to the existing LangGraph stream client; no external write capability is added.

## P12 Queue Findings

- P12 should be implemented as a Python backend reliability layer: the current durable task surface is `task_delegation_tools.py`, and `TASK_DIR` already centralizes `data/tasks`.
- Existing recovery only scans JSON task files for `queued` / `running`; there is no claim owner, heartbeat, retry accounting, event table, or idempotency key.
- The compatibility boundary is important: P10 task pages read `data/tasks/*.json`, so P12 should keep writing JSON task exports instead of forcing the UI to know SQLite.
- `agent-chat-ui` has no SQLite dependency. Avoid adding one just for P12 logs; keep `task_events` authoritative in Python/SQLite and expose it later through an API if the UI needs it.
- The safest incremental design is SQLite as the queue authority plus JSON as an export/detail document: enqueue/claim/heartbeat/retry/cancel live in SQLite, while workflow step details still append to the JSON task log.

## P14 Evidence Graph Findings

- `data/warehouse/dataset_registry.json` stores datasets as a mapping keyed by `dataset_slug`; records include source paths, manifest/quality paths, DuckDB path, `sheet_views`, field profiles, and wiki page paths.
- Task JSON files already carry report paths, `steps[].evidence`, risks, missing data, next actions, and `final_report.evidence_chain`.
- Reports include a markdown `## Evidence Chain` section with wiki pages, DuckDB marts, data gaps, and manifest/report paths; this can seed report/decision/risk edges.
- `wiki/datasets/**` and `wiki/decisions/**` are concrete filesystem paths and are enough for first-version wiki/decision nodes.
- Audit events contain structured `risk_level`, `data_sources`, `paths`, `task_id`, `tool_name`, `risks`, and metadata; use them for risk and sensitive-field nodes but do not place raw values in labels.
- The front-end has P10 task helpers in `agent-chat-ui/src/lib/tasks.ts` and dense operational page patterns in `/tasks`, `/data-health`, `/governance`, and `/logs`; P14 should match that utilitarian style.

## WeCom/ERP Live Data Recheck Findings

- Front-end thread `019e4d58-8a41-7073-a57d-1d17c7ad16b2` did call `query_wecom_smartsheet_records` successfully with the user-provided WeCom URL; the tool returned `live_read_only_mcp`, sheet `taDIvD`, and `raw_total_count=304`.
- WeCom formula fields are not materialized through the MCP response: live recheck returned 0 non-empty `品牌` rows and 0 non-empty `渠道名称` rows, but 297 rows had `渠道编码` and there were 63 unique channel codes. Channel code must be treated as the join key for brand/channel dimensions.
- The same thread then called `query_fact_layer_from_question` against `marts.agg_sku_daily_sales`; that DuckDB result is not real-time WeCom daily sales. Current DuckDB file mtime is 2026-05-15 and `marts.agg_sku_daily_sales` max `date_value` is 2026-04-23.
- `query_inventory_cost_reference` performs a real-time 吉客云 read: live recheck returned `inventory_row_count=3791`, but detailed `rows` are capped at 100. The full-brand conclusion must use `brand_expansion.summary`, not the first 100 rows.
- 金蝶 `supplier_procurement_terms` returned `FTaxPrice`, but `cost_reference.selected_value` is a reference for the derived SKU filter, not a brand-wide procurement price or final inventory accounting cost.
- 吉客云 Skill already contains `modules.reports.query_channel_sales_summary`, which is the right surface for 日期 + 渠道/店铺 + SKU 销量/金额. The A2A side should expose only this read-only wrapper for realtime SKU sales; broader吉客云 Skill write workflows remain outside Agent permissions.
- Current 吉客云 report AppKey may still return 0 rows when the report/吉智 BI permission is missing. That is a data/permission gap, not proof of zero sales.

## Runtime Capability Findings

- Existing Tool Registry already knows risk, read-only status, owner module, and allowed Agents, so a generic runtime discovery layer can reuse it instead of creating a second permission model.
- Skill Registry stores Skills as governed prompt/template bundles. Runtime invocation should therefore return an active Skill prompt bundle and tool allowlist, not pretend that a Skill is arbitrary executable Python.
- MCP/API governance already centralizes read-only/write policy and Agent Inbox confirmation. Runtime invocation should call through that policy first, then dispatch only allowed read-only capabilities.
- Uploaded MCP tools need policy-first onboarding: a user can register `mcp_url`/`mcp_url_env`, `mcp_tool_name`, risk metadata, and allowed callers, but external writes must remain disabled unless a future explicit approval executor is built.
- The correct user-facing promise is “all registered capabilities are discoverable and launchable through one entry point”; it is not “all uploaded tools can perform writes automatically.”

## S0.5 Security Governance Findings

- Root `.env` was removed from Git tracking while remaining local; `.gitignore` now ignores root env files and keeps `.env.example` committable.
- Thread archive doctor and repair now share stricter `tool_call_id` coverage checks for top-level and `values.messages` archives. `repair_thread_archives.py --write --confirm` generated local backups/checkpoint migration manifests and left JSON archives with no changed files.
- Front-end governance and evidence graph APIs now constrain user-provided paths with realpath-based allowlists before reading reports, task files, or imported Skill sources.
- MCP policy upsert derives write-like actions as high-risk, non-read-only, confirmation-required entries, and external writes remain disabled.
- Runtime Agent mounts default to direct/read-only tools; confirmation/write/destructive tools stay behind explicit approval paths.
- Shell dotenv parsing no longer uses `eval`; fact-layer CLI passes SQL/limit as data, and `query_fact_layer` uses positive fact-layer object validation.
- Project `skills/` is treated as runtime prompt/adapter surface only; guardrails reject env/config/cache/zip/temp artifacts in runtime Skill scans.
- Archive repair redaction is now idempotent: already-redacted plain or URL-encoded markers do not increment `sensitive_urls_redacted` or create false-positive dry-run work.
- S0.5 verification passed with `scripts/doctor.py --json`, targeted backend/frontend tests, `bash -n`, fact-layer CLI smoke, Skill artifact scan, and `./scripts/verify_all.sh`.

## P16 Source Registry Findings

- Referenced thread `019e677a-be65-72a2-9fb9-a007a9a50966` confirms the chosen P16 direction: enterprise WeCom Wedrive as the business-editable current source, local `raw/snapshots` as immutable evidence, COS/OSS deferred to optional archival mirroring, and LightRAG kept for semantic/decision context rather than numeric fact computation.
- Current project has no `.codegraph/` index; `codegraph` is installed but structural navigation for this pass is via `rg`, LSP-style symbol tools, and direct file reads unless the user later asks to initialize CodeGraph.
- Existing P16 TODO is still fully open. README already documents the intended P16 direction but marks source sync as planned.
- Existing source-adjacent code: `wecom_smartsheet_tools.py` already provides read-only MCP query and staging/DuckDB snapshot sync for WeCom smart sheets; `connector_tools.py` already syncs ERP connector snapshots to staging/DuckDB; `task_queue.py` can enqueue durable tasks; `enterprise_audit_tools.py` can record redacted audit events; `data-health-state.ts` is the right place to expose source freshness.
- Implementation should add a new backend `source_registry_tools.py` rather than folding P16 into connector registry: Source Registry spans local files/folders, manual upload, WeCom smart sheet, Wedrive, ERP snapshots, and future API/MCP sources.
- Wedrive real credentials/admin parameters are not available and should remain empty placeholders. The first implementation should expose metadata/config hooks and a testable read-only client seam, with no external write capability and no persisted access tokens or temporary download URLs.
- Landed architecture: Source Registry owns long-lived source identity; snapshot manifest owns immutable evidence versions; dataset registry/wiki/audit/task outputs all point back to `source_id` + `snapshot_id`.
- Wedrive production client remains a seam until tenant parameters are available; local verification can use `metadata.local_fixture_path`. Registry still supports blank WeCom admin fields and safe `space_id` / `file_id` placeholders.
- `/data-sources` is the PM-facing source console. `/data-health` only shows summary counts so the operational page stays dense and task-focused.
- Reference repositories were absorbed as docs/checklists only: Understand-Anything for optional local graph POC, Harness for workflow contract patterns, and AI Engineering From Scratch for eval/MCP/production checklist ideas.
