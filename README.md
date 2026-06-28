# A2A 电商经营大脑

本项目是一个本地优先的电商经营分析工作台，面向公司内部 PM、运营和经营团队使用。它把前端对话、LangGraph 多 Agent、DuckDB 事实层、Obsidian/LLM Wiki、LightRAG 检索、ERP 实时只读兜底、任务队列、治理审计和证据图谱串成一条可追溯的经营决策链路。

一句话概括：

```text
LLM Wiki + DuckDB 事实层 + LightRAG 检索 + 多 Agent + ERP 实时兜底 + 治理审计
```

文档里的 `<A2A_PROJECT_ROOT>` 表示项目根目录。

## 当前状态

当前已经可以作为公司内部本地经营工作台试运行。标准 A2A Server/Client 暂缓，只有当项目需要被外部系统调用，或需要接入远程 Agent 时再推进 P8。

已落地能力：

| 层级 | 状态 | 说明 |
| --- | --- | --- |
| 前端工作台 | 已落地 | 对话首页、trace 面板、任务历史、任务详情、数据健康、数据源、Logs / Doctor、Governance、证据图谱；历史归档会折叠重复 supervisor 最终报告 |
| 多 Agent 编排 | 已落地 | LangGraph supervisor、多团队 Agent、动态 Agent、active Skill 自动注入 |
| 数据事实层 | 已落地 | Excel/CSV 清洗、大文件分块、Parquet、DuckDB、dataset registry、mart 查询 |
| ERP 实时兜底 | 已落地 | 吉客云 / 金蝶只读查询，默认 DuckDB 优先；吉客云库存支持品牌扩展、仓库口径映射和周转/批次效期口径护栏；吉客云销售汇总支持日期 + 渠道/店铺 + SKU + 销量/金额只读查询 |
| 企业微信智能表 | 已接入 | 支持通过 WeDoc MCP 只读读取智能表，必要时同步为本地 connector snapshot 并注册 DuckDB |
| 平台数据接入 | 已定边界 | 天猫、淘宝、抖音、拼多多、京东、广告、客服售后等默认走后台导出文件入库 |
| 工作台控制面 | 已落地 | P9 `/api/workbench` 统一 task、trace、data-health、governance、approval、logs |
| 任务系统 | 已落地 | P10 任务页 + P12 SQLite durable queue，保留 JSON 任务详情兼容视图 |
| 工具治理 | 已落地 | P11 Tool Registry 2.0、Agent allowlist、MCP/API policy、写入确认 |
| 运维诊断 | 已落地 | P13 doctor、logs、config health、旧线程清洗、LightRAG 诊断 |
| 证据体系 | 已落地 | P14 经营对象证据图谱，连接品牌、渠道、SKU、仓库、供应商、数据集、报告和决策 |
| 知识复利 | 已落地 | P15 LLM Wiki schema/index/log、claim/evidence 生命周期、wiki lint 和复盘问题 |
| 数据源增量同步 | 已落地 | P16 已新增 Source Registry、版本化 `raw/snapshots`、本地/手工/WeCom/ERP 只读 adapter、`/data-sources`、Workbench `source.*` 方法和 source doctor；企业微信微盘真实管理参数可先留空，COS/OSS 仍是后续归档镜像选项 |

详细路线和历史记录见 [TODO.md](TODO.md) 与 [progress.md](progress.md)。

## 当前未完成项

截至 2026-05-30，P16 已完成；剩余 TODO 都是后续增强，不阻塞当前本地试运行：

| 方向 | 未完成内容 |
| --- | --- |
| Runtime Capability / MCP | 上传 MCP policy 向导、远端 MCP schema 自动发现、capability 使用统计页；Skill/MCP marketplace 第一批模板已落地 |
| A2A 标准化 | A2A Protocol schema、本地 A2A Server/Client、远程 Agent 路由、权限、审计和前端状态 |
| 参考仓库能力吸收 | `supermemory`、`agency-agents`、`harness-anything` 的可控吸收路线：Agent 模板、跨会话记忆、CLI/桌面工具市场模板 |
| LightRAG 运维 | 若再次出现 pending 长时间不动，按 runbook 检查供应商模型、embedding 稳定性和 worker 状态 |
| 库存周转增强 | 自动组合吉客云库存、品牌扩展和销售汇总，生成覆盖天数报告；金额口径需补成本价/采购价和敏感字段审计 |
| 批次效期增强 | 小样、赠品或临期风险较高时，自动追加批次库存/效期查询 |

## 适合做什么

面向 PM 和经营团队的常用场景：

- 把 `raw/` 下的资料整理成 Obsidian wiki，并同步到 LightRAG。
- 清洗 Excel / CSV，生成 `data/cleaned`、Parquet、DuckDB view、质量报告和 dataset wiki。
- 处理 50MB+ 大 Excel，自动画像、分块、注册事实层、生成查询 recipes。
- 查询库存、销售、广告、财务、供应商、订单、吉客云实时 SKU 销售汇总和 ERP 实时只读快照。
- 生成库存风险、渠道经营分析、广告诊断、供应商风险、老板报告和执行建议。
- 查看 Agent 执行 trace、任务状态、产物链接、数据健康、日志诊断和证据图谱。
- 把高复用 wiki 页面沉淀为可审批、可启停、可回滚的 Agent Skill。

不默认做的事：

- 不把国内平台 API 作为默认接入方式。平台/广告/评价/售后优先导出文件入库。
- 不让决策类 Agent 启动 raw 清洗、LightRAG rebuild 或长任务。
- 不直接执行外部写入。采购单、广告预算、外发消息等写入动作必须人工确认。
- 不把 ERP 实时快照当成长期事实。ERP 实时结果必须标注查询时间、过滤条件和 `live_read_only_fallback`；企业微信智能表 MCP 结果使用 `live_read_only_mcp`。

## 架构概览

```text
浏览器前端 agent-chat-ui
        |
        v
LangGraph Server: http://127.0.0.1:2024
        |
        v
top_company_brain_supervisor
        |
        +-- friendly_router_agent
        +-- auto_workflow_agent
        +-- agent_factory_agent
        +-- data_pipeline_team
        +-- decision_team
        +-- strategy_team
        |
        v
专业 Agent + Tool Registry + Agent allowlist
        |
        +-- DuckDB / Parquet / dataset registry
        +-- Obsidian / LLM Wiki
        +-- LightRAG
        +-- 吉客云 / 金蝶 read-only ERP
        +-- SQLite durable queue
        +-- audit / governance / evidence graph
        |
        v
报告、决策页、证据链、任务状态和前端控制台
```

