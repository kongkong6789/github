from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import requests
from dotenv import load_dotenv
from src.a2a_ecommerce_demo.connector_registry import (
    PROJECT_ROOT,
    get_connector_dataset,
    get_connector_spec,
    normalize_connector_id,
)

MAX_LIVE_QUERY_LIMIT = 100
JACKYUN_BRAND_EXPANSION_MAX_GOODS = 1000
JACKYUN_BRAND_EXPANSION_MAX_GOODS_PAGES = 10
JACKYUN_INVENTORY_EXPANSION_MAX_PAGES = 20
JACKYUN_INVENTORY_GOODS_NOS_BATCH_SIZE = 5
_ENV_LOCK = threading.RLock()

JACKYUN_BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "unove": ("UNOVE", "Unove", "柔诺伊", "UNOVE柔诺伊", "Unove柔诺伊"),
    "柔诺伊": ("柔诺伊", "UNOVE", "UNOVE柔诺伊", "Unove柔诺伊"),
}
JACKYUN_BRAND_FILTER_KEYS = ("brand", "brand_name", "goods_name", "sku_name")
JACKYUN_PRECISE_GOODS_FILTER_KEYS = ("goods_no", "goods_nos", "sku_barcode")
JACKYUN_CURRENT_QUANTITY_KEYS = (
    "currentQuantity",
    "currentQty",
    "stockQuantity",
    "quantity",
    "qty",
    "totalQuantity",
    "库存",
    "库存数量",
)
JACKYUN_AVAILABLE_QUANTITY_KEYS = (
    "useQuantity",
    "usableQuantity",
    "availableQuantity",
    "canUseQuantity",
    "salableQuantity",
    "qtyAvail",
    "可用库存",
)
JACKYUN_RECENT_SALES_QUANTITY_KEYS: dict[str, tuple[str, ...]] = {
    "yesterday_quantity": ("yesterdayQuantity", "yesterdayQty", "昨日销量", "近1天销量"),
    "three_day_quantity": ("threedayQuantity", "threeDayQuantity", "three_day_quantity", "近3天销量"),
    "week_quantity": ("weekQuantity", "sevenDayQuantity", "weekQty", "近7天销量"),
    "stock_out_quantity": ("stockOutuantity", "stockOutQuantity", "outQuantity", "出库量"),
}
JACKYUN_CHANNEL_SALES_ALLOWED_FILTERS = (
    "start_time",
    "end_time",
    "query_time_begin",
    "query_time_end",
    "date_from",
    "date_to",
    "month",
    "shop_names",
    "shop_ids",
    "channel_include_keyword",
    "channel_exclude_keywords",
    "channel_active_only",
    "filter_time_type",
    "time_type",
    "trade_status",
    "tradeStatus",
    "trade_from",
    "tradeFrom",
    "seller_ids",
    "warehouse_ids",
    "assembly_dimension",
    "sku_ids",
    "goods_no",
    "sku_barcode",
    "goods_name",
    "sku_keyword",
    "brand",
    "brand_name",
)
JACKYUN_CHANNEL_SALES_POST_FILTER_KEYS = (
    "goods_no",
    "sku_barcode",
    "goods_name",
    "sku_keyword",
    "brand",
    "brand_name",
)
JACKYUN_EXCLUDED_MATERIAL_GOODS_KEYWORDS = (
    "内卡纸",
    "卡纸",
    "pvc袋",
    "袋子",
    "包材",
    "纸箱",
    "外箱",
    "塑料薄膜",
    "贴纸",
    "标签",
    "说明书",
)

DEFAULT_JACKYUN_WAREHOUSE_SCOPE_RULES: tuple[dict[str, Any], ...] = (
    {
        "business_scope": "售后",
        "canonical_warehouse": "宝鼎仓（售后仓）",
        "keywords": ("宝鼎", "售后"),
    },
    {
        "business_scope": "大贸",
        "canonical_warehouse": "麦歌仓",
        "keywords": ("麦歌",),
    },
    {
        "business_scope": "跨境",
        "canonical_warehouse": "韩国申通仓",
        "keywords": ("韩国申通",),
    },
    {
        "business_scope": "保税",
        "canonical_warehouse": "菜鸟仓",
        "keywords": ("菜鸟", "保税"),
    },
)
DEFAULT_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH = PROJECT_ROOT / "config" / "jackyun_warehouse_scope_rules.json"


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _load_env() -> None:
    env_path = Path(os.getenv("A2A_ENV_PATH", PROJECT_ROOT / ".env")).expanduser()
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


def _safe_limit(limit: int | str | None) -> int:
    try:
        value = int(limit or 20)
    except (TypeError, ValueError):
        value = 20
    return max(1, min(value, MAX_LIVE_QUERY_LIMIT))


def _parse_filters(filters_json: str = "") -> dict[str, Any]:
    if not filters_json.strip():
        return {}
    try:
        value = json.loads(filters_json)
    except json.JSONDecodeError as exc:
        raise ValueError("filters_json must be a JSON object.") from exc
    if not isinstance(value, dict):
        raise ValueError("filters_json must be a JSON object.")
    return value


def _safe_text(value: Any, *, max_length: int = 120) -> str:
    text = str(value or "").strip()
    return text[:max_length]


def _normalize_brand_key(value: Any) -> str:
    return re.sub(r"[\s_\-]+", "", str(value or "")).lower()


