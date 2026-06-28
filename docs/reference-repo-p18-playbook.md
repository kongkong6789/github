# P18 Reference Platform Playbook

P18 merges six external reference projects into this workspace using the same integration model as [53AI Hub](https://github.com/53ai/53aihub): keep one local control plane, register external platforms, and only call sidecars when they are explicitly configured.

None of the six projects replace the current LangGraph + DuckDB + Wiki + LightRAG core. They are absorbed in three modes:

| Mode | Projects | Runtime behavior |
| --- | --- | --- |
| Embedded | DuckDB, Karpathy LLM Wiki | Already implemented in `fact_layer_tools.py` and `wiki_lifecycle_tools.py` |
| Embedded + optional sidecar | LightRAG | Local tools remain primary; official LightRAG Server is optional on `:9621` |
| Optional sidecar | RuoYi AI, MaxKB, MiroFish | Read-only HTTP bridge through `platform_integration_tools.py` when env URLs are set |

## Project mapping

| Project | Role in this workspace | Primary local entry |
| --- | --- | --- |
| [duckdb/duckdb](https://github.com/duckdb/duckdb) | Numeric fact layer | `query_fact_layer`, `list_registered_datasets` |
| [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) | Semantic retrieval over wiki/cleaned docs | `query_lightrag`, `query_official_lightrag` |
| [karpathy/llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) | Durable markdown knowledge codebase | `ensure_wiki_knowledge_scaffold`, `lint_wiki_knowledge_base` |
| [666ghj/MiroFish](https://github.com/666ghj/MiroFish) | Scenario simulation reports | `simulate_decision_scenarios` locally; optional `MIROFISH_API_URL` |
| [ageerle/ruoyi-ai](https://github.com/ageerle/ruoyi-ai) | Enterprise agent/workflow hub | Optional `RUOYI_AI_API_URL`; LangGraph stays orchestrator |
| [1Panel-dev/MaxKB](https://github.com/1Panel-dev/MaxKB) | Enterprise RAG/agent portal | Optional `MAXKB_API_URL`; local LightRAG stays default |

## Registry and tools

Committed registry:

```text
config/reference_platforms.json
config/reference_platform.schema.json
config/agent_templates/*.json
```

Runtime tools:

```text
list_reference_platforms
check_reference_platform_health
route_knowledge_stack
query_external_platform_readonly
```

Routing discipline:

- Numeric facts, inventory, sales, finance, filters, Top N -> DuckDB
- Semantic background, entity relations, long-form docs -> LightRAG + wiki
- Durable business understanding, SOP, claim/evidence lifecycle -> Karpathy LLM Wiki
- Scenario comparison / what-if reports -> local `simulate_decision_scenarios`; MiroFish sidecar only when configured
- External enterprise portals -> RuoYi AI / MaxKB only as read-only sidecars, never as fact sources

## Optional sidecar setup

Copy `.env.example` and configure only the platforms you actually run:

```text
RUOYI_AI_API_URL=http://127.0.0.1:26039
MAXKB_API_URL=http://127.0.0.1:8080
MIROFISH_API_URL=http://127.0.0.1:5001
```

Health checks:

```powershell
cd <A2A_PROJECT_ROOT>
./scripts/doctor.ps1
.venv/Scripts/python -c "from src.a2a_ecommerce_demo.platform_integration_tools import check_reference_platform_health; print(check_reference_platform_health())"
```

Reference source sync (optional, local only):

```powershell
./scripts/sync_reference_platforms.ps1
```

Cloned snapshots land in `_references/` which is gitignored. The main repo keeps only registry metadata and integration code.

## Agent templates added in P18

| Template | Source inspiration | Use |
| --- | --- | --- |
| `mirofish_scenario_report` | MiroFish report workflow | Evidence-first multi-scenario decision memo |
| `ruoyi_workflow_operator` | RuoYi AI workflow nodes | Structured handoff across data/knowledge/decision steps |
| `maxkb_knowledge_operator` | MaxKB RAG pipeline | Document ingest + retrieval QA with local stack first |

Templates live in `config/agent_templates/` and can be copied into `data/agent_templates/` during bootstrap.

## Explicit non-goals

- Do not vendor full Java/Python platform trees into the main runtime path.
- Do not let RuoYi AI, MaxKB, or MiroFish replace DuckDB numeric facts or ERP read-only evidence.
- Do not expose sidecar write/admin APIs to ordinary analysis Agents.
- Do not treat external platform answers as audit evidence without local DuckDB/wiki/LightRAG citations.

## Acceptance checklist

- [x] Registry documents all six requested projects.
- [x] Embedded stack remains DuckDB + Wiki + LightRAG.
- [x] Sidecar URLs are optional and degrade gracefully.
- [x] Doctor reports configured/unconfigured platform status.
- [x] Tests cover registry, routing, and unavailable sidecar behavior.
