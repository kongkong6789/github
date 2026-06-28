# Karpathy Fact-Layer Refactor Plan

## Goal

Keep the existing large Excel preprocessing entrypoints, but change their outputs from "CSV preview as primary interface" into a split architecture:

- Wiki memory layer: durable, human-readable dataset knowledge pages.
- DuckDB fact layer: full structured storage and query path for large-table facts.
- LightRAG semantic layer: index only wiki knowledge pages and reusable insight pages.
- Agent routing layer: use wiki/LightRAG for meaning and history, DuckDB for metrics and aggregates.

## Scope

- Preserve `profile_large_excel_file`, `process_large_excel_file`, `assess_large_excel_quality`, and batch wrappers.
- Add DuckDB-backed dataset registration and Parquet materialization behind the existing large Excel pipeline.
- Generate dataset wiki pages under `wiki/datasets/<slug>/`.
- Stop indexing warehouse CSV previews in LightRAG.
- Add mart/query helpers so business analysis can use DuckDB facts instead of warehouse sampling when large datasets are available.
- Update supervisor prompts, README, and TODO.

## Constraints

- Keep diffs small and reversible.
- Reuse current manifest/quality artifacts instead of replacing them.
- Avoid a platform rewrite; land the fact layer inside the current local-first tool architecture.
- Add only the dependencies needed for the explicit DuckDB/Parquet path.

## Implementation Steps

1. Introduce a shared DuckDB dataset registry utility module.
2. Extend the large Excel pipeline to materialize per-sheet Parquet files, register DuckDB views, and build semantic marts.
3. Generate wiki dataset pages: overview, sheet pages, field dictionary, quality report, query recipes, open questions.
4. Restrict LightRAG indexing inputs to wiki knowledge pages and decision/insight pages.
5. Add business query helpers that route structured questions to DuckDB and keep the older sampled CSV fallback for non-registered data.
6. Update agent prompts and docs to reflect the new routing model.
7. Verify with focused tests plus syntax/test runs.
