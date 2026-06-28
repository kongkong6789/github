"""
Business report wrappers.

Currently covers the official goods sales multidimensional analysis report:
birc.report.needauth.goodsMultiDimensionalAnalysis.
"""
from __future__ import annotations

import json
from calendar import monthrange
from pathlib import Path
from typing import Any

import pandas as pd

import config
from jackyun_api import JackyunAPIError, JackyunValidationError, get_client
from helpers.cli_docs import load_method_detail
from helpers.constants import METHOD_GOODS_SALES_ANALYSIS, METHOD_USER_DEFINED_REPORT


GOODS_SALES_ANALYSIS_FALLBACK_COLUMNS = [
    "shopCateName",
    "costAmtCompanyCurrency",
    "companyName",
    "sellerName",
    "shopName",
    "grossProfitCompanyCurrency",
    "finReceiptTime",
    "cateName",
    "warehouseName",
    "goodsQty",
    "skuName",
    "expenseShareAmtCompanyCurrency",
    "cityName",
    "taxAmtCompanyCurrency",
    "noTaxGoodsAmtCompanyCurrency",
    "customerTotal",
    "goodsName",
    "barcode",
    "departName",
    "deductRefundgoodsAmtCompanyCurrency",
    "goodsNo",
    "sellAmtCompanyCurrency",
    "noTaxGrossProfitCompanyCurrency",
    "brandName",
    "unitName",
    "cancelGoodsAmtCompanyCurrency",
    "returnGoodsQty",
    "noTaxGrossProfitRateCompanyCurrencyShow",
    "estimateWeight",
    "logisticName",
    "goodsAmtCompanyCurrency",
    "skuNo",
    "refundGoodsAmtCompanyCurrency",
    "returnGoodsRate",
    "countryName",
    "provinceName",
    "time",
    "grossProfitRateCompanyCurrencyShow",
    "deliveryGoodsQty",
]


GOODS_SALES_ANALYSIS_LABELS = {
    "shopCateName": "渠道分类",
    "costAmtCompanyCurrency": "成本(本币)",
    "companyName": "公司",
    "sellerName": "业务员",
    "shopName": "销售渠道",
    "grossProfitCompanyCurrency": "毛利(本币)",
    "finReceiptTime": "收款时间",
    "cateName": "分类",
    "warehouseName": "发货仓库",
    "goodsQty": "销售量",
    "skuName": "规格",
    "expenseShareAmtCompanyCurrency": "费用分摊(本币)",
    "cityName": "城市",
    "taxAmtCompanyCurrency": "税额(本币)",
    "noTaxGoodsAmtCompanyCurrency": "未税金额(本币)",
    "customerTotal": "分销终端金额",
    "goodsName": "货品名称",
    "barcode": "条码",
    "departName": "部门",
    "deductRefundgoodsAmtCompanyCurrency": "销售额_扣退(本币)",
    "goodsNo": "货品编号",
    "sellAmtCompanyCurrency": "货品金额(本币)",
    "noTaxGrossProfitCompanyCurrency": "未税毛利(本币)",
    "brandName": "品牌",
    "unitName": "单位",
    "cancelGoodsAmtCompanyCurrency": "取消金额(本币)",
    "returnGoodsQty": "退货量",
    "noTaxGrossProfitRateCompanyCurrencyShow": "未税毛利率%(本币)",
    "estimateWeight": "预估销售重量(g)",
    "logisticName": "物流公司",
    "goodsAmtCompanyCurrency": "销售额(本币)",
    "skuNo": "规格编码",
    "refundGoodsAmtCompanyCurrency": "退款金额(本币)",
    "returnGoodsRate": "退货率",
    "countryName": "国家及地区",
    "provinceName": "省份",
    "time": "时间",
    "grossProfitRateCompanyCurrencyShow": "毛利率%(本币)",
    "deliveryGoodsQty": "发货量",
}


