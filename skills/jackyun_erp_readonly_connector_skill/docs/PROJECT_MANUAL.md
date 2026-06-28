# 吉客云 ERP Skill 项目手册

## 覆盖范围

本 skill 通过业务工作流帮助同事操作吉客云 ERP，避免手工拼 API 参数。当前覆盖：

- 销售单查询、普通手工单创建、寄样单创建、补发单创建、审核、驳回、包裹/物流查询。
- 待审核网店订单汇总、候选列表、批量审核、批量修改仓库物流。
- 调拨单创建、快速调拨、调拨查询、关闭、完成。
- 出库单、入库单创建与审核。
- 库存查询、批次库存查询、库存导出、受控历史库存查询。
- 经营报表：货品销售多维分析，支持按时间段、渠道、仓库、业务员等筛选并导出销售额、销量等所有官方返回字段。
- 基础资料查询与本地缓存：用户、公司、部门、渠道、仓库、物流、货品、数据字典。
- 按销售单生成 Excel 模板单据，例如默认申通仓出库单模板。

## 运行策略

高频业务工作流调用业务模块，业务模块最终统一调用：

```text
jackyun_api.get_client().call(method, bizcontent)
```

底层客户端按配置选择通道：

```text
MCP -> 官方 CLI -> 签名 HTTP
```

配置说明：

- `JACKYUN_CALL_STRATEGY=auto`：方法在 `docs/jackyun_mcp_tools.json` 中且配置了 `JACKYUN_MCP_TOKEN` 时优先走 MCP；`JACKYUN_CLI_ENABLED=1` 时使用 CLI；否则走签名 HTTP。
- `JACKYUN_CALL_STRATEGY=mcp`：强制走 MCP，token 或工具缺失则报错。
- `JACKYUN_CALL_STRATEGY=cli`：强制走官方 CLI。
- `JACKYUN_CALL_STRATEGY=http`：强制走签名 HTTP。
- `JACKYUN_MCP_URL=https://mcp.open.jackyun.com/mcp/messages`
- `JACKYUN_AUTHORIZED_APP_KEY` 默认跟随 `JACKYUN_APP_KEY`；真实值仅从本地环境变量读取。
- 直连 HTTP 必须保证 `JACKYUN_APP_KEY` 与 `JACKYUN_APP_SECRET` 匹配，不在文档或测试中记录真实 AppKey。

MCP token 规则：HTTP 请求头是 `Authorization: <token>`，不要加 `Bearer` 前缀。

## MCP 验证记录

2026-04-28 已用 `erp.stockquantity.get` 验证 MCP。

测试参数：

```json
{"pageIndex":"0","pageSize":"1","isChannelReserve":"0"}
```

实测结果：MCP 返回的库存行位于 `content.text` 中；运行时已把它规范化为内部 OpenAPI 风格结构：

```json
{
  "code": "200",
  "result": {
    "data": {
      "goodsStockQuantity": [
        {
          "goodsNo": "8809644499056",
          "warehouseCode": "YR03",
          "currentQuantity": 0,
          "useQuantity": 0
        }
      ]
    }
  }
}
```

不要把 MCP token 写入源码或文档，只能通过环境变量配置。

## 诊断方式

运行：

```bash
python scripts/diagnose_runtime.py
```

输出内容包括：

- 是否配置了 `JACKYUN_MCP_TOKEN`。
- 当前打包的 MCP 工具数量。
- 是否启用 CLI 兜底。
- 已携带哪些 CLI 压缩包。
- 各工作流的 `execution_plan`，展示方法级路由。

高频工作流返回值也包含 `execution_plan`，方便判断本次预计走 MCP、CLI 还是 HTTP。

## 官方来源

新增或修改字段前必须先看官方来源：

- MCP 工具列表：`https://open.jackyun.com/developer/mcpservice/toolList.html`
- MCP 文档：`https://open.jackyun.com/developer/mcpservice/documentation.html`
- CLI 页面：`https://open.jackyun.com/developer/jkyuncli/jkyuncli.html?from=self`
- CLI 方法索引：`https://open.jackyun.com/developer/jkyuncli/methods-index.json`
- CLI 方法详情：`https://open.jackyun.com/developer/jkyuncli/methods/{method}.json`
- 已缓存 CLI 文档：`docs/jackyun_cli_docs/`
- 已缓存 OpenAPI 文档：`dist/jackyun_project_docs/`

规则：MCP 只决定调用通道，字段名仍以官方 CLI/OpenAPI JSON 为准。

