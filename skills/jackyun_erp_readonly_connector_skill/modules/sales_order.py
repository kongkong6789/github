"""
销售单模块（核心）

已确认订阅的 API（2026-04-02~04 验证）：
┌──────────────────────────────────────────────────┬──────────────┬──────────┐
│ API 方法名                                       │ 功能          │ 权限     │
├──────────────────────────────────────────────────┼──────────────┼──────────┤
│ oms.trade.fullinfoget                            │ 销售单查询    │ 全员     │
│ oms.trade.countget                               │ 销售单总数    │ 全员     │
│ oms.trade.ordercreate                            │ 销售单创建    │ 全员     │
│ oms.open.trade.audit.reject                      │ 驳回审核      │ 全员     │
│ oms.trade.order.completeDelivery                 │ 完成发货      │ 全员     │
│ oms.trade.order.batchUpdateLogisticWarehouse      │ 修改仓库/物流 │ 全员     │
│ oms.trade.orderloglist                           │ 日志列表      │ 全员     │
│ oms.trade.package.querylist                      │ 包裹查询      │ 全员     │
└──────────────────────────────────────────────────┴──────────────┴──────────┘

★ 创建流程（2026-04-04 重构）：
  渠道名 → 查渠道获取默认仓库+公司 → 查仓库获取仓库ID → 查物流获取可用物流
  → 校验渠道与仓库属于同一公司 → 填充仓库+物流 → 添加寄样标记 → 创建
"""
from __future__ import annotations

import logging
import time
import json
from datetime import datetime
from typing import Optional

import config
from jackyun_api import get_client, JackyunAPIError, JackyunValidationError
from helpers.constants import (
    METHOD_TRADE_GET, METHOD_TRADE_ADD, METHOD_TRADE_COUNT,
    METHOD_TRADE_AUDIT_PASS,
    METHOD_TRADE_REJECT,
    METHOD_TRADE_COMPLETE_DELIVERY, METHOD_TRADE_UPDATE_LOGISTICS,
    METHOD_TRADE_LOG, METHOD_TRADE_PACKAGE, METHOD_TRADE_BATCH_UPDATE_GOODS_BATCH_NO,
)
from helpers.validators import require_fields_or_raise
from helpers.local_store import (
    append_experience,
    get_most_used_preference,
    get_user_preference,
    increment_user_preference_counter,
    read_experiences,
)

logger = logging.getLogger(__name__)

# ==================== 查询字段 ====================

DEFAULT_GOODS_DETAIL_FIELDS = (
    "goodsDetail.goodsNo",
    "goodsDetail.goodsName",
    "goodsDetail.specName",
    "goodsDetail.specId",
    "goodsDetail.barcode",
    "goodsDetail.sellCount",
    "goodsDetail.unit",
    "goodsDetail.sellPrice",
    "goodsDetail.sellTotal",
    "goodsDetail.cost",
    "goodsDetail.discountTotal",
    "goodsDetail.discountPoint",
    "goodsDetail.taxFee",
    "goodsDetail.shareFavourableFee",
    "goodsDetail.estimateWeight",
    "goodsDetail.goodsMemo",
    "goodsDetail.cateName",
    "goodsDetail.brandName",
    "goodsDetail.goodsTags",
    "goodsDetail.isFit",
    "goodsDetail.isGift",
    "goodsDetail.discountFee",
    "goodsDetail.taxRate",
    "goodsDetail.estimateGoodsVolume",
    "goodsDetail.isPresell",
    "goodsDetail.customerPrice",
    "goodsDetail.customerTotal",
    "goodsDetail.tradeGoodsNo",
    "goodsDetail.tradeGoodsName",
    "goodsDetail.tradeGoodsSpec",
    "goodsDetail.tradeGoodsUnit",
    "goodsDetail.sourceSubtradeNo",
    "goodsDetail.platCode",
    "goodsDetail.platGoodsId",
    "goodsDetail.subTradeId",
    "goodsDetail.goodsFlagName",
    "goodsDetail.goodsFlagNames",
    "goodsDetail.goodsDelivery.batchNo",
    "goodsDetail.goodsDelivery.sendCount",
    "goodsDetail.goodsDelivery.productionDate",
    "goodsDetail.goodsDelivery.expirationDate",
)

DEFAULT_TRADE_FIELDS = (
    "tradeNo,orderNo,shopName,shopCode,shopTypeCode,tradeType,"
    "totalFee,payment,receiverName,phone,mobile,"
    "state,city,district,town,address,"
    "onlineTradeNo,customerName,customerAccount,sellerName,registerName,seller,chargeType,warehouseName,warehouseCode,"
    "payStatus,tradeTime,remark,buyerMessage,sellerMemo,"
    "tradeStatus,tradeStatusExplain,departName,chargeCurrency,"
    "chargeExchangeRate,confirmTime,lastShipTime,logisticName,logisticCode,"
    "flagIds,flagNames,sysFlagIds,platFlags,"
    + ",".join(DEFAULT_GOODS_DETAIL_FIELDS)
)

# ==================== 校验规则 ====================

SALES_ORDER_REQUIRED_FIELDS = [
    ("shopName", "销售渠道名称"),
    ("receiverName", "收件人姓名"),
    ("mobile", "收件人手机号"),
    ("address", "收件人地址"),
]

GOODS_ITEM_REQUIRED_FIELDS = [
    ("goodsNo", "货品编号"),
    ("sellCount", "数量"),
]

OPTIONAL_DETAIL_PASSTHROUGH_FIELDS = [
    "batchNo",
    "batch_no",
    "batchNos",
    "batch_no_list",
    "batchList",
    "batch_list",
    "productionDate",
    "expirationDate",
]

# 寄样标记
SAMPLE_FLAG = "【寄样】"
RESEND_FLAG = "【补发】"

# ==================== 仓库→默认物流 映射规则 ====================
# 根据仓库名称关键词匹配默认物流名称
# 匹配规则：按列表顺序，仓库名包含 keyword 则使用对应 logisticName
# 物流档案名称通常包含仓库名前缀，所以这套规则适配大多数场景
WAREHOUSE_LOGISTICS_RULES = [
    {"keyword": "麦歌",   "logisticName": "麦歌中通"},
    {"keyword": "宝鼎",   "logisticName": "宝鼎中通"},
    {"keyword": "韩国申通", "logisticName": "依然物流"},
    {"keyword": "韩国韵达", "logisticName": "韩国韵达-韵达国际"},
]


# ==================== 工具函数 ====================

def generate_online_trade_no(order_type: str = "JY") -> str:
    """
    生成网店订单号

    规则: yyyyMMddHHmmss + 类型后缀（精确到秒避免重复）
    - 普通手工销售单(PT): 无后缀，仅 yyyyMMddHHmmss
    - 寄样(JY): yyyyMMddHHmmssJY
    - 补发(BF): yyyyMMddHHmmssBF
    """
    now = datetime.now()
    prefix = now.strftime("%Y%m%d%H%M%S")
    if order_type == "PT":
        return prefix
    return prefix + order_type


def _get_order_flag(order_type: str) -> str:
    """获取订单类型标记"""
    if order_type == "JY":
        return SAMPLE_FLAG
    elif order_type == "BF":
        return RESEND_FLAG
    # PT（普通手工销售单）无标记
    return ""


def _get_trade_order_flag(order_type: str) -> dict | None:
    if order_type == "JY":
        flag = {"flagName": config.SAMPLE_ORDER_FLAG_NAME, "flagType": 1}
        if config.SAMPLE_ORDER_FLAG_ID:
            flag["flagId"] = config.SAMPLE_ORDER_FLAG_ID
        return flag
    if order_type == "BF":
        flag = {"flagName": config.RESEND_ORDER_FLAG_NAME, "flagType": 1}
        if config.RESEND_ORDER_FLAG_ID:
            flag["flagId"] = config.RESEND_ORDER_FLAG_ID
        return flag
    return None


def _apply_optional_detail_passthrough(detail: dict, source: dict):
    for field in OPTIONAL_DETAIL_PASSTHROUGH_FIELDS:
        if field in source and field not in detail:
            detail[field] = source[field]
    if "batch_no" in detail and "batchNo" not in detail:
        detail["batchNo"] = detail.pop("batch_no")
    if "batch_no_list" in detail and "batchNos" not in detail:
        detail["batchNos"] = detail.pop("batch_no_list")
    if "batch_list" in detail and "batchList" not in detail:
        detail["batchList"] = detail.pop("batch_list")


def _build_batch_list(allocation: list[dict]) -> list[dict]:
    return [
        {
            "batchNo": row.get("batch_no"),
            "quantity": row.get("quantity"),
            "productionDate": row.get("production_date"),
            "expirationDate": row.get("expiration_date"),
        }
        for row in (allocation or [])
        if row.get("batch_no")
    ]


def _select_logistic_for_warehouse(warehouse_name: str, warehouse_id: str = "") -> tuple[str, str]:
    """
    Pick the default logistics company for a warehouse.

    The rule table is intentionally warehouse-name based because operators use
    warehouse names in conversation, and logistics archives are warehouse-scoped.
    """
    from modules.logistics import get_logistics_for_warehouse

    rule_matched_name = ""
    for rule in WAREHOUSE_LOGISTICS_RULES:
        if rule["keyword"] in (warehouse_name or ""):
            rule_matched_name = rule["logisticName"]
            break

    available_logistics = get_logistics_for_warehouse(warehouse_id) if warehouse_id else []
    if available_logistics:
        if rule_matched_name:
            for lg in available_logistics:
                if lg.get("logisticName") == rule_matched_name:
                    return lg.get("logisticName", ""), lg.get("logisticCode", "")
            return rule_matched_name, ""
        logistic = available_logistics[0]
        return logistic.get("logisticName", ""), logistic.get("logisticCode", "")

    return rule_matched_name, ""


