---
name: jackyun-erp-readonly-connector
description: Use when a project agent needs read-only 吉客云 ERP inventory, warehouse, order, sales summary, purchase, supplier, batch, or cost-reference context without enabling write operations.
---

# 吉客云 ERP 只读 Connector Skill

本项目使用吉客云能力时，只允许通过项目 Tool Registry / MCP policy 暴露的只读 connector 工具获取实时兜底证据。桌面原始 Skill 的全功能说明已保留为 `DESKTOP_SKILL_REFERENCE.md`，仅作为字段和流程参考，不授予创建、审核、发货、改仓配、退款、退换货、库存校准、字典新增或货品新增等写入能力。

## 使用边界

- 当前库存、分仓库存、批次效期、销售订单、销售汇总、采购、供应商、仓库、渠道、货品基础资料优先走吉客云只读 connector。
- 当用户同时要求库存金额、成本价、采购价、毛利或金额口径周转时，优先调用 `route_erp_live_query`，再调用 `query_inventory_cost_reference`。
- 当用户要求日期 + 渠道/店铺 + SKU 的销量或销售金额时，优先通过项目只读工具路由到销售汇总能力；若权限返回 0 行，必须把报表权限或过滤口径列为数据缺口。
- 吉客云实时结果必须标注 `live_read_only_fallback`，不能说成已入库长期事实。
- SKU 编码只能使用吉客云返回的 `goodsNo` 或 `skuBarcode`，商品名只能使用 `goodsName`。
- 不能从 `DESKTOP_SKILL_REFERENCE.md` 推导新的可调用写入工具；工具权限只以 `skill.registry.json`、Tool Registry 和 MCP policy 为准。

## 禁止事项

不得把桌面 Skill 里的创建销售单、寄样单、补发单、审核、发货、改仓配、退款、退换货、库存校准、字典新增或货品新增等写入能力暴露给分析 Agent。需要外部写入时，只能生成 Agent Inbox 人工确认请求。
