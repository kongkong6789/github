"""
供应商模块

提供供应商查询功能。
"""
import logging
from typing import Optional

from jackyun_api import get_client
from helpers.constants import METHOD_VENDOR_GET

logger = logging.getLogger(__name__)


def query_vendors(
    name: str = None,
    code: str = None,
    page_index: int = 0,
    page_size: int = 50,
    gmt_modified_start: str = None,
    gmt_modified_end: str = None,
) -> list:
    """
    查询供应商

    :param name: 供应商名称
    :param code: 供应商编号
    :return: 供应商列表
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

    result = client.call(METHOD_VENDOR_GET, bizcontent)
    data = result.get("result", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def query_all_vendors() -> list:
    """查询所有供应商（自动分页）"""
    client = get_client()
    return client.call_paged(METHOD_VENDOR_GET, {})


def get_vendor_by_name(name: str) -> Optional[dict]:
    """按供应商名称查询"""
    results = query_vendors(name=name, page_size=10)
    for v in results:
        if v.get("vendorName") == name or v.get("name") == name:
            return v
    return results[0] if results else None
