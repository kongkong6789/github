---
name: jackyun-erp
description: >
  吉客云 ERP 全功能操作 Skill。通过吉客云开放平台 API 实现自然语言驱动的 ERP 操作。
  当前重点覆盖：销售单查询/创建/审核/驳回/发货/修改物流仓库/操作日志/包裹查询，
  待审核单据统计/候选/批量审核/按条件批量改仓配，
  渠道/仓库/物流/货品智能联动与模糊候选，
  批次库存推荐、批次候选选择与批次引导建单，
  调拨、出入库单、组合装、售后、财务，
  批量导入（从 Excel/CSV 表格智能识别并批量建单），
  库存查询：批次库存查询（含效期）、分仓库存查询(规格模式)。
  使用场景关键词：吉客云、ERP、销售单、寄样单、补发单、普通手工单、创建订单、驳回、批量驳回、
  批量导入、导入表格、Excel建单、查销售单、查仓库、查渠道、查物流、出库单、包裹、发货、
  查库存、批次库存、效期、分仓库存。
---

# 吉客云 ERP Skill

## 概述

完整项目手册、MCP/CLI 运行策略、业务流程、经验沉淀与文档整合规则见：`docs/PROJECT_MANUAL.md`
业务同事使用 SOP 见：`docs/USER_SOP.md`
真实运行反馈记录见：`FEEDBACK_LOG.jsonl`

本 Skill 封装了吉客云开放平台 API，让运营同事通过自然语言完成 ERP 日常操作。

**当前以项目内代码与 2026-04-13 补充规则为准**，已覆盖：
- 销售单全生命周期管理：查询 / 创建 / 审核 / 驳回 / 发货 / 修改仓库物流 / 日志 / 包裹
- 三种销售单类型：普通手工销售单 / 寄样单 / 补发单
- 运营待审核处理：统计 / 候选列表 / 批量审核 / 按筛选条件批量改仓配
- 渠道 / 仓库 / 物流 / 货品智能联动查询与模糊候选
- 批次库存查询、批次推荐、批次手工选择引导
- 出入库单 / 调拨单 / 组合装 / 售后 / 财务
- Excel/CSV 批量导入建单
- 批次库存查询（含效期）/ 分仓库存查询(规格模式)
- 经营报表：货品销售多维分析报表，可按月份/日期范围、渠道、仓库、业务员等筛选并导出所有官方返回字段

## 2026-04-28 最新规则

### 官方文档来源

- 新增接口和字段必须优先读取吉客云官方 CLI 机器可读文档：`docs/jackyun_cli_docs/methods-index.json` 和 `docs/jackyun_cli_docs/{method}.json`
- 也可用 `scripts/fetch_jackyun_openapi_docs.py` 抓取官方 OpenAPI JSON
- 字段不能靠页面展示或经验猜测；官方 JSON 中不存在的字段，不写入请求

### 默认操作人

- 首次创建单据时，必须让用户提供一次本人姓名
- 本地保存到 `data/profile.json`，后续销售单创建人/业务员、调拨单申请人等默认复用该姓名
- 解析时调用 `erp.user.search`，并结合部门档案补齐 `departCode`

### 本地缓存

- 基础资料查询优先读 `data/cache/`：用户、部门、公司、渠道、仓库、物流、货品、数据字典
- 本地没命中或需要刷新时，再调用对应吉客云接口
- 发布包会带上已有的 `data/cache/*.json` 基础资料缓存；不打包 `data/profile.json`、`data/experiences/`、`data/runtime/`
- 可运行 `python scripts/refresh_master_cache.py` 全量刷新仓库、渠道、货品、用户缓存后再发布
- 不允许把按名称/编号查询到的局部结果覆盖全量基础资料缓存；全量缓存只能由全量分页刷新写入
- 仓库、渠道、货品、用户等“查全部/包含关键词/排除关键词”类需求，必须优先走本地全量缓存；若缓存疑似不完整，自动分页刷新后再过滤
- 仓库名称/编号单条解析也不能只信第一页缓存：如果本地仓库缓存疑似只有第一页，或按名称/编号首次未命中，必须自动调用 `erp.warehouse.get` 全量分页刷新后再匹配；销售单、调拨单、出入库单都必须复用 `modules.warehouse.get_warehouse_by_name()` / `get_warehouse_by_code()`
- 基础资料名称匹配会归一化中英文括号、全角/半角字符、空格和大小写，例如 `（UNOVE）` 与 `(UNOVE)` 可匹配
- 成功建单经验写入 `data/experiences/`，供后续模板和流程参考

### 调拨单修正

- 申请公司固定为 `JACKYUN_DEFAULT_APPLICATION_COMPANY_NAME`，默认“依然电商”
- 申请人和部门按默认操作人解析，不再让用户随意填写申请公司/部门
- `reason` 是数据字典值：先调用 `erp.dictionary.page` 查询 `JACKYUN_TRANSFER_REASON_DICT_VALUE`，默认“调拨原因”；若不存在，必须用户明确确认后才允许调用 `erp.dictionary.save` 新增
- 调拨单备注写入官方 `memo` 字段
- 调拨单、销售单、出库单/出库申请单等涉及批次管理的建单，必须优先走对应工作流入口，不要手动拼底层 API 请求体。调拨单必须走 `run_transfer_workflow()`，让 `prepare_transfer_payload()` 自动补货品和批次。
- 调拨单货品明细 `unitName` 固定写入 `Pcs`，不从货品档案带其他单位，也不使用“件”
- 调拨单创建成功后必须用 `erp.allocate.get` 按新单号反查，并把创建后的调拨单信息返回给用户

### 销售单修正

- 官方字段：`buyerMemo` 是买家备注，`sellerMemo` 是备注
- 寄样单/补发单必须写入 `tradeOrderFlags`，不再只依赖备注文字
- 标记 ID 不猜；如实例要求固定 ID，用 `JACKYUN_SAMPLE_ORDER_FLAG_ID` / `JACKYUN_RESEND_ORDER_FLAG_ID` 配置
- 已用真实单据校准标记：样品单 `YR260429001034` 的 `flagIds=1108774772244219136`、`flagNames=样品`；补发单 `YR260428000231` 的 `flagIds=1108772859952365824`、`flagNames=补发`
- 新建销售单必须写入业务员/登记人：首次要求用户提供本人员工姓名，后续复用本地默认操作人；创建请求同时写入 `sellerName` 与 `registerName`
- 寄样单必须由用户提供 `customer_name/customerName`，不能用收件人或渠道名代替客户名称
- 新建销售单模板必须包含 `warehouse_name`；用户可不填，但模板必须提示可提供仓库，系统会按最终仓库自动选择对应物流
- 货品批次不能凭空猜。用户未提供批次时，先按最终仓库查询批次库存并推荐；用户已确认 `batchList`/`batchNo` 后再创建
- 建单前默认执行预检。预检有 `errors` 时必须返回 `needs_input` 和对应模板，禁止调用创建接口，避免在吉客云产生脏数据
- 库存不足默认阻断建单；但如果用户明确要求“先建单，等有库存后再匹配批次发货”，可传 `allow_stock_shortage_create=True` 创建待配批次单。该模式必须强制不自动审核，并提示后续补库存、匹配批次、再审核发货
- 新建成功后必须立刻用 `oms.trade.fullinfoget` 按新单号反查，并把新建单据字段（含仓库、物流、业务员、客户名、标记、货品批次）展示给用户
- 如果用户不知道要提供哪些字段，必须先给 `modules.templates.get_template("sales_order")` 模板

### 历史库存边界

- 当前官方 CLI `methods-index.json` 未发现明确历史库存接口
- `modules.inventory.query_historical_stock()` 只有在配置 `JACKYUN_STOCK_HISTORY_METHOD` 且该方法存在于官方 CLI 目录、字段也在 method JSON 中声明时才允许调用
- 未确认前不能猜接口名或历史时间字段

## 高频工作流

以下场景不应让用户自己思考“该调哪个接口”，而应优先走工作流入口：

| 用户目标 | 建议工作流函数 | 默认行为 |
|------|------|------|
| 销售单建单前体检 | `modules.workflows.run_sales_order_workflow(preflight_only=True)` | 不创建单据，只校验渠道/仓库/物流/业务员/金额/批次，并返回最终解析结果 |
| 新建普通手工销售单 | `modules.workflows.run_sales_order_workflow(order_type="manual")` | 自动解析渠道/仓库/物流；未手填批次时默认按 FIFO 先进先出自动拆分 `batchList`；可选提交审核 |
| 新建寄样单 | `modules.workflows.run_sales_order_workflow(order_type="sample")` | 自动加寄样标记；默认按 FIFO 选批次；如用户要求自选则先给候选；可选提交审核 |
| 新建补发单 | `modules.workflows.run_sales_order_workflow(order_type="resend")` | 自动加补发标记；默认按 FIFO 选批次；如用户要求自选则先给候选；可选提交审核 |
| 处理待审核网店订单 | `modules.workflows.run_pending_sales_order_workflow()` | 支持汇总、列候选、诊断未审核原因、批量审核、批量改仓配 |
| 新建调拨单 | `modules.workflows.run_transfer_workflow()` | 自动串行补全仓库/公司/联系人/申请人/部门/货品/批次；默认按调出仓 FIFO 自动生成 `batchList`；用户明确允许缺货先建时可 `allow_stock_shortage_create=True`，只标记 `isBatch=1` 不伪造批次 |
| 新建出库单 / 入库单 | `modules.workflows.run_stock_doc_workflow()` | 出库单未手填批次时可按库存自动拆分 `batchList`；创建后可选自动审核 |
| 新建入库申请单 / 出库申请单 | `modules.workflows.run_stock_apply_workflow()` | 基于 `erp.storage.stockincreate` / `erp.storage.stockoutcreate`；申请人必须用用户提供的员工姓名；出库申请单未手填批次时默认按 FIFO 自动拆分 `batchList` |
| 按销售单生成模板出库单 | `modules.workflows.run_delivery_note_export_workflow()` | 查询销售单并填充 Excel 模板；默认内置申通仓出库单模板，可配置列映射 |
| 导出仓库库存表 | `modules.workflows.run_inventory_export_workflow()` | 默认中文表头；可选附带批次明细文件 |
| 导出仓库关键词批次库存报表 | `modules.workflows.run_warehouse_keyword_batch_stock_export_workflow()` | 按用户提供的仓库包含/排除关键词筛选仓库，逐仓导出批次库存，可选补近30天销量 |
| 导出货品销售多维分析报表 | `modules.workflows.run_goods_sales_analysis_workflow()` | 基于 `birc.report.needauth.goodsMultiDimensionalAnalysis`，支持月份/日期范围、渠道名称自动转 `shopIds`，默认按渠道+货品汇总并导出所有官方返回字段 |
| 渠道销售数量/金额汇总 | `modules.workflows.run_channel_sales_summary_workflow()` | 优先用销售多维分析报表下推 `shopIds`/发货时间/状态/维度；如多维报表返回 0 且配置了吉智BI自定义报表 `reportId`，自动兜底调用 `udr.openapi.userdefinedreport`；未配置时必须提示不可上线空结果 |
| 查询仓库关键词 | `modules.warehouse.search_warehouses_by_keywords()` | 基于全量仓库缓存/API，支持包含关键词、排除关键词和“除……关键词”语义排除 |
| 新建组合装 / 售后退款 / 退换货 | `modules.workflows.run_misc_workflow()` | 作为高频业务快捷入口 |