def _default_batch_strategy() -> str:
    return str(get_user_preference("default_batch_strategy", "fifo") or "fifo").lower()


def _extract_batch_requirements(item: dict) -> dict:
    requirements = item.get("batch_requirements") or item.get("batchRequirements") or {}
    if not isinstance(requirements, dict):
        requirements = {}
    aliases = {
        "batch_no": "batch_no",
        "batchNoRequired": "batch_no",
        "batch_no_contains": "batch_no_contains",
        "batchContains": "batch_no_contains",
        "include_batch_nos": "include_batch_nos",
        "includeBatchNos": "include_batch_nos",
        "exclude_batch_nos": "exclude_batch_nos",
        "excludeBatchNos": "exclude_batch_nos",
        "production_date_from": "production_date_from",
        "productionDateFrom": "production_date_from",
        "production_date_to": "production_date_to",
        "productionDateTo": "production_date_to",
        "expiration_date_from": "expiration_date_from",
        "expirationDateFrom": "expiration_date_from",
        "expiration_date_to": "expiration_date_to",
        "expirationDateTo": "expiration_date_to",
        "min_remaining_valid_days": "min_remaining_valid_days",
        "minRemainingValidDays": "min_remaining_valid_days",
    }
    for source, target in aliases.items():
        if source in item and target not in requirements:
            requirements[target] = item[source]
    return requirements


def _record_sales_order_preferences(order_type: str, trade_order: dict):
    prefix = f"sales_order.{order_type}"
    for field in ("shopName", "warehouseName", "logisticName", "sellerName", "customerName"):
        increment_user_preference_counter(f"{prefix}.{field}", field, trade_order.get(field))
        increment_user_preference_counter(f"sales_order.all.{field}", field, trade_order.get(field))


def _auto_select_order_batches(
    goods_list: list,
    warehouse_code: str,
    strategy: str = None,
    is_batch_management: int = 1,
    allow_stock_shortage: bool = False,
) -> list:
    from modules.inventory import recommend_batches

    if not warehouse_code:
        return goods_list
    strategy = strategy or _default_batch_strategy()

    for index, item in enumerate(goods_list, start=1):
        if item.get("batchList") or item.get("batchNo") or item.get("batchNos"):
            continue

        requested_quantity = (
            item.get("sellCount")
            or item.get("qty")
            or item.get("quantity")
            or item.get("count")
        )
        if requested_quantity in (None, "", 0, "0"):
            continue

        batch_result = recommend_batches(
            warehouse_code=warehouse_code,
            goods_no=item.get("goodsNo"),
            goods_name=item.get("goodsName") or item.get("goods_name"),
            required_quantity=int(requested_quantity),
            strategy=strategy,
            is_batch_management=is_batch_management,
            **_extract_batch_requirements(item),
        )
        if batch_result.get("enough_stock") is False:
            if allow_stock_shortage:
                item["batch_allocation_status"] = "stock_shortage_pending"
                item["batch_shortage_quantity"] = batch_result.get("remaining_quantity") or 0
                continue
            raise JackyunValidationError(
                f"货品 {item.get('goodsNo') or item.get('goodsName') or index} 批次可用库存不足，"
                f"当前还缺少 {batch_result.get('remaining_quantity') or 0}"
            )

        batch_list = _build_batch_list(batch_result.get("recommended_allocation") or [])
        if not batch_list:
            continue

        item["isBatch"] = 1
        item["batchList"] = batch_list
        if len(batch_list) == 1:
            item["batchNo"] = batch_list[0]["batchNo"]

    return goods_list


def _resolve_sales_warehouse_code(resolved: dict, warehouse_name: str = None) -> str:
    if not warehouse_name:
        return resolved.get("warehouseCode", "")

    from modules.warehouse import get_warehouse_by_name

    warehouse = get_warehouse_by_name(warehouse_name)
    return warehouse.get("warehouseCode", "") if warehouse else ""


def _validate_manual_warehouse_and_logistic(
    resolved: dict,
    warehouse_name: str = None,
    logistic_name: str = None,
) -> tuple[str, str]:
    """
    Validate user-selected warehouse/logistic against the channel company
    and the warehouse-available logistics list.
    """
    from modules.logistics import get_logistics_for_warehouse
    from modules.warehouse import get_warehouse_by_name, validate_warehouse_company

    final_warehouse = warehouse_name or resolved["warehouseName"]
    final_logistic = logistic_name or resolved["logisticName"]

    if warehouse_name:
        manual_warehouse = get_warehouse_by_name(warehouse_name)
        if not manual_warehouse:
            raise JackyunValidationError(f"未找到仓库: {warehouse_name}")
        if not validate_warehouse_company(manual_warehouse, resolved["companyId"]):
            raise JackyunValidationError(
                f"渠道「{resolved['channelName']}」属于公司「{resolved['companyName']}」，"
                f"不能选择其他公司的仓库「{warehouse_name}」"
            )
        final_warehouse = manual_warehouse.get("warehouseName", warehouse_name)

        available_logistics = get_logistics_for_warehouse(manual_warehouse.get("warehouseId", ""))
        if logistic_name and available_logistics:
            available_names = {item.get("logisticName", "") for item in available_logistics}
            if logistic_name not in available_names:
                raise JackyunValidationError(
                    f"物流「{logistic_name}」不在仓库「{final_warehouse}」的可用物流档案中"
                )
        elif not logistic_name:
            final_logistic, _ = _select_logistic_for_warehouse(
                final_warehouse,
                manual_warehouse.get("warehouseId", ""),
            )
    elif logistic_name and resolved.get("warehouseId"):
        available_logistics = get_logistics_for_warehouse(resolved["warehouseId"])
        if available_logistics:
            available_names = {item.get("logisticName", "") for item in available_logistics}
            if logistic_name not in available_names:
                raise JackyunValidationError(
                    f"物流「{logistic_name}」不在仓库「{resolved['warehouseName']}」的可用物流档案中"
                )

    return final_warehouse, final_logistic


def _resolve_confirmed_seller(
    seller_name: str,
    seller_user_id: str = None,
    seller_depart_code: str = None,
) -> dict:
    from modules.user import resolve_default_operator

    return resolve_default_operator(
        user_name=str(seller_name or "").strip(),
        user_id=seller_user_id,
        depart_code=seller_depart_code,
    )


def _quantity_from_sales_goods(item: dict) -> int:
    value = (
        item.get("sellCount")
        or item.get("qty")
        or item.get("quantity")
        or item.get("count")
    )
    return int(float(value or 0))


def _recent_sales_order_correction_hints(limit: int = 5) -> list[dict]:
    hints = []
    for record in read_experiences("corrections", limit=50):
        if record.get("workflow") != "sales_order":
            continue
        hints.append({
            "issue": record.get("issue", ""),
            "root_cause": record.get("root_cause", ""),
            "prevention_rule": record.get("prevention_rule", ""),
            "corrected_fields": record.get("corrected_fields", {}),
            "timestamp": record.get("timestamp", ""),
        })
        if len(hints) >= limit:
            break
    return hints