## 本地状态

运行状态位于 `data/`。发布包会携带 `data/cache/*.json` 基础资料缓存，但不携带用户资料、运行经验和运行期二进制：

- `data/profile.json`：默认操作人资料。
- `data/cache/*.json`：基础资料缓存。
- `data/experiences/*.jsonl`：成功工作流样例。
- `data/runtime/jkyuncli/`：运行期解压的 CLI 文件。

## 首次操作人

第一次执行写操作时，必须让用户提供本人姓名。保存后复用于：

- 销售单业务员/登记人字段。
- 调拨单申请人字段。
- 后续创建人、申请人、业务员等字段。

调拨单申请公司默认读取 `JACKYUN_DEFAULT_APPLICATION_COMPANY_NAME`，当前为“依然电商”。申请人部门从默认操作人的吉客云用户/部门档案解析。

## 模板与经验

用户不知道字段时，可以给模板：

- 销售单模板。
- 调拨单模板。
- 出入库单模板。
- 库存查询模板。

调用 `modules/templates.py`。成功操作会记录到 `data/experiences/`，可作为后续参考，但不要把一次性数据直接升级为长期业务规则。

如果用户不知道销售单需要哪些字段，必须先给销售单模板。模板必须包含仓库、业务员/登记人、客户名称、收件信息、货品、价格/数量、批次字段。

建单防脏数据规则：

- 销售单、调拨单、出入库单在工作流层必须先校验字段。校验失败时返回 `needs_input`、缺失项和对应模板，不调用创建接口。
- 用户说“不知道填什么”时，先给模板；用户给的信息明显不完整时，先列缺失项和候选，不猜默认值建单。
- 用户纠正错误后，先复盘原因，再调用 `record_workflow_correction()` 记录 `issue`、`root_cause`、`prevention_rule`、`corrected_fields`。纠错后重新跑预检，预检通过前不创建。
- 纠错经验写入 `data/experiences/corrections.jsonl`；销售单预检会带出最近同类纠错提示，常用字段也会写入本地偏好，避免第二次重复踩坑。

## 销售单

支持类型：

- 普通手工销售单。
- 寄样单。
- 补发单。

规则：

- 创建前必须确认单据类型。
- 必须确认渠道、用户已知的仓库、收件人、手机号、地址、货品、数量和创建人。
- 普通手工销售单必须有单价和金额，除非货品明确标记为赠品 `isGift=1`。
- `buyerMemo` 是买家备注。
- `sellerMemo` 是内部备注/订单备注。
- 寄样单和补发单必须写入 `tradeOrderFlags`，不能只靠备注文字。
- 已用真实单据确认：样品标记名称为 `样品`，标记 ID 为 `1108774772244219136`，参考单号 `YR260429001034`；补发标记名称为 `补发`，标记 ID 为 `1108772859952365824`，参考单号 `YR260428000231`。
- 寄样单必须由用户提供 `customer_name/customerName`，不能用收件人或渠道代替。
- 业务员/操作人必须使用已确认员工实名，并同时写入 `sellerName` 和 `registerName`。
- 用户提供仓库时，物流必须按最终仓库推导，不能按渠道原默认仓库推导。
- 仓库物流别名：
  - 仓库名称包含 `麦歌`：物流用 `麦歌中通`。
  - 仓库名称包含 `宝鼎`：物流用 `宝鼎中通`。
  - 仓库名称包含 `韩国申通`：物流用 `依然物流`。
  - 仓库名称包含 `韩国韵达`：物流用 `韩国韵达-韵达国际`。
