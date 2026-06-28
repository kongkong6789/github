# 辅助决策升级说明

本项目参考 MiroFish 的五段式思路，但做成适合国内多平台电商的轻量业务决策系统。

## MiroFish 思路映射

| MiroFish 能力 | 本项目落地方式 |
| --- | --- |
| 种子材料输入 | `<A2A_PROJECT_ROOT>/data` 下的库存、销量、广告、利润表 |
| 图谱/环境构建 | `data_agent` 汇总业务数据和字段 |
| 多 Agent 推演 | 库存、财务、风险、广告、调研、决策 Agent 分工 |
| 报告生成 | `decision_agent` 输出结构化辅助决策报告 |
| 深度互动 | `agent-chat-ui` 网页继续追问 |

## 主要决策场景

- SKU 是否需要补货
- 补 500/1000/2000 件哪个更合理
- 广告预算是否需要调整
- 哪些 SKU 有断货或积压风险
- 哪些 SKU 利润和现金流压力较大
- 新品上架前的运营、广告和风险评估

## 本地数据文件

默认读取：

```text
<A2A_PROJECT_ROOT>/data
```

支持：

```text
.csv
.xlsx
.xlsm
```

建议文件命名：

```text
inventory.xlsx / inventory.csv
sales.xlsx / sales.csv
ads.xlsx / ads.csv
profit.xlsx / profit.csv
products.xlsx / products.csv
```

中文文件名也可以包含：

```text
库存
销量
销售
广告
利润
商品
产品
```

## 推荐提问

```text
帮我分析某个 SKU 是否需要补货，给出保守、平衡、激进三个方案
```

```text
读取本地数据，找出库存风险最高的 SKU
```

```text
帮我评估某个 SKU 如果补货 1000 件，现金占用和积压风险如何
```

```text
基于库存、销量、广告、利润数据，给我一份下个月经营风险报告
```