更细的设计见 [docs/architecture.md](docs/architecture.md)。

## 主要页面和 API

本地默认地址：

| 页面 / API | 地址 | 用途 |
| --- | --- | --- |
| 聊天工作台 | `http://127.0.0.1:3000` | PM 入口，对话、任务触发、trace 面板 |
| LangGraph API | `http://127.0.0.1:2024` | 后端 Agent graph |
| LightRAG UI | `http://127.0.0.1:9621/webui/#/` | LightRAG 文档和状态 |
| 数据健康 | `http://127.0.0.1:3000/data-health` | DuckDB、LightRAG、ERP connector、Wiki Knowledge、任务、配置 |
| 数据源 | `http://127.0.0.1:3000/data-sources` | Source Registry、快照历史、schema diff、Sync now、Pause/Resume、Rebind |
| 任务历史 | `http://127.0.0.1:3000/tasks` | 任务列表、阶段进度、产物链接 |
| 证据图谱 | `http://127.0.0.1:3000/evidence-graph` | 经营对象、数据集、报告、决策、风险节点关系 |
| Logs / Doctor | `http://127.0.0.1:3000/logs` | 日志、doctor 诊断、错误定位 |
| Governance | `http://127.0.0.1:3000/governance` | Skill、Tool Registry、MCP/API policy 和审计 |
| Workbench API | `http://127.0.0.1:3000/api/workbench` | typed control plane |

`/api/workbench` 当前方法：

```text
task.list
task.show
agent.trace
data.health
governance.policy
approval.submit
logs.tail
evidence.graph
source.list
source.show
source.sync
```

所有响应都使用统一 envelope：`ok`、`method`、`request_id`、`generated_at`、`data`、`error`、`warnings`。读取类方法默认带 scope 保护，无 scope 时不会返回全局任务、审计、trace 或日志历史，除非显式传 `scope=global`。

## 数据和知识流

```text
raw/
  |
  v
资料解析、Excel 画像、大文件分块
  |
  v
data/cleaned + data/warehouse
  |
  v
DuckDB fact layer + marts + dataset registry
  |
  v
wiki/datasets + wiki/decisions + wiki/data-dictionary
  |
  v
LLM Wiki schema + index + log + claim/evidence lifecycle
  |
  v
LightRAG semantic index
  |
  v
Agent 分析、证据图谱、决策报告和复盘页
```

P16 源文件更新链路：

```text
企业微信微盘 / 平台导出目录 / 手工上传 / WeCom 智能表 / ERP 只读快照
  |
  v
Source Registry
  |
  v
raw/snapshots/<source_id>/<snapshot_id>/...
  |
  v
现有清洗、DuckDB、wiki、LightRAG 和报告链路
```

关键口径：

- `raw/` 保留原始证据，不直接覆盖。
- P16 的目标不是用线上文件库替代 `raw/`，而是让企业微信微盘作为“业务人员协作编辑的当前源”，再同步到本地 `raw/snapshots` 形成不可变证据；COS/OSS 只作为后续长期归档或镜像层。
- 长期源登记在 `data/source_registry/sources.json`，快照 manifest 写入 `data/source_registry/snapshots.jsonl`。
- 前端 `/data-sources` 可查看 source freshness、最新 snapshot、schema diff 和历史快照；`/data-health` 汇总失败源、过期源和 schema drift。
- 操作细节见 [docs/runbook.md](docs/runbook.md)，团队契约见 [docs/source-sync-workflow-contract.md](docs/source-sync-workflow-contract.md)，参考仓库吸收方式见 [docs/reference-repo-p16-playbook.md](docs/reference-repo-p16-playbook.md)。
- `data/cleaned/` 存普通清洗结果。
- `data/warehouse/` 存大表分块、Parquet、DuckDB、manifest、quality report 和 dataset registry。
- DuckDB / mart 负责事实数字和全量聚合。
- LLM Wiki 负责长期业务理解、口径、claim、决策沉淀和知识复盘。
- LightRAG 负责语义检索、实体关系和证据定位，不承担大表全量计算。
- ERP 实时只读只作为当前数据兜底，不能替代 DuckDB 已注册事实。

## LLM Wiki 规则

P15 把 wiki 从“数据处理产物 + 决策报告库”升级为长期知识代码库。核心文件：

| 文件 | 用途 |
| --- | --- |
| [docs/wiki_schema.md](docs/wiki_schema.md) | 页面类型、frontmatter、证据、归档规则 |
| `wiki/AGENTS.md` | Agent 写 wiki 时必须遵守的规则 |
| `wiki/index.md` | Agent 可发现目录，记录页面类型、摘要、证据和是否可用于决策 |
| `wiki/log.md` | append-only 知识演进日志 |
| `data/wiki_knowledge_health.json` | wiki lint / knowledge doctor 输出 |

页面类型包括：

```text
source, dataset, brand, sku, channel, warehouse, supplier,
decision, claim, contradiction, playbook, index, log, schema
```

归档规则：

- `decision` / `claim` 页面要记录 evidence、数据源、查询时间、过滤条件、row_count 和状态。
- ERP 实时查询归档必须标注 `live_read_only_fallback`。
- DuckDB mart 归档必须附 registry、mart/view 名称、SQL 摘要和数据更新时间。
- `/data-health` 的 Wiki Knowledge 区域会显示孤页、缺证据 claim、过期/被推翻 claim、未登记 index 和复盘问题。
- 当前旧 wiki 页面可能会触发 frontmatter/evidence warning，这是历史页面治理问题，不代表 P15 框架不可用。

## 后台任务和 durable queue

长任务由 SQLite durable queue 管理，默认数据库：

```text
data/tasks/tasks.sqlite
```

`data/tasks/*.json` 继续作为任务详情导出和前端兼容视图。后端启动时会恢复 `queued`、`recoverable` 和上次中断遗留的 `running` 任务；已经完成的步骤会跳过，避免从头重复跑完整链路。

主要表：

