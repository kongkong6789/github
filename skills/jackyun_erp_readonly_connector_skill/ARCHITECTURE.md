# 项目架构

## 分层说明

- `SKILL.md`：Skill 入口文档，记录面向智能体的业务规则、触发说明、安全边界和工作流选择规则。
- `jackyun_api.py`：吉客云底层客户端。按配置在 MCP、官方 CLI、签名 HTTP 之间路由，并负责签名、限流、重试、分页和通用错误处理。
- `modules/`：业务模块，包括销售单、调拨、库存、基础资料、财务、售后、模板单据等能力。
- `modules/workflows.py`：高频业务工作流入口，用底层模块组合完整业务动作，并写入反馈日志。
- `helpers/`：通用辅助能力，包括校验、格式化、常量、本地状态、名称匹配、签名、官方 CLI 文档读取等。
- `helpers/runtime_plan.py`：工作流级别的执行通道可视化，用于展示 MCP / CLI / HTTP 预计路由。
- `docs/jackyun_cli_docs/`：随包携带的吉客云官方 CLI 机器可读文档，包括 `methods-index.json` 和关键接口详情 JSON。
- `docs/jackyun_mcp_tools.json`：吉客云 MCP 工具列表快照，用作 MCP 允许列表。
- `docs/PROJECT_MANUAL.md`：完整项目手册，记录运行策略、业务规则、工作流经验和文档维护规则。
- `docs/USER_SOP.md`：业务同事使用 SOP。
- `templates/`：随 skill 打包的 Excel 模板，例如默认申通仓出库单模板。
- `tools/jkyuncli/`：随包携带的官方 CLI 压缩包，覆盖 Windows amd64、macOS Intel、macOS Apple Silicon。
- `dist/`：发布包、官方文档缓存和历史构建产物。
- `data/`：本地运行状态目录，保存默认操作人、基础资料缓存、运行经验和运行期解压文件。发布包只携带 `data/cache/*.json`。

## 官方文档来源

新增或修改字段前，必须优先使用官方机器可读来源：

- CLI 方法索引：`https://open.jackyun.com/developer/jkyuncli/methods-index.json`
- CLI 方法详情：`https://open.jackyun.com/developer/jkyuncli/methods/{method}.json`
- MCP 工具列表：`https://open.jackyun.com/developer/mcpservice/toolList.html`
- MCP 服务地址：`https://mcp.open.jackyun.com/mcp/messages`
- OpenAPI 文档抓取脚本：`scripts/fetch_jackyun_openapi_docs.py`

不能只凭页面展示文字猜字段。官方 method JSON 或缓存 OpenAPI JSON 中不存在的字段，不写入请求。

## 运行调用策略

- `JACKYUN_CALL_STRATEGY=auto`：方法在 MCP 工具列表中且配置了 `JACKYUN_MCP_TOKEN` 时优先走 MCP；`JACKYUN_CLI_ENABLED=1` 时可用官方 CLI 兜底；否则走签名 HTTP。
- `JACKYUN_CALL_STRATEGY=mcp`：强制走 MCP，工具不存在或 token 缺失则报错。
- `JACKYUN_CALL_STRATEGY=cli`：强制走官方 CLI。
- `JACKYUN_CALL_STRATEGY=http`：强制走签名 HTTP。

授权 MCP AppKey 默认跟随 `JACKYUN_APP_KEY`；不要在文档中记录真实 AppKey。签名 HTTP 仍要求 `JACKYUN_APP_KEY` 与 `JACKYUN_APP_SECRET` 匹配。

高频工作流会返回由 `helpers/runtime_plan.py` 生成的 `execution_plan`。这只用于观察与排查；实际执行仍统一经过 `jackyun_api.py`。

## 本地状态

- `data/profile.json`：保存已确认的默认操作人姓名和吉客云用户档案。
- `data/cache/*.json`：基础资料缓存，包括用户、部门、公司、渠道、仓库、物流、货品和数据字典。
- `data/experiences/*.jsonl`：成功工作流记录，供后续复用和沉淀。
- `data/runtime/`：运行期解压的 CLI 文件，不随发布包携带。

## 当前业务默认值

- 调拨单申请公司默认读取 `JACKYUN_DEFAULT_APPLICATION_COMPANY_NAME`，当前默认“依然电商”。
- 调拨原因字典默认读取 `JACKYUN_TRANSFER_REASON_DICT_VALUE`，当前默认“调拨原因”。
- 销售单寄样/补发标记使用 `tradeOrderFlags`。如实例要求固定标记 ID，使用 `JACKYUN_SAMPLE_ORDER_FLAG_ID` 和 `JACKYUN_RESEND_ORDER_FLAG_ID`。
- 历史库存能力默认受控关闭，只有确认官方接口并配置 `JACKYUN_STOCK_HISTORY_METHOD` 后才允许调用。
