"""
网店订单模块

提供网店销售订单查询（线上订单）和物流追踪功能。
"""
import logging
from typing import Optional

from jackyun_api import get_client
from helpers.constants import METHOD_SHOP_ORDER_GET

logger = logging.getLogger(__name__)


def query_shop_orders(
    platform_bill_no: str = None,
    trade_status: int = None,
    buyer_nick: str = None,
    gmt_create_start: str = None,
    gmt_create_end: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    """
    查询网店订单

    :param platform_bill_no: 平台订单号
    :param trade_status: 交易状态
    :param buyer_nick: 买家昵称
    :param gmt_create_start: 下单起始时间
    :param gmt_create_end: 下单结束时间
    :return: 订单列表
    """
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if platform_bill_no:
        bizcontent["platformBillNo"] = platform_bill_no
    if trade_status is not None:
        bizcontent["tradeStatus"] = trade_status
    if buyer_nick:
        bizcontent["buyerNick"] = buyer_nick
    if gmt_create_start:
        bizcontent["gmtCreateStart"] = gmt_create_start
    if gmt_create_end:
        bizcontent["gmtCreateEnd"] = gmt_create_end

    result = client.call(METHOD_SHOP_ORDER_GET, bizcontent)
    data = result.get("result", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def query_all_shop_orders(**kwargs) -> list:
    """查询所有网店订单（自动分页）"""
    client = get_client()
    bizcontent = {}
    if kwargs.get("trade_status") is not None:
        bizcontent["tradeStatus"] = kwargs["trade_status"]
    if kwargs.get("gmt_create_start"):
        bizcontent["gmtCreateStart"] = kwargs["gmt_create_start"]
    if kwargs.get("gmt_create_end"):
        bizcontent["gmtCreateEnd"] = kwargs["gmt_create_end"]
    return client.call_paged(METHOD_SHOP_ORDER_GET, bizcontent)


def get_order_logistics(platform_bill_no: str) -> list:
    """
    获取订单的物流信息

    :param platform_bill_no: 平台订单号
    :return: 物流信息列表
    """
    orders = query_shop_orders(platform_bill_no=platform_bill_no, page_size=5)
    logistics = []
    for order in orders:
        logistics_list = order.get("logisticList", []) or []
        for item in logistics_list:
            logistics.append({
                "logisticNo": item.get("logisticNo", ""),
                "logisticName": item.get("logisticName", ""),
                "logisticCode": item.get("logisticCode", ""),
            })
        if not logistics_list:
            if order.get("logisticNo"):
                logistics.append({
                    "logisticNo": order.get("logisticNo", ""),
                    "logisticName": order.get("logisticName", ""),
                    "logisticCode": "",
                })
    return logistics