工作流层原则：
- 优先调用现有模块能力，不重写底层接口逻辑
- 用户缺字段时先返回“缺什么、候选是什么、下一步做什么”
- 高频固定场景也必须先经过工作流预检；预检通过才可快速建单。批量建单、陌生渠道/仓库、用户不确定字段时，先跑 `preflight_only=True` 或 `batch_create_orders(..., dry_run=True)`
- 销售单、调拨单、出入库单如果校验失败，工作流要返回 `needs_input`、缺失项和模板，不能让底层异常变成“猜参数后重试创建”
- 销售单涉及业务员、调拨单涉及申请人时，必须先确认是创建人本人，再写入单据
- 销售单创建后必须反查完整单据并展示给用户，不只返回创建接口的单号
- 销售单查询默认使用 `oms.trade.fullinfoget`，默认 `fields` 必须包含 `DEFAULT_GOODS_DETAIL_FIELDS` 中维护的完整 `goodsDetail.*` 货品明细字段；新增货品明细字段时只扩展该列表
- 处理网店下载到 ERP 后未自动审核的订单时，优先执行 `run_pending_sales_order_workflow(action="diagnose")`，按缺货、仓库/物流异常、退款/售后风险、无效货品、收件信息缺失等原因分组，再决定修改、审核、驳回/取消或等待库存
- 调拨单优先自动补全仓库、公司、联系人、申请人、部门、货品、批次，减少人工来回确认；禁止绕过 `run_transfer_workflow()` 直接手动拼 `erp.allocate.create`，否则会绕过批次选择、字段校验、反查展示和经验记录
- 入库/出库申请单不要用旧的普通出入库单接口替代；申请单创建必须走 `run_stock_apply_workflow()`，并把用户提供的员工姓名写入 `applyUserName`
- 写操作完成后，要返回单号、关键字段、后续是否还需人工处理
- 当用户基于吉客云完成新的稳定工作流、新模板或新报表需求后，默认建议单独打包成新 skill，避免当前 `jackyun-erp` 后续由 IT 更新、卸载重装时覆盖用户自定义内容。只有明确属于通用 ERP 基础能力，且用户确认要并入当前 skill 时，才集成进 `jackyun-erp`

### 给其他 Agent / OpenClaw / Work Buddy 的快速入口

如果员工在其他类产品里使用本 Skill，不要让模型反复临时写签名、分页、批次、字段映射代码。先调用：

```python
from modules.workflows import get_workflow_catalog, run_fast_workflow

get_workflow_catalog()
run_fast_workflow("channel_sales_summary", month="2026-05", shop_names=["渠道A"], dimension="channel_goods")
```

当前稳定 action 包括：`sales_order_create`、`transfer_create`、`stock_apply_create`、`channel_sales_summary`、`goods_sales_analysis`、`inventory_export`。

渠道销售汇总示例：

```python
run_fast_workflow(
    "channel_sales_summary",
    period="昨天",
    channel_include_keyword="分销组",
    dimension="channel",
    trade_status="发货在途或者已完成",
)
```

该工作流先用本地全量渠道缓存/API 找到匹配渠道，再把 `shopIds`、`filterTimeType=2` 发货时间、`tradeStatus`、`summaryType` 下推给报表接口；不要先拉全部销售单再本地清洗。

如果 `birc.report.needauth.goodsMultiDimensionalAnalysis` 返回 0，但 ERP 前台确认有数据，不能直接把空表交付给业务同事。应优先检查当前 AppKey 的报表数据权限；同时可以让 IT 在吉智BI建立并开放一个自定义报表，然后配置：

```bash
export JACKYUN_CHANNEL_SALES_UDR_REPORT_ID="吉智BI自定义报表ID"
```

或调用时传：

```python
run_fast_workflow(
    "channel_sales_summary",
    period="昨天",
    channel_include_keyword="分销组",
    dimension="channel",
    trade_status="发货在途或者已完成",
    udr_report_id="159",
)
```

`udr.openapi.userdefinedreport` 必须传 `reportId`，且该报表必须在吉智BI侧支持开放平台查询；skill 不允许猜测 reportId。

## 经验沉淀机制

- 用户指出创建错误、查询漏查、批次选择错误或字段写错时，必须先复盘原因，再调用 `modules.workflows.record_workflow_correction()` 记录 `issue`、`root_cause`、`prevention_rule`、`corrected_fields`
- 纠错记录写入 `data/experiences/corrections.jsonl`，销售单预检会展示最近同类纠错提示；如果纠正了常用仓库、物流、渠道、业务员、客户或批次策略，也会更新本地偏好
- 纠错后必须重新跑预检；预检通过前禁止创建单据

为了让 skill 在真实使用后越来越智能，但又不把正式规则写乱，经验记录分三层：

- `FEEDBACK_LOG.jsonl`
  原始使用日志。高频工作流执行后，会自动追加一条机器可读记录；现在会额外记录 `input_summary`、`steps`、`pain_points`、`reuse_hints`，用于下次快速复用。
- `docs/PROJECT_MANUAL.md`
  完整中文项目手册。记录稳定经验、处理套路、MCP/CLI 运行策略、业务规则和文档整合规则。

读取顺序：
1. 先按 `SKILL.md` 的正式规则执行
2. 再参考 `docs/PROJECT_MANUAL.md` 的稳定经验和高频处理套路
3. 如需回看最近真实使用情况，再查 `FEEDBACK_LOG.jsonl`

重要规则：
- 不要把单次用户要求直接写进 `SKILL.md`
- 先写入 `FEEDBACK_LOG.jsonl`
- 同类问题重复出现 2 到 3 次，或用户明确要求记忆，再整理到 `docs/PROJECT_MANUAL.md`
- 只有正式确认后的规则，才同步进 `SKILL.md`
- 新工作流沉淀前必须先问清复用边界，默认顺序如下：
  - 优先单独打包成新 skill：适合固定模板、固定部门、固定供应商/客户、固定报表或外部交付物，能避免 `jackyun-erp` 升级时丢失用户自定义内容
  - 少数情况下归入当前 `jackyun-erp`：仅适合通用 ERP 基础能力，依赖销售单/库存/仓库/货品等共享模块，且用户明确确认要并入

## 凭证维护规则

- 吉客云开放平台使用的 `key` 和 `secret` 存在定期失效风险，按当前规则需要每 3 个月检查一次是否已失效
- 如果出现签名失败、鉴权失败、接口突然整体不可用，应优先怀疑 `key` / `secret` 已过期
- 失效后需要联系依然集团 IT 部重新获取并更新
- 这类凭证更新属于运维维护事项，不应由普通业务同事自行处理

## 已实现能力

### 总体原则

- 能查询就先查询，不直接猜测渠道、仓库、物流、货品
- 名称不精确时先给候选，不直接替用户拍板
- 缺字段时必须补齐，不完整数据不创建单据
- 高风险写操作必须二次确认
- 不默认执行删除、取消、覆盖式危险操作

### 一、销售单（核心）— 8 个 API

| 能力 | API 方法 | 对应函数 | 权限 |
|------|---------|---------|------|
| 销售单查询 | `oms.trade.fullinfoget` | `query_trades()` / `query_trade_by_no()` | 全员 |
| 销售单统计 | `oms.trade.countget` | `count_trades()` | 全员 |
| 创建销售单 | `oms.trade.ordercreate` | `create_trade()` / `create_sample_order()` / `create_manual_order()` | 全员 |
| 驳回审核 | `oms.open.trade.audit.reject` | `reject_trade()` | 全员 |
| 完成发货 | `oms.trade.order.completeDelivery` | `complete_delivery()` | 全员 |
| 修改仓库/物流 | `oms.trade.order.batchUpdateLogisticWarehouse` | `update_logistics_warehouse()` | 全员 |
| 操作日志 | `oms.trade.orderloglist` | `query_trade_logs()` | 全员 |
| 包裹查询 | `oms.trade.package.querylist` | `query_trade_packages()` | 全员 |

**审批流程说明**：
- 审核：运营同事负责提交审核
- 寄样单：提交审核之后，会进入审批流，流转后自动递交给仓库
- 普通手工单 / 补发单：提交审核之后，会进入复核，需联系财务FBP复核，复核后递交仓库
- 网店订单：提交审核之后，无需复核，可直接递交仓库

> ⚠️ **当前 skill 不自动调用复核接口**。业务上仍以财务 / FBP 人工复核为准。

### 二、批量操作

| 能力 | 对应函数 | 说明 |
|------|---------|------|
| **Excel/CSV 批量导入建单** | `batch_import.batch_create_orders()` | 读取表格→智能列映射→逐行校验→自动匹配仓库物流→批量创建 |
| **批量驳回** | `sales_order.batch_reject_trades()` | 传入多个单号，逐个驳回 |

