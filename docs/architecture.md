# A2A Workbench Architecture

## Multi-Agent Runtime

The project already uses a LangGraph multi-agent architecture:

```text
agent-chat-ui
  -> LangGraph StateGraph entry router
  -> top_company_brain_supervisor
  -> data_pipeline_team / decision_team / strategy_team
  -> specialized agents
  -> tools
  -> DuckDB / wiki / LightRAG / task state / reports
```

The product boundary is:

- Read-only analysis uses existing DuckDB, wiki, and LightRAG evidence.
- Background ingestion is only for explicit new material, raw, Excel, cleaning, wiki ingest, or sync requests.
- Decision agents should not start raw cleaning, wiki ingest, LightRAG sync, or long-running background workflows.
- Data pipeline and workflow agents own side-effectful processing.

## Core Guards

- `intent_router.classify_user_intent()` is the shared intent classifier for supervisor routing and workflow tools.
- Tool Registry v2 is the primary permission registry for specialist Agent tools. `agent_tool_registry.AGENT_TOOL_ALLOWLISTS` remains as a legacy compatibility layer over registry entries.
- Runtime Agent mounting defaults to direct/read-only tools. Confirmation, external-write, and destructive tools stay behind explicit approval flows and are not mounted into normal `create_react_agent` execution.
- `agent_tool_registry.validate_agent_tool_policy()` blocks read-only analysis Agents from receiving raw ingest, LightRAG sync, confirmation, external-write, or background workflow tools.
- `task_delegation_tools.start_company_workflow_task()` rejects existing-data analysis goals before creating a background task.
- `task_delegation_tools.recover_workflow_queue()` restores `queued` and interrupted `running` tasks from `data/tasks` on backend startup.
- LightRAG destructive cleanup tools return `confirmation_required` previews with approve/reject interrupts by default; CLI execution can still use an explicit confirmation token.
- Frontend local-file APIs resolve realpaths under allowlisted roots before reading reports, task files, or imported Skill sources.
- `query_fact_layer()` accepts only SELECT/CTE queries over the registered fact-layer allowlist and rejects external DuckDB read/load/attach/copy patterns.
- SQLite durable queue state is the task source of truth; JSON task files are retained as export/compatibility state.
- JSON task and sync state writes use atomic replacement with fsync and stale-lock recovery to reduce partial-write risk.

## Memory Vs RAG

- DuckDB and ERP read-only queries are the only sources for numeric operating facts.
- Wiki and LightRAG manage local documents, rules, historical reports, claims, and evidence discovery.
- Supermemory is optional hosted memory for user/team preferences, project status, and retrospective context only.
- Supermemory `profile` / `recall` / `context` are read-only MCP policy entries; recalled memory must not be written into business `evidence`.
- Supermemory writes go through human confirmation and `external_memory_tools` sensitive-field scanning. ERP rows, customer data, purchase prices, supplier quotes, financial details, inventory details, and private smartsheet URLs are blocked before any hosted write.

## Next Architecture Work

- Move the recoverable local queue to a dedicated durable worker process if concurrent users or multi-machine deployment becomes necessary.
- Split larger frontend thread surfaces into smaller provider/view modules as the product UI grows.
