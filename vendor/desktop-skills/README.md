# Vendored Desktop Skills

这里保存从桌面复制进项目的金蝶和吉客云 Skill 参考实现，用于让项目离开当前电脑后仍能带上业务接入说明、OpenAPI 封装、字段文档和测试样例。

## 当前包含

- `kingdee-finance/`：来自 `/Users/seven/Desktop/Finance` 的金蝶 Finance Skill 安全副本。
- `jackyun-erp/`：来自 `/Users/seven/Desktop/jackyun-skill-project` 的吉客云 Skill 安全副本。

## 已排除内容

- `.env`、真实 `config.py`、账套配置、token、secret、apikey 等运行密钥。
- `dist/`、`output/`、缓存、发布 zip、临时查询结果和本地业务数据。
- 吉客云本地 master cache 数据与 CLI 二进制包。

## 与当前项目的关系

这些目录是 reference-only vendored skills，不参与 runtime governance scan，也不会自动暴露给 Agent。当前系统真正给 Agent 使用的仍然是项目里的只读 connector wrapper：

- `query_erp_live_snapshot`
- `route_erp_live_query`
- `query_inventory_cost_reference`
- `verify_erp_supplier_terms_mapping`

也就是说，桌面 Skill 的源码和文档已经随项目保存，但治理页、Agent allowlist 和 MCP/API policy 仍然只开放只读白名单，写入动作不会因为复制目录而被自动启用。