- 不猜标记 ID。只有实例确认固定 ID 后，才使用 `JACKYUN_SAMPLE_ORDER_FLAG_ID` 和 `JACKYUN_RESEND_ORDER_FLAG_ID`。
- 涉及批次管理货品时，按最终仓库库存推荐/分配批次。默认策略为 FIFO 先进先出；用户提出效期、生产日期、指定/排除批次等要求时，先筛选符合要求的批次，再按 FIFO 自动分配。一个批次不够时自动拆分多个批次；总可用库存不足时才提示缺货。用户要求自选时，展示候选批次并等待确认。已确认的 `batchList` 视作用户指定批次。
- 库存不足默认阻断建单，避免错单；但用户明确要求“先建单，等有库存后匹配批次发货”时，可走 `allow_stock_shortage_create=True`。该模式创建待配批次单，不写不存在的批次，且强制不自动审核；后续必须在库存到货后匹配批次再审核/发货。
- 销售单创建成功后，必须立刻用 `oms.trade.fullinfoget` 反查并展示字段，包括仓库、物流、业务员、客户名、标记、货品、批次发货信息。
- Excel 批量导入支持官方销售单模板列名，如 `网店订单号`、`收货人`、`发货仓库`、`销售渠道名称`、`批次号`、`物流公司`、`业务员`、`标记`。表头匹配会归一化中英文括号、全角/半角、空格和大小写。
- 批量导入必须有业务员员工姓名。表格没有时，传 `default_seller_name`；寄样单还必须有 `客户名称`/`客户账号` 或 `default_customer_name`。
- 单个销售单快速创建也必须先走工作流预检；预检通过才创建。批量建单、陌生渠道/仓库、用户不确定字段时，显式调用 `run_sales_order_workflow(preflight_only=True)` 或 `modules.sales_order.preflight_sales_order()`；Excel/CSV 批量导入先调用 `batch_create_orders(..., dry_run=True)`，预览报告会返回阻断原因和解析后的仓库、物流、业务员、批次建议。

审核流：

- 寄样单：审核后进入审批流，审批通过后递交仓库。
- 普通手工单/补发单：审核后进入财务/FBP 复核，复核后递交仓库。
- 网店订单：可不走财务复核，直接递交仓库。

## 待审核网店订单处理

场景：平台订单已下载到 ERP，但自动审核策略没有通过，运营需要判断原因并处理。

默认流程：

1. 先执行 `run_pending_sales_order_workflow(action="diagnose")`，不要直接批量审核。
2. 诊断维度包括：缺货/批次库存不足、仓库缺失、物流缺失、退款/售后风险、无效货品、数量异常、收件信息缺失、库存诊断失败。
3. `audit_ready_trade_nos` 只表示当前诊断未发现阻断问题，仍需用户确认后再批量审核。
4. 缺货订单可选择等待库存、改正确仓库、拆单/换货品，不能直接伪造批次。
5. 仓库/物流错误先用 `batch_update_pending_trades_logistics_by_filter()` 或单据修改能力修正，再重新诊断。
6. 退款、售后、无效货品或收件信息异常的订单，必须先人工确认平台状态；需要取消/驳回时，按当前可用 API 和用户确认执行。

## 调拨单

规则：

- 使用 `erp.allocate.*`，不使用旧的 `erp.storage.transfer.*`。
- 申请公司默认“依然电商”。
- 申请人和部门来自默认操作人。
- 用户提供的调拨备注写入官方 `memo`。
- 调拨原因 `reason` 是数据字典值。先用 `erp.dictionary.page` 查询；只有用户明确确认后，才允许用 `erp.dictionary.save` 新增。
- 调拨明细 `unitName` 固定为 `Pcs`，不要从货品档案复制其他单位。
- 调拨单创建成功后，必须立刻用 `erp.allocate.get` 反查并返回新单据字段。
- 联系人字段应按仓库档案回填到 `stockAllocateExpressInfo.send*` 和 `stockAllocateExpressInfo.receive*`。
- 调拨明细支持官方 `batchList`。用户未指定批次时，`run_transfer_workflow()` 默认按调出仓批次库存执行 FIFO；如果用户提供批次、效期、排除批次、最少剩余效期等规则，则先按规则筛选，再按 FIFO 自动拆分多个批次。
- 调拨建单禁止手动拼 `erp.allocate.create` 绕过工作流。必须走 `run_transfer_workflow()`，因为批次自动选择在 `prepare_transfer_payload()` / `_auto_select_batches()` 链路里完成，手动拼 API 会跳过批次、字段校验、反查展示和经验记录。
- 调拨单库存不足默认阻断；如果用户明确要求“缺货也先建调拨单”，传 `allow_stock_shortage_create=True`。此时缺货明细只写 `isBatch=1`，不写不存在的 `batchList`；缺货数量写入 workflow 的 `auto_fill_summary.batches`，用于后续库存到货后补配批次。
- 同主体调拨使用 `allocateType=0`。
- 跨公司调拨使用 `allocateType=1`，若官方 API 要求价格/金额字段，必须补齐。
- 自定义主表字段 `field1` 到 `field10`、明细字段 `detailField1` 到 `detailField10`，只有官方文档和业务确认都允许时才透传。

## 入库/出库申请单