### 三、其他模块 — 4 个 API

| 能力 | API 方法 | 对应函数 |
|------|---------|---------|
| 仓库查询 | `erp.warehouse.get` | `modules/warehouse.py` |
| 渠道查询 | `erp.sales.get` | `modules/channel.py`（实时接口查询，当前约 645 个渠道） |
| 物流档案 | `erp.logistic.get` | `modules/logistics.py`（仓库→物流匹配） |
| 出库单查询 | `erp.storage.goodsdocout.v2` | `modules/stock_doc.py` |

### YR 销售单号查询物流单号

当用户提供 `YR` 开头的销售单号，并明确要查“物流单号/快递单号”时，必须走下面两步，不能只查销售单详情：

1. 第一步：调用 `oms.trade.fullinfoget`
   - 入参：`tradeNo=销售单号`
   - 作用：确认销售单存在，拿到 `billNo`
   - 注意：这个接口不返回物流单号，只会返回 `logisticName` / `logisticCode`
2. 第二步：调用 `erp.storage.goodsdocout.v2`
   - 入参：`billNo=销售单号`
   - 作用：查询对应出库单
   - 关键字段：`logisticNo`（物流单号）、`logisticName`（物流公司）

完整链路：

```text
销售单号(tradeNo / YR...)
  -> oms.trade.fullinfoget
  -> 确认单据存在，拿到 billNo（通常 billNo = tradeNo）
  -> erp.storage.goodsdocout.v2
  -> 返回 logisticNo / logisticName
```

### 四、库存查询 — 2 个 API

| 能力 | API 方法 | 对应函数 | 说明 |
|------|---------|---------|------|
| 批次库存查询（含效期） | `erp.batchstockquantity.get` | `query_batch_stock_quantity()` / `query_batch_stock_formatted()` | 查询某仓库物料的批次、生产日期、到期日期、质保期等 |
| 分仓库存查询(规格模式) | `erp-stock.stock.skulist` | `query_sku_stock_list()` | 按规格维度查询各仓库库存（必须传货品+规格，最多1000规格） |

**推荐使用 `query_batch_stock_formatted()`**：自动转换时间戳为可读日期，使用正确字段名。

### 五、自动化能力

#### 三种销售单类型

用户说"创建销售单"/"新建订单"时，**必须先确认类型**：

| 类型 | 金额 | 网店订单号格式 | 标记 | sellPrice | payStatus | 对应函数 |
|------|------|---------------|------|-----------|-----------|---------|
| **普通手工销售单** | 正常填写；赠品可为0 | yyyyMMddHHmmss（无后缀） | 无 | **必填** | "0"（待付款） | `create_manual_order()` |
| **寄样单** | 一般为0 | yyyyMMddHHmmss + JY | 【寄样】 | 默认0 | "9" | `create_sample_order(JY)` |
| **补发单** | 一般为0 | yyyyMMddHHmmss + BF | 【补发】 | 默认0 | "9" | `create_sample_order(BF)` |

**判断规则**：
- 用户说"寄样"/"寄样单" → JY
- 用户说"补发"/"补发单" → BF
- 用户说"手工单"/"普通销售单"/未指定且需要填写金额 → PT
- **如果用户只说"创建销售单"不指定类型，必须先询问是哪种类型**

创建寄样/补发单时，系统自动完成以下链路（无需用户手动指定仓库和物流）：

```
渠道名 → erp.sales.get    → 获取默认仓库编号 + 公司ID
       → erp.warehouse.get → 获取仓库ID + 校验仓库与渠道属于同一公司
       → 仓库名关键词匹配  → 按规则选择默认物流（见下表）
       → erp.logistic.get  → 验证物流在该仓库可用列表中
       → 自动填充 warehouseName / logisticName
       → sellerMemo 添加【寄样】/【补发】前缀
       → goodsFlagName 设为【寄样】/【补发】
```

#### 仓库→物流 默认匹配规则

| 仓库名包含 | 默认物流 |
|-----------|---------|
| **麦歌** | 麦歌中通 |
| **宝鼎** | 宝鼎中通 |
| **韩国申通** | 依然物流 |
| **韩国韵达** | 韩国韵达-韵达国际 |

> 匹配逻辑：按上表顺序检查仓库名是否包含关键词，命中则使用对应物流。
> 未命中任何规则时，取该仓库可用物流列表中的第一个。
> 上表右侧是物流档案别名/名称，创建销售单时按最终仓库自动写入对应 `logisticName`。
> 规则定义在 `sales_order.py` 的 `WAREHOUSE_LOGISTICS_RULES` 常量中，可随时扩展。

## 当前能力状态

以下能力当前已接入并可直接使用：

| 模块 | 说明 | 文件 |
|------|------|------|
| 销售单 | 查询 / 创建 / 审核 / 驳回 / 发货 / 改仓配 / 日志 / 包裹 | `modules/sales_order.py` |
| 批量导入 | Excel/CSV 预览与建单 | `modules/batch_import.py` |
| 渠道 | 查询 / 模糊候选 / 渠道→仓库解析 | `modules/channel.py` |
| 仓库 | 查询 / 公司校验 | `modules/warehouse.py` |
| 物流 | 仓库→可用物流匹配 | `modules/logistics.py` |
| 货品 | 查询 / 模糊候选 | `modules/goods.py` |
| 出入库单 | 查询 / 创建 / 审核 | `modules/stock_doc.py` |
| 调拨单 | 查询 / 创建 / 完成 / 关闭 | `modules/transfer.py` |
| 组合装 / 组装拆卸 | 查询 / 创建 / 关闭 | `modules/combined.py` |
| 售后 | 退款 / 退换货 / 争议 / 补发等 | `modules/aftersales.py` |
| 财务 | `fin.*` / `fin-fbs.*` 统一入口 | `modules/finance.py` |
| 网店订单 | 查询 / 物流提取 | `modules/shop_order.py` |

以下内容不建议作为当前 skill 主能力依赖：

- `oms.trade.order.reAudit`
  公开接口可查到，但当前业务流程仍以财务 / FBP 人工复核为准
- 销售单删除、取消等高风险操作
  未纳入默认安全操作链路

## 权限控制

| 功能 | 运营同事 | 财务同事 |
|------|---------|---------|
| 查询类（销售单/仓库/渠道/物流/出库单/日志/包裹） | ✅ | ✅ |
| 创建销售单（含批量导入） | ✅ | ✅ |
| **提交审核** | ✅ | ✅ |
| **审核（确认单据正确）** | ✅ | ❌ |
| **复核（财务复核权限）** | ❌ | ✅ |
| 驳回审核（含批量驳回） | ✅ | ✅ |
| 修改仓库/物流 | ✅ | ✅ |
| 完成发货 | ✅ | ✅ |

**审批流程说明**：
- 审核：运营同事负责，确认单据信息是否正确
- 复核：财务同事负责，需财务复核权限，**补发单需联系财务FBP审核**
- 寄样单：提交审核之后，会有审批流流转，流转后会自动递交给仓库
- 补发单：提交审核之后，需联系财务FBP复核，复核后自动递交仓库

> ⚠️ **复核功能已禁用**（reAudit API 已取消订阅），创建后请在吉客云网页端手动复核。

## 交互规范

### 查询操作 — 直接执行

用户说"查一下 YR260402000932"→ 直接调用 `query_trade_by_no()` → 返回结果。

### 写操作 — 二次确认

所有创建、驳回、发货等写操作，**必须先展示操作汇总，等用户确认后再执行**。

### 批量导入 — 预览→确认→执行

1. 用户上传表格文件
2. 先调用 `batch_create_orders(file_path, dry_run=True)` **预览模式**
3. 预览模式会执行建单前体检，提前校验渠道、仓库、物流、业务员/登记人、客户名称、金额和批次库存
4. 展示列映射结果 + 校验汇总 + 订单预览 + 预检阻断原因
5. 等用户确认后，再调用 `batch_create_orders(file_path, dry_run=False)` 实际创建；如遇接口限流，再显式设置 `create_interval`
6. 展示创建结果报告（成功/失败/跳过明细）
7. 创建后请在吉客云网页端手动复核

### 创建销售单 — 类型确认（必须先确认）

用户说"创建销售单"/"新建订单"时，**必须先确认类型**：
1. **普通手工销售单**（需要填写单价/金额，网店订单号为 yyyyMMddHHmmss 无后缀）
2. **寄样单**（金额一般为0，网店订单号后缀 JY，有【寄样】标记）
3. **补发单**（金额一般为0，网店订单号后缀 BF，有【补发】标记）
4. **是否提交审核**（寄样提交后进入审批流；普通手工单 / 补发单提交后进入复核；网店订单提交后无需复核，直接递交仓库）

如果用户已明确指定类型（如"创建寄样单"），则无需再确认。

### 高频工作流触发建议

当用户表达的是业务目标，而不是接口名时，优先按以下方式理解：

- “帮我新建一个手工单/寄样单/补发单”
  先走 `run_sales_order_workflow()`
- “帮我看看今天待审核有多少单 / 直接批量审核”
  先走 `run_pending_sales_order_workflow()`
- “帮我新建一个同主体/跨公司调拨”
  先走 `run_transfer_workflow()`
- “帮我建一个出库单 / 入库单”
  先走 `run_stock_doc_workflow()`
- “帮我创建退款 / 退换货 / 组合装”
  先走 `run_misc_workflow()`

只有当用户明确要求某个底层接口，或者工作流无法覆盖时，才直接使用底层模块函数。
如果底层模块函数会创建单据，也应先确认对应工作流确实无法覆盖，并在最终反馈中说明为什么没有使用工作流。

### 创建寄样/补发销售单 — 多轮对话引导

需要用户提供 **5 项必填信息**：

1. **渠道名称** (`shopName`) — 从实时渠道列表中匹配
2. **收件人** (`receiverName`) + **手机号** (`mobile`)
3. **地址** — 省(`state`) 市(`city`) 区(`district`) + 详细地址(`address`)
4. **货品明细** — 货品编号(`goodsNo`) + 数量(`sellCount`)
5. **业务员姓名** (`sellerName`) — 必须确认是创建人本人员工姓名，不能代填他人；创建时同步写入 `registerName`
6. 如涉及批次管理，可先查询批次库存，再由用户选择批次，或采用系统推荐批次
7. **是否提交审核** — 这会决定是仅创建单据，还是立即提交到后续流程

