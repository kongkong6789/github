"""
Transfer document helpers based on the official erp.allocate.* API family.
"""
from __future__ import annotations

import logging

import config
from jackyun_api import JackyunValidationError, get_client
from helpers.constants import (
    METHOD_TRANSFER_CLOSE,
    METHOD_TRANSFER_COMPLETE,
    METHOD_TRANSFER_CREATE,
    METHOD_TRANSFER_GET,
    METHOD_TRANSFER_QUICK_CREATE,
)
from helpers.validators import require_fields_or_raise, validate_amount, validate_quantity
from helpers.local_store import append_experience

logger = logging.getLogger(__name__)

VALID_CURRENCIES = {"CNY", "USD", "KRW"}
VALID_TAX_RATES = {"13%", "0%"}
DEFAULT_GOODS_UNIT_NAME = "Pcs"
SAME_COMPANY_CHANNEL = "同主体调拨"
VALID_OUT_CHANNELS = {
    "同主体调拨", "流光-骅韵", "美妆-三清", "美妆-南天", "依然美妆-ACT", "美妆-海纳达", "凤雏-依然",
    "骅韵-美妆", "骅韵-流光溢彩", "易美贸易-依然电商", "易美贸易-ACT", "三清-正品", "正品-南天",
    "正品-美妆", "正品-ACT", "三清-易美贸易", "海纳达-易美贸易", "海纳达-三清", "海纳达-美妆",
    "实业-易美贸易", "实业-三清", "实业-正品", "实业-美妆", "流光-凤雏", "美妆-实业", "美妆-易美",
    "美妆-正品", "易美-美妆", "易美-正品", "正品-三清", "正品-易美", "美妆-依然", "依然-骅韵",
    "依然-流光", "依然-凤雏", "依然-其他", "依然-正品", "易美贸易-海纳达", "流光-其他", "凤雏-其他",
    "易美-三清", "骅韵-依然", "正品-依然", "流光-依然", "易美贸易-实业", "三清-美妆", "骅韵-凤雏",
    "正品-海纳达", "骅韵-其他", "凤雏-骅韵", "其他-ACT", "ACT-易美贸易", "ACT-依然正品", "ACT-三清",
    "ACT-其他（外贸组）", "ACT-依然美妆（UN/DFH）", "ACT-依然电商", "ACT-骅韵（UNOVE)", "ACT-骅韵（DFH)",
    "ACT-依然美妆（HP）", "ACT-依然美妆（AHC）", "ACT-海纳达", "ACT-其他（分销组）", "ACT-依然美妆",
    "博瑞特-三清", "正品-SK", "SK-正品", "SK-美妆", "美妆-其他", "ACT-实业", "正品-实业", "ACT-流光溢彩",
    "正品-骅韵", "三清-实业", "实业-ACT",
}


def _normalize_currency_code(currency_code: str) -> str:
    value = str(currency_code or "").strip().upper()
    alias_map = {
        "RMB": "CNY",
        "人民币": "CNY",
    }
    return alias_map.get(value, value)

TRANSFER_REQUIRED_FIELDS = [
    ("allocateType", "调拨类型"),
    ("applyUserId", "申请人ID"),
    ("applyUserName", "申请人"),
    ("departCode", "部门编号"),
    ("companyCode", "公司编号"),
    ("outWarehouseCode", "调出仓库编号"),
    ("intWarehouseCode", "调入仓库编号"),
]

TRANSFER_DETAIL_REQUIRED_FIELDS = [
    ("unitName", "单位名称"),
    ("skuCount", "数量"),
    ("isCertified", "是否正品"),
]

HEADER_ALIAS_TO_FIELD = {
    "currency_code": "field1",
    "currency": "field1",
    "out_channel": "field3",
    "source_channel": "field3",
    "in_channel": "field4",
    "target_channel": "field4",
    "out_tax_rate": "field5",
    "source_tax_rate": "field5",
    "in_tax_rate": "field6",
    "target_tax_rate": "field6",
}

HEADER_ALIASES = {
    "remark": "memo",
    "notes": "memo",
    "transfer_memo": "memo",
    "transferMemo": "memo",
    "transfer_reason": "reason",
    "transferReason": "reason",
    "reason_name": "reason",
    "reasonName": "reason",
}


def _strip_channel_prefix(channel_name: str) -> str:
    """Normalize inbound-channel labels by removing the company prefix before the first hyphen."""
    value = (channel_name or "").strip()
    if not value or "-" not in value:
        return value
    return value.split("-", 1)[1].strip()