GOODS_SALES_ANALYSIS_FILTER_ALIASES = {
    "fin_receipt_status": "finReceiptStatus",
    "finReceiptStatus": "finReceiptStatus",
    "fin_receipt_time_begin": "startFinReceiptTime",
    "finReceiptTimeBegin": "startFinReceiptTime",
    "start_fin_receipt_time": "startFinReceiptTime",
    "startFinReceiptTime": "startFinReceiptTime",
    "fin_receipt_time_end": "endFinReceiptTime",
    "finReceiptTimeEnd": "endFinReceiptTime",
    "end_fin_receipt_time": "endFinReceiptTime",
    "endFinReceiptTime": "endFinReceiptTime",
    "query_time_begin": "startTime",
    "queryTimeBegin": "startTime",
    "query_time_end": "endTime",
    "queryTimeEnd": "endTime",
    "start_time": "startTime",
    "startTime": "startTime",
    "end_time": "endTime",
    "endTime": "endTime",
    "time_type": "timeType",
    "timeType": "timeType",
    "sku_ids": "skuIds",
    "skuIds": "skuIds",
    "trade_from": "tradeFrom",
    "tradeFrom": "tradeFrom",
    "logistic_ids": "logisticIds",
    "logisticIds": "logisticIds",
    "filter_time_type": "filterTimeType",
    "filterTimeType": "filterTimeType",
    "summary_types": "summaryType",
    "summaryTypes": "summaryType",
    "summary_type": "summaryType",
    "summaryType": "summaryType",
    "shop_ids": "shopIds",
    "shopIds": "shopIds",
    "trade_status": "tradeStatus",
    "tradeStatus": "tradeStatus",
    "depart_id": "departId",
    "departId": "departId",
    "seller_ids": "sellerIds",
    "sellerIds": "sellerIds",
    "warehouse_ids": "warehouseIds",
    "warehouseIds": "warehouseIds",
    "trade_type": "tradeType",
    "tradeType": "tradeType",
    "assembly_dimension": "assemblyDimension",
    "assemblyDimension": "assemblyDimension",
}

UDR_TIME_TYPE_BY_FILTER_TIME_TYPE = {
    1: "created_time",
    2: "consign_time",
    3: "pay_time",
}

UDR_STANDARD_FIELD_ALIASES = {
    "time": ["time", "日期", "时间", "统计日期", "发货日期", "付款日期", "下单日期"],
    "shopName": ["shopName", "channelName", "渠道", "渠道名称", "销售渠道", "店铺", "店铺名称"],
    "goodsNo": ["goodsNo", "货品编号", "商品编号", "商品编码", "货号"],
    "goodsName": ["goodsName", "货品名称", "商品名称", "品名"],
    "goodsQty": ["goodsQty", "销售数量", "销量", "数量", "成交数量", "发货数量", "发货量"],
    "goodsAmtCompanyCurrency": ["goodsAmtCompanyCurrency", "销售额", "销售金额", "成交金额", "金额", "实付金额"],
    "sellAmtCompanyCurrency": ["sellAmtCompanyCurrency", "货品金额", "商品金额"],
    "deliveryGoodsQty": ["deliveryGoodsQty", "发货量", "发货数量"],
    "returnGoodsQty": ["returnGoodsQty", "退货量", "退货数量"],
    "refundGoodsAmtCompanyCurrency": ["refundGoodsAmtCompanyCurrency", "退款金额", "退款额"],
}


def _join_values(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, (list, tuple, set)):
        return ",".join(str(item).strip() for item in values if str(item or "").strip())
    return str(values).strip()


def _to_number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _first_present(row: dict, aliases: list[str]) -> Any:
    for key in aliases:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return ""


def _month_range(month: str) -> tuple[str, str]:
    month_text = str(month or "").strip()
    parts = month_text.split("-")
    if len(parts) != 2:
        raise JackyunValidationError("month 必须是 YYYY-MM 格式，例如 2026-05")
    year = int(parts[0])
    month_no = int(parts[1])
    last_day = monthrange(year, month_no)[1]
    return f"{year:04d}-{month_no:02d}-01", f"{year:04d}-{month_no:02d}-{last_day:02d}"


def _month_value(month: str) -> str:
    month_text = str(month or "").strip()
    parts = month_text.split("-")
    if len(parts) != 2:
        raise JackyunValidationError("month 必须是 YYYY-MM 格式，例如 2026-05")
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}"


def goods_sales_analysis_columns() -> list[str]:
    detail = load_method_detail(METHOD_GOODS_SALES_ANALYSIS)
    props = (
        detail.get("response", {})
        .get("schema", {})
        .get("properties", {})
        .get("result", {})
        .get("properties", {})
        .get("data", {})
        .get("properties", {})
    )
    if isinstance(props, dict) and props:
        return list(props.keys())
    return list(GOODS_SALES_ANALYSIS_FALLBACK_COLUMNS)