**以下字段自动处理，无需用户提供**：
- `onlineTradeNo`: 寄样=`yyyyMMddHHmmssJY`, 补发=`yyyyMMddHHmmssBF`
- `tradeTime`: 当前时间
- `warehouseName`: 自动从渠道默认仓库获取
- `logisticName`: 自动从仓库可用物流获取
- `sellerMemo`: 自动添加【寄样】/【补发】前缀
- `goodsFlagName`: 自动设为【寄样】/【补发】
- 寄样单固定值: `tradeType="1"`, `totalFee="0"`, `payment="0"`, `payStatus="9"`, `chargeType="1"`, `chargeCurrency="人民币"`

### 创建普通手工销售单 — 多轮对话引导

需要用户提供 **6 项必填信息**：

1. **渠道名称** (`shopName`) — 从实时渠道列表中匹配
2. **收件人** (`receiverName`) + **手机号** (`mobile`)
3. **地址** — 省(`state`) 市(`city`) 区(`district`) + 详细地址(`address`)
4. **货品明细** — 货品编号(`goodsNo`) + 数量(`sellCount`) + **单价(`sellPrice`)** + 金额(`sellTotal`)
5. **业务员姓名** (`sellerName`) — 必须确认是创建人本人员工姓名，不能代填他人；创建时同步写入 `registerName`
6. 如涉及批次管理，可先查询批次库存；若用户未手填批次且总可用库存足够，系统默认按 FIFO 先进先出自动拆分多个批次生成 `batchList`
7. **是否提交审核** — 提交后进入复核；如是网店订单则无需复核，直接递交仓库
8. **单价必填** — 普通手工单与寄样/补发单最大的区别是 `sellPrice` 默认不能为0
9. **赠品例外** — 如该货品是赠品，需显式传 `isGift=1`，此时允许 `sellPrice=0`、`sellTotal=0`
10. **金额校验** — `sellTotal` 缺失时按 `sellPrice * sellCount` 自动回算；已传金额时必须与数量、单价一致

**以下字段自动处理，无需用户提供**：
- `onlineTradeNo`: `yyyyMMddHHmmss`（无后缀）
- `tradeTime`: 当前时间
- `warehouseName`: 自动从渠道默认仓库获取
- `logisticName`: 自动从仓库可用物流获取
- `totalFee`/`payment`: 由明细 sellTotal 自动汇总
- `payStatus`: "0"（待付款）
- 无寄样/补发标记，sellerMemo 不加前缀

## 使用示例

### 查询销售单

```
用户：查一下 YR260402000932
Skill：调用 modules/sales_order.query_trade_by_no("YR260402000932")
       返回：单号、渠道、状态、仓库、物流、收件人、货品明细等
```

### 查询 YR 销售单的物流单号

```
用户：查一下 YR260413002043 的物流单号
Skill：先调用 modules/sales_order.query_trade_logistics("YR260413002043")
       第一步：oms.trade.fullinfoget，确认销售单存在，拿到 billNo
       第二步：erp.storage.goodsdocout.v2，按 billNo 查询出库单
       返回：物流公司、物流单号、出库单号
```

### 查询仓库名称包含/排除关键词

```
用户：查询所有名称包含分销组的仓库，有“除分销组”的不要

Skill：调用 modules.warehouse.search_warehouses_by_keywords(
         include_keyword="分销组",
         exclude_keywords=["除分销组"]
       )

       规则：
       - 优先使用 data/cache/warehouses.json 全量缓存
       - 如缓存条数异常偏少，自动分页调用 erp.warehouse.get 刷新全量缓存
       - 排除名称里包含“除分销组”以及“除外贸组和分销组”这类否定语境的仓库
       - 返回仓库名称、仓库编码、所属公司、状态
```

### 按销售单生成 Excel 模板出库单

```
用户：帮我生成申通仓出库单 YR260429001022

Skill：调用 modules.workflows.run_delivery_note_export_workflow(
         trade_no="YR260429001022"
       )

       工作流：
       1. 调用 oms.trade.fullinfoget 查询销售单，fields 必须包含 goodsDetail.*
       2. 读取 Excel 模板 templates/shentong_delivery_note.xlsx
       3. F5 写入 “销售单/采购单：YR260429001022”，保留模板原有文字
       4. 明细行默认从第 10 行开始：
          - A列：序号
          - B列：条码；无条码时用 goodsNo
          - E列：产品品名
          - F列：数量
          - C/D/I列保持空白
       5. F列汇总公式写入 `=SUM(F10:F最后明细行)`；D列不写汇总
       6. 货品超过模板行数时自动新增明细行
       7. 文件名使用原始销售单号，不从 F5 展示文字反推
```

可复用原则：

- 这不是只服务申通仓。申通仓只是内置默认模板；其他仓库模板可通过 `config` 调整单号单元格、明细起止行、列映射、汇总列和留空列。
- 写 Excel 合并单元格时，必须写合并区域左上角。
- 不要默认填客户名、联系人、电话、地址、出入库仓库、包装规格、总箱数；这些是否填写必须由模板配置或用户明确要求决定。

### 查询今天的销售单数量

```
用户：今天有多少销售单？
Skill：调用 modules/sales_order.count_trades(start_trade_time="今天00:00", end_trade_time="今天23:59")
       返回：总数
```

### 创建寄样单（单个，自动匹配仓库物流）

```
用户：帮我创建一个寄样单

Skill：好的，请提供以下信息：
       1. 销售渠道名称
       2. 收件人姓名和手机号
       3. 收件地址（含省市区）
       4. 货品编号和数量

用户：渠道是直播组小红书NUDARA海外旗舰店，寄给张三 13800138000
      杭州市萧山区XX路XX号，货品 8809874701554 一件

Skill：确认创建寄样单：
       ┌──────────────────────────────────────────┐
       │ 渠道: 直播组小红书NUDARA海外旗舰店         │
       │ 仓库: 正品-韩国韵达公共仓（自动匹配）       │
       │ 物流: 韩国韵达-韵达国际（自动匹配）         │
       │ 收件: 张三 13800138000                    │
       │ 地址: 浙江省杭州市萧山区 XX路XX号          │
       │ 货品: 8809874701554 × 1                   │
       │ 金额: ¥0（寄样）                          │
       │ 标记: 【寄样】                             │
       └──────────────────────────────────────────┘
       确认提交？

用户：确认

Skill：调用 modules/sales_order.create_sample_order(...)
       ✅ 寄样单创建成功！
       单号: YR260402001486
       仓库: 正品-韩国韵达公共仓
       物流: 韩国韵达-韵达国际
       状态: 待审核
       下一步: 运营审核 → 财务复核 → 审批流流转后自动递交仓库
```

### 创建普通手工销售单，自动匹配仓库物流）

```
用户：帮我创建一个销售单

Skill：请问是哪种类型的销售单？
       1. 普通手工销售单（需要填写单价/金额）
       2. 寄样单（金额一般为0，有寄样标记）
       3. 补发单（金额一般为0，有补发标记）

用户：普通手工销售单

Skill：好的，请提供以下信息：
       1. 销售渠道名称
       2. 收件人姓名和手机号
       3. 收件地址（含省市区）
       4. 货品编号、数量和单价（⚠️ 普通手工单必须填写单价）

用户：渠道是芙莉美娜抖音旗舰店，寄给张三 13800138000
      杭州市萧山区XX路XX号，货品 8809874701554 一件 单价99元

Skill：确认创建普通手工销售单：
       ┌──────────────────────────────────────────┐
       │ 渠道: 芙莉美娜抖音旗舰店                    │
       │ 仓库: 正品-韩国韵达公共仓（自动匹配）       │
       │ 物流: 韩国韵达-韵达国际（自动匹配）         │
       │ 收件: 张三 13800138000                    │
       │ 地址: 浙江省杭州市萧山区 XX路XX号          │
       │ 货品: 8809874701554 × 1 单价 ¥99.00      │
       │ 金额: ¥99.00                             │
       │ 类型: 普通手工销售单（无标记）              │
       └──────────────────────────────────────────┘
       确认提交？

用户：确认

Skill：调用 modules/sales_order.create_manual_order(...)
       ✅ 普通手工销售单创建成功！
       单号: YR260409001234
       仓库: 正品-韩国韵达公共仓
       物流: 韩国韵达-韵达国际
       金额: ¥99.00（待付款）
       状态: 待审核
       下一步: 运营审核 → 财务复核
```

### 查询批次库存（含效期）

```
用户：查一下正品仓库货品 A00011289 的批次库存和效期

Skill：调用 modules/inventory.query_batch_stock_formatted(
         warehouse_code="仓库编码",
         goods_no="A00011289",
         is_batch_management=1
       )

       | 批次编号 | 当前库存 | 可用 | 锁定 | 生产日期 | 到期日期 | 质保期 |
       |----------|----------|------|------|----------|----------|--------|
       | CS000212 | 10 | 10 | 0 | 2020-11-10 | 2022-01-01 | 1年 |

注意：推荐使用 query_batch_stock_formatted()，它会自动：
- 转换毫秒时间戳为 YYYY-MM-DD 格式日期
- 使用正确的字段名（currentQuantity 而非错误的 stockQty）
- 返回格式化后的易读数据

### 批次推荐与用户自选

如用户创建销售单时涉及批次管理，Skill 应按以下顺序处理：

1. 先调用 `modules.inventory.recommend_batches(...)`
2. 返回该货品在目标仓库下的可用批次候选
3. 默认按 `fifo` 先进先出规则推荐：
   - 先按用户要求筛选批次，例如指定批次、排除批次、效期要求、生产日期范围
   - 再优先使用生产日期更早的批次
   - 单批次不足时自动拆分多个批次
4. 如用户不接受系统推荐，展示候选批次并让用户手动选择
5. 用户确认批次后，可把 `batchNo` 或官方 `batchList` 写入销售单货品明细

推荐调用：

```python
from modules.inventory import recommend_batches