def _normalize_detail(detail: dict) -> dict:
    normalized = dict(detail)

    if "skuCount" not in normalized and "qty" in normalized:
        normalized["skuCount"] = normalized["qty"]
    if "skuBarcode" not in normalized and "barcode" in normalized:
        normalized["skuBarcode"] = normalized["barcode"]
    if "outSkuCode" not in normalized and "outerSkuCode" in normalized:
        normalized["outSkuCode"] = normalized["outerSkuCode"]
    if "rowRemark" not in normalized and "remark" in normalized:
        normalized["rowRemark"] = normalized["remark"]
    if "batchNo" not in normalized and "batch_no" in normalized:
        normalized["batchNo"] = normalized["batch_no"]
    if "batchNos" not in normalized and "batch_no_list" in normalized:
        normalized["batchNos"] = normalized["batch_no_list"]
    if "batchList" not in normalized and "batch_list" in normalized:
        normalized["batchList"] = normalized["batch_list"]

    return normalized


def _apply_header_aliases(normalized: dict) -> dict:
    for alias, field_name in HEADER_ALIAS_TO_FIELD.items():
        if field_name not in normalized and alias in normalized:
            normalized[field_name] = normalized[alias]
    return normalized


def _normalize_transfer_data(transfer_data: dict) -> dict:
    normalized = dict(transfer_data)
    normalized["_providedCompanyCode"] = bool(normalized.get("companyCode"))
    normalized = _apply_header_aliases(normalized)
    for alias, field_name in HEADER_ALIASES.items():
        if field_name not in normalized and alias in normalized:
            normalized[field_name] = normalized[alias]

    if "stockAllocateDetailViews" not in normalized and "goodsList" in normalized:
        normalized["stockAllocateDetailViews"] = normalized["goodsList"]
    if "allocateType" not in normalized:
        if "isDifferentCompany" in normalized:
            normalized["allocateType"] = 1 if normalized["isDifferentCompany"] else 0
        elif "is_cross_company" in normalized:
            normalized["allocateType"] = 1 if normalized["is_cross_company"] else 0

    normalized.setdefault("currencyRate", 1)
    normalized.setdefault("outCurrencyCode", "CNY")
    normalized.setdefault("inCurrencyCode", "CNY")
    normalized.setdefault("status", 0)

    details = normalized.get("stockAllocateDetailViews", []) or []
    normalized["stockAllocateDetailViews"] = [_normalize_detail(item) for item in details]
    return normalized


def _get_warehouse_or_raise(warehouse_code: str, field_label: str) -> dict:
    from modules.warehouse import get_warehouse_by_code

    warehouse = get_warehouse_by_code(warehouse_code)
    if not warehouse:
        raise JackyunValidationError(f"未找到{field_label}: {warehouse_code}")
    return warehouse


def _get_company_by_code(company_code: str):
    from modules.company import resolve_company

    if not company_code:
        return None
    return resolve_company(company_code=f"$eq${company_code}") or resolve_company(company_code=company_code)


