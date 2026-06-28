"""
货品模块

优先使用当前已确认存在的真实接口：
- erp.storage.goodslist: 分页查询货品信息
- erp-goods.goods.sku.search: 条件查询货品
- erp.goodsbatchinfo.get: 货品批次查询
"""
import logging
from typing import Optional

from jackyun_api import get_client
from helpers.constants import (
    METHOD_GOODS_ADD,
    METHOD_GOODS_BATCH_INFO_GET,
    METHOD_GOODS_SKU_SEARCH,
    METHOD_GOODS_UPDATE,
    METHOD_STORAGE_GOODS_LIST,
)
from helpers.local_store import get_cached_master_data, get_master_data
from helpers.matching import best_match, lookup_score, normalize_lookup_text

logger = logging.getLogger(__name__)

GOODS_FULL_CACHE_MIN_COUNT = 10000

DEFAULT_SKU_SEARCH_COLS = ",".join([
    "goodsId",
    "goodsNo",
    "goodsName",
    "skuId",
    "skuNo",
    "skuName",
    "skuBarcode",
    "outSkuCode",
    "unitName",
    "isBlockup",
])


def _extract_items(data) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("goods", "goodsList", "goodsInfo", "rows", "records", "list", "data"):
        items = data.get(key)
        if isinstance(items, list):
            return items
        if isinstance(items, dict) and items:
            nested = _extract_items(items)
            return nested or [items]
    return [data] if data else []


def query_goods(
    goods_no: str = None,
    goods_name: str = None,
    sku_barcode: str = None,
    sku_name: str = None,
    page_index: int = 0,
    page_size: int = 50,
    start_date_modified_sku: str = None,
    end_date_modified_sku: str = None,
    max_sku_id: str = None,
) -> list:
    """
    分页查询货品信息（erp.storage.goodslist）。
    """
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if goods_no:
        bizcontent["goodsNo"] = goods_no
    if goods_name:
        bizcontent["goodsName"] = goods_name
    if sku_barcode:
        bizcontent["skuBarcode"] = sku_barcode
    if sku_name:
        bizcontent["skuName"] = sku_name
    if start_date_modified_sku:
        bizcontent["startDateModifiedSku"] = start_date_modified_sku
    if end_date_modified_sku:
        bizcontent["endDateModifiedSku"] = end_date_modified_sku
    if max_sku_id is not None:
        bizcontent["maxSkuId"] = str(max_sku_id)

    result = client.call(METHOD_STORAGE_GOODS_LIST, bizcontent)
    data = result.get("result", {})
    return _extract_items(data)


def query_goods_sku_search(
    goods_nos: str = None,
    goods_names: str = None,
    sku_barcodes: str = None,
    sku_names: str = None,
    cols: str = DEFAULT_SKU_SEARCH_COLS,
    page_index: int = 0,
    page_size: int = 50,
    is_include_blockup: int = 0,
) -> list:
    """
    条件查询货品（erp-goods.goods.sku.search）。
    """
    client = get_client()
    bizcontent = {
        "cols": cols,
        "pageIndex": page_index,
        "pageSize": page_size,
        "isIncludeBlockup": is_include_blockup,
    }
    if goods_nos:
        bizcontent["goodsNos"] = goods_nos
    if goods_names:
        bizcontent["goodsNames"] = goods_names
    if sku_barcodes:
        bizcontent["skuBarcodes"] = sku_barcodes
    if sku_names:
        bizcontent["skuNames"] = sku_names

    result = client.call(METHOD_GOODS_SKU_SEARCH, bizcontent)
    data = result.get("result", {})
    return _extract_items(data)


def query_goods_batch_info(
    goods_no: str = None,
    sku_barcode: str = None,
    out_sku_code: str = None,
    batch_no: str = None,
    page_index: int = 0,
    page_size: int = 50,
    not_filter_no_stock_batch: int = 1,
) -> list:
    """
    货品批次查询（erp.goodsbatchinfo.get）。
    """
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
        "notFilterNoStockBatch": not_filter_no_stock_batch,
    }
    if goods_no:
        bizcontent["goodsNo"] = goods_no
    if sku_barcode:
        bizcontent["skuBarcode"] = sku_barcode
    if out_sku_code:
        bizcontent["outSkuCode"] = out_sku_code
    if batch_no:
        bizcontent["batchNo"] = batch_no

    result = client.call(METHOD_GOODS_BATCH_INFO_GET, bizcontent)
    data = result.get("result", {})
    return _extract_items(data)


def query_all_goods(**kwargs) -> list:
    if "page_index" not in kwargs and "max_sku_id" not in kwargs:
        return query_all_goods_by_cursor(**kwargs)

    all_items = []
    page_index = 0
    page_size = 50
    while True:
        items = query_goods(page_index=page_index, page_size=page_size, **kwargs)
        if not items:
            break
        all_items.extend(items)
        if len(items) < page_size:
            break
        page_index += 1
    return all_items


def query_all_goods_by_cursor(**kwargs) -> list:
    """
    Query all goods using the official maxSkuId cursor to avoid the 10k limit.
    """
    all_items = []
    max_sku_id = kwargs.pop("max_sku_id", "0")
    page_size = int(kwargs.pop("page_size", 200))
    seen_cursors = set()
    while True:
        if max_sku_id in seen_cursors:
            break
        seen_cursors.add(max_sku_id)
        items = query_goods(
            page_index=0,
            page_size=page_size,
            max_sku_id=max_sku_id,
            **kwargs,
        )
        if not items:
            break
        all_items.extend(items)
        next_cursor = str(items[-1].get("skuId") or "")
        if not next_cursor or next_cursor == str(max_sku_id) or len(items) < page_size:
            break
        max_sku_id = next_cursor
    return all_items


