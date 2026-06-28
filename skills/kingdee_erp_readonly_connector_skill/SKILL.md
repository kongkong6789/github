# 金蝶 ERP 只读 Connector Skill

本项目 Skill 只提供金蝶云星空只读连接说明和治理元数据。真实查询由 A2A 后端的只读 connector 工具执行，默认只允许 `ExecuteBillQuery` 类读取动作。

## 边界

- 允许：供应商、采购订单分录、组织、客户、其他应付、销售退货等只读查询。
- 禁止：Save、Submit、Push、Delete、批量导入、外发消息、写回 ERP。
- 凭据：只从本地 `.env` 或进程环境读取，不写入本目录。
- 全功能桌面包：已移到 `vendor/reference-only/kingdee_erp_desktop_skill`，仅作人工参考，不参与 `/governance` 运行扫描。

## 环境变量

参考 `env.example` 配置本地运行环境：

- `KINGDEE_BASE_URL`
- `KINGDEE_ACCT_ID`
- `KINGDEE_USERNAME`
- `KINGDEE_PASSWORD`
- `KINGDEE_LCID`

## Agent 使用建议

当用户询问采购价、供应商条款、采购订单分录或金蝶当前只读数据时，优先调用 A2A 后端已登记的只读工具，例如 `query_erp_live_snapshot` 或 `query_inventory_cost_reference`。如果用户要求创建、提交、下推或保存单据，只返回人工确认需求，不执行外部写入。