def _fill_contact_fields_from_warehouses(transfer_data: dict):
    from modules.warehouse import extract_warehouse_contact

    out_warehouse = _get_warehouse_or_raise(transfer_data.get("outWarehouseCode", ""), "调出仓库")
    in_warehouse = _get_warehouse_or_raise(transfer_data.get("intWarehouseCode", ""), "调入仓库")

    out_contact = extract_warehouse_contact(out_warehouse)
    in_contact = extract_warehouse_contact(in_warehouse)

    contact_aliases = {
        "outContact": out_contact["name"],
        "outContactName": out_contact["name"],
        "senderName": out_contact["name"],
        "deliverName": out_contact["name"],
        "outContactMobile": out_contact["mobile"],
        "senderMobile": out_contact["mobile"],
        "deliverMobile": out_contact["mobile"],
        "outAddress": out_contact["address"],
        "senderAddress": out_contact["address"],
        "deliverAddress": out_contact["address"],
        "intContact": in_contact["name"],
        "intContactName": in_contact["name"],
        "receiverName": in_contact["name"],
        "receiveName": in_contact["name"],
        "intContactMobile": in_contact["mobile"],
        "receiverMobile": in_contact["mobile"],
        "receiveMobile": in_contact["mobile"],
        "intAddress": in_contact["address"],
        "receiverAddress": in_contact["address"],
        "receiveAddress": in_contact["address"],
    }
    for field_name, value in contact_aliases.items():
        if value and not transfer_data.get(field_name):
            transfer_data[field_name] = value

    existing_express_info = transfer_data.get("stockAllocateExpressInfo")
    if existing_express_info is None or isinstance(existing_express_info, dict):
        express_info = dict(existing_express_info or {})
        express_field_candidates = {
            "send": {
                "value": [
                    express_info.get("send"),
                    express_info.get("senderName"),
                    express_info.get("deliverName"),
                    transfer_data.get("senderName"),
                    transfer_data.get("deliverName"),
                    transfer_data.get("outContactName"),
                    transfer_data.get("outContact"),
                    out_contact["name"],
                ],
                "aliases": ["send", "senderName", "deliverName", "outContactName", "outContact"],
            },
            "sendTel": {
                "value": [
                    express_info.get("sendTel"),
                    express_info.get("sendPhone"),
                    express_info.get("senderMobile"),
                    express_info.get("deliverMobile"),
                    transfer_data.get("senderMobile"),
                    transfer_data.get("deliverMobile"),
                    transfer_data.get("outContactMobile"),
                    out_contact["mobile"],
                ],
                "aliases": ["sendTel", "sendPhone", "senderMobile", "deliverMobile", "outContactMobile"],
            },
            "sendAddress": {
                "value": [
                    express_info.get("sendAddress"),
                    express_info.get("senderAddress"),
                    express_info.get("deliverAddress"),
                    transfer_data.get("senderAddress"),
                    transfer_data.get("deliverAddress"),
                    transfer_data.get("outAddress"),
                    out_contact["address"],
                ],
                "aliases": ["sendAddress", "senderAddress", "deliverAddress", "outAddress"],
            },
            "receive": {
                "value": [
                    express_info.get("receive"),
                    express_info.get("receiverName"),
                    express_info.get("receiveName"),
                    transfer_data.get("receiverName"),
                    transfer_data.get("receiveName"),
                    transfer_data.get("intContactName"),
                    transfer_data.get("intContact"),
                    in_contact["name"],
                ],
                "aliases": ["receive", "receiverName", "receiveName", "intContactName", "intContact"],
            },
            "receiveTel": {
                "value": [
                    express_info.get("receiveTel"),
                    express_info.get("receivePhone"),
                    express_info.get("receiverMobile"),
                    express_info.get("receiveMobile"),
                    transfer_data.get("receiverMobile"),
                    transfer_data.get("receiveMobile"),
                    transfer_data.get("intContactMobile"),
                    in_contact["mobile"],
                ],
                "aliases": ["receiveTel", "receivePhone", "receiverMobile", "receiveMobile", "intContactMobile"],
            },
            "receiveAddress": {
                "value": [
                    express_info.get("receiveAddress"),
                    express_info.get("receiverAddress"),
                    transfer_data.get("receiverAddress"),
                    transfer_data.get("receiveAddress"),
                    transfer_data.get("intAddress"),
                    in_contact["address"],
                ],
                "aliases": ["receiveAddress", "receiverAddress", "receiveAddress", "intAddress"],
            },
        }
        for field_name, field_config in express_field_candidates.items():
            selected_value = ""
            for candidate in field_config["value"]:
                if candidate:
                    selected_value = candidate
                    break
            if not selected_value:
                continue
            for alias in field_config["aliases"]:
                express_info[alias] = selected_value
        if express_info:
            transfer_data["stockAllocateExpressInfo"] = express_info

    transfer_data["_resolvedOutWarehouse"] = out_warehouse
    transfer_data["_resolvedIntWarehouse"] = in_warehouse


def _fill_company_fields_from_warehouses(transfer_data: dict):
    out_warehouse = transfer_data.get("_resolvedOutWarehouse") or _get_warehouse_or_raise(
        transfer_data.get("outWarehouseCode", ""),
        "调出仓库",
    )
    in_warehouse = transfer_data.get("_resolvedIntWarehouse") or _get_warehouse_or_raise(
        transfer_data.get("intWarehouseCode", ""),
        "调入仓库",
    )

    out_company_code = str(out_warehouse.get("warehouseCompanyCode") or "")
    in_company_code = str(in_warehouse.get("warehouseCompanyCode") or "")
    out_company = _get_company_by_code(out_company_code) or {}
    in_company = _get_company_by_code(in_company_code) or {}

    app_company = {}
    if not transfer_data.get("companyCode"):
        from modules.company import resolve_company_or_raise

        app_company = resolve_company_or_raise(company_name=config.DEFAULT_APPLICATION_COMPANY_NAME)
        transfer_data["companyCode"] = app_company.get("companyCode")
        transfer_data["companyId"] = app_company.get("companyId") or transfer_data.get("companyId")
    transfer_data["companyName"] = (
        app_company.get("companyName")
        or transfer_data.get("companyName")
        or config.DEFAULT_APPLICATION_COMPANY_NAME
    )

    transfer_data["outCurrencyCode"] = _normalize_currency_code(
        out_company.get("currencyCode") or transfer_data.get("outCurrencyCode") or "CNY"
    )
    transfer_data["inCurrencyCode"] = _normalize_currency_code(
        in_company.get("currencyCode") or transfer_data.get("inCurrencyCode") or "CNY"
    )

    if not transfer_data.get("field1"):
        transfer_data["field1"] = _normalize_currency_code(
            app_company.get("currencyCode") or transfer_data.get("outCurrencyCode") or "CNY"
        )

    transfer_data["_resolvedOutCompany"] = out_company
    transfer_data["_resolvedInCompany"] = in_company


