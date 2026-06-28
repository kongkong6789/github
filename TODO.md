# A2A 项目后续 TODO

## 当前未完成摘要（按架构层）

当前项目已经具备可运行的本地多 Agent 主链路：前端对话、LangGraph supervisor、多团队 Agent、DuckDB fact layer、Obsidian wiki、LightRAG、可恢复后台任务、trace 面板、数据健康页和 Skill / MCP 显示页都已落地。本轮已补齐 P0/P1/P4/P5/P6/P7 清单中的核心工程项；如果仅限公司内部、本地 PM 使用，标准 A2A Server/Client 可以暂缓。下一阶段更应该把项目从“能跑”升级为“稳定、可观察、可长期维护的经营工作台”。

- **S0 稳定交付层**：完整 LangGraph interrupt 人工确认、LightRAG embedding 稳定配置、LangGraph checkpoint 持久化策略、旧 checkpoint pickle 结构化迁移和 S0.5 安全治理/历史上下文卫生已完成；下一步可以进入真实业务试跑。
- **P0 数据闭环层**：二级分区索引、异常库存 mart、前端全链路进度和产物链接已完成；后续只做阈值配置、专用详情页和体验优化。
- **P1 动态 Agent 层**：Agent Registry、dynamic_agent_hub、一句话生成/确认/执行、生命周期、审计、模板沉淀和 active Skill 自动注入已完成；后续只做独立管理页和治理体验优化。
- **P3 真实业务接入层**：吉客云/金蝶 ERP 已具备“DuckDB 优先、实时只读 ERP 兜底”的前端对话工具；吉客云库存已补品牌扩展、仓库口径映射、SKU/品名防编造和周转/批次效期口径护栏；吉客云销售汇总已封装为只读工具，可按日期 + 渠道/店铺 + SKU 查询销量/金额；国内平台、广告、客服售后评价受接口权限限制，不再承诺直接 API，统一走平台后台导出文件、raw 清洗、DuckDB/wiki/LightRAG 入库兜底。
- **P4/P6/P8 扩展治理层**：Connector/Skill/MCP 注册审批、工具权限、审计、写入确认、字段级敏感数据轻量治理、前端提示词自动匹配 Skill 和 Runtime Capability 统一调用层已完成；后续创建或上传的 Skill/MCP 可以先登记/发现，再按只读直接执行、写入人工确认的边界调用；P8 只有在需要外部系统调用本地 Agent 或调用远程 Agent 时再做。
- **P9/P10 工作台产品化层**：参考 OpenClaw 和 MiroFish，`/api/workbench` 已把 data-health、governance、trace、task、logs 收敛为统一 typed control plane；任务历史和任务详情页已落地。
- **P11/P12 运行时可靠性层**：参考 Hermes Agent，把静态工具 allowlist 升级为工具注册中心，并把 JSON 任务队列逐步升级为 SQLite durable queue。
- **P13/P14 可观测与证据层**：doctor、logs、config schema、审计字段和经营对象证据图谱已完成，PM 可以从任务、报告、wiki、数据集和风险节点复盘结论来源。
- **P15 LLM Wiki 知识复利层**：已参考 Karpathy LLM Wiki，把当前 wiki 从“数据处理产物 + 决策报告库”升级为带 schema、index、log、lint 和 claim/evidence 生命周期的长期知识代码库。
- **P16 Source Registry 与增量数据源同步层**：2026-05-30 已落地。已从“每次手工上传 raw”升级为“登记长期数据源 -> 按需同步变更 -> 生成版本化 raw snapshot -> 增量清洗/入库/wiki/LightRAG 同步”；企业微信微盘真实租户参数、管理企业微信等外部管理字段先保留为空占位，COS/OSS 仍只是后续归档镜像选项。
- **P17 参考仓库能力吸收层**：2026-06-01 已完成 `supermemory`、`agency-agents`、`harness-anything` 三仓库调研和第一批工程落地。已新增 evidence-first Agent 模板库、动态 Agent 模板起草、handoff/QA 事件、任务详情展示、Supermemory 只读/写入确认策略、外部记忆敏感拦截、Skill/MCP marketplace 模板和桌面 harness doctor 边界。

## 当前仍未完成的 TODO（P16 后）

截至 2026-05-30，P16 正文已全部完成；`TODO.md` 中仍未勾选的事项共 15 项，均属于后续增强或暂缓路线，不阻塞当前本地经营工作台试运行：

1. **Runtime Capability / MCP 治理增强**：前端上传 MCP policy 向导、远端 MCP schema 自动发现、capability 使用统计页、Skill/MCP marketplace 导入模板。
2. **A2A 标准化 / 远程 Agent**：A2A Protocol schema、本地 A2A Server、A2A Client、本地/远程 agent 统一路由、远程上下文权限、跨系统审计、前端显示本地/远程调用状态。
3. **LightRAG 运维 follow-up**：如果后续再次出现 pending 长时间不动，优先检查供应商模型日志、embedding 供应商稳定性和 LightRAG worker 状态。
4. **真实库存周转增强**：把 `inventory_stock` / `brand_expansion.summary` 与 `query_jackyun_channel_sales_summary` 自动组合成覆盖天数报告，并按需读取成本价/采购价字段和敏感字段审计。
5. **批次效期增强**：当小样、赠品或临期风险占比高时，自动追加 `batch_inventory / erp.batchstockquantity.get` 查询，输出批次效期风险。
6. **参考仓库吸收增强**：P17 第一批已完成；后续只剩 Product/trend/feedback、Automation governance、MCP builder、MemoryBench、memory graph、桌面 connector 等低优先级扩展，不阻塞当前工作台试跑。

## 推荐下一阶段路线图

### S0.5：安全治理与历史上下文卫生（2026-05-27 多 Agent 审阅新增，最高优先级）

本轮多 Agent 只读审阅覆盖了后端、前端、项目 Skill Library、README/TODO/docs 和历史线程归档。结论：主功能已经能支撑本地经营工作台试运行，但真实业务试跑前必须先做一轮安全治理、归档脱敏和运行边界收口。否则真实 ERP / 企业微信 / LLM 凭据、私密智能表链接、本地文件路径、历史 tool message、写入型 Skill 代码和误挂载的确认类工具会继续污染 Agent 上下文，并放大误调用外部系统的风险。

2026-05-27 已完成落地并通过 preflight：`scripts/doctor.py --json` 无 fail，`scripts/repair_thread_archives.py --write --confirm` 已生成本地备份/迁移清单，`./scripts/verify_all.sh` 退出码 0。

#### S0.5 总体验收标准

- [x] 根目录 `.env` 不再被 Git 跟踪，`.gitignore` 明确忽略 `.env` / `.env.*`，只保留 `.env.example` 可提交；曾进入版本库或历史对话的真实密钥已从仓库、文档、测试和归档暴露面出库，供应商侧轮换需凭据持有人按 runbook 执行。
- [x] 项目内不再硬编码真实 AppKey、AppSecret、公网 ERP 地址、账套 ID、管理员用户名、WeCom `scode`、MCP `apikey` 或真实业务私密链接。
- [x] 前端 API 不允许通过 query/body 读取工作区外文件；所有 `sourcePath`、`reportPath`、`taskId` 都做 realpath + root allowlist 校验。
- [x] 历史对话归档写入前会脱敏 URL 查询参数和大体量业务行；旧归档可 dry-run / write 修复，doctor 能准确发现 `values.messages` 内的 orphan tool message。
- [x] Agent 实际挂载工具不包含需确认、写入、高风险或 destructive 工具；确认类工具统一返回 Agent Inbox approval，不直接交给模型执行。
- [x] `scripts/common.sh` 不再使用 `eval` 解析 `.env`；`scripts/query_fact_layer.sh` 不再把 `--limit` 拼进 Python `-c` 源码。
- [x] `query_fact_layer` 从黑名单式 SQL 拦截升级为表/视图白名单或 AST allowlist，只允许查询 `datasets.*`、`marts.*` 等受控事实层对象。
- [x] `skills/` 运行目录只保留只读 adapter、只读 schema、只读文档和必要测试；全功能桌面写入脚本、临时 JSON、CLI zip、缓存和 live 写测试移出 governance 扫描范围。

#### S0.5.1 凭据、Git 卫生和密钥轮换

发现与证据：

- [x] 根目录 `.env` 当前被 Git 跟踪：`git ls-files .env` 返回 `.env`；`.gitignore` 只忽略了 `agent-chat-ui/.env`，没有忽略根目录 `.env`。
- [x] 当前 `.env` diff 新增了 ERP / WeCom / Node / Kingdee / Jackyun 运行配置；HEAD 中已经存在 LLM / embedding / LightRAG 相关真实运行配置。
- [x] 吉客云测试和文档里存在疑似真实 AppKey / AppSecret：`skills/jackyun_erp_readonly_connector_skill/tests/test_jackyun_api.py` 和 `docs/PROJECT_MANUAL.md`。
- [x] 金蝶 Skill README 示例暴露了真实服务地址、账套 ID 和管理员用户名；应当视为敏感运行信息，而不是公共安装说明。

待办：

- [x] 执行 `git rm --cached .env`，保留本地 `.env` 文件但从版本控制中移除。
- [x] 更新 `.gitignore`：加入 `.env`、`.env.*`，并用 `!.env.example` 保留模板可提交。
- [x] 清理 `.env.example`：只保留占位符和说明，不出现真实 host、真实账号、真实 key、真实 doc URL。
- [x] 清理曾进入 `.env`、测试、文档或历史对话的真实密钥暴露面，并列出必须在供应商控制台轮换的范围：OpenAI / embedding / WeCom MCP / 吉客云 AppSecret / 金蝶密码 / 其他供应商 key。
- [x] 把 `tests/test_jackyun_api.py` 中的真实 AppKey / AppSecret 改为固定假值，例如 `TEST_APP_KEY` / `TEST_APP_SECRET_DO_NOT_USE`，并更新预期签名。
- [x] 把吉客云文档里的“当前统一 AppKey 为真实值”改成 `<jackyun-app-key>`，只说明字段语义，不记录真实值。
- [x] 把金蝶 README 中的真实公网地址、账套 ID、Administrator 示例改成 `https://<kingdee-host>/k3cloud`、`<acct-id>`、`<username>`。
- [x] 增加仓库策略测试：`tests/test_p7_engineering_guardrails.py` 或新测试检查 `.env` 不在 `git ls-files` 中、文档不包含真实 key 模式、`.env.example` 不含生产值。
- [x] 增加 doctor 检查：如果根 `.env` 被 Git 跟踪，直接 `fail`；如果文档/测试匹配高风险密钥模式，至少 `warn` 并列出文件。

验收命令：

```bash
git ls-files .env
git diff -- .env
.venv/bin/python scripts/doctor.py --json
.venv/bin/python -m unittest tests.test_p7_engineering_guardrails tests.test_doctor
```

预期：

- `git ls-files .env` 无输出。
- `git diff -- .env` 不再展示真实密钥变更。
- doctor 对根 `.env` 被跟踪不再误报 `ok`。

#### S0.5.2 历史对话归档修复、脱敏和上下文污染治理

发现与证据：

- [x] `scripts/doctor.py --json` 报告 19 个 archived thread 无 orphan tool message，但 `scripts/repair_thread_archives.py` dry-run 仍发现 `data/thread_archive/019e2c51-88eb-7db2-9a8c-9ccb601f1ed4.json` 有 1 条 orphan tool message。说明 doctor 对当前归档结构 `values.messages` 的检查不完整。
- [x] `data/thread_archive/019e4d58-8a41-7073-a57d-1d17c7ad16b2.json` 保存了企业微信智能表私密 URL、`scode`、docid、sheet_id 和业务行数据；这些内容会被历史展示和续聊上下文复用。
- [x] 历史归档里仍可见机器路径和过期路径口径，例如 `<A2A_PROJECT_ROOT>...` 或旧桌面路径，可能污染后续回答。
- [x] 前端已有 `ensureToolCallsHaveResponses` 和后端 `_sanitize_messages_for_llm`，但前端修复逻辑只检查“下一条是否 tool”，不严格校验每个 `tool_call_id`。

待办：

- [x] 修复 `scripts/doctor.py::check_thread_archive`，支持同时检查顶层 messages 和 `values.messages`；检查 AI tool_calls 后连续 tool message 是否精确覆盖每个 `tool_call_id`。
- [x] 扩展 `repair_thread_archives.py` dry-run 输出：列出孤立 tool、缺失 tool response、错配 tool_call_id、多余 tool response、超长消息、敏感 URL、绝对路径。
- [x] 对当前 `data/thread_archive` 先 dry-run，再在确认后 write 修复，并备份到 `data/thread_archive_backups/<timestamp>`。
- [x] 支持可选扫描 `data_reset_archive/**/data/thread_archive` 和历史 backups，但默认不修改历史取证材料；提供 `--include-reset-archive` 显式参数。
- [x] 为归档写入新增脱敏层：URL query 中的 `scode`、`apikey`、`access_token`、`token`、`secret`、`key` 统一替换为 `***REDACTED***`。
- [x] 对 WeCom tool result 做瘦身：归档默认只保存 `transport`、`source_id`、`dataset`、`row_count`、`raw_total_count`、`schema`、`source_sheet_ids`、少量脱敏样例，不保存完整业务行。
- [x] 对归档中的绝对路径统一规范化：项目内路径显示为 `<A2A_PROJECT_ROOT>/...` 或相对路径；项目外旧路径只作为错误摘要，不进入模型续聊 payload。
- [x] 把前端 `ensureToolCallsHaveResponses` 改成严格状态机：AI tool_calls 必须有非空唯一 id；后续连续 tool message 必须按 id 精确匹配；孤立 tool 删除或隔离；缺失 tool response 插入 synthetic message。
- [x] `/api/local-threads` 的 `sanitizeMessages` 写入归档前复用同一状态机，避免坏序列持久化。
- [x] 增加前端测试：多 tool call、错 id、孤立 tool、缺 tool response、超长 tool result、WeCom URL 脱敏。

验收命令：

```bash
.venv/bin/python scripts/repair_thread_archives.py
.venv/bin/python scripts/doctor.py --json
.venv/bin/python -m unittest tests.test_thread_repair_tools tests.test_doctor tests.test_supervisor_model_config
cd agent-chat-ui && ./scripts/with-env-node.sh ./node_modules/.bin/esbuild src/lib/local-archive-thread.test.ts src/lib/stream-errors.test.ts --bundle --platform=node --format=esm --outdir=.tmp-test-review '--external:node:*'
cd agent-chat-ui && ./scripts/with-env-node.sh node --test .tmp-test-review/local-archive-thread.test.js .tmp-test-review/stream-errors.test.js
```

预期：

- 修复前 dry-run 能准确列出待修归档；修复后 doctor 不再和 repair dry-run 结论矛盾。
- 历史归档不再暴露 WeCom `scode`、MCP `apikey` 或完整智能表业务行。
- 从归档续聊不会触发 `Messages with role 'tool' must be a response...` 类模型协议错误。

#### S0.5.3 前端 API 本地文件边界收口

发现与证据：

- [x] `/api/governance` 的 `import_skill` 直接把 `body.sourcePath` 传给 `createDraftSkillFromSource`；`resolveSourcePath` 接受绝对路径和工作区相对路径，可能导入工作区外任意可读 `.md` / `SKILL.md` 并持久化到 Skill Registry。
- [x] `/api/evidence-graph` 的 `reportPath` 来自 query；`addReportFile` 接受绝对路径并读取内容。
- [x] `/api/evidence-graph` 的 `taskId` 直接拼到 `paths.taskDir`，缺少严格白名单正则；`../` 这类路径需要明确拒绝。
- [x] Evidence Graph 现有测试固化了绝对 `reportPath` 行为，缺少 API route 级安全测试。

待办：

