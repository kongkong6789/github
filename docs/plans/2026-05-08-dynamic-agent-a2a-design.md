# Dynamic Agent + A2A Full Rollout Design

## Goal

Land two production-style capabilities into the current project:

1. Dynamic executable agents that can be created from user intent and invoked immediately without manually editing the static supervisor graph for every new role.
2. A standardized external A2A layer so this project can call remote agent services and can also expose its own agents/tasks over a local HTTP API.

## Design Principles

- Keep the current static supervisor graph as the stable control plane.
- Add a dynamic runtime hub inside that control plane instead of recompiling the whole graph per agent.
- Use structured agent specs, not free-form prompt blobs.
- Reuse current permission, audit, task, DuckDB, Obsidian, and LightRAG layers.
- Default to multi-brand scope. No agent should assume one fixed brand unless explicitly constrained.

## Main Components

### 1. Agent Registry

Store reusable `AgentSpec` JSON documents under `data/agent_registry/`.

Fields:

- `agent_id`
- `name`
- `role`
- `goal`
- `prompt`
- `tool_allowlist`
- `input_schema`
- `output_schema`
- `routing_hints`
- `data_scope`
- `brand_scope`
- `execution_mode`
- `remote_endpoint`
- `status`
- `version`

### 2. Dynamic Runtime Hub

Add a fixed runtime layer that:

- loads an `AgentSpec`
- resolves allowed tools from a shared tool catalog
- instantiates a local agent runtime
- invokes it immediately

Execution modes:

- `local_dynamic` — real LLM + tool runtime
- `remote_a2a` — proxy call to another agent service
- `local_mock` — deterministic test/runtime fallback

### 3. Tool Catalog

Centralize project tools into a shared registry so both:

- dynamic local agents
- A2A-exposed agents

can resolve the same tool names consistently.

### 4. A2A Protocol Layer

HTTP JSON endpoints:

- `GET /a2a/health`
- `GET /a2a/agents`
- `POST /a2a/agents/register`
- `POST /a2a/invoke`
- `POST /a2a/tasks`
- `GET /a2a/tasks/{task_id}`
- `GET /a2a/tasks/{task_id}/events`

### 5. A2A Client Layer

Local tools for:

- remote agent discovery
- remote invoke
- remote async task launch
- remote task polling
- local connector registry

### 6. Routing Integration

Add:

- `dynamic_agent_hub_agent`
- `a2a_gateway_agent`

to the supervisor so front-end users can request:

- “create a new agent for X and run it now”
- “call a remote agent for X”

without manual graph edits.

## Verification

- unit tests for registry CRUD
- unit tests for local mock dynamic invocation
- unit tests for local A2A HTTP server/client loop
- full `verify_python.ps1`