recommend_batches(
    warehouse_code="WH001",
    goods_no="G001",
    required_quantity=3,
    strategy="fifo",
    min_remaining_valid_days=90,
)
```

说明：

- 销售单明细现在支持透传 `batchNo` 和 `batchList`
- 如果单个批次不足但多个批次合计足够，销售单创建会自动拆分多个批次生成 `batchList`
- 调拨单明细除 `batchNo` 外，也支持官方 `batchList` 结构；调拨 workflow 会按批次库存自动生成批次分配
- 出库单在未手填批次时，也会按仓库批次库存自动拆分多个批次生成 `batchList`
- 只有总可用库存不足时才应提示缺货，不能因为单个批次不足就报缺货
```

### 查询分仓库存(规格模式)

```
用户：查一下正品仓库货品 A00011289 各规格的库存情况

Skill：调用 modules/inventory.query_sku_stock_list(
         warehouse_code="仓库编码",
         goods_no="A00011289"
       )

       | 仓库 | 当前库存 | 可用库存 | 锁定待发 | 采购在途 | 可用量 | 成本价 |

### 导出仓库库存表

```python
from modules.workflows import run_inventory_export_workflow
```

示例：导出某仓库库存表，默认中文表头

```python
run_inventory_export_workflow(
    output_path="C:/Users/YiRan/Desktop/WH001库存.xlsx",
    warehouse_code="WH001",
    include_batch_details=False,
)
```

示例：导出某仓库库存表，并额外附带批次明细文件

```python
run_inventory_export_workflow(
    output_path="C:/Users/YiRan/Desktop/WH001库存.xlsx",
    warehouse_code="WH001",
    include_batch_details=True,
)
```

导出规则：

- 主表统一基于官方 `erp.stockquantity.get`
- 默认中文表头，适合同事直接打开查看
- 默认核心字段包括：仓库编码、仓库名称、货品编号、货品名称、规格名称、条码、单位、当前库存、可用库存、锁定库存、渠道预留库存、调拨在途数量、采购在途数量、订购数量、入库申请数量、出库申请数量、残次品数量、次品可用库存、成本价
- 如果 `include_batch_details=True`，会额外导出一份批次明细文件，不把单头库存和批次库存混在同一张表中
- 批次明细文件基于官方 `erp.batchstockquantity.get`
       |------|----------|----------|----------|----------|--------|--------|
       | 正品仓 | 100 | 88 | 12 | 50 | 88 | ¥25.00 |
```

### 导出仓库关键词批次库存报表

```
用户：导出所有名称包含分销组的仓库批次库存，有“除分销组”的不要。
     字段要：仓库、批次、货品编号、货品名称、库存数量、可用库存、
     生产日期、到期日期、剩余有效天数、月末成本、含税成本、库存金额、近30天销量。

Skill：调用 modules.workflows.run_warehouse_keyword_batch_stock_export_workflow(
         output_path="仓库批次库存.xlsx",
         include_keyword="分销组",
         exclude_keywords=["除分销组"],
         fill_missing_sales_zero=True
       )

       工作流：
       1. 调用 modules.warehouse.search_warehouses_by_keywords(include_keyword, exclude_keywords)
          - 优先用 data/cache/warehouses.json 全量缓存
          - 缓存异常偏少时自动分页刷新
          - 排除“除X”“除A和X”等否定语境
       2. 对每个命中仓库调用 erp.batchstockquantity.get 拉取批次库存和效期
       3. 通过 erp-stock.stock.skulist 的 threedayQuantity 尝试补近30天销量
       4. 若命中仓库为虚拟/调拨仓，销量接口可能为空；按用户确认口径填 0 或留空
       5. 月末成本、含税成本、库存金额只在接口返回成本字段时填；否则留空，不猜
       6. 导出 Excel/CSV，并返回行数、仓库数、文件路径、踩坑提示
```

默认导出字段：

| 字段 |
|---|
| 仓库 |
| 批次 |
| 货品编号 |
| 货品名称 |
| 库存数量 |
| 可用库存 |
| 生产日期 |
| 到期日期 |
| 剩余有效天数 |
| 月末成本 |
| 含税成本 |
| 库存金额 |
| 近30天销量 |

> 学习到的通用规则：这不是“只查分销组”的固定功能，而是仓库关键词批次库存报表模板。仓库关键词、排除关键词、销量为空填 0 还是留空，都必须来自用户需求或用户确认。分销组案例仅作为示例：分销组仓库常是调拨仓/虚拟仓，不直接对外销售；`erp-stock.stock.skulist.threedayQuantity`、销售多维分析报表等可能返回空，用户确认后近30天销量可填 0。

### 货品销售多维分析报表

用于查询某个时间段、某些渠道下所有货品的销售额、销量、发货量、退货量、毛利等经营指标。

官方接口：`birc.report.needauth.goodsMultiDimensionalAnalysis`

兜底接口：`udr.openapi.userdefinedreport`（吉智BI自定义报表，必须提供 `reportId`）

```python
from modules.workflows import run_goods_sales_analysis_workflow

run_goods_sales_analysis_workflow(
    output_path="C:/Users/YiRan/Desktop/5月渠道货品销售分析.xlsx",
    month="2026-05",
    shop_names=["渠道A", "渠道B"],
    summary_types="channel,goods",
    filter_time_type=2,
)
```

规则：

- `month="YYYY-MM"` 会按官方月统计格式传 `startTime=endTime=YYYY-MM`、`timeType=2`；也可以直接传 `start_time` / `end_time`
- 用户提供渠道名称时，先通过 `erp.sales.get` / 本地渠道缓存解析 `channelId`，再写入官方 `shopIds`
- 默认 `summary_types="channel,goods"`，适合按渠道+货品看销售额和销量；如需按规格、时间、仓库、业务员等维度，必须让用户明确汇总维度
- 默认 `filter_time_type=2`，按发货时间统计；用户要求下单时间或付款时间时分别传 1 或 3
- 如果接口返回空，但 ERP 前台确认有数据，优先核对当前 Skill 使用的 AppKey 是否就是已订阅且有数据权限的应用；订阅接口不等于所有 AppKey 都有同一份报表数据权限。
- 多维报表持续返回 0 时，渠道销售汇总工作流可使用吉智BI自定义报表兜底：配置 `JACKYUN_CHANNEL_SALES_UDR_REPORT_ID` 或传入 `udr_report_id`。未提供 `reportId` 时，必须明确提示“缺少吉智BI自定义报表 reportId”，不能把 0 行结果当成上线可用结果。
- 导出字段来自官方 CLI JSON 的 response schema，包含销售量、销售额、货品金额、发货量、退货量、退款金额、成本、毛利、毛利率、品牌、分类、渠道、仓库、物流、地区等所有官方返回字段
- 该接口是报表查询，不用于替代销售单明细查询；需要单据字段时仍使用 `oms.trade.fullinfoget`

### 批量导入建单（从 Excel/CSV）

```
用户：帮我从这个表格批量创建寄样单 [上传 sample_orders.xlsx]

Skill：收到表格，先进行预览...
       调用 batch_import.batch_create_orders("sample_orders.xlsx", dry_run=True)

       📋 批量导入预览（未实际创建）
       ┌──────────────────────────────────────────┐
       │ 表格总行数: 15                             │
       │ 合并后订单数: 10（同收件人多货品自动合并）    │
       │ 校验跳过: 2 行（手机号格式错误）             │
       │                                          │
       │ 列映射:                                   │
       │   渠道 → shopName                         │
       │   收件人 → receiverName                   │
       │   手机 → mobile                           │
       │   地址 → address                          │
       │   业务员/创建人 → sellerName/registerName │
       │   货品编号 → goodsNo                       │
       │   数量 → sellCount                        │
       └──────────────────────────────────────────┘
       确认创建这 10 个订单？

用户：确认

Skill：调用 batch_import.batch_create_orders("sample_orders.xlsx", dry_run=False)
       
       📋 批量导入结果
       ✅ 创建成功: 9
       ❌ 创建失败: 1（渠道名不存在）
       ⏭️ 校验跳过: 2
       
       成功创建的单号: YR260404001001, YR260404001002, ..., YR260404001009
       每个成功结果包含 created_trade：创建后用 oms.trade.fullinfoget 反查到的新销售单字段
       
       ⚠️ 复核功能已禁用，创建后请在吉客云网页端手动复核。
       - 普通手工单：运营审核 → 财务复核
```

### 批量导入支持的表格列名

| API 字段 | 支持的列名（中英文均可） |
|----------|----------------------|
| shopName | 渠道、店铺、销售渠道、销售渠道名称、channel |
| receiverName | 收件人、收货人、姓名、客户、receiver |
| mobile | 手机、手机号、电话、联系电话、phone |
| state | 省、省份、province |
| city | 市、城市、市（区） |
| district | 区、区县、区（县） |
| address | 地址、详细地址、收件地址、收货地址 |
| sellerName | 业务员、创建人、申请人、销售员 |
| goodsNo | 货品编号、SKU、编号、条码、barcode |
| goodsName | 货品名称、商品名称、品名 |
| batchNo | 批次号、批号、生产批号 |
| sellCount | 数量、qty、发货数量 |
| sellPrice | 单价、售价、price（可选） |
| sellerMemo | 备注、客服备注、内部备注、remark（可选） |
| buyerMemo | 客户备注、买家备注、buyerMemo（可选） |
| customerName | 客户名称、客户账号（寄样单必填；表格没有时可传 `default_customer_name`） |
| onlineTradeNo | 网店订单号、平台订单号、onlineTradeNo（可选；不填自动生成） |
| warehouseName | 仓库、仓库名称、发货仓库（可选，不填则自动匹配） |
| logisticName | 物流、物流公司、快递（可选，不填则自动匹配） |
| orderType | 类型、订单类型、单据类型、标记（可选，默认"寄样"；支持：样品/寄样/JY、补发/BF、普通/手工/PT） |