- 创建入口：`modules.workflows.run_stock_apply_workflow()`。
- 入库申请单接口：`erp.storage.stockincreate`。
- 出库申请单接口：`erp.storage.stockoutcreate`，请求体按官方要求包在 `bizdata`。
- 查询反查：`erp.stockin.get.v2` / `erp.stockout.get.v2`。
- 申请人必须由用户提供员工姓名，写入 `applyUserName`，同时默认写入 `operator`；不能让系统自动留空或随便猜。
- 入库/出库申请单创建成功后，工作流必须尽量按单号或 `relDataId` 反查新建单据并返回。
- 出库申请单如果用户没有指定批次，默认按出库仓批次库存 FIFO 自动生成 `batchList`；用户提供批次规则时，先筛选再 FIFO。入库申请单批次属于新入库批次，只有用户提供批次信息时才写入。
- 货品单位固定 `Pcs`。
- 缺申请人、仓库、类型、货品数量等字段时返回 `needs_input` 和 `stock_apply` 模板，不创建脏数据。

## 库存

支持能力：

- `erp.stockquantity.get` 库存查询，已支持 MCP。
- `erp.batchstockquantity.get` 批次库存查询。
- `erp-stock.stock.skulist` 分仓库存规格模式查询。
- 中文表头库存导出，可选附带批次明细。
- 仓库关键词批次库存报表：`run_warehouse_keyword_batch_stock_export_workflow()`。仓库包含/排除关键词由用户提供，不能硬编码。“分销组”只是一个已学习示例。
- 仓库关键词批次库存报表中，成本字段只有官方库存接口返回时才填写，否则留空。近 30 天销量来自 `threedayQuantity`，只有用户确认该业务口径时，才把空值填 0。

历史库存：

- 不猜接口名或日期字段。
- `query_historical_stock()` 只有在配置 `JACKYUN_STOCK_HISTORY_METHOD`，且方法与字段存在于官方 CLI JSON 中时才可用。

## 经营报表

货品销售多维分析：

- 官方接口：`birc.report.needauth.goodsMultiDimensionalAnalysis`。
- 官方机器可读文档缓存：`docs/jackyun_cli_docs/birc.report.needauth.goodsMultiDimensionalAnalysis.json`。
- 吉智BI兜底接口：`udr.openapi.userdefinedreport`，官方机器可读文档缓存：`docs/jackyun_cli_docs/udr.openapi.userdefinedreport.json`。
- 工作流入口：`run_goods_sales_analysis_workflow()`。
- 查询封装：`modules.reports.query_goods_sales_analysis()`。
- 导出封装：`modules.reports.export_goods_sales_analysis_report()`。
- 常见场景：查询某个月、某些渠道下所有货品的销售额、销量、发货量、退货量、退款金额、成本、毛利和毛利率。
- 渠道销售数量/金额汇总优先走 `run_channel_sales_summary_workflow()`。如果用户只要数量和金额，默认不要逐页拉销售单后本地汇总；底层仍用销售多维分析报表，维度可选 `channel`、`channel_goods`、`channel_daily`、`channel_goods_daily`。
- 用户说“渠道包含某关键词”时，先用全量渠道缓存/API 找到渠道并转成 `shopIds`，再传给报表接口；不能用销售单明细做本地渠道过滤。
- 用户说“昨天、本月、上月”时，工作流可用 `period` 转换为官方 `startTime/endTime` 或 `month`；默认 `filterTimeType=2` 表示按发货时间。
- 用户说“发货在途或者已完成”时，报表接口侧按官方 `tradeStatus=6000` 已发货口径处理；如果业务确认还需其他状态，再显式传入状态码。
- 用户提供渠道名称时，先用渠道缓存/API 解析为 `shopIds`，不能把渠道名称直接传给报表接口。
- `month="YYYY-MM"` 可自动转换为官方 `startTime/endTime=YYYY-MM`，并使用 `timeType=2` 按月统计；日期范围使用 `startTime/endTime=YYYY-MM-dd` 和 `timeType=3`。
- 默认 `summaryType="channel,goods"`，用于按渠道+货品汇总；如果用户要求按规格、时间、仓库、业务员等维度，必须让用户明确 `summaryType`。
- 默认 `filterTimeType=2`，按发货时间统计；下单时间为 1，付款时间为 3。
- 导出列来自官方 response schema，不能只导出销售额和销量两个字段；用户要求“所有字段”时必须包含官方 JSON 中列出的全部字段。
- 如果修正官方参数后接口仍返回空，但 ERP 前台确认有数据，优先检查当前 Skill 运行 AppKey 是否与已订阅/授权报表的应用一致，以及该应用是否具备对应公司、部门、渠道的数据权限。
- `birc.report.needauth.goodsMultiDimensionalAnalysis` 返回 0 时不能直接上线交付空表。当前已知原因通常不是签名，而是报表数据权限/应用授权范围/报表口径不一致。工作流会给出警告，并可在配置 `JACKYUN_CHANNEL_SALES_UDR_REPORT_ID` 或传入 `udr_report_id` 后，自动改用 `udr.openapi.userdefinedreport` 兜底。
- `udr.openapi.userdefinedreport` 必须传 `reportId` 和 `filterKeyValueJson`。默认筛选键按官方示例生成：`timeType=consign_time`、`shopId=渠道ID逗号串`、`date_key=开始日期,结束日期`，状态会传 `tradeStatus`。如果吉智BI自定义报表的筛选键不同，调用时通过 `udr_filters` 显式覆盖/补充，不能猜字段。
- 吉智BI报表必须在报表侧支持开放平台查询；否则接口会返回“当前报表不支持开放平台查询”。遇到该错误时，让 IT 打开该报表的开放平台查询能力或提供正确的报表 ID。