def _unique_texts(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    unique = []
    for value in values:
        text = _safe_text(value)
        key = _normalize_brand_key(text)
        if not text or key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def _jackyun_brand_search_terms(filters: dict[str, Any]) -> list[str]:
    raw_terms = [
        filters.get("brand"),
        filters.get("brand_name"),
        filters.get("goods_name"),
        filters.get("sku_name"),
    ]
    terms = _unique_texts(raw_terms)
    expanded = list(terms)
    for term in terms:
        expanded.extend(JACKYUN_BRAND_ALIASES.get(_normalize_brand_key(term), ()))
    return _unique_texts(expanded)


def _jackyun_dataset_filter_keys(dataset: str, spec: dict[str, Any]) -> list[str]:
    filter_keys = {
        key
        for resource in spec.get("resources", {}).values()
        for key in resource.get("filter_map", {})
    } or set(spec.get("filter_map", {}))
    if dataset in {"inventory_stock", "batch_inventory"}:
        filter_keys.update({"brand", "brand_name"})
    return sorted(filter_keys)


def _jackyun_warehouse_scope_rules_path() -> Path:
    configured = _safe_text(os.getenv("A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH", ""), max_length=500)
    return Path(configured).expanduser() if configured else DEFAULT_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH


def _normalize_jackyun_warehouse_scope_rule(rule: Any) -> dict[str, Any] | None:
    if not isinstance(rule, dict):
        return None
    if rule.get("enabled") is False:
        return None
    business_scope = _safe_text(rule.get("business_scope") or rule.get("scope"))
    canonical_warehouse = _safe_text(rule.get("canonical_warehouse") or rule.get("warehouse"))
    raw_keywords = rule.get("keywords") or rule.get("aliases") or []
    if isinstance(raw_keywords, str):
        keywords = [raw_keywords]
    elif isinstance(raw_keywords, list | tuple):
        keywords = [_safe_text(keyword) for keyword in raw_keywords]
    else:
        keywords = []
    keywords = [keyword for keyword in keywords if keyword]
    if not business_scope or not canonical_warehouse or not keywords:
        return None
    return {
        "business_scope": business_scope,
        "canonical_warehouse": canonical_warehouse,
        "keywords": tuple(keywords),
    }


def get_jackyun_warehouse_scope_rules() -> list[dict[str, Any]]:
    """Load warehouse business-scope rules from config with built-in defaults as fallback."""
    path = _jackyun_warehouse_scope_rules_path()
    raw_rules: Any = DEFAULT_JACKYUN_WAREHOUSE_SCOPE_RULES
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_rules = payload.get("rules", []) if isinstance(payload, dict) else payload
        except (OSError, json.JSONDecodeError):
            raw_rules = DEFAULT_JACKYUN_WAREHOUSE_SCOPE_RULES
    rules = [
        normalized
        for rule in raw_rules
        if (normalized := _normalize_jackyun_warehouse_scope_rule(rule)) is not None
    ]
    if rules:
        return rules
    return [
        normalized
        for rule in DEFAULT_JACKYUN_WAREHOUSE_SCOPE_RULES
        if (normalized := _normalize_jackyun_warehouse_scope_rule(rule)) is not None
    ]


def format_jackyun_warehouse_scope_rules_for_prompt() -> str:
    parts = []
    for rule in get_jackyun_warehouse_scope_rules():
        keywords = "、".join(str(keyword) for keyword in rule["keywords"])
        parts.append(f"{rule['business_scope']}={rule['canonical_warehouse']}（关键词：{keywords}）")
    return "；".join(parts)


def _warehouse_scope_rules_payload() -> list[dict[str, Any]]:
    return [
        {
            "business_scope": rule["business_scope"],
            "canonical_warehouse": rule["canonical_warehouse"],
            "keywords": list(rule["keywords"]),
        }
        for rule in get_jackyun_warehouse_scope_rules()
    ]


def _classify_jackyun_warehouse(row: dict[str, Any]) -> dict[str, str]:
    warehouse_name = _safe_text(row.get("warehouseName") or row.get("仓库") or row.get("warehouse"))
    if not warehouse_name:
        return {}
    for rule in get_jackyun_warehouse_scope_rules():
        if any(keyword in warehouse_name for keyword in rule["keywords"]):
            return {
                "warehouseBusinessScope": str(rule["business_scope"]),
                "warehouseCanonicalName": str(rule["canonical_warehouse"]),
            }
    return {}


def _enrich_jackyun_inventory_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for row in rows:
        warehouse_scope = _classify_jackyun_warehouse(row)
        enriched.append({**row, **warehouse_scope} if warehouse_scope else row)
    return enriched


def _escape_kingdee_filter_value(value: Any) -> str:
    return _safe_text(value).replace("'", "''")


def _redact_erp_error_text(text: Any) -> str:
    redacted = str(text or "")[:500]
    patterns = [
        r"(?i)(appKey(?:\s*=\s*|\s+))[^,\s，。；;]+",
        r"(?i)(appSecret(?:\s*=\s*|\s+))[^,\s，。；;]+",
        r"(?i)(password(?:\s*=\s*|\s+))[^,\s，。；;]+",
        r"(?i)(token(?:\s*=\s*|\s+))[^,\s，。；;]+",
        r"(?i)(secret(?:\s*=\s*|\s+))[^,\s，。；;]+",
    ]
    for pattern in patterns:
        redacted = re.sub(pattern, r"\1***REDACTED***", redacted)
    return redacted


@contextmanager
def _prepend_sys_path(path: str) -> Iterator[None]:
    expanded = str(Path(path).expanduser())
    sys.path.insert(0, expanded)
    try:
        yield
    finally:
        try:
            sys.path.remove(expanded)
        except ValueError:
            pass


JACKYUN_LIVE_DATASETS: dict[str, dict[str, Any]] = {
    "inventory_stock": {
        "label": "吉客云实时库存",
        "method": "erp.stockquantity.get",
        "item_keys": ["goodsStockQuantity", "data", "records", "rows", "list"],
        "filter_map": {
            "warehouse_code": "warehouseCode",
            "goods_no": "goodsNo",
            "goods_name": "goodsName",
            "sku_name": "skuName",
            "sku_barcode": "skuBarcode",
            "unit_name": "unitName",
            "goods_nos": "goodsNos",
            "modified_start": "gmtModifiedStart",
            "modified_end": "gmtModifiedEnd",
        },
    },
    "batch_inventory": {
        "label": "吉客云实时批次库存",
        "method": "erp.batchstockquantity.get",
        "item_keys": ["batchStockQuantity", "goodsStockQuantity", "data", "records", "rows", "list"],
        "filter_map": {
            "warehouse_code": "warehouseCode",
            "goods_no": "goodsNo",
            "goods_name": "goodsName",
            "sku_name": "skuName",
            "sku_barcode": "skuBarcode",
            "batch_no": "batchNo",
            "modified_start": "gmtModifiedStart",
            "modified_end": "gmtModifiedEnd",
        },
    },
    "sales_orders": {
        "label": "吉客云实时销售订单",
        "method": "oms.trade.fullinfoget",
        "item_keys": ["trades", "trade", "data", "records", "rows", "list"],
        "filter_map": {
            "trade_no": "tradeNo",
            "bill_no": "billNo",
            "source_trade_nos": "sourceTradeNos",
            "date_from": "startTradeTime",
            "date_to": "endTradeTime",
            "shop_name": "shopName",
            "trade_status": "tradeStatus",
        },
    },
    "sales_report": {
        "label": "吉客云实时货品销售分析",
        "method": "birc.report.needauth.goodsMultiDimensionalAnalysis",
        "item_keys": ["items", "data", "records", "rows", "list"],
        "filter_map": {
            "date_from": "queryTimeBegin",
            "date_to": "queryTimeEnd",
            "shop_name": "shopName",
            "goods_no": "goodsNo",
            "sku_barcode": "skuBarcode",
        },
    },
    "purchase_orders": {
        "label": "吉客云实时采购订单",
        "method": "erp.purch.get",
        "item_keys": ["purchs", "purchases", "purchaseList", "data", "records", "rows", "list"],
        "filter_map": {
            "purchase_no": "purchNo",
            "vendor_code": "vendCode",
            "vendor_name": "vendName",
            "goods_no": "goodsNo",
            "date_from": "gmtCreateStart",
            "date_to": "gmtCreateEnd",
        },
        "coverage": {
            "purchase_price": "available_from_purchase_or_inbound_docs",
            "lead_time": "available_when_arrive_period_or_plan_in_date_exists",
            "historical_delay": "requires_purchase_vs_receipt_join",
        },
    },
    "stock_inbound": {
        "label": "吉客云实时入库明细",
        "method": "erp.stockin.get.v2",
        "item_keys": ["stockInList", "stockin", "data", "records", "rows", "list"],
        "filter_map": {
            "stock_in_no": "inNo",
            "bill_no": "billNo",
            "rel_data_id": "relDataId",
            "date_from": "gmtCreateStart",
            "date_to": "gmtCreateEnd",
        },
    },
    "stock_outbound": {
        "label": "吉客云实时出库明细",
        "method": "erp.stockout.get.v2",
        "item_keys": ["stockOutList", "stockout", "data", "records", "rows", "list"],
        "filter_map": {
            "stock_out_no": "outNo",
            "bill_no": "billNo",
            "rel_data_id": "relDataId",
            "date_from": "gmtCreateStart",
            "date_to": "gmtCreateEnd",
        },
    },
    "suppliers": {
        "label": "吉客云实时供应商",
        "method": "erp.vend.get",
        "item_keys": ["vendors", "vendList", "data", "records", "rows", "list"],
        "filter_map": {
            "name": "name",
            "code": "code",
            "modified_start": "gmtModifiedStart",
            "modified_end": "gmtModifiedEnd",
        },
        "coverage": {
            "lead_time": "available_when_arrivePeriod_field_returned",
            "purchase_price": "not_in_vendor_master",
            "historical_delay": "requires_purchase_vs_receipt_join",
        },
    },
    "master_data": {
        "label": "吉客云实时基础资料",
        "resources": {
            "warehouses": {
                "method": "erp.warehouse.get",
                "item_keys": ["warehouseInfo", "data", "records", "rows", "list"],
                "filter_map": {
                    "name": "name",
                    "code": "code",
                    "modified_start": "gmtModifiedStart",
                    "modified_end": "gmtModifiedEnd",
                },
            },
            "channels": {
                "method": "erp.sales.get",
                "item_keys": ["salesChannelInfo", "data", "records", "rows", "list"],
                "filter_map": {
                    "name": "name",
                    "code": "code",
                    "modified_start": "gmtModifiedStart",
                    "modified_end": "gmtModifiedEnd",
                },
            },
            "goods": {
                "method": "erp.storage.goodslist",
                "item_keys": ["goods", "goodsList", "goodsInfo", "data", "records", "rows", "list"],
                "filter_map": {
                    "goods_no": "goodsNo",
                    "goods_name": "goodsName",
                    "sku_name": "skuName",
                    "sku_barcode": "skuBarcode",
                    "modified_start": "startDateModifiedSku",
                    "modified_end": "endDateModifiedSku",
                },
            },
        },
    },
}


KINGDEE_LIVE_DATASETS: dict[str, dict[str, Any]] = {
    "suppliers": {
        "label": "金蝶实时供应商",
        "form_id": "BD_Supplier",
        "field_keys": "FNumber,FName,FForbidStatus",
        "keyword_field": "FName",
    },
    "purchase_orders": {
        "label": "金蝶实时采购订单",
        "form_id": "PUR_PurchaseOrder",
        "field_keys": "FBillNo,FDate,FSupplierId.FName,FMaterialId.FNumber,FMaterialId.FName,FQty,FTaxPrice,FAllAmount,FDeliveryDate,FDOCUMENTSTATUS",
        "keyword_field": "FSupplierId.FName",
        "date_field": "FDate",
        "material_filter_fields": ("FMaterialId.FNumber", "FMaterialId.FName"),
        "coverage": {
            "purchase_price": "available_from_PUR_PurchaseOrder_entry",
            "lead_time": "available_when_delivery_date_field_exists",
            "historical_delay": "requires_purchase_vs_receipt_join",
        },
    },
    "supplier_procurement_terms": {
        "label": "金蝶实时供应商采购条款观察",
        "form_id": "PUR_PurchaseOrder",
        "field_keys": "FBillNo,FDate,FSupplierId.FName,FMaterialId.FNumber,FMaterialId.FName,FQty,FTaxPrice,FAllAmount,FDeliveryDate",
        "keyword_field": "FSupplierId.FName",
        "date_field": "FDate",
        "material_filter_fields": ("FMaterialId.FNumber", "FMaterialId.FName"),
        "coverage": {
            "purchase_price": "available_from_PUR_PurchaseOrder_entry",
            "lead_time": "available_when_delivery_date_field_exists",
            "historical_delay": "requires_purchase_vs_receipt_join",
        },
    },
    "sales_outstock": {
        "label": "金蝶实时销售出库",
        "form_id": "SAL_OUTSTOCK",
        "field_keys": "FBillNo,FDate,FCustomerID.FName,FDOCUMENTSTATUS",
        "keyword_field": "FCUSTOMERID.FName",
        "date_field": "FDate",
    },
    "sales_returns": {
        "label": "金蝶实时销售退货",
        "form_id": "SAL_RETURNSTOCK",
        "field_keys": "FBillNo,FDate,FCustomerID.FName,FMaterialID.FNumber,FMaterialID.FName,FREALQTY,FAllAmount,FDOCUMENTSTATUS",
        "keyword_field": "FCUSTOMERID.FName",
        "date_field": "FDate",
    },
    "other_payables": {
        "label": "金蝶实时其他应付",
        "form_id": "AP_OtherPayable",
        "field_keys": "FBillNo,FDate,FCONTACTUNIT.FName,FALLAMOUNTFOR,FDOCUMENTSTATUS",
        "keyword_field": "FCONTACTUNIT.FName",
        "date_field": "FDate",
    },
    "organizations": {
        "label": "金蝶实时组织",
        "form_id": "ORG_Organizations",
        "field_keys": "FNumber,FName,FForbidStatus",
        "keyword_field": "FName",
    },
    "customers": {
        "label": "金蝶实时客户",
        "form_id": "BD_Customer",
        "field_keys": "FNumber,FName,FForbidStatus",
        "keyword_field": "FName",
    },
    "finance_snapshot": {
        "label": "金蝶实时应收快照",
        "form_id": "AR_receivable",
        "field_keys": "FBillNo,FDate,FCUSTOMERID.FName,FDOCUMENTSTATUS",
        "keyword_field": "FCUSTOMERID.FName",
        "date_field": "FDate",
    },
}


SUPPLIER_TERMS_VERIFICATION_TARGETS = [
    ("jackyun_erp", "suppliers"),
    ("jackyun_erp", "purchase_orders"),
    ("jackyun_erp", "stock_inbound"),
    ("kingdee_erp", "supplier_procurement_terms"),
    ("kingdee_erp", "purchase_orders"),
]

SUPPLIER_TERM_FIELD_PATTERNS = {
    "purchase_price": ["采购价", "采购单价", "taxprice", "price", "unitprice", "purchaseprice"],
    "lead_time": ["arriveperiod", "leadtime", "deliverydate", "planindate", "交期", "交货日期", "到货日期"],
    "historical_delay": ["delay", "overdue", "late", "延期", "延误", "逾期"],
}

JACKYUN_INVENTORY_COST_FIELD_KEYS = (
    "costPrice",
    "cost_price",
    "成本价",
    "采购价",
)
JACKYUN_BATCH_COST_FIELD_KEYS = (
    "monthEndCost",
    "endMonthCost",
    "costPrice",
    "taxIncludedCost",
    "taxCostPrice",
    "taxPrice",
    "成本价",
)
JACKYUN_PURCHASE_PRICE_FIELD_KEYS = (
    "price",
    "taxPrice",
    "taxIncludedPrice",
    "unitPrice",
    "purchasePrice",
    "cuPrice",
    "estPrice",
    "estCost",
    "transHasTaxPrice",
    "transNoTaxPrice",
    "采购价",
    "采购单价",
)
KINGDEE_PURCHASE_PRICE_FIELD_KEYS = (
    "FTaxPrice",
    "FPrice",
    "FAllAmount",
)
ERP_ROUTE_INVENTORY_KEYWORDS = ("库存", "分仓", "仓库", "可用", "在途", "临期", "批次", "效期", "周转", "覆盖天数")
ERP_ROUTE_COST_KEYWORDS = ("采购价", "采购单价", "成本价", "成本", "毛利", "库存金额", "金额口径", "金额周转")
ERP_ROUTE_WECOM_KEYWORDS = ("企业微信智能表", "企微智能表", "智能表", "wedoc", "日销", "日销表")
ERP_ROUTE_LIVE_KEYWORDS = ("吉客云", "金蝶", "erp", "实时", "当前", "现在", "最新")
WECOM_SMARTSHEET_URL_PATTERN = re.compile(r"https://doc\.weixin\.qq\.com/smartsheet/[^\s\"'<>）)]+")


def _normalize_field_name(field_name: str) -> str:
    return re.sub(r"[\s_.\-/]+", "", field_name).lower()


def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def _extract_brand_hint(text: str, filters: dict[str, Any]) -> str:
    existing = _safe_text(filters.get("brand") or filters.get("brand_name"))
    if existing:
        return existing
    normalized = text.lower()
    has_unove = "unove" in normalized
    has_rounuoyi = "柔诺伊" in text
    if has_unove and has_rounuoyi:
        return "Unove柔诺伊"
    if has_unove:
        return "UNOVE"
    if has_rounuoyi:
        return "柔诺伊"
    return ""


def _extract_wecom_smartsheet_urls(text: str) -> list[str]:
    urls = []
    seen: set[str] = set()
    for match in WECOM_SMARTSHEET_URL_PATTERN.finditer(text):
        url = match.group(0).rstrip("，。；;、")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _collect_field_paths(value: Any, fields: set[str], prefix: str = "") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            field_path = f"{prefix}.{key}" if prefix else str(key)
            fields.add(field_path)
            _collect_field_paths(nested, fields, field_path)
    elif isinstance(value, list):
        for item in value[:3]:
            _collect_field_paths(item, fields, prefix)


def _row_field_names(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    fields: set[str] = set()
    for row in rows:
        _collect_field_paths(row, fields)
    return sorted(fields)


def _match_supplier_term_fields(fields: list[str], pattern_key: str) -> list[str]:
    patterns = [_normalize_field_name(pattern) for pattern in SUPPLIER_TERM_FIELD_PATTERNS[pattern_key]]
    matched = [
        field
        for field in fields
        if any(pattern and pattern in _normalize_field_name(field) for pattern in patterns)
    ]
    return sorted(dict.fromkeys(matched))


def _find_normalized_field_value(value: Any, normalized_key: str, prefix: str = "") -> tuple[str, Any] | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            field_path = f"{prefix}.{key_text}" if prefix else key_text
            if _normalize_field_name(key_text) == normalized_key or _normalize_field_name(field_path) == normalized_key:
                return field_path, nested
            found = _find_normalized_field_value(nested, normalized_key, field_path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value[:5]):
            found = _find_normalized_field_value(item, normalized_key, f"{prefix}[{index}]" if prefix else f"[{index}]")
            if found is not None:
                return found
    return None


def _first_numeric_field_value(
    rows: list[dict[str, Any]],
    field_keys: tuple[str, ...],
) -> dict[str, Any] | None:
    for field_key in field_keys:
        normalized_key = _normalize_field_name(field_key)
        for row in rows:
            found = _find_normalized_field_value(row, normalized_key)
            if found is None:
                continue
            field_path, value = found
            number = _to_number(value)
            if number is None or number <= 0:
                continue
            return {
                "field": field_path,
                "value": _display_quantity(number),
                "row_preview": _cost_row_preview(row, field_path),
            }
    return None


def _row_has_numeric_field_value(row: dict[str, Any], field_keys: tuple[str, ...]) -> bool:
    for field_key in field_keys:
        found = _find_normalized_field_value(row, _normalize_field_name(field_key))
        if found is None:
            continue
        number = _to_number(found[1])
        if number is not None and number > 0:
            return True
    return False


def _cost_field_coverage(
    rows: list[dict[str, Any]],
    field_keys: tuple[str, ...],
    *,
    row_count: int,
) -> dict[str, Any]:
    returned_row_count = len(rows)
    priced_row_count = sum(1 for row in rows if _row_has_numeric_field_value(row, field_keys))
    missing_row_count = max(returned_row_count - priced_row_count, 0)
    coverage_ratio = round(priced_row_count / returned_row_count, 4) if returned_row_count else None
    if returned_row_count == 0:
        status = "no_rows"
    elif missing_row_count == 0:
        status = "complete_for_returned_rows"
    elif priced_row_count == 0:
        status = "missing_for_returned_rows"
    else:
        status = "partial_for_returned_rows"
    return {
        "status": status,
        "source_row_count": row_count,
        "returned_row_count": returned_row_count,
        "priced_row_count": priced_row_count,
        "missing_row_count": missing_row_count,
        "coverage_ratio": coverage_ratio,
        "complete_for_returned_rows": returned_row_count > 0 and missing_row_count == 0,
        "checked_fields": list(field_keys),
    }


def _cost_row_preview(row: dict[str, Any], selected_field: str) -> dict[str, Any]:
    preview_keys = {
        "goodsNo",
        "skuBarcode",
        "goodsName",
        "warehouseName",
        "batchNo",
        "purchNo",
        "FBillNo",
        "FDate",
        "FSupplierId.FName",
        "FMaterialId.FNumber",
        "FMaterialId.FName",
        "FQty",
        "FTaxPrice",
        "FAllAmount",
        "FDeliveryDate",
        selected_field,
    }
    preview: dict[str, Any] = {}
    for key in preview_keys:
        found = _find_normalized_field_value(row, _normalize_field_name(key))
        if found is not None:
            preview[found[0]] = found[1]
    return preview


def _first_non_empty_row_text(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    for row in rows:
        for key in keys:
            found = _find_normalized_field_value(row, _normalize_field_name(key))
            if found is None:
                continue
            text = _safe_text(found[1])
            if text:
                return text
    return ""


def _cost_reference_filters(filters: dict[str, Any], inventory_rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for date_key in ("date_from", "date_to"):
        if filters.get(date_key):
            output[date_key] = filters[date_key]
    material_no = _safe_text(
        filters.get("material_no")
        or filters.get("goods_no")
        or filters.get("sku")
        or filters.get("sku_barcode")
        or _first_non_empty_row_text(inventory_rows, ("goodsNo", "skuBarcode"))
    )
    if material_no:
        output["goods_no"] = material_no
        return output
    material_name = _safe_text(filters.get("material_name") or filters.get("goods_name"))
    if material_name:
        output["goods_name"] = material_name
        output["material_keyword"] = material_name
        return output
    row_name = _first_non_empty_row_text(inventory_rows, ("goodsName", "skuName"))
    if row_name:
        output["goods_name"] = row_name
        output["material_keyword"] = row_name
        return output
    brand = _safe_text(filters.get("brand") or filters.get("brand_name"))
    if brand:
        output["material_keyword"] = brand
    return output


def _selected_cost_reference(
    *,
    connector_id: str,
    dataset: str,
    rows: list[dict[str, Any]],
    field_keys: tuple[str, ...],
    row_count: int,
) -> dict[str, Any] | None:
    selected = _first_numeric_field_value(rows, field_keys)
    if selected is None:
        return None
    source = f"{connector_id}/{dataset}"
    semantic_boundary = (
        "FTaxPrice 是采购订单含税单价参考，不等同于最终库存核算成本。"
        if connector_id == "kingdee_erp"
        else "吉客云返回的是运营/采购链路中的成本或采购价候选字段，仍需结合财务核算口径复核。"
    )
    return {
        "selected_source": source,
        "selected_field": selected["field"],
        "selected_value": selected["value"],
        "confidence": "reference",
        "semantic_boundary": semantic_boundary,
        "row_count": row_count,
        "row_preview": selected["row_preview"],
    }


def _choose_cost_reference(
    references: list[dict[str, Any]],
    *,
    prefer_procurement_reference: bool,
) -> dict[str, Any] | None:
    if not references:
        return None
    priority = (
        [
            "kingdee_erp/supplier_procurement_terms",
            "jackyun_erp/purchase_orders",
            "jackyun_erp/batch_inventory",
            "jackyun_erp/inventory_stock",
        ]
        if prefer_procurement_reference
        else [
            "jackyun_erp/inventory_stock",
            "kingdee_erp/supplier_procurement_terms",
            "jackyun_erp/purchase_orders",
            "jackyun_erp/batch_inventory",
        ]
    )
    for source in priority:
        for reference in references:
            if reference.get("selected_source") == source:
                return reference
    return references[0]


def _supplier_term_finding(
    checks: list[dict[str, Any]],
    field_key: str,
    *,
    missing_status: str,
    note: str,
) -> dict[str, Any]:
    sources = []
    matched_fields: list[str] = []
    for check in checks:
        fields = [str(field) for field in check.get("fields", [])]
        current_matches = _match_supplier_term_fields(fields, field_key)
        if not current_matches:
            continue
        matched_fields.extend(current_matches)
        sources.append(
            {
                "connector_id": check.get("connector_id", ""),
                "dataset": check.get("dataset", ""),
                "matched_fields": current_matches,
                "row_count": check.get("row_count", 0),
            }
        )
    unique_fields = sorted(dict.fromkeys(matched_fields))
    return {
        "status": "confirmed" if unique_fields else missing_status,
        "matched_fields": unique_fields,
        "sources": sources,
        "note": note,
    }


def _jackyun_read_method_allowlist() -> set[str]:
    methods: set[str] = set()
    for spec in JACKYUN_LIVE_DATASETS.values():
        method = spec.get("method")
        if method:
            methods.add(str(method))
        for resource_spec in spec.get("resources", {}).values():
            resource_method = resource_spec.get("method")
            if resource_method:
                methods.add(str(resource_method))
    return methods


def _assert_jackyun_read_method(method: str) -> None:
    method = method.strip()
    allowed_methods = _jackyun_read_method_allowlist()
    if method not in allowed_methods:
        raise PermissionError(f"吉客云接口当前为只读白名单，禁止调用未登记或写入类方法：{method}")


def list_erp_live_query_capabilities() -> str:
    """列出前端对话可调用的吉客云/金蝶实时只读查询能力，不返回密钥或账套标识。"""
    return _json(
        {
            "mode": "live_read_only_fallback",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "default_route": "优先读取 DuckDB mart；用户明确要求实时 ERP 或本地 mart 缺数据时，才调用这些只读 API。",
            "limit_cap": MAX_LIVE_QUERY_LIMIT,
            "write_guard": {
                "jackyun_allowed_methods": sorted(_jackyun_read_method_allowlist()),
                "kingdee_allowed_method": "ExecuteBillQuery",
                "external_write_api_allowed": False,
            },
            "semantic_tools": [
                {
                    "tool": "route_erp_live_query",
                    "label": "ERP/WeCom/DuckDB 确定性只读路由",
                    "read_only": True,
                    "write_enabled": False,
                },
                {
                    "tool": "query_inventory_cost_reference",
                    "label": "库存成本/采购价只读组合参考",
                    "read_only": True,
                    "write_enabled": False,
                    "semantic_boundary": "金蝶 FTaxPrice 只能作为采购订单含税单价参考，不等同于最终库存核算成本。",
                },
                {
                    "tool": "query_jackyun_channel_sales_summary",
                    "label": "吉客云日期+渠道+SKU 销量/金额只读销售汇总",
                    "read_only": True,
                    "write_enabled": False,
                    "grain": ["日期", "渠道/店铺", "SKU", "销量/金额"],
                    "semantic_boundary": "只读调用吉客云 Skill 销售汇总工作流，不写 ERP；用于销售/出库数量与销售金额口径，不代表库存核算成本。",
                },
            ],
            "jackyun_warehouse_scope_rules_path": str(_jackyun_warehouse_scope_rules_path()),
            "jackyun_warehouse_scope_rules": _warehouse_scope_rules_payload(),
            "connectors": [
                {
                    "connector_id": "jackyun_erp",
                    "display_name": "吉客云 ERP",
                    "permission_scope": "read_only",
                    "external_write_enabled": False,
                    "datasets": [
                        {
                            "dataset": dataset,
                            "label": spec["label"],
                            "read_only": True,
                            "write_enabled": False,
                            "method": spec.get("method", "resource-selected read API"),
                            "resources": sorted(spec.get("resources", {}).keys()),
                            "coverage": spec.get("coverage", {}),
                            "filters": _jackyun_dataset_filter_keys(dataset, spec),
                        }
                        for dataset, spec in JACKYUN_LIVE_DATASETS.items()
                    ],
                },
                {
                    "connector_id": "kingdee_erp",
                    "display_name": "金蝶云星空",
                    "permission_scope": "read_only",
                    "external_write_enabled": False,
                    "datasets": [
                        {
                            "dataset": dataset,
                            "label": spec["label"],
                            "read_only": True,
                            "write_enabled": False,
                            "method": "ExecuteBillQuery",
                            "form_id": spec["form_id"],
                            "coverage": spec.get("coverage", {}),
                            "filters": ["keyword", "date_from", "date_to"],
                        }
                        for dataset, spec in KINGDEE_LIVE_DATASETS.items()
                    ],
                },
            ],
        }
    )


def _trusted_skill_roots() -> list[Path]:
    """Return resolved paths that are allowed to contain executable skill config."""
    from src.a2a_ecommerce_demo.connector_registry import PROJECT_JACKYUN_SKILL_DIR, PROJECT_ROOT

    roots = [PROJECT_ROOT / "skills", PROJECT_JACKYUN_SKILL_DIR]
    extra = os.getenv("A2A_TRUSTED_SKILL_DIRS", "").strip()
    if extra:
        for entry in extra.split(os.pathsep):
            entry = entry.strip()
            if entry:
                roots.append(Path(entry).expanduser())
    return [root.resolve() for root in roots if root]


def _assert_jackyun_skill_dir_trusted(skill_path: Path) -> None:
    """Reject skill_path unless it resolves inside a trusted project skills directory.

    Prevents arbitrary config.py execution from untrusted directories and blocks
    symlink escapes that resolve outside allowed roots.
    """
    resolved = skill_path.resolve()
    roots = _trusted_skill_roots()
    if not roots:
        raise PermissionError("无可用的可信技能目录；请配置 A2A_TRUSTED_SKILL_DIRS 或确保项目 skills/ 目录存在。")
    for root in roots:
        try:
            resolved.relative_to(root)
            return
        except ValueError:
            continue
    raise PermissionError(
        f"吉客云 skill 目录不在可信范围内：{skill_path}。"
        f"允许的根目录：{', '.join(str(r) for r in roots)}"
    )


def _import_jackyun_config(skill_path: Path) -> Any:
    _assert_jackyun_skill_dir_trusted(skill_path)
    config_path = skill_path / "config.py"
    example_path = skill_path / "config.example.py"
    selected_path = config_path if config_path.exists() else example_path
    if not selected_path.exists():
        raise ModuleNotFoundError(f"吉客云 config.py/config.example.py 缺失：{skill_path}")
    spec = importlib.util.spec_from_file_location("config", selected_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"吉客云配置无法加载：{selected_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["config"] = module
    spec.loader.exec_module(module)
    return module


def _call_jackyun_openapi(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, Any]:
    _assert_jackyun_read_method(method)
    skill_path = Path(skill_dir).expanduser()
    if not (skill_path / "jackyun_api.py").exists():
        raise RuntimeError(f"吉客云 skill/API 目录不可用：{skill_path}")
    with _ENV_LOCK:
        previous_strategy = os.environ.get("JACKYUN_CALL_STRATEGY")
        saved_modules = {name: sys.modules.get(name) for name in ("config", "jackyun_api")}
        os.environ["JACKYUN_CALL_STRATEGY"] = "http"
        with _prepend_sys_path(str(skill_path)):
            config = None
            previous_config_strategy = None
            try:
                for module_name in saved_modules:
                    sys.modules.pop(module_name, None)
                config = cast(Any, _import_jackyun_config(skill_path))
                missing_credentials = [
                    name
                    for name in ("JACKYUN_APP_KEY", "JACKYUN_APP_SECRET")
                    if not str(getattr(config, name, "") or "").strip()
                ]
                if missing_credentials:
                    raise RuntimeError(f"吉客云凭据环境变量未配置：{', '.join(missing_credentials)}")
                previous_config_strategy = getattr(config, "JACKYUN_CALL_STRATEGY", None)
                setattr(config, "JACKYUN_CALL_STRATEGY", "http")
                jackyun_api = importlib.import_module("jackyun_api")
                return jackyun_api.get_client().call(method, bizcontent)
            finally:
                if config is not None and previous_config_strategy is not None:
                    setattr(config, "JACKYUN_CALL_STRATEGY", previous_config_strategy)
                if previous_strategy is None:
                    os.environ.pop("JACKYUN_CALL_STRATEGY", None)
                else:
                    os.environ["JACKYUN_CALL_STRATEGY"] = previous_strategy
                for module_name in saved_modules:
                    sys.modules.pop(module_name, None)
                for module_name, module in saved_modules.items():
                    if module is not None:
                        sys.modules[module_name] = module


def _jackyun_skill_module_names() -> list[str]:
    prefixes = ("modules", "helpers")
    exact = {"config", "jackyun_api"}
    return [
        name
        for name in list(sys.modules)
        if name in exact or any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)
    ]


@contextmanager
def _isolated_jackyun_skill_imports(skill_path: Path) -> Iterator[None]:
    with _ENV_LOCK:
        previous_strategy = os.environ.get("JACKYUN_CALL_STRATEGY")
        module_names = _jackyun_skill_module_names()
        saved_modules = {name: sys.modules.get(name) for name in module_names}
        os.environ["JACKYUN_CALL_STRATEGY"] = "http"
        with _prepend_sys_path(str(skill_path)):
            try:
                for module_name in module_names:
                    sys.modules.pop(module_name, None)
                yield
            finally:
                if previous_strategy is None:
                    os.environ.pop("JACKYUN_CALL_STRATEGY", None)
                else:
                    os.environ["JACKYUN_CALL_STRATEGY"] = previous_strategy
                for module_name in _jackyun_skill_module_names():
                    sys.modules.pop(module_name, None)
                for module_name, module in saved_modules.items():
                    if module is not None:
                        sys.modules[module_name] = module


def _call_jackyun_channel_sales_summary(skill_dir: str, query_kwargs: dict[str, object]) -> dict[str, Any]:
    skill_path = Path(skill_dir).expanduser()
    if not (skill_path / "modules" / "reports.py").exists():
        raise RuntimeError(f"吉客云销售汇总 Skill 不可用：{skill_path / 'modules' / 'reports.py'}")
    with _isolated_jackyun_skill_imports(skill_path):
        config = None
        previous_config_strategy = None
        config = cast(Any, _import_jackyun_config(skill_path))
        missing_credentials = [
            name
            for name in ("JACKYUN_APP_KEY", "JACKYUN_APP_SECRET")
            if not str(getattr(config, name, "") or "").strip()
        ]
        if missing_credentials:
            raise RuntimeError(f"吉客云凭据环境变量未配置：{', '.join(missing_credentials)}")
        previous_config_strategy = getattr(config, "JACKYUN_CALL_STRATEGY", None)
        try:
            setattr(config, "JACKYUN_CALL_STRATEGY", "http")
            reports = importlib.import_module("modules.reports")
            result = reports.query_channel_sales_summary(**query_kwargs)
        finally:
            if previous_config_strategy is not None:
                setattr(config, "JACKYUN_CALL_STRATEGY", previous_config_strategy)
        if not isinstance(result, dict):
            raise RuntimeError(f"吉客云销售汇总 Skill 返回结构异常：{type(result).__name__}")
        return result


def _extract_rows_from_mapping(value: Any, item_keys: list[str]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []
    for key in item_keys:
        if key not in value:
            continue
        item = value.get(key)
        return _extract_rows_from_mapping(item, item_keys)
    return [value] if value else []


def _extract_jackyun_rows(response: dict[str, Any], item_keys: list[str]) -> list[dict[str, Any]]:
    result = response.get("result", {})
    data = result.get("data", result) if isinstance(result, dict) else result
    return _extract_rows_from_mapping(data, item_keys)


def _select_jackyun_query(dataset: str, filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    spec = JACKYUN_LIVE_DATASETS[dataset]
    if dataset == "master_data":
        resource = _safe_text(filters.get("resource") or "warehouses").lower()
        resource_spec = spec["resources"].get(resource)
        if not resource_spec:
            resources = ", ".join(sorted(spec["resources"]))
            raise ValueError(f"Unsupported jackyun master_data resource: {resource}. Supported: {resources}")
        return resource, resource_spec
    return dataset, spec


def _build_jackyun_bizcontent(query_spec: dict[str, Any], filters: dict[str, Any], limit: int) -> dict[str, object]:
    try:
        page_index = max(0, int(filters.get("page_index", 0) or 0))
    except (TypeError, ValueError):
        page_index = 0
    payload: dict[str, object] = {"pageIndex": page_index, "pageSize": limit}
    for filter_key, api_key in query_spec.get("filter_map", {}).items():
        value = filters.get(filter_key)
        if value not in (None, ""):
            payload[str(api_key)] = _safe_text(value)
    return payload


def _query_jackyun_rows(
    query_spec: dict[str, Any],
    filters: dict[str, Any],
    limit: int,
    skill_dir: str,
) -> tuple[list[dict[str, Any]], dict[str, object]]:
    payload = _build_jackyun_bizcontent(query_spec, filters, limit)
    response = _call_jackyun_openapi(str(query_spec["method"]), payload, skill_dir)
    rows = _extract_jackyun_rows(response, [str(item) for item in query_spec["item_keys"]])
    return rows, payload


def _jackyun_row_goods_no(row: dict[str, Any]) -> str:
    return _safe_text(row.get("goodsNo") or row.get("goods_no") or row.get("goodsCode") or row.get("skuCode"))


def _jackyun_row_sku_barcode(row: dict[str, Any]) -> str:
    return _safe_text(row.get("skuBarcode") or row.get("barcode") or row.get("barCode") or row.get("产品条码"))


def _jackyun_row_goods_name(row: dict[str, Any]) -> str:
    return _safe_text(row.get("goodsName") or row.get("goods_name") or row.get("skuName") or row.get("产品名称"))


def _dedupe_jackyun_goods(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    goods: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        goods_no = _jackyun_row_goods_no(row)
        sku_barcode = _jackyun_row_sku_barcode(row)
        goods_name = _jackyun_row_goods_name(row)
        key = _normalize_brand_key(goods_no or sku_barcode or goods_name)
        if not key or key in seen:
            continue
        seen.add(key)
        goods.append(row)
    return goods


def _jackyun_truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    text = str(value or "").strip().lower()
    return text in {"1", "1.0", "true", "yes", "y", "是"}


def _filter_jackyun_brand_goods(goods_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    kept: list[dict[str, Any]] = []
    excluded = {
        "deleted": 0,
        "blocked": 0,
        "package_goods": 0,
        "material_goods": 0,
    }
    for goods in goods_rows:
        if _jackyun_truthy_flag(goods.get("isDelete")):
            excluded["deleted"] += 1
            continue
        if _jackyun_truthy_flag(goods.get("isBlockup")) or _jackyun_truthy_flag(goods.get("skuIsBlockup")):
            excluded["blocked"] += 1
            continue
        if _jackyun_truthy_flag(goods.get("isPackageGood")):
            excluded["package_goods"] += 1
            continue
        goods_name = _jackyun_row_goods_name(goods).lower()
        if any(keyword.lower() in goods_name for keyword in JACKYUN_EXCLUDED_MATERIAL_GOODS_KEYWORDS):
            excluded["material_goods"] += 1
            continue
        kept.append(goods)
    return kept, {key: value for key, value in excluded.items() if value}


def _chunks(values: list[Any], size: int) -> Iterator[list[Any]]:
    chunk_size = max(1, size)
    for index in range(0, len(values), chunk_size):
        yield values[index : index + chunk_size]


def _to_number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _row_quantity(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in row:
            continue
        number = _to_number(row.get(key))
        if number is not None:
            return number
    return None


def _display_quantity(value: float) -> int | float:
    if abs(value - round(value)) < 0.000001:
        return int(round(value))
    return round(value, 4)


def _merge_jackyun_goods_metadata(row: dict[str, Any], goods: dict[str, Any]) -> dict[str, Any]:
    merged = dict(row)
    goods_no = _jackyun_row_goods_no(goods)
    sku_barcode = _jackyun_row_sku_barcode(goods)
    goods_name = _jackyun_row_goods_name(goods)
    if goods_no and not _jackyun_row_goods_no(merged):
        merged["goodsNo"] = goods_no
    if sku_barcode and not _jackyun_row_sku_barcode(merged):
        merged["skuBarcode"] = sku_barcode
    if goods_name and not _jackyun_row_goods_name(merged):
        merged["goodsName"] = goods_name
    return merged


def _aggregate_jackyun_inventory_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_zeroes = {metric: 0.0 for metric in JACKYUN_RECENT_SALES_QUANTITY_KEYS}
    totals = {
        "row_count": len(rows),
        "current_quantity": 0.0,
        "available_quantity": 0.0,
        **metric_zeroes,
    }
    by_scope: dict[tuple[str, str], dict[str, Any]] = {}
    by_warehouse: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_goods: dict[tuple[str, str, str], dict[str, Any]] = {}

    def empty_bucket(**values: Any) -> dict[str, Any]:
        return {
            **values,
            "row_count": 0,
            "current_quantity": 0.0,
            "available_quantity": 0.0,
            **metric_zeroes,
        }

    def row_metrics(row: dict[str, Any]) -> dict[str, float | None]:
        return {
            metric: _row_quantity(row, keys)
            for metric, keys in JACKYUN_RECENT_SALES_QUANTITY_KEYS.items()
        }

    def add_quantity(
        bucket: dict[str, Any],
        current: float | None,
        available: float | None,
        metrics: dict[str, float | None],
    ) -> None:
        bucket["row_count"] += 1
        if current is not None:
            bucket["current_quantity"] += current
        if available is not None:
            bucket["available_quantity"] += available
        for metric, value in metrics.items():
            if value is not None:
                bucket[metric] += value

    for row in rows:
        current = _row_quantity(row, JACKYUN_CURRENT_QUANTITY_KEYS)
        available = _row_quantity(row, JACKYUN_AVAILABLE_QUANTITY_KEYS)
        metrics = row_metrics(row)
        if current is not None:
            totals["current_quantity"] += current
        if available is not None:
            totals["available_quantity"] += available
        for metric, value in metrics.items():
            if value is not None:
                totals[metric] += value

        scope = _safe_text(row.get("warehouseBusinessScope") or "未归类")
        canonical = _safe_text(row.get("warehouseCanonicalName"))
        scope_key = (scope, canonical)
        by_scope.setdefault(
            scope_key,
            empty_bucket(
                business_scope=scope,
                canonical_warehouse=canonical,
            ),
        )
        add_quantity(by_scope[scope_key], current, available, metrics)

        warehouse_name = _safe_text(row.get("warehouseName") or row.get("仓库") or row.get("warehouse"))
        warehouse_key = (scope, canonical, warehouse_name or "未命名仓")
        by_warehouse.setdefault(
            warehouse_key,
            empty_bucket(
                business_scope=scope,
                canonical_warehouse=canonical,
                warehouse_name=warehouse_name or "未命名仓",
            ),
        )
        add_quantity(by_warehouse[warehouse_key], current, available, metrics)

        goods_no = _jackyun_row_goods_no(row)
        sku_barcode = _jackyun_row_sku_barcode(row)
        goods_name = _jackyun_row_goods_name(row)
        goods_key = (goods_no, sku_barcode, goods_name)
        by_goods.setdefault(
            goods_key,
            empty_bucket(
                goodsNo=goods_no,
                skuBarcode=sku_barcode,
                goodsName=goods_name,
            ),
        )
        add_quantity(by_goods[goods_key], current, available, metrics)

    def formatted(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output = []
        for item in items:
            formatted_item = dict(item)
            formatted_item["current_quantity"] = _display_quantity(float(item["current_quantity"]))
            formatted_item["available_quantity"] = _display_quantity(float(item["available_quantity"]))
            for metric in JACKYUN_RECENT_SALES_QUANTITY_KEYS:
                formatted_item[metric] = _display_quantity(float(item[metric]))
            output.append(formatted_item)
        return sorted(output, key=lambda item: float(item.get("current_quantity", 0)), reverse=True)

    return {
        "totals": {
            "row_count": totals["row_count"],
            "current_quantity": _display_quantity(totals["current_quantity"]),
            "available_quantity": _display_quantity(totals["available_quantity"]),
            **{
                metric: _display_quantity(float(totals[metric]))
                for metric in JACKYUN_RECENT_SALES_QUANTITY_KEYS
            },
        },
        "recent_sales_metric_source": (
            "yesterday_quantity/three_day_quantity/week_quantity/stock_out_quantity "
            "来自吉客云库存接口返回的近销或出库字段，可用于实时数量口径覆盖天数估算，"
            "不等同于完整销售订单明细。"
        ),
        "by_business_scope": formatted(list(by_scope.values())),
        "by_warehouse": formatted(list(by_warehouse.values())),
        "top_goods": formatted(list(by_goods.values()))[:20],
    }


def _should_expand_jackyun_brand_inventory(dataset: str, filters: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    if dataset not in {"inventory_stock", "batch_inventory"}:
        return False
    if any(_safe_text(filters.get(key)) for key in JACKYUN_PRECISE_GOODS_FILTER_KEYS):
        return False
    if not _jackyun_brand_search_terms(filters):
        return False
    if _safe_text(filters.get("brand") or filters.get("brand_name")):
        return True
    return not rows


def _inventory_brand_base_filters(filters: dict[str, Any]) -> dict[str, Any]:
    excluded = set(JACKYUN_BRAND_FILTER_KEYS) | set(JACKYUN_PRECISE_GOODS_FILTER_KEYS) | {"resource", "page_index"}
    return {key: value for key, value in filters.items() if key not in excluded}


def _expand_jackyun_brand_inventory(
    dataset: str,
    filters: dict[str, Any],
    query_spec: dict[str, Any],
    skill_dir: str,
) -> dict[str, Any]:
    terms = _jackyun_brand_search_terms(filters)
    goods_spec = JACKYUN_LIVE_DATASETS["master_data"]["resources"]["goods"]
    warnings: list[str] = []
    raw_goods_rows: list[dict[str, Any]] = []
    incomplete = False

    for term in terms:
        for page_index in range(JACKYUN_BRAND_EXPANSION_MAX_GOODS_PAGES):
            goods_filters = {"resource": "goods", "goods_name": term, "page_index": page_index}
            goods_rows, _ = _query_jackyun_rows(goods_spec, goods_filters, MAX_LIVE_QUERY_LIMIT, skill_dir)
            raw_goods_rows.extend(goods_rows)
            if len(goods_rows) < MAX_LIVE_QUERY_LIMIT:
                break
            if page_index == JACKYUN_BRAND_EXPANSION_MAX_GOODS_PAGES - 1:
                incomplete = True
                warnings.append(f"货品主数据搜索词 {term} 已达到分页上限，结果可能不完整。")

    raw_matched_goods = _dedupe_jackyun_goods(raw_goods_rows)
    matched_goods, excluded_goods_counts = _filter_jackyun_brand_goods(raw_matched_goods)
    if len(matched_goods) > JACKYUN_BRAND_EXPANSION_MAX_GOODS:
        incomplete = True
        warnings.append(
            f"命中货品 {len(matched_goods)} 个，当前最多展开查询 {JACKYUN_BRAND_EXPANSION_MAX_GOODS} 个。"
        )
    goods_to_query = matched_goods[:JACKYUN_BRAND_EXPANSION_MAX_GOODS]

    inventory_rows: list[dict[str, Any]] = []
    queried_goods_count = 0
    skipped_goods_count = 0
    base_filters = _inventory_brand_base_filters(filters)

    goods_with_no = [goods for goods in goods_to_query if _jackyun_row_goods_no(goods)]
    goods_without_no = [goods for goods in goods_to_query if not _jackyun_row_goods_no(goods)]
    query_batches: list[tuple[str, str, list[dict[str, Any]]]] = []
    if dataset == "inventory_stock":
        for goods_chunk in _chunks(goods_with_no, JACKYUN_INVENTORY_GOODS_NOS_BATCH_SIZE):
            goods_nos = [_jackyun_row_goods_no(goods) for goods in goods_chunk]
            query_batches.append(("goods_nos", ",".join(goods_nos), goods_chunk))
    else:
        for goods in goods_with_no:
            query_batches.append(("goods_no", _jackyun_row_goods_no(goods), [goods]))
    for goods in goods_without_no:
        sku_barcode = _jackyun_row_sku_barcode(goods)
        if sku_barcode:
            query_batches.append(("sku_barcode", sku_barcode, [goods]))
        else:
            skipped_goods_count += 1

    for goods_filter_key, goods_filter_value, batch_goods in query_batches:
        queried_goods_count += len(batch_goods)
        batch_goods_by_no = {_jackyun_row_goods_no(goods): goods for goods in batch_goods if _jackyun_row_goods_no(goods)}
        batch_goods_by_barcode = {
            _jackyun_row_sku_barcode(goods): goods for goods in batch_goods if _jackyun_row_sku_barcode(goods)
        }
        for page_index in range(JACKYUN_INVENTORY_EXPANSION_MAX_PAGES):
            inventory_filters = {
                **base_filters,
                goods_filter_key: goods_filter_value,
                "page_index": page_index,
            }
            page_rows, _ = _query_jackyun_rows(query_spec, inventory_filters, MAX_LIVE_QUERY_LIMIT, skill_dir)
            if not page_rows:
                break
            for row in page_rows:
                goods = (
                    batch_goods_by_no.get(_jackyun_row_goods_no(row))
                    or batch_goods_by_barcode.get(_jackyun_row_sku_barcode(row))
                    or (batch_goods[0] if len(batch_goods) == 1 else {})
                )
                inventory_rows.append(_merge_jackyun_goods_metadata(row, goods) if goods else row)
            if len(page_rows) < MAX_LIVE_QUERY_LIMIT:
                break
            if page_index == JACKYUN_INVENTORY_EXPANSION_MAX_PAGES - 1:
                incomplete = True
                warnings.append(f"货品过滤 {goods_filter_key}={goods_filter_value} 库存行已达到分页上限，结果可能不完整。")

    if skipped_goods_count:
        warnings.append(f"{skipped_goods_count} 个货品缺少 goodsNo/skuBarcode，已跳过库存展开查询。")

    inventory_rows = _enrich_jackyun_inventory_rows(inventory_rows)
    return {
        "enabled": True,
        "reason": "direct_inventory_query_empty_or_brand_filter_expanded_via_master_data",
        "search_terms": terms,
        "goods_filter_policy": {
            "exclude_deleted": True,
            "exclude_blocked": True,
            "exclude_package_goods": True,
            "exclude_material_goods_keywords": list(JACKYUN_EXCLUDED_MATERIAL_GOODS_KEYWORDS),
        },
        "raw_matched_goods_count": len(raw_matched_goods),
        "matched_goods_count": len(matched_goods),
        "excluded_goods_counts": excluded_goods_counts,
        "queried_goods_count": queried_goods_count,
        "inventory_row_count": len(inventory_rows),
        "incomplete": incomplete,
        "warnings": warnings,
        "summary": _aggregate_jackyun_inventory_rows(inventory_rows),
        "rows": inventory_rows,
    }


def _find_kingdee_datacenter_id(skill_dir: str) -> str:
    env_value = _safe_text(os.getenv("KINGDEE_ACCT_ID", ""))
    if env_value:
        return env_value
    root = Path(skill_dir).expanduser()
    candidates = [
        root / "docs" / "金蝶单据导入字段字典.md",
        root / "data" / "output" / "_gaps2_out.txt",
        root / "data" / "output" / "_create_out.txt",
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"(?:DBID|DBid)[\"：:\s]+([0-9a-f]{8,})", text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _login_kingdee_session(skill_dir: str) -> requests.Session:
    _load_env()
    base_url = _safe_text(os.getenv("KINGDEE_BASE_URL", "")).rstrip("/")
    username = _safe_text(os.getenv("KINGDEE_USERNAME", ""))
    password = str(os.getenv("KINGDEE_PASSWORD", ""))
    lcid = int(os.getenv("KINGDEE_LCID", "2052") or "2052")
    datacenter_id = _find_kingdee_datacenter_id(skill_dir)
    missing = [
        name
        for name, value in {
            "KINGDEE_BASE_URL": base_url,
            "KINGDEE_USERNAME": username,
            "KINGDEE_PASSWORD": password,
            "KINGDEE_DATACENTER_ID_OR_LOCAL_HINT": datacenter_id,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"金蝶登录配置不完整：{', '.join(missing)}")
    session = requests.Session()
    url = f"{base_url}/Kingdee.BOS.WebApi.ServicesStub.AuthService.ValidateUser.common.kdsvc"
    response = session.post(
        url,
        json={"acctid": datacenter_id, "username": username, "password": password, "lcid": lcid},
        timeout=15,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        preview = (response.text or "")[:200]
        raise RuntimeError(f"金蝶登录返回非 JSON：HTTP {response.status_code}; preview={preview}") from exc
    if not payload.get("IsSuccessByAPI"):
        message = payload.get("Message") or (payload.get("Result") or {}).get("Message") or "未知登录失败"
        raise RuntimeError(f"金蝶登录失败：{message}")
    return session


def _execute_kingdee_bill_query(
    *,
    form_id: str,
    field_keys: str,
    filter_string: str,
    limit: int,
    start_row: int,
    skill_dir: str,
) -> list[list[Any]]:
    _load_env()
    base_url = _safe_text(os.getenv("KINGDEE_BASE_URL", "")).rstrip("/")
    session = _login_kingdee_session(skill_dir)
    query_url = f"{base_url}/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc"
    query_data = {
        "FormId": form_id,
        "FieldKeys": field_keys,
        "FilterString": filter_string,
        "TopRowCount": limit,
        "StartRow": start_row,
        "Limit": limit,
    }
    response = session.post(query_url, json={"data": json.dumps(query_data, ensure_ascii=False)}, timeout=20)
    try:
        rows = response.json()
    except ValueError as exc:
        preview = (response.text or "")[:200]
        raise RuntimeError(f"金蝶 ExecuteBillQuery 返回非 JSON：HTTP {response.status_code}; preview={preview}") from exc
    if not isinstance(rows, list):
        raise RuntimeError(f"金蝶 ExecuteBillQuery 返回结构异常：{type(rows).__name__}")
    return rows


def _build_kingdee_filter(query_spec: dict[str, Any], filters: dict[str, Any]) -> str:
    clauses = []
    keyword = _escape_kingdee_filter_value(filters.get("keyword"))
    keyword_field = query_spec.get("keyword_field")
    if keyword and keyword_field:
        clauses.append(f"{keyword_field} like '%{keyword}%'")
    date_field = query_spec.get("date_field")
    date_from = _escape_kingdee_filter_value(filters.get("date_from"))
    date_to = _escape_kingdee_filter_value(filters.get("date_to"))
    if date_field and date_from:
        clauses.append(f"{date_field} >= '{date_from}'")
    if date_field and date_to:
        clauses.append(f"{date_field} <= '{date_to}'")
    material_no = _escape_kingdee_filter_value(
        filters.get("material_no") or filters.get("goods_no") or filters.get("sku") or filters.get("sku_barcode")
    )
    material_name = _escape_kingdee_filter_value(filters.get("material_name") or filters.get("goods_name"))
    material_keyword = _escape_kingdee_filter_value(filters.get("material_keyword") or filters.get("sku_keyword"))
    material_fields = tuple(query_spec.get("material_filter_fields") or ("", ""))
    material_number_field = str(material_fields[0]) if len(material_fields) > 0 else ""
    material_name_field = str(material_fields[1]) if len(material_fields) > 1 else ""
    if material_no and material_number_field:
        clauses.append(f"{material_number_field} = '{material_no}'")
    if material_name and material_name_field:
        clauses.append(f"{material_name_field} like '%{material_name}%'")
    if material_keyword and material_number_field and material_name_field:
        clauses.append(
            f"({material_number_field} like '%{material_keyword}%' OR {material_name_field} like '%{material_keyword}%')"
        )
    return " AND ".join(clauses)


def _normalize_kingdee_rows(field_keys: str, rows: list[Any]) -> list[dict[str, Any]]:
    fields = [field.strip() for field in field_keys.split(",") if field.strip()]
    normalized = []
    for row in rows:
        if isinstance(row, list):
            normalized.append({fields[index]: value for index, value in enumerate(row[: len(fields)])})
        elif isinstance(row, dict):
            normalized.append(row)
    return normalized


def _record_live_query_audit(result: dict[str, Any], *, requested_by: str) -> None:
    try:
        from src.a2a_ecommerce_demo.mcp_governance_tools import record_mcp_tool_audit

        record_mcp_tool_audit(
            "query_erp_live_snapshot",
            "read",
            status=str(result.get("status", "unknown")),
            args_json=json.dumps(
                {
                    "connector_id": result.get("connector_id", ""),
                    "dataset": result.get("dataset", ""),
                    "query": result.get("query", {}),
                    "row_count": result.get("row_count", 0),
                    "error_type": result.get("error_type", ""),
                },
                ensure_ascii=False,
            ),
            result_summary=f"ERP live read-only query {result.get('status', 'unknown')}: {result.get('connector_id', '')}/{result.get('dataset', '')}",
            actor=requested_by,
        )
    except Exception:
        return


def _record_jackyun_sales_summary_audit(result: dict[str, Any], *, requested_by: str) -> None:
    try:
        from src.a2a_ecommerce_demo.mcp_governance_tools import record_mcp_tool_audit

        record_mcp_tool_audit(
            "query_jackyun_channel_sales_summary",
            "read",
            status=str(result.get("status", "unknown")),
            args_json=json.dumps(
                {
                    "connector_id": "jackyun_erp",
                    "dataset": "channel_sales_summary",
                    "dimension": result.get("dimension", ""),
                    "query": result.get("query", {}),
                    "row_count": result.get("row_count", 0),
                    "error_type": result.get("error_type", ""),
                },
                ensure_ascii=False,
            ),
            result_summary=f"Jackyun channel sales summary {result.get('status', 'unknown')}: {result.get('row_count', 0)} rows",
            actor=requested_by,
        )
    except Exception:
        return


def _filter_int(filters: dict[str, Any], key: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(filters.get(key, default) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _filter_bool(filters: dict[str, Any], key: str, default: bool = False) -> bool:
    if key not in filters:
        return default
    value = filters.get(key)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def _jackyun_channel_sales_query_kwargs(
    filters: dict[str, Any],
    *,
    dimension: str,
    limit: int,
) -> dict[str, object]:
    query_kwargs: dict[str, object] = {}
    normalized_filters = dict(filters)
    if normalized_filters.get("date_from") and not normalized_filters.get("start_time"):
        normalized_filters["start_time"] = normalized_filters["date_from"]
    if normalized_filters.get("date_to") and not normalized_filters.get("end_time"):
        normalized_filters["end_time"] = normalized_filters["date_to"]
    for key in JACKYUN_CHANNEL_SALES_ALLOWED_FILTERS:
        value = normalized_filters.get(key)
        if value not in (None, "", []):
            query_kwargs[key] = value
    query_kwargs["dimension"] = _safe_text(dimension or "channel_goods_daily", max_length=80)
    query_kwargs["page_size"] = _filter_int(normalized_filters, "page_size", limit, minimum=1, maximum=MAX_LIVE_QUERY_LIMIT)
    query_kwargs["max_pages"] = _filter_int(normalized_filters, "max_pages", 1, minimum=1, maximum=20)
    query_kwargs["use_udr_fallback"] = _filter_bool(normalized_filters, "use_udr_fallback", True)
    if "prefer_udr" in normalized_filters:
        query_kwargs["prefer_udr"] = _filter_bool(normalized_filters, "prefer_udr", False)
    if normalized_filters.get("udr_report_id"):
        query_kwargs["udr_report_id"] = normalized_filters["udr_report_id"]
    if normalized_filters.get("udr_filters"):
        query_kwargs["udr_filters"] = normalized_filters["udr_filters"]
    return query_kwargs


def _row_text_for_keys(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    values = []
    for key in keys:
        found = _find_normalized_field_value(row, _normalize_field_name(key))
        if found is not None:
            values.append(_safe_text(found[1], max_length=500))
    return " ".join(value for value in values if value)


def _jackyun_sales_row_matches_filters(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    goods_no = _safe_text(filters.get("goods_no"))
    if goods_no and goods_no.lower() not in _row_text_for_keys(row, ("goodsNo", "goodsCode", "skuCode")).lower():
        return False
    sku_barcode = _safe_text(filters.get("sku_barcode"))
    if sku_barcode and sku_barcode.lower() not in _row_text_for_keys(row, ("skuBarcode", "barcode", "barCode")).lower():
        return False
    keyword_terms = _unique_texts(
        [
            filters.get("goods_name"),
            filters.get("sku_keyword"),
            filters.get("brand"),
            filters.get("brand_name"),
        ]
    )
    if keyword_terms:
        goods_text = _row_text_for_keys(row, ("goodsName", "skuName", "goodsNo", "skuBarcode")).lower()
        if not any(term.lower() in goods_text for term in keyword_terms):
            return False
    return True


def _post_filter_jackyun_sales_rows(
    rows: list[dict[str, Any]],
    filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    active = any(_safe_text(filters.get(key)) for key in JACKYUN_CHANNEL_SALES_POST_FILTER_KEYS)
    if not active:
        return rows, []
    filtered = [row for row in rows if _jackyun_sales_row_matches_filters(row, filters)]
    return filtered, [
        "goods_no/sku_barcode/goods_name/brand 过滤是在吉客云销售汇总返回行上做的后置筛选；"
        "如果返回页数受限，需用更精确的渠道/日期或开放平台报表权限补全。"
    ]


def query_jackyun_channel_sales_summary(
    filters_json: str = "",
    dimension: str = "channel_goods_daily",
    limit: int = 100,
    requested_by: str = "agent",
) -> str:
    """封装吉客云 Skill 的销售汇总工作流，只读查询日期/渠道/货品销量与金额。"""
    _load_env()
    try:
        connector = get_connector_spec("jackyun_erp")
        filters = _parse_filters(filters_json)
        capped_limit = _safe_limit(limit)
        query_kwargs = _jackyun_channel_sales_query_kwargs(filters, dimension=dimension, limit=capped_limit)
        raw_result = _call_jackyun_channel_sales_summary(str(connector.get("skill_dir", "")), query_kwargs)
        raw_rows = [row for row in raw_result.get("summary_rows", []) if isinstance(row, dict)]
        rows, post_filter_warnings = _post_filter_jackyun_sales_rows(raw_rows, filters)
        rows = rows[:capped_limit]
        warnings = [_redact_erp_error_text(warning) for warning in raw_result.get("warnings", []) if warning]
        warnings.extend(post_filter_warnings)
        source_row_count = int(raw_result.get("row_count", len(raw_rows)) or 0)
        total_qty = _to_number(raw_result.get("total_goods_qty"))
        total_amount = _to_number(raw_result.get("total_goods_amount"))
        result = {
            "status": "success",
            "mode": "live_read_only_sales_summary",
            "connector_id": "jackyun_erp",
            "display_name": connector.get("display_name", ""),
            "dataset": "channel_sales_summary",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "dimension": raw_result.get("dimension") or query_kwargs.get("dimension"),
            "summaryType": raw_result.get("summaryType", ""),
            "grain": ["日期", "渠道/店铺", "SKU", "销量/金额"],
            "query": {
                "method": raw_result.get("source_method") or raw_result.get("method", ""),
                "primary_method": raw_result.get("primary_method", ""),
                "filters": sorted(filters),
                "request": raw_result.get("request", {}),
                "page_size": query_kwargs.get("page_size"),
                "max_pages": query_kwargs.get("max_pages"),
            },
            "row_count": len(rows),
            "source_row_count": source_row_count,
            "returned_row_count": len(rows),
            "totals": {
                "goods_qty": _display_quantity(total_qty) if total_qty is not None else None,
                "goods_amount": _display_quantity(total_amount) if total_amount is not None else None,
            },
            "resolved_shops": raw_result.get("resolved_shops", []),
            "warnings": warnings,
            "row_schema": [
                "time",
                "shopName",
                "goodsNo",
                "goodsName",
                "goodsQty",
                "goodsAmtCompanyCurrency",
                "sellAmtCompanyCurrency",
                "deliveryGoodsQty",
                "returnGoodsQty",
                "refundGoodsAmtCompanyCurrency",
            ],
            "semantic_boundary": (
                "这是吉客云销售汇总/货品销售分析只读结果，可作为 SKU+日期+渠道 销量/金额口径；"
                "不写入 ERP，也不替代库存核算成本。"
            ),
            "rows": rows,
        }
        _record_jackyun_sales_summary_audit(result, requested_by=requested_by)
        return _json(result)
    except Exception as exc:
        result = {
            "status": "error",
            "mode": "live_read_only_sales_summary",
            "connector_id": "jackyun_erp",
            "dataset": "channel_sales_summary",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "dimension": dimension,
            "error_type": type(exc).__name__,
            "error": _redact_erp_error_text(exc),
        }
        _record_jackyun_sales_summary_audit(result, requested_by=requested_by)
        return _json(result)


def query_erp_live_snapshot(
    connector_id: str,
    dataset: str,
    filters_json: str = "",
    limit: int = 20,
    requested_by: str = "agent",
) -> str:
    """按需查询吉客云/金蝶实时只读数据。

    路由原则：默认经营分析仍优先走本地 DuckDB mart；只有用户明确要求“实时 ERP”
    或本地 fact layer 缺数据时，Agent 才应调用本工具。本工具不写 ERP，也不写本地快照。
    """
    _load_env()
    requested_connector_id = connector_id
    connector_id = normalize_connector_id(connector_id)
    try:
        connector = get_connector_spec(connector_id)
        get_connector_dataset(connector_id, dataset)
        filters = _parse_filters(filters_json)
        capped_limit = _safe_limit(limit)
        skill_dir = str(connector.get("skill_dir", ""))
        if connector_id == "jackyun_erp":
            if dataset not in JACKYUN_LIVE_DATASETS:
                raise ValueError(f"Unsupported live dataset for jackyun_erp: {dataset}")
            resource, query_spec = _select_jackyun_query(dataset, filters)
            rows, payload = _query_jackyun_rows(query_spec, filters, capped_limit, skill_dir)
            if dataset in {"inventory_stock", "batch_inventory"}:
                rows = _enrich_jackyun_inventory_rows(rows)
            brand_expansion = None
            if _should_expand_jackyun_brand_inventory(dataset, filters, rows):
                expanded = _expand_jackyun_brand_inventory(dataset, filters, query_spec, skill_dir)
                rows = expanded.pop("rows")
                brand_expansion = expanded
            result = {
                "status": "success",
                "mode": "live_read_only_fallback",
                "connector_id": connector_id,
                "requested_connector_id": requested_connector_id,
                "display_name": connector.get("display_name", ""),
                "dataset": dataset,
                "resource": resource,
                "read_only": True,
                "external_write_enabled": False,
                "permission_scope": "read_only",
                "query": {
                    "method": query_spec["method"],
                    "page_index": payload.get("pageIndex"),
                    "page_size": payload.get("pageSize"),
                    "filters": sorted(key for key in filters if key != "resource"),
                },
                "warehouse_scope_rules": _warehouse_scope_rules_payload()
                if dataset in {"inventory_stock", "batch_inventory"}
                else [],
                "warehouse_scope_rules_path": str(_jackyun_warehouse_scope_rules_path())
                if dataset in {"inventory_stock", "batch_inventory"}
                else "",
                "coverage": query_spec.get("coverage", {}),
                "row_count": len(rows),
                "rows": rows[:capped_limit],
            }
            if brand_expansion is not None:
                result["brand_expansion"] = brand_expansion
            _record_live_query_audit(result, requested_by=requested_by)
            return _json(result)
        if connector_id == "kingdee_erp":
            if dataset not in KINGDEE_LIVE_DATASETS:
                raise ValueError(f"Unsupported live dataset for kingdee_erp: {dataset}")
            query_spec = KINGDEE_LIVE_DATASETS[dataset]
            filter_string = _build_kingdee_filter(query_spec, filters)
            raw_rows = _execute_kingdee_bill_query(
                form_id=str(query_spec["form_id"]),
                field_keys=str(query_spec["field_keys"]),
                filter_string=filter_string,
                limit=capped_limit,
                start_row=0,
                skill_dir=skill_dir,
            )
            rows = _normalize_kingdee_rows(str(query_spec["field_keys"]), raw_rows)
            result = {
                "status": "success",
                "mode": "live_read_only_fallback",
                "connector_id": connector_id,
                "requested_connector_id": requested_connector_id,
                "display_name": connector.get("display_name", ""),
                "dataset": dataset,
                "read_only": True,
                "external_write_enabled": False,
                "permission_scope": "read_only",
                "query": {
                    "method": "ExecuteBillQuery",
                    "form_id": query_spec["form_id"],
                    "field_keys": query_spec["field_keys"],
                    "filters": sorted(filters),
                    "limit": capped_limit,
                },
                "coverage": query_spec.get("coverage", {}),
                "row_count": len(rows),
                "rows": rows[:capped_limit],
            }
            _record_live_query_audit(result, requested_by=requested_by)
            return _json(result)
        raise ValueError(f"Unsupported connector_id for live query: {connector_id}")
    except Exception as exc:
        result = {
            "status": "error",
            "mode": "live_read_only_fallback",
            "connector_id": connector_id,
            "requested_connector_id": requested_connector_id,
            "dataset": dataset,
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "error_type": type(exc).__name__,
            "error": _redact_erp_error_text(exc),
        }
        _record_live_query_audit(result, requested_by=requested_by)
        return _json(result)


def route_erp_live_query(user_query: str, filters_json: str = "", requested_by: str = "agent") -> str:
    """确定性规划 ERP/WeCom/DuckDB 只读查询路线，不直接读取外部系统。"""
    del requested_by
    filters = _parse_filters(filters_json)
    text = _safe_text(user_query, max_length=2000)
    inventory_intent = _contains_keyword(text, ERP_ROUTE_INVENTORY_KEYWORDS)
    cost_intent = _contains_keyword(text, ERP_ROUTE_COST_KEYWORDS)
    wecom_intent = _contains_keyword(text, ERP_ROUTE_WECOM_KEYWORDS)
    live_intent = _contains_keyword(text, ERP_ROUTE_LIVE_KEYWORDS)
    sales_or_turnover_intent = _contains_keyword(text, ("日销", "销量", "销售", "周转", "覆盖天数", "出库"))
    wecom_doc_urls = _extract_wecom_smartsheet_urls(text)
    brand_hint = _extract_brand_hint(text, filters)
    if brand_hint and not filters.get("brand"):
        filters["brand"] = brand_hint
    if "所有仓库" in text or "全仓" in text or "全部仓库" in text:
        filters.setdefault("warehouse_scope", "all")

    recommended_tools: list[str] = ["route_erp_live_query"]
    data_sources: list[str] = []
    plan: list[dict[str, Any]] = []

    if inventory_intent and cost_intent:
        primary_tool = "query_inventory_cost_reference"
        recommended_tools.append(primary_tool)
        data_sources.extend(["jackyun_erp", "kingdee_erp"])
        plan.append(
            {
                "step": "inventory_cost_reference",
                "tool": "query_inventory_cost_reference",
                "reason": "库存金额、成本价、采购价或毛利问题需要先读吉客云库存，再在成本缺失时补采购价参考。",
                "filters": sorted(filters),
            }
        )
    elif sales_or_turnover_intent and live_intent:
        primary_tool = "query_jackyun_channel_sales_summary"
        recommended_tools.append(primary_tool)
        data_sources.append("jackyun_erp")
        plan.append(
            {
                "step": "jackyun_channel_sales_summary",
                "tool": "query_jackyun_channel_sales_summary",
                "connector_id": "jackyun_erp",
                "dataset": "channel_sales_summary",
                "dimension": "channel_goods_daily",
                "reason": "用户要求吉客云/实时 SKU 销量、日销、销售金额或渠道货品销量时，优先走吉客云 Skill 销售汇总只读封装。",
                "filters": sorted(filters),
            }
        )
    elif inventory_intent and live_intent:
        primary_tool = "query_erp_live_snapshot"
        recommended_tools.append(primary_tool)
        data_sources.append("jackyun_erp")
        plan.append(
            {
                "step": "live_inventory",
                "tool": "query_erp_live_snapshot",
                "connector_id": "jackyun_erp",
                "dataset": "inventory_stock",
                "reason": "当前库存、分仓库存和 SKU/仓库事实优先来自吉客云实时只读库存。",
                "filters": sorted(filters),
            }
        )
    elif cost_intent:
        primary_tool = "query_erp_live_snapshot"
        recommended_tools.extend(["verify_erp_supplier_terms_mapping", primary_tool])
        data_sources.extend(["kingdee_erp", "jackyun_erp"])
        plan.append(
            {
                "step": "purchase_price_reference",
                "tool": "query_erp_live_snapshot",
                "connector_id": "kingdee_erp",
                "dataset": "supplier_procurement_terms",
                "reason": "采购价/采购单价优先用金蝶采购订单分录字段做只读参考。",
                "filters": sorted(filters),
            }
        )
    else:
        primary_tool = "query_fact_layer_from_question"
        recommended_tools.append(primary_tool)
        data_sources.append("DuckDB")
        plan.append(
            {
                "step": "local_fact_first",
                "tool": "query_fact_layer_from_question",
                "reason": "没有明确实时 ERP 需求时，默认先查本地 DuckDB fact layer。",
            }
        )

    if wecom_intent:
        recommended_tools.append("query_wecom_smartsheet_records")
        data_sources.append("WeCom_smartsheet")
        daily_sales_step = {
            "step": "daily_sales",
            "tool": "query_wecom_smartsheet_records",
            "dataset": "channel_daily_sales",
            "reason": "企业微信智能表/日销表通过 WeDoc MCP 只读查询；如果用户提供了智能表 URL，则运行时直接用该 URL，不依赖固定 source 配置。",
        }
        if wecom_doc_urls:
            daily_sales_step["doc_url"] = wecom_doc_urls[0]
        else:
            daily_sales_step["source_id"] = "channel_daily_sales"
        plan.append(
            daily_sales_step
        )
    elif sales_or_turnover_intent:
        recommended_tools.append("query_fact_layer_from_question")
        data_sources.append("DuckDB")
        plan.append(
            {
                "step": "sales_or_turnover",
                "tool": "query_fact_layer_from_question",
                "reason": "销量、出库、周转和覆盖天数优先读取已入库事实层；缺口再走实时只读兜底。",
            }
        )
    if sales_or_turnover_intent and live_intent and "query_jackyun_channel_sales_summary" not in recommended_tools:
        recommended_tools.append("query_jackyun_channel_sales_summary")
        data_sources.append("jackyun_erp")
        plan.append(
            {
                "step": "jackyun_channel_sales_summary",
                "tool": "query_jackyun_channel_sales_summary",
                "connector_id": "jackyun_erp",
                "dataset": "channel_sales_summary",
                "dimension": "channel_goods_daily",
                "reason": "实时 SKU 日销/渠道销售可用吉客云销售汇总只读封装补证。",
                "filters": sorted(filters),
            }
        )

    return _json(
        {
            "status": "success",
            "mode": "deterministic_live_erp_route",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "primary_tool": primary_tool,
            "recommended_tools": list(dict.fromkeys(recommended_tools)),
            "data_sources": list(dict.fromkeys(data_sources)),
            "suggested_filters": filters,
            "intent": {
                "inventory": inventory_intent,
                "cost_or_purchase_price": cost_intent,
                "wecom_daily_sales": wecom_intent,
                "live_erp": live_intent,
                "sales_or_turnover": sales_or_turnover_intent,
            },
            "routing_policy": [
                "当前库存、分仓、批次和货品事实优先吉客云。",
                "采购价、供应商采购条款和财务采购参考价优先金蝶。",
                "用户明确要求吉客云实时 SKU 日销/渠道销量时，优先 query_jackyun_channel_sales_summary；企业微信日销表仍走 WeDoc MCP。",
                "历史聚合优先 DuckDB。",
                "FTaxPrice 只能作为采购订单含税单价参考，不等同于最终库存核算成本。",
            ],
            "plan": plan,
        }
    )


def query_inventory_cost_reference(
    filters_json: str = "",
    limit: int = 20,
    requested_by: str = "agent",
) -> str:
    """组合查询吉客云库存与金蝶/吉客云采购价参考，保持只读。"""
    filters = _parse_filters(filters_json)
    capped_limit = _safe_limit(limit)
    route = json.loads(route_erp_live_query("库存 成本价 采购价", filters_json=filters_json, requested_by=requested_by))
    source_checks: list[dict[str, Any]] = []
    price_references: list[dict[str, Any]] = []

    inventory_result = json.loads(
        query_erp_live_snapshot(
            "jackyun_erp",
            "inventory_stock",
            filters_json=json.dumps(filters, ensure_ascii=False),
            limit=capped_limit,
            requested_by=requested_by,
        )
    )
    inventory_rows = [row for row in inventory_result.get("rows", []) if isinstance(row, dict)]
    source_checks.append(
        {
            "connector_id": "jackyun_erp",
            "dataset": "inventory_stock",
            "status": inventory_result.get("status", "unknown"),
            "row_count": int(inventory_result.get("row_count", 0) or 0),
            "selected": False,
            "checked_fields": list(JACKYUN_INVENTORY_COST_FIELD_KEYS),
        }
    )
    inventory_cost_coverage = _cost_field_coverage(
        inventory_rows,
        JACKYUN_INVENTORY_COST_FIELD_KEYS,
        row_count=int(inventory_result.get("row_count", 0) or 0),
    )
    if inventory_result.get("status") == "success":
        inventory_reference = _selected_cost_reference(
            connector_id="jackyun_erp",
            dataset="inventory_stock",
            rows=inventory_rows,
            field_keys=JACKYUN_INVENTORY_COST_FIELD_KEYS,
            row_count=int(inventory_result.get("row_count", 0) or 0),
        )
        source_checks[-1]["matched_reference"] = inventory_reference is not None
        if inventory_reference is not None:
            price_references.append(inventory_reference)

    reference_filters = _cost_reference_filters(filters, inventory_rows)
    should_query_reference_sources = (
        inventory_result.get("status") != "success"
        or not inventory_cost_coverage["complete_for_returned_rows"]
        or not price_references
    )
    if should_query_reference_sources:
        batch_result = json.loads(
            query_erp_live_snapshot(
                "jackyun_erp",
                "batch_inventory",
                filters_json=json.dumps({**filters, **reference_filters}, ensure_ascii=False),
                limit=capped_limit,
                requested_by=requested_by,
            )
        )
        batch_rows = [row for row in batch_result.get("rows", []) if isinstance(row, dict)]
        source_checks.append(
            {
                "connector_id": "jackyun_erp",
                "dataset": "batch_inventory",
                "status": batch_result.get("status", "unknown"),
                "row_count": int(batch_result.get("row_count", 0) or 0),
                "selected": False,
                "checked_fields": list(JACKYUN_BATCH_COST_FIELD_KEYS),
            }
        )
        batch_reference = _selected_cost_reference(
            connector_id="jackyun_erp",
            dataset="batch_inventory",
            rows=batch_rows,
            field_keys=JACKYUN_BATCH_COST_FIELD_KEYS,
            row_count=int(batch_result.get("row_count", 0) or 0),
        )
        source_checks[-1]["matched_reference"] = batch_reference is not None
        if batch_reference is not None:
            price_references.append(batch_reference)

        purchase_result = json.loads(
            query_erp_live_snapshot(
                "jackyun_erp",
                "purchase_orders",
                filters_json=json.dumps(reference_filters, ensure_ascii=False),
                limit=capped_limit,
                requested_by=requested_by,
            )
        )
        purchase_rows = [row for row in purchase_result.get("rows", []) if isinstance(row, dict)]
        source_checks.append(
            {
                "connector_id": "jackyun_erp",
                "dataset": "purchase_orders",
                "status": purchase_result.get("status", "unknown"),
                "row_count": int(purchase_result.get("row_count", 0) or 0),
                "selected": False,
                "checked_fields": list(JACKYUN_PURCHASE_PRICE_FIELD_KEYS),
            }
        )
        purchase_reference = _selected_cost_reference(
            connector_id="jackyun_erp",
            dataset="purchase_orders",
            rows=purchase_rows,
            field_keys=JACKYUN_PURCHASE_PRICE_FIELD_KEYS,
            row_count=int(purchase_result.get("row_count", 0) or 0),
        )
        source_checks[-1]["matched_reference"] = purchase_reference is not None
        if purchase_reference is not None:
            price_references.append(purchase_reference)

        kingdee_result = json.loads(
            query_erp_live_snapshot(
                "kingdee_erp",
                "supplier_procurement_terms",
                filters_json=json.dumps(reference_filters, ensure_ascii=False),
                limit=capped_limit,
                requested_by=requested_by,
            )
        )
        kingdee_rows = [row for row in kingdee_result.get("rows", []) if isinstance(row, dict)]
        source_checks.append(
            {
                "connector_id": "kingdee_erp",
                "dataset": "supplier_procurement_terms",
                "status": kingdee_result.get("status", "unknown"),
                "row_count": int(kingdee_result.get("row_count", 0) or 0),
                "selected": False,
                "checked_fields": list(KINGDEE_PURCHASE_PRICE_FIELD_KEYS),
            }
        )
        kingdee_reference = _selected_cost_reference(
            connector_id="kingdee_erp",
            dataset="supplier_procurement_terms",
            rows=kingdee_rows,
            field_keys=KINGDEE_PURCHASE_PRICE_FIELD_KEYS,
            row_count=int(kingdee_result.get("row_count", 0) or 0),
        )
        source_checks[-1]["matched_reference"] = kingdee_reference is not None
        if kingdee_reference is not None:
            price_references.append(kingdee_reference)

    selected_reference = _choose_cost_reference(
        price_references,
        prefer_procurement_reference=not inventory_cost_coverage["complete_for_returned_rows"],
    )
    selected_source = selected_reference.get("selected_source") if selected_reference else ""
    for check in source_checks:
        check_source = f"{check.get('connector_id')}/{check.get('dataset')}"
        check["selected"] = check_source == selected_source

    cost_reference = dict(selected_reference) if selected_reference else {
        "selected_source": "",
        "selected_field": "",
        "selected_value": None,
        "confidence": "missing",
        "semantic_boundary": "当前只读白名单未返回可用采购价/成本价字段；只能做数量口径库存分析。",
        "row_count": 0,
        "row_preview": {},
    }
    if selected_reference and reference_filters:
        cost_reference["scope_note"] = (
            f"该采购价参考基于 derived_reference_filters={reference_filters} 命中的首个参考值，"
            "只能用于对应物料/SKU参考，不能代表整个品牌、所有渠道或所有仓库的最终库存核算成本。"
        )
    elif selected_reference:
        cost_reference["scope_note"] = (
            "该采购价参考来自当前返回行中的首个可用价格字段，只能作为对应返回行参考，不能代表整个品牌。"
        )
    else:
        cost_reference["scope_note"] = "未命中可用采购价/成本价参考。"
    inventory_row_count = int(inventory_result.get("row_count", 0) or 0)
    brand_expansion = inventory_result.get("brand_expansion")
    inventory_analysis_notes: list[str] = []
    if isinstance(brand_expansion, dict) and brand_expansion:
        inventory_analysis_notes.append(
            "存在全量品牌展开汇总：做全仓/全品牌结论时优先使用 brand_expansion.summary，rows 只是按 limit 截断的样例。"
        )
    if inventory_row_count > len(inventory_rows):
        inventory_analysis_notes.append(
            f"库存明细 rows 仅返回 {len(inventory_rows)} 行样例，row_count={inventory_row_count} 表示底层只读查询命中的总行数。"
        )
    return _json(
        {
            "status": "success" if inventory_result.get("status") == "success" else "partial",
            "mode": "inventory_cost_reference_readonly",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "limit": capped_limit,
            "filters": filters,
            "derived_reference_filters": reference_filters,
            "route": route,
            "inventory": {
                "connector_id": "jackyun_erp",
                "dataset": "inventory_stock",
                "status": inventory_result.get("status", "unknown"),
                "row_count": inventory_row_count,
                "returned_row_count": len(inventory_rows),
                "rows": inventory_rows[:capped_limit],
                "brand_expansion": brand_expansion if isinstance(brand_expansion, dict) else {},
                "analysis_notes": inventory_analysis_notes,
            },
            "inventory_cost_coverage": inventory_cost_coverage,
            "cost_reference": cost_reference,
            "price_references": price_references,
            "source_checks": source_checks,
            "next_actions": [
                "若吉客云库存 costPrice 覆盖不全，但金蝶 FTaxPrice 命中，可把 selected_value 标注为采购订单含税单价参考，不能写成最终库存核算成本。",
                "若 source_checks 全部未命中价格字段，报告中只输出数量口径周转/覆盖天数，并把成本价列为数据缺口。",
            ],
        }
    )


def test_erp_live_connection(connector_id: str = "") -> str:
    """对吉客云/金蝶做最小实时只读连通性验证，不返回密钥、Cookie 或账套标识。"""
    targets = [normalize_connector_id(connector_id)] if connector_id else ["jackyun_erp", "kingdee_erp"]
    checks = []
    for target in targets:
        if target == "jackyun_erp":
            payload = query_erp_live_snapshot(
                "jackyun_erp",
                "master_data",
                filters_json=json.dumps({"resource": "warehouses"}, ensure_ascii=False),
                limit=1,
            )
        elif target == "kingdee_erp":
            payload = query_erp_live_snapshot("kingdee_erp", "suppliers", limit=1)
        else:
            checks.append({"connector_id": target, "ok": False, "error": "unsupported_connector"})
            continue
        result = json.loads(payload)
        checks.append(
            {
                "connector_id": target,
                "ok": result.get("status") == "success",
                "status": result.get("status"),
                "row_count": result.get("row_count", 0),
                "query": result.get("query", {}),
                "error": result.get("error", ""),
            }
        )
    return _json(
        {
            "mode": "live_read_only_fallback",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "connector_count": len(checks),
            "ready_count": sum(1 for item in checks if item.get("ok")),
            "checks": checks,
        }
    )


def verify_erp_supplier_terms_mapping(limit: int = 3, requested_by: str = "agent") -> str:
    """只读验证供应商交期、采购价和历史延误字段能否从吉客云/金蝶返回字段中映射。

    本工具只调用 `query_erp_live_snapshot` 的只读查询，不返回行值，只返回字段名、
    行数和字段匹配结论，避免泄露供应商、价格明细或账号信息。
    """
    capped_limit = _safe_limit(limit)
    checks: list[dict[str, Any]] = []
    for connector_id, dataset in SUPPLIER_TERMS_VERIFICATION_TARGETS:
        payload = query_erp_live_snapshot(connector_id, dataset, limit=capped_limit, requested_by=requested_by)
        result = json.loads(payload)
        rows = result.get("rows", [])
        fields = _row_field_names(rows)
        checks.append(
            {
                "connector_id": connector_id,
                "dataset": dataset,
                "status": result.get("status", "unknown"),
                "read_only": bool(result.get("read_only", True)),
                "query": result.get("query", {}),
                "row_count": int(result.get("row_count", 0) or 0),
                "field_count": len(fields),
                "fields": fields,
                "error_type": result.get("error_type", ""),
                "error": result.get("error", ""),
            }
        )
    purchase_price = _supplier_term_finding(
        checks,
        "purchase_price",
        missing_status="not_found",
        note="采购价通常来自采购订单分录、采购入库或结算单；若未命中，需要补字段映射。",
    )
    lead_time = _supplier_term_finding(
        checks,
        "lead_time",
        missing_status="not_found",
        note="交期优先看吉客云 arrivePeriod、计划到货/入库日期，或金蝶采购订单交货日期。",
    )
    delay_fields = _supplier_term_finding(
        checks,
        "historical_delay",
        missing_status="derived_required",
        note="历史延误通常不是原生单字段，应由采购计划/交货日期、实际入库日期和未入库数量二次推导。",
    )
    successful_checks = [check for check in checks if check["status"] == "success"]
    return _json(
        {
            "status": "verified" if len(successful_checks) == len(checks) else "partial",
            "mode": "supplier_terms_mapping_verification",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "limit": capped_limit,
            "summary": "只读检查吉客云/金蝶返回字段，判断供应商交期、采购价和历史延误能否映射。",
            "findings": {
                "purchase_price": purchase_price,
                "lead_time": lead_time,
                "historical_delay": delay_fields,
            },
            "checks": checks,
            "next_actions": [
                "历史延误建议用采购订单交货日期与入库完成日期做二次计算，不建议依赖单个文本字段。",
            ],
        }
    )