> `sellerName` 必填，并且必须是当前创建人本人员工姓名，不允许代填其他人；系统会把同一个员工姓名写入 `sellerName` 和 `registerName`。
> 官方导入模板已支持：`网店订单号、收货人、发货仓库、销售渠道名称、批次号、物流公司、业务员、标记` 等列；表头中的中文/英文括号、全角/半角、空格会自动归一化匹配。

> **智能合并**：优先按 `onlineTradeNo` 合并多货品；没有网店订单号时，同一渠道 + 收件人 + 手机 + 地址的多行自动合并为一个订单的多个货品明细。

### 驳回审核

```
用户：驳回 YR260402001234
Skill：确认要驳回销售单 YR260402001234 的审核？（驳回后需重新审核）
用户：确认
Skill：调用 modules/sales_order.reject_trade("YR260402001234")
       ✅ 已驳回
```

### 批量驳回

```
用户：批量驳回这几个单号：YR260404001001, YR260404001002, YR260404001003
Skill：确认要批量驳回以下 3 个销售单？
       YR260404001001, YR260404001002, YR260404001003
用户：确认
Skill：调用 modules/sales_order.batch_reject_trades([...])
       ✅ 批量驳回完成: 3/3 成功
```

### 查询渠道

```
用户：查一下直播组有哪些渠道
Skill：调用 modules/channel.py 查询 channelDepartName 包含"直播组"的渠道
       返回：82 个匹配渠道
```

### 查询物流

```
用户：查一下正品-宝鼎售后仓有哪些物流可用
Skill：调用 modules/logistics.get_logistics_for_warehouse(warehouseId)
       返回：可用物流列表
```

> 如果用户给的是 `YR` 销售单号，且要查的是“物流单号/快递单号”，不要走仓库物流档案查询；应改走 `query_trade_logistics()` 这条两步链路。

### 查询操作日志

```
用户：查一下 YR260402000932 的操作日志
Skill：调用 modules/sales_order.query_trade_logs("YR260402000932", start_time, end_time)
       注意：startTime 与 endTime 间隔不能超过 1 天
```

## 技术实现

### 项目结构

```
jackyun-skill-project/
├── SKILL.md               # 本文件 — Skill 入口
├── config.py               # 配置（AppKey/Secret/URL/超时/重试）
├── jackyun_api.py           # API 客户端（签名、重试、分页、限流）
├── templates/
│   └── shentong_delivery_note.xlsx # 默认申通仓出库单 Excel 模板
├── helpers/
│   ├── constants.py         # API 方法名常量 + 状态码枚举
│   ├── validators.py        # 参数校验（必填/手机/金额/日期）
│   └── formatters.py        # 格式化（金额/表格/状态翻译）
├── modules/
│   ├── sales_order.py       # ★ 核心：查询/创建/驳回/发货/日志/包裹
│   │                        #   + 批量驳回/全流程编排
│   │                        #   + 渠道→仓库→物流自动解析
│   │                        #   + 三种类型：普通手工单/寄样/补发
│   ├── batch_import.py      # ★ 批量导入：Excel/CSV→智能列映射→批量建单
│   ├── warehouse.py         # 仓库查询/搜索/公司校验（已订阅 ✅）
│   ├── channel.py           # 渠道查询/搜索/渠道→仓库解析（已订阅 ✅，当前约645个）
│   ├── logistics.py         # 物流档案/仓库→物流匹配（已订阅 ✅）
│   ├── stock_doc.py         # 出入库单查询/创建/审核
│   ├── delivery_note.py     # 销售单→Excel模板出库单生成
│   ├── goods.py             # 货品查询 / 模糊候选
│   ├── inventory.py         # 库存
│   │                        #   + 批次库存查询含效期(erp.batchstockquantity.get)
│   │                        #   + 分仓库存查询-规格模式(erp-stock.stock.skulist)
│   ├── transfer.py          # 调拨
│   ├── shop_order.py        # 网店订单（复用 fullinfoget）
│   ├── finance.py           # 财务
│   ├── combined.py          # 组合装 / 组装拆卸
│   └── vendor.py            # 供应商
└── tests/                   # 测试
```

### 核心调用链

```
# 单个创建寄样/补发单
create_sample_order(shopName, receiver, mobile, address, goods_list, order_type="JY"/"BF")
  └→ resolve_channel_warehouse_logistics(shopName)
  │     └→ channel.resolve_channel_info()          → 渠道 + 默认仓库 + 公司
  │     └→ warehouse.get_warehouse_by_code()       → 仓库ID + 公司校验
  │     └→ logistics.get_logistics_for_warehouse() → 可用物流
  └→ create_trade() → 返回单号

# 单个创建普通手工销售单
create_manual_order(shopName, receiver, mobile, address, goods_list)
  └→ resolve_channel_warehouse_logistics(shopName)  → 同上自动解析
  └→ 校验 sellPrice 必填；赠品需显式传 isGift=1 才允许 0 金额
  └→ 未手填批次时按仓库库存自动拆分 batchList
  └→ 校验 sellTotal = sellPrice * sellCount
  └→ 自动计算 totalFee/payment
  └→ create_trade() → 返回单号

# 批次库存查询（含效期）
query_batch_stock_quantity(warehouse_code, goods_no, ...)
  └→ erp.batchstockquantity.get
  └→ 返回含 batchNo, productionDate, expirationDate, shelfLife 等效期信息

# 分仓库存查询(规格模式)
query_sku_stock_list(warehouse_code, goods_no, cols, ...)
  └→ erp-stock.stock.skulist
  └→ 返回按 cols 指定的库存字段（必须传货品+规格信息）

# 批量导入建单
batch_create_orders(file_path, dry_run=False)
  └→ read_spreadsheet()     → 读取 Excel/CSV
  └→ auto_map_columns()     → 智能列名映射
  └→ validate_row()         → 逐行校验
  └→ group_orders_from_rows() → 多货品合并
  └→ create_sample_order()  → 逐个创建（含自动仓库/物流）
  └→ format_import_report() → 生成报告

```

### API 签名算法

```
签名 = MD5(appSecret + key1value1key2value2... + appSecret).lower()
参数按 key 字母序排列，排除 sign / contextid / token
```

签名逻辑是可直接调用的公共能力，禁止临时重写：

```python
from helpers.jackyun_signature import build_signed_openapi_params, generate_openapi_sign

params = build_signed_openapi_params(
    method="erp.warehouse.get",
    bizcontent={"pageIndex": 0, "pageSize": 100},
)
# params 可直接作为 form data POST 到吉客云 OpenAPI
```

常规接口调用优先使用：

```python
from jackyun_api import get_client

result = get_client().call("erp.warehouse.get", {"pageIndex": 0, "pageSize": 100})
```

### API 请求格式

- POST `https://open.jackyun.com/open/openapi/do`
- Content-Type: `application/x-www-form-urlencoded`
- `method` 参数区分接口，`bizcontent` 参数为 JSON 字符串
- 成功码: `code` 为 `200` 或 `"200"`

### 关键踩坑点

| 项目 | 注意 |
|------|------|
| ordercreate 参数 | `tradeOrderDetails` 必须嵌套在 `tradeOrder` **内部**，不是并列顶级字段 |
| 明细必填字段 | `goodsNo`, `specName`, `barcode`, `unit`, `sellPrice`, `sellCount`, `sellTotal` 全部必填 |
| 数值字段类型 | 统一传**字符串**（`"0"` 而不是 `0`） |
| 出库单字段名 | `selelctFields`（吉客云拼写错误，必须照搬） |
| 销售单字段名 | `fields`（正确拼写，与出库单不同） |
| 日志时间限制 | `orderloglist` 的 startTime/endTime 间隔**不能超过 1 天** |
| 备注字段 | 用 `sellerMemo`（不是 `remark`），`phone` 和 `mobile` 都要传 |
| 渠道无仓库 | 部分渠道 `warehouseName="无"`，此时需手动指定仓库 |
| 公司校验 | 渠道和仓库必须属于同一公司（`companyId == warehouseCompanyId`） |
| 物流匹配 | 物流档案的 `warehouseId` 是逗号分隔的仓库ID列表 |
| 复核功能 | reAudit API 已取消订阅，创建后请在吉客云网页端手动复核 |
| 普通手工单金额 | `create_manual_order` 的 sellPrice 必填，不能为0；totalFee/payment 由明细自动汇总 |
| 批次库存查询 | `erp.batchstockquantity.get` 的 warehouseCode 必填；productionDate 返回毫秒时间戳 |
| 分仓库存查询 | `erp-stock.stock.skulist` 必须传货品+规格信息，不能只传仓库编码；cols 字段必填，按需指定返回字段 |
| 分仓库存限制 | `erp-stock.stock.skulist` 最多匹配 1000 个规格 |

### 错误处理

- **网络超时**: 指数退避自动重试（最多 3 次）
- **业务错误**: 翻译为中文友好提示返回给用户
- **参数缺失**: 引导用户补充缺失信息
- **未订阅 API**: 提示用户联系 IT 在开放平台订阅
- **写入保护**: 操作前展示汇总并等待用户明确确认
- **批量容错**: 批量操作中单个失败不影响其余，最终汇总展示所有结果
## 新增单据能力补充

以下能力已经可以直接调用，属于写操作，执行前仍然需要先向用户展示摘要并二次确认。

### 1. 新增出库单

- 对应函数：`modules.stock_doc.create_doc_out(doc_data)`
- 审核函数：`modules.stock_doc.check_doc(rec_id=..., goodsdoc_no=...)`
- 最低必填：
  - `inouttype`
  - `goodsDocDetailList`
  - 每条明细至少包含 `goodsNo`、`quantity`
- 如未手填批次且仓库可解析出 `warehouseCode`，出库单会按批次库存自动拆分 `batchList`

示例：

```python
create_doc_out({
    "inouttype": 201,
    "outBillNo": "OUT001",
    "warehouseName": "上海成品仓",
    "goodsDocDetailList": [
        {"goodsNo": "G001", "quantity": 2}
    ]
})
```

### 2. 新增入库单