def goods_sales_analysis_labels() -> dict[str, str]:
    labels = dict(GOODS_SALES_ANALYSIS_LABELS)
    detail = load_method_detail(METHOD_GOODS_SALES_ANALYSIS)
    props = (
        detail.get("response", {})
        .get("schema", {})
        .get("properties", {})
        .get("result", {})
        .get("properties", {})
        .get("data", {})
        .get("properties", {})
    )
    if isinstance(props, dict):
        for field, meta in props.items():
            description = str(meta.get("description") or "").split("。", 1)[0].strip()
            if description:
                labels[field] = description
    return labels


def resolve_shop_ids(shop_names: list[str] | str = None, shop_ids: list[str] | str = None) -> tuple[str, list[dict]]:
    ids = [item for item in _join_values(shop_ids).split(",") if item]
    resolved = []
    names = [item for item in _join_values(shop_names).split(",") if item]
    if names:
        from modules.channel import get_channel_by_name

        for name in names:
            channel = get_channel_by_name(name)
            if not channel:
                raise JackyunValidationError(f"未找到销售渠道: {name}")
            channel_id = channel.get("channelId")
            if not channel_id:
                raise JackyunValidationError(f"销售渠道「{name}」缺少 channelId，无法用于多维报表查询")
            ids.append(str(channel_id))
            resolved.append({
                "shopName": channel.get("channelName", name),
                "shopId": str(channel_id),
                "companyName": channel.get("companyName", ""),
            })
    return ",".join(dict.fromkeys(ids)), resolved


def resolve_shop_ids_by_channel_keyword(
    include_keyword: str = None,
    exclude_keywords: list[str] | str = None,
    active_only: bool = False,
) -> tuple[str, list[dict]]:
    if not include_keyword:
        return "", []
    from modules.channel import search_channels_by_keywords

    exclude_list = [item for item in _join_values(exclude_keywords).split(",") if item]
    channels = search_channels_by_keywords(
        include_keyword=include_keyword,
        exclude_keywords=exclude_list,
        active_only=active_only,
    )
    ids = []
    resolved = []
    for channel in channels:
        channel_id = channel.get("channelId")
        if not channel_id:
            continue
        ids.append(str(channel_id))
        resolved.append({
            "shopName": channel.get("channelName", ""),
            "shopId": str(channel_id),
            "shopCode": channel.get("channelCode", ""),
            "companyName": channel.get("companyName", ""),
            "departName": channel.get("channelDepartName", ""),
        })
    return ",".join(dict.fromkeys(ids)), resolved


def build_user_defined_report_filter_json(filters: dict | list[dict] | str) -> str:
    """
    Build the filterKeyValueJson value required by udr.openapi.userdefinedreport.

    The API expects a JSON string shaped like:
    [{"key":"timeType","value":"consign_time"},{"key":"date_key","value":"2026-05-12,2026-05-12"}]
    """
    if isinstance(filters, str):
        filters_text = filters.strip()
        if not filters_text:
            raise JackyunValidationError("filterKeyValueJson 不能为空")
        return filters_text
    if isinstance(filters, dict):
        items = [{"key": key, "value": value} for key, value in filters.items() if value not in (None, "", [])]
    elif isinstance(filters, list):
        items = []
        for item in filters:
            if not isinstance(item, dict):
                raise JackyunValidationError("自定义报表筛选项必须是 dict 或 [{'key':..., 'value':...}]")
            key = item.get("key")
            value = item.get("value")
            if key and value not in (None, "", []):
                items.append({"key": key, "value": _join_values(value)})
    else:
        raise JackyunValidationError("自定义报表筛选项必须是 dict、list 或 JSON 字符串")
    if not items:
        raise JackyunValidationError("自定义报表筛选项不能为空")
    return json.dumps(items, ensure_ascii=False)