def preflight_sales_order(
    order_type: str,
    shop_name: str,
    receiver_name: str = "",
    mobile: str = "",
    address: str = "",
    goods_list: list = None,
    warehouse_name: str = None,
    logistic_name: str = None,
    customer_name: str = None,
    customerName: str = None,
    seller_name: str = None,
    seller_user_id: str = None,
    seller_depart_code: str = None,
    check_batches: bool = True,
    batch_strategy: str = None,
    allow_stock_shortage: bool = False,
) -> dict:
    """
    Validate and summarize a sales order before creation.

    This function does not create anything. Batch import and workflow previews
    use it to catch wrong channel/warehouse/logistics/seller/batch choices early.
    """
    normalized_order_type = str(order_type or "sample").strip().lower()
    order_type_code = {"manual": "PT", "sample": "JY", "resend": "BF"}.get(
        normalized_order_type,
        str(order_type or "JY").strip().upper(),
    )
    goods_list = goods_list or []
    batch_strategy = batch_strategy or _default_batch_strategy()
    final_customer_name = customer_name if customer_name is not None else customerName
    result = {
        "ok": False,
        "order_type": order_type_code,
        "errors": [],
        "warnings": [],
        "resolved": {},
        "goods": [],
        "batch_summary": {
            "checked": bool(check_batches),
            "all_enough_stock": True,
            "needs_confirmation": False,
            "strategy": batch_strategy,
            "stock_shortage_allowed": bool(allow_stock_shortage),
        },
        "habit_suggestions": {
            "sellerName": get_most_used_preference("sales_order.all.sellerName"),
            "shopName": get_most_used_preference("sales_order.all.shopName"),
            "warehouseName": get_most_used_preference("sales_order.all.warehouseName"),
            "logisticName": get_most_used_preference("sales_order.all.logisticName"),
        },
        "correction_hints": _recent_sales_order_correction_hints(),
    }

    required_inputs = {
        "shop_name": shop_name,
        "receiver_name": receiver_name,
        "mobile": mobile,
        "address": address,
    }
    for field, value in required_inputs.items():
        if not str(value or "").strip():
            result["errors"].append(f"缺少 {field}")
    if not goods_list:
        result["errors"].append("缺少货品明细")
    if order_type_code == "JY" and not str(final_customer_name or "").strip():
        result["errors"].append("寄样单缺少客户名称")

    resolved = {}
    final_warehouse = warehouse_name or ""
    final_logistic = logistic_name or ""
    warehouse_code = ""
    try:
        if shop_name:
            resolved = resolve_channel_warehouse_logistics(shop_name)
            if not resolved.get("success"):
                result["errors"].append(resolved.get("error", f"未找到渠道: {shop_name}"))
            else:
                final_warehouse, final_logistic = _validate_manual_warehouse_and_logistic(
                    resolved,
                    warehouse_name=warehouse_name,
                    logistic_name=logistic_name,
                )
                warehouse_code = _resolve_sales_warehouse_code(resolved, warehouse_name=warehouse_name)
                result["warnings"].extend(resolved.get("warnings") or [])
    except JackyunValidationError as exc:
        result["errors"].append(str(exc))
    except Exception as exc:
        result["errors"].append(f"渠道/仓库/物流预检失败: {exc}")

    try:
        seller = _resolve_confirmed_seller(
            seller_name=seller_name,
            seller_user_id=seller_user_id,
            seller_depart_code=seller_depart_code,
        )
        result["resolved"]["sellerName"] = _seller_employee_name(seller, seller_name)
        result["resolved"]["sellerUserId"] = seller.get("userId") or seller.get("id")
    except JackyunValidationError as exc:
        result["errors"].append(str(exc))
    except Exception as exc:
        result["errors"].append(f"业务员预检失败: {exc}")

    if resolved.get("success"):
        result["resolved"].update({
            "shopName": resolved.get("channelName") or shop_name,
            "shopCode": resolved.get("channelCode", ""),
            "companyName": resolved.get("companyName", ""),
            "companyId": resolved.get("companyId", ""),
            "warehouseName": final_warehouse,
            "warehouseCode": warehouse_code or resolved.get("warehouseCode", ""),
            "logisticName": final_logistic,
        })

    for index, item in enumerate(goods_list, start=1):
        goods_no = item.get("goodsNo") or item.get("goods_no") or ""
        quantity = 0
        try:
            quantity = _quantity_from_sales_goods(item)
        except (TypeError, ValueError):
            result["errors"].append(f"第 {index} 个货品数量格式不正确")

        if not goods_no and not item.get("goodsName"):
            result["errors"].append(f"第 {index} 个货品缺少 goodsNo 或 goodsName")
        if quantity <= 0:
            result["errors"].append(f"第 {index} 个货品数量必须为正整数")

        if order_type_code == "PT":
            is_gift = bool(item.get("isGift") or item.get("gift") or item.get("is_free"))
            sell_price = item.get("sellPrice")
            if sell_price in (None, ""):
                result["errors"].append(f"普通手工单第 {index} 个货品缺少单价 sellPrice")
            else:
                try:
                    price = float(sell_price or 0)
                    sell_total = item.get("sellTotal")
                    if price == 0 and not is_gift:
                        result["errors"].append(f"普通手工单第 {index} 个货品单价为0；如为赠品请显式传 isGift=1")
                    if sell_total not in (None, "") and abs(float(sell_total) - round(price * quantity, 2)) > 0.0001:
                        result["errors"].append(f"第 {index} 个货品金额不等于单价*数量")
                except (TypeError, ValueError):
                    result["errors"].append(f"第 {index} 个货品单价/金额格式不正确")

        goods_summary = {
            "line_index": index,
            "goodsNo": goods_no,
            "goodsName": item.get("goodsName", ""),
            "quantity": quantity,
            "has_batch": bool(item.get("batchList") or item.get("batchNo") or item.get("batchNos")),
        }

        if check_batches and warehouse_code and quantity > 0 and not goods_summary["has_batch"]:
            try:
                from modules.inventory import recommend_batches

                batch_result = recommend_batches(
                    warehouse_code=warehouse_code,
                    goods_no=goods_no or None,
                    goods_name=item.get("goodsName") or item.get("goods_name"),
                    required_quantity=quantity,
                    strategy=batch_strategy,
                    is_batch_management=1,
                    **_extract_batch_requirements(item),
                )
                goods_summary["batch_recommendation"] = {
                    "enough_stock": batch_result.get("enough_stock"),
                    "remaining_quantity": batch_result.get("remaining_quantity"),
                    "allocation": batch_result.get("recommended_allocation", []),
                    "candidate_count": len(batch_result.get("candidates", []) or []),
                }
                if batch_result.get("enough_stock") is False:
                    result["batch_summary"]["all_enough_stock"] = False
                    message = (
                        f"第 {index} 个货品 {goods_no or item.get('goodsName') or ''} 批次可用库存不足，"
                        f"还缺 {batch_result.get('remaining_quantity') or 0}"
                    )
                    if allow_stock_shortage:
                        result["warnings"].append(f"{message}；用户已允许先建待配批次单")
                    else:
                        result["errors"].append(message)
                elif batch_result.get("recommended_allocation"):
                    result["batch_summary"]["needs_confirmation"] = True
            except Exception as exc:
                result["warnings"].append(f"第 {index} 个货品批次预检失败: {exc}")

        result["goods"].append(goods_summary)

    result["ok"] = not result["errors"]
    result["status"] = "ok" if result["ok"] else "blocked"
    result["next_action"] = (
        "预检通过，可创建单据；如有批次推荐，请确认后再批量创建"
        if result["ok"]
        else "请先修正 errors 中的问题，再创建单据"
    )
    if result["ok"] and allow_stock_shortage and result["batch_summary"]["all_enough_stock"] is False:
        result["next_action"] = "库存不足但已允许先建单：只能创建待配批次单，待有库存后再匹配批次并审核发货"
    return result


# ==================== 渠道→仓库→物流 解析 ====================

def resolve_channel_warehouse_logistics(shop_name: str) -> dict:
    """
    根据渠道名称自动解析：渠道 → 默认仓库 → 可用物流

    ★ 核心业务逻辑：确保渠道和仓库属于同一公司

    :param shop_name: 渠道名称
    :return: {
        "success": bool,
        "error": str (失败时),
        "channel": {...},
        "warehouseCode": "...",
        "warehouseName": "...",
        "warehouseId": "...",
        "companyId": "...",
        "companyName": "...",
        "logisticName": "...",
        "logisticCode": "...",
    }
    """
    from modules.channel import resolve_channel_info
    from modules.warehouse import get_warehouse_by_code, validate_warehouse_company
    from modules.logistics import get_logistics_for_warehouse

    # Step 1: 查渠道
    ch_info = resolve_channel_info(shop_name)
    if not ch_info.get("found"):
        return {"success": False, "error": ch_info.get("error", f"未找到渠道: {shop_name}")}

    wh_code = ch_info["warehouseCode"]
    wh_name = ch_info["warehouseName"]
    company_id = ch_info["companyId"]
    company_name = ch_info["companyName"]

    # 检查仓库是否有效（"无" 或空表示未绑定仓库）
    no_warehouse = not wh_name or wh_name in ("无", "null", "None")

    logger.info("渠道 %s → 默认仓库 %s (%s), 公司 %s",
                shop_name, wh_name, wh_code, company_name)

    if no_warehouse:
        logger.warning("渠道 %s 未绑定有效仓库 (warehouseName=%s)", shop_name, wh_name)

    # Step 2: 查仓库详情获取 warehouseId
    warehouse = get_warehouse_by_code(wh_code) if wh_code and not no_warehouse else None
    warehouse_id = ""
    if warehouse:
        warehouse_id = warehouse.get("warehouseId", "")
        # 验证仓库和渠道属于同一公司
        if not validate_warehouse_company(warehouse, company_id):
            wh_company = warehouse.get("warehouseCompanyName", "未知")
            return {
                "success": False,
                "error": (
                    f"渠道「{shop_name}」属于公司「{company_name}」，"
                    f"但仓库「{wh_name}」属于公司「{wh_company}」，不在同一公司。"
                    f"请检查渠道配置或选择正确的仓库。"
                ),
            }
    else:
        logger.warning("未找到仓库 code=%s，将仅传 warehouseName", wh_code)

    # Step 3: 匹配物流
    # 优先按仓库名关键词规则匹配，命中后再从可用物流中验证
    logistic_name = ""
    logistic_code = ""

    logistic_name, logistic_code = _select_logistic_for_warehouse(wh_name, warehouse_id)
    if logistic_name:
        logger.info("仓库 %s → 物流 %s (%s)", wh_name, logistic_name, logistic_code)
    elif warehouse_id:
        logger.warning("仓库 %s 没有可用物流档案", wh_name)

    warnings = []
    if no_warehouse:
        warnings.append(f"渠道「{shop_name}」未绑定默认仓库，请手动指定仓库")
    if not logistic_name and warehouse_id:
        warnings.append(f"仓库「{wh_name}」没有可用物流档案，请手动指定物流")

    return {
        "success": True,
        "channel": ch_info.get("channel"),
        "channelName": ch_info["channelName"],
        "channelCode": ch_info["channelCode"],
        "departName": ch_info["departName"],
        "warehouseCode": wh_code if not no_warehouse else "",
        "warehouseName": wh_name if not no_warehouse else "",
        "warehouseId": warehouse_id,
        "companyId": company_id,
        "companyName": company_name,
        "logisticName": logistic_name,
        "logisticCode": logistic_code,
        "warnings": warnings,
    }