- 对应函数：`modules.stock_doc.create_doc_in(doc_data)`
- 审核函数：`modules.stock_doc.check_doc(rec_id=..., goodsdoc_no=...)`
- 最低必填：
  - `inouttype`
  - `goodsDocDetailList`
  - 每条明细至少包含 `goodsNo`、`quantity`

示例：

```python
create_doc_in({
    "inouttype": 101,
    "billNo": "IN001",
    "warehouseName": "上海成品仓",
    "goodsDocDetailList": [
        {"goodsNo": "G001", "quantity": 5}
    ]
})
```

### 3. 新增调拨单

- 对应函数：`modules.transfer.create_transfer(transfer_data)`
- 审核函数：`modules.transfer.check_transfer(bill_no=..., rec_id=...)`
- 最低必填：
  - `outWarehouseNo`
  - `inWarehouseNo`
  - `goodsList`
  - 每条明细至少包含 `goodsNo`、`qty`

示例：

```python
create_transfer({
    "outWarehouseNo": "WH001",
    "inWarehouseNo": "WH002",
    "goodsList": [
        {"goodsNo": "G001", "qty": 3}
    ]
})
```

### 4. 对话执行规则

- 用户说“新增单据”时，先确认是“出库单 / 入库单 / 调拨单”
- 如果缺少关键字段，先补齐，不要直接调用接口
- `quantity` / `qty` 必须为正整数
- 单据创建成功后，如用户要求继续审核，再调用对应 `check_*` 函数
- 当前代码层已经做了基础校验；如果 ERP 仍报业务错，直接把 ERP 返回信息反馈给用户

## 调拨单优化补充

调拨单能力已切换到官方 `erp.allocate.*` API 族，不再优先使用旧的 `erp.storage.transfer.*`。

### 当前可用函数

- `modules.transfer.create_transfer(transfer_data)`
  对应 `erp.allocate.create`
- `modules.transfer.quick_create_transfer(transfer_data)`
  对应 `erp.allocate.quick.create`
- `modules.transfer.query_transfers(...)`
  对应 `erp.allocate.get`
- `modules.transfer.close_transfer(allocate_no, reason="")`
  对应 `erp.allocate.close`
- `modules.transfer.complete_transfer(allocate_no, reason="", memo="", is_not_notify=0)`
  对应 `erp.allocate.complete`

### 同价 / 异价规则

- 同主体调拨：使用 `allocateType=0`
- 跨公司调拨：使用 `allocateType=1`
- 异价调拨才允许并要求填写明细单价/金额
- 同价调拨会自动移除明细中的 `skuPrice` / `totalAmount`

### 明细字段映射

- 业务侧常用 `qty` 会自动映射为 `skuCount`
- `barcode` 会自动映射为 `skuBarcode`
- `outerSkuCode` 会自动映射为 `outSkuCode`
- `remark` 会自动映射为 `rowRemark`

### 调拨创建最小建议参数

创建前补充规则：

- 发件人 / 收件人默认取调出仓 / 调入仓对应联系人与电话、地址
- `applyUserName` 必须让用户明确确认是创建人本人
- `applyUserId` 会按 `erp.user.search` 结果校验，`departCode` 会结合 `erp.depart.query` 精确校验
- `companyCode` 必须对应调出公司或调入公司
- 币种按仓库所属公司自动查询：调用 `erp.company.query` 读取 `currencyCode`
- 货品会优先尝试调用货品接口自动补齐条码 / 外部货品编码；单位 `unitName` 固定为 `Pcs`
- 批次会按调出仓批次库存自动生成 `batchList`，默认策略 `fifo` 先进先出；用户有特殊要求时先筛选批次再 FIFO 分配
- 如果用户明确允许“缺货也先建调拨单”，调用 `run_transfer_workflow(..., allow_stock_shortage_create=True)`；缺货明细只写 `isBatch=1`，不写不存在的 `batchList`，并在返回结果中提示后续补库存后再匹配批次

```python
create_transfer({
    "allocateType": 0,
    "applyUserId": 1,
    "applyUserName": "张三",
    "departCode": "D01",
    "companyCode": "P01",
    "outWarehouseCode": "WH001",
    "intWarehouseCode": "WH002",
    "stockAllocateDetailViews": [
        {
            "unitName": "Pcs",
            "skuCount": 3,
            "isCertified": 1,
            "skuBarcode": "BAR001"
        }
    ]
})
```

跨公司异价调拨示例：

```python
create_transfer({
    "allocateType": 1,
    "applyUserId": 1,
    "applyUserName": "张三",
    "departCode": "D01",
    "companyCode": "P01",
    "outWarehouseCode": "WH001",
    "intWarehouseCode": "WH002",
    "stockAllocateDetailViews": [
        {
            "unitName": "Pcs",
            "skuCount": 3,
            "isCertified": 1,
            "skuBarcode": "BAR001",
            "skuPrice": 12,
            "totalAmount": 36
        }
    ]
})
```

### 关于“递交”

- 官方开放平台方法列表中未发现单独名为“调拨递交 / submit”的公开接口
- 如果需要更接近“创建后自动推进流程”，优先评估 `quick_create_transfer()`
- `quick_create_transfer()` 支持 `openAllocateType`
  - `1`：一键调拨
  - `2`：生成入库申请，但不自动入库
  - `3`：只生成出库申请，后续手动直接出库
- 若后续确认你们内部“递交”对应的是别的私有接口，再补充到 skill

### 调拨单自定义字段

- 代码层支持直接透传调拨单自定义字段，不会主动过滤
- 单头可直接传 `field1` - `field10`
- 明细可直接传 `detailField1` - `detailField10`
- 如果你们吉客云实例实际返回了更多扩展位，也可以继续按原字段名透传
- 如果业务需要的字段当前不存在，联系 IT 新增字段，或者先从流程中排除该字段，不在代码里做虚拟字段兜底

根据你提供的两张调拨单，当前实际有值的单头自定义字段如下：

- `YRDB202604130034`
  - `field1 = CNY`
  - `field3 = 同主体调拨`
  - `field4 = 分销组COLORGRAM`
  - `field5 = 13%`
  - `field6 = 13%`
- `YRDB202604130033`
  - `field1 = KRW`
  - `field3 = ACT-依然美妆（UN/DFH）`
  - `field4 = 个护部天猫UNOVE海外旗舰店`
  - `field5 = 0%`
  - `field6 = 0%`

这两张单据的明细 `detailField1` - `detailField10` 当前都为空。

当前已确认的单头字段定义：

- `field1`：币种
  可选：`CNY`、`USD`、`KRW`
- `field3`：调出渠道
  数据字典单选下拉
  同主体调拨默认值：`同主体调拨`
- `field4`：调入渠道
  数据字典单选下拉
  取实际渠道名称，不带公司前缀
  例如：
  - `ACT-彩妆部天猫Apieu奥馥海外旗舰店` -> `彩妆部天猫Apieu奥馥海外旗舰店`
  - `依然美妆-彩妆部天猫Apieu奥馥海外旗舰店` -> `彩妆部天猫Apieu奥馥海外旗舰店`
  - `依然美妆-直播组小红书APIEU奥馥海外旗舰店` -> `直播组小红书APIEU奥馥海外旗舰店`
  - `其他-直播组小红书APIEU奥馥海外旗舰店` -> `直播组小红书APIEU奥馥海外旗舰店`
- `field5`：调出税率
  可选：`13%`、`0%`
- `field6`：调入税率
  可选：`13%`、`0%`

税率规则：

- 同主体调拨：`field5` / `field6` 默认都为 `0%`
- 跨主体调拨：需要按实际业务分别填写调出税率和调入税率

调入渠道规则：

- `field4` 如果传入的是完整渠道名，代码会自动剔除第一个 `-` 前面的公司前缀
- 如果字段缺失，可以先调用渠道查询列表确定渠道名称
## 2026-04-13 增量集成说明

本次已补齐以下能力，并保留公开接口目录：

- 调拨单：`modules/transfer.py`
  - 已切换到官方 `erp.allocate.*`
  - 支持 `get / create / quick.create / close / complete`
  - 已支持调拨单业务自定义字段映射：
    - `currency -> field1`
    - `out_channel -> field3`
    - `in_channel -> field4`
    - `out_tax_rate -> field5`
    - `in_tax_rate -> field6`
- 组装拆卸单：`modules/combined.py`
  - 已支持 `erp.combined.get.v2`
  - 已支持 `erp.combind.create`
  - 已支持 `erp.combind.create.v2`
  - 已支持 `erp.combined.close`
- 售后：`modules/aftersales.py`
  - 已整合全部公开 `ass-business.*` 方法
  - 已整合全部公开 `ass.*` 方法
  - 通过 `call_aftersales_api(method_key_or_name, bizcontent)` 统一分发
- 财务：`modules/finance.py`
  - 已整合全部公开 `fin.*` 方法
  - 已整合全部公开 `fin-fbs.*` 方法
  - 通过 `call_finance_api(method_key_or_name, bizcontent)` 统一分发

### 接口目录文件

- 全量方法原始目录：`openapi_method_catalog.json`
- 人类可读目录：`OPENAPI_METHOD_CATALOG.md`

当前目录统计：
- `ass-business.*`: 26 个
- `ass.*`: 5 个
- `fin.*`: 11 个
- `fin-fbs.*`: 22 个
- `erp.combined* / erp.combind*`: 4 个

### 代码修复

本次顺手修复了项目中的几处实际兼容性问题：

- `modules/sales_order.py`
  - 补回 `check_trade()` / `finance_check_trade()` 兼容入口
  - 补回 `create_and_approve_trade()` 兼容流程
  - 修复 `query_trades()` 返回结构兼容性
  - 支持 `bill_no` 查询别名
- `modules/stock_doc.py`
  - 增加入库单/出库单创建校验
- `modules/transfer.py`
  - 修复旧调拨接口族不一致问题
  - 增加同主体/跨主体调拨规则
  - 增加自定义字段默认值和校验

### 推荐调用方式

组装拆卸单：

```python
from modules.combined import query_combined, create_combined, close_combined
```

售后：

```python
from modules.aftersales import call_aftersales_api, create_refund, create_returnchange
```