## 基础资料缓存

用户、部门、公司、渠道、仓库、物流、货品、数据字典优先查本地缓存。缓存不存在或过旧时，再调用对应吉客云 API。

发布前运行 `python scripts/refresh_master_cache.py` 刷新仓库、渠道、货品、用户缓存。基础资料匹配会归一化中英文括号、全角/半角、空格和大小写。

禁止用窄查询结果覆盖全量基础资料缓存。按名称/编号精确查询可以调 API，但不能把局部结果保存成 `data/cache/{master}.json`。

“包含关键词 / 排除关键词”类需求必须优先用全量缓存；缓存疑似不完整时，先全量分页刷新再过滤。仓库关键词查询使用 `modules.warehouse.search_warehouses_by_keywords()`，它会处理 `除外贸组和分销组` 这类否定表达。

仓库单条解析同样要防止“只查第一页”的问题。销售单、调拨单、出入库单只要需要按仓库名称或仓库编号补全字段，都必须走 `modules.warehouse.get_warehouse_by_name()` / `get_warehouse_by_code()`；当缓存条数异常偏少或首次未命中时，公共函数会自动全量分页刷新后再匹配，不能在业务模块里临时调用 `query_warehouses(page_index=0)` 后直接判定不存在。

## CLI 兜底与签名

不要在临时 Python/Node 脚本中重写吉客云签名。需要直连签名 HTTP 时，使用可复用签名 helper：

```python
from helpers.jackyun_signature import build_signed_openapi_params, generate_openapi_sign

params = build_signed_openapi_params(
    method="erp.warehouse.get",
    bizcontent={"pageIndex": 0, "pageSize": 100},
)
```

官方 HTTP client 已调用这个 helper，并自动包含 `appkey`、`version`、`contenttype`、时间戳和 MD5 签名规则；CLI 兜底则交给 `jky-cli` 自动签名。

打包 CLI 可能包含平台特定可执行文件名，例如 `jky-cli-darwin-arm64`；`helpers.jkyun_cli.ensure_cli_executable()` 会自动识别并解压到 `data/runtime/jkyuncli/`。

`helpers.jkyun_cli.call_cli()` 会在 skill 运行目录中自动配置凭证，用户不需要手动 echo 凭证。

## 工作流入口

优先使用工作流入口：

- `modules.workflows.run_sales_order_workflow()`
- `modules.workflows.run_pending_sales_order_workflow()`
- `modules.workflows.run_transfer_workflow()`
- `modules.workflows.run_stock_doc_workflow()`
- `modules.workflows.run_stock_apply_workflow()`
- `modules.workflows.run_delivery_note_export_workflow()`
- `modules.workflows.run_inventory_export_workflow()`
- `modules.workflows.run_goods_sales_analysis_workflow()`
- `modules.workflows.run_channel_sales_summary_workflow()`
- `modules.workflows.run_warehouse_keyword_batch_stock_export_workflow()`
- `modules.workflows.run_misc_workflow()`

除非是调试或扩展代码，不要在对话中直接拼底层 API payload。

