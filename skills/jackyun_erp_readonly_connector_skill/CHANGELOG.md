# 变更记录

## 2026.05.19.1

- 修复调拨单缺货先建单链路：`run_transfer_workflow(..., allow_stock_shortage_create=True)` 现在会透传到 `prepare_transfer_payload()` / `_auto_select_batches()`。
- 调拨单未指定批次时继续按调出仓 FIFO 自动生成 `batchList`；如果总库存不足且用户明确允许先建单，则缺货明细只写 `isBatch=1`，不写不存在的 `batchList`，缺货数量返回在 `auto_fill_summary.batches`。
- 新增回归测试覆盖调拨缺货先建、workflow 参数透传和自动批次保护。
- 文档补充踩坑规则：调拨单、销售单、出库单/申请单建单必须优先走工作流，禁止手动拼底层创建 API 绕过批次、预检、反查和经验记录。

## 2026.05.13.3

- 新增吉智BI自定义报表接口 `udr.openapi.userdefinedreport` 的官方 CLI JSON 缓存和通用查询封装 `query_user_defined_report()`。
- 渠道销售数量/金额汇总工作流新增自定义报表兜底：当 `birc.report.needauth.goodsMultiDimensionalAnalysis` 返回 0 行且配置了 `JACKYUN_CHANNEL_SALES_UDR_REPORT_ID` 或传入 `udr_report_id` 时，自动改用吉智BI自定义报表查询。
- 明确上线保护：多维报表返回 0 且未配置吉智BI `reportId` 时，工作流返回警告，不能把空结果当作可用结果交付。
- 记录实测原因：`udr.openapi.userdefinedreport` 必须使用已支持开放平台查询的自定义报表 ID；使用不支持开放平台查询的报表会返回“当前报表不支持开放平台查询”。

## 2026.05.13.2

- 渠道销售数量/金额汇总工作流新增渠道关键词筛选：支持 `channel_include_keyword="分销组"`，先从全量渠道缓存/API 解析为 `shopIds`，再下推给报表接口。
- 新增常用时间口径 `period`：支持“昨天 / 今天 / 本月 / 上月”，自动转换为官方 `startTime/endTime` 或 `month`。
- 新增日销维度：`channel_daily`、`channel_goods_daily`，可按渠道日销或渠道+货品日销汇总数量和金额。
- 新增订单状态口径归一化：用户说“发货在途或者已完成”时，报表接口按官方 `tradeStatus=6000` 已发货口径传参。
- 实测“昨天发货、渠道包含分销组、按渠道维度”请求：匹配到 144 个渠道，已把 `shopIds`、发货时间、状态和汇总维度全部下推给 `birc.report.needauth.goodsMultiDimensionalAnalysis`；当前 AppKey 仍返回空数据，需继续核对该应用报表数据权限。

## 2026.05.13.1

- 新增入库/出库申请单工作流 `run_stock_apply_workflow()`，对接 `erp.storage.stockincreate` / `erp.storage.stockoutcreate`，并缓存官方 CLI JSON 文档。
- 入库/出库申请单申请人强制写入用户提供的员工姓名 `applyUserName`，并默认同步到 `operator`；缺申请人、仓库、类型、货品数量时返回 `needs_input` 和模板，不创建脏数据。
- 出库申请单支持未手填批次时按出库仓批次库存 FIFO 自动拆分 `batchList`；用户提供批次/效期规则时先筛选再 FIFO。
- 调拨工作流文档补强：明确调拨明细支持官方 `batchList`，默认按调出仓 FIFO 自动选批次，单批次不够可拆多批。
- 新增渠道销售数量/金额汇总工作流 `run_channel_sales_summary_workflow()`，基于货品销售多维分析报表，支持按渠道或渠道+货品维度汇总数量和金额。
- 新增 `get_workflow_catalog()` / `run_fast_workflow()` 快速入口，方便 OpenClaw / Work Buddy 等类产品直接调用稳定工作流，减少重复临时写代码和重复猜字段。

