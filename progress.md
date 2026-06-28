# P0/P1 Progress

## 2026-05-22 Session Recovery / Frontend 500 Closeout

- Restored conversation `019e4d6f-0a9b-7702-93ca-c43996693540`; the main code/docs work for Runtime Capability / OpenClaw-like Skill-MCP invocation had already landed and was verified in that session.
- Picked up the final interrupted issue: `http://127.0.0.1:3000/` returned `500 Internal Server Error`.
- Root cause evidence from `frontend.err.log`: repeated `EPERM: operation not permitted, scandir .../agent-chat-ui/src/app` from the Next dev process, while filesystem ownership, flags, and normal shell reads were healthy.
- Resolution: restarted the frontend through `./scripts/start_frontend.sh`, which stops the stale process and clears `.next`; the dev server then recompiled `/` successfully.
- Fresh verification in this session:
  - `curl` returned HTTP 200 for `/`, `/api/lightrag-status`, and `/api/workbench` `data.health`.
  - In-app Browser rendered `http://127.0.0.1:3000/` with title `Agent Chat`, meaningful app content, no `Internal Server Error`, no Next error overlay, and no console error/warn entries.
  - UI smoke interaction filled and cleared the chat textarea successfully.

## 2026-05-22 Backend EPERM Interruption

- Investigated the front-end toast `后端执行中断 / An internal error occurred` after a 吉客云库存 prompt.
- Root cause from `langgraph-server.log`: the run failed in `pre_model_hook` before tool execution because the running LangGraph process hit `PermissionError: [Errno 1] Operation not permitted` while reading `data/skill_registry/registry.json`.
- Related evidence: the same backend process also logged EPERM loading `.langgraph_api/.langgraph_checkpoint.2.pckl`, `.langgraph_api/.langgraph_checkpoint.3.pckl`, and moving `.langgraph_api/.langgraph_ops.pckl.tmp`.
- Normal shell and project Python could read those files, so this was a stale running process / macOS EPERM state rather than bad file contents or a 吉客云 API failure.
- Resolution: restarted LangGraph with `./scripts/start_backend.sh --host 127.0.0.1 --port 2024 --timeout 90`; stale `.langgraph_api/*.pckl.tmp` was cleared by checkpoint preflight.
- Fresh verification:
  - `http://127.0.0.1:2024/ok` returned 200.
  - A minimal LangGraph run on `ecommerce_agent` completed successfully and returned `OK`, proving `pre_model_hook` can read Skill registry again.
  - `query_erp_live_snapshot("jackyun_erp", "inventory_stock", brand=Unove柔诺伊, warehouse_scope=all)` returned `status=success`, `row_count=3791`, and `brand_expansion` summary without warnings.

## 2026-05-21 Multi-Agent Debug Review

- Started a stabilization/debug review because small runtime issues have been accumulating after multiple feature phases.
- Loaded `systematic-debugging`, `code-review`, `dispatching-parallel-agents`, and `planning-with-files`.
- Re-read `README.md`, `TODO.md`, `task_plan.md`, `findings.md`, and `progress.md` before touching code.
- Initial process finding: README/TODO describe the project as landed and internally usable, so this pass should focus on runtime stability, docs/code consistency, and verification gates rather than adding new product surface area.
- Four-agent review split findings across docs/process, backend graph/tool registry, frontend runtime, and verification scripts.
- Backend fixes landed:
  - Added `run_fact_layer_registration_task` to supervisor imports/catalog and auto workflow registry/confirmation metadata.
  - Repaired model-input and offline thread repair handling for OpenAI-style `role: "assistant"` tool-call messages.
  - Expanded MCP/API policy for ERP list/test and WeCom list/test/query/sync tools while keeping read-only listing non-mutating.
  - Normalized WeCom smart sheet success mode to `live_read_only_mcp`.
  - Persisted the WeCom `channel_daily_sales` source config with docid + 5 sheet IDs and env-referenced MCP URL; `list_wecom_smartsheet_sources` now surfaces the source even when the private MCP URL is not set.
- Frontend fixes landed:
  - Unified `verify_frontend.sh` now dynamically discovers `*.test.ts(x)` files, works with macOS bash 3.2, and uses `npm run build`.
  - Archive continuation no longer lets stale local archive values hide a newly started streamed run.
  - `/api/local-threads` skips individual corrupt/disappearing JSON files instead of failing the whole endpoint.
  - Local archived-thread delete now checks HTTP status and surfaces failures instead of removing UI optimistically.
- Focused verification passed so far:
  - `./scripts/verify_frontend.sh --unit-only` with 53 node tests.
  - `cd agent-chat-ui && ./scripts/with-env-node.sh ./node_modules/.bin/tsc --noEmit --pretty false`.
  - `.venv/bin/python -m unittest tests.test_supervisor_model_config tests.test_thread_repair_tools tests.test_agent_tool_registry tests.test_mcp_governance_tools tests.test_wecom_smartsheet_tools tests.test_p7_engineering_guardrails`.
  - `.venv/bin/ruff check` on the touched backend and regression test files.
