# Task Delegation 工作流

本项目已经加入 DeepAgents / Claude subagents 风格的任务委派层。

它不是让多个 Agent 无限聊天，而是让 `auto_workflow_agent` 像项目经理一样，把复杂任务拆成多个受控子任务，每个子任务只返回结构化结果。

## 核心文件

```text
<A2A_PROJECT_ROOT>/src/a2a_ecommerce_demo/task_delegation_tools.py
<A2A_PROJECT_ROOT>/src/a2a_ecommerce_demo/task_queue.py
<A2A_PROJECT_ROOT>/data/tasks
```

每次任务会生成一个 `task_id`，并保存为 JSON 兼容视图：

```text
<A2A_PROJECT_ROOT>/data/tasks\<task_id>.json
```

长任务调度状态由 SQLite durable queue 负责，默认位置：

```text
<A2A_PROJECT_ROOT>/data/tasks/tasks.sqlite
```

JSON 文件继续用于任务详情、人工排查和前端兼容；SQLite 存权威队列状态、claim、heartbeat、事件、产物和重试记录。

## 子任务

- `create_workflow_task`：创建任务和 task_id。
- `run_raw_discovery_task`：列出 raw 文件，识别超过 100MB 的大文件。
- `run_excel_cleaning_task`：画像和清洗 Excel，超大文件自动跳过。
- `run_wiki_ingest_task`：整理资料进入 Obsidian。
- `run_quality_task`：检查数据质量和字段缺口。
- `run_finance_task`：分析公司级财务和现金流。
- `run_company_strategy_task`：生成公司级经营策略建议。
- `finalize_workflow_report`：汇总子任务，保存报告和 Obsidian 决策记录。
- `get_workflow_task_status`：读取任务状态。
- `recover_workflow_queue`：恢复 JSON/SQLite 中可恢复的长任务，并回收过期 claim。
- `cancel_workflow_task`：请求取消长任务；queued/recoverable 任务会直接进入 `cancelled`。

## Durable Queue

P12 之后，raw ingest、Excel 分块、LightRAG rebuild、ERP snapshot 这类长任务进入 SQLite durable queue。队列表包括：

- `tasks`：任务状态、idempotency key、当前步骤和错误码。
- `task_claims`：claim lock、worker、heartbeat、过期时间。
- `task_events`：入队、claim、heartbeat、步骤完成、恢复、失败、取消。
- `task_artifacts`：步骤证据和产物路径。
- `task_retries`：失败重试次数和原因。
- `schema_migrations`：本地 schema 版本。

同一个 idempotency key 不会创建第二个任务，避免前端重复点击造成重复写入。后端启动恢复时会先扫描过期 heartbeat，把 `running` 任务标记为 `recoverable`，再由 worker 重新 claim。

历史 JSON 任务可先 dry-run 检查：

```text
python scripts/migrate_tasks_to_sqlite.py
```

确认无误后再写入：

```text
python scripts/migrate_tasks_to_sqlite.py --write
```

## 推荐前端说法

```text
请用 task delegation 工作流处理 raw 目录里的公司资料：创建 task_id，发现资料，清洗表格，整理进 Obsidian，做数据质量检查，分析财务和公司策略，最后生成公司经营辅助决策报告。
```

查询状态：

```text
请查询 task_id 为 xxx 的任务状态，并告诉我每个子任务完成了什么、还有哪些风险。
```

## 大文件策略

超过 100MB 的 Excel 不会进入前端同步解析。系统会：

- 记录文件路径和大小。
- 标记风险。
- 要求先拆分或导出 CSV。
- 不阻塞后续小文件处理。

## 为什么这样设计

借鉴 DeepAgents：

- 主 Agent 只拿子任务摘要，减少上下文膨胀。
- 每个子任务独立返回结构化结果。

借鉴 Claude subagents：

- 每类任务有明确角色和工具边界。
- 财务、清洗、知识库、策略任务分开执行。

保留本项目特点：

- 所有本地文件访问仍限制在 `raw`、`wiki`、`data`。
- 输出可追踪，可复盘。
- 适合国内多平台电商公司的经营辅助决策。