def build_channel_sales_udr_filters(
    start_time: str = None,
    end_time: str = None,
    month: str = None,
    shop_ids: list[str] | str = None,
    filter_time_type: int = 2,
    trade_status: str | int = None,
    extra_filters: dict | list[dict] | str = None,
) -> str:
    if month and (not start_time or not end_time):
        start_time, end_time = _month_range(month)
    if not start_time or not end_time:
        raise JackyunValidationError("自定义报表销售汇总必须提供 start_time/end_time 或 month")

    filters = [
        {"key": "timeType", "value": UDR_TIME_TYPE_BY_FILTER_TIME_TYPE.get(int(filter_time_type or 2), "consign_time")},
        {"key": "date_key", "value": f"{start_time},{end_time}"},
    ]
    shop_ids_text = _join_values(shop_ids)
    if shop_ids_text:
        filters.append({"key": "shopId", "value": shop_ids_text})
    if trade_status not in (None, "", []):
        filters.append({"key": "tradeStatus", "value": _join_values(trade_status)})

    if extra_filters:
        if isinstance(extra_filters, str):
            try:
                extra_filters = json.loads(extra_filters)
            except json.JSONDecodeError:
                return build_user_defined_report_filter_json(extra_filters)
        if isinstance(extra_filters, dict):
            filters.extend({"key": key, "value": value} for key, value in extra_filters.items())
        elif isinstance(extra_filters, list):
            filters.extend(extra_filters)
        else:
            raise JackyunValidationError("udr_filters 必须是 dict、list 或 JSON 字符串")
    return build_user_defined_report_filter_json(filters)


def _parse_user_defined_report_rows(value: Any) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("rows", "list", "items", "records", "data"):
            nested = value.get(key)
            if isinstance(nested, (list, dict, str)):
                parsed = _parse_user_defined_report_rows(nested)
                if parsed:
                    return parsed
        return [value] if value else []
    if not isinstance(value, str):
        return []
    text = value.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return _parse_user_defined_report_rows(parsed)
    except json.JSONDecodeError:
        return []


def query_user_defined_report(
    report_id: str | int = None,
    filter_key_value_json: str = None,
    filters: dict | list[dict] | str = None,
    page_size: int = 200,
    max_pages: int = 100,
) -> dict:
    """
    Query a JackYun BI custom report.

    The report must be enabled for OpenAPI in 吉智BI, and callers must provide
    the exact reportId. There is no reliable public list-report endpoint in the
    current official docs, so the skill must not guess the reportId.
    """
    report_id = str(report_id or config.CHANNEL_SALES_UDR_REPORT_ID or "").strip()
    if not report_id:
        raise JackyunValidationError(
            "缺少吉智BI自定义报表 reportId。请先在吉智BI确认报表已支持开放平台查询，"
            "再配置 JACKYUN_CHANNEL_SALES_UDR_REPORT_ID 或调用时传入 udr_report_id。"
        )
    filter_text = build_user_defined_report_filter_json(filter_key_value_json or filters)
    client = get_client()
    rows = []
    last_payload = {}
    page_size = min(int(page_size or 200), 200)

    for page_index in range(max_pages):
        payload = {
            "reportId": report_id,
            "filterKeyValueJson": filter_text,
            "pageIndex": str(page_index),
            "pageSize": str(page_size),
        }
        last_payload = payload
        result = client.call(METHOD_USER_DEFINED_REPORT, payload)
        result_data = result.get("result", {}).get("data", {}) if isinstance(result, dict) else {}
        raw_data = result_data.get("data") if isinstance(result_data, dict) else result_data
        page_rows = _parse_user_defined_report_rows(raw_data)
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(page_rows) < page_size:
            break

    columns = list(dict.fromkeys(field for row in rows for field in row.keys()))
    return {
        "method": METHOD_USER_DEFINED_REPORT,
        "request": last_payload,
        "items": rows,
        "row_count": len(rows),
        "columns": columns,
        "warnings": [],
    }


def _standardize_sales_summary_row(row: dict) -> dict:
    quantity = _first_present(row, UDR_STANDARD_FIELD_ALIASES["goodsQty"])
    amount = _first_present(row, UDR_STANDARD_FIELD_ALIASES["goodsAmtCompanyCurrency"])
    sell_amount = _first_present(row, UDR_STANDARD_FIELD_ALIASES["sellAmtCompanyCurrency"])
    return {
        "time": _first_present(row, UDR_STANDARD_FIELD_ALIASES["time"]),
        "shopName": _first_present(row, UDR_STANDARD_FIELD_ALIASES["shopName"]),
        "goodsNo": _first_present(row, UDR_STANDARD_FIELD_ALIASES["goodsNo"]),
        "goodsName": _first_present(row, UDR_STANDARD_FIELD_ALIASES["goodsName"]),
        "goodsQty": quantity,
        "goodsAmtCompanyCurrency": amount,
        "sellAmtCompanyCurrency": sell_amount,
        "deliveryGoodsQty": _first_present(row, UDR_STANDARD_FIELD_ALIASES["deliveryGoodsQty"]),
        "returnGoodsQty": _first_present(row, UDR_STANDARD_FIELD_ALIASES["returnGoodsQty"]),
        "refundGoodsAmtCompanyCurrency": _first_present(row, UDR_STANDARD_FIELD_ALIASES["refundGoodsAmtCompanyCurrency"]),
        "raw": row,
    }