## 2026.05.12.2

- 用 Chrome 访问吉客云开放平台测试工具复核 `birc.report.needauth.goodsMultiDimensionalAnalysis`，修正货品销售多维分析报表的官方请求字段：`startTime`、`endTime`、`timeType`、`summaryType`、`startFinReceiptTime`、`endFinReceiptTime`。
- 修正 `month="YYYY-MM"` 的月统计请求：按官方格式传 `startTime=endTime=YYYY-MM`、`timeType=2`，默认 `summaryType="channel,goods"`。
- 同步更新官方 CLI JSON 缓存、Skill 说明和项目手册，避免后续继续使用 `queryTimeBegin/queryTimeEnd/summaryTypes` 旧字段踩坑。
- 报表返回空数据时新增诊断提示：若 ERP 前台确认有销量，优先核对当前 Skill 的 AppKey 是否为已订阅且具备对应公司/部门/渠道数据权限的应用。

## 2026.05.12.1

- 新增货品销售多维分析报表接口：`birc.report.needauth.goodsMultiDimensionalAnalysis`。
- 新增官方 CLI JSON 缓存：`docs/jackyun_cli_docs/birc.report.needauth.goodsMultiDimensionalAnalysis.json`，请求/响应字段以官方 schema 为准。
- 新增 `modules.reports`：支持按 `month` 或日期范围查询，渠道名称自动解析为 `shopIds`，默认按渠道+货品汇总，分页拉取并返回/导出所有官方响应字段。
- 新增工作流 `run_goods_sales_analysis_workflow()`，可直接查询或导出 CSV/XLSX/TSV，默认中文表头。
- 更新中文 SOP、项目手册和 Skill 说明，补充“某月某些渠道所有货品销售额和销量”场景。

## 2026.05.11.2

- 新增 Obsidian 项目记忆笔记：`/Users/li/Documents/obsidian/li/10 Projects/吉客云 ERP Skill/吉客云 ERP Skill 项目记忆.md`。
- 项目手册新增 Obsidian 知识库同步规则：后续功能更新、规则更新、打包发布或重要修复后，应同步更新该知识库笔记。

## 2026.05.11.1

- 销售单查询 `oms.trade.fullinfoget` 的默认 `fields` 补齐货品明细字段：新增 `goodsDetail.cost`、折扣、税额、重量、货品备注、分类、品牌、标签、组合装/赠品/预售标记、终端销售价/金额、交易货品、平台子订单和平台商品明细等字段。
- 新增 `DEFAULT_GOODS_DETAIL_FIELDS` 集中维护销售单货品明细查询字段，避免后续遗漏 `goodsDetail.*`。
- 新增回归测试，确保默认销售单查询字段包含本次要求的完整 `goodsDetail.*` 字段。

## 2026.05.10.5

- 销售单新增“库存不足先建待配批次单”受控模式：用户明确允许时可 `allow_stock_shortage_create=True`，不写不存在的批次，并强制不自动审核，后续待库存到货后再匹配批次审核发货。
- 新增待审核网店订单诊断：`run_pending_sales_order_workflow(action="diagnose")` 会按缺货/批次库存不足、仓库物流异常、退款售后风险、无效货品、收件信息缺失等原因分组，并返回可审核候选。
- 更新中文 SOP 和项目手册，补充库存不足先建单与待审核订单处理流程。

## 2026.05.10.4

- 新增建单防脏数据硬拦截：销售单工作流默认先预检，预检失败返回 `needs_input`、缺失项和销售单模板，不调用创建接口。
- 调拨单、出入库单工作流在字段校验失败时也返回 `needs_input` 和对应模板，避免底层异常后继续猜参数重试创建。
- 新增 `modules.workflows.record_workflow_correction()`：用户纠正错误后记录问题、根因、防错规则和正确字段，并同步更新销售单常用字段/批次策略偏好。
- 销售单预检会展示最近同类纠错提示，帮助后续建单前主动规避已踩过的坑。
- 更新中文 SOP 和项目手册：明确“信息不完整不建单、先给模板、纠错后重新预检”的使用规则。

