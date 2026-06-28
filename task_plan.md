# P0/P1 Completion Task Plan

## Goal

Land the remaining P0 data/front-end loop and P1 dynamic-agent platform items without overwriting the current in-progress work.

## Current Constraints

- Work in the current dirty workspace because many relevant files are already modified or newly added.
- Preserve all existing user changes.
- Use focused tests before production edits where practical.

## Phases

- [complete] Phase 1: Inspect current data, front-end, agent, and test surfaces.
- [complete] Phase 2: Add P0 fact-layer partition metadata and inventory anomaly mart tests.
- [complete] Phase 3: Implement P0 fact-layer partition metadata and inventory anomaly mart.
- [complete] Phase 4: Add P0 front-end progress/artifact-link API and UI tests or static checks.
- [complete] Phase 5: Implement P0 front-end progress and artifact links.
- [complete] Phase 6: Add P1 registry/hub/lifecycle/audit/template tests.
- [complete] Phase 7: Implement P1 dynamic agent registry, hub, lifecycle, trace/audit, and template persistence.
- [complete] Phase 8: Run focused and full verification; update TODO/docs if needed.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| `spawn_agent` rejected `fork_context=true` with explicit `agent_type` | Initial parallel explorer dispatch | Re-dispatched explorers without full-history fork and included repo context in prompts |
| System Python lacked `openpyxl` | Initial Python red test run | Re-ran with project `.venv/bin/python` |
| `./scripts/verify_python.sh` failed Ruff import ordering in `supervisor_app.py` | Full verification after implementation | Ran Ruff auto-fix on the file and re-ran full verification successfully |

## S0 Stabilization Extension

- [complete] Phase S0.1: Inspect LightRAG confirmation, embedding health, and checkpoint/archive surfaces.
- [complete] Phase S0.2: Add failing tests for HITL approval, embedding health, and checkpoint migration.
- [complete] Phase S0.3: Implement S0 stability helpers and integrate them.
- [complete] Phase S0.4: Run focused/full verification and update final status.

## S0 Verification

- `./scripts/verify_python.sh`: passed, 58 unittest cases plus Ruff and Pyright.
- `./node_modules/.bin/tsc --noEmit --pretty false`: passed.
- `esbuild src/lib/data-health.test.ts ... && node --test /tmp/data-health.s0.test.mjs`: passed, 3 node tests.
- `git diff --check`: passed.
- Runtime smoke: `/api/data-health` returned `embedding_health.status=success`, 7 workflow stages, and 190 artifacts.

## ERP-First P3/P6 Connector Extension

- [complete] Phase C1: Inspect current TODO/docs, tool registry, fact layer, and data-health surfaces.
- [complete] Phase C2: Add failing connector registry/tool/front-end health tests.
- [complete] Phase C3: Implement default 吉客云/金蝶 connector registry, read-only health, capability preview, and snapshot registration.
- [complete] Phase C4: Wire connector tools into supervisor and Agent allowlists.
- [complete] Phase C5: Update TODO/README/docs/supervisor wording from overseas marketplace defaults to domestic platform + ERP-first language.
- [complete] Phase C6: Extend `/api/data-health` and `/data-health` with connector status and artifact links.
- [complete] Phase C7: Run focused Python/TypeScript verification and record results.

## ERP-First P3/P6 Verification

- Red tests: connector registry/tool/front-end tests failed before implementation because modules and helpers were missing.
- Focused Python: `.venv/bin/python -m unittest tests.test_connector_registry tests.test_agent_tool_registry tests.test_supervisor_model_config` passed.
- Full Python: `./scripts/verify_python.sh` passed with 62 unittest cases, Ruff, and Pyright; only existing LangGraph deprecation warnings were emitted.
- TypeScript: `./node_modules/.bin/tsc --noEmit --pretty false` passed.
- Front-end helper tests: `esbuild src/lib/data-health.test.ts ... && node --test /tmp/data-health.connector-final2.test.mjs` passed, 4 node tests.
- Whitespace: `git diff --check` passed.
- Runtime smoke: `/api/data-health` returned `connector_registry_file.exists=true` and two connectors: `jackyun_erp`, `kingdee_erp`; Playwright snapshot of `/data-health` showed the `Connectors` stat card and `ERP Connectors` table.

## P4 Lightweight Sensitive Data Guardrail

- [complete] Phase P4.1: Inspect audit, registry, task trace, and data-health surfaces.
- [complete] Phase P4.2: Add red tests for field classification, masking, audit metadata, and data-health summary.
- [complete] Phase P4.3: Implement lightweight backend sensitive-field helpers and audit integration.
- [complete] Phase P4.4: Surface sensitive-field summary in `/api/data-health` and front-end helpers.
- [complete] Phase P4.5: Update TODO/README and run focused/runtime verification.

## P7 Engineering Guardrail Closeout

