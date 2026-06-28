"""
物流档案模块

API: erp.logistic.get（已确认订阅 2026-04-04）

数据结构（实测）：
- logisticCode: 物流编号（如 YR100）
- logisticName: 物流名称（如 申通LAZADA）
- acronyms: 缩写
- expressCode / expressName: 快递鸟编码/名称
- warehouseId: 逗号分隔的仓库ID列表（该物流可用的仓库）
- warehouseInfo: 逗号分隔的仓库名称列表
- isBlockup: 0=正常, 1=停用
- linkMan / linkTel: 联系人/电话
- interfaceId / interfaceName: 对接接口
"""
import logging
from typing import Optional

from jackyun_api import get_client
from helpers.constants import METHOD_LOGISTIC_GET
from helpers.local_store import get_cached_master_data, get_master_data

logger = logging.getLogger(__name__)

LOGISTICS_FULL_CACHE_MIN_COUNT = 50


def query_logistics(
    name: str = None,
    code: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    """
    查询物流档案

    :param name: 物流名称（模糊搜索）
    :param code: 物流编号
    :return: 物流列表
    """
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if name:
        bizcontent["logisticName"] = name
    if code:
        bizcontent["logisticCode"] = code

    result = client.call(METHOD_LOGISTIC_GET, bizcontent)
    data = result.get("result", {}).get("data", {})
    return data.get("logisticInfo", [])


def query_all_logistics() -> list:
    """查询所有物流档案（自动分页）"""
    cached = get_cached_master_data("logistics")
    if len(cached) >= LOGISTICS_FULL_CACHE_MIN_COUNT:
        return cached
    all_items = []
    page_index = 0
    page_size = 50
    while True:
        items = query_logistics(page_index=page_index, page_size=page_size)
        if not items:
            break
        all_items.extend(items)
        if len(items) < page_size:
            break
        page_index += 1
    from helpers.local_store import save_cached_master_data

    return save_cached_master_data("logistics", all_items) if all_items else all_items


def get_logistics_for_warehouse(warehouse_id: str) -> list:
    """
    获取指定仓库可用的物流列表

    物流档案的 warehouseId 字段是逗号分隔的仓库ID列表，
    遍历所有物流找出包含该仓库ID的记录。

    :param warehouse_id: 仓库ID
    :return: 可用物流列表 [{"logisticCode": "...", "logisticName": "...", ...}]
    """
    all_logistics = query_all_logistics()
    matched = []
    for lg in all_logistics:
        if lg.get("isBlockup") == 1:
            continue
        wh_ids = str(lg.get("warehouseId", "") or "")
        if warehouse_id in wh_ids.split(","):
            matched.append(lg)
    return matched


def get_default_logistics_for_warehouse(warehouse_id: str) -> Optional[dict]:
    """
    获取仓库的默认物流（第一个可用的）

    :param warehouse_id: 仓库ID
    :return: 物流信息或 None
    """
    available = get_logistics_for_warehouse(warehouse_id)
    return available[0] if available else None


def get_logistics_by_name(name: str) -> Optional[dict]:
    """按名称精确查找物流"""
    items = get_master_data(
        "logistics",
        lambda: query_logistics(name=name, page_size=20),
        lambda item: str(item.get("logisticName") or "") == str(name),
        save_fresh=False,
    )
    for item in items:
        if item.get("logisticName") == name:
            return item
    return items[0] if items else None