def _resolve_goods_detail(detail: dict) -> dict:
    from modules.goods import resolve_goods_for_transfer

    goods_no = str(detail.get("goodsNo") or "").strip()
    goods_name = str(detail.get("goodsName") or detail.get("goods_name") or "").strip()
    resolved = resolve_goods_for_transfer(goods_no=goods_no, goods_name=goods_name)
    goods = resolved.get("record")

    if goods:
        detail.setdefault("goodsNo", goods.get("goodsNo") or goods_no)
        detail.setdefault("goodsName", goods.get("goodsName") or goods_name)
        detail.setdefault("skuBarcode", goods.get("skuBarcode") or goods.get("barcode") or goods.get("goodsNo"))
        detail.setdefault("outSkuCode", goods.get("outSkuCode") or goods.get("outerSkuCode") or goods.get("skuCode"))
        detail["unitName"] = DEFAULT_GOODS_UNIT_NAME
        detail["_goodsResolution"] = {
            "source": resolved.get("source"),
            "match": resolved.get("match"),
            "goodsNo": detail.get("goodsNo"),
            "goodsName": detail.get("goodsName"),
        }
    else:
        if goods_name and not goods_no:
            raise JackyunValidationError(f"未找到货品名称「{goods_name}」对应档案，请明确货品编号")
        detail["unitName"] = DEFAULT_GOODS_UNIT_NAME
        detail["_goodsResolution"] = {
            "source": None,
            "match": None,
            "goodsNo": goods_no or None,
            "goodsName": goods_name or None,
        }

    detail.setdefault("isCertified", 1)
    return detail


def _auto_fill_goods_details(transfer_data: dict):
    details = transfer_data.get("stockAllocateDetailViews", []) or []
    resolved_details = [_resolve_goods_detail(dict(item)) for item in details]
    transfer_data["stockAllocateDetailViews"] = resolved_details
    transfer_data["_goodsAutoFillSummary"] = [
        {
            "line_index": index,
            **(item.pop("_goodsResolution", {}) or {}),
        }
        for index, item in enumerate(resolved_details, start=1)
    ]


def _extract_batch_requirements(detail: dict) -> dict:
    requirements = detail.get("batch_requirements") or detail.get("batchRequirements") or {}
    if not isinstance(requirements, dict):
        requirements = {}
    for source, target in {
        "batch_no": "batch_no",
        "batchNoRequired": "batch_no",
        "batch_no_contains": "batch_no_contains",
        "batchContains": "batch_no_contains",
        "include_batch_nos": "include_batch_nos",
        "includeBatchNos": "include_batch_nos",
        "exclude_batch_nos": "exclude_batch_nos",
        "excludeBatchNos": "exclude_batch_nos",
        "productionDateFrom": "production_date_from",
        "productionDateTo": "production_date_to",
        "expirationDateFrom": "expiration_date_from",
        "expirationDateTo": "expiration_date_to",
        "minRemainingValidDays": "min_remaining_valid_days",
    }.items():
        if source in detail and target not in requirements:
            requirements[target] = detail[source]
    return requirements