- [complete] Phase P7.1: Inventory cross-platform script pairs and machine-specific path examples.
- [complete] Phase P7.2: Add red guardrail tests for script parity and markdown path hygiene.
- [complete] Phase P7.3: Add missing macOS/Windows wrapper pairs and shared PowerShell helpers.
- [complete] Phase P7.4: Clean remaining markdown path examples to `<A2A_PROJECT_ROOT>` and update audit docs/TODO.
- [complete] Phase P7.5: Run focused/full verification.

## P9 Workbench Control Plane

- [complete] Phase P9.1: Confirm previous thread conclusion: P10/P11/P13 are landed; P9 only had thin `task.list` / `task.show` support.
- [complete] Phase P9.2: Add P9 red/green tests for the full method set, envelope/error shapes, scope protection, split trace data, logs, governance audit trimming, data health metadata, and approval resume payloads.
- [complete] Phase P9.3: Extract reusable `data-health`, `agent-traces`, and `lightrag-status` loaders from API routes.
- [complete] Phase P9.4: Expand `/api/workbench` to dispatch `task.list`, `task.show`, `agent.trace`, `data.health`, `governance.policy`, `approval.submit`, and `logs.tail`.
- [complete] Phase P9.5: Migrate read paths in `/data-health`, `/governance`, `/logs`, `/tasks`, and the chat trace panel to `workbench-client`.
- [complete] Phase P9.6: Update TODO/README and run focused, build, whitespace, and runtime verification.

## P9 Verification

- Focused front-end helper tests: `workbench-contract`, `workbench-server`, `data-health`, `governance`, `logs`, and `tasks` passed, 23 node tests.
- TypeScript: `./scripts/with-env-node.sh ./node_modules/.bin/tsc --noEmit --pretty false` passed.
- Production build: `npm run build` passed; existing lint warnings remain in pre-existing Fast Refresh / unused `_` locations.
- Whitespace: `git diff --check` passed.
- Runtime smoke: `/api/workbench` returned the unified envelope and scope warning for unscoped `agent.trace`; `/data-health`, `/governance`, `/logs`, and `/tasks` returned HTTP 200.
- Browser smoke: Playwright rendered `/data-health` with Workflow, ERP Connectors, Artifact Links, Dataset Registry, and 最近任务 sections.

## P12 SQLite Durable Queue

- [complete] Phase P12.1: Inspect the current JSON task queue, P12 TODO scope, and task page compatibility boundary.
- [complete] Phase P12.2: Add red tests for durable enqueue, claim lock, heartbeat, completion/failure/cancel, crash reclaim, idempotency, terminal states, and concurrent claim behavior.
- [complete] Phase P12.3: Implement `src/a2a_ecommerce_demo/task_queue.py` with SQLite schema migrations and transactional queue operations.
- [complete] Phase P12.4: Wire `task_delegation_tools.py` to the durable queue while keeping `data/tasks/*.json` as the compatibility/export view.
- [complete] Phase P12.5: Add a dry-run-first JSON-to-SQLite migration script.
- [complete] Phase P12.6: Update TODO/README/docs and run focused/full verification.

## P12 Verification

- Red tests failed as expected before implementation because `src.a2a_ecommerce_demo.task_queue` did not exist.
- Focused queue and compatibility tests passed: `.venv/bin/python -m unittest tests.test_task_queue tests.test_recoverable_workflow_queue`.
- Related workflow/router/evidence tests passed: `.venv/bin/python -m unittest tests.test_supervisor_model_config tests.test_intent_router_and_safety tests.test_decision_evidence_chain`.
- Migration dry-run passed: `.venv/bin/python scripts/migrate_tasks_to_sqlite.py --limit 3`.
- Full Python verification passed: `./scripts/verify_python.sh` with 102 unittest cases, Ruff, and Pyright.

## P14 Evidence Graph

- [completed] Phase P14.1: Inspect P14 TODO scope, dataset registry, wiki/report/task/audit data shapes, and frontend task page patterns.
- [completed] Phase P14.2: Add red backend tests for graph schema, node/edge de-dupe, source path links, task/report scope filters, and sensitive label redaction.
- [completed] Phase P14.3: Implement `src/a2a_ecommerce_demo/evidence_graph_tools.py` and wire tool registry/supervisor access if required.
- [completed] Phase P14.4: Add front-end graph loader/API tests for filters, href routing, and risk highlighting data.
- [completed] Phase P14.5: Implement `/api/evidence-graph`, `/evidence-graph`, and task/report entry links without changing P10 visual intent.
- [completed] Phase P14.6: Update TODO/README/planning docs and run Python, TypeScript, build, whitespace, and browser verification.

## P15 LLM Wiki Knowledge Compounding

- [completed] Phase P15.1: Add red tests for wiki scaffold, index/log maintenance, lint health, decision archive, and claim/evidence records.
- [completed] Phase P15.2: Implement wiki lifecycle tools and initial schema/index/log wiki files.
- [completed] Phase P15.3: Wire P15 tools into the supervisor catalog and Agent registry.
- [completed] Phase P15.4: Surface wiki knowledge health through `/api/data-health` and the data-health page.
- [completed] Phase P15.5: Update README/TODO/progress and run focused/full verification.

