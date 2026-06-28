"""
仓库模块

API: erp.warehouse.get（已确认订阅）

数据结构（实测）：
- warehouseId / warehouseCode / warehouseName: 仓库标识
- warehouseCompanyId / warehouseCompanyName / warehouseCompanyCode: 所属公司
- warehouseDepartId / warehouseDepartName / warehouseDepartCode: 所属部门
- warehouseTypeCode / warehouseTypeName: 仓库类型（1=自建自用）
- isBlockup: 0=正常, 1=停用
- salesList[]: 关联的渠道列表 [{warehouseId, channelId, channelName, channelCode}]
- address / tel / linkMan: 仓库地址/电话/联系人

★ 业务规则：仓库通过 warehouseCompanyId 与渠道的 companyId 关联
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from jackyun_api import get_client
from helpers.constants import METHOD_WAREHOUSE_GET
from helpers.local_store import get_cached_master_data, get_master_data
from helpers.matching import best_match, normalize_lookup_text

logger = logging.getLogger(__name__)


def query_warehouses(
    name: str = None,
    code: str = None,
    page_index: int = 0,
    page_size: int = 50,
    gmt_modified_start: str = None,
    gmt_modified_end: str = None,
) -> list:
    """
    查询仓库列表

    返回嵌套结构: result.data.warehouseInfo[]

    :param name: 仓库名称（模糊搜索）
    :param code: 仓库编号
    :return: 仓库列表
    """
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if name:
        bizcontent["name"] = name
    if code:
        bizcontent["code"] = code
    if gmt_modified_start:
        bizcontent["gmtModifiedStart"] = gmt_modified_start
    if gmt_modified_end:
        bizcontent["gmtModifiedEnd"] = gmt_modified_end

    result = client.call(METHOD_WAREHOUSE_GET, bizcontent)
    data = result.get("result", {}).get("data", {})

    if isinstance(data, dict):
        items = data.get("warehouseInfo", data.get("data", []))
        if isinstance(items, list):
            return items
        return [items] if items else []
    if isinstance(data, list):
        return data
    return []


WAREHOUSE_FULL_CACHE_MIN_COUNT = 200


def query_all_warehouses() -> list:
    """查询所有仓库（自动分页）"""
    all_items = []
    page_index = 0
    page_size = 100
    while True:
        items = query_warehouses(page_index=page_index, page_size=page_size)
        if not items:
            break
        all_items.extend(items)
        if len(items) < page_size:
            break
        page_index += 1
    return all_items


def _cache_seems_incomplete(items: list[dict] | None) -> bool:
    return len(items or []) < WAREHOUSE_FULL_CACHE_MIN_COUNT


def _matches_warehouse_name_or_code(warehouse: dict, value: str) -> bool:
    target = normalize_lookup_text(value)
    return target in {
        normalize_lookup_text(warehouse.get("warehouseName")),
        normalize_lookup_text(warehouse.get("warehouseCode")),
        normalize_lookup_text(warehouse.get("name")),
        normalize_lookup_text(warehouse.get("code")),
    }


def _find_exact_cached_warehouse(value: str) -> Optional[dict]:
    cached = get_cached_master_data("warehouses")
    for warehouse in cached:
        if _matches_warehouse_name_or_code(warehouse, value):
            return warehouse
    return None


def _refresh_full_warehouse_cache() -> list[dict]:
    fresh = query_all_warehouses()
    if fresh:
        from helpers.local_store import save_cached_master_data

        save_cached_master_data("warehouses", fresh)
    return fresh


def get_warehouse_by_name(name: str) -> Optional[dict]:
    """按仓库名称/编号查询单个仓库。

    单据创建都应走这个公共入口。若本地缓存只有第一页或缓存较旧，
    首次未命中时会自动全量分页刷新一次，避免漏掉后面页的仓库。
    """
    cached = get_cached_master_data("warehouses")
    cached_match = _find_exact_cached_warehouse(name)
    if cached_match:
        return cached_match

    if _cache_seems_incomplete(cached):
        refreshed = _refresh_full_warehouse_cache()
        for warehouse in refreshed:
            if _matches_warehouse_name_or_code(warehouse, name):
                return warehouse
        refreshed_match = best_match(name, refreshed, ("warehouseName", "warehouseCode", "name", "code"), min_ratio=0.9)
        if refreshed_match:
            return refreshed_match

    cached_fuzzy_match = best_match(name, cached, ("warehouseName", "warehouseCode", "name", "code"), min_ratio=0.9)
    if cached_fuzzy_match:
        return cached_fuzzy_match

    results = get_master_data(
        "warehouses",
        lambda: query_warehouses(name=name, page_size=20),
        lambda item: normalize_lookup_text(item.get("warehouseName")) == normalize_lookup_text(name),
        save_fresh=False,
    )
    for wh in results:
        if normalize_lookup_text(wh.get("warehouseName")) == normalize_lookup_text(name):
            return wh

    # Some users provide warehouse code in the natural-language "warehouse name"
    # slot. Try the code API, then refresh the full cache once even when the cache
    # looks large enough, because a newly added warehouse can be missing locally.
    code_results = query_warehouses(code=name, page_size=20)
    for wh in code_results:
        if _matches_warehouse_name_or_code(wh, name):
            return wh

    refreshed = _refresh_full_warehouse_cache()
    refreshed_match = best_match(name, refreshed, ("warehouseName", "warehouseCode", "name", "code"), min_ratio=0.9)
    return refreshed_match or (results or code_results or [None])[0]


def get_warehouse_by_code(code: str) -> Optional[dict]:
    """按仓库编号查询单个仓库"""
    cached = get_cached_master_data("warehouses")
    for warehouse in cached:
        if str(warehouse.get("warehouseCode") or warehouse.get("code") or "") == str(code):
            return warehouse

    if _cache_seems_incomplete(cached):
        for warehouse in _refresh_full_warehouse_cache():
            if str(warehouse.get("warehouseCode") or warehouse.get("code") or "") == str(code):
                return warehouse

    results = get_master_data(
        "warehouses",
        lambda: query_warehouses(code=code, page_size=5),
        lambda item: str(item.get("warehouseCode") or "") == str(code),
        save_fresh=False,
    )
    for wh in results:
        if wh.get("warehouseCode") == code:
            return wh

    # If a packaged cache is old but not obviously partial, refresh once before
    # declaring the warehouse missing. This protects all order-creation flows.
    for warehouse in _refresh_full_warehouse_cache():
        if str(warehouse.get("warehouseCode") or warehouse.get("code") or "") == str(code):
            return warehouse
    return results[0] if results else None


def _get_full_warehouse_cache(refresh_if_incomplete: bool = True) -> tuple[list[dict], str]:
    cached = get_cached_master_data("warehouses")
    if cached and (len(cached) >= WAREHOUSE_FULL_CACHE_MIN_COUNT or not refresh_if_incomplete):
        return cached, "data/cache/warehouses"

    if refresh_if_incomplete:
        fresh = _refresh_full_warehouse_cache()
        if fresh:
            return fresh, "erp.warehouse.get"

    return cached, "data/cache/warehouses(partial)"


def _has_negative_keyword_context(text: str, keyword: str) -> bool:
    if not text or not keyword:
        return False
    if f"除{keyword}" in text:
        return True
    return re.search(rf"除.{{0,12}}{re.escape(keyword)}", text) is not None


def search_warehouses_by_keywords(
    include_keyword: str,
    exclude_keywords: list[str] | None = None,
    active_only: bool = False,
    refresh_if_incomplete: bool = True,
    exclude_negative_context: bool = True,
) -> dict:
    """
    Search warehouses from the full master-data cache/API.

    Use this for requests like: 名称包含“分销组”，但不要“除分销组”。
    The function avoids the historical bug where a narrow lookup overwrote the
    full warehouse cache with only a few records.
    """
    include_text = normalize_lookup_text(include_keyword)
    excludes = [normalize_lookup_text(item) for item in (exclude_keywords or []) if str(item or "").strip()]
    if not include_text:
        return {
            "total": 0,
            "source": "none",
            "cache_count": 0,
            "items": [],
            "error": "include_keyword 不能为空",
        }

    warehouses, source = _get_full_warehouse_cache(refresh_if_incomplete=refresh_if_incomplete)
    matched = []
    for warehouse in warehouses:
        name = warehouse.get("warehouseName") or warehouse.get("name") or ""
        normalized_name = normalize_lookup_text(name)
        if include_text not in normalized_name:
            continue
        if exclude_negative_context and _has_negative_keyword_context(normalized_name, include_text):
            continue
        if any(exclude in normalized_name for exclude in excludes):
            continue
        if active_only and str(warehouse.get("isBlockup") or "0") not in {"0", "False", "false", ""}:
            continue
        matched.append(warehouse)

    matched.sort(key=lambda item: (
        str(item.get("warehouseCompanyName") or ""),
        str(item.get("warehouseName") or ""),
    ))
    return {
        "total": len(matched),
        "source": source,
        "cache_count": len(warehouses),
        "include_keyword": include_keyword,
        "exclude_keywords": exclude_keywords or [],
        "exclude_negative_context": exclude_negative_context,
        "items": matched,
    }


def get_warehouse_id_by_code(code: str) -> Optional[str]:
    """根据仓库编号获取仓库ID（用于物流匹配）"""
    wh = get_warehouse_by_code(code)
    return wh.get("warehouseId") if wh else None


def validate_warehouse_company(warehouse: dict, company_id: str) -> bool:
    """
    验证仓库是否属于指定公司

    :param warehouse: 仓库数据
    :param company_id: 公司ID（来自渠道的 companyId）
    :return: True=属于同一公司
    """
    wh_company_id = warehouse.get("warehouseCompanyId", "")
    return wh_company_id == company_id


def search_warehouses_by_company(company_id: str) -> list:
    """
    查询属于指定公司的所有仓库

    :param company_id: 公司ID
    :return: 仓库列表
    """
    all_wh = query_all_warehouses()
    return [
        wh for wh in all_wh
        if wh.get("warehouseCompanyId") == company_id
        and wh.get("isBlockup", 0) == 0
    ]


def extract_warehouse_contact(warehouse: dict) -> dict:
    """
    Extract commonly used warehouse contact fields with tolerant key handling.
    """
    warehouse = warehouse or {}
    return {
        "name": (
            warehouse.get("linkMan")
            or warehouse.get("linkman")
            or warehouse.get("contactName")
            or warehouse.get("contacts")
            or ""
        ),
        "mobile": (
            warehouse.get("mobile")
            or warehouse.get("tel")
            or warehouse.get("phone")
            or warehouse.get("contactMobile")
            or ""
        ),
        "address": warehouse.get("address") or warehouse.get("detailAddress") or "",
    }
