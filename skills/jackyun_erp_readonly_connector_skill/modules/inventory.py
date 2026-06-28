"""
库存模块

提供实时库存查询、批次库存查询、批次库存查询（含效期）、分仓库存查询(规格模式)、库存校准功能。

已实现 / 已封装 API：
┌──────────────────────────────────────┬──────────────────────────────────┐
│ API 方法名                           │ 功能                             │
├──────────────────────────────────────┼──────────────────────────────────┤
│ erp.stock.get                        │ 实时库存查询                      │
│ erp.stock.batch.get                  │ 批次库存查询                      │
│ erp.batchstockquantity.get           │ 批次库存查询含效期                │
│ erp-stock.stock.skulist              │ 分仓库存查询-规格模式             │
│ erp.stock.quantityadjust             │ 三方仓库存校准                    │
│ erp.stock.quantityadjustbyunitname   │ 三方仓库存校准(带单位)            │
└──────────────────────────────────────┴──────────────────────────────────┘
"""
import logging
from datetime import date, datetime
from typing import Optional, Union

import pandas as pd

import config
from jackyun_api import get_client
from helpers.constants import (
    METHOD_STOCK_GET, METHOD_STOCK_BATCH_GET,
    METHOD_STOCK_ADJUST, METHOD_STOCK_ADJUST_UNIT,
    METHOD_BATCH_STOCK_QUANTITY_GET, METHOD_SKU_STOCK_LIST, METHOD_STOCK_QUANTITY_GET,
)
from jackyun_api import JackyunValidationError
from helpers.cli_docs import method_exists, request_properties

logger = logging.getLogger(__name__)

WAREHOUSE_BATCH_REPORT_COLUMNS = [
    "warehouse_name",
    "batch_no",
    "goods_no",
    "goods_name",
    "current_quantity",
    "available_quantity",
    "production_date",
    "expiration_date",
    "remaining_valid_days",
    "month_end_cost",
    "tax_included_cost",
    "stock_amount",
    "last_30_days_sales",
]

WAREHOUSE_BATCH_REPORT_LABELS = {
    "warehouse_name": "仓库",
    "batch_no": "批次",
    "goods_no": "货品编号",
    "goods_name": "货品名称",
    "current_quantity": "库存数量",
    "available_quantity": "可用库存",
    "production_date": "生产日期",
    "expiration_date": "到期日期",
    "remaining_valid_days": "剩余有效天数",
    "month_end_cost": "月末成本",
    "tax_included_cost": "含税成本",
    "stock_amount": "库存金额",
    "last_30_days_sales": "近30天销量",
}

DEFAULT_STOCK_EXPORT_COLUMNS = [
    "warehouse_code",
    "warehouse_name",
    "goods_no",
    "goods_name",
    "sku_name",
    "sku_barcode",
    "unit_name",
    "current_quantity",
    "available_quantity",
    "locked_quantity",
    "reserve_quantity",
    "allocate_quantity",
    "purchasing_quantity",
    "ordering_quantity",
    "stock_in_quantity",
    "stock_out_quantity",
    "defective_quantity",
    "defective_available_quantity",
    "cost_price",
]

STOCK_EXPORT_COLUMN_LABELS = {
    "warehouse_code": "仓库编码",
    "warehouse_name": "仓库名称",
    "goods_no": "货品编号",
    "goods_name": "货品名称",
    "sku_name": "规格名称",
    "sku_barcode": "条码",
    "unit_name": "单位",
    "current_quantity": "当前库存",
    "available_quantity": "可用库存",
    "locked_quantity": "锁定库存",
    "reserve_quantity": "渠道预留库存",
    "allocate_quantity": "调拨在途数量",
    "purchasing_quantity": "采购在途数量",
    "ordering_quantity": "订购数量",
    "stock_in_quantity": "入库申请数量",
    "stock_out_quantity": "出库申请数量",
    "defective_quantity": "残次品数量",
    "defective_available_quantity": "次品可用库存",
    "cost_price": "成本价",
}

BATCH_EXPORT_COLUMNS = [
    "warehouse_code",
    "warehouse_name",
    "goods_no",
    "goods_name",
    "sku_name",
    "sku_barcode",
    "unit_name",
    "batch_no",
    "current_quantity",
    "available_quantity",
    "locked_quantity",
    "defective_quantity",
    "production_date",
    "expiration_date",
    "shelf_life",
]

BATCH_EXPORT_COLUMN_LABELS = {
    "warehouse_code": "仓库编码",
    "warehouse_name": "仓库名称",
    "goods_no": "货品编号",
    "goods_name": "货品名称",
    "sku_name": "规格名称",
    "sku_barcode": "条码",
    "unit_name": "单位",
    "batch_no": "批次号",
    "current_quantity": "批次库存",
    "available_quantity": "批次可用库存",
    "locked_quantity": "批次锁定库存",
    "defective_quantity": "批次次品库存",
    "production_date": "生产日期",
    "expiration_date": "到期日期",
    "shelf_life": "保质期",
}