## WeCom/ERP Live Data Recheck

- [completed] Phase R1: Restore interrupted thread context from conversation `019e4877-26e8-7370-aabe-1c3975718647`.
- [completed] Phase R2: Inspect front-end thread `019e4d58-8a41-7073-a57d-1d17c7ad16b2`, audit logs, and tool payloads.
- [completed] Phase R3: Add regression tests for WeCom channel-code fallback, DuckDB realtime wording, inventory brand-expansion summaries, and procurement price scope.
- [completed] Phase R4: Implement tool/prompt guardrails and run live read-only verification.
- [completed] Phase R5: Add the dedicated 吉客云 sales-summary read-only wrapper, route realtime SKU sales to it, wire governance/Agent permissions, and update README/TODO/progress docs.

## Runtime Capability / OpenClaw-Like Skill-MCP Invocation

- [completed] Phase RC1: Clarify boundary from user request: discover and invoke later-created Skill/MCP flexibly, while keeping external writes behind confirmation.
- [completed] Phase RC2: Add red tests for runtime capability discovery, active Skill prompt-bundle invocation, read-only local tool execution, write-MCP confirmation, and uploaded MCP policy registration.
- [completed] Phase RC3: Implement `runtime_capability_tools.py` with `list_runtime_capabilities`, `invoke_runtime_capability`, and `register_runtime_mcp_tool`.
- [completed] Phase RC4: Wire runtime tools into Tool Registry, Agent allowlists, supervisor catalog, Skill allowlist, and Agent prompts.
- [completed] Phase RC5: Update README/TODO/progress/findings and run focused/full verification.

## Skill Library Governance

- [completed] Phase SL1: Add red tests for `skills/<folder>/SKILL.md` discovery in `/governance`.
- [completed] Phase SL2: Add red tests for folder Skill metadata in active Skill injection and runtime capability prompt bundles.
- [completed] Phase SL3: Implement Skill Library scanning, import/update form integration, and folder metadata propagation.
- [completed] Phase SL4: Update README/TODO/progress and run focused/full verification plus browser smoke.

## S0.5 Security Governance And Context Hygiene

- [completed] Phase S0.5.1: Remove tracked root `.env`, sanitize examples/docs/tests, add credential hygiene and doctor guardrails.
- [completed] Phase S0.5.2: Repair thread archive protocol checks, add redaction/compaction, and reuse the strict tool-message state machine in local archive writes.
- [completed] Phase S0.5.3: Lock front-end file path boundaries for governance Skill import and evidence graph report/task access.
- [completed] Phase S0.5.4: Harden MCP/Governance policy writes and Runtime Capability MCP HTTP error handling.
- [completed] Phase S0.5.5: Ensure runtime Agent tool mounts are direct/read-only by default and confirmation tools stay behind approval.
- [completed] Phase S0.5.6: Remove shell/dotenv eval, harden fact-layer query execution, and add injection regressions.
- [completed] Phase S0.5.7: Minimize Skill Library runtime contents and add guardrails for write-capable/temporary artifacts.
- [completed] Phase S0.5.8: Strengthen file/state persistence and dependency maintainability within the feasible local boundary.
- [completed] Phase S0.5.9: Synchronize README, architecture, runbook, reference docs, TODO, findings, and progress.
- [completed] Phase S0.5.10: Run targeted and full verification; fix any regressions before reporting completion.

## P16 Source Registry And Incremental Source Sync

- [completed] Phase P16.1: Confirm current TODO/README/thread scope and inspect source, snapshot, WeCom, ERP, task, doctor, and Workbench surfaces.
- [completed] Phase P16.2: Add red backend tests for source registry CRUD, path/token guardrails, snapshot idempotency/schema drift, adapter workflow, and doctor checks.
- [completed] Phase P16.3: Implement Source Registry, snapshot manifest, local/manual/WeCom/Wedrive/ERP adapters, source sync workflow, audit/wiki/task records, and Tool Registry wiring.
- [completed] Phase P16.4: Add red front-end/Workbench tests for source listing, snapshot history, schema diff, sync now, path errors, and data-health freshness.
- [completed] Phase P16.5: Implement `/api/data-sources`, `/data-sources`, Workbench methods/client helpers, and data-health source freshness.
- [completed] Phase P16.6: Update TODO/README/runbook/progress and run focused/full verification.

## P17 Reference Repository Absorption

- [completed] Phase P17.1: Read referenced threads and align P17 scope with TODO/README.
- [completed] Phase P17.2: Add red tests for Agent templates, dynamic template drafts, handoff/QA events, Supermemory policy, marketplace templates, task UI parsing, and desktop harness doctor checks.
- [completed] Phase P17.3: Implement Agent template schema/files, dynamic Agent template drafting, task handoff/QA helpers, Supermemory policy, external memory guards, marketplace template loading, and doctor harness availability.
- [completed] Phase P17.4: Update `/governance` template market and `/tasks/[taskId]` handoff/QA UI surfaces.
- [completed] Phase P17.5: Update TODO/README/architecture/progress and run focused/full verification.
