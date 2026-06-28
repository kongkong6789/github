# Wiki Schema

This document defines the local LLM Wiki discipline for the ecommerce workbench.

## Principle

The wiki is a durable knowledge codebase, not a dump of chat answers. Raw files remain immutable sources, DuckDB/ERP own numeric facts, LightRAG owns semantic retrieval, and Agent-written wiki pages own reusable business understanding.

## Page Types

- `source`
- `dataset`
- `brand`
- `sku`
- `channel`
- `warehouse`
- `supplier`
- `decision`
- `claim`
- `contradiction`
- `playbook`
- `index`
- `log`
- `schema`

## Required Frontmatter

```yaml
---
type: decision
updated_at: 2026-05-20T00:00:00Z
source: wiki/log.md
evidence:
  - wiki/datasets/example/overview.md
status: current
---
```

## Evidence Rules

- ERP live reads must be marked `live_read_only_fallback` and include query time, filters and row count.
- DuckDB mart claims must include the mart/view name, SQL summary and registry update time.
- Durable claims use `status: current`, `status: stale` or `status: contradicted`.
- Every high-value answer should be archived to `wiki/decisions/` and linked from `wiki/log.md`.
