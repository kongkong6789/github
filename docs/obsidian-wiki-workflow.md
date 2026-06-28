# Obsidian LLM Wiki 使用说明

本项目已经按 Karpathy 的 LLM Wiki 思路加入本地知识库。

## 第一次打开

1. 打开 Obsidian。
2. 选择 `Open folder as vault`。
3. 选择：

```text
<A2A_PROJECT_ROOT>/wiki
```

4. 打开 `index.md` 作为首页。

## 推荐工作流

### 1. 原始资料放 raw

把原始资料放到：

```text
<A2A_PROJECT_ROOT>/raw
```

例如：

- 平台规则摘录
- 供应商资料
- 会议记录
- 历史复盘
- 产品说明
- 竞品分析

原则：`raw` 里放原始材料，尽量不改动。

### 2. 长期知识写 wiki

把整理后的知识写到：

```text
<A2A_PROJECT_ROOT>/wiki
```

推荐目录：

```text
products/        产品档案
suppliers/       供应商
sop/             公司流程和决策规则
platform-rules/  平台规则和合规
ad-strategy/     广告策略
decisions/       历史决策记录
logs/            知识库维护日志
```

### 3. Agent 自动检索

后端已经加入 `knowledge_agent`，可以读取：

```text
<A2A_PROJECT_ROOT>/wiki
```

你可以在前端问：

```text
结合 Obsidian 知识库和本地数据，分析某个 SKU 是否需要补货
```

系统会同时参考：

- `<A2A_PROJECT_ROOT>/data` 下的结构化表格
- `<A2A_PROJECT_ROOT>/wiki` 下的 Markdown 知识页

## 推荐页面类型

### 产品页

```text
products/SKU.md
```

包含：

- 产品卖点
- 经营注意
- 历史问题
- 售后风险
- 商品内容风格
- 相关供应商

### SOP 页

```text
sop/restock-policy.md
```

包含：

- 判断规则
- 阈值
- 人工确认项
- 标准报告格式

### 决策记录

```text
decisions/YYYYMMDD-主题.md
```

包含：

- 当时问题
- 使用数据
- Agent 建议
- 人工最终选择
- 后续结果复盘

## 注意

- 不要把密钥写进 wiki。
- 不要把隐私合同原文直接暴露给不该访问的人。
- Agent 只允许访问 `<A2A_PROJECT_ROOT>/wiki` 和 `<A2A_PROJECT_ROOT>/raw`，不会扫描整台电脑。