def build_goods_sales_analysis_payload(
    query_time_begin: str = None,
    query_time_end: str = None,
    start_time: str = None,
    end_time: str = None,
    month: str = None,
    shop_names: list[str] | str = None,
    shop_ids: list[str] | str = None,
    channel_include_keyword: str = None,
    channel_exclude_keywords: list[str] | str = None,
    channel_active_only: bool = False,
    summary_types: str = "channel,goods",
    filter_time_type: int = 2,
    time_type: int = None,
    assembly_dimension: int = 0,
    page_index: int = 0,
    page_size: int = 100,
    **filters,
) -> tuple[dict, list[dict]]:
    if month and (not start_time or not end_time):
        start_time = end_time = _month_value(month)
        if time_type is None:
            time_type = 2
    if not start_time:
        start_time = query_time_begin
    if not end_time:
        end_time = query_time_end
    if not start_time or not end_time:
        raise JackyunValidationError("货品销售多维分析必须提供 start_time/end_time、query_time_begin/query_time_end 或 month")
    if time_type is None:
        time_type = 2 if len(str(start_time)) == 7 and len(str(end_time)) == 7 else 3

    keyword_shop_ids, keyword_resolved_shops = resolve_shop_ids_by_channel_keyword(
        include_keyword=channel_include_keyword,
        exclude_keywords=channel_exclude_keywords,
        active_only=channel_active_only,
    )
    combined_shop_ids = ",".join(item for item in (_join_values(shop_ids), keyword_shop_ids) if item)
    shop_ids_text, resolved_shops = resolve_shop_ids(shop_names=shop_names, shop_ids=combined_shop_ids)
    if keyword_resolved_shops:
        existing_ids = {item.get("shopId") for item in resolved_shops}
        resolved_shops.extend(item for item in keyword_resolved_shops if item.get("shopId") not in existing_ids)
    payload = {
        "startTime": start_time,
        "endTime": end_time,
        "timeType": time_type,
        "filterTimeType": filter_time_type,
        "summaryType": summary_types,
        "assemblyDimension": assembly_dimension,
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if shop_ids_text:
        payload["shopIds"] = shop_ids_text

    for source, target in GOODS_SALES_ANALYSIS_FILTER_ALIASES.items():
        if source in filters and filters[source] not in (None, "", []):
            payload[target] = _join_values(filters[source])
    return payload, resolved_shops


def _extract_report_rows(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("rows", "list", "items", "records", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
    if any(key in data for key in goods_sales_analysis_columns()):
        return [data]
    return []


def query_goods_sales_analysis(
    query_time_begin: str = None,
    query_time_end: str = None,
    start_time: str = None,
    end_time: str = None,
    month: str = None,
    shop_names: list[str] | str = None,
    shop_ids: list[str] | str = None,
    channel_include_keyword: str = None,
    channel_exclude_keywords: list[str] | str = None,
    channel_active_only: bool = False,
    summary_types: str = "channel,goods",
    filter_time_type: int = 2,
    time_type: int = None,
    assembly_dimension: int = 0,
    page_size: int = 100,
    max_pages: int = 100,
    **filters,
) -> dict:
    """
    Query goods sales multidimensional analysis.

    Common use: query one month and several channels, grouped by channel and
    goods, returning sales amount, sales quantity and all official response
    fields.
    """
    client = get_client()
    rows = []
    resolved_shops = []
    last_payload = {}

    for page_index in range(max_pages):
        payload, resolved_shops = build_goods_sales_analysis_payload(
            query_time_begin=query_time_begin,
            query_time_end=query_time_end,
            start_time=start_time,
            end_time=end_time,
            month=month,
            shop_names=shop_names,
            shop_ids=shop_ids,
            channel_include_keyword=channel_include_keyword,
            channel_exclude_keywords=channel_exclude_keywords,
            channel_active_only=channel_active_only,
            summary_types=summary_types,
            filter_time_type=filter_time_type,
            time_type=time_type,
            assembly_dimension=assembly_dimension,
            page_index=page_index,
            page_size=page_size,
            **filters,
        )
        last_payload = payload
        result = client.call(METHOD_GOODS_SALES_ANALYSIS, payload)
        result_data = result.get("result", {}).get("data", {}) if isinstance(result, dict) else {}
        page_rows = _extract_report_rows(result_data)
        if not page_rows:
            break
        rows.extend(page_rows)

        total = 0
        if isinstance(result_data, dict):
            total = result_data.get("totalCount") or result_data.get("total") or result_data.get("count") or 0
        if total and len(rows) >= int(total):
            break
        if len(page_rows) < page_size:
            break

    columns = goods_sales_analysis_columns()
    extra_columns = [field for row in rows for field in row.keys() if field not in columns]
    columns = columns + list(dict.fromkeys(extra_columns))
    warnings = []
    if not rows:
        warnings.append(
            "货品销售多维分析返回空数据。若 ERP 前台确认有销量，请先核对 Skill 当前 AppKey "
            f"{config.JACKYUN_APP_KEY} 是否为已订阅且具备对应公司/部门/渠道数据权限的应用。"
        )
    return {
        "method": METHOD_GOODS_SALES_ANALYSIS,
        "request": last_payload,
        "resolved_shops": resolved_shops,
        "items": rows,
        "row_count": len(rows),
        "columns": columns,
        "labels": goods_sales_analysis_labels(),
        "warnings": warnings,
    }


def export_goods_sales_analysis_report(
    output_path: str,
    use_chinese_headers: bool = True,
    **query_kwargs,
) -> dict:
    result = query_goods_sales_analysis(**query_kwargs)
    output = str(output_path)
    columns = result["columns"]
    rows = result["items"]
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=columns)
    else:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df[columns]

    export_df = df.rename(columns=result["labels"]) if use_chinese_headers else df
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    lower_output = output.lower()
    if lower_output.endswith(".csv"):
        export_df.to_csv(output, index=False, encoding="utf-8-sig")
    elif lower_output.endswith((".xlsx", ".xlsm")):
        export_df.to_excel(output, index=False)
    elif lower_output.endswith(".tsv"):
        export_df.to_csv(output, index=False, sep="\t", encoding="utf-8-sig")
    else:
        raise ValueError("不支持的导出格式，请使用 .csv、.tsv、.xlsx 或 .xlsm")

    return {
        **result,
        "output_path": output,
        "header_mode": "zh-CN" if use_chinese_headers else "api",
    }


def query_channel_sales_summary(
    dimension: str = "channel_goods",
    prefer_udr: bool = False,
    use_udr_fallback: bool = True,
    udr_report_id: str | int = None,
    udr_filters: dict | list[dict] | str = None,
    **query_kwargs,
) -> dict:
    """
    Query channel sales summary for frequent operations use.

    dimension:
    - channel: by channel
    - channel_goods: by channel + goods
    """
    dimension_map = {
        "channel": "channel",
        "shop": "channel",
        "channel_daily": "time,channel",
        "daily_channel": "time,channel",
        "channel_goods": "channel,goods",
        "shop_goods": "channel,goods",
        "channel_goods_daily": "time,channel,goods",
        "daily_channel_goods": "time,channel,goods",
        "goods": "goods",
    }
    summary_type = dimension_map.get(str(dimension or "channel_goods"), dimension)
    query_kwargs.setdefault("summary_types", summary_type)
    primary_result = None
    result = None
    udr_error = ""

    def _query_udr_sales_summary() -> dict:
        shop_ids_text, resolved_shops = resolve_shop_ids(
            shop_names=query_kwargs.get("shop_names"),
            shop_ids=query_kwargs.get("shop_ids"),
        )
        keyword_shop_ids, keyword_resolved_shops = resolve_shop_ids_by_channel_keyword(
            include_keyword=query_kwargs.get("channel_include_keyword"),
            exclude_keywords=query_kwargs.get("channel_exclude_keywords"),
            active_only=bool(query_kwargs.get("channel_active_only", False)),
        )
        combined_shop_ids = ",".join(item for item in (shop_ids_text, keyword_shop_ids) if item)
        if keyword_resolved_shops:
            existing_ids = {item.get("shopId") for item in resolved_shops}
            resolved_shops.extend(item for item in keyword_resolved_shops if item.get("shopId") not in existing_ids)
        filter_text = build_channel_sales_udr_filters(
            start_time=query_kwargs.get("start_time") or query_kwargs.get("query_time_begin"),
            end_time=query_kwargs.get("end_time") or query_kwargs.get("query_time_end"),
            month=query_kwargs.get("month"),
            shop_ids=combined_shop_ids,
            filter_time_type=query_kwargs.get("filter_time_type", 2),
            trade_status=query_kwargs.get("trade_status") or query_kwargs.get("tradeStatus"),
            extra_filters=udr_filters,
        )
        udr_result = query_user_defined_report(
            report_id=udr_report_id,
            filter_key_value_json=filter_text,
            page_size=query_kwargs.get("page_size", 200),
            max_pages=query_kwargs.get("max_pages", 100),
        )
        udr_result["resolved_shops"] = resolved_shops
        return udr_result

    if prefer_udr:
        result = _query_udr_sales_summary()
    else:
        primary_result = query_goods_sales_analysis(**query_kwargs)
        result = primary_result
        if use_udr_fallback and primary_result.get("row_count", 0) == 0:
            try:
                result = _query_udr_sales_summary()
                result.setdefault("warnings", []).append(
                    "货品销售多维分析接口返回 0 行，已自动改用吉智BI自定义报表查询。"
                )
                result["fallback_from"] = METHOD_GOODS_SALES_ANALYSIS
            except (JackyunAPIError, JackyunValidationError) as exc:
                udr_error = str(exc)

    rows = []
    total_quantity = 0.0
    total_amount = 0.0
    for row in result.get("items") or []:
        summary_row = _standardize_sales_summary_row(row)
        quantity = summary_row.get("goodsQty") or 0
        amount = summary_row.get("goodsAmtCompanyCurrency")
        if amount in (None, ""):
            amount = summary_row.get("sellAmtCompanyCurrency") or 0
        try:
            total_quantity += _to_number(quantity)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            total_quantity += 0
        try:
            total_amount += _to_number(amount)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            total_amount += 0
        rows.append(summary_row)

    warnings = list(result.get("warnings") or [])
    if (
        primary_result
        and primary_result.get("row_count", 0) == 0
        and use_udr_fallback
        and result is primary_result
    ):
        warnings.append(
            "货品销售多维分析接口返回 0 行，且未能启用吉智BI自定义报表兜底。"
            "上线前必须在吉智BI提供已支持开放平台查询的 reportId。"
        )
        if udr_error:
            warnings.append(f"吉智BI自定义报表兜底失败: {udr_error}")
    result.update({
        "workflow_view": "channel_sales_summary",
        "dimension": dimension,
        "summaryType": summary_type,
        "summary_rows": rows,
        "total_goods_qty": total_quantity,
        "total_goods_amount": total_amount,
        "warnings": warnings,
        "primary_method": primary_result.get("method") if primary_result else None,
        "source_method": result.get("method"),
    })
    return result


def export_channel_sales_summary_report(
    output_path: str,
    dimension: str = "channel_goods",
    use_chinese_headers: bool = True,
    **query_kwargs,
) -> dict:
    result = query_channel_sales_summary(dimension=dimension, **query_kwargs)
    rows = result.get("summary_rows") or []
    df = pd.DataFrame(rows)
    if "raw" in df.columns:
        df = df.drop(columns=["raw"])
    columns = [
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
    ]
    if df.empty:
        df = pd.DataFrame(columns=columns)
    else:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df[columns]
    if use_chinese_headers:
        df = df.rename(columns={
            "shopName": "销售渠道",
            "time": "时间",
            "goodsNo": "货品编号",
            "goodsName": "货品名称",
            "goodsQty": "销售数量",
            "goodsAmtCompanyCurrency": "销售额(本币)",
            "sellAmtCompanyCurrency": "货品金额(本币)",
            "deliveryGoodsQty": "发货量",
            "returnGoodsQty": "退货量",
            "refundGoodsAmtCompanyCurrency": "退款金额(本币)",
        })
    output = str(output_path)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    if output.lower().endswith((".xlsx", ".xlsm")):
        df.to_excel(output, index=False)
    else:
        df.to_csv(output, index=False, encoding="utf-8-sig")
    return {
        **result,
        "output_path": output,
        "header_mode": "zh-CN" if use_chinese_headers else "api",
    }