- Final verification passed:
  - `./scripts/verify_all.sh` with 137 Python unittest cases, Ruff, Pyright, 53 front-end node tests, TypeScript check, and Next production build.
  - `./scripts/verify_frontend.sh` after removing the newly introduced hook dependency warning; remaining build warnings are pre-existing Fast Refresh / ESLint config warnings.
  - `.venv/bin/python -m unittest tests.test_p7_engineering_guardrails` and `.venv/bin/ruff check tests/test_p7_engineering_guardrails.py` after aligning the PowerShell frontend verifier with the macOS/Linux verifier.
  - Restarted backend with `./scripts/start_backend.sh --host 127.0.0.1 --port 2024 --timeout 90` and frontend with `./scripts/start_frontend.sh --host 127.0.0.1 --port 3000 --timeout 90`.
  - Smoke checks: backend `/ok` returned healthy, front-end `/` returned HTTP 200, `/api/local-threads` returned HTTP 200, `/api/governance` returned HTTP 200.
  - Browser smoke passed on `/` and `/governance` with no console warnings or errors.

## 2026-05-22 WeCom/ERP Live Data Recheck

- Restored previous conversation `019e4877-26e8-7370-aabe-1c3975718647` and continued the interrupted debug thread.
- Inspected front-end thread `019e4d58-8a41-7073-a57d-1d17c7ad16b2`; it successfully read WeCom MCP, then fell back to DuckDB because `品牌` and `渠道名称` formula fields were null.
- Live WeCom recheck: 304 rows read from sheet `taDIvD`; `品牌` non-empty rows = 0, `渠道名称` non-empty rows = 0, `渠道编码` non-empty rows = 297, unique channel codes = 63.
- Live ERP recheck: 吉客云 inventory brand expansion returned 3,791 inventory rows for Unove柔诺伊, but tool details are capped to 100 rows; `brand_expansion.summary` now surfaces the full-brand totals for Agent analysis.
- Confirmed DuckDB `marts.agg_sku_daily_sales` is not real-time daily sales for this prompt: DuckDB file mtime is 2026-05-15 and max `date_value` is 2026-04-23.
- Added regression tests and guardrails so future Agent runs:
  - use `渠道编码` as the WeCom join key when formula dimension fields are blank;
  - do not describe DuckDB `agg_sku_daily_sales` as real-time WeCom daily sales;
  - use `brand_expansion.summary` for full-brand/full-warehouse inventory conclusions;
  - treat 金蝶 `FTaxPrice` as SKU-scoped procurement reference, not brand-wide cost.
- Added `query_jackyun_channel_sales_summary` as a narrow read-only wrapper around the registered 吉客云 Skill `modules.reports.query_channel_sales_summary` workflow.
- Wired the sales-summary wrapper into ERP routing, Agent allowlists, Tool Registry, MCP/API policy, supervisor catalog, and live ERP prompt guardrails.
- The supported grain is 日期 + 渠道/店铺 + SKU + 销量/金额. If the 吉客云 report permission returns 0 rows, the report must state that as a sales-summary permission/filtering gap rather than inventing daily sales.
- Live smoke: `query_jackyun_channel_sales_summary` executed against the registered 吉客云 Skill, returned 0 rows with redacted warnings for missing report/吉智 BI permission, and did not expose the raw AppKey.
- Verification passed: focused connector/registry/MCP/supervisor tests, `git diff --check`, and `./scripts/verify_python.sh` with 150 unittest cases, Ruff, and Pyright.

## 2026-05-22 Runtime Capability Layer

- User asked for OpenClaw-like flexible invocation so later-created or uploaded MCP/Skill capabilities can be used by Agents without hard-coding every function name.
- Added `src/a2a_ecommerce_demo/runtime_capability_tools.py`:
  - `list_runtime_capabilities` discovers local Tool Registry entries, Skill Registry entries, and MCP/API policy entries.
  - `invoke_runtime_capability` invokes read-only local tools, returns active Skill prompt bundles, maps read-only MCP policy entries to local handlers, and can call configured MCP JSON-RPC tools.
  - `register_runtime_mcp_tool` writes uploaded MCP/API tool policy entries with `external_write_enabled=false` by default.