- `tasks`：任务状态、idempotency key、当前步骤、开始/结束时间。
- `task_claims`：worker claim lock、heartbeat、过期时间。
- `task_events`：入队、claim、heartbeat、步骤完成、失败、取消、恢复事件。
- `task_artifacts`：步骤证据和产物路径。
- `task_retries`：失败重试次数和原因。

常用任务工具：

```text
start_company_workflow_task
get_workflow_task_status
list_workflow_tasks
cancel_workflow_task
recover_workflow_queue
```

历史 JSON 任务迁移预检：

```bash
python scripts/migrate_tasks_to_sqlite.py
```

真正写入 SQLite：

```bash
python scripts/migrate_tasks_to_sqlite.py --write
```

## 治理和安全边界

Tool / Skill / MCP：

- `agent_tool_registry.py` 是工具注册中心，记录工具分组、风险级别、只读/写入、确认策略、数据来源和可见 Agent。
- Agent allowlist 仍保留为兼容层，但工具元数据以 Tool Registry 为准。
- Runtime Capability 是统一调用入口：`list_runtime_capabilities` 会列出 `tool:*`、`skill:*`、`mcp:*`；`invoke_runtime_capability` 负责按统一边界调用；`register_runtime_mcp_tool` 用于登记后续上传或创建的 MCP/API policy。
- wiki、Markdown 页面或项目内 `skills/<folder>/SKILL.md` 都可以导入为 Skill 配置草稿，人工确认后才启用。
- `skills/` 是项目专用 Skill Library：每个直接子目录代表一个 Skill，可以包含 `SKILL.md`、assets、scripts、templates 等文件；`/governance` 会扫描这些目录并提供导入/更新入口。
- SkillHub 已作为外部技能市场接入：`/governance?tab=skills` 内的“技能市场”子页会读取 SkillHub 目录索引/API 展示标签、下载量、评分、最近更新和安装量，并用 `skillhub install <slug> --json --dir <workspace>/skills` 安装到项目 `skills/`，随后自动导入为 Skill 配置草稿；需要先安装 CLI：`curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/install.sh | bash -s -- --cli-only`。
- 导入或上传文件夹后，系统会把完整 Skill 文件夹复制为受管副本 `data/skill_registry/imports/<skill_id>/`，并把 `source_skill_path`、`managed_skill_dir` 记录进 Skill Registry；原始 `skills/` 目录不会被删除。
- 如果 `source_skill_path` 对应的原始 `skills/<folder>` 被手动删除，`/governance` 会在 Skill Registry 显示 `source missing`，并提供删除注册、重新绑定、从受管副本恢复到 `skills/` 的操作。
- 删除 Skill Registry 注册项只删除 registry 记录、active template 和受管副本；不会删除 `skills/<folder>` 原始文件夹。保留的文件夹会回到 Skill Library 的未注册状态，可再次导入。
- 文件夹 Skill 可以放 `skill.registry.json` 作为重新导入默认元数据，保存 `skill_id`、场景、只读工具白名单和输出 schema；重新添加吉客云/金蝶这类 connector Skill 时，可用它固定只读权限边界。
- active Skill 会按用户提示词自动匹配并注入 supervisor / 多 Agent 上下文，也可以通过 `invoke_runtime_capability("skill:<skill_id>")` 返回 prompt bundle；这不会扩大工具权限。
- 当前项目内 active Skill 为 `unove_domestic_channel_strategy`、`jackyun_erp_readonly_connector_skill`、`kingdee_erp_readonly_connector_skill`；吉客云/金蝶使用项目内 `skills/<folder>/SKILL.md` 只读 wrapper 和 `skill.registry.json` 权限白名单。
- Skill Registry 只负责 Agent prompt bundle 和工具白名单；真实 ERP API 是否可用还要看 connector runtime 配置：`data/warehouse/connector_registry.json`、`A2A_JACKYUN_SKILL_DIR` / `A2A_KINGDEE_SKILL_DIR` 和 `.env` 凭据。
- MCP/API policy 会和 Tool Registry 交叉校验，缺失或冲突会在 `/governance` 中提示。
- 新 MCP/API 工具先进入 policy，再进入 capability discovery；只读工具可直接执行，写入、高风险或未授权工具只生成 Agent Inbox 人工确认请求。

Runtime Capability 调用例子：

```text
list_runtime_capabilities()
invoke_runtime_capability("tool:list_agent_skills", args_json="{\"status\":\"active\"}")
invoke_runtime_capability("skill:unove_domestic_channel_strategy", args_json="{\"user_task\":\"分析本月渠道策略\"}")
invoke_runtime_capability("mcp:list_erp_live_query_capabilities")
```

上传或创建 MCP/API 后登记为本地 policy：

```text
register_runtime_mcp_tool(
  "uploaded_read_tool",
  policy_json="{\"read_only\":true,\"execution_mode\":\"mcp_jsonrpc_tool\",\"mcp_tool_name\":\"uploaded.echo\",\"mcp_url_env\":\"UPLOADED_MCP_URL\"}"
)
```

写入和敏感数据：

- 外部写入、高风险和破坏性工具默认需要人工确认。
- 吉客云 / 金蝶当前强制只读，应用层 `external_write_enabled=false`。
- 吉客云只允许白名单查询方法，金蝶只允许 `ExecuteBillQuery`。
- 客户个人信息字段输出时强制脱敏。
- 采购价、供应商报价和财务字段默认聚合分析或记录敏感字段访问审计。
- 审计日志保存到 `data/audit/events.jsonl`，常见 token、secret、password 会脱敏。

字段级敏感数据治理是轻量版，适合内部 PM 使用。如果进入多用户生产环境，还需要补账户、角色和存储层权限。

## 参考仓库综合吸收路线

2026-06-01 已调研三个新参考仓库，结论是：可以吸收，但都不应该替代当前主系统。当前项目的主干仍然是本地优先的经营工作台，DuckDB 负责事实数字，Wiki/LightRAG 负责本地知识和语义检索，Tool Registry/MCP policy 负责权限、审批和审计。

调研快照：