# ==================== 查询 ====================

def query_trades(
    trade_no: str = None,
    bill_no: str = None,
    trade_ids: list = None,
    source_trade_nos: str = None,
    trade_status: int = None,
    trade_status_list: list = None,
    start_trade_time: str = None,
    end_trade_time: str = None,
    shop_name: str = None,
    page_index: int = 0,
    page_size: int = 50,
    fields: str = None,
) -> dict:
    """
    查询销售单 (oms.trade.fullinfoget)

    注意: tradeNo/tradeIds/sourceTradeNos/时间条件 必传其一
    """
    client = get_client()
    bizcontent = {
        "fields": fields or DEFAULT_TRADE_FIELDS,
        "pageSize": page_size,
        "pageIndex": page_index,
    }
    if bill_no and not trade_no:
        trade_no = bill_no
    if trade_no:
        bizcontent["tradeNo"] = trade_no
    if trade_ids:
        bizcontent["tradeIds"] = trade_ids
    if source_trade_nos:
        bizcontent["sourceTradeNos"] = source_trade_nos
    if trade_status is not None:
        bizcontent["tradeStatus"] = trade_status
    if trade_status_list:
        bizcontent["tradeStatusList"] = trade_status_list
    if start_trade_time:
        bizcontent["startTradeTime"] = start_trade_time
    if end_trade_time:
        bizcontent["endTradeTime"] = end_trade_time
    if shop_name:
        bizcontent["shopName"] = shop_name

    result = client.call(METHOD_TRADE_GET, bizcontent)
    data = result.get("result", {}).get("data", {})
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        trades = data.get("trades")
        if isinstance(trades, list):
            return trades
        if isinstance(trades, dict):
            return [trades]
        items = data.get("data")
        if isinstance(items, list):
            return items
        if isinstance(items, dict):
            return [items]
    return []


def query_trade_by_no(trade_no: str, fields: str = None) -> Optional[dict]:
    """按销售单号查询单个销售单"""
    trades = query_trades(trade_no=trade_no, page_size=5, fields=fields)
    return trades[0] if trades else None


def query_trade_logistics(trade_no: str) -> dict:
    """
    Query logistics number for a sales order through trade -> outbound-doc flow.
    """
    from modules.stock_doc import query_outbound_logistics_by_bill_no

    trade = query_trade_by_no(
        trade_no,
        fields="tradeNo,billNo,tradeStatus,tradeStatusExplain,warehouseName,logisticName,logisticCode",
    )
    if not trade:
        raise JackyunValidationError(f"未找到销售单: {trade_no}")

    bill_no = trade.get("billNo") or trade.get("tradeNo") or trade_no
    outbound = query_outbound_logistics_by_bill_no(bill_no)

    return {
        "trade_no": trade.get("tradeNo", "") or trade_no,
        "bill_no": bill_no,
        "trade_exists": True,
        "trade_status": trade.get("tradeStatus"),
        "trade_status_explain": trade.get("tradeStatusExplain", ""),
        "warehouse_name": trade.get("warehouseName", ""),
        "trade_logistic_name": trade.get("logisticName", ""),
        "trade_logistic_code": trade.get("logisticCode", ""),
        "logistic_found": outbound.get("found", False),
        "logistic_name": outbound.get("logistic_name", "") or trade.get("logisticName", ""),
        "logistic_no": outbound.get("logistic_no", ""),
        "goodsdoc_no": outbound.get("goodsdoc_no", ""),
        "goods_list": outbound.get("goods_list", []),
        "trade": trade,
        "outbound_doc": outbound.get("raw"),
    }


def count_trades(
    start_trade_time: str = None,
    end_trade_time: str = None,
    trade_status: int = None,
    trade_status_list: list = None,
    shop_name: str = None,
) -> int:
    """
    查询销售单总数 (oms.trade.countget)

    注意: 必须传时间条件或单号条件之一
    """
    client = get_client()
    bizcontent = {}
    if start_trade_time:
        bizcontent["startTradeTime"] = start_trade_time
    if end_trade_time:
        bizcontent["endTradeTime"] = end_trade_time
    if trade_status is not None:
        bizcontent["tradeStatus"] = trade_status
    if trade_status_list:
        bizcontent["tradeStatusList"] = trade_status_list
    if shop_name:
        bizcontent["shopName"] = shop_name

    result = client.call(METHOD_TRADE_COUNT, bizcontent)
    return result.get("result", {}).get("data", 0)


# ==================== 创建 ====================

def create_trade(order_data: dict) -> dict:
    """
    创建销售单 (oms.trade.ordercreate)

    ★ 关键: tradeOrderDetails 必须嵌套在 tradeOrder 内部（非并列字段）
    ★ 明细必填字段: goodsNo, specName, barcode, unit, sellPrice, sellCount, sellTotal
    ★ 所有数值字段应传字符串类型
    """
    trade_order = order_data.get("tradeOrder", order_data)
    trade_details = order_data.get("tradeOrderDetails", order_data.get("goodsList", []))

    require_fields_or_raise(trade_order, SALES_ORDER_REQUIRED_FIELDS)
    if not trade_details:
        raise JackyunValidationError("缺少货品明细(tradeOrderDetails)，请至少添加一个货品")
    for item in trade_details:
        require_fields_or_raise(item, GOODS_ITEM_REQUIRED_FIELDS)

    # 自动填充默认值
    defaults = {
        "tradeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tradeType": "1",
        "chargeType": "1",
        "chargeCurrency": "人民币",
        "payStatus": "9",
    }
    for k, v in defaults.items():
        if k not in trade_order:
            trade_order[k] = v

    if "totalFee" not in trade_order:
        trade_order["totalFee"] = str(sum(
            float(d.get("sellTotal", 0) or 0) for d in trade_details
        ))
    if "payment" not in trade_order:
        trade_order["payment"] = str(trade_order["totalFee"])
    if "onlineTradeNo" not in trade_order:
        trade_order["onlineTradeNo"] = generate_online_trade_no("JY")

    # 明细自动补全默认值
    for item in trade_details:
        item.setdefault("specName", "默认")
        if "barcode" not in item:
            item["barcode"] = item.get("goodsNo", "")
        item.setdefault("unit", "Pcs")
        item.setdefault("sellPrice", "0")
        item.setdefault("sellTotal", "0")
        for k in ("sellPrice", "sellCount", "sellTotal"):
            item[k] = str(item[k])

    # ★ tradeOrderDetails 嵌套在 tradeOrder 内部
    trade_order["tradeOrderDetails"] = trade_details

    bizcontent = {"tradeOrder": trade_order}

    client = get_client()
    logger.info("创建销售单: shopName=%s, warehouseName=%s, logisticName=%s, onlineTradeNo=%s",
                trade_order.get("shopName"), trade_order.get("warehouseName"),
                trade_order.get("logisticName"), trade_order.get("onlineTradeNo"))
    result = client.call(METHOD_TRADE_ADD, bizcontent)
    logger.info("销售单创建成功")
    append_experience("sales_order", {"payload": bizcontent, "result": result})
    return result


def _extract_trade_no(create_result: dict) -> str:
    trade_result = create_result.get("result", {}) or {}
    return (
        trade_result.get("billNo")
        or trade_result.get("tradeNo")
        or trade_result.get("data", {}).get("tradeNo", "")
        or trade_result.get("data", {}).get("billNo", "")
    )


def _seller_employee_name(seller: dict, fallback: str = "") -> str:
    """Prefer the employee's real name when writing operator fields."""
    return seller.get("realName") or seller.get("name") or seller.get("userName") or fallback or ""


