"""
User-facing payload templates for common operations.
"""
from __future__ import annotations

from copy import deepcopy


SALES_ORDER_TEMPLATE = {
    "order_type": "sample | resend | manual",
    "shop_name": "销售渠道名称",
    "warehouse_name": "仓库名称，建议提供；不提供时按渠道默认仓库自动匹配",
    "logistic_name": "物流名称，可空；默认根据最终仓库自动匹配",
    "seller_name": "业务员/创建人姓名，首次必须提供，后续可复用本地默认操作人",
    "customer_name": "客户名称；寄样单必填，普通/补发可按业务需要填写",
    "receiver_name": "收件人姓名",
    "mobile": "手机号",
    "state": "省",
    "city": "市",
    "district": "区县",
    "address": "详细地址",
    "buyerMemo": "买家备注，可空",
    "sellerMemo": "备注，可空",
    "goods_list": [
        {
            "goodsNo": "货品编号",
            "goodsName": "货品名称，可空",
            "specName": "规格名称，默认 默认",
            "barcode": "条码，默认同货品编号",
            "unit": "单位，默认 Pcs",
            "sellCount": 1,
            "sellPrice": "单价；普通手工单必填，寄样/补发默认0",
            "sellTotal": "金额；普通手工单默认按单价*数量校验",
            "batchNo": "单一批次号，可空；不确定时先让系统按仓库查库存推荐",
            "batchList": [
                {"batchNo": "批次号", "quantity": 1}
            ],
            "isGift": 0
        }
    ],
    "submit_audit": False
}


TRANSFER_TEMPLATE = {
    "allocateType": 0,
    "outWarehouseCode": "调出仓库编码",
    "intWarehouseCode": "调入仓库编码",
    "reason": "调拨原因，可空；如需新增数据字典，确认后执行",
    "memo": "调拨单备注，可空",
    "field4": "调入渠道，自定义字段4",
    "stockAllocateDetailViews": [
        {
            "goodsNo": "货品编号",
            "skuBarcode": "条码，和 outSkuCode 二选一",
            "outSkuCode": "外部货品编码，和 skuBarcode 二选一",
            "unitName": "单位固定 Pcs",
            "skuCount": 1,
            "isCertified": 1,
            "batchNo": "批次号，可空"
        }
    ],
    "quick_create": False
}


INVENTORY_TEMPLATE = {
    "warehouse_code": "仓库编码",
    "company_code": "公司编码，可空；当前库存接口以仓库编码为主",
    "goods_no": "货品编号，可空",
    "goods_name": "货品名称，可空",
    "sku_barcode": "条码，可空",
    "query_time": "历史库存时间；只有配置官方历史库存方法后才可用"
}


STOCK_DOC_TEMPLATE = {
    "doc_type": "out | in",
    "inouttype": "出入库类型编码",
    "warehouseName": "仓库名称",
    "warehouseCode": "仓库编码，可空；建议优先提供名称并由系统解析",
    "remark": "备注，可空",
    "goodsDocDetailList": [
        {
            "goodsNo": "货品编号",
            "goodsName": "货品名称，可空",
            "unitName": "单位固定 Pcs",
            "quantity": 1,
            "batchNo": "批次号，可空；不确定时按库存 FIFO 自动推荐",
            "batchList": [
                {"batchNo": "批次号", "quantity": 1}
            ]
        }
    ],
    "auto_check": False
}


STOCK_APPLY_TEMPLATE = {
    "doc_type": "out | in",
    "applyUserName": "申请人姓名，必须由用户提供；后续可复用本地默认操作人",
    "warehouseName": "仓库名称，系统会解析为出库/入库仓库编码",
    "outType": "出库类型；出库申请单必填，如 202=调拨出库、204=其他出库",
    "inType": "入库类型；入库申请单必填，如 102=调拨入库、104=其他入库",
    "relDataId": "关联单据ID，可空；不填时系统生成唯一外部关联号",
    "applyDate": "申请日期，可空，默认今天",
    "reason": "出库/入库原因，可空",
    "memo": "备注，可空",
    "goodsList": [
        {
            "goodsNo": "货品编号",
            "goodsName": "货品名称，可空",
            "skuCount": 1,
            "unitName": "单位固定 Pcs",
            "skuBarcode": "条码，可空；会尽量由货品档案补齐",
            "outSkuCode": "外部货品编码，可空",
            "batchNo": "单一批次号，可空；出库申请不填时按 FIFO 自动推荐",
            "batchList": [
                {"batchNo": "批次号", "quantity": 1}
            ],
            "isCertified": 1
        }
    ],
    "batch_strategy": "fifo"
}


def get_template(template_name: str) -> dict:
    templates = {
        "sales_order": SALES_ORDER_TEMPLATE,
        "transfer": TRANSFER_TEMPLATE,
        "inventory": INVENTORY_TEMPLATE,
        "stock_doc": STOCK_DOC_TEMPLATE,
        "stock_apply": STOCK_APPLY_TEMPLATE,
    }
    return deepcopy(templates.get(template_name, {}))


def build_missing_input_response(template_name: str, missing_fields: list[str] = None, message: str = "") -> dict:
    """
    Return a user-facing template payload when creation input is incomplete.
    """
    missing_fields = [str(item) for item in (missing_fields or []) if str(item or "").strip()]
    return {
        "status": "needs_input",
        "message": message or "信息不完整，已阻止创建；请补齐缺失信息后再执行。",
        "missing_fields": missing_fields,
        "template_name": template_name,
        "template": get_template(template_name),
        "next_action": "请按 template 补齐信息；不确定字段可先查询基础资料或让系统给候选项。",
    }
