# 参考项目分析与取舍

本项目参考了三个开源项目和 Karpathy LLM Wiki 的方向，但不会直接照搬。目标是把优点转成适合国内多平台电商公司的本地多 Agent 决策工作台。

## OpenClaw

可借鉴点：

- 本地优先：用户资料、文件、浏览器、工具调用尽量在本机或受控环境中完成。
- 工具网关：Agent 不应该无限制控制电脑，而是通过明确工具访问文件、网页、API、MCP。
- 任务路由：复杂目标需要一个主管层，把任务交给合适的执行单元。
- 安全边界：读取本地文件时必须限制目录，避免越权读取或误操作。

落到本项目：

- `raw`、`wiki`、`data`、`data/cleaned` 都有固定边界。
- `supervisor` 负责路由。
- `auto_workflow_agent` 负责全链路任务。
- 后续可加入工具权限配置和人工确认门槛。

## MiroFish

可借鉴点：

- 种子资料驱动：先从用户上传的资料、文档、表格中抽取结构化信息。
- 知识结构：把资料沉淀为可复用知识，而不是只做一次性聊天。
- 多视角推演：同一问题从库存、财务、风险、运营等角度交叉验证。
- 决策报告：输出不是闲聊，而是结论、证据、风险、方案和下一步动作。

落到本项目：

- `wiki` 作为 Obsidian 知识库。
- `data/cleaned` 作为结构化数据层。
- `inventory_agent`、`finance_agent`、`risk_agent`、`decision_agent` 做多视角决策。
- 后续可引入轻量知识图谱，把 SKU、供应商、仓库、平台规则、历史决策建立关系。

## Hermes Agent

可借鉴点：

- Skill 化：能力应该拆成可复用技能，而不是每次都写长 prompt。
- 长程任务：复杂任务要能拆分、执行、检查、修复，而不是一步输出。
- 记忆沉淀：每次任务的经验、清洗规则、失败原因要保存下来。
- 动态执行：根据任务目标临时组合工具和角色。

落到本项目：

- 清洗、入库、检索、决策都已经拆成工具。
- `auto_workflow_agent` 作为长程任务编排入口。
- 清洗报告和决策记录可以写入 Obsidian。
- 后续建设 `Agent Factory`，自动生成临时角色和 prompt。

## Karpathy LLM Wiki

可借鉴点：

- 把知识库当作 LLM 的长期外部记忆，而不是文件堆积处。
- 页面要写给未来的自己和 Agent 看，必须可检索、可引用、可复盘。
- 保留来源和证据链，避免 Agent 只给结论没有出处。
- 原子化和链接化：产品、供应商、字段、规则、决策都应该独立成页，并用双链连接。
- 从每次任务中提炼可复用规则，例如字段解释、清洗经验、补货判断标准。

落到本项目：

- `wiki` 是长期记忆层。
- `raw` 是原始证据层。
- `data/cleaned` 是可分析数据层。
- `decisions` 保存决策记录，`cleaning-rules` 保存清洗经验，`data-dictionary` 保存字段解释。
- `auto_workflow_agent` 在全链路任务中负责把一次性处理结果沉淀为长期知识。

## 推荐架构

```text
用户一句话任务
    ↓
supervisor
    ↓
auto_workflow_agent
    ↓
任务画像 / 文件发现 / 数据质量门
    ↓
data_cleaning_agent / wiki_ingest_agent / knowledge_agent
    ↓
data_agent / inventory_agent / finance_agent / risk_agent
    ↓
decision_agent
    ↓
报告 / Obsidian 记录 / cleaned 数据
    ↓
长期记忆：字段字典 / 清洗规则 / 决策复盘 / 产品与供应商知识
```

## 当前已经落地

- 本地文件边界：`raw`、`wiki`、`data`、`data/cleaned`。
- Obsidian 入库：多格式资料自动生成 Markdown。
- Excel 清洗：画像、表头识别、空行空列、合并单元格、重复表头、公式风险提示。
- 决策 Agent：库存、财务、风险、A/B/C 方案。
- 全链路入口：`auto_workflow_agent`。
- Karpathy LLM Wiki 文档：把 Obsidian 作为长期外部记忆使用。

## 历史参考状态

这份文档保留为历史参考。原先的增强方向已经部分吸收进主线：

- `quality_gate_agent`、Agent Factory、任务状态、ERP 只读兜底、证据图谱和 Wiki claim/evidence 生命周期已落地。
- 高风险写入、删除、外发和清理类动作已经统一走 confirmation/approval 边界，普通运行时 Agent 默认只挂载 direct/read-only 工具。
- 广告平台、客服售后和店铺后台数据仍按“后台导出文件 -> raw 清洗 -> DuckDB/wiki/LightRAG 入库”的保守路径处理。
- 后续仍可优化的是更细的图谱交互、管理页体验和多用户/多机器部署下的 durable worker。