def create_sample_order(
    shop_name: str,
    receiver_name: str,
    mobile: str,
    address: str,
    goods_list: list,
    state: str = "",
    city: str = "",
    district: str = "",
    town: str = "",
    remark: str = "",
    buyer_memo: str = None,
    seller_memo: str = None,
    buyerMemo: str = None,
    sellerMemo: str = None,
    warehouse_name: str = None,
    logistic_name: str = None,
    order_type: str = "JY",
    customer_name: str = None,
    customerName: str = None,
    online_trade_no: str = None,
    onlineTradeNo: str = None,
    seller_name: str = None,
    seller_user_id: str = None,
    seller_depart_code: str = None,
    batch_strategy: str = None,
    allow_stock_shortage: bool = False,
) -> dict:
    """
    创建寄样/补发销售单（全自动流程）

    ★ 自动完成：
    1. 根据渠道名 → 查渠道默认仓库 + 公司
    2. 校验渠道与仓库属于同一公司
    3. 根据仓库 → 查可用物流档案
    4. 添加寄样/补发标记到备注和货品标记
    5. 创建销售单

    :param shop_name: 渠道名称（从实时渠道列表中选）
    :param receiver_name: 收件人
    :param mobile: 手机号
    :param address: 详细地址
    :param goods_list: [{"goodsNo": "...", "sellCount": 1}, ...]
    :param warehouse_name: 手动指定仓库（可选，不传则自动从渠道获取）
    :param logistic_name: 手动指定物流（可选，不传则自动从仓库获取）
    :param order_type: "JY"=寄样, "BF"=补发
    :param customer_name: 客户名称；寄样单必须由用户提供
    :return: 创建结果
    """
    final_customer_name = customer_name if customer_name is not None else customerName
    if order_type == "JY" and not str(final_customer_name or "").strip():
        raise JackyunValidationError("寄样单必须提供客户名称(customer_name/customerName)，请向用户确认后再创建")

    # ==================== 自动解析渠道→仓库→物流 ====================
    resolved = resolve_channel_warehouse_logistics(shop_name)
    if not resolved.get("success"):
        raise JackyunValidationError(resolved.get("error", "渠道解析失败"))

    # 仓库：优先用手动指定，否则用渠道默认
    final_warehouse, final_logistic = _validate_manual_warehouse_and_logistic(
        resolved,
        warehouse_name=warehouse_name,
        logistic_name=logistic_name,
    )

    flag = _get_order_flag(order_type)
    trade_order_flag = _get_trade_order_flag(order_type)
    final_buyer_memo = buyer_memo if buyer_memo is not None else buyerMemo
    final_seller_memo = seller_memo if seller_memo is not None else sellerMemo
    if final_seller_memo is None:
        final_seller_memo = remark

    logger.info(
        "创建%s单: 渠道=%s, 仓库=%s, 物流=%s, 公司=%s",
        "寄样" if order_type == "JY" else "补发",
        shop_name, final_warehouse, final_logistic, resolved["companyName"]
    )
    seller = _resolve_confirmed_seller(
        seller_name=seller_name,
        seller_user_id=seller_user_id,
        seller_depart_code=seller_depart_code,
    )
    goods_list = _auto_select_order_batches(
        goods_list=goods_list,
        warehouse_code=_resolve_sales_warehouse_code(resolved, warehouse_name=warehouse_name),
        strategy=batch_strategy,
        allow_stock_shortage=allow_stock_shortage,
    )
    seller_display_name = _seller_employee_name(seller, seller_name)
    final_online_trade_no = online_trade_no if online_trade_no is not None else onlineTradeNo

    trade_order = {
        "shopName": shop_name,
        "tradeType": "1",
        "totalFee": "0",
        "payment": "0",
        "chargeType": "1",
        "chargeCurrency": "人民币",
        "payStatus": "9",
        "receiverName": receiver_name,
        "phone": mobile,
        "mobile": mobile,
        "state": state,
        "city": city,
        "district": district,
        "town": town,
        "address": address,
        "onlineTradeNo": final_online_trade_no or generate_online_trade_no(order_type),
        "tradeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sellerMemo": final_seller_memo or "",
        "sellerName": seller_display_name,
        "registerName": seller_display_name,
    }
    if final_customer_name:
        trade_order["customerName"] = final_customer_name
    if final_buyer_memo:
        trade_order["buyerMemo"] = final_buyer_memo
    if trade_order_flag:
        trade_order["tradeOrderFlags"] = [trade_order_flag]

    # 仓库
    if final_warehouse:
        trade_order["warehouseName"] = final_warehouse
        warehouse_code = _resolve_sales_warehouse_code(resolved, warehouse_name=warehouse_name)
        if warehouse_code:
            trade_order["warehouseCode"] = warehouse_code
    # 物流
    if final_logistic:
        trade_order["logisticName"] = final_logistic

    trade_details = []
    for g in goods_list:
        detail = {
            "goodsNo": g["goodsNo"],
            "sellCount": str(g.get("sellCount", 1)),
            "sellPrice": str(g.get("sellPrice", 0)),
            "sellTotal": str(g.get("sellTotal", 0)),
            "unit": g.get("unit", "Pcs"),
            "specName": g.get("specName", "默认"),
            "barcode": g.get("barcode", g["goodsNo"]),
        }
        if "goodsName" in g:
            detail["goodsName"] = g["goodsName"]
        _apply_optional_detail_passthrough(detail, g)
        # 货品标记
        if flag:
            detail["goodsFlagName"] = flag
        trade_details.append(detail)

    create_result = create_trade({
        "tradeOrder": trade_order,
        "tradeOrderDetails": trade_details,
    })
    _record_sales_order_preferences(order_type, trade_order)
    return create_result


def prepare_sales_order_batches(
    shop_name: str,
    goods_list: list,
    warehouse_name: str = None,
    strategy: str = None,
    is_batch_management: int = 1,
) -> dict:
    """
    为销售单货品生成批次候选与推荐方案。

    该函数只做查询与推荐，不直接创建销售单。
    适合在用户不确定批次时先给出候选，再由用户确认批次后继续建单。
    """
    from modules.inventory import recommend_batches
    from modules.warehouse import get_warehouse_by_name

    strategy = strategy or _default_batch_strategy()

    resolved = resolve_channel_warehouse_logistics(shop_name)
    if not resolved.get("success"):
        raise JackyunValidationError(resolved.get("error", "渠道解析失败"))

    final_warehouse, _ = _validate_manual_warehouse_and_logistic(
        resolved,
        warehouse_name=warehouse_name,
        logistic_name=None,
    )

    warehouse_code = resolved.get("warehouseCode", "")
    if warehouse_name:
        warehouse = get_warehouse_by_name(final_warehouse)
        warehouse_code = warehouse.get("warehouseCode", "") if warehouse else ""

    if not warehouse_code:
        raise JackyunValidationError(f"仓库「{final_warehouse}」缺少仓库编号，无法查询批次库存")

    if not goods_list:
        raise JackyunValidationError("请提供货品明细后再查询批次推荐")

    recommendations = []
    all_enough_stock = True
    for index, item in enumerate(goods_list, start=1):
        goods_no = item.get("goodsNo")
        goods_name = item.get("goodsName") or item.get("goods_name")
        requested_quantity = (
            item.get("sellCount")
            or item.get("qty")
            or item.get("quantity")
            or item.get("count")
        )

        if not goods_no and not goods_name:
            raise JackyunValidationError(f"第 {index} 个货品缺少 goodsNo 或 goodsName，无法查询批次")
        if requested_quantity in (None, "", 0, "0"):
            raise JackyunValidationError(f"第 {index} 个货品缺少数量，无法查询批次")

        batch_result = recommend_batches(
            warehouse_code=warehouse_code,
            goods_no=goods_no,
            goods_name=goods_name,
            required_quantity=int(requested_quantity),
            strategy=strategy,
            is_batch_management=is_batch_management,
            **_extract_batch_requirements(item),
        )
        batch_result["line_index"] = index
        recommendations.append(batch_result)

        enough_stock = batch_result.get("enough_stock")
        if enough_stock is False:
            all_enough_stock = False

    return {
        "shop_name": shop_name,
        "warehouse_name": final_warehouse,
        "warehouse_code": warehouse_code,
        "strategy": strategy,
        "goods_recommendations": recommendations,
        "all_enough_stock": all_enough_stock,
        "next_action": "请先让用户确认批次方案，再把 batchList 或 batchNo 写入销售单明细后创建单据",
    }