def _auto_select_batches(transfer_data: dict, strategy: str = "fifo", allow_stock_shortage: bool = False):
    from modules.inventory import recommend_batches

    out_warehouse_code = transfer_data.get("outWarehouseCode", "")
    if not out_warehouse_code:
        return

    auto_batch_plans = []
    for index, item in enumerate(transfer_data.get("stockAllocateDetailViews", []) or [], start=1):
        if item.get("batchList") or item.get("batchNo"):
            continue
        if not item.get("goodsNo") and not item.get("goodsName"):
            continue

        requested_quantity = int(item.get("skuCount") or item.get("qty") or 0)
        if requested_quantity <= 0:
            continue

        batch_result = recommend_batches(
            warehouse_code=out_warehouse_code,
            goods_no=item.get("goodsNo"),
            goods_name=item.get("goodsName"),
            required_quantity=requested_quantity,
            strategy=strategy,
            is_batch_management=1,
            **_extract_batch_requirements(item),
        )
        if batch_result.get("enough_stock") is False:
            if allow_stock_shortage:
                item["isBatch"] = 1
                shortage_quantity = batch_result.get("remaining_quantity") or requested_quantity
                auto_batch_plans.append(
                    {
                        "line_index": index,
                        "goods_no": item.get("goodsNo"),
                        "goods_name": item.get("goodsName"),
                        "allocation": [],
                        "status": "stock_shortage_pending",
                        "shortage_quantity": shortage_quantity,
                    }
                )
                continue
            raise JackyunValidationError(
                f"货品 {item.get('goodsNo') or item.get('goodsName') or index} 批次可用库存不足，无法自动分配批次"
            )

        allocation = batch_result.get("recommended_allocation") or []
        if not allocation:
            continue

        item["isBatch"] = 1
        item["batchList"] = [
            {
                "batchNo": row.get("batch_no"),
                "quantity": row.get("quantity"),
                "productionDate": row.get("production_date"),
                "expirationDate": row.get("expiration_date"),
            }
            for row in allocation
            if row.get("batch_no")
        ]
        if len(item["batchList"]) == 1:
            item["batchNo"] = item["batchList"][0]["batchNo"]

        auto_batch_plans.append(
            {
                "line_index": index,
                "goods_no": item.get("goodsNo"),
                "goods_name": item.get("goodsName"),
                "allocation": item["batchList"],
                "status": "allocated",
            }
        )

    if auto_batch_plans:
        transfer_data["batchControlByWarehouse"] = 1
        transfer_data["_autoBatchPlans"] = auto_batch_plans


def _build_auto_fill_summary(transfer_data: dict) -> dict:
    out_company = transfer_data.get("_resolvedOutCompany") or {}
    in_company = transfer_data.get("_resolvedInCompany") or {}
    return {
        "contacts": {
            "sender_name": transfer_data.get("senderName") or transfer_data.get("outContactName"),
            "receiver_name": transfer_data.get("receiverName") or transfer_data.get("intContactName"),
        },
        "companies": {
            "application_company_code": transfer_data.get("companyCode"),
            "out_company_code": out_company.get("companyCode") or transfer_data.get("companyCode"),
            "in_company_code": in_company.get("companyCode"),
            "currency": transfer_data.get("field1"),
            "out_currency": transfer_data.get("outCurrencyCode"),
            "in_currency": transfer_data.get("inCurrencyCode"),
        },
        "applicant": {
            "applyUserId": transfer_data.get("applyUserId"),
            "applyUserName": transfer_data.get("applyUserName"),
            "departCode": transfer_data.get("departCode"),
        },
        "goods": transfer_data.get("_goodsAutoFillSummary", []),
        "batches": transfer_data.get("_autoBatchPlans", []),
    }


def _resolve_and_validate_applicant(transfer_data: dict):
    from modules.user import resolve_default_operator

    applicant = resolve_default_operator(
        user_name=str(transfer_data.get("applyUserName", "")).strip(),
        user_id=transfer_data.get("applyUserId"),
        depart_code=transfer_data.get("departCode"),
    )
    company_name = str(applicant.get("companyName") or "")
    if company_name and config.DEFAULT_APPLICATION_COMPANY_NAME not in company_name:
        raise JackyunValidationError(
            f"申请人「{applicant.get('realName') or applicant.get('userName')}」不属于默认申请公司「{config.DEFAULT_APPLICATION_COMPANY_NAME}」"
        )
    transfer_data["applyUserId"] = applicant.get("userId") or applicant.get("id") or transfer_data.get("applyUserId")
    transfer_data["applyUserName"] = (
        applicant.get("realName") or applicant.get("name") or applicant.get("userName") or transfer_data.get("applyUserName")
    )

    applicant_depart_code = applicant.get("departCode") or applicant.get("departmentCode") or ""
    if applicant_depart_code:
        transfer_data["departCode"] = applicant_depart_code


