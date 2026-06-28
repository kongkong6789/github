# 复杂表格清洗工作流

本项目已经加入 `data_cleaning_agent`，用于处理后续上传的复杂 Excel、乱表、合并单元格、多空行、重复表头和公式表。

## 推荐流程

1. 把原始表格放到：

```text
<A2A_PROJECT_ROOT>/raw
```

2. 在前端先让 Agent 做表格体检：

```text
请分析 raw/进销存台账_2026-04-30.xlsx 的表结构，识别表头、行列数量、合并单元格、公式和清洗风险
```

3. 再让 Agent 清洗成 CSV：

```text
请把 raw/进销存台账_2026-04-30.xlsx 清洗成标准 CSV，并告诉我输出路径、字段、行列数量和需要人工确认的问题
```

4. 批量处理 raw 目录里的 Excel：

```text
请把 raw 目录里的所有 Excel 表格体检并清洗到 data/cleaned
```

清洗后的文件会输出到：

```text
<A2A_PROJECT_ROOT>/data/cleaned
```

原始文件不会被覆盖，仍保留在：

```text
<A2A_PROJECT_ROOT>/raw
```

## Agent 会做什么

- 自动识别最可能的表头行。
- 丢弃完全空白的行和列。
- 合并单元格会用左上角值填充。
- 重复表头会自动追加后缀，例如 `字段`、`字段_2`。
- 公式列使用 Excel 文件中保存的当前缓存值。
- 输出 UTF-8 CSV，方便后续库存、财务、风险和决策 Agent 使用。

## 什么时候需要人工指定规则

如果表格出现以下情况，前端可以明确告诉 Agent：

```text
这个表第 3 行才是真正表头，请按第 3 行清洗 raw/xxx.xlsx
```

常见需要人工确认的情况：

- 一张表里有多个业务表块。
- 表头分两行或三行。
- 汇总行、备注行混在数据中。
- 单元格颜色代表业务含义。
- 公式没有在 Excel 里重新计算。
- 同一个字段有多个不同名称，例如 SKU、货品编码、商品编码。

## 超大 Excel 处理

如果 Excel 超过 100MB，例如：

```text
<A2A_PROJECT_ROOT>/raw/3、UNOVE出库&库存数据.xlsx
```

系统不会在前端聊天请求里直接解析整张表。原因是这类文件会让后端长时间占用内存和 CPU，前端看起来就像卡死。

当前安全策略：

- Obsidian 入库只生成文件大小、来源和处理建议。
- 表格画像会直接提示“too large for interactive profile”。
- 清洗工具会提示“too large for interactive clean”，不会强行整表转 CSV。

推荐做法：

- 先在 Excel/WPS 里按月份、工作表、仓库、品类或 SKU 范围拆成小文件。
- 优先导出 CSV。
- 单个文件建议控制在 50MB 以下。
- 再把拆分后的文件放进 `<A2A_PROJECT_ROOT>/raw` 让 Agent 清洗和入库。

## 后续决策怎么用

清洗后，可以继续在前端说：

```text
基于 data/cleaned 里的最新进销存 CSV，帮我分析哪些 SKU 有断货风险、哪些 SKU 有积压风险
```

或者：

```text
结合 Obsidian 知识库和 cleaned 数据，生成本周库存风险报告，并保存到 wiki
```

建议把“字段映射规则”和“清洗注意事项”沉淀到 Obsidian，这样以后相同 ERP 或平台导出的乱表可以复用同一套经验。