已学习踩坑：曾因手动拼 `erp.allocate.create` 导致调拨单没有选择批次。后续凡是“根据单据模板/表格明细创建调拨单、销售单、出库单、出库申请单”等场景，先调用 `get_workflow_catalog()` 选择稳定 action，再走 `run_fast_workflow()` 或对应 `run_*_workflow()`；不要重新写签名、分页、批次选择和字段映射代码。

面向 OpenClaw、Work Buddy 或其他类产品时，优先使用 `modules.workflows.get_workflow_catalog()` 和 `run_fast_workflow(action, **kwargs)`。稳定 action 包括：`sales_order_create`、`transfer_create`、`stock_apply_create`、`channel_sales_summary`、`goods_sales_analysis`、`inventory_export`。这样可以减少模型每次重复写临时脚本、重复猜接口字段、重复实现分页/签名/批次逻辑。

大数据量规则：能用报表接口聚合的，不拉销售单明细。只有用户明确需要逐单明细，或报表接口无法提供字段时，才允许走销售单查询；这类查询必须严格限制时间、渠道、状态、字段，并优先采用分页/批量并发策略。

## 模板文件工作流

通用规则：用户基于吉客云数据生成 Excel/PDF/Doc 模板文件时，不要把它写成一次性逻辑，除非用户明确要求单独 skill。应抽取以下可复用部分：

- API 查询契约，尤其是必要 `fields`，如 `goodsDetail.*`。
- 模板文件路径。
- 可写单元格和合并单元格左上角。
- 明细起止行、溢出插行、样式复制、汇总公式。
- 列映射和必须留空的单元格/列。
- 文件命名来源字段，必须和展示单元格分离。

已学习的申通仓出库单工作流位于 `modules.delivery_note` 和 `run_delivery_note_export_workflow()`。它是“销售单到 Excel 模板”的通用模式，默认带一个申通模板，不代表所有出库单都必须按申通规则。

当用户完成新的稳定吉客云工作流、模板或报表后，必须提醒用户做复用决策。默认建议单独打包成新 skill，因为当前 `jackyun-erp` skill 可能由 IT 同事持续优化、频繁更新；用户自定义流程如果直接放进当前 skill，卸载重装或覆盖安装时容易丢失。

- 优先单独打包成新 skill：适合固定部门、供应商、客户模板、固定报表或独立交付物，便于独立安装、升级和备份。
- 少数情况下集成进当前 `jackyun-erp` skill：仅适合通用 ERP 基础能力，复用共享吉客云模块，并且用户明确确认要随 ERP skill 一起维护。

## 产品与工程评审

产品侧：

- 通过 `execution_plan` 让调用通道可见，但用户界面仍以业务语言呈现。
- 查询类能力可积极使用 MCP。
- 写操作仍必须完整校验字段并确认意图。
- 不要宣称所有 API 都走 MCP；只有 MCP 允许列表中的方法才可走 MCP。

工程侧：

- 调用通道路由集中在 `jackyun_api.py`。
- `helpers/runtime_plan.py` 只读，只做可视化，不执行调用。
- `docs/jackyun_mcp_tools.json` 视为 MCP 允许列表。
- `docs/jackyun_cli_docs/` 视为字段契约。
- 未来 MCP 写接口启用时，注意跨通道兜底可能造成重复写：超时后服务端可能已成功，除非官方 API 支持幂等，否则不能盲目重试。

## 文档维护规则

当前活跃 Markdown 文档只保留：

- `SKILL.md`：简洁的 skill 触发和操作规则。
- `docs/PROJECT_MANUAL.md`：完整项目手册。
- `docs/USER_SOP.md`：业务同事使用 SOP。
- `ARCHITECTURE.md`：架构图谱。
- `CHANGELOG.md`：版本历史。
- `OPENAPI_METHOD_CATALOG.md`：生成/历史 API 目录。

更早的零散说明已合并到本手册。

## Obsidian 知识库同步

Obsidian vault 路径：

- `/Users/li/Documents/obsidian/li`

当前项目记忆笔记：

- `/Users/li/Documents/obsidian/li/10 Projects/吉客云 ERP Skill/吉客云 ERP Skill 项目记忆.md`

维护规则：

- 每次对本项目做功能更新、规则更新、打包发布或重要修复后，都要同步更新 Obsidian 项目记忆。
- Obsidian 记录项目定位、当前版本、最新包路径、关键能力、重要业务规则、近期版本摘要和维护检查项。
- Obsidian 是面向人读的长期知识库，不写入 API 密钥、token、secret、个人 profile 或运行期临时数据。