- Safety boundary landed: read-only capabilities can execute; write, destructive, high-risk, unknown, or unapproved capabilities return `confirmation_required` and reuse Agent Inbox approval instead of performing external writes.
- Wired runtime tools into `agent_tool_registry.py`, `skill_registry_tools.py`, `supervisor_app.py`, top supervisor safe tools, `data_agent`, `inventory_agent`, `decision_agent`, `company_strategy_agent`, `auto_workflow_agent`, and `agent_factory_agent`.
- Updated Agent prompts so requests to call future Skill/MCP/API first use `list_runtime_capabilities`, then `invoke_runtime_capability`; uploaded MCP registration goes through `register_runtime_mcp_tool`.
- Added tests covering discovery, local read-only invocation, active Skill prompt bundle invocation, MCP local handler dispatch, write-MCP confirmation, uploaded MCP registration, Skill allowlist acceptance, Tool Registry metadata, and supervisor catalog wiring.
- Verification passed: `.venv/bin/python -m unittest tests.test_runtime_capability_tools tests.test_skill_registry_tools tests.test_agent_tool_registry tests.test_supervisor_model_config`, `./scripts/verify_python.sh` with 157 unittest cases plus Ruff/Pyright, and `git diff --check`.
- Runtime smoke in the real workspace listed `agent_skill` + `mcp_api` capabilities including `skill:jackyun_erp_readonly_connector_skill`, `skill:kingdee_erp_readonly_connector_skill`, `skill:unove_domestic_channel_strategy`, and `mcp:list_erp_live_query_capabilities`; invoking `mcp:list_erp_live_query_capabilities` returned `mode=mcp_local_tool`, `permission_allowed=true`, `read_only=true`.

## 2026-05-23 Skill Library Governance

- Added `skills/` as the project Skill Library. `/governance` scans direct child folders that contain `SKILL.md`, shows registered/unregistered state, and can prefill the import/update form.
- Migrated the current active Skills into `skills/`: `jackyun_erp_readonly_connector_skill`, `kingdee_erp_readonly_connector_skill`, and `unove_domestic_channel_strategy`. Registry metadata now points at these folder-backed Skills.
- Added source-missing recovery: Skill Registry now detects missing `source_skill_path`, surfaces `source missing` in `/governance`, and can restore the original `skills/<folder>` from the managed copy.
- Added `skill.registry.json` metadata to folder Skills so re-imports preserve `skill_id`, scenarios, read-only tool allowlists, and output schemas.
- Folder imports still create draft Skill Registry records first; activation remains an explicit approval/status step before any Agent uses the Skill.
- Imported folder Skills keep a full managed copy under `data/skill_registry/imports/<skill_id>/`, while original `skills/<folder>/` files are left untouched.
- Active Skill injection and `invoke_runtime_capability("skill:<skill_id>")` now expose `source_type`, `source_skill_path`, and `managed_skill_dir`, so multi-agent runs can identify the folder-backed Skill context.

## 2026-05-25 Skill Reset

- Deleted the 吉客云 and 金蝶 project Skills completely from the project workspace: Skill Registry records, active templates, managed copies, `skills/` source folders, imported wiki copies, and `vendor/desktop-skills` reference copies.
- `/governance` now shows only `unove_domestic_channel_strategy` in Skill Registry and Skill Library; 吉客云/金蝶 are ready to be re-added from the web UI.

## 2026-05-25 吉客云/金蝶 Project Skill Re-add

- Re-added 吉客云 and 金蝶 as project folder Skills under `skills/jackyun_erp_readonly_connector_skill` and `skills/kingdee_erp_readonly_connector_skill`, excluding local `.env`, `config.py`, and `data/` runtime caches.
- Added project-owned top-level `SKILL.md` wrappers and `skill.registry.json` metadata so imports preserve stable skill ids, read-only connector allowlists, scenarios, and output schemas.
- Imported both folder Skills through `/api/governance` and activated them; `/governance` now reports 3 registered active Skill Library entries: UNOVE, 吉客云, and 金蝶.
- Runtime capability discovery now exposes `skill:jackyun_erp_readonly_connector_skill` and `skill:kingdee_erp_readonly_connector_skill` as active read-only agent Skill prompt bundles for multi-agent use.
- Investigated thread `019e5cf8-b7f4-7c42-bdbc-87647d9dfd06`: live ERP failed because connector runtime still pointed at stale `/Users/seven/Desktop/jackyun-skill-project` and `.env` did not define `JACKYUN_APP_KEY` / `JACKYUN_APP_SECRET`.
- Rebound stale connector runtime paths to project Skill Library folders and added an env-only `config.example.py` for the 吉客云 project Skill; health now reports the project Skill directory is present and only real credentials remain to be configured.
- Migrated 吉客云 OpenAPI env values into local `.env` without printing secrets, restarted the backend, and verified `get_erp_connector_health("jackyun_erp")` is `ready`.
- Live read-only smoke passed through the project Skill folder: `master_data/warehouses` returned `status=success`, and `inventory_stock` with SKU barcode `8809669502427` returned `status=success` via `erp.stockquantity.get`.

## 2026-05-18

- Loaded required workflow skills: `using-superpowers`, `brainstorming`, `dispatching-parallel-agents`, `subagent-driven-development`, `test-driven-development`, `planning-with-files`, `writing-plans`, `web-design-engineer`, `verification-before-completion`, and `requesting-code-review`.
- Confirmed the repository has significant uncommitted work that must be preserved.
- Started four explorer agents:
  - Backend data layer
  - Front-end progress/artifact UI
  - Agent platform
  - Test and run commands