def create_manual_order(
    shop_name: str,
    receiver_name: str,
    mobile: str,
    address: str,
    goods_list: list,
    state: str = "",
    city: str = "",
    district: str = "",
    town: str = "",
    remark: str = "",
    buyer_memo: str = None,
    seller_memo: str = None,
    buyerMemo: str = None,
    sellerMemo: str = None,
    warehouse_name: str = None,
    logistic_name: str = None,
    customer_name: str = None,
    customerName: str = None,
    online_trade_no: str = None,
    onlineTradeNo: str = None,
    seller_name: str = None,
    seller_user_id: str = None,
    seller_depart_code: str = None,
    batch_strategy: str = None,
    allow_stock_shortage: bool = False,
) -> dict:
    """
    创建普通手工销售单（全自动流程）

    ★ 与寄样/补发单的区别：
    - 金额由用户填写（sellPrice/sellTotal 必填，不强制为0）
    - 网店订单号无后缀（yyyyMMddHHmmss）
    - 无【寄样】/【补发】标记
    - payStatus 默认 "0"（待付款，而非寄样的 "9"）
    - totalFee/payment 由明细 sellTotal 自动汇总

    :param shop_name: 渠道名称
    :param receiver_name: 收件人
    :param mobile: 手机号
    :param address: 详细地址
    :param goods_list: [{"goodsNo": "...", "sellCount": 1, "sellPrice": "99.00", "sellTotal": "99.00"}, ...]
    :param state: 省
    :param city: 市
    :param district: 区
    :param town: 镇
    :param remark: 备注（不加前缀标记）
    :param warehouse_name: 手动指定仓库（可选）
    :param logistic_name: 手动指定物流（可选）
    :return: 创建结果
    """
    # 自动解析渠道→仓库→物流
    resolved = resolve_channel_warehouse_logistics(shop_name)
    if not resolved.get("success"):
        raise JackyunValidationError(resolved.get("error", "渠道解析失败"))

    final_warehouse, final_logistic = _validate_manual_warehouse_and_logistic(
        resolved,
        warehouse_name=warehouse_name,
        logistic_name=logistic_name,
    )

    logger.info(
        "创建普通手工销售单: 渠道=%s, 仓库=%s, 物流=%s, 公司=%s",
        shop_name, final_warehouse, final_logistic, resolved["companyName"]
    )
    seller = _resolve_confirmed_seller(
        seller_name=seller_name,
        seller_user_id=seller_user_id,
        seller_depart_code=seller_depart_code,
    )
    goods_list = _auto_select_order_batches(
        goods_list=goods_list,
        warehouse_code=_resolve_sales_warehouse_code(resolved, warehouse_name=warehouse_name),
        strategy=batch_strategy,
        allow_stock_shortage=allow_stock_shortage,
    )
    final_buyer_memo = buyer_memo if buyer_memo is not None else buyerMemo
    final_seller_memo = seller_memo if seller_memo is not None else sellerMemo
    final_customer_name = customer_name if customer_name is not None else customerName
    final_online_trade_no = online_trade_no if online_trade_no is not None else onlineTradeNo
    if final_seller_memo is None:
        final_seller_memo = remark
    seller_display_name = _seller_employee_name(seller, seller_name)

    # 校验货品明细必须提供金额
    for i, g in enumerate(goods_list):
        is_gift = bool(g.get("isGift") or g.get("gift") or g.get("is_free"))
        if g.get("sellPrice") in (None, ""):
            raise JackyunValidationError(
                f"普通手工销售单的货品明细必须填写单价(sellPrice)，"
                f"第 {i+1} 个货品 {g.get('goodsNo', '?')} 缺少单价"
            )
        if not is_gift and float(g.get("sellPrice", 0) or 0) == 0:
            raise JackyunValidationError(
                f"普通手工销售单的货品明细单价不能为0，"
                f"如为赠品请显式传 isGift=1。第 {i+1} 个货品 {g.get('goodsNo', '?')}"
            )

    # 构建明细
    trade_details = []
    total_fee = 0.0
    for g in goods_list:
        sell_price = float(g.get("sellPrice", 0) or 0)
        sell_count = int(g.get("sellCount", 1) or 1)
        sell_total = g.get("sellTotal")
        sell_total = float(sell_total) if sell_total not in (None, "") else None
        expected_total = round(sell_price * sell_count, 2)
        if sell_total is None:
            sell_total = expected_total
        elif abs(sell_total - expected_total) > 0.0001:
            raise JackyunValidationError(
                f"货品 {g.get('goodsNo', '?')} 的金额不正确，应为单价*数量={expected_total}"
            )
        total_fee += sell_total

        detail = {
            "goodsNo": g["goodsNo"],
            "sellCount": str(sell_count),
            "sellPrice": str(sell_price),
            "sellTotal": str(sell_total),
            "unit": g.get("unit", "Pcs"),
            "specName": g.get("specName", "默认"),
            "barcode": g.get("barcode", g["goodsNo"]),
        }
        if "goodsName" in g:
            detail["goodsName"] = g["goodsName"]
        _apply_optional_detail_passthrough(detail, g)
        # 普通手工单无货品标记（不设 goodsFlagName）
        trade_details.append(detail)

    trade_order = {
        "shopName": shop_name,
        "tradeType": "1",
        "totalFee": str(total_fee),
        "payment": str(total_fee),
        "chargeType": "1",
        "chargeCurrency": "人民币",
        "payStatus": "0",  # 普通手工单：待付款（与寄样的 "9" 不同）
        "receiverName": receiver_name,
        "phone": mobile,
        "mobile": mobile,
        "state": state,
        "city": city,
        "district": district,
        "town": town,
        "address": address,
        "onlineTradeNo": final_online_trade_no or generate_online_trade_no("PT"),  # 无后缀
        "tradeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sellerMemo": final_seller_memo or "",
        "sellerName": seller_display_name,
        "registerName": seller_display_name,
    }
    if final_customer_name:
        trade_order["customerName"] = final_customer_name
    if final_buyer_memo:
        trade_order["buyerMemo"] = final_buyer_memo

    if final_warehouse:
        trade_order["warehouseName"] = final_warehouse
        warehouse_code = _resolve_sales_warehouse_code(resolved, warehouse_name=warehouse_name)
        if warehouse_code:
            trade_order["warehouseCode"] = warehouse_code
    if final_logistic:
        trade_order["logisticName"] = final_logistic

    create_result = create_trade({
        "tradeOrder": trade_order,
        "tradeOrderDetails": trade_details,
    })
    _record_sales_order_preferences("PT", trade_order)
    return create_result


def create_manual_order_and_audit(**kwargs) -> dict:
    """
    Create a manual sales order and immediately call the audit-pass API.
    """
    create_result = create_manual_order(**kwargs)
    trade_no = _extract_trade_no(create_result)
    audit_result = check_trade(trade_no) if trade_no else None
    return {
        "create_result": create_result,
        "trade_no": trade_no,
        "audit_result": audit_result,
    }


def create_sample_order_and_audit(**kwargs) -> dict:
    """
    Create a sample/resend sales order and immediately call the audit-pass API.
    """
    create_result = create_sample_order(**kwargs)
    trade_no = _extract_trade_no(create_result)
    audit_result = check_trade(trade_no) if trade_no else None
    return {
        "create_result": create_result,
        "trade_no": trade_no,
        "audit_result": audit_result,
    }


# ==================== 审核 / 驳回 ====================

def reject_trade(trade_no: str) -> dict:
    """
    驳回审核 (oms.open.trade.audit.reject)
    """
    client = get_client()
    logger.info("驳回销售单审核: tradeNo=%s", trade_no)
    return client.call(METHOD_TRADE_REJECT, {"tradeNo": trade_no})


# [已禁用] 销售单复核功能（reAudit API 已取消订阅）
# def reaudit_trade(trade_nos: str, operator: str) -> dict:
#     """
#     销售单复核 (oms.trade.order.reAudit)
#
#     ⚠️ 仅限财务权限人员使用
#     """
#     client = get_client()
#     logger.info("财务复核销售单: tradeNos=%s, operator=%s", trade_nos, operator)
#     return client.call(METHOD_TRADE_REAUDIT, {
#         "tradeNos": trade_nos,
#         "operator": operator,
#     })


# ==================== 发货 / 物流 ====================

def complete_delivery(delivery_list: list) -> dict:
    """
    完成发货 (oms.trade.order.completeDelivery)

    :param delivery_list: [{"tradeNo": "YR...", "logisticNo": "SF...", "logisticName": "顺丰速运"}, ...]
    """
    client = get_client()
    logger.info("完成发货: %d 个订单", len(delivery_list))
    return client.call(METHOD_TRADE_COMPLETE_DELIVERY, delivery_list)


def update_logistics_warehouse(update_list: list) -> dict:
    """
    批量修改仓库或物流信息 (oms.trade.order.batchUpdateLogisticWarehouse)

    :param update_list: [{"tradeNo": "YR...", "warehouseName": "...", "logisticName": "..."}, ...]
    """
    client = get_client()
    logger.info("修改仓库/物流: %d 个订单", len(update_list))
    return client.call(METHOD_TRADE_UPDATE_LOGISTICS, update_list)


# ==================== 日志 / 包裹 ====================

