# P16 Reference Repo Playbook

P16 used three external repositories as design references only. None are runtime dependencies in this project.

## Understand-Anything

Reference: [Lum1104/Understand-Anything](https://github.com/Lum1104/Understand-Anything)

Use as a local POC for codebase/wiki navigation:

- Generate an exploratory graph for project source code and selected `wiki/` pages.
- Keep outputs under ignored local directories such as `_references/understand-anything/` or `.understand-anything/`.
- Do not upload business source files, raw snapshots, ERP exports, customer data, or credentials to third-party services.
- Treat output as navigation/context only. DuckDB remains the numeric fact layer, LightRAG remains semantic retrieval, and this project evidence graph remains the auditable decision graph.

## Harness

Reference: [revfactory/harness](https://github.com/revfactory/harness)

Absorb patterns, not the repository:

- Pipeline: fixed sequence from source watcher to verifier.
- Fan-out/Fan-in: profile, quality, fact registration, and wiki work can be independently checked before final status.
- Producer-Reviewer: schema profiler produces drift evidence; quality gate reviews it.
- Supervisor / Hierarchical Delegation: `auto_workflow_agent` owns orchestration while specialized agents own steps.
- QA/validation: every role emits inputs, outputs, evidence, and recovery fields.

The concrete contract lives in [source-sync-workflow-contract.md](source-sync-workflow-contract.md).

## AI Engineering From Scratch

Reference: [rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch)

Use as an engineering checklist source:

- Agent loop: keep tool access explicit and state transitions observable.
- MCP: keep read/write boundaries in policy, not only in prompts.
- Evals: add regression tests around path guardrails, token redaction, idempotency, and read-only analysis intent.
- Production checklist: prefer doctor checks, runbooks, and deterministic local verification before adding new frameworks.

P16 keeps the current LangGraph stack and only documents reusable checklist/prompt/playbook ideas.