def _validate_application_company(transfer_data: dict):
    if transfer_data.get("_providedCompanyCode"):
        out_warehouse = transfer_data.get("_resolvedOutWarehouse") or {}
        in_warehouse = transfer_data.get("_resolvedIntWarehouse") or {}
        valid_company_codes = {
            str(out_warehouse.get("warehouseCompanyCode") or ""),
            str(in_warehouse.get("warehouseCompanyCode") or ""),
        }
        valid_company_codes.discard("")
        company_code = str(transfer_data.get("companyCode") or "")
        if valid_company_codes and company_code not in valid_company_codes:
            raise JackyunValidationError(
                f"显式传入的申请公司编码 {company_code} 不属于调出/调入仓公司；如需使用默认申请公司，请不要手动传 companyCode"
            )
    if not transfer_data.get("companyCode"):
        raise JackyunValidationError(f"默认申请公司「{config.DEFAULT_APPLICATION_COMPANY_NAME}」缺少 companyCode")
    if config.DEFAULT_APPLICATION_COMPANY_NAME not in str(transfer_data.get("companyName") or ""):
        raise JackyunValidationError(
            f"调拨单申请公司必须为「{config.DEFAULT_APPLICATION_COMPANY_NAME}」，当前为「{transfer_data.get('companyName')}」"
        )


def _ensure_transfer_reason(transfer_data: dict):
    reason = str(transfer_data.get("reason") or "").strip()
    if not reason:
        return
    from modules.dictionary import ensure_dictionary_item

    ensure_dictionary_item(
        dict_value=transfer_data.get("reasonDictValue") or config.TRANSFER_REASON_DICT_VALUE,
        text=reason,
        auto_create=bool(transfer_data.get("auto_create_dictionary")),
    )


def _apply_custom_field_business_rules(transfer_data: dict):
    allocate_type = str(transfer_data.get("allocateType"))

    if not transfer_data.get("field1"):
        transfer_data["field1"] = transfer_data.get("outCurrencyCode", "CNY")

    if transfer_data.get("field4"):
        transfer_data["field4"] = _strip_channel_prefix(transfer_data["field4"])

    if allocate_type == "0":
        transfer_data["field3"] = SAME_COMPANY_CHANNEL
        transfer_data.setdefault("field5", "0%")
        transfer_data.setdefault("field6", "0%")


def _validate_required_contact_fields(transfer_data: dict):
    required_top_level_fields = {
        "senderName": "调出仓联系人姓名",
        "senderAddress": "调出仓联系人地址",
        "receiverName": "调入仓联系人姓名",
        "receiverAddress": "调入仓联系人地址",
    }
    missing_fields = [
        label for field_name, label in required_top_level_fields.items()
        if not str(transfer_data.get(field_name) or "").strip()
    ]
    if missing_fields:
        raise JackyunValidationError(
            "调拨单联系人信息不完整，请先维护仓库联系人/地址或显式传入这些字段: "
            + "、".join(missing_fields)
        )

    express_info = transfer_data.get("stockAllocateExpressInfo")
    if not isinstance(express_info, dict):
        raise JackyunValidationError("调拨单联系人信息不完整，缺少 stockAllocateExpressInfo")

    required_express_fields = {
        "send": "stockAllocateExpressInfo.send",
        "sendAddress": "stockAllocateExpressInfo.sendAddress",
        "receive": "stockAllocateExpressInfo.receive",
        "receiveAddress": "stockAllocateExpressInfo.receiveAddress",
    }
    missing_express_fields = [
        label for field_name, label in required_express_fields.items()
        if not str(express_info.get(field_name) or "").strip()
    ]
    if missing_express_fields:
        raise JackyunValidationError(
            "调拨单联系人信息不完整，请先维护仓库联系人/地址或显式传入这些字段: "
            + "、".join(missing_express_fields)
        )


def _validate_custom_fields(transfer_data: dict):
    currency = transfer_data.get("field1")
    if currency and currency not in VALID_CURRENCIES:
        raise JackyunValidationError(f"自定义1 币种不合法: {currency}")

    out_channel = transfer_data.get("field3")
    if out_channel and out_channel not in VALID_OUT_CHANNELS:
        raise JackyunValidationError(f"自定义3 调出渠道不合法: {out_channel}")

    if not transfer_data.get("field4"):
        raise JackyunValidationError("自定义4 调入渠道不能为空")

    out_tax_rate = transfer_data.get("field5")
    in_tax_rate = transfer_data.get("field6")
    if out_tax_rate and out_tax_rate not in VALID_TAX_RATES:
        raise JackyunValidationError(f"自定义5 调出税率不合法: {out_tax_rate}")
    if in_tax_rate and in_tax_rate not in VALID_TAX_RATES:
        raise JackyunValidationError(f"自定义6 调入税率不合法: {in_tax_rate}")