## 2026.05.10.3

- 批次推荐默认策略改为 FIFO 先进先出：未指定批次时优先使用生产日期更早的批次。
- 批次推荐支持用户条件筛选后再 FIFO：支持指定批次、批次包含、包含/排除批次列表、生产日期范围、到期日期范围、最少剩余有效天数。
- 销售单、调拨单、出库单的自动批次分配统一支持单批次不够时自动拆分多个批次生成 `batchList`；只有总可用库存不足才阻断。
- 新增用户习惯记录：成功建单后会在本地 `data/profile.json` 记录常用渠道、仓库、物流、业务员、客户等计数，用于后续预检提示和更少确认。
- 销售单工作流默认进入快速建单模式：字段明确时自动 FIFO 选批次并创建；批量、陌生资料或不确定字段再使用预检模式。

## 2026.05.10.2

- 新增销售单建单前预检：`modules.sales_order.preflight_sales_order()` 可在不创建单据的情况下校验渠道、仓库、物流、业务员/登记人、客户名称、金额、批次库存，并返回最终会写入的仓库/物流/业务员摘要。
- `run_sales_order_workflow()` 新增 `preflight_only=True`，适合同事先用一句话做建单体检，再确认创建。
- 批量导入 `dry_run=True` 升级为建单体检报告：预览时会执行销售单预检，展示阻断原因和解析结果，避免批量创建时才发现渠道/仓库/批次/业务员错误。
- 批量创建移除每单固定 0.5 秒额外等待，改为可选 `create_interval`；底层 API client 仍保留统一节流与重试，批量处理更快。
- 新增回归测试覆盖销售单预检、批量导入预检通过和预检阻断场景。

## 2026.05.10.1

- 修复仓库基础资料漏查问题：按仓库名称/编号解析时，如果本地缓存只有第一页或缓存较旧，首次未命中会自动全量分页刷新后再匹配，避免 `YRMG04` 这类后页仓库被误判为不存在。
- 将同类保护扩展到销售单、调拨单、出入库单共用的仓库解析入口；渠道、物流、货品候选、用户全量查询也增加缓存完整性防线。
- 提高发布前基础资料刷新校验阈值，拒绝把明显偏少的第一页结果打包成全量缓存。
- 修复 Python 3.9 兼容性：销售单/调拨模块启用延迟类型注解，经验记录时间戳不再使用 Python 3.11 才有的 `datetime.UTC`。
- 新增回归测试，覆盖“缓存只有第一页时仍能通过全量分页刷新找到后页仓库”的场景；当前 `python3 -m unittest discover -s tests` 通过 120 个测试。

## 2026.05.07.1

- 调整新工作流沉淀策略：用户基于吉客云形成的新稳定工作流、模板或报表，默认建议单独打包成新 skill，避免当前 `jackyun-erp` 被 IT 持续更新或重装时覆盖用户自定义内容；只有通用 ERP 基础能力且用户确认时才并入当前 skill。

## 2026.04.29.1

