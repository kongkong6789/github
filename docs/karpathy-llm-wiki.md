# Karpathy 式 LLM Wiki 个人知识库方案

这里的“个人知识库”不是把文件堆进 Obsidian，而是把资料变成 Agent 长期可用的外部记忆。

核心思想：

- 写给未来的自己和 Agent：每一页都要能被检索、引用、复盘。
- 保留来源：结论必须能追溯到原始文件、清洗后的数据和生成时间。
- 原子化：一个页面尽量围绕一个产品、供应商、规则、决策或清洗规则。
- 链接化：用 Obsidian 双链把 SKU、供应商、仓库、平台、广告活动、历史决策连起来。
- 可执行：知识页不只是摘录，要沉淀 SOP、判断标准、字段解释和下一步动作。

## 推荐目录

```text
<A2A_PROJECT_ROOT>/wiki
├─ index.md
├─ products\        # SKU、产品档案、卖点、差评、商品内容记录
├─ suppliers\       # 供应商、报价、交期、合同、异常记录
├─ inventory\       # 库存规则、安全库存、补货策略
├─ platform-rules\  # 天猫、淘宝、抖音、拼多多、唯品会、京东等平台规则
├─ ad-strategy\     # 广告策略、投产比、费比、GMV、预算复盘
├─ data-dictionary\ # 字段解释、ERP/平台报表字段映射
├─ cleaning-rules\  # 表格清洗规则、表头规则、异常格式处理经验
├─ decisions\       # 辅助决策报告、结论、证据、复盘
└─ logs\            # 自动入库、清洗、任务执行日志
```

## 页面模板

每个重要页面建议保持这个结构：

```markdown
---
type: product | supplier | rule | cleaning-rule | decision | log
source:
created_at:
updated_at:
tags:
---

# 标题

## 这是什么

一句话说明页面用途。

## 关键事实

- 可被 Agent 直接引用的事实。

## 来源

- 原始文件：
- 清洗文件：
- 相关 wiki：

## 判断标准

- 什么情况下应该采取动作。
- 什么情况下应该人工确认。

## 相关页面

- [[products/xxx]]
- [[suppliers/xxx]]
- [[decisions/xxx]]

## 待确认

- 数据缺口。
- 人工需要补充的信息。
```

## 和当前项目怎么配合

当前项目已经具备基础能力：

- `wiki_ingest_agent`：把 raw 资料转成 Obsidian Markdown。
- `data_cleaning_agent`：把复杂 Excel 清洗成 `data/cleaned`。
- `knowledge_agent`：检索和读取 Obsidian。
- `auto_workflow_agent`：把清洗、入库、分析、决策串成一条流水线。

后续应该让 Agent 自动沉淀四类长期记忆：

1. 清洗规则：例如“进销存台账第 1 行是表头，货品 ID 和货品编码必须按文本处理”。
2. 字段字典：例如“期末良品 = 可销售库存，采购在途 = 未入仓采购量”。
3. 决策记录：例如“某 SKU 是否补货，为什么，引用了哪些数据”。
4. 复盘结论：例如“上次预测断货是否发生，补货建议是否过量”。

## 推荐前端说法

```text
请把 raw 目录里的资料整理进 Obsidian，并按照 Karpathy LLM Wiki 的方式拆成可复用知识页：产品、供应商、字段字典、清洗规则、决策记录分别沉淀。
```

```text
请基于 cleaned 数据生成库存辅助决策报告，并把结论、证据链、字段解释和可复用规则保存进 Obsidian。
```

```text
请搜索 Obsidian 里和这个 SKU 相关的产品、供应商、库存、广告和历史决策页面，再给我建议。
```

## 后续升级目标

- 自动生成 data dictionary 页面。
- 自动把 SKU、供应商、仓库、平台规则变成双链。
- 自动给每次决策生成复盘提醒。
- 从 wiki 页面抽取轻量知识图谱。
- 把高价值页面转成 Agent 可复用 skill。