def _validate_transfer_data(transfer_data: dict, batch_strategy: str = "fifo", allow_stock_shortage: bool = False):
    transfer_data = _normalize_transfer_data(transfer_data)
    allow_stock_shortage = bool(
        allow_stock_shortage
        or transfer_data.get("allow_stock_shortage")
        or transfer_data.get("allow_stock_shortage_create")
    )
    _fill_contact_fields_from_warehouses(transfer_data)
    _fill_company_fields_from_warehouses(transfer_data)
    _resolve_and_validate_applicant(transfer_data)
    _auto_fill_goods_details(transfer_data)
    _auto_select_batches(
        transfer_data,
        strategy=batch_strategy or transfer_data.get("batchStrategy") or transfer_data.get("batch_strategy") or "fifo",
        allow_stock_shortage=allow_stock_shortage,
    )

    require_fields_or_raise(transfer_data, TRANSFER_REQUIRED_FIELDS)
    _validate_required_contact_fields(transfer_data)

    allocate_type = transfer_data.get("allocateType")
    if str(allocate_type) not in ("0", "1"):
        raise JackyunValidationError("调拨类型只能为 0(同价调拨) 或 1(异价调拨)")

    _validate_application_company(transfer_data)
    _ensure_transfer_reason(transfer_data)
    _apply_custom_field_business_rules(transfer_data)
    _validate_custom_fields(transfer_data)
    transfer_data["_autoFillSummary"] = _build_auto_fill_summary(transfer_data)

    details = transfer_data.get("stockAllocateDetailViews")
    if not isinstance(details, list) or not details:
        raise JackyunValidationError("缺少货品明细(stockAllocateDetailViews)，请至少添加一个货品")

    for index, item in enumerate(details, start=1):
        item["unitName"] = DEFAULT_GOODS_UNIT_NAME
        require_fields_or_raise(item, TRANSFER_DETAIL_REQUIRED_FIELDS)
        if not validate_quantity(item.get("skuCount")):
            raise JackyunValidationError(f"第 {index} 个货品明细数量必须为正整数")

        has_barcode = bool(str(item.get("skuBarcode", "")).strip())
        has_outer_sku = bool(str(item.get("outSkuCode", "")).strip())
        if not has_barcode and not has_outer_sku:
            raise JackyunValidationError(
                f"第 {index} 个货品明细必须至少提供 skuBarcode 或 outSkuCode 其中一个"
            )

        if str(allocate_type) == "1":
            if "skuPrice" not in item or not validate_amount(item.get("skuPrice")):
                raise JackyunValidationError(f"异价调拨时，第 {index} 个货品明细必须填写有效单价 skuPrice")
            if "totalAmount" not in item:
                item["totalAmount"] = float(item["skuPrice"]) * int(item["skuCount"])
            elif not validate_amount(item.get("totalAmount")):
                raise JackyunValidationError(f"异价调拨时，第 {index} 个货品明细总金额 totalAmount 格式不正确")
        else:
            item.pop("skuPrice", None)
            item.pop("totalAmount", None)

    transfer_data.pop("_resolvedOutWarehouse", None)
    transfer_data.pop("_resolvedIntWarehouse", None)
    transfer_data.pop("_resolvedOutCompany", None)
    transfer_data.pop("_resolvedInCompany", None)
    transfer_data.pop("_providedCompanyCode", None)
    transfer_data.pop("_goodsAutoFillSummary", None)
    transfer_data.pop("_autoBatchPlans", None)
    transfer_data.pop("allow_stock_shortage", None)
    transfer_data.pop("allow_stock_shortage_create", None)
    transfer_data.pop("batchStrategy", None)
    transfer_data.pop("batch_strategy", None)
    return transfer_data


def prepare_transfer_payload(
    transfer_data: dict,
    batch_strategy: str = "fifo",
    allow_stock_shortage: bool = False,
) -> tuple[dict, dict]:
    normalized = _validate_transfer_data(
        transfer_data,
        batch_strategy=batch_strategy,
        allow_stock_shortage=allow_stock_shortage,
    )
    summary = normalized.pop("_autoFillSummary", {})
    return normalized, summary


def submit_transfer_payload(normalized: dict, quick_create: bool = False) -> dict:
    client = get_client()
    if quick_create:
        normalized.setdefault("openAllocateType", 1)
        logger.info(
            "Quick creating transfer doc: %s -> %s, openAllocateType=%s",
            normalized.get("outWarehouseCode", ""),
            normalized.get("intWarehouseCode", ""),
            normalized.get("openAllocateType", ""),
        )
        return client.call(METHOD_TRANSFER_QUICK_CREATE, normalized)

    logger.info(
        "Creating transfer doc: %s -> %s, allocateType=%s",
        normalized.get("outWarehouseCode", ""),
        normalized.get("intWarehouseCode", ""),
        normalized.get("allocateType", ""),
    )
    return client.call(METHOD_TRANSFER_CREATE, normalized)