| 仓库 | 调研版本 | 推荐定位 |
| --- | --- | --- |
| [supermemoryai/supermemory](https://github.com/supermemoryai/supermemory) | `253a82b`，2026-05-31 | 可选外部记忆层：跨会话用户/团队记忆、profile、recall/context MCP，不作为经营事实来源 |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | `783f6a7`，2026-04-11 | Agent/Skill 模板库：电商运营、供应链、FP&A、广告、合规、handoff/QA 模板 |
| [yb2460/harness-anything](https://github.com/yb2460/harness-anything) | `60d5f61`，2026-05-31 | CLI/桌面软件 harness 参考：Skill/MCP marketplace 模板、WPS/Office 报告导出、PPT 质量审查、Windows worker 工具边界 |

完整可结合清单：

| 优先级 | 可结合能力 | 来源 | 接入位置 | 边界和建议 |
| --- | --- | --- | --- | --- |
| P0 | 中国电商运营 Agent 模板 | `agency-agents` China E-Commerce Operator | `data/agent_templates` / `skills` / `listing_agent` | 强烈建议；改造成国内平台经营分析 Skill，必须引用 DuckDB/wiki/ERP 快照 |
| P0 | 供应链、库存、采购策略模板 | `agency-agents` Supply Chain Strategist | `inventory_agent` / `company_strategy_agent` | 强烈建议；结合库存周转、覆盖天数、补货、供应商风险 TODO |
| P0 | FP&A / 财务分析模板 | `agency-agents` finance FP&A | `finance_agent` / 老板报告 | 建议；做毛利、预算、费用偏差、情景分析模板 |
| P0 | Paid Media 广告诊断模板 | `agency-agents` paid-media agents | `ads_agent` | 建议；适配阿里妈妈、万相台、巨量千川、京准通、多多推广导出报表 |
| P0 | Agent 交接模板和 QA gate | `agency-agents` handoff templates | task event / Agent trace / task detail | 强烈建议；用于标准化 handoff、PASS/FAIL、重试和升级记录 |
| P0 | Dev-QA 循环编排 | `agency-agents` Agents Orchestrator | `auto_workflow_agent` / durable queue | 吸收流程，不照搬人格 prompt；每个任务必须有证据和验收字段 |
| P0 | 用户/团队长期记忆 | `supermemory` Memory API / profile | supervisor pre-context | 可选接入；只记录 PM/运营偏好、项目状态、复盘经验 |
| P0 | `recall` / `context` 只读 MCP | `supermemory` MCP | Runtime Capability / MCP policy | 先只读接入；召回内容只能做上下文，不作为经营证据 |
| P0 | User Profile 静态/动态画像 | `supermemory` Profile API | `top_company_brain_supervisor` system context | 适合记录“用户偏好、当前项目状态”；禁止上传敏感明细 |
| P0 | Memory vs RAG 分层原则 | `supermemory` docs | `docs/architecture.md` / README | 写入架构纪律：RAG 管资料，Memory 管关于用户/项目的演进状态 |
| P1 | Skill/MCP marketplace 模板格式 | `harness-anything` `registry_entry.json` | `/governance` / Runtime Capability | 很适合当前 TODO：外部 CLI/MCP 工具导入模板 |
| P1 | CLI 工具 JSON 输出规范 | `harness-anything` WPS Skill | Runtime Capability 外部工具适配 | 可作为上传 CLI 工具约定：`--json`、结构化错误、dry-run、项目文件 |
| P1 | WPS/Office 报告导出 | `harness-anything` WPS harness | task artifact export / 老板报告 | 仅在 Windows worker 可用时接入；写文件/导出必须审批或由任务执行器执行 |
| P1 | PPT 设计预设和质量审查 | `harness-anything` quality checks | 老板报告 / 月报 PPT | 建议先吸收规则，不急于接 WPS COM |
| P1 | 会话状态、undo/redo 模型 | `harness-anything` session | 动态 Agent / 文档生成草稿 | 可参考为报告草稿、PPT 草稿增加回滚能力 |
| P1 | 文档导出 pipeline | `harness-anything` export | task artifact export | 可参考；macOS 本机不能直接跑 Windows COM |
| P1 | Product / trend / feedback 模板 | `agency-agents` product agents | `listing_agent` / 产品线复盘 | 用于商品卖点、差评、竞品和新品机会分析 |
| P1 | Data consolidation Agent | `agency-agents` specialized | Source Registry / 清洗工作流 | 改造成“多源数据归并检查”模板 |
| P1 | Compliance auditor | `agency-agents` specialized | `risk_agent` / governance | 做广告文案、平台规则、敏感字段和外部写入前审查 |
| P1 | Automation governance architect | `agency-agents` specialized | MCP/API policy | 辅助设计工具权限、审批、审计和风险分级 |
| P1 | MCP builder 模板 | `agency-agents` specialized MCP builder | Agent Factory / MCP 上传向导 | 用于创建 MCP policy 草稿，不自动放权 |
| P2 | Supermemory scoped API key 机制 | `supermemory` auth docs | MCP policy / env 配置 | 参考 container 级权限隔离；优先使用 scoped key |
| P2 | MemoryBench 思路 | `supermemory` MemoryBench | Wiki/LightRAG 召回质量评测 | 可做本地知识召回评测，不引入外部基准依赖到主链路 |
| P2 | Memory graph UI 思路 | `supermemory` memory graph | Evidence Graph | 只参考交互，不替代经营对象证据图谱 |
| P2 | GitHub/Drive/Notion connector 设计 | `supermemory` connectors | Source Registry | 参考资源选择、增量同步、webhook、连接健康检查 |
| P2 | Zotero 本地 SQLite + Local API 模式 | `harness-anything` Zotero harness | 未来桌面 connector 设计 | 参考“只读 SQLite + 官方写接口”的边界 |
| P2 | Photoshop / Illustrator harness | `harness-anything` PS/AI harness | 商品图、海报、素材生成 | 低优先级，高风险；必须人工确认，默认不挂给分析 Agent |
| P3 | 学术研究 pipeline | `harness-anything` Zotero / `agency-agents` academic | 暂无主线落点 | 暂不建议，除非后续做研发、专利、成分或论文型资料 |
| P3 | 全量 Supermemory RAG 替代 LightRAG | `supermemory` | 不接入 | 不建议；会破坏本地优先和证据链 |
| P3 | 全量 agency-agents 导入 | `agency-agents` | 不接入 | 不建议；太泛，会污染 Agent 角色边界 |
| P3 | WPS/PS/AI 写入工具直接挂给 Agent | `harness-anything` | 不接入 | 不建议；桌面自动化和本地写文件必须走审批或后台任务执行器 |

2026-06-01 第一批已经落地：

1. 精选 `agency-agents` 的电商运营、供应链、FP&A、广告诊断、合规审查、数据归并 6 个模板，写入 `data/agent_templates/`。
2. 新增 `agent_template.schema.json`，每个模板包含 `tool_allowlist`、`output_schema`、`risk_level`、`evidence_required`。
3. 把 handoff / QA 模板接入 SQLite task event，新增 `handoff.created`、`qa.pass`、`qa.fail`、`qa.escalated`。
4. 任务详情页展示 handoff、QA verdict、证据路径、失败重试次数和下一步动作。
5. `dynamic_agent_hub.draft_dynamic_agent_spec_from_template()` 可从模板生成受控动态 Agent spec，写入/高风险工具仍被过滤。
6. Supermemory `profile` / `recall` / `context` 已作为 MCP policy 只读能力进入 Runtime Capability；召回内容只作为上下文。
7. `save memory` 走人工确认，`external_memory_tools` 会先拦截 ERP、财务、客户、采购价、库存明细和私密智能表 URL。
8. `data/mcp_marketplace/templates/` 已沉淀 CLI JSON、WPS 报告质量、PPT 质量审查模板。
9. `/governance` 新增模板市场视图，可查看来源、风险、读写属性、确认策略、允许调用方并填入 MCP/API 策略表单。
10. `/governance?tab=skills` 的“权限与工具”页新增“技能市场 / 已安装 / 已配置”子页：技能市场支持按类目、来源和综合评分/下载量/最近更新/安装量浏览 SkillHub，并可安装到项目 `skills/` 后自动导入为配置草稿。
11. 首页左侧导航新增“历史对话”，会打开 `/?chatHistoryOpen=true`；空白首页桌面端在主内容区显示本地聊天归档，进入具体对话后改用居中浮层选择器，移动端仍用抽屉，`/tasks` 继续只作为经营任务历史库。
12. `scripts/doctor.py` 会在非 Windows 平台把 WPS/Photoshop/Illustrator harness 标为 unavailable，而不是运行失败。

明确不做：

- 不把 Supermemory hosted API 当成 ERP、财务、客户、库存明细或采购价的事实来源。
- 不让 Supermemory、agency-agents、harness-anything 绕过 Tool Registry、MCP policy、Agent allowlist 或人工确认。
- 不把 agency-agents 全量导入为 active Agent。
- 不在 macOS 本地默认启用 Windows COM harness。
- 不让 WPS、Photoshop、Illustrator 这类写文件/桌面自动化工具直接暴露给普通分析 Agent。

## ERP 和平台数据边界

已支持的实时只读 ERP 能力：

- 吉客云：SKU 库存、批次库存、销售订单、货品销售分析、日期 + 渠道/店铺 + SKU 销售汇总、采购订单、入库、出库、供应商、仓库、渠道、货品基础资料。
- 金蝶：供应商、采购订单分录、供应商采购条款观察、销售出库、销售退货、其他应付、组织、客户、应收快照。
- 确定性路由：`route_erp_live_query` 会把“库存、采购价、成本价、毛利、库存金额、日销、周转、企业微信智能表”等组合请求路由到吉客云、金蝶、WeCom MCP 或 DuckDB。
- 库存成本参考：`query_inventory_cost_reference` 会先读吉客云库存；若 `costPrice` 为空或仅部分库存行有值，会继续查吉客云批次/采购，并用金蝶 `supplier_procurement_terms` / `purchase_orders` 的 `FTaxPrice` 作为采购单价参考；该值不等同于最终库存核算成本。
- 实时销售汇总：`query_jackyun_channel_sales_summary` 只封装吉客云 Skill 的销售汇总工作流，不开放写入；适合按 `start_time/end_time + shop_names/shop_ids/channel_include_keyword + goods_no/sku_barcode/goods_name` 查询销量和销售金额。若吉客云报表权限返回 0 行或 SKU/品牌只能后置筛选，报告必须把“销售汇总权限或精确过滤”列为数据缺口。
- 桌面 Skill 副本：历史 `vendor/desktop-skills/kingdee-finance` 和 `vendor/desktop-skills/jackyun-erp` 脱敏参考副本已移除；当前吉客云/金蝶项目 Skill 位于 `skills/jackyun_erp_readonly_connector_skill` 和 `skills/kingdee_erp_readonly_connector_skill`，Agent 只使用顶层只读 wrapper 与 registry policy，桌面原始说明仅作为 `DESKTOP_SKILL_REFERENCE.md` 参考。
- 吉客云实时 connector：默认使用 `skills/jackyun_erp_readonly_connector_skill`，项目内只保留 env-only `config.example.py`，真实 OpenAPI 凭据从 `.env` / 进程环境读取 `JACKYUN_APP_KEY`、`JACKYUN_APP_SECRET` 和可选 `JACKYUN_API_URL`。不要把 `config.py` 或密钥提交进 Skill 文件夹。
- 2026-05-25 验证：吉客云 connector health 为 `ready`，`inventory_stock` 使用 `erp.stockquantity.get` 的只读 smoke 查询返回 `status=success`；如果后续再出现“目录/凭据缺失”，优先检查 `A2A_JACKYUN_SKILL_DIR` 是否指向已删除目录，以及 `.env` 是否缺少吉客云凭据。

企业微信智能表：

- 只读工具：`list_wecom_smartsheet_sources`、`test_wecom_smartsheet_connection`、`query_wecom_smartsheet_records`。
- 读取路径：仅使用 WeDoc MCP；没有 `WECOM_SMARTSHEET_MCP_URL`（或 `WEWORK_SMARTSHEET_MCP_URL` / `WEDOC_MCP_URL` / `WEWORK_WEDOC_MCP_URL`）时不会回退到企业微信自建应用 API 读取文档内容。
- URL 优先：用户在前端提示词里提供 `https://doc.weixin.qq.com/smartsheet/...&tab=<sheet_id>` 时，Agent 会把该链接作为 `doc_url` 传给 `query_wecom_smartsheet_records`；工具从 URL 的 `tab` 参数自动识别 `sheet_id`，不依赖固定 `source_id`。
- 命名源可选：`config/wecom_smartsheet_sources.json` 默认不再写死任何私有智能表；只有要维护可复用 named source 时才配置 `docid + sheet_ids`。多子表也可通过一次传多个 URL，或用可选 `WECOM_SMARTSHEET_SHEET_IDS=<sheet_id_1>,<sheet_id_2>` 配置。
- 治理权限：`list_wecom_smartsheet_sources`、`test_wecom_smartsheet_connection`、`query_wecom_smartsheet_records` 已登记到 `/governance` 的 MCP/API policy，作为 low-risk read-only 工具供 `top_company_brain_supervisor`、`data_agent`、`decision_agent`、`company_strategy_agent`、`auto_workflow_agent` 和 `agent_factory_agent` 调用。
- 入库工具：`sync_wecom_smartsheet_snapshot`，只写本地 `data/staging/connectors/wecom_smartsheet` 和 DuckDB fact layer，不写回智能表。
- 配置优先放 `.env` 和 `config/wecom_smartsheet_sources.json`；参考 [config/wecom_smartsheet_sources.example.json](config/wecom_smartsheet_sources.example.json)。
- 桌面脚本里的 webhook 新增/修改逻辑没有纳入默认 Agent 权限；如未来要做写回，必须走 MCP/API policy 和人工确认。

企业微信微盘（P16 规划）：

- 推荐定位：微盘作为团队协作编辑的源文件库，本地 `raw/snapshots` 作为系统处理和审计使用的不可变证据层。
- 首期只做只读 list/download：登记微盘文件或文件夹后，系统按 `mtime`、文件大小和内容 hash 判断是否变化；变化时下载当前版本形成新 snapshot，再进入现有清洗、DuckDB、wiki 和 LightRAG 链路。
- 不做微盘写回：上传、覆盖、删除、移动、分享权限修改都不纳入 P16 默认能力；如未来需要写回，必须走 MCP/API policy 和人工确认。
- 不保存临时下载 URL 或 token：Source Registry 只记录 `space_id`、`file_id`、文件名、路径摘要和 credential env key。

仓库业务口径配置化：

```text
config/jackyun_warehouse_scope_rules.json
```

配置含义：

- `business_scope`：输出口径，例如大贸、跨境、保税、售后。
- `canonical_warehouse`：标准仓名。
- `keywords`：匹配吉客云 `warehouseName`。

新增、减少或改名仓库时维护这个 JSON 后重启 backend。也可以设置：

```text
A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH=<path>
```

吉客云库存查询口径：

- 品牌查询不能直接依赖库存接口的 `brandName`。当用户说 “UNOVE / 柔诺伊” 这类品牌名时，Agent 会先用货品资料按 `goodsName` / alias 找到 `goodsNo` / `skuBarcode`，再用 `inventory_stock` 按 goods_no 查询库存。
- SKU 和品名必须沿用吉客云返回的 `goodsNo`、`skuBarcode`、`goodsName`，不得输出 `UNV-001`、`UNV-008` 这类占位编码。
- `costPrice` 或采购价缺失只影响库存金额、成本金额、毛利和金额口径周转；数量口径周转仍可在有销量或出库数据时计算。
- 只读取 `inventory_stock / erp.stockquantity.get` 时不能量化批次效期；临期风险需要再读 `batch_inventory / erp.batchstockquantity.get`。
- 未命中 `warehouse_scope_rules` 的仓库会单独列为“未映射”，例如虚拟仓、样品仓、办公室仓或新仓库别名；新增映射时维护 `config/jackyun_warehouse_scope_rules.json`。

走导出文件入库的平台数据：

- 天猫、淘宝、抖音、拼多多、唯品会、京东销售、商品、退款、评价。
- 阿里妈妈、万相台、巨量千川、京准通、多多推广等广告报表。
- 客服会话、售后工单、问大家、退款退货原因和差评跟进记录。

原因：国内平台接口权限、稳定性和合规成本不可控。当前已落地策略是导出文件进入 `raw/`，再由清洗、DuckDB、wiki 和 LightRAG 承接分析。P16 后续会把这一步升级为“登记微盘或导出目录 source -> 生成本地 raw snapshot -> 增量处理”，避免同一个源文件更新时反复手工上传。

## 目录结构

```text
<A2A_PROJECT_ROOT>
├─ agent-chat-ui/              # Next.js 前端、控制台页面、API routes
├─ config/                     # 业务口径配置，例如吉客云仓库映射
├─ data/                       # 业务数据、任务、审计、注册表、LightRAG 状态
│  ├─ audit/                   # 企业审计事件 JSONL
│  ├─ cleaned/                 # 清洗后的 CSV
│  ├─ tasks/                   # SQLite queue 和 JSON 任务详情
│  ├─ warehouse/               # DuckDB、Parquet、manifest、quality report
│  ├─ skill_registry/          # Skill 注册表
│  └─ mcp/                     # MCP/API 工具策略
├─ docs/                       # 架构、运行、工作流、参考项目分析、wiki schema
├─ raw/                        # 原始资料入口
├─ scripts/                    # 启停、健康检查、doctor、LightRAG、fact layer、验证
├─ skills/                     # 项目专用 Skill Library，每个子目录包含 SKILL.md
├─ src/a2a_ecommerce_demo/     # LangGraph 后端和工具实现
├─ tests/                      # Python 回归和工程护栏测试
├─ wiki/                       # Obsidian vault 和长期业务记忆
├─ langgraph.json              # LangGraph Server 配置
├─ pyproject.toml              # Ruff / Pyright 配置
├─ requirements.txt            # 后端依赖
├─ requirements-lightrag.txt   # LightRAG 依赖
└─ TODO.md                     # 当前路线图和历史进度
```

## 核心模块

| 模块 | 说明 |
| --- | --- |
| [supervisor_app.py](src/a2a_ecommerce_demo/supervisor_app.py) | LangGraph 多 Agent 入口、路由、模型消息清洗和 active Skill 注入 |
| [agent_tool_registry.py](src/a2a_ecommerce_demo/agent_tool_registry.py) | Tool Registry、Agent 可见工具解析、allowlist 兼容层和工具边界校验 |
| [task_delegation_tools.py](src/a2a_ecommerce_demo/task_delegation_tools.py) | 可恢复后台任务、全链路任务步骤、取消和恢复 |
| [task_queue.py](src/a2a_ecommerce_demo/task_queue.py) | SQLite durable queue、claim lock、heartbeat、retry 和 idempotency |
| [fact_layer_tools.py](src/a2a_ecommerce_demo/fact_layer_tools.py) | Parquet 物化、DuckDB 注册、mart 视图和 dataset registry |
| [business_tools.py](src/a2a_ecommerce_demo/business_tools.py) | 业务数据读取、受控自然语言查询、库存/财务/广告/经营分析 |
| [knowledge_tools.py](src/a2a_ecommerce_demo/knowledge_tools.py) | Obsidian wiki 读写、raw ingest、长期知识沉淀 |
| [wiki_lifecycle_tools.py](src/a2a_ecommerce_demo/wiki_lifecycle_tools.py) | P15 wiki scaffold、index/log、lint、claim/evidence 和决策归档 |
| [lightrag_tools.py](src/a2a_ecommerce_demo/lightrag_tools.py) | LightRAG 同步、查询、状态、失败诊断和恢复 |
| [connector_live_tools.py](src/a2a_ecommerce_demo/connector_live_tools.py) | 吉客云 / 金蝶 ERP 实时只读兜底 |
| [wecom_smartsheet_tools.py](src/a2a_ecommerce_demo/wecom_smartsheet_tools.py) | 企业微信智能表只读读取和本地快照入库 |
| [evidence_graph_tools.py](src/a2a_ecommerce_demo/evidence_graph_tools.py) | P14 经营对象证据图谱 |
| [skill_registry_tools.py](src/a2a_ecommerce_demo/skill_registry_tools.py) | Skill 创建、审批、启停、版本更新和回滚 |
| [mcp_governance_tools.py](src/a2a_ecommerce_demo/mcp_governance_tools.py) | MCP/API 工具权限、写入确认和审计 |
| [sensitive_data_tools.py](src/a2a_ecommerce_demo/sensitive_data_tools.py) | 字段级敏感数据识别、脱敏和访问审计 |

## Agent 分工

| Agent | 责任 |
| --- | --- |
| `top_company_brain_supervisor` | 顶层经营大脑，判断任务类型、分配团队、汇总答案 |
| `friendly_router_agent` | 把普通业务说法翻译成系统任务 |
| `auto_workflow_agent` | 编排发现资料、清洗、入库、同步、分析和报告 |
| `agent_factory_agent` | 生成动态 Agent spec、工具范围和输出 schema |
| `data_agent` | 读取本地结构化数据、DuckDB mart 和 ERP 只读兜底 |
| `knowledge_agent` | 读取 wiki、搜索知识库、写入长期复盘知识 |
| `lightrag_agent` | 执行 LightRAG 同步、查询、实体关系和引用定位 |
| `wiki_ingest_agent` | 把 `raw/` 资料整理为 Obsidian wiki |
| `data_cleaning_agent` | Excel 画像、清洗和大文件分块 |
| `quality_gate_agent` | 数据质量、字段完整性、公式风险和敏感字段 |
| `company_strategy_agent` | 产品线、库存、销售、广告、财务、供应商和历史决策整合 |
| `decision_agent` | 方案对比、证据链、风险和最终建议 |
| `inventory_agent` / `finance_agent` / `risk_agent` / `listing_agent` / `ads_agent` | 专项库存、财务、风险、商品内容和广告诊断 |

Graph ID：

```text
ecommerce_agent
```

## 快速启动

### 1. 配置环境变量

后端配置在根目录 `.env`：

```text
OPENAI_API_KEY=你的 token
OPENAI_MODEL=当前可用模型
OPENAI_BASE_URL=模型供应商的 OpenAI-compatible base URL
EMBEDDING_BINDING_HOST=embedding 供应商地址
EMBEDDING_BINDING_API_KEY=embedding token
EMBEDDING_MODEL=embedding 模型
A2A_DATA_DIR=<A2A_PROJECT_ROOT>/data
```

前端配置在 `agent-chat-ui/.env` 或 `.env.local`：

```text
NEXT_PUBLIC_API_URL=http://localhost:2024
NEXT_PUBLIC_ASSISTANT_ID=ecommerce_agent
NEXT_PUBLIC_AUTH_SCHEME=
```

### 2. 启动服务

macOS / Linux：

```bash
cd <A2A_PROJECT_ROOT>
./scripts/start_fullstack.sh
```

`start_fullstack` 只启动 LangGraph 后端和 Next 前端；LightRAG 是独立服务，需要语义检索或同步时再启动：

```bash
./scripts/start_lightrag_server.sh
```

Windows：

```powershell
cd <A2A_PROJECT_ROOT>
./scripts/start_fullstack.ps1
```

分开启动：

```bash
./scripts/start_backend.sh
./scripts/start_frontend.sh
./scripts/start_lightrag_server.sh
```

停止服务：

```bash
./scripts/stop_fullstack.sh
./scripts/stop_backend.sh
./scripts/stop_frontend.sh
./scripts/stop_lightrag_server.sh
```

## 健康检查

从项目根目录执行：

```bash
./scripts/health_backend.sh
./scripts/health_lightrag.sh
./scripts/doctor.sh
./scripts/doctor.sh --json
curl -s http://127.0.0.1:3000/api/lightrag-status
```

后端应返回：

```json
{
  "ok": true
}
```

LightRAG 空闲状态通常应满足：

```text
pending: 0
processing: 0
failed: 0
pipeline_busy: false
```

`processed` 是动态计数，不是固定版本号。更多运行规则见 [docs/runbook.md](docs/runbook.md)。

## 常用任务话术

整理资料：

```text
我已经把资料放到 raw 目录了，帮我整理进知识库，并同步到完整 LightRAG。完成后告诉我用了哪些文件、生成了哪些页面、有没有需要人工确认的问题。
```

清洗表格：

```text
我放了一些表格，帮我检查并清洗成后续能分析的数据。如果有大文件或表头不清楚，请告诉我怎么处理。
```

基于已有数据分析：

```text
基于所有已有数据，分析 5/6 月 UNOVE 销售提升决策，输出优先级、证据链、风险和下一步动作。
```

库存风险：

```text
帮我看看库存有没有风险，哪些商品可能断货或积压，并给出保守、平衡、激进三个建议。
```

实时 ERP 只读兜底：

```text
使用吉客云查询下 UNOVE 当前全渠道库存信息。请先用品牌货品资料定位 goodsNo / skuBarcode，再按 goods_no 查询库存，并标注页码、过滤条件、row_count、查询时间和仓库口径。
```

实时 SKU 销售：

```text
用吉客云实时查询 UNOVE 近 30 天按日期、渠道/店铺、SKU 汇总的销量和销售金额；如果销售汇总接口返回空数据，请说明是吉客云报表权限或过滤口径缺口，不要回退成当前实时日销。
```

库存周转：

```text
使用吉客云分仓库存筛选品牌 UNOVE 柔诺伊，选择所有仓库。先分析库存结构，再结合近 30 天销量或出库数据计算数量口径库存周转和覆盖天数；如果没有成本价、批次效期或销量数据，请分别标注缺口，不要编造金额周转。
```

老板报告：

```text
帮我生成一份面向老板的国内多平台电商经营报告。请整合销售、广告、库存、财务和履约数据，输出关键结论、风险、机会和下一步动作。
```

规则提醒：

- “基于已有数据”只做只读分析，不应重新处理 `raw/` 或启动 LightRAG 同步。
- “刚上传、放到 raw、清洗入库、同步知识库”才会启动后台处理。
- 如果 Agent 需要执行高风险动作，前端会展示人工确认卡。
- 实时库存答案必须区分库存数量、可用库存、金额口径、批次效期和仓库映射缺口。

## 验证命令

完整稳定性验证：

```bash
./scripts/verify_all.sh
```

后端全量验证：

```bash
./scripts/verify_python.sh
```

前端单测：

```bash
./scripts/verify_frontend.sh --unit-only
```

前端类型检查和构建：

```bash
./scripts/verify_frontend.sh
```

也可以在前端目录使用 npm scripts：

```bash
cd agent-chat-ui
npm test
npm run verify
```

## 常见问题

### 打开网页但无法对话

检查后端：

```bash
curl -s http://127.0.0.1:2024/ok
```

失败时重启后端：

```bash
./scripts/start_backend.sh
```

### 页面提示找不到 Assistant 或 Graph

确认 `agent-chat-ui/.env` 或 `.env.local`：

```text
NEXT_PUBLIC_API_URL=http://localhost:2024
NEXT_PUBLIC_ASSISTANT_ID=ecommerce_agent
NEXT_PUBLIC_AUTH_SCHEME=
```

修改后重启前端。

### LLM 调用失败

检查根目录 `.env`：

- `OPENAI_API_KEY` 是否正确。
- `OPENAI_MODEL` 是否为当前可用模型。
- `OPENAI_BASE_URL` 是否符合供应商要求。
- 供应商余额、额度和地区访问是否正常。

### LightRAG pending 长时间不动

排查顺序：

1. 查看 `/data-health` 和 `/api/lightrag-status`。
2. 检查 `data/tasks` 是否有误触发后台任务。
3. 先调用 LightRAG 诊断工具，不要反复 retry。
4. 检查供应商模型日志、embedding 稳定性和 LightRAG worker 状态。

### 前端出现 BadRequestError 或 network error

当前前端会把常见 LangGraph stream 错误转为中文提示：

- `连接后端失败`：通常是 LangGraph 后端未启动、正在重启，或 SDK 抛出 fetch 错误。
- `请求被模型服务拒绝`：通常是模型供应商拒绝本次请求。
- `对话历史异常，系统已自动保护`：通常是旧线程残留不完整 tool 消息；后端会在模型输入前自动清洗。

排查日志：

```bash
tail -n 120 langgraph-server.log
tail -n 80 frontend.err.log
tail -n 120 lightrag-server.err.log
```

### 同一份 Agent 报告显示两次

多 Agent handoff 时，子团队 supervisor 可能先产出一份最终报告，顶层 `top_company_brain_supervisor` 随后再转述同一份报告。前端历史渲染会折叠相邻的重复 supervisor 最终报告，只保留顶层最终答案；trace 面板仍可能显示两个 Agent 节点，这是为了保留执行过程。

### 吉客云库存输出“数据缺口”

这通常不是前端错误，而是实时接口口径限制：

- `brandName` 为空时，系统只能通过货品名称和品牌 alias 扩展 goodsNo，可能遗漏命名不规范的货品。
- `costPrice` 缺失时，不能做库存金额、成本金额或金额口径周转，但可以在有销量/出库时做数量口径周转。
- 吉客云销售汇总需要报表/吉智 BI 权限；如果 `query_jackyun_channel_sales_summary` 返回 0 行，只能说明销售汇总权限或过滤口径未命中，不能把库存接口的近销字段包装成完整销售订单明细。
- “未映射仓库”表示当前仓库名没有命中 `warehouse_scope_rules`，补充配置后重启 backend 即可。
- 批次有效期需要读取 `batch_inventory`，普通库存快照不会批量返回效期。

## 参考文档

- [TODO.md](TODO.md)：路线图、P9-P15 清单和历史进度。
- [progress.md](progress.md)：近期落地记录和验证命令。
- [docs/runbook.md](docs/runbook.md)：健康检查、LightRAG、后台任务和验证规则。
- [docs/architecture.md](docs/architecture.md)：核心架构和守卫边界。
- [docs/reference-project-analysis.md](docs/reference-project-analysis.md)：OpenClaw、MiroFish、Hermes Agent 和 Karpathy LLM Wiki 的参考取舍。
- 本 README 的“参考仓库综合吸收路线”：`supermemory`、`agency-agents`、`harness-anything` 的可结合能力、落点、优先级和禁止边界。
- [docs/task-delegation-workflow.md](docs/task-delegation-workflow.md)：后台任务和子任务委派说明。
- [docs/lightrag-integration.md](docs/lightrag-integration.md)：LightRAG 集成说明。
- [docs/wiki_schema.md](docs/wiki_schema.md)：LLM Wiki 页面、证据和归档规范。

## 后续路线

S0.5 安全治理与历史上下文卫生已经落地并通过 preflight，P16 Source Registry 也已落地。下一阶段可以继续用现有数据跑真实业务试跑；如果要增强产品复利，优先推进参考仓库吸收路线：先做 `agency-agents` 精选 Agent 模板和 handoff/QA gate，再做 Supermemory 只读上下文记忆试点，最后评估 `harness-anything` 风格的 Skill/MCP marketplace 与 Windows worker 报告导出能力。

当前不急着推进 P8。只有当本项目需要作为标准 A2A 服务被其他系统调用，或需要接入远程 Agent 服务时，再补 A2A Protocol schema、本地 A2A Server/Client、远程 Agent 权限和审计。