def get_goods_by_no(goods_no: str) -> Optional[dict]:
    results = get_master_data(
        "goods",
        lambda: query_goods(goods_no=goods_no, page_size=10),
        lambda item: str(item.get("goodsNo") or "") == str(goods_no),
        save_fresh=False,
    )
    for item in results:
        if str(item.get("goodsNo") or "") == goods_no:
            return item
    fallback = query_goods_sku_search(goods_nos=goods_no, page_size=10)
    for item in fallback:
        if str(item.get("goodsNo") or "") == goods_no:
            return item
    return (results or fallback or [None])[0]


def suggest_goods(keyword: str, limit: int = 10) -> list:
    cached = get_cached_master_data("goods")
    candidates = cached if len(cached) >= GOODS_FULL_CACHE_MIN_COUNT else []
    if not candidates:
        candidates = query_goods(goods_name=keyword, page_size=50)
    if not candidates:
        candidates = query_goods_sku_search(goods_names=keyword, page_size=50)

    def _score(item: dict) -> tuple:
        goods_name = str(item.get("goodsName", ""))
        goods_no = str(item.get("goodsNo", ""))
        sku_name = str(item.get("skuName", ""))
        sku_barcode = str(item.get("skuBarcode", ""))
        return max(
            (*lookup_score(keyword, goods_name), -len(goods_name)),
            (*lookup_score(keyword, goods_no), -len(goods_name)),
            (*lookup_score(keyword, sku_name), -len(goods_name)),
            (*lookup_score(keyword, sku_barcode), -len(goods_name)),
        )

    candidates.sort(key=_score, reverse=True)
    return candidates[:limit]


def resolve_goods_for_transfer(goods_no: str = None, goods_name: str = None) -> dict:
    """
    Resolve a goods record for transfer auto-fill.

    Search order:
    1. erp.storage.goodslist
    2. erp-goods.goods.sku.search
    """
    if goods_no:
        cached_hits = get_master_data("goods", lambda: [])
        cached_match = best_match(goods_no, cached_hits, ("goodsNo", "skuNo", "skuBarcode", "outSkuCode"), min_ratio=0.92)
        if cached_match:
            return {"record": cached_match, "source": "data/cache/goods", "match": "goodsNo_cached"}
        storage_hits = query_goods(goods_no=goods_no, page_size=10)
        exact_storage = [
            item for item in storage_hits
            if normalize_lookup_text(item.get("goodsNo")) == normalize_lookup_text(goods_no)
        ]
        if len(exact_storage) == 1:
            return {"record": exact_storage[0], "source": METHOD_STORAGE_GOODS_LIST, "match": "goodsNo_exact"}
        sku_hits = query_goods_sku_search(goods_nos=goods_no, page_size=10)
        exact_sku = [
            item for item in sku_hits
            if normalize_lookup_text(item.get("goodsNo")) == normalize_lookup_text(goods_no)
        ]
        if len(exact_sku) == 1:
            return {"record": exact_sku[0], "source": METHOD_GOODS_SKU_SEARCH, "match": "goodsNo_exact"}
        candidate = (exact_storage or storage_hits or exact_sku or sku_hits or [None])[0]
        return {"record": candidate, "source": METHOD_STORAGE_GOODS_LIST if storage_hits else METHOD_GOODS_SKU_SEARCH if sku_hits else None, "match": "goodsNo_fallback"}

    if goods_name:
        cached_hits = get_master_data("goods", lambda: [])
        cached_match = best_match(goods_name, cached_hits, ("goodsName", "skuName", "goodsNo", "skuBarcode"), min_ratio=0.9)
        if cached_match:
            return {"record": cached_match, "source": "data/cache/goods", "match": "goodsName_cached"}
        storage_hits = query_goods(goods_name=goods_name, page_size=20)
        exact_storage = [
            item for item in storage_hits
            if normalize_lookup_text(item.get("goodsName")) == normalize_lookup_text(goods_name)
        ]
        if len(exact_storage) == 1:
            return {"record": exact_storage[0], "source": METHOD_STORAGE_GOODS_LIST, "match": "goodsName_exact"}
        sku_hits = query_goods_sku_search(goods_names=goods_name, page_size=20)
        exact_sku = [
            item for item in sku_hits
            if normalize_lookup_text(item.get("goodsName")) == normalize_lookup_text(goods_name)
        ]
        if len(exact_sku) == 1:
            return {"record": exact_sku[0], "source": METHOD_GOODS_SKU_SEARCH, "match": "goodsName_exact"}
        candidate = (exact_storage or storage_hits or exact_sku or sku_hits or [None])[0]
        return {"record": candidate, "source": METHOD_STORAGE_GOODS_LIST if storage_hits else METHOD_GOODS_SKU_SEARCH if sku_hits else None, "match": "goodsName_fallback"}

    return {"record": None, "source": None, "match": None}


def add_goods(goods_data: dict) -> dict:
    client = get_client()
    return client.call(METHOD_GOODS_ADD, goods_data)


def update_goods(goods_data: dict) -> dict:
    client = get_client()
    return client.call(METHOD_GOODS_UPDATE, goods_data)