def query_trade_logs(
    trade_no: str,
    start_time: str,
    end_time: str,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    """
    查询销售单操作日志 (oms.trade.orderloglist)

    注意: start_time 和 end_time 间隔不能超过 1 天
    """
    client = get_client()
    result = client.call(METHOD_TRADE_LOG, {
        "tradeNo": trade_no,
        "startTime": start_time,
        "endTime": end_time,
        "pageIndex": page_index,
        "pageSize": page_size,
    })
    data = result.get("result", {}).get("data", {})
    return data.get("tradeOrderDbLogList", [])


def query_trade_packages(trade_no: str) -> dict:
    """
    查询订单包裹信息 (oms.trade.package.querylist)
    """
    client = get_client()
    result = client.call(METHOD_TRADE_PACKAGE, {"tradeNo": trade_no})
    return result.get("result", {}).get("data", {})


def batch_update_trade_goods_batch_no(trade_no: str, goods_batch_rows: list[dict]) -> dict:
    """
    修改销售单货品批次（oms.trade.batchUpdateGoodsBatchNo）
    """
    client = get_client()
    return client.call(
        METHOD_TRADE_BATCH_UPDATE_GOODS_BATCH_NO,
        {
            "tradeNo": trade_no,
            "tradeOrderGoodsRelateDeliveryArr": goods_batch_rows,
        },
    )


# ==================== 全流程编排 ====================

def create_and_submit_trade(order_data: dict, operator: str = None) -> dict:
    """
    销售单全流程：创建 → 等待手动复核

    [已禁用] reAudit 复核 API 已取消订阅，创建后需在吉客云网页端手动复核
    """
    result = {
        "success": False,
        "trade_no": None,
        "steps": [],
    }

    # Step 1: 创建
    try:
        create_result = create_trade(order_data)
        trade_data = create_result.get("result", {}).get("data", {})
        trade_order = trade_data.get("tradeOrder", {})
        trade_no = trade_order.get("tradeNo", "") or trade_data.get("tradeNo", "")
        result["trade_no"] = trade_no
        result["steps"].append({
            "step": "创建销售单",
            "status": "success",
            "message": f"单号: {trade_no}",
        })
    except (JackyunAPIError, Exception) as e:
        result["steps"].append({
            "step": "创建销售单",
            "status": "failed",
            "message": str(e),
        })
        return result

    if not trade_no:
        result["steps"].append({
            "step": "创建销售单",
            "status": "failed",
            "message": "未获取到单号",
        })
        return result

    # [已禁用] Step 2: 财务复核（reAudit API 已取消订阅）
    # if operator:
    #     try:
    #         reaudit_trade(trade_no, operator)
    #         result["steps"].append({
    #             "step": "财务复核",
    #             "status": "success",
    #             "message": f"复核通过 (操作员: {operator})，已递交仓库",
    #         })
    #     except (JackyunAPIError, Exception) as e:
    #         result["steps"].append({
    #             "step": "财务复核",
    #             "status": "failed",
    #             "message": str(e),
    #         })
    #         return result
    # else:
    result["steps"].append({
        "step": "财务复核",
        "status": "skipped",
        "message": "[已禁用] 复核功能已关闭，请手动在吉客云网页端复核",
    })

    result["success"] = True
    return result


def check_trade(trade_no: str = None, trade_nos: list = None, operator: str = None) -> dict:
    """
    审核销售单 (oms.trade.audit.pass)
    """
    trade_list = trade_nos or ([trade_no] if trade_no else [])
    if not trade_list:
        raise JackyunValidationError("缺少销售单号，必须提供 trade_no 或 trade_nos")
    client = get_client()
    bizcontent = {
        "tradeNos": json.dumps(trade_list, ensure_ascii=False),
    }
    if operator:
        bizcontent["operator"] = operator
    logger.info("审核销售单: tradeNos=%s", ",".join(trade_list))
    return client.call(METHOD_TRADE_AUDIT_PASS, bizcontent)


def finance_check_trade(trade_no: str, operator: str = None) -> dict:
    """
    Finance re-audit is still not exposed here as an open public method in this skill.
    """
    return {"code": "200", "msg": "finance approval step requires FBP/manual review"}


def batch_audit_trades(trade_nos: list, operator: str = None) -> dict:
    """
    Batch audit sales orders with the public audit-pass API.
    """
    result = check_trade(trade_nos=trade_nos, operator=operator)
    data = result.get("result", {}).get("data", {}) if isinstance(result, dict) else {}
    failed = data.get("failedResults", []) if isinstance(data, dict) else []
    failed_nos = {item.get("tradeNo") for item in failed if isinstance(item, dict)}
    return {
        "total": len(trade_nos),
        "success_count": len([no for no in trade_nos if no not in failed_nos]),
        "fail_count": len(failed_nos),
        "failed_results": failed,
        "raw": result,
    }


def summarize_pending_trades(
    shop_name: str = None,
    start_trade_time: str = None,
    end_trade_time: str = None,
) -> dict:
    """
    Summarize pending sales orders for operations users.
    """
    trades = query_trades(
        trade_status=1010,
        shop_name=shop_name,
        start_trade_time=start_trade_time,
        end_trade_time=end_trade_time,
        page_size=200,
    )
    goods_count = 0
    for trade in trades:
        for item in trade.get("goodsDetail", []) or []:
            try:
                goods_count += int(float(item.get("sellCount", 0) or 0))
            except (TypeError, ValueError):
                continue
    return {
        "trade_count": len(trades),
        "goods_count": goods_count,
        "trades": trades,
    }


def list_pending_trade_candidates(
    shop_name: str = None,
    start_trade_time: str = None,
    end_trade_time: str = None,
    page_size: int = 200,
) -> list:
    """
    Return simplified pending-trade candidates for operations users.
    """
    trades = query_trades(
        trade_status=1010,
        shop_name=shop_name,
        start_trade_time=start_trade_time,
        end_trade_time=end_trade_time,
        page_size=page_size,
    )
    candidates = []
    for trade in trades:
        goods_detail = trade.get("goodsDetail", []) or []
        goods_count = 0
        goods_summary = []
        for item in goods_detail:
            qty_raw = item.get("sellCount", 0) or 0
            try:
                qty = int(float(qty_raw))
            except (TypeError, ValueError):
                qty = 0
            goods_count += qty
            goods_summary.append(
                {
                    "goodsNo": item.get("goodsNo", ""),
                    "goodsName": item.get("goodsName", ""),
                    "sellCount": qty,
                }
            )
        candidates.append(
            {
                "tradeNo": trade.get("tradeNo", "") or trade.get("billNo", ""),
                "onlineTradeNo": trade.get("onlineTradeNo", ""),
                "shopName": trade.get("shopName", ""),
                "receiverName": trade.get("receiverName", ""),
                "warehouseName": trade.get("warehouseName", ""),
                "logisticName": trade.get("logisticName", ""),
                "tradeTime": trade.get("tradeTime", ""),
                "goodsCount": goods_count,
                "goodsSummary": goods_summary,
                "raw": trade,
            }
        )
    return candidates


def summarize_pending_shop_orders(
    shop_name: str = None,
    start_trade_time: str = None,
    end_trade_time: str = None,
) -> dict:
    """
    Summary view tailored for pending online-shop order handling.
    """
    candidates = list_pending_trade_candidates(
        shop_name=shop_name,
        start_trade_time=start_trade_time,
        end_trade_time=end_trade_time,
    )
    return {
        "trade_count": len(candidates),
        "goods_count": sum(item.get("goodsCount", 0) for item in candidates),
        "online_trade_count": len(
            {item.get("onlineTradeNo") for item in candidates if item.get("onlineTradeNo")}
        ),
        "candidates": candidates,
    }


def _trade_has_refund_risk(trade: dict) -> bool:
    refund_fields = (
        "refundStatus",
        "refundStatusName",
        "refundState",
        "refundNo",
        "afterSaleStatus",
        "afterSalesStatus",
    )
    for field in refund_fields:
        value = str(trade.get(field) or "").strip()
        if value and value not in ("0", "无", "None", "null", "false", "False"):
            return True
    text = " ".join(
        str(trade.get(field) or "")
        for field in ("remark", "buyerMessage", "sellerMemo", "flagNames", "sysFlagNames", "tradeStatusExplain")
    )
    return "退款" in text or "退货" in text or "仅退款" in text


def diagnose_pending_trade(trade: dict, check_stock: bool = True) -> dict:
    """
    Diagnose why a downloaded online order is still pending audit.
    """
    issues = []
    actions = []
    goods_detail = trade.get("goodsDetail", []) or []
    warehouse_code = trade.get("warehouseCode") or ""
    warehouse_name = trade.get("warehouseName") or ""

    if _trade_has_refund_risk(trade):
        issues.append({"code": "refund_risk", "message": "订单疑似存在退款/售后/退货信息，需先核对平台状态"})
        actions.append("hold_and_check_refund")

    if not warehouse_name:
        issues.append({"code": "missing_warehouse", "message": "订单缺少发货仓库"})
        actions.append("fix_warehouse_logistics")
    if not trade.get("logisticName"):
        issues.append({"code": "missing_logistics", "message": "订单缺少物流公司"})
        actions.append("fix_warehouse_logistics")
    if not trade.get("receiverName") or not (trade.get("mobile") or trade.get("phone")) or not trade.get("address"):
        issues.append({"code": "missing_receiver_info", "message": "收件人、手机号或地址不完整"})
        actions.append("fix_receiver_info")
    if not goods_detail:
        issues.append({"code": "missing_goods", "message": "订单没有货品明细"})
        actions.append("fix_goods_or_cancel")

    for index, item in enumerate(goods_detail, start=1):
        goods_no = item.get("goodsNo") or ""
        goods_name = item.get("goodsName") or ""
        qty_raw = item.get("sellCount") or item.get("qty") or item.get("quantity")
        try:
            qty = int(float(qty_raw or 0))
        except (TypeError, ValueError):
            qty = 0
        if not goods_no:
            issues.append({"code": "invalid_goods", "message": f"第 {index} 个货品缺少货品编号", "goodsName": goods_name})
            actions.append("fix_goods_or_cancel")
        if qty <= 0:
            issues.append({"code": "invalid_quantity", "message": f"第 {index} 个货品数量不是正整数", "goodsNo": goods_no})
            actions.append("fix_goods_or_cancel")
        if check_stock and warehouse_code and goods_no and qty > 0:
            try:
                from modules.inventory import recommend_batches

                stock_result = recommend_batches(
                    warehouse_code=warehouse_code,
                    goods_no=goods_no,
                    goods_name=goods_name,
                    required_quantity=qty,
                    strategy=_default_batch_strategy(),
                    is_batch_management=1,
                )
                if stock_result.get("enough_stock") is False:
                    issues.append({
                        "code": "stock_shortage",
                        "message": f"第 {index} 个货品批次可用库存不足，还缺 {stock_result.get('remaining_quantity') or 0}",
                        "goodsNo": goods_no,
                        "goodsName": goods_name,
                        "requiredQuantity": qty,
                        "remainingQuantity": stock_result.get("remaining_quantity") or 0,
                    })
                    actions.append("wait_stock_or_change_warehouse")
            except Exception as exc:
                issues.append({"code": "stock_check_failed", "message": f"第 {index} 个货品库存诊断失败: {exc}", "goodsNo": goods_no})
                actions.append("manual_stock_check")

    unique_actions = []
    for action in actions:
        if action not in unique_actions:
            unique_actions.append(action)
    if not issues:
        unique_actions.append("audit_ready")

    return {
        "tradeNo": trade.get("tradeNo", "") or trade.get("billNo", ""),
        "onlineTradeNo": trade.get("onlineTradeNo", ""),
        "shopName": trade.get("shopName", ""),
        "warehouseName": warehouse_name,
        "logisticName": trade.get("logisticName", ""),
        "issues": issues,
        "issue_codes": sorted({item["code"] for item in issues}),
        "recommended_actions": unique_actions,
        "audit_ready": not issues,
        "raw": trade,
    }


def diagnose_pending_trade_candidates(
    shop_name: str = None,
    start_trade_time: str = None,
    end_trade_time: str = None,
    limit: int = 200,
    check_stock: bool = True,
) -> dict:
    """
    Diagnose pending online-shop orders before operations audit.
    """
    trades = query_trades(
        trade_status=1010,
        shop_name=shop_name,
        start_trade_time=start_trade_time,
        end_trade_time=end_trade_time,
        page_size=limit,
    )
    diagnostics = [diagnose_pending_trade(trade, check_stock=check_stock) for trade in trades]
    issue_summary = {}
    for item in diagnostics:
        for code in item.get("issue_codes", []):
            issue_summary[code] = issue_summary.get(code, 0) + 1
    audit_ready = [item for item in diagnostics if item.get("audit_ready")]
    blocked = [item for item in diagnostics if not item.get("audit_ready")]
    return {
        "total": len(diagnostics),
        "audit_ready_count": len(audit_ready),
        "blocked_count": len(blocked),
        "issue_summary": issue_summary,
        "audit_ready_trade_nos": [item["tradeNo"] for item in audit_ready if item.get("tradeNo")],
        "diagnostics": diagnostics,
        "next_action": "先处理 blocked 订单；audit_ready_trade_nos 可确认后批量审核",
    }


def batch_audit_pending_trades_by_filter(
    shop_name: str = None,
    start_trade_time: str = None,
    end_trade_time: str = None,
    operator: str = None,
    limit: int = 200,
) -> dict:
    """
    Query pending sales orders by filter and batch-audit them directly.
    """
    candidates = list_pending_trade_candidates(
        shop_name=shop_name,
        start_trade_time=start_trade_time,
        end_trade_time=end_trade_time,
        page_size=limit,
    )
    trade_nos = [item["tradeNo"] for item in candidates if item.get("tradeNo")]
    if not trade_nos:
        return {
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "failed_results": [],
            "raw": None,
            "matched_trades": [],
        }
    result = batch_audit_trades(trade_nos, operator=operator)
    result["matched_trades"] = candidates
    return result


def batch_update_pending_trades_logistics_by_filter(
    warehouse_name: str,
    logistic_name: str,
    shop_name: str = None,
    start_trade_time: str = None,
    end_trade_time: str = None,
    limit: int = 200,
) -> dict:
    """
    Query pending sales orders by filter and batch-update warehouse/logistics.
    """
    candidates = list_pending_trade_candidates(
        shop_name=shop_name,
        start_trade_time=start_trade_time,
        end_trade_time=end_trade_time,
        page_size=limit,
    )
    update_list = []
    for item in candidates:
        trade_no = item.get("tradeNo")
        if not trade_no:
            continue
        update_list.append(
            {
                "tradeNo": trade_no,
                "warehouseName": warehouse_name,
                "logisticName": logistic_name,
            }
        )
    if not update_list:
        return {
            "total": 0,
            "updated_count": 0,
            "raw": None,
            "matched_trades": [],
        }
    raw = update_logistics_warehouse(update_list)
    return {
        "total": len(update_list),
        "updated_count": len(update_list),
        "raw": raw,
        "matched_trades": candidates,
        "update_list": update_list,
    }


def create_and_approve_trade(order_data: dict, operator: str = None) -> dict:
    """
    Backward-compatible flow kept for old callers and tests.
    Flow: create -> check -> finance_check
    """
    result = {
        "success": False,
        "trade_no": None,
        "steps": [],
    }

    try:
        create_result = create_trade(order_data)
        trade_no = _extract_trade_no(create_result)
        result["trade_no"] = trade_no
        result["steps"].append({
            "step": "create_trade",
            "status": "success",
            "message": f"trade_no={trade_no}",
        })
    except (JackyunAPIError, Exception) as e:
        result["steps"].append({
            "step": "create_trade",
            "status": "failed",
            "message": str(e),
        })
        return result

    try:
        check_trade(trade_no)
        result["steps"].append({
            "step": "check_trade",
            "status": "success",
            "message": trade_no,
        })
    except (JackyunAPIError, Exception) as e:
        result["steps"].append({
            "step": "check_trade",
            "status": "failed",
            "message": str(e),
        })
        return result

    try:
        finance_check_trade(trade_no, operator=operator)
        result["steps"].append({
            "step": "finance_check_trade",
            "status": "success",
            "message": trade_no,
        })
    except (JackyunAPIError, Exception) as e:
        result["steps"].append({
            "step": "finance_check_trade",
            "status": "failed",
            "message": str(e),
        })
        return result

    result["success"] = True
    return result


# [已禁用] ==================== 批量审核（复核） ====================
# [已禁用] reAudit API 已取消订阅，batch_reaudit_trades 不再可用
# def batch_reaudit_trades(trade_nos: list, operator: str) -> dict:
#     """
#     批量复核销售单（财务权限）
#
#     ★ reAudit 接口的 tradeNos 参数支持逗号分隔的多个单号，
#        但为了逐个收集结果和容错，这里按批次处理。
#
#     :param trade_nos: 单号列表 ["YR...", "YR...", ...]
#     :param operator: 操作员名称（财务人员）
#     :return: {
#         "total": int,
#         "success_count": int,
#         "fail_count": int,
#         "results": [{"tradeNo": str, "status": "success"|"fail", "error": str}, ...]
#     }
#     """
#     report = {
#         "total": len(trade_nos),
#         "success_count": 0,
#         "fail_count": 0,
#         "results": [],
#     }
#
#     # 尝试批量提交（逗号分隔）
#     # 如果批量失败则降级为逐个提交
#     if len(trade_nos) <= 50:
#         try:
#             trade_nos_str = ",".join(trade_nos)
#             reaudit_trade(trade_nos_str, operator)
#             # 批量成功
#             for no in trade_nos:
#                 report["results"].append({"tradeNo": no, "status": "success"})
#             report["success_count"] = len(trade_nos)
#             logger.info("批量复核成功: %d 个单号", len(trade_nos))
#             return report
#         except (JackyunAPIError, Exception) as e:
#             logger.warning("批量复核失败，降级为逐个处理: %s", e)
#
#     # 逐个复核
#     for i, trade_no in enumerate(trade_nos):
#         try:
#             reaudit_trade(trade_no, operator)
#             report["results"].append({"tradeNo": trade_no, "status": "success"})
#             report["success_count"] += 1
#             logger.info("[%d/%d] 复核成功: %s", i + 1, len(trade_nos), trade_no)
#         except (JackyunAPIError, Exception) as e:
#             report["results"].append({
#                 "tradeNo": trade_no,
#                 "status": "fail",
#                 "error": str(e),
#             })
#             report["fail_count"] += 1
#             logger.warning("[%d/%d] 复核失败: %s → %s", i + 1, len(trade_nos), trade_no, e)
#
#         if i < len(trade_nos) - 1:
#             time.sleep(0.3)
#
#     return report


def batch_reject_trades(trade_nos: list) -> dict:
    """
    批量驳回销售单

    :param trade_nos: 单号列表
    :return: 同 batch_reaudit_trades 格式
    """
    report = {
        "total": len(trade_nos),
        "success_count": 0,
        "fail_count": 0,
        "results": [],
    }

    for i, trade_no in enumerate(trade_nos):
        try:
            reject_trade(trade_no)
            report["results"].append({"tradeNo": trade_no, "status": "success"})
            report["success_count"] += 1
            logger.info("[%d/%d] 驳回成功: %s", i + 1, len(trade_nos), trade_no)
        except (JackyunAPIError, Exception) as e:
            report["results"].append({
                "tradeNo": trade_no,
                "status": "fail",
                "error": str(e),
            })
            report["fail_count"] += 1
            logger.warning("[%d/%d] 驳回失败: %s → %s", i + 1, len(trade_nos), trade_no, e)

        if i < len(trade_nos) - 1:
            time.sleep(0.3)

    return report


def format_batch_audit_report(report: dict, action: str = "复核") -> str:
    """
    格式化批量审核结果

    :param report: batch_reaudit_trades / batch_reject_trades 的返回值
    :param action: "复核" 或 "驳回"
    :return: Markdown 格式报告
    """
    lines = [f"## 批量{action}结果\n"]
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 总数 | {report['total']} |")
    lines.append(f"| ✅ 成功 | {report['success_count']} |")
    lines.append(f"| ❌ 失败 | {report['fail_count']} |")
    lines.append("")

    results = report.get("results", [])
    if results:
        lines.append(f"| 单号 | 状态 | 详情 |")
        lines.append(f"|------|------|------|")
        for r in results:
            icon = "✅" if r["status"] == "success" else "❌"
            detail = r.get("error", f"{action}成功")
            if len(detail) > 40:
                detail = detail[:37] + "..."
            lines.append(f"| {r['tradeNo']} | {icon} | {detail} |")

    return "\n".join(lines)
