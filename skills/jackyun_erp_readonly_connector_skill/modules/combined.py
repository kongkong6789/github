"""
Combined/assembly-disassembly helpers.
"""
import logging

from jackyun_api import get_client

logger = logging.getLogger(__name__)

METHOD_COMBINED_GET_V2 = "erp.combined.get.v2"
METHOD_COMBINED_CREATE = "erp.combind.create"
METHOD_COMBINED_CREATE_V2 = "erp.combind.create.v2"
METHOD_COMBINED_CLOSE = "erp.combined.close"


def _extract_list(result: dict) -> list:
    data = result.get("result", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        if isinstance(items, list):
            return items
        return [items] if items else []
    if isinstance(data, list):
        return data
    return []


def query_combined(
    goods_no: str = None,
    goods_name: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if goods_no:
        bizcontent["goodsNo"] = goods_no
    if goods_name:
        bizcontent["goodsName"] = goods_name
    return _extract_list(client.call(METHOD_COMBINED_GET_V2, bizcontent))


def query_all_combined() -> list:
    client = get_client()
    return client.call_paged(METHOD_COMBINED_GET_V2, {})


def create_combined(combined_data: dict, use_v2: bool = True) -> dict:
    client = get_client()
    method = METHOD_COMBINED_CREATE_V2 if use_v2 else METHOD_COMBINED_CREATE
    logger.info("Creating combined doc with %s", method)
    return client.call(method, combined_data)


def close_combined(bill_no: str = None, rec_id: str = None, reason: str = "") -> dict:
    client = get_client()
    bizcontent = {"reason": reason}
    if bill_no:
        bizcontent["billNo"] = bill_no
    if rec_id:
        bizcontent["recId"] = rec_id
    logger.info("Closing combined doc: billNo=%s recId=%s", bill_no, rec_id)
    return client.call(METHOD_COMBINED_CLOSE, bizcontent)