def query_transfers(
    allocate_nos: str = None,
    status: str = None,
    out_status: str = None,
    in_status: str = None,
    out_warehouse_code: str = None,
    in_warehouse_code: str = None,
    start_create_time: str = None,
    end_create_time: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if allocate_nos:
        bizcontent["allocateNos"] = allocate_nos
    if status:
        bizcontent["status"] = status
    if out_status:
        bizcontent["outStatus"] = out_status
    if in_status:
        bizcontent["inStatus"] = in_status
    if out_warehouse_code:
        bizcontent["outWarehouseCode"] = out_warehouse_code
    if in_warehouse_code:
        bizcontent["inWarehouseCode"] = in_warehouse_code
    if start_create_time:
        bizcontent["startCreateTime"] = start_create_time
    if end_create_time:
        bizcontent["endCreateTime"] = end_create_time

    result = client.call(METHOD_TRANSFER_GET, bizcontent)
    data = result.get("result", {}).get("data", {})
    items = data.get("stockAllocate", []) if isinstance(data, dict) else []
    normalized_items = items if isinstance(items, list) else ([items] if items else [])
    append_experience("transfer_query", {"query": bizcontent, "result_count": len(normalized_items)})
    return normalized_items


def query_transfer_by_no(allocate_no: str) -> dict | None:
    """按调拨单号查询单个调拨单。"""
    items = query_transfers(allocate_nos=allocate_no, page_size=5)
    return items[0] if items else None


def extract_allocate_no(create_result: dict) -> str:
    """Extract allocate number from common erp.allocate.* response shapes."""
    result = create_result.get("result", {}) if isinstance(create_result, dict) else {}
    data = result.get("data", {}) if isinstance(result, dict) else {}
    candidates = [result, data]
    for container in candidates:
        if not isinstance(container, dict):
            continue
        for field in ("allocateNo", "allocate_no", "billNo", "bill_no", "docNo", "doc_no"):
            value = container.get(field)
            if value:
                return str(value)
    return ""


def prepare_transfer_batches(
    out_warehouse_code: str,
    goods_list: list,
    strategy: str = "fifo",
    is_batch_management: int = 1,
) -> dict:
    """
    为调拨单货品生成调出仓批次候选与推荐方案。

    该函数只做查询与推荐，不直接创建调拨单。
    """
    from modules.inventory import recommend_batches

    if not out_warehouse_code:
        raise JackyunValidationError("请提供调出仓库编号 outWarehouseCode 后再查询批次")
    if not goods_list:
        raise JackyunValidationError("请提供调拨货品明细后再查询批次推荐")

    recommendations = []
    all_enough_stock = True
    for index, item in enumerate(goods_list, start=1):
        goods_no = item.get("goodsNo")
        goods_name = item.get("goodsName") or item.get("goods_name")
        requested_quantity = item.get("skuCount") or item.get("qty") or item.get("quantity")

        if not goods_no and not goods_name:
            raise JackyunValidationError(f"第 {index} 个调拨货品缺少 goodsNo 或 goodsName，无法查询批次")
        if requested_quantity in (None, "", 0, "0"):
            raise JackyunValidationError(f"第 {index} 个调拨货品缺少数量，无法查询批次")

        batch_result = recommend_batches(
            warehouse_code=out_warehouse_code,
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
        "out_warehouse_code": out_warehouse_code,
        "strategy": strategy,
        "goods_recommendations": recommendations,
        "all_enough_stock": all_enough_stock,
        "next_action": "请先让用户确认调出批次，再把 batchNo 写入调拨单明细后创建单据",
    }


def create_transfer(transfer_data: dict) -> dict:
    normalized, _ = prepare_transfer_payload(transfer_data)
    result = submit_transfer_payload(normalized, quick_create=False)
    append_experience("transfer", {"payload": normalized, "result": result})
    return result


def quick_create_transfer(transfer_data: dict) -> dict:
    normalized, _ = prepare_transfer_payload(transfer_data)
    result = submit_transfer_payload(normalized, quick_create=True)
    append_experience("transfer", {"payload": normalized, "quick_create": True, "result": result})
    return result


def close_transfer(allocate_no: str, reason: str = "") -> dict:
    client = get_client()
    return client.call(METHOD_TRANSFER_CLOSE, {"allocateNo": allocate_no, "reason": reason})


def complete_transfer(allocate_no: str, reason: str = "", memo: str = "", is_not_notify: int = 0) -> dict:
    client = get_client()
    return client.call(
        METHOD_TRANSFER_COMPLETE,
        {
            "allocateNo": allocate_no,
            "reason": reason,
            "memo": memo,
            "isNotNotify": is_not_notify,
        },
    )
