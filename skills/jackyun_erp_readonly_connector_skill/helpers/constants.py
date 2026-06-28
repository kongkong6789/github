"""
吉客云业务常量定义

包含出入库类型、审核状态、结算方式等枚举映射，
供各业务模块统一引用。
"""

# ==================== 出入库类型 ====================
INOUT_TYPES = {
    101: "采购入库",
    102: "调拨入库",
    103: "盘盈入库",
    104: "其他入库",
    105: "生产入库",
    106: "退货入库",
    201: "销售出库",
    202: "调拨出库",
    203: "盘亏出库",
    204: "其他出库",
    205: "生产领料出库",
}

# ==================== 单据审核状态 ====================
CHECK_STATUS = {
    0: "未审核",
    1: "已审核",
    2: "已复核",
    3: "已递交",
    4: "已完成",
    -1: "已取消",
}

CHECK_STATUS_REVERSE = {v: k for k, v in CHECK_STATUS.items()}

# ==================== 结算方式 ====================
CHARGE_TYPES = {
    1: "担保交易",
    2: "银行收款",
    3: "现金收款",
    4: "货到付款",
    5: "欠款计应收",
    6: "客户预存款",
    7: "多种结算",
}

CHARGE_TYPE_REVERSE = {v: k for k, v in CHARGE_TYPES.items()}

# ==================== 销售单状态（oms.trade.fullinfoget 返回的 tradeStatus） ====================
TRADE_STATUS = {
    1010: "待审核",
    1020: "审核中",
    1050: "已审核",
    3010: "已发货",
    6000: "已完成",
    9090: "已取消",
    5010: "已退货",
    # 旧版兼容
    0: "待审核",
    1: "已审核",
    2: "已发货",
    3: "已完成",
    4: "已取消",
    5: "已退货",
}

# ==================== 物流公司编码（常用） ====================
LOGISTICS_CODES = {
    "SF": "顺丰速运",
    "YTO": "圆通速递",
    "ZTO": "中通快递",
    "STO": "申通快递",
    "YUNDA": "韵达快递",
    "JD": "京东物流",
    "EMS": "邮政EMS",
    "HTKY": "百世快递",
    "DBL": "德邦物流",
    "JTSD": "极兔速递",
}

# ==================== API 方法名常量 ====================

# 货品
METHOD_GOODS_SKU_SEARCH = "erp-goods.goods.sku.search"
METHOD_STORAGE_GOODS_LIST = "erp.storage.goodslist"
METHOD_GOODS_BATCH_INFO_GET = "erp.goodsbatchinfo.get"
METHOD_GOODS_CATE_GET = "erp.goodscate.get"
METHOD_GOODS_ADD = "erp.goods.add"
METHOD_GOODS_UPDATE = "erp.goods.update"

# 库存
METHOD_STOCK_GET = "erp.stock.get"
METHOD_STOCK_BATCH_GET = "erp.stock.batch.get"
METHOD_STOCK_ADJUST = "erp.stock.quantityadjust"
METHOD_STOCK_ADJUST_UNIT = "erp.stock.quantityadjustbyunitname"
METHOD_STOCK_CREATE_IN = "erp.stock.createandstockin"
METHOD_STOCK_QUANTITY_GET = "erp.stockquantity.get"                # 库存分页查询（官方）
METHOD_BATCH_STOCK_QUANTITY_GET = "erp.batchstockquantity.get"   # 批次库存查询（含效期）
METHOD_SKU_STOCK_LIST = "erp-stock.stock.skulist"               # 分仓库存查询(规格模式)
METHOD_STOCK_HISTORY_GET = ""                                   # 历史库存官方方法名；未确认前保持空

# 仓库
METHOD_WAREHOUSE_GET = "erp.warehouse.get"

# 用户
METHOD_USER_SEARCH = "erp.user.search"
METHOD_DEPART_QUERY = "erp.depart.query"
METHOD_COMPANY_QUERY = "erp.company.query"

# 渠道 / 客户
METHOD_CHANNEL_GET = "erp.sales.get"

# 物流档案（已确认订阅 2026-04-04）
METHOD_LOGISTIC_GET = "erp.logistic.get"

# 供应商
METHOD_VENDOR_GET = "erp.vend.get"

# ==================== 销售单 API（全部已确认订阅 2026-04-02） ====================
METHOD_TRADE_GET = "oms.trade.fullinfoget"                          # 销售单查询
METHOD_TRADE_ADD = "oms.trade.ordercreate"                          # 销售单创建
METHOD_TRADE_COUNT = "oms.trade.countget"                           # 销售单总数查询
METHOD_TRADE_AUDIT_PASS = "oms.trade.audit.pass"                    # 销售单审核通过
METHOD_TRADE_REJECT = "oms.open.trade.audit.reject"                 # 销售单驳回审核
# [已禁用] METHOD_TRADE_REAUDIT = "oms.trade.order.reAudit"                    # 销售单复核（财务权限，API已取消订阅）
METHOD_TRADE_COMPLETE_DELIVERY = "oms.trade.order.completeDelivery" # 销售单完成发货
METHOD_TRADE_UPDATE_LOGISTICS = "oms.trade.order.batchUpdateLogisticWarehouse"  # 修改仓库/物流
METHOD_TRADE_LOG = "oms.trade.orderloglist"                         # 销售单日志列表
METHOD_TRADE_PACKAGE = "oms.trade.package.querylist"                # 订单包裹查询
METHOD_TRADE_BATCH_UPDATE_GOODS_BATCH_NO = "oms.trade.batchUpdateGoodsBatchNo"  # 修改销售单货品批次

# 网店订单 (fullinfoget 可同时查线上线下单)
METHOD_SHOP_ORDER_GET = "oms.trade.fullinfoget"

# 出入库单
METHOD_DOC_OUT = "erp.storage.goodsdocout.v2"
METHOD_DOC_IN = "erp.storage.goodsdocin.v2"
METHOD_DOC_OUT_ADD = "erp.storage.goodsdocout.add"
METHOD_DOC_IN_ADD = "erp.storage.goodsdocin.add"
METHOD_DOC_CHECK = "erp.storage.goodsdoc.check"
METHOD_STOCK_IN_APPLY_CREATE = "erp.storage.stockincreate"
METHOD_STOCK_OUT_APPLY_CREATE = "erp.storage.stockoutcreate"
METHOD_STOCK_IN_APPLY_GET = "erp.stockin.get.v2"
METHOD_STOCK_OUT_APPLY_GET = "erp.stockout.get.v2"

# 调拨单
METHOD_TRANSFER_GET = "erp.allocate.get"
METHOD_TRANSFER_CREATE = "erp.allocate.create"
METHOD_TRANSFER_QUICK_CREATE = "erp.allocate.quick.create"
METHOD_TRANSFER_CLOSE = "erp.allocate.close"
METHOD_TRANSFER_COMPLETE = "erp.allocate.complete"

# 数据字典
METHOD_DICTIONARY_PAGE = "erp.dictionary.page"
METHOD_DICTIONARY_SAVE = "erp.dictionary.save"
METHOD_DICTIONARY_UPDATE = "erp.dictionary.update"

# 组合单
METHOD_COMBINED_GET = "erp.combined.get"

# 财务
METHOD_FINANCE_SALES_SUMMARY = "erp.finance.summary.sales"
METHOD_FINANCE_GOODS_SUMMARY = "erp.finance.summary.goods"
METHOD_GOODS_SALES_ANALYSIS = "birc.report.needauth.goodsMultiDimensionalAnalysis"
METHOD_USER_DEFINED_REPORT = "udr.openapi.userdefinedreport"