- 统一 MCP 授权 AppKey 与现有吉客云 HTTP AppKey。
- `JACKYUN_AUTHORIZED_APP_KEY` 默认跟随 `JACKYUN_APP_KEY`，避免维护两套 AppKey。
- 在本地环境用新的 MCP token 验证库存查询；token 不写入源码或文档。
- 新增 `scripts/refresh_master_cache.py`，发布前可刷新随包携带的仓库、渠道、货品、用户基础资料缓存。
- 增强基础资料名称匹配：统一处理中英文括号、全角/半角、空格和大小写。
- 发布包开始携带 `data/cache/*.json` 基础资料缓存，同时继续排除 profile、experiences、runtime 等本地运行状态。
- 销售单创建时，将已确认员工实名同时写入 `sellerName` 和 `registerName`。
- Excel 批量销售单导入支持官方模板表头，包括 `网店订单号`、`收货人`、`发货仓库`、`销售渠道名称`、`批次号`、`物流公司`、`业务员`、`标记`。
- 批量导入支持 `default_seller_name` 和 `default_customer_name`，便于官方模板缺少对应单元格时先完成校验；寄样单仍要求客户名称。
- 批量导入创建时保留 `onlineTradeNo`、`buyerMemo`、`sellerMemo`、`batchNo`、仓库、物流、业务员、客户字段，并在创建后反查新销售单到 `created_trade`。
- 新增 `docs/USER_SOP.md`，面向业务同事说明常用指令、销售单创建、Excel 批量导入、批次库存、调拨、查询/审核流程和禁止事项。
- 修复 Python 3.9 兼容性：本地状态时间戳从 `datetime.UTC` 改为 `timezone.utc`。
- 防止窄范围基础资料查询覆盖全量缓存；刷新脚本遇到异常偏少结果会拒绝写入。
- 新增 `modules.warehouse.search_warehouses_by_keywords()`，支持基于全量缓存/API 的仓库关键词查询、包含/排除规则，以及 `除外贸组和分销组` 这类否定语境。
- 修复随包 CLI 在不同平台的可执行文件名识别问题，并在调用 CLI 前自动完成运行期凭证配置。
- 新增公共签名 helper：`helpers/jackyun_signature.py`。直连签名 HTTP 可复用 `build_signed_openapi_params()` / `generate_openapi_sign()`，无需重新实现签名。
- 将“分销组库存导出”经验抽象为 `run_warehouse_keyword_batch_stock_export_workflow()`，仓库关键词、排除关键词、销量空值处理都由用户需求提供，不硬编码 `分销组`。
- 新增通用“销售单转 Excel 模板出库单”能力：`modules.delivery_note` 和 `run_delivery_note_export_workflow()`；默认随包携带申通仓模板配置。
- 新增工作规则：用户基于吉客云形成新的稳定工作流、模板或报表后，必须提醒用户做复用沉淀选择。

## 2026.04.28.4

- 使用真实 MCP token 在本地验证 `erp.stockquantity.get`。
- 修复 MCP 响应规范化：将 `content.text` 载荷转换为业务模块期望的 `code/result/data` 结构。
- 新增 `tests/test_mcp_runtime.py`，覆盖嵌套 MCP content 规范化。
- 将零散 Markdown 指南合并到 `docs/PROJECT_MANUAL.md`。
- 合并后移除过时或重复的 Markdown 指南。

## 2026.04.28.3

- 新增工作流级 `execution_plan` 输出，让高频工作流可展示预计 MCP/CLI/HTTP 路由。
- 新增 `helpers/runtime_plan.py`，集中维护路由可视化，不重复执行逻辑。
- 新增 `scripts/diagnose_runtime.py`，用于环境和工作流路由诊断。
- 增加产品与工程优化评审，后续合并到 `docs/PROJECT_MANUAL.md`。
- 更新 `SKILL.md`、`ARCHITECTURE.md` 和整合手册中的 MCP/CLI 工作流说明。

## 2026.04.28.2

- 对 `docs/jackyun_mcp_tools.json` 中列出的官方 MCP 工具，新增 MCP 优先运行路由。
- 新增官方 CLI 兜底 wrapper，并在 `tools/jkyuncli/` 打包 Windows/macOS CLI 压缩包。
- 新增 MCP/CLI 运行文档和 Windows/macOS 安装检查脚本，后续合并到 `docs/PROJECT_MANUAL.md`。
- 临时记录过独立 MCP 授权 AppKey，已在 `2026.04.29.1` 统一回 `JACKYUN_APP_KEY`。
- 除非 `JACKYUN_CALL_STRATEGY` 强制 `mcp` 或 `cli`，直连签名 HTTP 仍作为兼容兜底。