- Created this planning file set.
- Added and passed P0 backend tests for `marts.inventory_partition_index`, `marts.inventory_anomalies`, and natural-language anomaly routing.
- Verified `validate_agent_tool_registry(_tool_catalog())` after adding `query_inventory_anomalies`.
- Added P0 fact-layer partition fields (`effective_month`, `warehouse_partition`, `sku_hash`, `sku_hash_bucket`), `marts.inventory_partition_index`, and `marts.inventory_anomalies`.
- Added `query_inventory_anomalies` and routed Chinese anomaly questions such as negative inventory, inbound/outbound imbalance, no-sales high inventory, and stockout risk to the anomaly mart.
- Added P0 front-end health helpers/API/UI for 7-stage workflow progress and artifact links covering reports, DuckDB, dataset registry, wiki pages, derived exports, LightRAG state, and manifests.
- Added P1 `dynamic_agent_hub` with draft, permission preview, confirm, run, list/get, update, pause/disable, rollback, audit, and template promotion.
- Wired dynamic Agent tools into `agent_factory_agent` and clarified the one-sentence create -> permission preview -> human confirmation -> execution flow in its prompt.
- Verification passed:
  - `./scripts/verify_python.sh`
  - `./node_modules/.bin/tsc --noEmit --pretty false`
  - `./node_modules/.bin/esbuild src/lib/data-health.test.ts --bundle --platform=node --format=esm --outfile=/tmp/data-health.test.mjs && node --test /tmp/data-health.test.mjs`
- Runtime smoke passed on existing Next dev server at `http://localhost:3000/data-health`; hydrated page displayed workflow progress, LightRAG/DuckDB/dataset status, and artifact links.

## 2026-05-18 S0

- Added S0 red tests for HITL approval shape, LightRAG interrupt rejection, checkpoint directory preflight, checkpoint pickle migration manifest, and embedding health.
- Added `human_approval_tools` as the reusable approve/reject interrupt foundation used by LightRAG destructive recovery.
- Upgraded `auto_recover_lightrag_timeouts` to emit Agent Inbox-compatible interrupt payloads and to respect approve/reject decisions; legacy `confirmation_token` remains for CLI compatibility.
- Added `checkpoint_tools` with `.langgraph_api` writable preflight, stale `*.pckl.tmp` cleanup, and structured raw pickle migration manifests.
- Wired backend startup through `prepare_langgraph_checkpoint_dir()` before launching `langgraph dev`.
- Added `/api/data-health` embedding health output and `/data-health` Embedding card with config status, timeout/balance root causes, timeout budget, and observed local status-read latency.
- Verification passed:
  - `./scripts/verify_python.sh` with 58 unittest cases, Ruff, and Pyright.
  - `./node_modules/.bin/tsc --noEmit --pretty false`.
  - `./node_modules/.bin/esbuild src/lib/data-health.test.ts --bundle --platform=node --format=esm --outfile=/tmp/data-health.s0.test.mjs && node --test /tmp/data-health.s0.test.mjs`.
  - `git diff --check`.
- Runtime smoke passed: `/api/data-health` returned `embedding_health.status=success`, 7 workflow stages, and 190 artifact links.

## 2026-05-19 ERP-First Connector Work

- Loaded `brainstorming`, `planning-with-files`, `test-driven-development`, and `verification-before-completion`.
- Confirmed the workspace is dirty with many existing P0/P1/S0 changes; this pass will preserve them and only add scoped connector/docs/front-end changes.
- Started C1/C2: inspect current TODO/docs, supervisor prompts, fact layer registration, agent tool registry, and data-health API/UI surfaces.
- Added red tests for connector registry defaults, connector health/preview, connector snapshot fact-layer registration, Agent allowlist boundaries, and data-health connector artifact links.
- Red tests failed as expected because connector modules/helpers did not exist and allowlists/data-health helpers were not wired.
- Added default 吉客云/金蝶 connector registry, connector tools, fact-layer connector snapshot tagging, supervisor catalog wiring, and `/data-health` connector summary UI.
- Focused green verification passed:
  - `.venv/bin/python -m unittest tests.test_connector_registry tests.test_agent_tool_registry`
  - `./node_modules/.bin/esbuild src/lib/data-health.test.ts --bundle --platform=node --format=esm --outfile=/tmp/data-health.connector-green.test.mjs && node --test /tmp/data-health.connector-green.test.mjs`
- Updated TODO/README/docs/supervisor prompts from overseas marketplace defaults to domestic platform + ERP-first language.
- Full verification passed after one Ruff import-sort fix:
  - `./scripts/verify_python.sh` with 62 unittest cases, Ruff, and Pyright.
  - `./node_modules/.bin/tsc --noEmit --pretty false`.
  - `./node_modules/.bin/esbuild src/lib/data-health.test.ts --bundle --platform=node --format=esm --outfile=/tmp/data-health.connector-final2.test.mjs && node --test /tmp/data-health.connector-final2.test.mjs`.
  - `git diff --check`.
- Runtime smoke passed: generated `data/warehouse/connector_registry.json`, `/api/data-health` reported two connectors, and Playwright showed the `/data-health` Connectors stat card plus ERP Connectors table.