def query_stock(
    goods_no: str = None,
    warehouse_name: str = None,
    warehouse_no: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    """
    查询实时库存

    :param goods_no: 货品编号
    :param warehouse_name: 仓库名称
    :param warehouse_no: 仓库编号
    :return: 库存记录列表
    """
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if goods_no:
        bizcontent["goodsNo"] = goods_no
    if warehouse_name:
        bizcontent["warehouseName"] = warehouse_name
    if warehouse_no:
        bizcontent["warehouseNo"] = warehouse_no

    result = client.call(METHOD_STOCK_GET, bizcontent)
    data = result.get("result", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def query_all_stock(**kwargs) -> list:
    """查询所有库存（自动分页）"""
    client = get_client()
    bizcontent = {}
    if kwargs.get("goods_no"):
        bizcontent["goodsNo"] = kwargs["goods_no"]
    if kwargs.get("warehouse_name"):
        bizcontent["warehouseName"] = kwargs["warehouse_name"]
    return client.call_paged(METHOD_STOCK_GET, bizcontent)


def query_batch_stock(
    goods_no: str = None,
    warehouse_name: str = None,
    batch_no: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    """
    查询批次库存

    :param goods_no: 货品编号
    :param warehouse_name: 仓库名称
    :param batch_no: 批次号
    :return: 批次库存列表
    """
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if goods_no:
        bizcontent["goodsNo"] = goods_no
    if warehouse_name:
        bizcontent["warehouseName"] = warehouse_name
    if batch_no:
        bizcontent["batchNo"] = batch_no

    result = client.call(METHOD_STOCK_BATCH_GET, bizcontent)
    data = result.get("result", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def adjust_stock(
    goods_no: str,
    warehouse_no: str,
    quantity: int,
) -> dict:
    """
    库存校准（三方仓同步）

    :param goods_no: 货品编号
    :param warehouse_no: 仓库编号
    :param quantity: 校准后数量
    :return: API 响应
    """
    client = get_client()
    bizcontent = {
        "goodsNo": goods_no,
        "warehouseNo": warehouse_no,
        "quantity": quantity,
    }
    return client.call(METHOD_STOCK_ADJUST, bizcontent)


def query_stock_quantity(
    warehouse_code: str = None,
    goods_no: str = None,
    goods_name: str = None,
    sku_name: str = None,
    sku_barcode: str = None,
    unit_name: str = None,
    page_index: int = 0,
    page_size: int = 50,
    is_blockup: int = None,
    is_channel_reserve: int = None,
    gmt_modified_start: str = None,
    gmt_modified_end: str = None,
    is_batch_management: int = None,
    is_not_query_batch_stock: int = None,
    goods_nos: str = None,
) -> list:
    """
    Official inventory paging query (erp.stockquantity.get).
    """
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    optional_fields = {
        "warehouseCode": warehouse_code,
        "goodsNo": goods_no,
        "goodsName": goods_name,
        "skuName": sku_name,
        "skuBarcode": sku_barcode,
        "unitName": unit_name,
        "isBlockup": is_blockup,
        "isChannelReserve": is_channel_reserve,
        "gmtModifiedStart": gmt_modified_start,
        "gmtModifiedEnd": gmt_modified_end,
        "isbatchmanagement": is_batch_management,
        "isNotQueryBatchStock": is_not_query_batch_stock,
        "goodsNos": goods_nos,
    }
    for field_name, value in optional_fields.items():
        if value is not None and value != "":
            bizcontent[field_name] = value

    result = client.call(METHOD_STOCK_QUANTITY_GET, bizcontent)
    data = result.get("result", {}).get("data", {})
    if isinstance(data, dict):
        items = data.get("goodsStockQuantity", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def query_historical_stock(
    warehouse_code: str,
    company_code: str = None,
    query_time: str = None,
    goods_no: str = None,
    goods_name: str = None,
    sku_barcode: str = None,
    page_index: int = 0,
    page_size: int = 50,
    method: str = None,
    extra_params: dict = None,
) -> list:
    """
    Query historical inventory through an officially confirmed method.

    The public CLI methods index available in this project does not currently
    include a clearly named historical-stock method. To avoid guessing fields,
    this function requires JACKYUN_STOCK_HISTORY_METHOD or an explicit method
    argument that exists in the official CLI methods index.
    """
    official_method = method or config.STOCK_HISTORY_METHOD
    if not official_method:
        raise JackyunValidationError(
            "当前官方 CLI 方法目录未发现明确的历史库存接口。请先确认官方方法名，并设置 JACKYUN_STOCK_HISTORY_METHOD。"
        )
    if not method_exists(official_method):
        raise JackyunValidationError(f"历史库存方法 {official_method} 不在官方 CLI methods-index.json 中，已拒绝调用")
    if not warehouse_code:
        raise JackyunValidationError("查询历史库存必须提供 warehouse_code")
    if not query_time:
        raise JackyunValidationError("查询历史库存必须提供 query_time")

    props = request_properties(official_method)
    payload = {}
    candidate_values = {
        "warehouseCode": warehouse_code,
        "warehouseNo": warehouse_code,
        "companyCode": company_code,
        "queryTime": query_time,
        "stockTime": query_time,
        "bizTime": query_time,
        "goodsNo": goods_no,
        "goodsName": goods_name,
        "skuBarcode": sku_barcode,
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    for key, value in candidate_values.items():
        if key in props and value not in (None, ""):
            payload[key] = value
    if "warehouseCode" not in payload and "warehouseNo" not in payload:
        raise JackyunValidationError(f"官方文档 {official_method} 未声明 warehouseCode/warehouseNo 字段，不能猜测仓库字段")
    if not any(key in payload for key in ("queryTime", "stockTime", "bizTime")):
        raise JackyunValidationError(f"官方文档 {official_method} 未声明 queryTime/stockTime/bizTime 字段，不能猜测历史时间字段")
    if extra_params:
        payload.update(extra_params)

    result = get_client().call(official_method, payload)
    data = result.get("result", {}).get("data", {}) if isinstance(result, dict) else {}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("goodsStockQuantity", "items", "data", "records", "rows", "list"):
            items = data.get(key)
            if isinstance(items, list):
                return items
            if isinstance(items, dict):
                return [items]
        return [data] if data else []
    return []


def query_all_stock_quantity(**kwargs) -> list:
    """
    Query all inventory rows with automatic paging for erp.stockquantity.get.
    """
    all_items = []
    page = 0
    while True:
        items = query_stock_quantity(page_index=page, page_size=50, **kwargs)
        if not items:
            break
        all_items.extend(items)
        if len(items) < 50:
            break
        page += 1
    return all_items


def format_stock_quantity(stock: dict) -> dict:
    """
    Normalize official stockquantity rows into a stable export shape.
    """
    stock = stock or {}
    return {
        "warehouse_code": stock.get("warehouseCode"),
        "warehouse_name": stock.get("warehouseName"),
        "goods_no": stock.get("goodsNo"),
        "goods_name": stock.get("goodsName"),
        "sku_name": stock.get("skuName"),
        "sku_barcode": stock.get("skuBarcode"),
        "unit_name": stock.get("unitName"),
        "current_quantity": stock.get("currentQuantity", 0),
        "available_quantity": stock.get("useQuantity", stock.get("availableQuantity", stock.get("currentQuantity", 0))),
        "locked_quantity": stock.get("lockedQuantity", 0),
        "reserve_quantity": stock.get("reserveQuantity", 0),
        "allocate_quantity": stock.get("allocateQuantity", 0),
        "purchasing_quantity": stock.get("purchasingQuantity", 0),
        "ordering_quantity": stock.get("orderingQuantity", 0),
        "stock_in_quantity": stock.get("stockInQuantity", 0),
        "stock_out_quantity": stock.get("stockOutQuantity", stock.get("stockOutuantity", 0)),
        "defective_quantity": stock.get("defectiveQuanity", 0),
        "defective_available_quantity": stock.get("defectiveUseQuantity", 0),
        "cost_price": stock.get("costPrice", 0),
    }


def export_stock_quantity_report(
    output_path: str,
    warehouse_code: str = None,
    goods_no: str = None,
    goods_name: str = None,
    sku_name: str = None,
    sku_barcode: str = None,
    unit_name: str = None,
    include_batch_details: bool = False,
    columns: list[str] = None,
    use_chinese_headers: bool = True,
) -> dict:
    """
    Export warehouse inventory to CSV/Excel.
    """
    items = query_all_stock_quantity(
        warehouse_code=warehouse_code,
        goods_no=goods_no,
        goods_name=goods_name,
        sku_name=sku_name,
        sku_barcode=sku_barcode,
        unit_name=unit_name,
    )
    rows = [format_stock_quantity(item) for item in items]
    selected_columns = columns or DEFAULT_STOCK_EXPORT_COLUMNS
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=selected_columns)
    else:
        df = df.reindex(columns=selected_columns)
    export_df = df.rename(columns=STOCK_EXPORT_COLUMN_LABELS) if use_chinese_headers else df

    output = output_path.strip()
    lower_output = output.lower()
    if lower_output.endswith(".csv"):
        export_df.to_csv(output, index=False, encoding="utf-8-sig")
    elif lower_output.endswith((".xlsx", ".xlsm")):
        export_df.to_excel(output, index=False)
    elif lower_output.endswith(".tsv"):
        export_df.to_csv(output, index=False, sep="\t", encoding="utf-8-sig")
    else:
        raise ValueError("不支持的导出格式，请使用 .csv、.tsv、.xlsx 或 .xlsm")

    batch_export = None
    if include_batch_details and warehouse_code:
        batch_items = query_all_batch_stock_quantity(
            warehouse_code=warehouse_code,
            goods_no=goods_no,
            goods_name=goods_name,
            sku_name=sku_name,
            sku_barcode=sku_barcode,
            unit_name=unit_name,
        )
        batch_rows = [format_batch_stock(item) for item in batch_items]
        batch_df = pd.DataFrame(batch_rows)
        if batch_df.empty:
            batch_df = pd.DataFrame(columns=BATCH_EXPORT_COLUMNS)
        else:
            batch_df = batch_df.reindex(columns=BATCH_EXPORT_COLUMNS)
        batch_export_df = batch_df.rename(columns=BATCH_EXPORT_COLUMN_LABELS) if use_chinese_headers else batch_df
        batch_output = output.rsplit(".", 1)[0] + ".batches.csv"
        batch_export_df.to_csv(batch_output, index=False, encoding="utf-8-sig")
        batch_export = batch_output

    return {
        "output_path": output,
        "row_count": len(rows),
        "columns": selected_columns,
        "header_mode": "zh-CN" if use_chinese_headers else "raw",
        "batch_output_path": batch_export,
    }


# ==================== 批次库存查询（含效期） ====================

def query_batch_stock_quantity(
    warehouse_code: str,
    goods_no: str = None,
    goods_name: str = None,
    sku_name: str = None,
    out_sku_code: str = None,
    sku_barcode: str = None,
    unit_name: str = None,
    page_index: int = 0,
    page_size: int = 50,
    gmt_modified_start: str = None,
    gmt_modified_end: str = None,
    expiration_date_start: str = None,
    expiration_date_end: str = None,
    is_batch_management: int = None,
) -> list:
    """
    批次库存查询（含效期）(erp.batchstockquantity.get)

    ★ 可查询某仓库某些物料的批次、生产日期、到期日期、质保期等完整信息。

    :param warehouse_code: 仓库编号（必填）
    :param goods_no: 货品编号
    :param goods_name: 货品名称
    :param sku_name: 规格，多个逗号分割
    :param out_sku_code: 第三方货品编码，多个逗号分割
    :param sku_barcode: 条码，多个逗号分割
    :param unit_name: 单位
    :param page_index: 页码，从0开始
    :param page_size: 每页记录数，默认50
    :param gmt_modified_start: 库存最近变动时间（起始，>=）
    :param gmt_modified_end: 库存最近变动时间（截止，<）
    :param expiration_date_start: 批次过期时间起
    :param expiration_date_end: 批次过期时间止
    :param is_batch_management: 传1排除未开启批次管理的批次信息，0不处理
    :return: 批次库存列表（含 batchNo, currentQuantity, availableQuantity, productionDate, expirationDate, shelfLife 等）
    """
    client = get_client()
    bizcontent = {
        "warehouseCode": warehouse_code,
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    # 可选参数
    if goods_no:
        bizcontent["goodsNo"] = goods_no
    if goods_name:
        bizcontent["goodsName"] = goods_name
    if sku_name:
        bizcontent["skuName"] = sku_name
    if out_sku_code:
        bizcontent["outSkuCode"] = out_sku_code
    if sku_barcode:
        bizcontent["skuBarcode"] = sku_barcode
    if unit_name:
        bizcontent["unitName"] = unit_name
    if gmt_modified_start:
        bizcontent["gmtModifiedStart"] = gmt_modified_start
    if gmt_modified_end:
        bizcontent["gmtModifiedEnd"] = gmt_modified_end
    if expiration_date_start:
        bizcontent["expirationDateStart"] = expiration_date_start
    if expiration_date_end:
        bizcontent["expirationDateEnd"] = expiration_date_end
    if is_batch_management is not None:
        bizcontent["isbatchmanagement"] = is_batch_management

    result = client.call(METHOD_BATCH_STOCK_QUANTITY_GET, bizcontent)
    data = result.get("result", {}).get("data", {})
    if isinstance(data, dict):
        items = data.get("goodsStockQuantity", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def format_batch_stock(batch: dict) -> dict:
    """
    格式化批次库存数据，转换时间戳为可读日期

    API返回字段说明：
    - currentQuantity: 当前库存
    - availableQuantity: 可用库存（有些记录可能没有）
    - defectiveQuanity: 残次品数量
    - lockedQuantity: 锁定库存
    - productionDate: 生产日期（毫秒时间戳）
    - expirationDate: 到期日期（毫秒时间戳）
    - shelfLife: 质保期
    - shelfLiftUnit: 质保期单位（day/year）

    :param batch: 原始批次数据
    :return: 格式化后的数据
    """
    def ts_to_date(ts):
        """毫秒时间戳转日期字符串"""
        if ts and isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
        return None

    def shelf_life_display(shelf_life, unit):
        """质保期显示"""
        if shelf_life is None:
            return None
        unit_map = {'day': '天', 'year': '年'}
        return f"{shelf_life}{unit_map.get(unit, unit)}" if unit else str(shelf_life)

    formatted = {
        # 基本信息
        'warehouse_code': batch.get('warehouseCode'),
        'warehouse_name': batch.get('warehouseName'),
        'goods_no': batch.get('goodsNo'),
        'goods_name': batch.get('goodsName'),
        'sku_name': batch.get('skuName'),
        'sku_barcode': batch.get('skuBarcode'),
        'unit_name': batch.get('unitName'),

        # 批次信息
        'batch_no': batch.get('batchNo'),

        # 库存数量（API实际字段名是 currentQuantity）
        'current_quantity': batch.get('currentQuantity', 0),
        'available_quantity': batch.get(
            'availableQuantity',
            batch.get('canUseQuantity', batch.get('useQuantity', batch.get('currentQuantity', 0)))
        ),
        'locked_quantity': batch.get('lockedQuantity', 0),
        'defective_quantity': batch.get('defectiveQuanity', 0),

        # 效期信息
        'production_date': ts_to_date(batch.get('productionDate')),
        'expiration_date': ts_to_date(batch.get('expirationDate')),
        'shelf_life': shelf_life_display(batch.get('shelfLife'), batch.get('shelfLiftUnit')),
    }
    return formatted


def query_batch_stock_formatted(warehouse_code: str, **kwargs) -> list:
    """
    查询批次库存并返回格式化后的数据（便捷函数）

    :param warehouse_code: 仓库编号（必填）
    :param kwargs: 其他查询参数（同 query_batch_stock_quantity）
    :return: 格式化后的批次库存列表
    """
    results = query_batch_stock_quantity(warehouse_code, **kwargs)
    return [format_batch_stock(b) for b in results]


def recommend_batches(
    warehouse_code: str,
    goods_no: str = None,
    goods_name: str = None,
    required_quantity: int = None,
    strategy: str = "fifo",
    is_batch_management: int = 1,
    batch_no: str = None,
    batch_no_contains: str = None,
    include_batch_nos: list[str] = None,
    exclude_batch_nos: list[str] = None,
    production_date_from: str = None,
    production_date_to: str = None,
    expiration_date_from: str = None,
    expiration_date_to: str = None,
    min_remaining_valid_days: int = None,
) -> dict:
    """
    Recommend inventory batches for a goods item and optionally build a batch allocation plan.

    strategy:
    - fifo: first produced, first out
    - fefo: first expired, first out
    - manual: only return candidates, no auto allocation

    Batch filters are applied before sorting/allocation. This supports user
    requests such as "只用某批次之后的批次" or "排除临期批次", then still follows
    FIFO unless the caller explicitly chooses another strategy.
    """
    strategy = (strategy or "fifo").lower()
    batches = query_batch_stock_formatted(
        warehouse_code=warehouse_code,
        goods_no=goods_no,
        goods_name=goods_name,
        is_batch_management=is_batch_management,
        page_size=200,
    )

    available_batches = [
        batch for batch in batches
        if float(batch.get("available_quantity", 0) or 0) > 0
    ]
    include_set = {str(item) for item in (include_batch_nos or []) if str(item or "").strip()}
    exclude_set = {str(item) for item in (exclude_batch_nos or []) if str(item or "").strip()}

    def _remaining_valid_days(batch: dict):
        expiration_date = batch.get("expiration_date")
        if not expiration_date:
            return None
        from datetime import date, datetime

        try:
            exp = datetime.strptime(str(expiration_date)[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None
        return (exp - date.today()).days

    def _matches_filters(batch: dict) -> bool:
        current_batch_no = str(batch.get("batch_no") or "")
        production_date = str(batch.get("production_date") or "")
        expiration_date = str(batch.get("expiration_date") or "")
        if batch_no and current_batch_no != str(batch_no):
            return False
        if batch_no_contains and str(batch_no_contains) not in current_batch_no:
            return False
        if include_set and current_batch_no not in include_set:
            return False
        if exclude_set and current_batch_no in exclude_set:
            return False
        if production_date_from and production_date and production_date < str(production_date_from):
            return False
        if production_date_to and production_date and production_date > str(production_date_to):
            return False
        if expiration_date_from and expiration_date and expiration_date < str(expiration_date_from):
            return False
        if expiration_date_to and expiration_date and expiration_date > str(expiration_date_to):
            return False
        if min_remaining_valid_days is not None:
            remaining_days = _remaining_valid_days(batch)
            if remaining_days is None or remaining_days < int(min_remaining_valid_days):
                return False
        return True

    available_batches = [batch for batch in available_batches if _matches_filters(batch)]

    if strategy == "fifo":
        available_batches.sort(
            key=lambda item: (
                item.get("production_date") or "9999-12-31",
                item.get("expiration_date") or "9999-12-31",
                item.get("batch_no") or "",
            )
        )
    elif strategy == "fefo":
        available_batches.sort(
            key=lambda item: (
                item.get("expiration_date") or "9999-12-31",
                item.get("production_date") or "9999-12-31",
                item.get("batch_no") or "",
            )
        )

    allocation = []
    remaining = int(required_quantity or 0)
    if strategy != "manual" and remaining > 0:
        for batch in available_batches:
            available_qty = int(float(batch.get("available_quantity", 0) or 0))
            if available_qty <= 0:
                continue
            use_qty = min(remaining, available_qty)
            allocation.append(
                {
                    "batch_no": batch.get("batch_no"),
                    "quantity": use_qty,
                    "expiration_date": batch.get("expiration_date"),
                    "production_date": batch.get("production_date"),
                }
            )
            remaining -= use_qty
            if remaining <= 0:
                break

    return {
        "warehouse_code": warehouse_code,
        "goods_no": goods_no,
        "goods_name": goods_name,
        "strategy": strategy,
        "required_quantity": required_quantity,
        "filters": {
            "batch_no": batch_no,
            "batch_no_contains": batch_no_contains,
            "include_batch_nos": include_batch_nos or [],
            "exclude_batch_nos": exclude_batch_nos or [],
            "production_date_from": production_date_from,
            "production_date_to": production_date_to,
            "expiration_date_from": expiration_date_from,
            "expiration_date_to": expiration_date_to,
            "min_remaining_valid_days": min_remaining_valid_days,
        },
        "candidates": available_batches,
        "recommended_allocation": allocation,
        "enough_stock": remaining <= 0 if required_quantity is not None else None,
        "remaining_quantity": remaining if required_quantity is not None else None,
    }


def query_all_batch_stock_quantity(**kwargs) -> list:
    """查询所有批次库存（含效期，自动分页）"""
    client = get_client()
    bizcontent = {}
    # 必填
    if kwargs.get("warehouse_code"):
        bizcontent["warehouseCode"] = kwargs["warehouse_code"]
    # 可选
    for key, api_key in [
        ("goods_no", "goodsNo"),
        ("goods_name", "goodsName"),
        ("sku_name", "skuName"),
        ("out_sku_code", "outSkuCode"),
        ("sku_barcode", "skuBarcode"),
        ("unit_name", "unitName"),
        ("gmt_modified_start", "gmtModifiedStart"),
        ("gmt_modified_end", "gmtModifiedEnd"),
        ("expiration_date_start", "expirationDateStart"),
        ("expiration_date_end", "expirationDateEnd"),
    ]:
        if kwargs.get(key):
            bizcontent[api_key] = kwargs[key]
    if kwargs.get("is_batch_management") is not None:
        bizcontent["isbatchmanagement"] = kwargs["is_batch_management"]

    all_items = []
    page = 0
    while True:
        bizcontent["pageIndex"] = page
        bizcontent["pageSize"] = 50
        result = client.call(METHOD_BATCH_STOCK_QUANTITY_GET, bizcontent)
        data = result.get("result", {}).get("data", {})
        items = data.get("goodsStockQuantity", []) if isinstance(data, dict) else []
        if not items:
            break
        all_items.extend(items)
        if len(items) < 50:
            break
        page += 1
    return all_items


# ==================== 分仓库存查询(规格模式) ====================

# 默认返回的常用字段
DEFAULT_SKU_STOCK_COLS = (
    "warehouseName,currentQuantity,canUseQuantity,lockingQuantity,"
    "purchasingQuantity,allocateQuantity,defectiveQuanity,"
    "availableQuantity,orderAbleQuantity,costPrice"
)


def query_sku_stock_list(
    warehouse_code: str,
    cols: str = None,
    goods_no: str = None,
    goods_name: str = None,
    sku_name: str = None,
    sku_barcode: str = None,
    sku_code: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    """
    分仓库存查询(规格模式) (erp-stock.stock.skulist)

    ★ 查询商品在不同仓库中的库存信息（按规格维度）。
    ★ 限制：
      1. 必须传货品和规格信息，不能只传仓库编码
      2. 最多匹配 1000 个规格

    :param warehouse_code: 仓库编码（必填）
    :param cols: 需要返回的字段，多个用逗号间隔（必填）
    :param goods_no: 货品编号
    :param goods_name: 货品名称
    :param sku_name: 规格
    :param sku_barcode: 条码（支持多条码查询 例:123,456）
    :param sku_code: 规格编码(外部编码)
    :param page_index: 页码，从0开始
    :param page_size: 每页记录数
    :return: 库存列表（按 cols 请求返回字段）
    """
    client = get_client()
    bizcontent = {
        "warehouseCode": warehouse_code,
        "cols": cols or DEFAULT_SKU_STOCK_COLS,
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if goods_no:
        bizcontent["goodsNo"] = goods_no
    if goods_name:
        bizcontent["goodsName"] = goods_name
    if sku_name:
        bizcontent["skuName"] = sku_name
    if sku_barcode:
        bizcontent["skuBarcode"] = sku_barcode
    if sku_code:
        bizcontent["skuCode"] = sku_code

    result = client.call(METHOD_SKU_STOCK_LIST, bizcontent)
    data = result.get("result", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def query_all_sku_stock_list(**kwargs) -> list:
    """查询所有分仓库存(规格模式，自动分页)"""
    client = get_client()
    bizcontent = {}
    # 必填
    if kwargs.get("warehouse_code"):
        bizcontent["warehouseCode"] = kwargs["warehouse_code"]
    bizcontent["cols"] = kwargs.get("cols", DEFAULT_SKU_STOCK_COLS)
    # 可选
    for key, api_key in [
        ("goods_no", "goodsNo"),
        ("goods_name", "goodsName"),
        ("sku_name", "skuName"),
        ("sku_barcode", "skuBarcode"),
        ("sku_code", "skuCode"),
    ]:
        if kwargs.get(key):
            bizcontent[api_key] = kwargs[key]

    all_items = []
    page = 0
    while True:
        bizcontent["pageIndex"] = page
        bizcontent["pageSize"] = 50
        result = client.call(METHOD_SKU_STOCK_LIST, bizcontent)
        data = result.get("result", {})
        items = data.get("data", []) if isinstance(data, dict) else []
        if not items:
            break
        all_items.extend(items)
        if len(items) < 50:
            break
        page += 1
    return all_items


def _coerce_date(value) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp).date()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def _date_text(value) -> str:
    parsed = _coerce_date(value)
    return parsed.isoformat() if parsed else ""


def _remaining_days(expiration_value, today: Optional[date] = None) -> Union[int, str]:
    expiration = _coerce_date(expiration_value)
    if not expiration:
        return ""
    base = today or date.today()
    return (expiration - base).days


def _first_value(source: dict, keys: tuple[str, ...], default=""):
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return default


def _to_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lookup_last_30_days_sales(
    warehouse_code: str,
    goods_no: str,
    fill_missing_zero: bool = True,
) -> Union[int, float, str]:
    if not warehouse_code or not goods_no:
        return 0 if fill_missing_zero else ""
    rows = query_all_sku_stock_list(
        warehouse_code=warehouse_code,
        goods_no=goods_no,
        cols="warehouseCode,warehouseName,goodsNo,skuName,threedayQuantity",
    )
    quantities = []
    for row in rows:
        quantity = _to_float(row.get("threedayQuantity"))
        if quantity is not None:
            quantities.append(quantity)
    if not quantities:
        return 0 if fill_missing_zero else ""
    total = sum(quantities)
    return int(total) if total.is_integer() else total


def export_warehouse_keyword_batch_stock_report(
    output_path: str,
    include_keyword: str,
    exclude_keywords: Optional[list[str]] = None,
    fill_missing_sales_zero: bool = True,
    include_sales: bool = True,
    active_only: bool = False,
    use_chinese_headers: bool = True,
) -> dict:
    """
    Export a batch-stock report for warehouses matched by keyword.

    Generalized from a real "分销组" report request:
    - Warehouse include/exclude keywords are user-provided parameters.
    - Negative contexts such as "除X" / "除A和X" are handled by
      modules.warehouse.search_warehouses_by_keywords().
    - Some matched warehouses may be virtual/transfer warehouses. If
      `erp-stock.stock.skulist.threedayQuantity` has no value, near-30-day
      sales may be filled with 0 only when the user accepts that business rule.
    - Cost fields are filled only when returned by inventory APIs; otherwise
      they remain blank.
    """
    from modules.warehouse import search_warehouses_by_keywords

    if not output_path:
        raise JackyunValidationError("导出仓库关键词批次库存报表必须提供 output_path")
    if not str(include_keyword or "").strip():
        raise JackyunValidationError("导出仓库关键词批次库存报表必须提供 include_keyword")

    excludes = exclude_keywords if exclude_keywords is not None else [f"除{include_keyword}"]
    warehouse_result = search_warehouses_by_keywords(
        include_keyword=include_keyword,
        exclude_keywords=excludes,
        active_only=active_only,
    )
    warehouses = warehouse_result.get("items") or []

    rows = []
    sales_cache: dict[tuple[str, str], Union[int, float, str]] = {}
    skipped_warehouses = []
    for warehouse in warehouses:
        warehouse_code = warehouse.get("warehouseCode") or warehouse.get("code") or ""
        warehouse_name = warehouse.get("warehouseName") or warehouse.get("name") or ""
        if not warehouse_code:
            skipped_warehouses.append({"warehouseName": warehouse_name, "reason": "missing warehouseCode"})
            continue

        batch_rows = query_all_batch_stock_quantity(
            warehouse_code=warehouse_code,
            is_batch_management=1,
        )
        for batch in batch_rows:
            goods_no = batch.get("goodsNo") or ""
            sales_key = (warehouse_code, goods_no)
            if include_sales and sales_key not in sales_cache:
                sales_cache[sales_key] = _lookup_last_30_days_sales(
                    warehouse_code=warehouse_code,
                    goods_no=goods_no,
                    fill_missing_zero=fill_missing_sales_zero,
                )

            month_end_cost = _first_value(batch, ("monthEndCost", "endMonthCost", "costPrice"))
            tax_included_cost = _first_value(batch, ("taxIncludedCost", "taxCostPrice", "taxPrice"))
            quantity = _to_float(_first_value(batch, ("currentQuantity", "quantity"), 0)) or 0
            cost_for_amount = _to_float(tax_included_cost) or _to_float(month_end_cost)
            stock_amount = round(quantity * cost_for_amount, 6) if cost_for_amount is not None else ""

            rows.append({
                "warehouse_name": batch.get("warehouseName") or warehouse_name,
                "batch_no": batch.get("batchNo") or "",
                "goods_no": goods_no,
                "goods_name": batch.get("goodsName") or "",
                "current_quantity": _first_value(batch, ("currentQuantity", "quantity"), 0),
                "available_quantity": _first_value(batch, ("availableQuantity", "canUseQuantity", "useQuantity", "currentQuantity"), 0),
                "production_date": _date_text(batch.get("productionDate")),
                "expiration_date": _date_text(batch.get("expirationDate")),
                "remaining_valid_days": _remaining_days(batch.get("expirationDate")),
                "month_end_cost": month_end_cost,
                "tax_included_cost": tax_included_cost,
                "stock_amount": stock_amount,
                "last_30_days_sales": sales_cache.get(sales_key, 0 if fill_missing_sales_zero else ""),
            })

    df = pd.DataFrame(rows, columns=WAREHOUSE_BATCH_REPORT_COLUMNS)
    export_df = df.rename(columns=WAREHOUSE_BATCH_REPORT_LABELS) if use_chinese_headers else df
    output = str(output_path)
    lower_output = output.lower()
    if lower_output.endswith(".csv"):
        export_df.to_csv(output, index=False, encoding="utf-8-sig")
    elif lower_output.endswith((".xlsx", ".xlsm")):
        export_df.to_excel(output, index=False)
    elif lower_output.endswith((".tsv", ".txt")):
        export_df.to_csv(output, index=False, sep="\t", encoding="utf-8-sig")
    else:
        raise ValueError("不支持的导出格式，请使用 .csv、.tsv、.xlsx 或 .xlsm")

    return {
        "output_path": output,
        "row_count": len(rows),
        "warehouse_count": len(warehouses),
        "warehouse_cache_count": warehouse_result.get("cache_count", 0),
        "warehouse_source": warehouse_result.get("source", ""),
        "include_keyword": include_keyword,
        "exclude_keywords": excludes,
        "fill_missing_sales_zero": fill_missing_sales_zero,
        "include_sales": include_sales,
        "columns": WAREHOUSE_BATCH_REPORT_COLUMNS,
        "header_mode": "zh-CN" if use_chinese_headers else "raw",
        "skipped_warehouses": skipped_warehouses,
        "pain_points": [
            "匹配到的仓库可能包含虚拟/调拨仓，erp-stock.stock.skulist.threedayQuantity 可能为空",
            "月末成本、含税成本、库存金额仅在接口返回成本字段时填充，否则留空",
        ],
    }


# Backward-compatible convenience wrapper for the real distribution-group case.
def export_distribution_group_batch_stock_report(
    output_path: str,
    include_keyword: str = "分销组",
    exclude_keywords: Optional[list[str]] = None,
    fill_missing_sales_zero: bool = True,
    include_sales: bool = True,
    active_only: bool = False,
    use_chinese_headers: bool = True,
) -> dict:
    return export_warehouse_keyword_batch_stock_report(
        output_path=output_path,
        include_keyword=include_keyword,
        exclude_keywords=exclude_keywords,
        fill_missing_sales_zero=fill_missing_sales_zero,
        include_sales=include_sales,
        active_only=active_only,
        use_chinese_headers=use_chinese_headers,
    )
