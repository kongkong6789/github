# Reference Platform Vendor Layout

This directory stores human-readable manifests for the six P18 reference platforms. Full upstream trees are **not** committed here.

Use:

```powershell
./scripts/sync_reference_platforms.ps1
```

That script shallow-clones upstream repos into gitignored `_references/` for local study or diff review.

| Platform | Upstream | Local integration |
| --- | --- | --- |
| DuckDB | https://github.com/duckdb/duckdb | Python package via `requirements.txt` |
| LightRAG | https://github.com/HKUDS/LightRAG | `./scripts/install_lightrag.ps1` |
| Karpathy LLM Wiki | https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f | `wiki/` + `docs/karpathy-llm-wiki.md` |
| MiroFish | https://github.com/666ghj/MiroFish | Optional sidecar + local scenario tools |
| RuoYi AI | https://github.com/ageerle/ruoyi-ai | Optional sidecar only |
| MaxKB | https://github.com/1Panel-dev/MaxKB | Optional sidecar only |

Runtime registry: `config/reference_platforms.json`.