## 2026-05-19 P4 Lightweight Sensitive Data Guardrail

- Loaded `brainstorming`, `planning-with-files`, `test-driven-development`, and `verification-before-completion`.
- User confirmed this should be a lightweight internal-PM guardrail, not a heavy RBAC system.
- Working design: classify sensitive fields by field name, mask customer personal data in values, audit usage by category, and surface dataset-level sensitive-field summary in data health.
- Added backend `sensitive_data_tools.py` with customer PII masking, procurement price / finance classification, and audit metadata that excludes row values.
- Wired the tools into supervisor catalog and Agent allowlists for data, strategy, decision, and workflow agents.
- Updated Agent prompts so sensitive-field usage is actively classified, audited, and masked instead of only passively available as tools.
- Extended `/api/data-health` and `/data-health` with `sensitive_fields`, a Sensitive Fields stat card, and a dataset-level sensitive field table.
- Focused verification passed:
  - `.venv/bin/python -m unittest tests.test_sensitive_data_tools tests.test_agent_tool_registry tests.test_supervisor_model_config`
  - `.venv/bin/ruff check src/a2a_ecommerce_demo/sensitive_data_tools.py tests/test_sensitive_data_tools.py tests/test_agent_tool_registry.py tests/test_supervisor_model_config.py`
  - `./node_modules/.bin/esbuild src/lib/data-health.test.ts --bundle --platform=node --format=esm --outfile=/tmp/data-health.p4-layout.test.mjs && node --test /tmp/data-health.p4-layout.test.mjs`
  - `./node_modules/.bin/tsc --noEmit --pretty false`
  - `git diff --check`
- Runtime smoke passed on `http://127.0.0.1:3000/data-health`: Sensitive Fields card and 字段级敏感数据 section render, `Skill / MCP 显示` remains visible, and the previous `businessTaskTemplates is not defined` runtime error is absent.

## 2026-05-19 P7 Engineering Guardrail Closeout

- Loaded `brainstorming`, `planning-with-files`, `test-driven-development`, and `verification-before-completion`.
- Scope: finish remaining P7 TODOs by enforcing shell/PowerShell script parity and removing machine-specific Windows path examples from README/TODO/docs markdown.
- Added red guardrail test `tests/test_p7_engineering_guardrails.py`.
- Red test failed as expected:
  - Missing script pairs: `common.ps1`, `repair_thread_archives.ps1`, `reset_knowledge_state.sh`.
  - Markdown still contained historical `D:\A2A`, fixed Node path, `.venv\Scripts`, or `powershell.exe` examples.
- Added `scripts/common.ps1`, `scripts/repair_thread_archives.ps1`, and `scripts/reset_knowledge_state.sh`.
- Cleaned README and docs markdown path examples to `<A2A_PROJECT_ROOT>` and updated the cross-platform path audit doc to point at the P7 guardrail test.
- Verification passed:
  - `bash -n scripts/common.sh scripts/repair_thread_archives.sh scripts/reset_knowledge_state.sh scripts/start_backend.sh scripts/start_frontend.sh scripts/start_fullstack.sh scripts/stop_backend.sh scripts/stop_frontend.sh scripts/stop_fullstack.sh scripts/start_lightrag_server.sh scripts/stop_lightrag_server.sh scripts/health_backend.sh scripts/health_lightrag.sh scripts/install_lightrag.sh scripts/query_fact_layer.sh scripts/register_fact_layer.sh scripts/sync_lightrag.sh scripts/verify_python.sh`
  - `.venv/bin/ruff check tests/test_p7_engineering_guardrails.py`
  - `.venv/bin/python -m unittest tests.test_p7_engineering_guardrails`
  - `./scripts/verify_python.sh`
  - `git diff --check`

## 2026-05-20 P9 Workbench Control Plane

- Loaded `brainstorming`, `planning-with-files`, `test-driven-development`, `react-best-practices`, and `verification-before-completion`.
- Read the referenced parent session `019e40a2-3a3f-7d41-8de2-e7256818eec5`; confirmed the prior conclusion that P13 was complete and P9 only had a thin `task.list` / `task.show` base.
- Added P9 Workbench tests for the full method set, unified envelope/error metadata, scope guards, split trace payloads, data health metadata, governance audit trimming, log tailing, and `approval.submit` Agent Inbox resume payload normalization.
- Extracted reusable loaders:
  - `agent-chat-ui/src/lib/agent-traces.ts`
  - `agent-chat-ui/src/lib/data-health-state.ts`
  - `agent-chat-ui/src/lib/lightrag-status.ts`
  - `agent-chat-ui/src/lib/workbench-server.ts`