- [x] `governance import_skill` 禁止工作区外绝对路径；只允许 `wikiDir`、`skillLibraryDir` 或显式 upload temp dir 内的 realpath。
- [x] 对 `sourcePath` 做 `\0`、`..`、绝对路径、软链逃逸、非 `.md` / 非 `SKILL.md`、secret-like filename、超大文件大小校验。
- [x] multipart Skill folder upload 增加文件数量、总大小、单文件大小、允许后缀、禁止目录名、禁止 `.env` / `config.py` / cache / binary zip 的规则。
- [x] `evidence-graph reportPath` 只允许 `data/reports`、`wiki/decisions` 或 `wiki/datasets` 内相对路径；拒绝外部绝对路径。
- [x] `taskId` 只允许 `[a-zA-Z0-9\u4e00-\u9fff._-]` 的安全 id，拒绝 `/`、`\`、`..`、URL 编码后的路径分隔符。
- [x] 所有路径校验采用 realpath 后 `path.relative(root, target)` 判断，防止符号链接逃逸。
- [x] 增加 `/api/governance` route handler 测试：工作区外 sourcePath、`.env`、secret 文件、过大 upload、软链逃逸均拒绝。
- [x] 增加 `/api/evidence-graph` route handler 测试：绝对 reportPath、`taskId=../../x`、URL encoded traversal、超大 limit 均拒绝或 clamp。

验收命令：

```bash
cd agent-chat-ui && ./scripts/with-env-node.sh ./node_modules/.bin/tsc --noEmit --pretty false
cd agent-chat-ui && ./scripts/with-env-node.sh ./node_modules/.bin/esbuild src/lib/governance.test.ts src/lib/evidence-graph.test.ts --bundle --platform=node --format=esm --outdir=.tmp-test-security '--external:node:*'
cd agent-chat-ui && ./scripts/with-env-node.sh node --test .tmp-test-security/governance.test.js .tmp-test-security/evidence-graph.test.js
```

#### S0.5.4 MCP / Governance policy 写入强校验

发现与证据：

- [x] `/api/governance` 的 `upsert_mcp_policy` 基本信任客户端传入的 `toolAction`、`readOnly`、`riskLevel`。
- [x] 当前实现允许组合出 `readOnly=true`、`action=write_external_*`、`riskLevel=low` 这类自相矛盾 policy，治理页可能误判高风险写工具为只读低风险。

待办：

- [x] 为 MCP policy upsert 增加 zod 或手写枚举 schema：`action`、`risk_level`、`execution_mode`、`allowed_callers`、`data_sources` 均限定枚举或受控模式。
- [x] 任何 `action` 包含 `write`、`external`、`delete`、`submit`、`push`、`save`、`send`、`create`、`update` 时强制 `read_only=false`、`requires_human_confirmation=true`、`risk_level=high` 或更高。
- [x] 如果 tool name 已存在于 `Tool Registry`，read-only / risk / requires_confirmation 必须从后端 registry 派生，不能由前端覆盖。
- [x] 对上传 MCP/API policy 增加 `external_write_enabled=false` 的不可覆盖保护；即使客户端传 true 也写 false。
- [x] `runtime_capability_tools._invoke_mcp_jsonrpc_tool` 的 initialize 和 tools/call 都调用 `raise_for_status()`，错误摘要进入 audit 前脱敏。
- [x] 增加测试覆盖：伪装只读写工具、风险级别降级、外部写 enabled、未知 caller、MCP HTTP 非 200。

#### S0.5.5 Agent 工具挂载和确认边界

发现与证据：

- [x] `resolve_agent_tools(..., include_confirmation=True)` 默认包含确认类工具；`supervisor_app._agent_tools()` 运行时未显式关闭。
- [x] 测试验证了 `resolve_direct_agent_tool_entries`，但实际 create_react_agent 挂载路径使用 `_agent_tools()`。
- [x] 这会让 `sync_connector_dataset`、`sync_wecom_smartsheet_snapshot`、`register_runtime_mcp_tool`、rollback/cleanup 等工具进入 LLM 可直接调用面，确认门禁退化为元数据约定。

待办：

- [x] 把 `resolve_agent_tools` 默认改为 `include_confirmation=False`；如确需获取确认工具，调用点必须显式传 true 并说明原因。
- [x] `supervisor_app._agent_tools()` 使用 direct/read-only 工具集合；只有专门 approval executor 可以拿到确认/写入工具。
- [x] `TOP_SUPERVISOR_SAFE_READ_TOOLS` 继续强制 read-only，不允许 requires_confirmation。
- [x] 确认类工具统一返回 `confirmation_required` payload，不直接执行任何外部写入或 destructive 本地操作。
- [x] 对 `auto_workflow_agent`、`agent_factory_agent`、`knowledge_agent` 单独审阅：哪些本地写入可以作为 workflow 步骤，哪些必须进入 approval。
- [x] 增加运行时挂载测试：构建 supervisor 后逐个 agent 的 tools 中不包含 `requires_confirmation=true`、`group=external_write_request`、`group=destructive_maintenance`。
- [x] 增加回归测试：LLM 不能通过 Runtime Capability 直接执行写入类 MCP / Skill / Tool。

验收命令：

```bash
.venv/bin/python -m unittest tests.test_agent_tool_registry tests.test_supervisor_model_config tests.test_runtime_capability_tools tests.test_mcp_governance_tools
```

#### S0.5.6 shell、dotenv 和 fact layer 查询安全

发现与证据：

- [x] `scripts/common.sh` 用 `eval "printf '%s' \"$value\""` 展开 `.env`，恶意或误写的 `.env` 值可在启动脚本时执行命令。
- [x] `scripts/query_fact_layer.sh` 将 `--limit` 直接插入 Python `-c` 源码，`--limit` 可形成命令注入面。
- [x] `query_fact_layer` 使用黑名单拦截 `read_csv`、`read_parquet`、`pragma` 等字符串，并把用户 SQL 包进 `SELECT * FROM (...) LIMIT ...` 执行；DuckDB 外部读取语法较多，黑名单容易漏。
- [x] `.env.example` 使用 `${OPENAI_MODEL}` 等插值，但 PowerShell `common.ps1` 只去引号不展开，Windows/Unix dotenv 行为不一致。

待办：

- [x] 移除 `scripts/common.sh` 中的 `eval`；只支持字面值和安全的 `${VAR}` 替换，或统一调用 Python `python-dotenv` 解析后输出环境。
- [x] 给 `.env` 解析增加测试：包含 `$(touch /tmp/a2a-pwned)`、反引号、分号、未闭合引号时不会执行命令。
- [x] `scripts/query_fact_layer.sh` 把 SQL 和 limit 都通过 env 或 argv 传入 Python，Python 内 `int()` 校验 limit，并 clamp 到上限。
- [x] `query_fact_layer` 改为 allowlist：只允许 SELECT/CTE 访问 `datasets.*`、`marts.*`、已注册 view；禁止裸表、外部函数、文件路径、extension、attach、copy、httpfs、secret manager。
- [x] 如暂不引入 SQL AST parser，至少用 DuckDB catalog 校验 query plan 中出现的表名都在 registry allowlist 内。
- [x] 增加 limit 上限，例如默认 200、最大 1000；过大 limit 自动 clamp 并返回 warning。
- [x] 统一 Bash / PowerShell dotenv 行为：要么 `.env.example` 不再使用 `${...}` 插值，要么两端都使用同一解析器。
- [x] 增加测试：`read_csv_auto` 已覆盖，还要补 `FROM '/tmp/file.csv'`、`COPY`、`INSTALL/LOAD`、`ATTACH`、`httpfs`、`--limit` Python 注入。

验收命令：

```bash
bash -n scripts/common.sh scripts/query_fact_layer.sh
.venv/bin/python -m unittest tests.test_intent_router_and_safety tests.test_fact_layer_pipeline
./scripts/query_fact_layer.sh --sql "SELECT 1 AS ok" --limit 1
```

#### S0.5.7 ERP / Skill Library 运行目录裁剪

发现与证据：

- [x] `skills/kingdee_erp_readonly_connector_skill/SKILL.md` 说只读，但目录内仍有 `api.py` 的 Save/Submit/Push、`kd_submit.py`、导入脚本、push 测试、真实样例配置和临时 JSON。
- [x] `skills/jackyun_erp_readonly_connector_skill` 只读 wrapper 之外仍包含创建销售单、库存单据、CLI 二进制 zip、缓存、临时测试和疑似真实 AppKey 文档。
- [x] 金蝶 live tests 存在模块导入阶段登录、默认 push 或保存采购申请的风险；不应在普通测试命令中可触发真实 ERP 写入。
- [x] `vendor/desktop-skills/README.md` 说排除发布 zip、缓存、CLI 二进制，但实际 `skills/` 下仍有 zip、`__pycache__`、`.pytest_cache`、`_tmp_view_*.json`。

待办：

- [x] 将项目运行目录裁剪为最小只读 adapter：`SKILL.md`、`skill.registry.json`、只读 `api/read_client`、字段映射、只读 docs、只读 tests。
- [x] 把全功能桌面包、写入脚本、Save/Submit/Push/PushSalesIC、临时诊断脚本、CLI zip 移到 `vendor/reference-only/` 或本地不被 Git 跟踪目录，并明确不被 `/governance` 扫描。
- [x] 对 `skills/**` 增加打包清单校验：禁止 `.env`、`config.py`、`data/`、`_tmp*`、`.pytest_cache`、`__pycache__`、`*.zip`、`dist/`、`output/`、`tmp_*push*.py`。
- [x] 所有 live ERP tests 默认 skip；必须同时设置 `RUN_LIVE_ERP_TESTS=1` 和写入二次确认变量才允许 Save/Submit/Push 测试。
- [x] 金蝶 `auth.py` 所有 requests 增加 timeout；默认不打印完整登录响应，debug 日志必须脱敏 session、cookie、acct、username。
- [x] 金蝶 `FilterString` 构造统一 escape helper 和字段白名单，避免 keyword 拼接。
- [x] 吉客云 CLI zip 如确需保留，必须有 SHA256 allowlist 校验；更推荐从官方发布下载并校验后执行，不随 Skill 打包。
- [x] 修复文件权限：源码 `0644`，脚本 `0755`，敏感本地配置不可 group/other writable。
- [x] `unove_domestic_channel_strategy` 增加 `effective_from`、`effective_to`、`owner`、`source`，避免月度 GMV 目标过期仍被 Agent 当长期事实。

验收命令：

```bash
find skills -name '.env' -o -name 'config.py' -o -name '_tmp*' -o -name '*.zip' -o -name '__pycache__' -o -name '.pytest_cache'
.venv/bin/python -m unittest tests.test_skill_registry_tools tests.test_connector_registry tests.test_agent_tool_registry
```

#### S0.5.8 状态持久化、依赖和可维护性补强

发现与证据：

- [x] `task_delegation_tools._save_task` 先写 JSON 再 upsert SQLite，两个存储不是一个事务；恢复流程也会跨 JSON / SQLite 多次更新。
- [x] `state_io.file_lock` 使用 `.lock` + `O_EXCL`，进程崩溃后残留 lock 只会等到 timeout，没有 stale lock 回收。
- [x] `requirements.txt` 只有 `>=` 下限，没有 lock / constraints，LangGraph / LangChain / DuckDB 更新可能导致本地不可复现。
- [x] `pyproject.toml` 只把 `src` / `tests` 纳入 Ruff/Pyright，`scripts/*.py` 和 Skill 下关键 Python 没进统一 lint。
- [x] 前端 `ThreadProvider` context value 未 memoize；`LightRAGStatusStrip` 多实例重复轮询；`agent-trace-panel` 存在请求竞态；`Thread` 组件过大。

待办：

- [x] 明确 SQLite 为任务队列 source of truth，JSON 只作为可重建导出；新增 reconciliation/outbox，避免双写不一致。
- [x] `file_lock` 写入 pid + timestamp + hostname；超过 TTL 后检查 pid 是否仍存在，允许 stale lock 回收。
- [x] `atomic_write_text` 写入 tmp 后 fsync 文件和父目录，再 `os.replace`。
- [x] 增加 `requirements-lock.txt` 或 constraints 文件；生产/验证命令使用锁定版本。
- [x] 扩大 lint 范围：`scripts/*.py`、关键 `skills/*/*.py` 纳入 Ruff；shell 增加 `shellcheck`；PowerShell 增加 PSScriptAnalyzer 或至少静态语法检查。
- [x] 前端 `ThreadProvider` 用 `useMemo` 包裹 context value；把状态和 actions 拆分为两个 context。
- [x] LightRAG 状态轮询提升为 provider/hook，页面多个位置消费同一状态，避免重复请求。
- [x] `agent-trace-panel` 使用 `AbortController` 或 request id guard，避免旧 thread 响应覆盖新 thread 状态。
- [x] 拆分 `components/thread/index.tsx`：`ChatHeader`、`MessageList`、`Composer`、`LightRAGStatus`、`EmptyStateActions`、`useThreadSubmit`。
- [x] 修复历史侧栏“清空全部”：仅有本地归档时也应可清空，或 UI 文案明确只清远端线程。

#### S0.5.9 文档和路线图同步

发现与证据：

- [x] README 后续路线仍写“下一步优先做真实业务试跑”，但本轮审阅结论是业务试跑前先做安全治理。
- [x] `docs/architecture.md` 仍说 `AGENT_TOOL_ALLOWLISTS` 是 single registry，但当前代码已经有 Tool Registry v2，legacy allowlist 只是兼容层。
- [x] `docs/reference-project-analysis.md` 的部分“后续增强方向”已经落地，例如 quality gate、agent factory、知识图谱、任务状态、ERP。
- [x] `vendor/desktop-skills/README.md` 描述与当前目录不一致。

待办：

- [x] README 后续路线改为：S0.5 安全治理完成后再进行真实业务试跑。
- [x] `docs/architecture.md` 改成：Tool Registry v2 是主权限注册表，legacy allowlist 是兼容层，运行时挂载默认 direct/read-only。
- [x] `docs/reference-project-analysis.md` 标注“历史参考”，逐项标注已吸收、已落地、仍未做。
- [x] `vendor/desktop-skills/README.md` 与实际目录对齐，说明全功能桌面包只可作为 reference-only，不参与 runtime governance scan。
- [x] 将本节 S0.5 的验收命令加入 `docs/runbook.md`，作为真实业务试跑前的 preflight。

#### S0.5 推荐执行顺序

- [x] 第 1 步：密钥出库、供应商侧轮换清单和 `.gitignore` 修复；这是唯一 CRITICAL 的前置项。
- [x] 第 2 步：前端 API 路径边界和归档脱敏；阻断本地文件读取和私密链接继续进入上下文。
- [x] 第 3 步：Agent 工具挂载改为 direct/read-only，确认类工具统一走 approval。
- [x] 第 4 步：shell / SQL 安全修复；避免本地脚本和 DuckDB 查询成为文件读取或代码执行入口。
- [x] 第 5 步：Skill Library 裁剪；只读 adapter 与全功能桌面写入包分离。
- [x] 第 6 步：状态持久化、依赖锁和前端可维护性优化。
- [x] 第 7 步：README / docs / runbook 同步，然后再开始真实业务试跑。

## 当前进度记录（2026-05-21）

- [x] 已新增企业微信智能表只读数据源：通过 WeDoc MCP 读取记录，`.env` 只保存 MCP 服务地址，不再把智能表私有 URL、docid、sheet_id 或密钥写死进脚本。
- [x] 已改为运行时 URL 优先：前端提示词提供 `doc.weixin.qq.com/smartsheet` 链接即可读取，工具从 URL 的 `tab` 自动识别 `sheet_id`；`config/wecom_smartsheet_sources.json` 默认不再固化日销表 docid 和 5 个 sheet_id。
- [x] 已取消企业微信自建应用 API 直连读取文档内容：`query_wecom_smartsheet_records` 不再通过 `gettoken` / `wedoc/smartsheet/get_records` 回退读取；现有智能表查询保持走 MCP，并支持 URL / 多子表保留 `_source_sheet_id`。
- [x] 已把企业微信智能表 MCP 读取工具补进 MCP/API policy：`query_wecom_smartsheet_records` 在 `/governance` 显示为 low-risk read-only，允许数据、决策、策略、workflow 和 agent factory 相关 Agent 调用。
- [x] 已把 `wecom_smartsheet` 纳入 connector registry、Tool Registry、Agent allowlist 和 supervisor 提示词；分析 Agent 可只读查询，只有 workflow Agent 可同步本地快照。
- [x] 已保留治理边界：桌面脚本里的 webhook 新增/修改/删除没有开放给决策 Agent；如需写回智能表，后续必须走 MCP/API policy 和人工确认。
- [x] 已完成一次多 Agent 稳定性审查：补齐 `run_fact_layer_registration_task` 的 catalog / allowlist / confirmation 注册，修复 OpenAI `role=assistant` 工具调用历史清洗，避免旧线程再次触发 tool protocol 错误。
- [x] 已补齐 MCP/API policy 的实际工具面：ERP list/test、WeCom list/test/query/sync 都能在 `/governance` 中显示；只读查询不落盘写 policy，sync 仍需人工确认。
- [x] 已修复前端本地归档续聊和本地线程 API 容错：从归档线程继续提问时不再用旧归档内容遮住新结果，坏 JSON 归档只跳过单文件，不让 `/api/local-threads` 整体 500。
- [x] 已新增统一验证入口：`./scripts/verify_frontend.sh` 动态发现前端测试，`./scripts/verify_all.sh` 串联后端和前端验证，避免 README 里的手写测试清单继续漂移。
- [x] 已落地 ERP 智能路由：新增 `route_erp_live_query`，把“库存、采购价、成本价、毛利、库存金额、日销、周转、企业微信智能表”等组合提示词确定性路由到吉客云、金蝶、WeCom MCP 或 DuckDB，不再完全依赖模型临场猜工具。
- [x] 已落地吉客云销售汇总只读工具：新增 `query_jackyun_channel_sales_summary`，专门封装吉客云 Skill 的销售汇总工作流，只开放查询日期 + 渠道/店铺 + SKU + 销量/金额，不开放写入。
- [x] 已落地库存成本语义工具：新增 `query_inventory_cost_reference`，内部按只读白名单执行“吉客云库存 -> 吉客云批次/采购 -> 金蝶采购订单价参考”的补证链路；当 `costPrice` 为空或仅部分库存行有值时自动尝试 `batch_inventory`、`purchase_orders` 和金蝶 `supplier_procurement_terms`。
- [x] 已明确成本语义边界：金蝶 `FTaxPrice` 只作为采购订单含税单价参考，不等同于最终库存核算成本；若所有只读来源均未命中价格字段，报告只能输出数量口径周转/覆盖天数，并把成本价列为数据缺口。
- [x] 已对齐 Agent 权限：`inventory_agent` 获得 `verify_erp_supplier_terms_mapping`、`route_erp_live_query`、`query_inventory_cost_reference`；`finance_agent` 和 `financial_planning_agent` 可只读调用库存成本参考工具；`decision_agent`、`company_strategy_agent`、`data_agent`、顶层 supervisor 和 workflow/factory 也纳入一致 allowlist。
- [x] 已同步 MCP/API policy：`route_erp_live_query` 和 `query_inventory_cost_reference` 在治理页显示为 low-risk read-only；`query_erp_live_snapshot` / `verify_erp_supplier_terms_mapping` 的 allowed callers 与实际 Agent 工具权限对齐，补上 `inventory_agent`。
- [x] 已把桌面 Skill 的项目可见性说清并落地：历史 vendor 脱敏参考副本已按 2026-05-25 请求从项目内移除；当前吉客云/金蝶已重新纳入 `skills/` 项目 Skill Library，Agent 仍只暴露 wrapper 工具边界，避免 Save/Submit/Push、创建、审核、发货、退款等写入能力进入分析 Agent。
- [x] 已修复吉客云实时 ERP “Skill 目录/凭据缺失”问题：connector runtime 不再指向已删除的 `/Users/seven/Desktop/jackyun-skill-project`，而是绑定到项目 `skills/jackyun_erp_readonly_connector_skill`；`.env` 已补齐本地吉客云 OpenAPI 凭据，后端重启后 health 为 `ready`。
- [x] 已补吉客云项目 Skill 的 env-only `config.example.py`：实时 API 只从 `.env` / 进程环境读取 `JACKYUN_APP_KEY`、`JACKYUN_APP_SECRET`、`JACKYUN_API_URL`，避免把 `config.py` 或密钥带进 `skills/`。
- [x] 已验证吉客云实时只读 smoke：`master_data/warehouses` 和 `inventory_stock` 均返回 `status=success`，库存查询方法为 `erp.stockquantity.get`。
- [x] 已补回归测试：固定提示词“查 UNOVE 全仓库存并结合采购价/成本价/企业微信日销分析”必须路由到 `query_inventory_cost_reference` + `query_wecom_smartsheet_records`；吉客云成本为空或覆盖不全时必须补查金蝶采购价参考。
- [x] 已落地 Runtime Capability 统一调用层：新增 `list_runtime_capabilities`、`invoke_runtime_capability`、`register_runtime_mcp_tool`，让 Agent 像 OpenClaw 一样先发现后调用本地工具、active Skill 和已登记 MCP/API policy。
- [x] 已明确动态调用边界：本地只读工具和只读 MCP 可直接执行；active Skill 以 prompt bundle 形式返回给当前 Agent 使用；写入、高风险、破坏性或未授权能力只生成 Agent Inbox 人工确认请求，不直接执行外部写入。
- [x] 已支持后续上传/创建 MCP/API：`register_runtime_mcp_tool` 可把用户上传的 MCP JSON-RPC 工具写入本地 policy，默认 `external_write_enabled=false`；只读工具登记后会出现在 `mcp:<tool_name>` capability 中。
- [x] 已让 active Skill 可携带 Runtime Capability 工具：Skill allowlist 允许 `list_runtime_capabilities` 和 `invoke_runtime_capability`，但不会绕过 Tool Registry/MCP policy 权限。
- [x] 已新增项目专用 Skill Library：`skills/<folder>/SKILL.md` 会在 `/governance` 自动识别；导入/更新会复制完整文件夹到 `data/skill_registry/imports/<skill_id>/`，并把 folder metadata 透传给 active Skill 注入和 `invoke_runtime_capability("skill:<skill_id>")`。
- [x] 已支持把 active Skill 迁移到 `skills/` 并同步 Registry 的 `source_type=skill_directory`、`source_skill_path`、`managed_skill_dir`；当前 UNOVE、吉客云、金蝶三个项目 Skill 都已注册并启用。
- [x] 已支持 `source missing` 治理：当注册 Skill 的原始 `skills/<folder>` 被手动删除时，前端显示缺源状态，并提供删除注册、重新绑定、从受管副本恢复到 `skills/`。
- [x] 已给文件夹 Skill 增加 `skill.registry.json` 默认元数据；吉客云/金蝶从 `skills/` 重新导入后保留只读 connector 工具白名单和输出 schema。

### P6：Runtime Capability 统一调用层（已落地）

核心目标：后续你创建 Skill、上传 MCP 或补本地工具时，Agent 不需要提前写死所有函数名；它可以先发现 capability，再按统一入口调用。

- [x] Capability 发现：`list_runtime_capabilities` 输出 `a2a_runtime_capability_registry_v1`，合并本地 Tool Registry、Skill Registry 和 MCP/API policy。
- [x] Capability ID 规范：本地工具使用 `tool:<tool_name>`，Agent Skill 使用 `skill:<skill_id>`，MCP/API 使用 `mcp:<tool_name>`。
- [x] 本地只读工具调用：`invoke_runtime_capability("tool:list_agent_skills", args_json=...)` 会直接执行并返回结构化结果，同时写入企业审计。
- [x] active Skill 调用：`invoke_runtime_capability("skill:<skill_id>", args_json={"user_task": "..."})` 返回 Skill prompt、工具白名单、输出 schema 和本次 user_task；draft/paused/disabled/archived 不直接调用。
- [x] Folder Skill 调用：从 `skills/` 导入并启用的 Skill 会在 prompt bundle 中带上 `source_skill_path`、`managed_skill_dir`、`source_type=skill_directory`，多 Agent 可据此知道该 Skill 的项目文件夹和受管副本位置。
- [x] MCP policy 本地映射调用：当 `mcp:<tool_name>` 对应已有本地 handler 且 policy 允许只读时，通过 `mcp_local_tool` 模式执行，并保留 MCP permission 结果。
- [x] MCP JSON-RPC 调用：当 policy 配置 `execution_mode=mcp_jsonrpc_tool` 且提供 `mcp_url` 或 `mcp_url_env` 时，通过 JSON-RPC `initialize` + `tools/call` 调用远端 MCP 工具。
- [x] 写入/高风险拦截：本地写入工具、外部写入 MCP、未知/未授权 MCP 都不会直接执行；统一返回 `confirmation_required`，并复用 Agent Inbox approve/edit/reject。
- [x] 上传 MCP 登记：`register_runtime_mcp_tool` 写入 `A2A_MCP_POLICY_PATH`，默认只读、低风险、外部写入关闭；写入类即使登记也默认需要人工确认。
- [x] Agent 权限接入：顶层 supervisor、`data_agent`、`inventory_agent`、`decision_agent`、`company_strategy_agent`、`auto_workflow_agent`、`agent_factory_agent` 可发现/调用只读 Runtime Capability；`agent_factory_agent` 和 `auto_workflow_agent` 可登记本地 MCP policy。
- [x] Supervisor 提示词接入：当用户要求像 OpenClaw 一样调用后期创建/上传的 Skill/MCP/API 时，Agent 会先 `list_runtime_capabilities`，再 `invoke_runtime_capability`。
- [x] 治理元数据接入：`agent_tool_registry.py` 中 Runtime Capability 工具被标记为 governance；`register_runtime_mcp_tool` 是本地 policy 写入工具，必须确认。
- [x] 回归测试：`tests/test_runtime_capability_tools.py` 覆盖发现、本地只读调用、active Skill prompt bundle、MCP 本地 handler、写入 MCP 确认、上传 MCP 登记；`agent_tool_registry`、`skill_registry`、`supervisor_model_config` 已同步覆盖。

后续增强项，不影响当前可用性：

- [ ] 增加前端上传 MCP policy 向导：把 `tool_name`、`mcp_url_env`、`mcp_tool_name`、读写风险和 allowed callers 做成表单。
- [ ] 增加 MCP schema 自动发现：从远端 MCP `tools/list` 自动生成 capability 描述、参数 schema 和示例。
- [ ] 增加 capability 使用统计页：按 tool/skill/mcp 展示调用次数、失败次数、确认次数和最近审计事件。
- [ ] 增加 Skill/MCP marketplace 导入模板：把常用外部工具登记模板沉淀到 `skills/`、`vendor/` 或 wiki playbook。

### P17：supermemory / agency-agents / harness-anything 综合吸收路线（2026-06-01 新增）

结论：三个仓库都可以结合，但都不应替代当前主系统。当前项目仍以本地优先、DuckDB 事实层、Wiki/LightRAG、只读 ERP、Tool Registry、MCP policy、人工确认和证据链为主。外部仓库只作为模板、可选能力或工具规范进入本项目。

调研快照：

| 仓库 | 版本 | 定位 |
| --- | --- | --- |
| [supermemoryai/supermemory](https://github.com/supermemoryai/supermemory) | `253a82b`，2026-05-31 | 可选外部记忆层：跨会话用户/团队记忆、profile、recall/context MCP |
| [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | `783f6a7`，2026-04-11 | Agent/Skill 模板库：电商运营、供应链、FP&A、广告、合规、handoff/QA |
| [yb2460/harness-anything](https://github.com/yb2460/harness-anything) | `60d5f61`，2026-05-31 | CLI/桌面软件 harness 参考：Skill/MCP marketplace、WPS/Office 报告导出、PPT 质量审查 |

#### P17.1 完整可结合清单

| 状态 | 优先级 | 可结合能力 | 来源 | 项目落点 | 边界 |
| --- | --- | --- | --- | --- | --- |
| [x] | P0 | 中国电商运营 Agent 模板 | `agency-agents` China E-Commerce Operator | `data/agent_templates` / `skills` / `listing_agent` | 必须本地化为 evidence-first 输出，引用 DuckDB/wiki/ERP 快照 |
| [x] | P0 | 供应链、库存、采购策略模板 | `agency-agents` Supply Chain Strategist | `inventory_agent` / `company_strategy_agent` | 结合库存周转、覆盖天数、补货、供应商风险 TODO |
| [x] | P0 | FP&A / 财务分析模板 | `agency-agents` finance FP&A | `finance_agent` / 老板报告 | 做毛利、预算、费用偏差、情景分析模板 |
| [x] | P0 | Paid Media 广告诊断模板 | `agency-agents` paid-media agents | `ads_agent` | 适配国内广告平台导出报表，不承诺 API 直连 |
| [x] | P0 | Agent 交接模板和 QA gate | `agency-agents` handoff templates | task event / Agent trace / task detail | 标准化 handoff、PASS/FAIL、重试和升级记录 |
| [ ] | P0 | Dev-QA 循环编排 | `agency-agents` Agents Orchestrator | `auto_workflow_agent` / durable queue | 吸收流程，不照搬人格 prompt |
| [x] | P0 | 用户/团队长期记忆 | `supermemory` Memory API / profile | supervisor pre-context | 只记录偏好、项目状态、复盘经验，不存敏感业务明细 |
| [x] | P0 | `recall` / `context` 只读 MCP | `supermemory` MCP | Runtime Capability / MCP policy | 先只读；召回内容只做上下文，不作为经营证据 |
| [x] | P0 | User Profile 静态/动态画像 | `supermemory` Profile API | `top_company_brain_supervisor` system context | 禁止上传 ERP、财务、客户、采购价、库存明细 |
| [x] | P0 | Memory vs RAG 分层原则 | `supermemory` docs | `docs/architecture.md` / README | RAG 管资料，Memory 管关于用户/项目的演进状态 |
| [x] | P1 | Skill/MCP marketplace 模板格式 | `harness-anything` `registry_entry.json` | `/governance` / Runtime Capability | 用于外部 CLI/MCP 工具导入模板 |
| [x] | P1 | SkillHub 技能市场接入 | [skillhub.cn](https://skillhub.cn/) CLI + 目录 API | `/governance?tab=skills` 技能市场 / `skills/` / Skill 配置草稿 | 浏览支持类目、来源、评分/下载/更新/安装排序；安装后默认 draft，不自动启用 |
| [x] | P1 | CLI 工具 JSON 输出规范 | `harness-anything` WPS Skill | Runtime Capability 外部工具适配 | 规范 `--json`、结构化错误、dry-run、项目文件 |
| [ ] | P1 | WPS/Office 报告导出 | `harness-anything` WPS harness | task artifact export / 老板报告 | 仅 Windows worker 可用；写文件/导出必须审批或后台任务执行 |
| [x] | P1 | PPT 设计预设和质量审查 | `harness-anything` quality checks | 老板报告 / 月报 PPT | 先吸收规则，不急于接 WPS COM |
| [ ] | P1 | 会话状态、undo/redo 模型 | `harness-anything` session | 动态 Agent / 文档生成草稿 | 用于报告草稿、PPT 草稿回滚 |
| [ ] | P1 | 文档导出 pipeline | `harness-anything` export | task artifact export | 可参考；macOS 本机不能直接跑 Windows COM |
| [ ] | P1 | Product / trend / feedback 模板 | `agency-agents` product agents | `listing_agent` / 产品线复盘 | 商品卖点、差评、竞品和新品机会分析 |
| [x] | P1 | Data consolidation Agent | `agency-agents` specialized | Source Registry / 清洗工作流 | 改造成多源数据归并检查模板 |
| [x] | P1 | Compliance auditor | `agency-agents` specialized | `risk_agent` / governance | 广告文案、平台规则、敏感字段和外部写入前审查 |
| [ ] | P1 | Automation governance architect | `agency-agents` specialized | MCP/API policy | 工具权限、审批、审计和风险分级 |
| [ ] | P1 | MCP builder 模板 | `agency-agents` specialized MCP builder | Agent Factory / MCP 上传向导 | 创建 MCP policy 草稿，不自动放权 |
| [x] | P2 | Supermemory scoped API key 机制 | `supermemory` auth docs | MCP policy / env 配置 | 参考 container 级权限隔离，优先 scoped key |
| [ ] | P2 | MemoryBench 思路 | `supermemory` MemoryBench | Wiki/LightRAG 召回质量评测 | 只做本地知识召回评测 |
| [ ] | P2 | Memory graph UI 思路 | `supermemory` memory graph | Evidence Graph | 只参考交互，不替代证据图谱 |
| [ ] | P2 | GitHub/Drive/Notion connector 设计 | `supermemory` connectors | Source Registry | 参考资源选择、增量同步、webhook、连接健康 |
| [ ] | P2 | Zotero 本地 SQLite + Local API 模式 | `harness-anything` Zotero harness | 未来桌面 connector 设计 | 参考“只读 SQLite + 官方写接口”边界 |
| [ ] | P2 | Photoshop / Illustrator harness | `harness-anything` PS/AI harness | 商品图、海报、素材生成 | 低优先级，高风险，必须人工确认 |
| [ ] | P3 | 学术研究 pipeline | `harness-anything` Zotero / `agency-agents` academic | 暂无主线落点 | 暂不做，除非后续做研发、专利、成分或论文资料 |
| [ ] | P3 | 全量 Supermemory RAG 替代 LightRAG | `supermemory` | 不接入 | 不建议 |
| [ ] | P3 | 全量 agency-agents 导入 | `agency-agents` | 不接入 | 不建议 |
| [ ] | P3 | WPS/PS/AI 写入工具直接挂给 Agent | `harness-anything` | 不接入 | 不建议 |

#### P17.2 第一批落地任务

- [x] 新建 `data/agent_templates/`，定义模板 JSON schema：`template_id`、`source_repo`、`source_path`、`role`、`scenarios`、`prompt`、`tool_allowlist`、`output_schema`、`risk_level`、`evidence_required`、`owner`、`status`。
- [x] 精选并改写 6 个 `agency-agents` 模板：`china_ecommerce_operator`、`supply_chain_strategist`、`fpa_analyst`、`paid_media_auditor`、`compliance_auditor`、`data_consolidation_agent`。
- [x] 每个模板必须加入本项目硬规则：优先 DuckDB/mart，本地 wiki/LightRAG 只做证据定位，ERP 只读兜底必须标注查询时间和过滤条件，缺数据必须显式列出。
- [x] 把 handoff / QA gate 模板接入任务事件模型，新增标准事件：`handoff.created`、`qa.pass`、`qa.fail`、`qa.escalated`。
- [x] 在任务详情页展示 handoff、QA verdict、证据路径、失败重试次数和下一步动作。
- [x] 让 `dynamic_agent_hub` 可从 `data/agent_templates/<id>.json` 生成动态 Agent spec，但工具权限仍由 Tool Registry 过滤。
- [x] 增加模板导入/启用测试：未审批模板不能变成 active Skill；模板的 `tool_allowlist` 不能包含写入/高风险工具。

#### P17.3 Supermemory 只读记忆试点

- [x] 新增 Supermemory policy 草案：默认只启用 `profile` / `recall` / `context` 只读能力。
- [x] 环境变量只保存 `SUPERMEMORY_API_KEY`、`SUPERMEMORY_CONTAINER_TAG` 或 scoped key；禁止把 key 写入仓库、wiki 或 task artifact。
- [x] `recall` / `context` 结果只注入为用户偏好和项目上下文，不能进入 `evidence` 字段，不能替代 DuckDB、ERP、wiki 或 LightRAG 引用。
- [x] `save memory` 必须走人工确认；确认预览中必须显示将要写入的内容、container tag、敏感字段扫描结果和来源。
- [x] 增加敏感字段拦截：ERP 行级数据、客户信息、采购价、供应商报价、财务明细、库存明细、私密智能表 URL 不允许写入 hosted Supermemory。
- [x] 增加审计事件：`external_memory_recalled`、`external_memory_save_requested`、`external_memory_save_approved`、`external_memory_blocked_sensitive`。
- [x] 如果没有配置 Supermemory，系统保持本地 Wiki/LightRAG 行为，不降级报错。

#### P17.4 harness-anything 风格工具市场与报告导出

- [x] 设计 `data/mcp_marketplace/templates/*.json` 或 `skills/<folder>/skill.registry.json` 的 marketplace 模板格式，参考 `harness-anything` 的 `registry_entry.json`。
- [x] 模板字段至少包含：`name`、`display_name`、`version`、`description`、`category`、`requires`、`homepage`、`source_url`、`install_cmd`、`entry_point`、`execution_mode`、`read_only`、`requires_human_confirmation`、`risk_level`、`allowed_callers`、`data_sources`。
- [x] 为 CLI harness 增加安全约定：必须支持 `--json`，错误必须结构化，写文件路径必须在项目 allowlist 内，默认 dry-run 或 preview-first。
- [x] 先吸收 WPS/PPT 质量审查规则到老板报告和月报 PPT 生成规范，不直接依赖 Windows COM。
- [x] 如后续接 WPS/Office 导出，必须放在 Windows worker 或专门 approval executor 内；普通分析 Agent 不直接拿到 WPS、Photoshop、Illustrator 写入工具。
- [x] 增加 doctor 检查：当前平台不是 Windows 时，WPS/Photoshop/Illustrator harness 显示 unavailable，而不是失败。
- [x] 接入 SkillHub 技能市场：新增 `/api/skillhub`，只允许检查 CLI、目录浏览、搜索、安装四类动作；浏览/搜索读取 SkillHub 目录索引/API，安装调用 `skillhub install <slug> --json --dir <workspace>/skills`。
- [x] SkillHub 安装完成后复用现有 `createDraftSkillFromSource`，把 `skills/<slug>/SKILL.md` 导入为 `skillhub-<slug>` 配置草稿，继续走启用、暂停、禁用、版本和受管副本治理。

#### P17.5 验收命令和准入标准

验收命令：

```bash
.venv/bin/python -m unittest tests.test_agent_tool_registry tests.test_runtime_capability_tools tests.test_skill_registry_tools
.venv/bin/python -m unittest tests.test_p17_reference_absorption tests.test_dynamic_agent_hub tests.test_task_queue tests.test_mcp_governance_tools tests.test_external_memory_tools tests.test_doctor
./scripts/verify_frontend.sh --unit-only
.venv/bin/python scripts/doctor.py --json
git diff -- README.md TODO.md
git diff --check README.md TODO.md
```

准入标准：

- [x] 所有新增模板默认 `status=draft`，只有人工确认后才能 active。
- [x] 所有外部记忆能力默认只读；写入外部记忆必须人工确认。
- [x] 任意 hosted 外部服务都不能接收真实 ERP、客户、采购价、财务、库存明细或私密智能表 URL。
- [x] 任意 CLI/桌面 harness 都不能绕过路径 allowlist、Tool Registry、MCP policy 和 approval。
- [x] 新模板或外部工具进入 `/governance` 后必须显示来源、风险等级、可见 Agent、读写属性、确认策略和最近审计事件。
- [x] SkillHub 技能市场不能执行任意命令；前端只调用后端白名单 action，后端浏览只请求 SkillHub 目录索引/API，安装只通过 `execFile` 调用 `skillhub install`，安装目标限制在项目 `skills/`。

#### P17 明确不做

- [x] 不把 Supermemory hosted API 当成经营事实来源。
- [x] 不用 Supermemory 替代本地 LightRAG。
- [x] 不把 `agency-agents` 全量导入为 active Agent。
- [x] 不把 `harness-anything` 的 WPS/PS/AI 写入能力直接挂给普通分析 Agent。
- [x] 不在 macOS 本地默认启用 Windows COM harness。
- [x] 不因为外部模板看起来完整就放松本项目的 evidence-first、read-only-first 和 approval-first 规则。

### S0：先补交付稳定性

- [x] 把 LightRAG destructive preview 从“填入确认指令”升级为完整 LangGraph interrupt approve/reject 流程，作为采购、广告预算、外部写入的统一确认底座。
- [x] 固化 `EMBEDDING_BINDING_HOST`、`EMBEDDING_BINDING_API_KEY`、`EMBEDDING_MODEL` 的推荐组合，并把 embedding 延迟、超时、余额/额度异常纳入 `/data-health`。
- [x] 评估并替换 LangGraph in-memory checkpoint 持久化策略，降低 `.langgraph_api/.langgraph_ops.pckl.tmp` 这类本地临时文件异常。
- [x] 增加旧线程 checkpoint pickle 结构化迁移器，把 runtime 清洗过的坏历史真正写回或归档到可迁移格式。

### P0：全链路数据能力剩余项

- [x] 增加异常库存平衡专用 mart：负库存、出入库不平、近 30 天销量为 0 但库存高、断货风险 SKU。
- [x] 增加按日期/月、仓库、SKU 哈希的二级切块/索引策略，支撑更大的 ERP 出入库、销售日报和广告明细。
- [x] 在前端展示全链路进度：已发现文件、已画像、已清洗、已入库、已注册 DuckDB、已同步 LightRAG、已生成报告。
- [x] 在前端展示生成文件链接：wiki 页面、cleaned CSV/derived export、DuckDB registry、质量报告、决策报告、LightRAG 状态。

### P1：动态 Agent 能力剩余项

- [x] 先做 `Agent Registry`：持久化保存 agent spec（role、goal、tool_allowlist、input/output schema、data scope、brand scope、status、version）。
- [x] 再做 `dynamic_agent_hub`：按 registry 中的 agent spec 动态执行本地 Agent，不重编译整张 LangGraph 主图。
- [x] 支持“前端一句话 -> 自动生成 agent spec -> 人工确认 -> 立即执行”的动态 Agent 运行链。
- [x] 增加动态 Agent 生命周期：草稿、激活、暂停、版本升级、回滚。
- [x] 增加动态 Agent 审计：记录创建者、工具调用、读写数据、输出结论、风险等级。
- [x] 把成功的临时角色、prompt 和分析模板沉淀为可复用 Skill 或 prompt template。

### P3/P6/P8：外部连接顺序

- [x] 第一阶段优先纳管现有吉客云 ERP / 金蝶 ERP API skill，形成只读 connector registry、health、capability preview 和 snapshot 注册入口。
- [x] 第二阶段先接 ERP 实时只读兜底：默认查 DuckDB mart；用户明确要求实时 ERP 或本地 mart 缺关键证据时，Agent 才调用吉客云/金蝶只读 API。
- [x] 第二阶段继续扩展 ERP 自动化数据面：补齐批次库存、销售订单、销售汇总、采购/应付、退货、组织/客户映射和只读快照注册入口。
- [x] 第二阶段补齐吉客云品牌库存查询口径：先用 master_data / goodsName / alias 扩展到 `goodsNo` / `skuBarcode`，再按 goods_no 查询 `inventory_stock`，避免直接用品牌名查库存返回 0 行。
- [x] 第二阶段补齐吉客云库存分析护栏：SKU/品名必须来自 `goodsNo` / `skuBarcode` / `goodsName`；`costPrice` 缺失只影响金额口径周转；批次效期必须读取 `batch_inventory`；未映射仓库按配置缺口展示。
- [x] 第三阶段改为国内平台导出文件接入：天猫、淘宝、抖音、拼多多、唯品会、京东销售/商品/退款/评价不做直接 API，走后台导出 Excel/CSV 后入库。
- [x] 第四阶段改为国内广告报表导出接入：投产比、费比、GMV、转化率、UV 价值、预算和竞价分析不做直接 API，走广告后台导出报表入库。
- [x] 第五阶段的本地 Connector / Skill / MCP 治理先行落地：Skill registry、MCP 权限策略、审计和写入确认已完成。
- [x] 第五阶段补齐 active Skill resolver：前端提示词进入 supervisor 模型前会自动匹配 active Skill/template 并注入上下文；draft、paused、disabled 不注入。
- [ ] 第六阶段再做 A2A Protocol schema、本地 A2A Server/Client、远程 Agent 权限和审计；仅内部本地使用时可以暂缓。

### P9-P14：参考项目调研后的优化顺序

本轮参考了 OpenClaw、MiroFish 和 Hermes Agent。结论不是照搬它们的大平台，而是吸收控制台、任务账本、工具注册、可恢复队列、日志诊断和证据图谱这几类适合本项目的做法。

- [x] **P10 已落地：任务详情页和经营任务历史库**。已新增 `/tasks` 页面，按任务展示发现资料、清洗、入库、同步、分析、报告等阶段，显示状态、耗时、错误、产物链接、可恢复/可取消状态，并支持按任务类型、时间、任务状态和关键词筛选历史。
- [x] **P11 已落地：工具注册中心 2.0**。`agent_tool_registry.py` 已从静态 allowlist 升级为结构化 `ToolEntry` 注册表，记录 `name`、`handler`、`group`、`read_only`、`risk_level`、`requires_confirmation`、`data_sources`、`max_result_size`，并让 Agent allowlist、MCP policy、治理页和测试共用同一来源。
- [x] **P13 已落地：doctor、logs 和配置 schema**。已新增 `scripts/doctor.py`、跨平台 doctor wrapper、`/api/logs`、`/logs`、配置健康摘要、治理页 policy validation 和扩展审计字段；本地诊断覆盖 LangGraph、LightRAG、DuckDB、dataset registry、MCP policy、env key、端口、旧线程协议和最近错误。
- [x] **P9 已落地：Workbench 控制台总线**。已定义轻量 typed API contract：`task.list`、`task.show`、`agent.trace`、`data.health`、`governance.policy`、`approval.submit`、`logs.tail`；`/api/workbench` 复用现有 helper，把分散 API 收敛成前端可复用的控制平面。
- [x] **P12：SQLite durable queue**。在 JSON task log 稳定后，把长任务队列迁移到 SQLite，支持 claim lock、heartbeat、crash reclaim、retry count、idempotency key 和 task events table；短委派继续保留为轻量只读子任务。
- [x] **P14：证据链图谱 / 经营对象图**。新增经营对象图视图，节点覆盖品牌、渠道、SKU、仓库、供应商、数据集、wiki 页面、报告、决策，边覆盖来源、汇总、引用、影响、风险和人工确认。

### P15：LLM Wiki 知识复利升级

参考 Karpathy LLM Wiki 的核心思想：不要只把 wiki 当成 RAG 索引材料，而要把它当成由 LLM 长期维护、持续重构、可审计、可复利的知识代码库。当前项目已经有 `raw -> wiki -> LightRAG -> DuckDB -> Agent 决策` 主链路；P15 的目标是补齐 wiki 纪律层，让事实数字走 DuckDB/ERP，长期业务理解走 LLM Wiki，复杂检索走 LightRAG，多 Agent 负责执行和治理。

- [x] 新增 `docs/wiki_schema.md` 和 `wiki/AGENTS.md`，定义 wiki 页面类型、frontmatter、引用格式、目录边界、可写 Agent 和更新流程。
- [x] 固化页面类型：`source`、`dataset`、`brand`、`sku`、`channel`、`warehouse`、`supplier`、`decision`、`claim`、`contradiction`、`playbook`。
- [x] 升级 `wiki/index.md` 为内容型目录：每页记录链接、类型、一句话摘要、更新时间、证据来源、关联对象和是否可用于经营决策。
- [x] 新增 `wiki/log.md` 作为 append-only 知识演进日志，记录 ingest、query、lint、决策归档、规则变更和关键口径调整。
- [x] 规范 `wiki/log.md` 可解析标题格式，例如 `## [2026-05-20] query | UNOVE 全渠道库存快照`，方便 Agent 和脚本读取最近知识变更。
- [x] 新增 wiki lint / knowledge doctor 工具，检查孤立页面、无来源结论、过期结论、互相矛盾的口径、缺失实体页和 index 未登记页面。
- [x] 把 wiki lint 摘要接入 `/data-health` 和 `/api/workbench` 的 `data.health`，让 PM 能看到知识库健康状态、矛盾数量、孤页数量和待补证据。
- [x] 增加“好答案归档”流程：对高价值经营分析、库存快照、补货建议和渠道策略，自动生成 `wiki/decisions/*.md` 并回写 `wiki/log.md`。
- [x] 增加实体页自动维护：归档决策时同步更新品牌、SKU、渠道、仓库、供应商等相关页面，而不是只保存孤立报告。
- [x] 增加 claim/evidence 生命周期：把经营结论拆成 claim，记录 evidence、数据源、查询时间、过滤条件、row_count、状态（current/stale/contradicted）和复核人。
- [x] 把 P14 经营对象证据图谱和 claim/evidence 绑定，让图谱节点不仅能展示“引用关系”，还能展示结论是否过期、是否被新数据推翻。
- [x] 为实时 ERP 查询结果建立归档规则：用户明确要求当前数据时，最终答案可归档为 live snapshot，但必须标注 `live_read_only_fallback`、查询时间、页码/过滤条件和不可作为长期事实的边界。
- [x] 为 DuckDB mart 查询结果建立归档规则：可进入长期事实页或数据集页，但必须附 registry、mart/view 名称、SQL 摘要和数据更新时间。
- [x] 增加“知识复盘问题”生成器：lint 后自动列出值得继续追问的问题、需要补充的源文件、需要人工确认的业务口径。
- [x] 更新 README，解释本项目和 Karpathy LLM Wiki 的关系：本项目是 `LLM Wiki + DuckDB 事实层 + LightRAG 检索 + 多 Agent + ERP 实时兜底 + 治理审计` 的电商经营大脑。

### P16：Source Registry 与增量数据源同步（2026-05-30 新增）

背景：当前 `raw/` 更像一次性原始材料入口。如果源文件后续在外部继续变化，系统无法知道“同一个源”已经更新，只能靠用户再次上传或替换文件。下一阶段应把 `raw/` 从“手工上传目录”升级为“版本化证据快照层”，并新增长期数据源注册表，让系统按需/定时同步变化。

核心结论：

- [x] 用户后续不应该每次重新上传同一个源文件。正确体验是：第一次登记源，以后源更新时点击“同步”或由 watcher/cron 发现变化，系统自动生成新 snapshot。
- [x] 当前推荐顺序明确为：**企业微信微盘 Source Adapter + 本地 `raw/snapshots` 优先，COS/OSS 只作为后续归档镜像可选项**。业务人员在微盘协作编辑“当前文件”，本地 snapshot 负责系统证据不可变和可追溯，COS/OSS 只有在数据量、长期备份或跨团队归档需要变强时再接。
- [x] 如果当前只有 `raw/xxx.xlsx`，且没有登记它来自哪个长期源，那么外部源更新后系统确实无法自动知道；必须先补 Source Registry，记录源位置、权限、同步方式和版本关系。
- [x] `raw/` 继续保持不可覆盖的原始证据边界；新版本写入 `raw/snapshots/<source_id>/<snapshot_id>/...`，旧版本保留，所有派生数据通过 registry 指回对应 snapshot。
- [x] DuckDB 继续负责数字事实和全量聚合；wiki/LightRAG/Understand-Anything 类图谱只负责语义、关系、解释、导航，不替代事实层计算。

#### P16.1 Source Registry 数据模型

目标：新增长期数据源注册表，统一管理本地文件夹、手工上传、企业微信智能表、ERP 只读快照、平台导出目录和后续 API/MCP 数据源。

待办：

- [x] 新增 `data/source_registry/sources.json` 或 SQLite 表 `source_registry`，字段至少包含：`source_id`、`display_name`、`source_type`、`uri`、`allowed_root`、`sync_mode`、`owner`、`sensitivity_level`、`credential_env_keys`、`format_hint`、`expected_schema`、`freshness_sla`、`status`、`created_at`、`updated_at`。
- [x] `source_type` 首批支持：`wecom_wedrive_file`、`wecom_wedrive_folder`、`local_file`、`local_folder`、`manual_upload`、`wecom_smartsheet`、`erp_readonly_snapshot`、`api_pull`、`mcp_readonly_tool`。
- [x] `wecom_wedrive_file` / `wecom_wedrive_folder` 用于登记企业微信微盘中的单文件或文件夹；registry 只保存 `space_id`、`file_id`、文件名、路径摘要和 credential env key，不保存 access token 或临时下载 URL。
- [x] `sync_mode` 首批支持：`manual`、`on_demand`、`polling`、`webhook_placeholder`；本地内部版先做 `manual/on_demand/polling`，webhook 只预留 schema。
- [x] 每个 source 必须记录路径边界：本地文件只能在 allowlisted root 下读取，绝对路径必须 realpath 后校验，不能回到 S0.5 之前的任意文件读取风险。
- [x] 每个 source 必须记录治理边界：只读源可直接同步；外部写入、删除、修改源系统配置一律不在 P16 范围内。
- [x] 增加 source registry doctor 检查：registry JSON/SQLite 可读、source_id 唯一、uri 不泄露 token、credential 只写 env key、不写明文。

验收标准：

- [x] 可以通过工具/API 注册一个本地导出文件夹，例如“天猫销售日报导出目录”。
- [x] 可以注册一个企业微信智能表 named source，但 registry 只保存 docid/sheet_id 或 URL 摘要，不保存 `scode`、`apikey`、access token。
- [x] 可以注册一个企业微信微盘文件或文件夹 source，并能显示最近一次微盘 `mtime` / hash / 文件大小，不在 registry、audit 或 thread archive 中保存临时下载 URL。
- [x] doctor 能发现坏 source：路径越界、credential 明文、重复 source_id、缺 owner、缺 freshness_sla。

#### P16.2 版本化 raw snapshot

目标：让 raw 不再代表“当前版本”，而是代表“原始证据快照集合”。同一源每次变化都形成新 snapshot，并可追溯到后续 cleaned、Parquet、DuckDB view、wiki 页面和 LightRAG doc。

待办：

- [x] 新增 snapshot manifest：`data/source_registry/snapshots.jsonl` 或 SQLite 表 `source_snapshots`。
- [x] snapshot 字段至少包含：`snapshot_id`、`source_id`、`observed_at`、`source_mtime`、`source_size`、`sha256`、`schema_hash`、`row_count`、`sheet_names`、`raw_snapshot_path`、`cleaned_paths`、`duckdb_dataset_slug`、`wiki_pages`、`lightrag_docs`、`task_id`、`audit_event_id`、`status`。
- [x] 新 snapshot 写入路径：`raw/snapshots/<source_id>/<YYYYMMDD-HHMMSS>-<short_hash>/...`。
- [x] 对同一 source + sha256 做幂等：内容未变化时不重复清洗、不重复入库，只记录一次 no-op sync event。
- [x] 对 Excel/CSV 增加 schema diff：字段新增/删除/类型变化、sheet 新增/删除、行数大幅变化要进入 quality gate。
- [x] 原有 `raw/` 下直接放文件的方式继续兼容，但首次处理时生成 `source_type=manual_upload` 的临时 source 和 snapshot。
- [x] 不覆盖旧 snapshot，不自动删除旧 snapshot；后续如要清理，只能做 preview-first archive/cleanup，并保留 manifest。

验收标准：

- [x] 同一个文件内容不变时重复同步，产生 `skipped_unchanged` 结果，不重跑 DuckDB/wiki/LightRAG。
- [x] 同一个源文件内容变化时，生成新的 snapshot_id，并在 dataset registry 中能看到对应 source_id/snapshot_id。
- [x] 旧报告仍能追溯到旧 snapshot，新报告能引用新 snapshot，不出现“历史结论被当前文件覆盖”的问题。

#### P16.3 数据源同步 adapter

目标：用统一接口包住不同来源，先做最实用的几个只读 adapter。

待办：

- [x] 本地文件夹 adapter：扫描 allowlisted export folder，按文件名模式、mtime、sha256 发现新增/更新文件。
- [x] 手工上传 adapter：前端上传文件后不只写 raw，还可绑定到已有 source 或创建 manual source。
- [x] 企业微信微盘 adapter：登记微盘文件/文件夹后，按 `mtime`、`size`、`sha/md5` 或下载后 `sha256` 判断是否变化；变化时把当前文件下载到 `raw/snapshots/<source_id>/<snapshot_id>/original.<ext>`，再进入现有清洗/入库链路。
- [x] 企业微信微盘权限边界：只做 read-only list/download，不做上传、覆盖、删除、移动或分享权限修改；微盘 token、临时下载 URL 和成员信息必须脱敏。
- [x] 企业微信智能表 adapter：复用 `query_wecom_smartsheet_records` 和 `sync_wecom_smartsheet_snapshot`，把每次同步结果登记为 source snapshot。
- [x] ERP 只读快照 adapter：复用 connector registry 的 `sync_readonly_snapshot` 能力，记录查询过滤条件和查询时间，避免把 live read-only 误当长期事实。
- [x] 平台导出目录 adapter：天猫/抖音/拼多多/京东/唯品会/广告后台的导出文件先走 local_folder，不直接承诺 API。
- [x] COS/OSS mirror adapter 暂缓：M1/M2 不直接依赖 COS/OSS；等微盘 source + 本地 snapshot 稳定后，再把 snapshot 异步镜像到对象存储，并用对象存储生命周期/版本控制做长期归档。
- [x] 每个 adapter 返回统一结构：`source_id`、`snapshot_id`、`changed`、`raw_snapshot_path`、`profile`、`quality_warnings`、`next_actions`。

验收标准：

- [x] local folder、manual upload、企业微信微盘、WeCom snapshot 至少四类 source 能跑通同一条 snapshot manifest 写入逻辑。
- [x] 用户在企业微信微盘编辑并保存源文件后，点击 `Sync now` 可以生成新 snapshot；如果内容未变，则返回 `skipped_unchanged`。
- [x] ERP live read-only 结果如果落地为 snapshot，必须标注 `live_read_only_fallback`、query filters、row_count、observed_at。
- [x] source adapter 失败不会污染旧 snapshot；失败状态写入 task queue 和 audit。

#### P16.4 增量处理编排

目标：把 source 变化自动接到现有清洗、DuckDB、wiki、LightRAG 和报告链路，但仍保持 Agent 权限边界。

待办：

- [x] 新增 durable task 类型：`source.sync`、`source.snapshot`、`source.profile`、`source.ingest`、`source.verify`。
- [x] 编排步骤固定为：`source_watcher -> snapshotter -> schema_profiler -> quality_gate -> fact_registrar -> wiki_ingest -> lightrag_sync -> verifier`。
- [x] 只有 `auto_workflow_agent` / `data_cleaning_agent` / `wiki_ingest_agent` 可启动 sync/ingest；`decision_agent`、`company_strategy_agent` 做只读分析时不能顺手重跑 source sync。
- [x] 增量策略：内容 hash 不变只更新 freshness；schema 变了必须进入 quality gate；大文件继续走 large_excel_pipeline；小文件可走现有 table cleaning。
- [x] 对 schema drift 输出明确人工确认问题：新增字段含义、字段删除影响、sheet 命名变化、行数异常、日期范围断层。
- [x] 每次同步结束写入 wiki/log 和 audit event，记录 source_id、snapshot_id、处理链路和产物链接。

验收标准：

- [x] 用户说“同步这个销售日报源”时，系统只处理该 source 的新 snapshot，不全量重跑所有 raw。
- [x] 用户说“基于已有数据分析”时，不触发 source.sync、raw cleaning 或 LightRAG rebuild。
- [x] task detail 页面能看到 source sync 的每一步、产物和失败恢复建议。

#### P16.5 前端与治理页

目标：让 PM 能看到“哪些数据源是活的、多久没更新、最近一次同步有没有失败”，而不是只看到一堆 raw 文件。

待办：

- [x] 新增 `/data-sources` 页面，或在 `/governance` 增加 `Data Sources` tab。
- [x] 列表字段：source name、type、status、freshness、last_snapshot_at、last_row_count、last_schema_hash、owner、sensitivity、downstream dataset/wiki/report。
- [x] 操作：`Sync now`、`Pause`、`Resume`、`Rebind source path`、`View snapshots`、`View schema diff`、`Open latest dataset`。
- [x] 新增 source 创建表单：企业微信微盘文件/文件夹、本地文件夹、手工上传、企业微信智能表、ERP 只读快照五类先支持；微盘表单只要求选择/填写文件定位信息和 credential env key，不要求用户粘贴临时下载链接。
- [x] 所有路径输入都复用 S0.5 realpath allowlist；所有 URL/token 输入都只保存脱敏摘要或 env key。
- [x] `/data-health` 增加 source freshness summary：过期源数量、失败源数量、最近成功同步、schema drift 数量。

验收标准：

- [x] PM 可以不用问 Agent，就能看到“这个日报源今天有没有更新”。
- [x] PM 在微盘编辑源文件后，可以在 source 页面看到微盘更新时间变化，并手动触发同步到本项目。
- [x] 点击 source 可以看到全部 snapshot 历史和每个 snapshot 的下游 DuckDB/wiki/LightRAG 产物。
- [x] 前端不能通过 source path 绕过工作区 allowlist 读取任意本地文件。

#### P16.6 参考仓库吸收方式

本轮评估的三个仓库不建议直接整包搬进主链路；更适合拆成局部能力吸收。

- [x] [Lum1104/Understand-Anything](https://github.com/Lum1104/Understand-Anything)：做 POC，目标是把当前 codebase 和 `wiki/` 生成可探索知识图谱，辅助新人理解代码、业务 wiki 和数据源关系。它可以补“理解/导航”，不能替代 DuckDB、LightRAG 或本项目的 evidence graph。
- [x] Understand-Anything POC 验收：能对项目代码生成 graph；能对 Karpathy-style wiki 运行 `/understand-knowledge` 或等价流程；产物路径、缓存和大文件目录写入 `.gitignore`；不上传业务数据到第三方。
- [x] [revfactory/harness](https://github.com/revfactory/harness)：吸收 agent team pattern，而不是直接依赖 Claude Code 目录结构。重点借鉴 Pipeline、Fan-out/Fan-in、Producer-Reviewer、Supervisor、Hierarchical Delegation，以及 QA/validation 方法。
- [x] Harness 吸收验收：把 P16 sync workflow 写成固定 team contract：`source_watcher`、`snapshotter`、`schema_profiler`、`quality_gate`、`fact_registrar`、`wiki_lightrag_sync`、`verifier`；每个角色都有输入、输出、失败恢复和验收字段。
- [x] [rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch)：作为课程/参考手册，不作为运行依赖。可提取 Agent loop、MCP、eval、production checklist 到项目 docs 或 wiki playbook。
- [x] AI Engineering 参考验收：只沉淀 checklist / playbook / prompt，不引入新框架、不重写当前 LangGraph 主链路。

#### P16.7 测试、doctor 和回归校验

待办：

- [x] 增加 `tests/test_source_registry.py`：source CRUD、重复 source_id、credential 明文拒绝、路径越界拒绝、source status 迁移。
- [x] 增加 `tests/test_source_snapshots.py`：sha256 幂等、mtime 变化但内容不变、内容变化生成新 snapshot、schema_hash 变化触发 quality warning。
- [x] 增加 `tests/test_source_sync_workflow.py`：local folder sync、manual upload sync、企业微信微盘 sync、WeCom snapshot sync、失败不污染旧 snapshot。
- [x] 增加企业微信微盘 adapter 测试：文件列表元数据变化、临时下载 URL 脱敏、内容 hash 幂等、下载失败重试、无权限时给出明确 remediation。
- [x] 增加前端测试：source list、snapshot history、schema diff、sync now、路径越界错误展示。
- [x] 增加 doctor 检查：source registry 文件/SQLite、snapshot manifest、stale sources、failed sources、明文 token、工作区外路径。
- [x] 增加 runbook：数据源首次登记、源文件更新、schema drift 人工确认、回滚到旧 snapshot、清理旧 snapshot 的操作步骤。

验收命令：

```bash
.venv/bin/python -m unittest tests.test_source_registry tests.test_source_snapshots tests.test_source_sync_workflow
cd agent-chat-ui && ./scripts/with-env-node.sh ./node_modules/.bin/tsc --noEmit --pretty false
.venv/bin/python scripts/doctor.py --json
./scripts/verify_all.sh
git diff --check
```

#### P16 推荐落地顺序

- [x] M1：先做 Source Registry + 企业微信微盘 Source Adapter + 本地 `raw/snapshots`。这是当前首选方案：微盘负责业务人员在线编辑当前文件，本地 snapshot 负责不可变证据和后续 DuckDB/wiki/LightRAG 引用。
- [x] M2：补 local folder/manual upload snapshot，兼容平台导出目录和临时文件上传，解决“同一个源更新不用重新上传”的核心痛点。
- [x] M3：把 WeCom smart sheet 和 ERP readonly snapshot 纳入同一套 source/snapshot manifest。
- [x] M4：把增量 sync 接入 durable queue、task detail、audit、wiki/log 和 `/data-health`。
- [x] M5：新增 `/data-sources` 或 governance tab，让 PM 能可视化管理 source 和 snapshots。
- [x] M6：评估是否把 snapshot 镜像到 COS/OSS；只有在长期归档、跨团队共享、容量或备份要求明显增强时再接。
- [x] M7：做 Understand-Anything POC；只在确认有价值后再决定是否保留为开发/知识导航工具。
- [x] M8：把 Harness 的 team pattern 写入 P16 workflow contract，并补 verifier/QA agent 验收。

明确不做：

- [x] P16 不做外部系统写回，不修改 ERP/平台/企业微信源数据。
- [x] P16 不把 LightRAG 或 Understand-Anything 当作库存、销售、财务计算引擎。
- [x] P16 不自动删除旧 raw snapshot。
- [x] P16 不允许只读分析 Agent 在回答过程中偷偷启动 source sync。
- [x] P16 不承诺国内平台 API 直连；平台和广告后台仍优先走导出文件夹 + snapshot。

## 历史进度记录（2026-05-15）

- [x] 已按“保留 raw、清空派生数据”的方式重建：`data_reset_archive/20260515-100908` 保存旧数据快照，`raw` 原始资料未清空。
- [x] 已重新跑通 P0 主链路：raw discovery、large Excel pipeline、Excel cleaning、DuckDB fact layer、wiki ingest、LightRAG sync、质量门、财务分析、公司策略、最终报告。
- [x] 已生成本轮任务日志：`data/tasks/20260515-102940-重新从-raw-目录整理-UNOVE-数据-清洗入库-注册-DuckDB-同步-Ligh.json`。
- [x] 已生成 P0/P1 验证版报告：`data/reports/20260515-103453-公司经营大脑全链路辅助决策报告-P0P1验证版.md`。
- [x] 已生成可追溯决策页：`wiki/decisions/20260515-103453-公司经营大脑全链路辅助决策报告-P0P1验证版.md`。
- [x] DuckDB 已重建完成，当前含 `datasets` 原始视图和 `marts` 事实/聚合视图，包含 `agg_sku_daily_sales`、`agg_warehouse_inventory`、`agg_inbound_outbound_daily`、`agg_channel_sales`。
- [x] LightRAG 已完成重建与 retry 摘要处理，当前服务健康；清理误触发记录后状态为 `processed 123 / pending 0 / processing 0 / failed 0 / all 123`，pipeline `busy=false`。
- [x] 前端 `3000`、LangGraph 后端 `2024`、LightRAG `9621` 均已确认可访问。
- [x] 已通过工程验证：`./scripts/verify_python.sh` 完成 compileall、30 个 unittest、Ruff、Pyright，结果通过；仅有既有 LangGraph deprecated warning。
- [x] 已处理后续 3 个 timeout failed：生成 `wiki/lightrag-retry/*.md` compact 摘要页，提交成功后清理 LightRAG 原始 failed 记录。
- [x] 已补齐 LightRAG 预防和自动恢复代码：同步前自动摘要高风险长文档，timeout failed 可用 `auto_recover_lightrag_timeouts` 自动摘要、重传并删除原始 failed 记录。
- [x] 已补齐前端分析请求保护：`基于所有已有数据...分析...` 这类问题不会重新处理 `raw`，也不会启动后台 LightRAG 同步；后台工作流工具自身也会拒绝这类误调用。
- [x] 已清理误触发同步产生的 LightRAG processing/pending/failed 记录和本地 `wiki/lightrag-auto-summary` 临时页，当前 LightRAG 为 `processed 123 / pending 0 / processing 0 / failed 0 / all 123`，pipeline `busy=false`。
- [x] 已修复前端续聊时提交 synthetic tool message 导致的 `Messages with role 'tool'...`，并补充 `local-archive-thread.test.ts` 回归测试。
- [x] 已在后端 supervisor / agent 模型调用前加入消息协议清洗，旧线程也能继续使用。
- [x] 已完成前端 stream 错误兜底：停后端制造 `network error` 时，页面显示“连接后端失败”中文提示，不再直接红屏。
- [x] 已执行旧线程归档离线修复：修复 `data/thread_archive/019e2c51-88eb-7db2-9a8c-9ccb601f1ed4.json`，移除 4 条孤立 tool，补 3 条缺失 tool response，备份到 `data/thread_archive_backups/20260518-225217`。
- [x] 已新增 `/api/agent-traces` 和聊天区 trace 面板，用于查看 Agent、工具、任务步骤、审计事件。
- [x] 已修复 trace 面板作用域：历史对话只显示当前 thread/task 相关 trace；无范围请求默认返回空，只有 `scope=global` 才返回全局最近 audit/task；没有 trace 的历史不显示面板。
- [x] 已新增 `/api/data-health` 和 `/data-health` 页面，用于查看 LightRAG / DuckDB / dataset registry / 最近任务健康状态。
- [ ] 后续如果再次出现 pending 长时间不动，优先检查供应商模型日志、embedding 供应商稳定性和 LightRAG worker 状态。

## 当前进度记录（2026-05-19）

- [x] 已完成吉客云/金蝶实时只读连通性验证：吉客云 `erp.warehouse.get` 查询成功；金蝶 `ValidateUser + ExecuteBillQuery` 查询 `BD_Supplier` 成功。
- [x] 新增 `connector_live_tools`：`list_erp_live_query_capabilities`、`test_erp_live_connection`、`query_erp_live_snapshot`，默认用于前端对话的实时 ERP 只读兜底。
- [x] 已把实时只读 ERP 工具加入 `data_agent`、`decision_agent`、`company_strategy_agent`、`auto_workflow_agent`、`agent_factory_agent` 的受控 allowlist。
- [x] 已固化路由策略：默认读本地 DuckDB mart；用户明确说“实时 ERP/吉客云/金蝶当前数据”或本地 mart 缺关键证据时，才调用实时只读 API。
- [x] 已补回归测试：限制实时工具只调用吉客云只读方法和金蝶 `ExecuteBillQuery`，并确认决策 Agent 仍不能调用 snapshot 写入工具。
- [x] 已把 UNOVE 国内渠道经营规则沉淀为 wiki 页面和 active Skill/template：`wiki/strategy/unove-domestic-channel-strategy.md` -> `data/skill_registry/skills/unove_domestic_channel_strategy.json` -> `data/agent_templates/unove_domestic_channel_strategy.json`。
- [x] 已新增 `active_skill_resolver`：前端输入业务提示词后，supervisor 会在模型调用前自动匹配 active Skill，并把命中的 Skill prompt 注入为 system 上下文；不会扩大工具权限。
- [x] 已新增 Skill Registry 工具：支持 wiki 转草稿 skill、人工审批启用、列表/详情、暂停/禁用、版本更新、回滚和 active template 同步。
- [x] 已新增项目 Skill Library 管理：`skills/` 下的 Skill 文件夹可被治理页扫描、导入、更新和删除注册项；启用后按现有 active Skill/template 流程供多 Agent 调用。
- [x] 已新增 MCP 治理工具：支持 MCP/API 工具权限查询、只读/写入/需确认策略、参数摘要脱敏、返回数据来源和风险等级审计。
- [x] 写入类 MCP/API 动作已复用 Agent Inbox 人工确认 UI：创建采购单、修改广告预算、外发消息等默认进入 approve/edit/reject，不直接执行外部写入。
- [x] 已根据国内平台接口限制重定 P3 边界：平台、广告、客服售后评价不做直接 API；已在 connector registry 固化 not-direct-api policy 和 manual export ingestion route。
- [x] 已扩展 ERP 实时只读数据面：吉客云批次库存、销售订单、货品销售分析、采购订单、入库、出库、供应商；金蝶采购订单分录、供应商采购条款观察、其他应付、销售退货、组织、客户。
- [x] 已落地供应商数据口径：吉客云供应商可读 `arrivePeriod` 交付周期；金蝶采购订单分录可读采购单价/金额/交货日期；历史延误由采购计划/入库完成时间二次推导。
- [x] 已验证金蝶采购订单分录可返回 `FTaxPrice` 采购单价字段；金蝶 `supplier_procurement_terms` / `purchase_orders` 支持按物料编码或物料名称过滤，用于补充吉客云库存 `costPrice` 缺口的采购参考价。
- [x] 已强制吉客云/金蝶接口权限只读：connector registry 清洗危险 override，统一 `permission_scope=read_only`、`external_write_enabled=false`；吉客云只允许白名单查询方法，金蝶只允许 `ExecuteBillQuery`，写入端点不暴露。
- [x] 已把吉客云实时 connector 从历史桌面路径迁到项目 Skill Library：`A2A_JACKYUN_SKILL_DIR` 指向 `skills/jackyun_erp_readonly_connector_skill`，connector health 检查会同时验证 Skill 目录、必要文件和 `.env` 凭据状态。
- [x] 已把吉客云仓库业务口径改为配置化规则：`config/jackyun_warehouse_scope_rules.json` 同时驱动实时 ERP 工具和模型护栏，后续新增/减少仓库只改配置。
- [x] 已新增供应商条款字段只读验证：`verify_erp_supplier_terms_mapping` 可检查真实返回字段中是否有交期、采购价和历史延误候选字段；不返回供应商名称或价格明细。

## 当前进度记录（2026-05-20 ~ 2026-05-22）

- [x] 2026-05-22：已新增 `query_jackyun_channel_sales_summary`，只读封装吉客云 Skill 销售汇总工作流；Agent 可按日期 + 渠道/店铺 + SKU 查询销量/金额，不再绕到库存接口里解释近销字段。
- [x] 2026-05-22：已把该工具接入 `data_agent`、`inventory_agent`、`decision_agent`、`company_strategy_agent`、`auto_workflow_agent`、`agent_factory_agent` 和顶层 supervisor 的只读工具面，并登记 MCP/API policy。
- [x] 2026-05-22：已更新实时 ERP 护栏：吉客云库存接口里的 `yesterdayQuantity/threedayQuantity/weekQuantity/stockOutuantity` 只能作为近销/出库数量参考；完整日期 + 渠道 + SKU 销售汇总优先用 `query_jackyun_channel_sales_summary`。

- [x] 已定位前端同一份库存报告显示两次的根因：线程归档里同时保留了 `data_pipeline_supervisor` 子团队最终报告和 `top_company_brain_supervisor` 顶层最终报告，前端之前只过滤 system 消息，所以两份都显示。
- [x] 已修复前端历史渲染：`getRenderableChatMessages()` 会折叠相邻、无 tool call、内容重复的 supervisor 最终报告，只保留顶层最终答案；trace 仍保留执行链路。
- [x] 已补前端回归测试：`local-archive-thread.test.ts` 覆盖 system 消息过滤、重复 supervisor 报告折叠和不同报告不误折叠。
- [x] 已补吉客云库存分析模型护栏：品牌字段为空时说明 master_data goodsName/alias -> goodsNo 查询口径；`costPrice` 缺失只影响金额口径；数量周转必须依赖销量/出库；批次效期必须读 `batch_inventory`。
- [x] 已重启 LangGraph backend，使新的实时 ERP / 库存分析护栏生效。
- [x] 已验证：前端 `tsc --noEmit` 通过，local archive 测试 15 个通过，后端 `unittest tests.test_supervisor_model_config` 15 个通过，`py_compile` 通过，浏览器打开问题线程后只显示一份最终库存报告且控制台无 warning/error。
- [x] 已补真实库存周转的销售侧入口：`query_jackyun_channel_sales_summary` 可只读调用吉客云销售汇总，按日期 + 渠道/店铺 + SKU 返回销量和销售金额；`route_erp_live_query` 会在“吉客云实时 SKU 日销/渠道销量”场景推荐该工具。
- [ ] 后续真实库存周转链路增强：把 `inventory_stock` / `brand_expansion.summary` 与 `query_jackyun_channel_sales_summary` 自动组合成一份覆盖天数报告；如需金额口径，再读取成本价/采购价可用字段并做敏感字段审计。
- [ ] 后续批次效期增强：当小样、赠品或临期风险占比高时，自动追加 `batch_inventory / erp.batchstockquantity.get` 查询，输出批次效期风险，而不是只列“未量化缺口”。

## 历史进度记录（2026-05-14）

- [x] 本地三段服务已重新确认：前端 `3000`、LangGraph 后端 `2024`、LightRAG `9621` 均可启动并响应健康检查。
- [x] 已定位本轮 LightRAG 大量 failed 的直接原因：不是电脑重启本身，而是 LightRAG 重启后继续处理队列时，LLM 供应商返回 `402 Insufficient Balance`。
- [x] 已统计当前 LightRAG 文档状态：`processed 36 / failed 79 / all 115`。
- [x] 已按根因拆分失败：`llm_insufficient_balance 53`、`embedding_timeout 24`、`llm_timeout 2`。
- [x] 已补充代码诊断能力：`diagnose_lightrag_failures` 可读取 LightRAG doc status 并输出失败原因、示例文档和恢复动作。
- [x] 已补充失败重试能力：`list_failed_lightrag_docs`、`retry_failed_lightrag_docs` 可列出失败文档并把失败 wiki 页压缩成 `wiki/lightrag-retry/*.md` 后重新提交。
- [x] 已把 LightRAG 诊断/重试工具暴露给知识库、入库、经营策略、决策、自动工作流和 LightRAG 专用 Agent。
- [x] 已通过 Python 验证：compileall、unittest、Ruff、Pyright 均通过。
- [x] 恢复或更换可用 LLM 额度后，重新执行 failed 文档重试。
- [x] 确认 retry 文档处理成功后，已通过 LightRAG 删除接口清理原始 failed 历史记录，本地 wiki 源文件保留。
- [x] 检查并固化 `EMBEDDING_BINDING_HOST`、`EMBEDDING_BINDING_API_KEY`、`EMBEDDING_MODEL` 的稳定组合，降低 embedding timeout。
- [x] 后续评估 LangGraph in-memory 持久化 `.langgraph_api/.langgraph_ops.pckl.tmp` 的偶发 `PermissionError`，必要时切换更稳定的本地持久化策略。

## P0：全链路自动化闭环

- [x] 增加非专业自然语言入口：`friendly_router_agent` 把普通业务说法翻译成系统任务。
- [x] 增加友好任务模板：整理资料、清洗表格、库存风险、经营分析、同步知识库、老板报告。
- [x] 前端增加常用业务按钮，点击即可填入普通话术提示词。
- [x] 增加 `auto_workflow_agent`，让一句话任务触发“发现资料、清洗、入库、读取数据、辅助决策、保存报告”。
- [x] 增加 Excel 画像和清洗工具，输出到 `data/cleaned`。
- [x] 让数据 Agent 可以读取 `data/cleaned`。
- [x] 增加 `quality_gate_agent`：检查字段完整性、行列数量、空值比例、重复数据、公式风险。
- [x] 增加 `company_strategy_agent`：公司级经营策略、产品线、库存、广告、供应商和数据缺口综合判断。
- [x] 增加 `financial_planning_agent`：公司级现金流、收入、成本、毛利、库存占用和广告支出判断。
- [x] 增加 DeepAgents 风格 task delegation 工具层：每个子任务返回结构化 JSON。
- [x] 增加全链路状态记录：每一步保存输入、输出、工具结果、错误和重试次数。
- [x] 增加后端启动、停止、健康检查脚本。
- [x] 增加后台任务入口：`start_company_workflow_task`、`get_workflow_task_status`、`list_workflow_tasks`、`cancel_workflow_task`。
- [x] 增加完整 LightRAG 同步子任务：入库后优先同步 LightRAG Server，不可用时重建本地兜底索引。
- [x] 增加失败补救策略基础版：表头/字段风险进入 task log 和下一步动作，超大文件进入熔断策略。
- [x] 增加真正的离线大文件拆分 worker：把 50MB+ Excel 按 sheet 和行数自动切块，输出 manifest、quality_report 和 Obsidian 摘要。
- [x] 让全链路后台任务在普通 Excel 清洗前先执行 `large_excel_pipeline`，避免前端长时间卡死。
- [x] 让业务数据读取对 `data/warehouse` 分块启用可控样本上限，避免决策阶段再次一次性读完整大表。
- [x] 增加 DuckDB + Parquet 事实层：把大表 chunk 注册成数据集，生成 Parquet、DuckDB 视图和全局 mart。
- [x] 增加数据集注册表：记录 source、manifest、quality_report、sheet view、mart view 和 wiki 页面。
- [x] 让大表处理结果自动生成 `wiki/datasets/<slug>` 页面：overview、sheet、field-dictionary、quality-report、query-recipes、open-questions。
- [x] 让业务分析优先走 DuckDB fact layer 查询全量库存/销量问题，warehouse sample 只保留为回退路径。
- [x] 增加历史 manifest 重新注册入口：`scripts/register_fact_layer.ps1` 可把已拆好的大表补注册进 DuckDB/Parquet。
- [x] 增加历史 chunk 缺失检测：注册时显式标记缺块，并回写到 registry/wiki warning/open-questions。
- [x] 增加标准结构化文件注册：`data/cleaned` 和 `data/*.csv` 也可进入 DuckDB fact layer。
- [x] 增加财务/广告 mart 框架：`fact_finance_daily`、`fact_ads_daily`。
- [x] 增加受控自然语言查询入口：`plan_fact_query` / `query_fact_layer_from_question`。
- [x] 增加库存快照视图和更稳的日期口径：`current_inventory_snapshot`、`snapshot_date`、`effective_date_value`。
- [x] 让库存查询默认优先非零库存，并支持当前快照查询。
- [x] 修复 `UNOVE` 历史缺块：`ERP底表4_23` 的 `part_0001 ~ part_0003` 已重新生成并重新注册。
- [x] 增加 fact source readiness 审计：系统可直接判断本地结构化文件能否长出 ads/finance marts。
- [x] 多品牌默认规则落地：Agent 不再把任何单一品牌当成隐含上下文，未指定品牌时先识别品牌范围。
- [x] `.xmind` 纳入项目内 raw->wiki 资料链，可作为运营/渠道/展会/营销方案输入。
- [x] 本轮 UNOVE 任务链已验证：raw 新资料可进入 wiki/事实层，DuckDB 承接大表查询，LightRAG 承接知识页语义检索和证据链。
- [x] 增加按日期/月、仓库、SKU 哈希进一步分区的二级切块/索引策略。
- [x] 增加更丰富的大表聚合指标物化表：SKU 日销量、仓库库存、出入库汇总、渠道维度销量。
- [x] 增加更强的自然语言到 DuckDB SQL 受控路由层：支持比较、Top N、分组聚合、多条件过滤基础能力。
- [x] 增加异常库存平衡专用聚合视图，例如库存负数、出入库不平、近 30 天销量为 0 但库存高的 SKU、断货风险 SKU。

## P1：动态 Agent 和能力生成

- [x] 增加 `agent_factory`：根据任务自动生成临时 Agent 的角色、目标、工具范围和输出格式。
- [x] 增加 Agent 模板库基础版：Excel 清洗、Obsidian 入库、库存决策、财务规划、公司策略、风险审查。
- [x] 增加动态角色审查基础版：输出 handoff contract 和权限策略，限制授权路径和工具范围。
- [x] 增加 `Agent Registry`：持久化保存 agent spec（role、goal、tool_allowlist、input/output schema、data scope、brand scope、status、version）。
- [x] 增加 `dynamic_agent_hub`：在不重编译整张 LangGraph 主图的前提下，按 agent spec 动态执行新的本地 agent。
- [x] 支持“前端一句话 -> 自动生成 agent spec -> 人工确认 -> 立即执行”的动态 agent 运行链。
- [x] 增加动态 agent 生命周期：草稿、激活、暂停、版本升级、回滚。
- [x] 增加动态 agent 审计：记录是谁创建、调用了哪些工具、读写了哪些数据、产生了哪些结论。
- [x] 增加任务结束后的经验沉淀：把成功的临时角色和 prompt 保存为可复用技能。

## P2：知识库和知识图谱

- [x] 增加 Karpathy LLM Wiki 个人知识库方案文档。
- [x] 创建 Obsidian 标准目录：`products`、`suppliers`、`inventory`、`data-dictionary`、`cleaning-rules`、`decisions`。
- [x] 自动生成字段字典页面：把 cleaned CSV 的字段解释、来源、示例值写入 `wiki/data-dictionary`。
- [x] 自动生成清洗规则页面：把表头行、字段映射、ID 文本保留、公式风险写入 `wiki/cleaning-rules`。
- [x] 建立 LightRAG 风格轻量知识图谱数据结构：文档、实体、关系、关键词和证据路径。
- [x] 从 Obsidian Markdown 和 dataset wiki 页面中抽取实体与关系。
- [x] 增加混合检索工具 `query_lightrag`：同时返回文档片段、实体和关系。
- [x] 在全链路任务中加入 LightRAG 证据索引步骤。
- [x] 升级完整 LightRAG Server 适配：`lightrag_server_status`、`sync_obsidian_to_official_lightrag`、`query_official_lightrag`、`get_lightrag_track_status`。
- [x] 增加 LightRAG 安装、启动、停止、健康检查、同步脚本。
- [x] 让 LightRAG 只索引 wiki 高信号页，不再把 `data/warehouse` 大表预览当成语义知识源。
- [x] 增加 LightRAG failed 文档可观测性：`diagnose_lightrag_failures` 按余额不足、embedding 超时、LLM 超时、供应商 API 错误等分类。
- [x] 增加 LightRAG failed 文档补救：`retry_failed_lightrag_docs` 自动生成压缩 retry 摘要页并重新提交，避免超长页面反复失败。
- [x] 将 LightRAG 诊断与补救工具加入 `wiki_ingest` 模板和相关 Agent 工具范围。
- [x] 增加“余额不足/模型不可用时暂停 LightRAG 重试”的保护，避免 pending 文档被批量打成 failed。
- [x] 增加 LightRAG 高风险页面自动摘要：字段字典、大表画像、销售日报和超长页面同步前写入 `wiki/lightrag-auto-summary/*.md`，避免 Web 端长时间等待或 timeout。
- [x] 增加 LightRAG timeout failed 自动恢复：`auto_recover_lightrag_timeouts` 可生成 compact retry 摘要、重新提交，并删除 LightRAG Server 中原始 failed 记录。
- [x] 增加 LightRAG retry 成功后的安全清理工具：`cleanup_confirmed_lightrag_failed_history` 只有在 retry 摘要 processed 且输入确认短语后才删除原始 failed 历史，并先归档 doc status。
- [x] 增加 LightRAG WebUI/API 状态汇总工具：`summarize_lightrag_processing_status` 可输出 processed/failed/pending、根因和 retry guard。
- [x] 增加 LightRAG WebUI/API 状态汇总到前端任务进度：前端 `/api/lightrag-status` 和状态条每 10 秒显示 processed/processing/pending/failed。
- [x] 在决策报告中输出更细粒度证据链：引用 wiki 页面、DuckDB mart、manifest、quality_report、registry 和数据缺口。
- [x] 让 LightRAG 引用能定位到 dataset wiki 页面、DuckDB mart、manifest、chunk 文件和源 Excel 行号：`resolve_lightrag_reference_paths` 已落地。
- [x] 给每次决策生成可追溯页面，方便后续复盘。
- [x] 增加 durable insight 回写策略：`append_durable_insight` 只允许字段口径、质量异常、业务规则、分析模板和复盘结论写回 wiki。
- [x] 把高复用 wiki 页面转成 Agent skill 或 prompt 模板：`save_wiki_page_as_prompt_template` 生成 draft prompt template。

## P3：国内电商与 ERP 真实业务接入

- [x] 建立 ERP connector registry：纳管吉客云 ERP、金蝶 ERP 的 skill/API 目录、能力、只读边界、凭据环境变量和同步状态。
- [x] 增加 connector health / capability preview / snapshot sync 工具，支持把只读快照注册进 DuckDB fact layer。
- [x] 接入吉客云 ERP 实时只读 API 兜底：SKU 库存、仓库、渠道、货品基础资料。
- [x] 修复吉客云 connector runtime 与 Skill Registry 脱节：active Skill 负责 Agent prompt/allowlist，真实 OpenAPI 查询由 connector registry + `.env` 驱动；两者现在都指向项目 `skills/` 下的吉客云只读 Skill。
- [x] 接入金蝶 ERP 实时只读 API 兜底：供应商、采购订单、销售出库、应收快照。
- [x] 扩展吉客云 ERP 自动化数据面：批次库存、销售订单、销售汇总、日期 + 渠道/店铺 + SKU 销售汇总只读封装、采购订单、出入库明细、供应商和只读快照注册入口。
- [x] 扩展金蝶 ERP 自动化数据面：采购订单分录、其他应付、销售退货、组织/客户映射、供应商采购条款观察和只读快照注册入口。
- [x] 国内平台销售和商品 API 改为 blocked/manual export：天猫、淘宝、抖音、拼多多、唯品会、京东不做直接 API，走后台导出文件接入。
- [x] 国内广告报表 API 改为 blocked/manual export：投产比、费比、GMV、转化率、UV 价值、预算和竞价分析走广告后台导出报表入库。
- [x] 接入供应商交期、采购价、历史延误记录的可用口径：交期优先读吉客云供应商 `arrivePeriod` 或金蝶交货日期；采购价读金蝶采购订单/吉客云采购入库；历史延误由采购和入库记录推导。
- [x] 客服会话、售后工单、评价、问大家、退款退货原因和差评跟进记录改为 blocked/manual export：走客服/售后/评价导出文件或 wiki 手工页，支持商品内容和产品改进建议。

## P4：安全和人工确认

- [x] 为高风险动作加入人工确认策略文档和工具提示：删除文件、外发消息、创建采购单、修改广告预算。
- [x] 增加工具权限配置基础版：`list_permission_policy`、`check_path_permission`。
- [x] 增加敏感信息过滤基础版：审计日志自动脱敏常见 API Key、token、secret、password。
- [x] 增加审计日志基础版：谁触发、用了哪些文件、生成了哪些结论，保存到 `data/audit/events.jsonl`。
- [x] 增加字段级敏感数据分类：客户信息、采购价、财务数据按字段名识别；客户个人信息输出脱敏，采购价/财务数据默认聚合或审计，并在 `/data-health` 标记本次可见敏感字段。

## P5：前端体验

- [x] 在前端增加任务模板基础版：整理资料、清洗表格、库存风险、经营分析、同步知识库。
- [x] 增加 LangGraph stream 错误中文提示条：`BadRequestError`、`TypeError: Failed to fetch`、旧 tool 历史、后端断连等问题不再直接暴露为 Next.js 红屏。
- [x] 修复真实线程续聊 payload，避免前端把用于 UI 显示的 synthetic tool response 当成实际模型上下文提交。
- [x] 增加 Agent 执行 trace 折叠面板：展示工具调用、后台任务步骤和审计事件。
- [x] 增加重复 supervisor 最终报告折叠：多 Agent handoff 后子团队报告和顶层转述内容重复时，聊天历史只展示一份最终答案。
- [x] 增加 `/data-health` 数据健康页：展示 LightRAG、DuckDB、datasets、最近任务。
- [x] 增加 `/governance` 轻量 Skill / MCP 显示页：展示 Skill 配置、MCP/API policy、治理审计，并支持导入已有 Markdown/SKILL.md 为配置草稿、启停 Skill、登记 MCP/API policy。
- [x] 在 `/governance?tab=skills` 的“权限与工具”页内增加 SkillHub 技能市场：可检查 CLI、按类目/来源/排序浏览或搜索 SkillHub、安装技能到项目 `skills/`，并自动导入为配置草稿。
- [x] “权限与工具”页前端文案已把偏技术的“注册表”收敛为“工具清单”“已配置”“已配置技能”和“配置状态”；底层 Skill Registry / Tool Registry 仍作为工程数据结构保留。
- [x] 增加左侧“历史对话”入口：点击后进入 `/?chatHistoryOpen=true`，空白首页桌面端在主内容区显示本地聊天归档，具体对话中改用居中浮层选择器；移动端保留抽屉，和 `/tasks` 的经营任务历史区分开。
- [x] 空白首页 composer 补回 `数据健康` 和 `Skill / MCP` 管理入口；之前入口只在进入对话后的顶部栏显示，容易误认为按钮丢失。
- [x] LightRAG destructive preview 升级为 approve/reject interrupt；CLI 仍兼容确认 token。
- [x] 增加更多前端任务模板：广告诊断、商品内容优化、供应商风险、财务分析、老板报告。
- [x] 展示全链路进度：已发现文件、已清洗、已入库、已分析、已生成报告。
- [x] 展示生成文件链接：wiki 页面、cleaned CSV/derived export、DuckDB、registry、LightRAG 状态、决策报告。
- [x] 增加人工确认按钮和风险提示。

## P6：Connector / Skill / MCP 扩展

- [x] 增加 Connector 注册表：名称、版本/来源目录、适用系统、只读/写入边界、凭据环境变量、数据集 schema、同步状态。
- [x] 增加 Connector 工具：list、health、capability preview、只读 snapshot 注册到 DuckDB fact layer。
- [x] 增加第一个只读 API adapter：吉客云/金蝶实时只读兜底查询，前端对话默认 DuckDB 优先、实时 ERP 按需调用。
- [x] 把高复用 wiki 页面转成真正可启用/禁用的 Agent Skill：UNOVE 国内渠道经营策略已启用为 active skill/template。
- [x] 增加 Skill 注册表：名称、版本、适用场景、工具权限、输出格式。
- [x] 增加 Skill 审批机制：新 skill 默认草稿状态，人工确认后启用。
- [x] 增加 active Skill 自动匹配与注入：前端对话提示词命中 active Skill 场景/关键词时，自动把对应 template 注入 Agent 模型上下文；暂停、禁用和草稿 Skill 不参与注入。
- [x] 增加前端“权限与工具”入口：`/governance?tab=skills` 支持导入已有 wiki/Markdown/SKILL.md、查看状态、启用、暂停、禁用和按版本回滚。
- [x] 增加外部技能市场接入：SkillHub 安装后的技能进入项目 Skill Library 和 Skill 配置草稿流，不自动变成 active Skill。
- [x] 接入第一个只读 MCP 或 API adapter：吉客云 ERP / 金蝶 ERP 实时只读查询，本地数据库查询继续走 DuckDB fact layer。
- [x] 增加 MCP 工具权限配置：只读、写入、需要人工确认。
- [x] 增加前端 MCP/API policy 管理入口：`/governance` 可登记已有 MCP/API 工具，写入类默认强制人工确认。
- [x] 增加 MCP 审计：记录调用者、参数摘要、返回数据来源、风险等级。
- [x] 为写入类 MCP 增加人工确认 UI：创建采购单、修改广告预算、外发消息复用 Agent Inbox approve/edit/reject。

## P8：标准化 A2A

- [ ] 增加项目内 `A2A Protocol` schema：agent discovery、invoke、async task、task status、task events。
- [ ] 增加本地 `A2A Server`：让本项目可作为独立 agent 服务被外部系统调用。
- [ ] 增加 `A2A Client`：支持调用外部独立 agent 服务。
- [ ] 统一本地动态 agent 和远程 A2A agent 的路由入口：对 supervisor 暴露同一套 agent_id 调用模型。
- [ ] 增加远程 A2A 权限边界：哪些上下文可以传、哪些数据只能传引用、哪些动作必须人工确认。
- [ ] 增加远程 A2A 审计：跨进程/跨系统调用的 trace_id、参数摘要、结果摘要、风险等级。
- [ ] 增加前端可见状态：当前调用的是本地 agent 还是远程 A2A agent，是否为动态生成 agent。

## P7：工程护栏

- [x] 增加 `scripts/verify_python.ps1`：统一跑 compileall、unittest，并在可用时执行 Ruff/Pyright。
- [x] 增加 `pyproject.toml`：放入 Ruff / Pyright 配置。
- [x] 增加 `requirements-dev.txt` 并在本地安装 Ruff / Pyright。
- [x] 让 `verify_python.ps1` 真正执行 Ruff / Pyright，当前本地结果为通过。
- [x] 增加 Windows + macOS 双平台启动骨架：`start/stop/health_*` 的 `.ps1` + `.sh` 版本并存。
- [x] 去掉前端启动脚本里的固定 Node 路径，改为读取 PATH 或 `A2A_NODE_BIN`。
- [x] 让前端本地线程归档支持 `A2A_DATA_DIR` / `A2A_TASK_DIR` / `A2A_THREAD_ARCHIVE_DIR`。
- [x] 更新 README 为跨平台运行说明，并补充路径审计文档 `docs/cross-platform-path-audit.md`。
- [x] 后端 macOS 启动脚本改为更稳的后台会话方式，并配套停止脚本，避免健康检查通过后进程退出。
- [x] 增加 LightRAG 失败诊断/补救回归测试：`tests/test_lightrag_retry.py`。
- [x] README 已补充当前进度、代码升级和 LightRAG 失败根因说明。
- [x] 增加前端 stream 错误回归测试：`agent-chat-ui/src/lib/stream-errors.test.ts`。
- [x] 增加旧线程 tool 消息协议回归测试：前端 `local-archive-thread.test.ts` 与后端 `test_supervisor_model_config.py` 均覆盖。
- [x] 增加旧线程归档离线修复测试：`tests/test_thread_repair_tools.py`。
- [x] 增加旧线程修复脚本：`scripts/repair_thread_archives.py` / `scripts/repair_thread_archives.sh`。
- [x] 增加 `install_lightrag.ps1/.sh` 之外更多跨平台运维脚本配对，并用 `tests/test_p7_engineering_guardrails.py` 固化新增脚本默认同时提供两套壳层。
- [x] 继续清理深层文档中的历史 Windows 路径示例，统一成 `<A2A_PROJECT_ROOT>` 占位符，并用 P7 guardrail 测试防止回归。

## P9：Workbench 控制台总线

目标：参考 OpenClaw 的 control plane 思路，但不重写成完整 Gateway。先在现有 Next API 之上建立轻量、稳定、类型化的 workbench contract，让聊天页、数据健康页、治理页、后续任务页和日志页不再各自拼字段。

范围：

- [x] 新增 `agent-chat-ui/src/lib/workbench-contract.ts`，定义统一方法名、请求参数、响应类型和错误类型。
- [x] 首批方法固定为：`task.list`、`task.show`、`agent.trace`、`data.health`、`governance.policy`、`approval.submit`、`logs.tail`。
- [x] 统一响应 envelope：`ok`、`method`、`request_id`、`generated_at`、`data`、`error`、`warnings`。
- [x] 统一错误结构：`code`、`message`、`hint`、`retryable`、`source`、`details`。
- [x] 统一作用域字段：`thread_id`、`task_id`、`agent_id`、`tool_name`、`scope`。
- [x] 为所有读取类 API 增加默认 scope 保护：无 `thread_id` / `task_id` 时默认不返回全局敏感历史，除非显式 `scope=global`。

后端/API：

- [x] 梳理现有 `/api/data-health` 响应，补齐 `schema_version`、`generated_at`、`source_files`、`warnings`。
- [x] 梳理现有 `/api/governance` 响应，补齐 Skill、MCP policy、audit 的稳定字段。
- [x] 梳理现有 `/api/agent-traces` 响应，拆成 `tool_calls`、`task_steps`、`audit_events`、`timeline`。
- [x] 梳理现有 `/api/lightrag-status` 响应，统一 `processed`、`pending`、`processing`、`failed`、`pipeline_busy`、`root_causes`。
- [x] 新增 `/api/workbench` 轻量分发入口，内部调用现有 API helper，不重复实现业务逻辑。
- [x] `approval.submit` 先只对接现有 Agent Inbox/interrupt payload，不新增外部写入能力。

前端：

- [x] 新增 `agent-chat-ui/src/lib/workbench-client.ts`，封装 `callWorkbench(method, params)`。
- [x] data-health 页面改为使用 workbench client。
- [x] governance 页面改为使用 workbench client。
- [x] trace panel 改为使用 workbench client。
- [x] 后续 `/tasks`、`/logs` 页面直接复用 workbench client。
- [x] 前端所有 workbench 错误统一显示中文提示，不再泄露原始堆栈。

测试/验收：

- [x] 增加 `agent-chat-ui/src/lib/workbench-contract.test.ts`：校验 envelope、错误结构和方法名。
- [x] 增加 API route 测试：无 scope 请求不得返回全局 audit/task 历史。
- [x] 增加 data-health/governance/trace smoke 测试：旧页面功能不回退。
- [x] `npm run build` 通过。
- [x] `git diff --check` 通过。

明确不做：

- [x] 不引入 OpenClaw 的完整 WebSocket Gateway。
- [x] 不接入 Telegram/Slack/WhatsApp 等多渠道 runtime。
- [x] 不改变 LangGraph 当前运行入口。

## P10：任务详情页和经营任务历史库

目标：参考 MiroFish 的阶段化工作台，把 `data/tasks` 从“后台 JSON 文件”变成 PM 能看懂的经营任务历史库。优先级最高，因为它直接提升日常使用体感。

核心页面：

- [x] 新增 `/tasks` 列表页。
- [x] 新增 `/tasks/[taskId]` 详情页。
- [x] 首页、聊天 trace 面板和 `/data-health` 增加任务历史入口。
- [x] 空状态说明：没有任务时提示用户如何把资料放入 `raw/` 并启动整理/清洗。

任务列表字段：

- [x] `task_id`
- [x] `goal`
- [x] `status`
- [x] `created_at`
- [x] `updated_at`
- [x] `requested_by`
- [x] `steps_count`
- [x] `background_running`
- [x] `recoverable`
- [x] `has_report`
- [x] `risk_count`
- [x] `artifact_count`

筛选和排序：

- [x] 按状态筛选：created、queued、running、warning、success、failed、cancelled、recoverable。
- [x] 按时间筛选：今天、7 天、30 天、全部。
- [x] 按任务类型筛选：资料整理、表格清洗、LightRAG 同步、经营分析、老板报告、ERP 只读查询。
- [x] 按关键词搜索：goal、task_id、报告名、wiki 页面名。
- [x] 默认按 `updated_at` 倒序。

任务详情内容：

- [x] 顶部 summary：目标、状态、创建时间、更新时间、是否后台运行、是否可恢复。
- [x] 阶段进度条：raw discovery、large excel、cleaning、fact registration、wiki ingest、LightRAG sync、quality gate、analysis、report。
- [x] 每个 step 展示：任务名、状态、摘要、完成时间、风险、缺失数据、下一步动作。
- [x] 产物区：wiki 页面、cleaned CSV、Parquet/DuckDB registry、quality report、decision report、LightRAG 状态链接。
- [x] 证据链区：引用的数据集、wiki、manifest、quality_report、mart 表。
- [x] 时间线区：task steps + audit events 合成单一 timeline；thread/tool calls 继续由 trace panel 和 `/api/agent-traces` 承接。
- [x] 错误区：错误代码、原始消息摘要、建议修复动作、相关日志链接。

操作按钮：

- [x] 查看报告。
- [x] 打开相关 wiki。
- [x] 打开 data-health。
- [x] 查看 trace。
- [x] 取消 running 任务。
- [x] 对 recoverable 任务触发恢复。
- [x] 对 LightRAG failed 任务跳转诊断/恢复入口。
- [x] 对旧线程协议异常跳转修复脚本说明。

后端/API：

- [x] 新增任务摘要 loader，读取 `data/tasks/*.json` 并容错 invalid JSON。
- [x] 新增 task artifact extractor，从 task steps、report path、wiki path、registry path 中提取产物。
- [x] 新增 timeline builder，合并 task steps、audit events；thread archive tool calls 保持在 trace API。
- [x] 新增 `GET /api/tasks`。
- [x] 新增 `GET /api/tasks/[taskId]`。
- [x] 可选接入 P9 的 `task.list` / `task.show`。

前端体验：

- [x] 使用表格或密集列表，不做营销式大卡片。
- [x] 状态使用小 badge：success、warning、failed、running、cancelled。
- [x] 任务详情要适合 PM 扫描，避免展示大段 JSON。
- [x] JSON 原文折叠到高级区。
- [x] 移动端至少保证可读，不要求复杂图表。

测试/验收：

- [x] 增加 `agent-chat-ui/src/lib/tasks.test.ts`：测试任务摘要、产物提取、timeline 合并、invalid JSON 容错。
- [x] 增加 route/API smoke：不存在 task 返回友好错误。
- [x] 增加页面 build 检查：`npm run build` 通过。
- [x] 用至少一个真实 `data/tasks/*.json` 验证列表和详情页可渲染。
- [x] 不破坏现有聊天、data-health、governance。

明确不做：

- [x] 不在 P10 迁移任务存储到 SQLite，P12 再做。
- [x] 不重写后台任务执行器。
- [x] 不把所有历史 thread 都强行变成 task。

## P11：工具注册中心 2.0

目标：参考 Hermes Agent 的 tool registry，把当前静态 `AGENT_TOOL_ALLOWLISTS` 升级为结构化、可治理、可测试、可展示的工具注册中心。收益是减少 allowlist 漂移，提升治理页和安全测试的可信度。

数据结构：

- [x] 新增 `ToolEntry` dataclass 或 TypedDict。
- [x] 字段包含：`name`、`handler`、`description`、`group`、`read_only`、`risk_level`、`requires_confirmation`、`data_sources`、`max_result_size`、`availability_check`、`owner_module`。
- [x] `risk_level` 固定为：low、medium、high、destructive。
- [x] `group` 固定为：`read_fact`、`read_knowledge`、`write_local_state`、`external_read`、`external_write_request`、`destructive_maintenance`、`governance`、`workflow`。
- [x] `data_sources` 固定使用项目内名字：DuckDB、wiki、LightRAG、raw、ERP_live_readonly、audit、tasks、reports、MCP_policy。

迁移步骤：

- [x] 在 `src/a2a_ecommerce_demo/agent_tool_registry.py` 中新增 `TOOL_REGISTRY`。
- [x] 先为现有工具补元数据，不改 Agent 行为。
- [x] 增加 `resolve_agent_tool_entries(agent_name)`，返回结构化 entries。
- [x] 现有 `resolve_agent_tools()` 改为从 entries 中取 handler，保持外部调用兼容。
- [x] 将超长 allowlist 拆为工具组 + 显式例外。
- [x] 保留旧 `AGENT_TOOL_ALLOWLISTS` 作为兼容层，直到测试完全覆盖。

工具组策略：

- [x] `data_agent` 默认可见 `read_fact`、`external_read`、部分 `governance`。
- [x] `knowledge_agent` 默认可见 `read_knowledge`、受控 `write_local_state`。
- [x] `decision_agent` 默认可见 `read_fact`、`read_knowledge`、低风险分析工具。
- [x] `auto_workflow_agent` 可见 `workflow` 和受控写入工具，但写入/破坏性动作必须 confirmation。
- [x] `quality_gate_agent` 可见敏感字段分类和只读质量工具。
- [x] 任何 read-only Agent 不得获得 `external_write_request` 或 `destructive_maintenance`。

治理页：

- [x] `/governance` 增加 Tool Registry tab 或区域。
- [x] 展示工具总数、read-only 数、写入类数、高风险数、需要确认数。
- [x] 支持按 group、risk_level、agent、data_source 过滤。
- [x] 每个工具显示：描述、所属模块、可见 Agent、确认策略、最近调用风险。
- [x] MCP/API policy 与 Tool Registry 做交叉展示：外部工具必须同时满足 registry 和 policy。

测试/验收：

- [x] 更新 `tests/test_agent_tool_registry.py` 覆盖 ToolEntry 元数据完整性。
- [x] 增加测试：所有 allowlist 工具必须存在于 TOOL_REGISTRY。
- [x] 增加测试：read-only Agent 不包含写入或破坏性工具。
- [x] 增加测试：requires_confirmation 的工具不能直接进入裸执行路径。
- [x] 增加测试：外部 ERP 写入能力保持 disabled。
- [x] `./scripts/verify_python.sh` 通过。

明确不做：

- [x] 不引入通用插件市场。
- [x] 不允许用户在前端随意打开写入工具。
- [x] 不改变现有工具函数业务逻辑，只改注册和治理层。

## P12：SQLite durable queue

目标：参考 Hermes Kanban，把长任务从 JSON + background thread 逐步升级为 SQLite durable queue。这个不是内部试用的前置条件，适合在 P10 任务页稳定后做。

设计原则：

- [x] 先兼容现有 `data/tasks/*.json`，不一次性迁移历史。
- [x] SQLite 存任务状态和事件，JSON 可继续作为导出/兼容格式。
- [x] 短委派和持久任务分层：策略拆解、只读补充分析仍走轻量工具；raw ingest、Excel 分块、LightRAG rebuild、ERP snapshot 进入 durable queue。
- [x] 所有长任务必须有 idempotency key，避免重复点击造成重复写入。

SQLite schema：

- [x] `tasks`：task_id、goal、status、requested_by、created_at、updated_at、started_at、finished_at、cancel_requested、idempotency_key、current_step、error_code。
- [x] `task_events`：event_id、task_id、timestamp、event_type、step_name、status、summary、payload_json、error_json。
- [x] `task_artifacts`：artifact_id、task_id、kind、path、label、created_at、metadata_json。
- [x] `task_claims`：claim_id、task_id、worker_id、claimed_at、heartbeat_at、expires_at、status。
- [x] `task_retries`：retry_id、task_id、step_name、attempt、reason、created_at。
- [x] `schema_migrations`：version、applied_at。

执行器：

- [x] 新增 `src/a2a_ecommerce_demo/task_queue.py`。
- [x] 支持 enqueue、claim、heartbeat、append_event、complete、fail、cancel、reclaim。
- [x] 后端启动时扫描过期 claim，把 running 任务标记为 recoverable。
- [x] 同一个 idempotency key 的任务不重复创建。
- [x] task step 执行前检查 cancel_requested。
- [x] 写入 event 和 artifact 使用事务。

兼容层：

- [x] `list_workflow_tasks()` 同时读取 SQLite 和旧 JSON。
- [x] `get_workflow_task_status()` 对新任务读 SQLite，对旧任务读 JSON。
- [x] P10 `/tasks` 页面不需要感知底层存储差异。
- [x] 提供一次性 `scripts/migrate_tasks_to_sqlite.py`，默认 dry-run；只有 `--write` 才写入。

测试/验收：

- [x] 增加队列单元测试：enqueue、claim、heartbeat、complete、fail、cancel。
- [x] 增加 crash reclaim 测试：过期 heartbeat 的 running task 可恢复。
- [x] 增加 idempotency 测试：重复 key 不创建第二个任务。
- [x] 增加状态机测试：success/failed/cancelled 不能再次 claim。
- [x] 增加并发 claim 测试：同一任务不会被两个 worker 同时 claim。
- [x] `./scripts/verify_python.sh` 通过。

明确不做：

- [x] 不引入外部队列服务。
- [x] 不做多机器分布式调度。
- [x] 不在 P12 改前端任务页视觉，P10 已负责。

## P13：Doctor、Logs 和配置 Schema

目标：让项目出问题时可以自诊断，而不是靠手翻日志。参考 OpenClaw 的 doctor/logging 思路，先做本地单机诊断和日志页面。

Doctor CLI：

- [x] 新增 `scripts/doctor.py`。
- [x] 新增 `scripts/doctor.sh` 和 `scripts/doctor.ps1` 脚本配对。
- [x] 输出格式支持 human-readable 和 `--json`。
- [x] 检查结果分级：ok、warn、fail、skipped。
- [x] 每个 fail 都给出修复建议和相关文件/命令。

Doctor 检查项：

- [x] Python 版本和虚拟环境。
- [x] 必要 Python 依赖是否可 import。
- [x] Node/npm/pnpm 和前端依赖状态。
- [x] `.env` 必要键是否存在，敏感值只显示是否设置，不打印明文。
- [x] LangGraph 后端端口 2024 是否可用。
- [x] 前端端口 3000 是否可用。
- [x] LightRAG 端口 9621 是否可用。
- [x] DuckDB 文件是否存在、可打开、主要 mart 是否存在。
- [x] dataset registry 是否存在、是否 valid JSON。
- [x] `data/tasks` 是否存在 invalid JSON。
- [x] `data/audit/events.jsonl` 是否可读，最近 N 行是否 valid JSON。
- [x] MCP policy 是否 valid JSON，外部写入是否默认 disabled。
- [x] Skill registry 是否 valid JSON，active Skill 是否有对应 template。
- [x] 旧 thread archive 是否存在孤立 tool message。
- [x] P7 脚本配对检查。

Logs 页面：

- [x] 新增 `/logs` 页面。
- [x] 新增 `/api/logs` 只读 API。
- [x] 支持读取 `langgraph-server.log`、`langgraph-server.err.log`、`frontend.err.log`、`lightrag-server.log`、`lightrag-server.err.log`。
- [x] 支持读取 `data/audit/events.jsonl`。
- [x] 支持未来读取 SQLite `task_events`。
- [x] 支持按 source、level、thread_id、task_id、agent_id、tool_name、risk_level 过滤。
- [x] 默认只返回最近 200 行。
- [x] 不在前端显示 API key、token、secret、password。

配置 schema：

- [x] 新增 `.env.example` 或更新现有模板，标明必填、可选、默认值。
- [x] 新增 config validator，覆盖 `.env`、connector registry、MCP policy、Skill registry、LightRAG settings。
- [x] `/data-health` 增加 config health 摘要。
- [x] `/governance` 增加 policy validation 状态。

Audit 字段约定：

- [x] 扩展 `record_audit_event()`，统一字段：timestamp、level、event_type、actor、agent_id、thread_id、task_id、tool_name、risk_level、data_sources、paths、status、duration_ms、error_code、metadata。
- [x] 老事件兼容读取，不强制迁移。
- [x] 敏感字段和参数摘要继续脱敏。

测试/验收：

- [x] 增加 `tests/test_doctor.py`：覆盖 ok/warn/fail 输出和敏感值不泄露。
- [x] 增加前端 logs lib 测试：tail、filter、redaction。
- [x] P7 guardrail 更新：doctor `.sh/.ps1` 必须配对。
- [x] `./scripts/verify_python.sh` 通过。
- [x] `npm run build` 通过。

明确不做：

- [x] 不做远程日志平台。
- [x] 不上传日志到第三方。
- [x] 不做多用户权限系统，只做本地内部诊断。

## P14：证据链图谱 / 经营对象图

目标：参考 MiroFish 的图谱面板，但做成电商经营证据导航，而不是社交仿真图。图谱帮助 PM 和老板理解结论来自哪里、影响哪些对象、哪些证据需要人工确认。

数据来源：

- [x] DuckDB dataset registry。
- [x] `wiki/datasets/**` 页面。
- [x] `wiki/decisions/**` 页面。
- [x] LightRAG 引用定位结果。
- [x] `data/tasks` step artifacts。
- [x] `data/reports` 决策报告。
- [x] `data/audit/events.jsonl` 中的风险和敏感字段事件。

节点类型：

- [x] `brand`：品牌。
- [x] `channel`：天猫、抖音、京东、拼多多、唯品会等。
- [x] `sku`：商品/SKU。
- [x] `warehouse`：仓库。
- [x] `supplier`：供应商。
- [x] `dataset`：数据集或表。
- [x] `mart`：DuckDB mart。
- [x] `wiki_page`：知识页。
- [x] `report`：报告。
- [x] `decision`：决策。
- [x] `risk`：风险。
- [x] `field`：关键字段或敏感字段类型。

关系类型：

- [x] `derived_from`：由某资料/数据集生成。
- [x] `summarizes`：汇总。
- [x] `references`：引用。
- [x] `affects`：影响。
- [x] `belongs_to`：归属品牌/渠道。
- [x] `has_risk`：存在风险。
- [x] `needs_confirmation`：需要人工确认。
- [x] `uses_sensitive_field`：使用敏感字段。

后端/API：

- [x] 新增 `src/a2a_ecommerce_demo/evidence_graph_tools.py`。
- [x] 新增 `build_evidence_graph(scope, task_id='', report_path='', limit=...)`。
- [x] 新增 `list_evidence_graph_nodes()` 和 `list_evidence_graph_edges()`。
- [x] 节点和边输出稳定 schema：id、type、label、source_path、summary、risk_level、metadata。
- [x] 对超大图做 limit 和 type filter。
- [x] 不把客户手机号、地址、采购价明细放进节点 label。

前端：

- [x] 新增 `/evidence-graph` 页面。
- [x] 在 `/tasks/[taskId]` 和报告区域增加“查看证据图”入口。
- [x] 支持按节点类型过滤。
- [x] 支持点击节点跳转到 wiki、dataset、report 或 task。
- [x] 支持风险节点高亮。
- [x] 首版可以用简单 force graph 或分层列表，不追求复杂交互。

测试/验收：

- [x] 增加 evidence graph 单元测试：节点去重、边去重、路径引用、敏感字段不泄露。
- [x] 增加真实 registry/wiki/report fixture 测试。
- [x] 前端 build 通过。
- [x] 图谱只作为证据导航，不能替代 DuckDB 查询结果。

明确不做：

- [x] 不引入 OASIS/Twitter/Reddit 仿真。
- [x] 不替换 LightRAG。
- [x] 不把图谱作为财务/库存聚合计算引擎。