财务：

```python
from modules.finance import call_finance_api, list_accounts, create_acdoc, create_fbs_bill
```

### 测试状态

以下测试在 2026-04-13 已通过：

- `python -m unittest tests.test_stock_doc`
- `python -m unittest tests.test_transfer`
- `python -m unittest tests.test_combined`
- `python -m unittest tests.test_aftersales`
- `python -m unittest tests.test_finance`
- `python -m unittest discover -s tests`

## 2026-04-13 最新业务规则补充

### 销售单创建规范

- 创建销售单前，必须先确认：
  - 渠道
  - 仓库
  - 物流
- 普通手工销售单如为赠品，需显式标记 `isGift=1`，才允许 0 单价 / 0 金额
- 普通手工销售单如已传 `sellTotal`，必须校验和 `sellPrice * sellCount` 一致
- 涉及批次管理时，若单个批次不足但总可用库存足够，应自动拆分多个批次生成 `batchList`
- 仓库必须属于该渠道对应公司名下，不允许跨公司乱选仓库
- 物流必须属于该仓库可用物流档案
- 默认物流规则已记录在 `modules/sales_order.py`：
  - 麦歌仓：`麦歌中通`
  - 宝鼎仓：`宝鼎中通`
  - 韩国申通仓：`依然物流`
  - 韩国韵达仓：`韩国韵达-韵达国际`

### 销售单审核规范

- 用户确认创建后，可以继续调用销售单审核接口：`oms.trade.audit.pass`
- 代码入口：
  - `modules.sales_order.check_trade(trade_no)`
  - `modules.sales_order.create_manual_order_and_audit(...)`
  - `modules.sales_order.create_sample_order_and_audit(...)`
- 流程说明：
  - 寄样单：审核后转入审批流程
  - 普通手工单：审核后转入复核，需联系对应 FBP
  - 补发单：审核后转入复核，需联系对应 FBP

### 组合装 / 组装拆卸 / 调拨 / 售后 / 财务订阅状态

以下接口已订阅，可直接使用：

- 调拨：`modules/transfer.py`
- 退换补发 / 售后：`modules/aftersales.py`
- 组装拆卸 / 组合装：`modules/combined.py`
- 财务：`modules/finance.py`

### 使用规范

- 尽量避免乱创建单据，避免造成系统单据混乱
- 任何缺失字段，都必须先向用户补齐后再创建
- 如果字段在系统中不存在，需要联系 IT 部新增字段，或明确从流程中排除
- 本 skill 不对外传播，仅由依然集团 IT 部维护
- 使用中如有问题，请联系 IT 部门

### Skill 应主动建议的常见能力

当用户只描述业务目标，没有说接口名时，Skill 应主动识别并建议可以做的操作，例如：

- 新建销售单 / 寄样单 / 补发单
- 审核、驳回、批量审核销售单
- 批量修改销售单仓库、物流
- 查询销售单、调拨单、出入库单、售后单、财务单据
- 新建调拨单、出入库单、组合装 / 组装拆卸单、售后单
- 查询库存、批次库存、分仓库存
- 查询渠道、仓库、物流、货品，并给出模糊候选
- 统计待审核订单、货品数量
- 做定时查询结果整理
- 对接邮箱推送、企业微信、智能表格写入等外部自动化流程

对于邮箱推送、企业微信、智能表格写入等外部自动化场景：

- Skill 应先说明当前项目是否已集成
- 若未集成，应说明可以继续扩展为自动化任务，而不是假装已支持
- 当前项目已支持“先导出库存主表 / 批次明细文件”，但**未内置**企业微信智能表格、文档 MCP、企微智能表格 webhook 的直接写入能力
- 如果用户需要把库存结果写入企业微信智能表格、文档 MCP 或 webhook，需由用户自己提供并对接对应的接入方式、鉴权信息、目标表结构或 webhook 地址

### 智能联动规则

- 用户不知道该用哪个渠道建销售单时：
  - 先调用 `modules.channel.suggest_channels(keyword, company_name=None)`
  - 如果用户给了公司名，则优先按公司过滤候选渠道
  - 如果该公司下没有匹配渠道，先提示用户名称可能有误并给出模糊候选
  - 仍找不到时，提示联系财务或 IT 新增渠道
- 用户不确定货品编号，只知道部分货品名称时：
  - 先调用 `modules.goods.suggest_goods(keyword)`
  - 返回候选货品后，再让用户确认具体货品
  - 不应在货品未确认时直接创建单据
- 用户指定仓库时：
  - 必须校验仓库属于该渠道对应公司
  - 物流必须属于该仓库可用物流档案
- 用户处理运营待审核单据时：
  - 先调用 `modules.sales_order.summarize_pending_trades(...)` 统计待审核单据数和货品数量
  - 如需列出候选单据，调用 `modules.sales_order.list_pending_trade_candidates(...)`
  - 如需按“渠道/时间范围”直接汇总网店待审核订单，调用 `modules.sales_order.summarize_pending_shop_orders(...)`
  - 如需按“渠道/时间范围”直接批量审核，调用 `modules.sales_order.batch_audit_pending_trades_by_filter(...)`
  - 如需按“渠道/时间范围”直接批量修改仓库物流，调用 `modules.sales_order.batch_update_pending_trades_logistics_by_filter(...)`
  - 批量审核时调用 `modules.sales_order.batch_audit_trades(trade_nos, operator=None)`
  - 批量修改仓库/物流时调用 `modules.sales_order.update_logistics_warehouse(update_list)`

### 销售单接口补充确认

通过浏览器查询销售单接口结果，当前销售单相关公开接口至少包括：

- `oms.trade.audit.pass`
- `oms.trade.fullinfoget`
- `oms.trade.countget`
- `oms.trade.ordercreate`
- `oms.trade.order.batchUpdateLogisticWarehouse`
- `oms.trade.order.completeDelivery`
- `oms.trade.order.reAudit`
- `oms.open.trade.audit.reject`
- `oms.trade.orderloglist`
- `oms.trade.package.querylist`

其中 `oms.trade.audit.pass` 页面示例显示：

- 支持 `tradeNos`
- 示例参数中包含 `operator`
- 适合做批量审核入口

### Skill 更新分发建议

- 当前项目带有版本文件：`VERSION`
- 更新记录文件：`CHANGELOG.md`
- 发布打包脚本：`scripts/build_release.ps1`
- 使用说明：`docs/PROJECT_MANUAL.md`

建议由依然集团 IT 部维护一个主版本目录或 Git 仓库。每次业务更新后：

1. 修改代码和 `SKILL.md`
2. 更新 `VERSION`
3. 记录 `CHANGELOG.md`
4. 运行发布脚本生成 zip
5. 将 zip 发给同事替换旧版本，或让同事从统一仓库拉取
## 2026-04-14 调拨单联系人字段修正

- 官方文档 `erp.allocate.create` 中，调拨单收发货人信息应写入 `stockAllocateExpressInfo`，且官方字段名为：
  - 发件人：`send`
  - 发件电话：`sendTel`
  - 发件手机号：`sendPhone`
  - 发件详细地址：`sendAddress`
  - 收件人：`receive`
  - 收件电话：`receiveTel`
  - 收件手机号：`receivePhone`
  - 收件详细地址：`receiveAddress`
- `erp.warehouse.get` 返回仓库联系人字段为：`linkMan`、`tel`、`address`
- 调拨单创建时，如果用户未显式提供收发货人姓名/地址，应默认从调出仓、调入仓查询结果中的 `linkMan` / `tel` / `address` 自动回填到 `stockAllocateExpressInfo`
- 如果仓库档案里也缺少联系人姓名或地址，应直接报错，不允许提交空的收发货人信息
## 2026-04-28.2 MCP/CLI 调用规则

- 吉客云 MCP 已作为优先调用路径：只有 `docs/jackyun_mcp_tools.json` 中存在且启用的 method 才允许走 MCP。
- MCP 服务地址为 `https://mcp.open.jackyun.com/mcp/messages`；请求头为 `Authorization: <token>`，不要加 `Bearer`。
- MCP 授权应用 AppKey 已统一跟随 `JACKYUN_APP_KEY`，真实值仅从本地环境变量读取。
- `jackyun_api.get_client().call()` 默认策略为 `auto`：MCP 可用则优先 MCP；`JACKYUN_CLI_ENABLED=1` 时可用官方 CLI 兜底；最后才走原签名 HTTP。
- 强制策略：
  - `JACKYUN_CALL_STRATEGY=mcp`：只走 MCP，未订阅工具或缺 token 直接失败。
  - `JACKYUN_CALL_STRATEGY=cli`：只走官方 CLI。
  - `JACKYUN_CALL_STRATEGY=http`：只走原签名 HTTP。
- 官方 CLI 已打包到 `tools/jkyuncli/`，包含 Windows amd64、macOS Intel、macOS Apple Silicon。首次运行会解压到 `data/runtime/jkyuncli/`，并自动在该 runtime 下配置凭证；该目录不随 skill 发布。
- 不要让用户或模型临时重写 Node/Python 签名逻辑。遇到需要直连签名 HTTP 的场景，必须调用 `helpers.jackyun_signature.build_signed_openapi_params()`；常规调用走 `jackyun_api.get_client().call()`，必要时再由官方 CLI fallback 接管。
- 字段来源仍以官方 `docs/jackyun_cli_docs/methods-index.json` 和 `docs/jackyun_cli_docs/{method}.json` 为准；MCP 只决定调用通道，不允许据此猜字段。
- 高频工作流返回值会包含 `execution_plan`，用于说明该工作流涉及的 method 预计优先走 MCP、CLI 还是 HTTP。
- 运行 `python scripts/diagnose_runtime.py` 可检查当前环境的 MCP token、CLI 打包文件、以及各高频工作流的路由计划。
- 写操作要格外谨慎：如果未来吉客云 MCP 增加创建/审核类工具，超时后的跨通道兜底可能带来重复提交风险；在官方未提供幂等键前，写操作仍应保持明确确认和完整字段校验。
- 产品/工程复盘和 MCP 实测记录见 `docs/PROJECT_MANUAL.md`。