- Updated `/api/workbench` to reuse existing helpers instead of duplicating business logic.
- Migrated read paths for `/data-health`, `/logs`, `/governance`, task pages, and chat trace panel to `workbench-client`; governance write actions remain on `/api/governance`.
- Focused verification passed:
  - `./scripts/with-env-node.sh ./node_modules/.bin/esbuild src/lib/workbench-contract.test.ts src/lib/workbench-server.test.ts src/lib/data-health.test.ts src/lib/governance.test.ts src/lib/logs.test.ts src/lib/tasks.test.ts --bundle --platform=node --format=esm --outdir=.tmp-test '--external:node:*' && ./scripts/with-env-node.sh node --test .tmp-test/workbench-contract.test.js .tmp-test/workbench-server.test.js .tmp-test/data-health.test.js .tmp-test/governance.test.js .tmp-test/logs.test.js .tmp-test/tasks.test.js`
  - `./scripts/with-env-node.sh ./node_modules/.bin/tsc --noEmit --pretty false`
- Final verification passed:
  - Focused P9/frontend tests: 23 node tests passed.
  - `npm run build` passed after clearing stale `.next` once; the final run passed with only existing lint warnings.
  - `git diff --check` passed.
  - Restarted frontend with `./scripts/start_frontend.sh --port 3000 --host 127.0.0.1 --timeout 60`.
  - Runtime smoke passed: `/api/workbench` returned a scoped envelope warning for unscoped `agent.trace`, and `/data-health`, `/governance`, `/logs`, `/tasks` all returned HTTP 200.
  - Playwright browser smoke rendered `/data-health` with Workflow, ERP Connectors, Artifact Links, Dataset Registry, and 最近任务 sections.

## 2026-05-20 P12 SQLite Durable Queue

- User chose to skip the first real business trial for now and land P12 directly.
- Loaded `brainstorming`, `planning-with-files`, `test-driven-development`, and `verification-before-completion`.
- Confirmed P12 scope from `TODO.md`: add SQLite durable queue tables and operations while preserving the existing JSON task log compatibility layer.
- Confirmed current implementation is JSON files plus in-process background threads in `task_delegation_tools.py`; no SQLite queue module exists yet.
- Confirmed the front-end task pages can stay on the JSON compatibility view for P12; there is no Node SQLite dependency in `agent-chat-ui`.
- Added `src/a2a_ecommerce_demo/task_queue.py` with SQLite migrations for `tasks`, `task_events`, `task_artifacts`, `task_claims`, `task_retries`, and `schema_migrations`.
- Added durable queue operations for enqueue, claim, heartbeat, current step, event/artifact append, complete, fail/retry, cancel, expired-claim reclaim, and idempotency reuse.
- Wired `task_delegation_tools.py` so JSON task creation/saves mirror into SQLite, background workers claim and heartbeat through the queue, startup recovery reclaims expired claims, and `list/get` can read SQLite-only tasks.
- Added `scripts/migrate_tasks_to_sqlite.py`, default dry-run with explicit `--write` for imports.
- Updated `TODO.md`, `README.md`, and `docs/task-delegation-workflow.md` for the landed P12 design.
- Verification passed:
  - `.venv/bin/python -m unittest tests.test_task_queue tests.test_recoverable_workflow_queue`
  - `.venv/bin/python -m unittest tests.test_supervisor_model_config tests.test_intent_router_and_safety tests.test_decision_evidence_chain`
  - `.venv/bin/python scripts/migrate_tasks_to_sqlite.py --limit 3`
  - `./scripts/verify_python.sh` with 102 unittest cases, Ruff, and Pyright.

## 2026-05-20 P14 Evidence Graph

- User asked to formally land every P14 TODO item.
- Loaded `brainstorming`, `planning-with-files`, `test-driven-development`, `react-best-practices`, and `verification-before-completion`.
- Confirmed P14 is the only unchecked item in the P9-P14 route.
- Sampled local data sources for graph construction:
  - `data/warehouse/dataset_registry.json`
  - `wiki/datasets/**`
  - `wiki/decisions/**`
  - `data/tasks/*.json`
  - `data/reports/*.md`
  - `data/audit/events.jsonl`
- Design direction: Python backend tool plus TypeScript front-end loader share the same node/edge schema; graph is evidence navigation only, not a DuckDB computation engine or LightRAG replacement.
- Added backend evidence graph tools, agent registry entries, and supervisor catalog exposure for `build_evidence_graph`, `list_evidence_graph_nodes`, and `list_evidence_graph_edges`.
- Added front-end evidence graph loader, `/api/evidence-graph`, `evidence.graph` workbench method, `/evidence-graph` page, and task/report entry links.
- Focused checks passed so far: backend evidence graph/registry/supervisor unittests, front-end evidence graph/workbench/tasks node tests, and TypeScript `tsc --noEmit`.
- Final verification passed: `./scripts/verify_python.sh`, all front-end node tests, `tsc --noEmit`, `npm run build`, API smoke for `/api/evidence-graph` and workbench `evidence.graph`, and browser smoke for `/evidence-graph` plus a real task detail page.
- Updated `TODO.md` and `README.md` to mark P14 landed; next route is a real business trial run rather than another P9-P14 implementation phase.

## 2026-05-20 P15 LLM Wiki Knowledge Compounding

