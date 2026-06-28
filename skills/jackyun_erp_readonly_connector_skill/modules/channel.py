"""
渠道/客户模块

API: erp.sales.get（已确认订阅）

数据结构（实测）：
- channelCode / channelName: 渠道编号/名称
- channelDepartId / channelDepartName: 所属部门
- companyId / companyName / companyCode: 所属公司
- warehouseCode / warehouseName: 默认仓库
- chargeType: 结算方式
- responsibleUserName: 负责人

★ 业务规则：创建销售单时，渠道和仓库必须属于同一个公司
"""
import logging
from typing import Optional

from jackyun_api import get_client
from helpers.constants import METHOD_CHANNEL_GET
from helpers.local_store import get_cached_master_data, get_master_data
from helpers.matching import best_match, lookup_score, normalize_lookup_text

logger = logging.getLogger(__name__)

CHANNEL_FULL_CACHE_MIN_COUNT = 200


def query_channels(
    name: str = None,
    code: str = None,
    page_index: int = 0,
    page_size: int = 50,
    gmt_modified_start: str = None,
    gmt_modified_end: str = None,
) -> list:
    """
    查询销售渠道

    返回嵌套结构: result.data.salesChannelInfo[]

    :param name: 渠道/客户名称（模糊搜索）
    :param code: 渠道编号
    :return: 渠道列表
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

    result = client.call(METHOD_CHANNEL_GET, bizcontent)
    data = result.get("result", {}).get("data", {})

    # erp.sales.get 返回嵌套结构 salesChannelInfo[]
    if isinstance(data, dict):
        items = data.get("salesChannelInfo", data.get("data", []))
        if isinstance(items, list):
            return items
        return [items] if items else []
    if isinstance(data, list):
        return data
    return []


def query_all_channels() -> list:
    """查询所有渠道（自动分页）"""
    all_items = []
    page_index = 0
    page_size = 50
    while True:
        items = query_channels(page_index=page_index, page_size=page_size)
        if not items:
            break
        all_items.extend(items)
        if len(items) < page_size:
            break
        page_index += 1
    return all_items


def _refresh_full_channel_cache() -> list[dict]:
    fresh = query_all_channels()
    if fresh:
        from helpers.local_store import save_cached_master_data

        save_cached_master_data("channels", fresh)
    return fresh


def _find_channel_in_items(name: str, items: list[dict]) -> Optional[dict]:
    normalized = normalize_lookup_text(name)
    for channel in items or []:
        if normalized in {
            normalize_lookup_text(channel.get("channelName")),
            normalize_lookup_text(channel.get("channelCode")),
        }:
            return channel
    return best_match(name, items, ("channelName", "channelCode"), min_ratio=0.9)


def get_channel_by_name(name: str) -> Optional[dict]:
    """
    按渠道名称查询

    先精确匹配，不到则返回第一条模糊结果
    """
    def matcher(item: dict) -> bool:
        return normalize_lookup_text(item.get("channelName")) == normalize_lookup_text(name)

    cached = get_cached_master_data("channels")
    cached_match = _find_channel_in_items(name, cached)
    if cached_match:
        return cached_match

    if len(cached) < CHANNEL_FULL_CACHE_MIN_COUNT:
        refreshed_match = _find_channel_in_items(name, _refresh_full_channel_cache())
        if refreshed_match:
            return refreshed_match

    results = get_master_data(
        "channels",
        lambda: query_channels(name=name, page_size=20),
        matcher,
        save_fresh=False,
    )
    for ch in results:
        if normalize_lookup_text(ch.get("channelName")) == normalize_lookup_text(name):
            return ch
    refreshed_match = _find_channel_in_items(name, _refresh_full_channel_cache())
    return refreshed_match or (results[0] if results else None)


def search_channels(keyword: str, page_size: int = 20) -> list:
    """
    搜索渠道（支持部门名/渠道名模糊匹配）

    :param keyword: 搜索关键词
    :return: 匹配的渠道列表
    """
    results = query_channels(name=keyword, page_size=page_size)
    return results


def search_channels_by_keywords(
    include_keyword: str,
    exclude_keywords: list[str] = None,
    fields: tuple[str, ...] = ("channelName", "channelCode", "channelDepartName", "companyName"),
    active_only: bool = False,
) -> list[dict]:
    """
    Search full channel cache/API by include/exclude keywords.

    Use this for report workflows such as "渠道包含分销组". It returns channel
    records so callers can pass channelId as shopIds to report APIs instead of
    fetching all sales orders and filtering locally.
    """
    include_text = normalize_lookup_text(include_keyword)
    if not include_text:
        return []
    exclude_texts = [
        normalize_lookup_text(item)
        for item in (exclude_keywords or [])
        if normalize_lookup_text(item)
    ]

    channels = get_cached_master_data("channels")
    if len(channels) < CHANNEL_FULL_CACHE_MIN_COUNT:
        channels = _refresh_full_channel_cache() or channels

    def haystack(item: dict) -> str:
        return " ".join(normalize_lookup_text(item.get(field)) for field in fields)

    matches = []
    for item in channels:
        if active_only and str(item.get("isBlockup") or item.get("status") or "").strip() in {"1", "停用", "禁用"}:
            continue
        text = haystack(item)
        if include_text not in text:
            continue
        if any(exclude in text for exclude in exclude_texts):
            continue
        matches.append(item)
    return matches


def get_channel_default_warehouse(channel: dict) -> dict:
    """
    从渠道数据中提取默认仓库信息

    :param channel: 渠道数据（从 query_channels 返回的单条记录）
    :return: {"warehouseCode": "...", "warehouseName": "...", "companyId": "...", "companyName": "..."}
    """
    return {
        "warehouseCode": channel.get("warehouseCode", ""),
        "warehouseName": channel.get("warehouseName", ""),
        "companyId": channel.get("companyId", ""),
        "companyName": channel.get("companyName", ""),
    }


def resolve_channel_info(shop_name: str) -> dict:
    """
    根据渠道名称解析完整的渠道→仓库→公司信息

    :param shop_name: 渠道名称
    :return: {
        "found": bool,
        "channel": 渠道完整数据,
        "channelName": 渠道名称,
        "channelCode": 渠道编号,
        "warehouseCode": 默认仓库编号,
        "warehouseName": 默认仓库名称,
        "companyId": 公司ID,
        "companyName": 公司名称,
        "departName": 部门名称,
    }
    """
    channel = get_channel_by_name(shop_name)
    if not channel:
        return {"found": False, "error": f"未找到渠道: {shop_name}"}

    return {
        "found": True,
        "channel": channel,
        "channelName": channel.get("channelName", ""),
        "channelCode": channel.get("channelCode", ""),
        "warehouseCode": channel.get("warehouseCode", ""),
        "warehouseName": channel.get("warehouseName", ""),
        "companyId": channel.get("companyId", ""),
        "companyName": channel.get("companyName", ""),
        "departName": channel.get("channelDepartName", ""),
    }


def suggest_channels(keyword: str, company_name: str = None, limit: int = 10) -> list:
    """
    Fuzzy channel suggestions for cases where the user does not know the exact name.
    """
    cached = get_cached_master_data("channels")
    candidates = cached or query_channels(name=keyword, page_size=50)
    if company_name:
        candidates = [
            item for item in candidates
            if company_name in str(item.get("companyName", ""))
        ]

    def _score(item: dict) -> tuple:
        name = str(item.get("channelName", ""))
        return (*lookup_score(keyword, name), -len(name))

    candidates.sort(key=_score, reverse=True)
    return candidates[:limit]