## 2026.04.28.1

- 接入吉客云官方 CLI 机器可读文档目录：`docs/jackyun_cli_docs/methods-index.json`
- 新增本地状态与缓存目录：`data/profile.json`、`data/cache/`、`data/templates/`、`data/experiences/`
- 新增默认操作人机制：首次建单需提供姓名，后续创建人、申请人、业务员优先复用本地默认操作人
- 调拨单创建修正：
  - 申请公司默认按 `JACKYUN_DEFAULT_APPLICATION_COMPANY_NAME`，默认值为“依然电商”
  - 申请人部门按默认操作人在吉客云用户/部门档案中解析
  - `reason` 调拨原因按官方 `erp.dictionary.page` 校验，可确认后用 `erp.dictionary.save` 新增
  - 用户提供的调拨备注写入官方 `memo` 字段
- 销售单创建修正：
  - 区分官方字段 `buyerMemo`（买家备注）和 `sellerMemo`（备注）
  - 寄样单/补发单新增官方 `tradeOrderFlags` 标记，不再只依赖备注文本
- 新增模板模块：`modules/templates.py`，支持销售单、调拨单、库存查询模板
- 新增历史库存受控入口：未在官方 CLI 目录发现明确方法前不猜接口；需配置 `JACKYUN_STOCK_HISTORY_METHOD` 且字段存在于官方 method JSON 后才允许调用
- 新增/更新回归测试，当前 `python -m unittest discover -s tests` 通过 89 个测试

## 2026.04.14.1

- 新增吉客云官方文档批量抓取脚本：`scripts/fetch_jackyun_openapi_docs.py`
- 已预抓取项目当前使用的 103 个接口文档，缓存到 `dist/jackyun_project_docs`
- 修复调拨单联系人字段：按官方 `stockAllocateExpressInfo.send* / receive*` 回填仓库联系人与地址
- 新增库存导出能力：
  - 基于官方 `erp.stockquantity.get`
  - 默认导出中文表头
  - 支持 `.csv` / `.tsv` / `.xlsx` / `.xlsm`
  - 支持可选批次明细附件导出
- 新增库存导出 workflow：`run_inventory_export_workflow()`
- `SKILL.md` 已补充库存导出调用示例、是否附带批次明细的说明，以及企业微信智能表格 / 文档 MCP / webhook 写入需用户自行对接的边界说明

## 2026.04.13.1

- 新增销售单待审核运营入口：
  - `list_pending_trade_candidates`
  - `summarize_pending_shop_orders`
  - `batch_audit_pending_trades_by_filter`
  - `batch_update_pending_trades_logistics_by_filter`
- 销售单审核改为按官方 `oms.trade.audit.pass` 的 `tradeNos` 格式调用
- 新增渠道模糊候选：`modules.channel.suggest_channels`
- 新增货品模糊候选：`modules.goods.suggest_goods`
- 已集成调拨、组装拆卸/组合装、售后、财务能力
## 2026.04.16.1

- 修复销售单多批次分配：单个批次不足时会按推荐结果自动生成 `batchList`，不再错误提示缺货。
- 新增出库单自动批次分配：按仓库批次库存自动拆分多个批次。
- 普通手工销售单新增赠品规则：显式 `isGift=1` 时允许 `sellPrice=0` / `sellTotal=0`。
- 普通手工销售单新增金额一致性校验：`sellTotal` 缺失时自动回算，传入错误金额时建单前拦截。
- 新增回归测试，覆盖销售单多批次、赠品零金额、金额校验、出库单多批次。
- workflow 日志增强：流程跑通或卡住后，会自动写入结构化 `FEEDBACK_LOG.jsonl`，新增 `input_summary`、`steps`、`pain_points`、`reuse_hints`、`auto_fill_summary` 字段，方便下次快速复用。