- User asked to land every P15 TODO item.
- Loaded `brainstorming`, `planning-with-files`, `test-driven-development`, and `verification-before-completion`.
- Added red backend tests for wiki scaffold, schema/index/log creation, wiki lint health, review-question generation, decision archive, and claim/evidence lifecycle.
- Implemented `src/a2a_ecommerce_demo/wiki_lifecycle_tools.py` with:
  - `ensure_wiki_knowledge_scaffold`
  - `refresh_wiki_index`
  - `append_wiki_log_event`
  - `lint_wiki_knowledge_base`
  - `generate_wiki_review_questions`
  - `register_wiki_claim_evidence`
  - `archive_decision_to_wiki`
- Wired P15 tools into Tool Registry Agent allowlists and the supervisor tool catalog.
- Generated the initial P15 files: `docs/wiki_schema.md`, `wiki/AGENTS.md`, `wiki/log.md`, refreshed `wiki/index.md`, and wrote `data/wiki_knowledge_health.json`.
- Extended `/api/data-health` and `/api/workbench` `data.health` through the shared data-health state loader with `wiki_knowledge` status, schema/index/log presence, claim gaps, orphan/index gaps, stale/contradicted claim counts, warnings, examples and review questions.
- Added the `/data-health` Wiki Knowledge card and detail section.
- Updated `TODO.md` and `README.md` so P15 is marked landed and the project is described as `LLM Wiki + DuckDB 事实层 + LightRAG 检索 + 多 Agent + ERP 实时兜底 + 治理审计`.
- Current wiki health after refresh/lint: `status=warning`, `page_count=127`, `indexed_count=126`, `missing_frontmatter_count=87`, `unsourced_claim_count=13`, `orphan_count=0`, `missing_index_count=0`; warnings come from legacy wiki pages that predate the P15 frontmatter/evidence discipline.
- Verification passed:
  - `.venv/bin/python -m unittest tests.test_wiki_lifecycle_tools tests.test_agent_tool_registry tests.test_supervisor_model_config`
  - `./scripts/verify_python.sh` with 122 unittest cases, Ruff and Pyright.
  - `./scripts/with-env-node.sh ./node_modules/.bin/esbuild src/lib/data-health.test.ts --bundle --platform=node --format=esm --outfile=.tmp-test/data-health.p15-final.test.js && ./scripts/with-env-node.sh node --test .tmp-test/data-health.p15-final.test.js`
  - `./scripts/with-env-node.sh ./node_modules/.bin/tsc --noEmit --pretty false`
  - `npm run build` passed with only pre-existing ESLint warnings.
  - `git diff --check`

## 2026-05-27 S0.5 Security Governance And Context Hygiene

- Loaded `brainstorming`, `test-driven-development`, `planning-with-files`, and `verification-before-completion`.
- Accepted the S0.5 TODO section as the execution contract: credentials/Git hygiene, archive repair/redaction, front-end path boundaries, MCP policy validation, Agent tool mounting, shell/SQL safety, Skill Library trimming, persistence/dependency maintainability, and docs synchronization.
- Confirmed the workspace is already dirty with many user/project changes; this pass will preserve existing changes and edit only S0.5-related files.
- Started Phase S0.5.1 by recording the implementation plan and security findings before adding focused guardrail tests and production fixes.
- Resumed from goal `019e6216-a704-74e0-9a19-47afd332a94e`: S0.5 is not complete yet. `task_plan.md` still has S0.5.1 in progress and S0.5.2-S0.5.10 pending, while `TODO.md` acceptance checkboxes remain open.
- Verified current S0.5 implementation state: `git ls-files .env` and `git diff -- .env` produced no output, `scripts/doctor.py --json` returned 0 fail / 3 expected service-port warnings, `scripts/repair_thread_archives.py --write --confirm` created local backups and checkpoint migration manifests without modifying JSON archives, `bash -n` and fact-layer CLI smoke passed, Skill artifact scan printed no disallowed files, frontend S0.5 bundled tests passed, and `./scripts/verify_all.sh` exited 0.
- Fixed verification issues found during full preflight: Ruff import ordering in `src/a2a_ecommerce_demo/connector_tools.py` and `tests/test_agent_tool_registry.py`, plus Pyright-only test typing in `tests/test_agent_tool_registry.py` and `tests/test_connector_registry.py`.
- Error log: an initial Perl one-liner intended to bulk-check TODO S0.5 boxes failed with a quoting syntax error and made no file changes; the retry used a Ruby section-limited replacement successfully.
- Updated `TODO.md`, `task_plan.md`, `findings.md`, README, architecture, runbook, reference analysis, and vendored Skill docs to mark S0.5 complete and record the preflight commands.
- Added a red/green regression for archive redaction idempotence after repair dry-run still counted already-redacted URL markers. Fixed `thread_repair_tools` so plain and URL-encoded `***REDACTED***` markers are preserved without false-positive `sensitive_urls_redacted` counts; `tests.test_thread_repair_tools` and repair dry-run now report clean.

## 2026-05-30 P16 Source Registry And Incremental Source Sync

- Loaded `using-superpowers`, `brainstorming`, `test-driven-development`, and `planning-with-files`; `verification-before-completion` will be loaded before final completion claims.
- Restored context from thread `019e677a-be65-72a2-9fb9-a007a9a50966`: P16 should prioritize enterprise WeCom Wedrive Source Adapter + local `raw/snapshots`; COS/OSS remains optional later archival mirroring; LightRAG remains useful for semantic evidence and decision context, not numeric computation.
- Confirmed current P16 TODO section is open and broad: Source Registry model, snapshot manifest, local/manual/Wedrive/WeCom/ERP adapters, durable workflow, frontend/data-health/governance visibility, doctor checks, runbook, and verification.
- CodeGraph index is missing in this checkout; proceeding with `rg`, current tests, and direct file reads while preserving the dirty worktree.
- Added `src/a2a_ecommerce_demo/source_registry_tools.py` with Source Registry JSON, snapshot JSONL, immutable `raw/snapshots`, local/manual/Wedrive fixture/WeCom smartsheet/ERP readonly adapters, source sync workflow, wiki/audit/dataset-registry writes, status changes, path rebind, and CLI commands.
- Wired Source Registry tools into supervisor catalog, Tool Registry/Agent allowlists, intent routing, doctor, Data Health, Workbench `source.list/source.show/source.sync`, `/api/data-sources`, `/data-sources`, and the chat header navigation.
- Added focused backend and frontend tests for source CRUD, credential/path guardrails, snapshot idempotency/schema drift, adapter workflow, read-only intent boundaries, Workbench source listing, schema diff, and path validation.
- Added docs/runbook coverage, source workflow contract, reference repo playbook, and ignored Understand-Anything POC output directories.
- Verification passed on 2026-05-30:
  - `.venv/bin/python -m unittest tests.test_source_registry tests.test_source_snapshots tests.test_source_sync_workflow`
  - `./scripts/verify_python.sh` with 181 unittest cases, Ruff, and Pyright.
  - `npm test` with 65 front-end node tests.
  - `cd agent-chat-ui && ./scripts/with-env-node.sh ./node_modules/.bin/tsc --noEmit`
  - `cd agent-chat-ui && npm run build`
  - `.venv/bin/python scripts/doctor.py --json` returned 0 fail checks; service/source-registration warnings are expected while optional services and real sources are not running/registered.
  - `./scripts/verify_all.sh`
  - `git diff --check`
  - Browser/API smoke for `http://127.0.0.1:3000/data-sources`, `/api/data-sources`, and workbench `source.list`.

## 2026-06-01 P17 Reference Repository Absorption

- User asked to read thread `019e80c7-df49-7360-8756-e8fc6c5a20b9`, then UI-focused thread `019e7670-0e91-72b1-a243-fa2082bf1d28`, and land the P17 TODO items.
- Confirmed P17 scope from the first thread: do not merge `supermemory`, `agency-agents`, or `harness-anything` wholesale; absorb them as Agent templates, read-only memory context, marketplace templates, and approval-first harness boundaries.
- Confirmed UI direction from the second thread: governance/task pages should show operational state clearly, using the existing WorkbenchShell and dense PM-facing tables/cards rather than a marketing surface.
- Added P17 red/green tests for seeded Agent templates, dynamic Agent drafts from templates, handoff/QA task events, Supermemory MCP policy, external memory sensitive blocking/approval, marketplace summaries, task detail parsing, and doctor desktop harness availability.
- Added `data/agent_templates/agent_template.schema.json` and six draft evidence-first templates: `china_ecommerce_operator`, `supply_chain_strategist`, `fpa_analyst`, `paid_media_auditor`, `compliance_auditor`, and `data_consolidation_agent`.
- Added `draft_dynamic_agent_spec_from_template()` so `dynamic_agent_hub` can create a draft spec from `data/agent_templates/<id>.json` while filtering write/high-risk tools through the existing dynamic-agent read-only allowlist.
- Added standardized task queue event helpers for `handoff.created`, `qa.pass`, `qa.fail`, and `qa.escalated`; task detail parsing and UI now expose handoff, QA verdict, evidence paths, retry count, and next actions.
- Added Supermemory policy defaults for read-only `profile`, `recall`, `context` and confirmation-only `save_memory`; `.env.example` now documents the optional Supermemory env keys.
- Added `external_memory_tools.py` for context-only recall audits, save-memory confirmation previews, and blocking ERP/customer/purchase-price/financial/inventory/private-smartsheet content before hosted writes.
- Added `data/mcp_marketplace/templates/` with CLI JSON, WPS report quality, and PPT quality review templates; `/governance` now has a template market tab and can prefill MCP/API policy fields from a template.
- Added doctor desktop harness availability checks so non-Windows platforms mark WPS/Photoshop/Illustrator harnesses unavailable instead of failing.
- Updated README, TODO, architecture, progress, and task plan to mark P17 first batch landed while keeping lower-priority reference-repo ideas as future backlog.
