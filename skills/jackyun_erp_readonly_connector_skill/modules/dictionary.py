"""
Data dictionary helpers.

Official methods:
- erp.dictionary.page: query dictionary values
- erp.dictionary.save: create dictionary value
"""
from __future__ import annotations

from jackyun_api import JackyunValidationError, get_client
from helpers.constants import METHOD_DICTIONARY_PAGE, METHOD_DICTIONARY_SAVE
from helpers.local_store import get_master_data, save_cached_master_data


def _extract_dictionary_items(result: dict) -> list[dict]:
    data = result.get("result", {}).get("data", {}) if isinstance(result, dict) else {}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "records", "rows", "list", "data"):
            items = data.get(key)
            if isinstance(items, list):
                return items
            if isinstance(items, dict):
                return [items]
        if any(key in data for key in ("value", "text", "orderIndex")):
            return [data]
    return []


def query_dictionary(dict_value: str, page_index: int = 0, page_size: int = 50, use_cache: bool = True) -> list[dict]:
    if not str(dict_value or "").strip():
        raise JackyunValidationError("查询数据字典必须提供 dictValue")

    cache_name = f"dictionary_{dict_value}"

    def fetch():
        client = get_client()
        result = client.call(
            METHOD_DICTIONARY_PAGE,
            {"dictValue": dict_value, "pageIndex": page_index, "pageSize": page_size},
        )
        return _extract_dictionary_items(result)

    if use_cache:
        return get_master_data(cache_name, fetch)

    items = fetch()
    if items:
        save_cached_master_data(cache_name, items)
    return items


def find_dictionary_item(dict_value: str, text: str, use_cache: bool = True) -> dict | None:
    target = str(text or "").strip()
    if not target:
        return None
    for item in query_dictionary(dict_value, use_cache=use_cache):
        if str(item.get("text") or "").strip() == target:
            return item
    return None


def add_dictionary_item(
    dict_value: str,
    text: str,
    value: str | None = None,
    order_index: int | None = None,
) -> dict:
    if not str(dict_value or "").strip() or not str(text or "").strip():
        raise JackyunValidationError("新增数据字典必须提供 dictValue 和 text")

    current_items = query_dictionary(dict_value, use_cache=False)
    existing = [
        item for item in current_items
        if str(item.get("text") or "").strip() == str(text).strip()
    ]
    if existing:
        return {"status": "exists", "item": existing[0]}

    if value is None:
        numeric_values = []
        for item in current_items:
            raw = str(item.get("value") or "")
            if raw.isdigit():
                numeric_values.append(int(raw))
        next_value = max(numeric_values or [0]) + 1
        value = f"{next_value:04d}"

    payload = {"dictValue": dict_value, "value": str(value), "text": str(text)}
    if order_index is not None:
        payload["orderIndex"] = order_index
    elif current_items:
        payload["orderIndex"] = max(int(item.get("orderIndex") or 0) for item in current_items) + 1

    client = get_client()
    result = client.call(METHOD_DICTIONARY_SAVE, payload)
    save_cached_master_data(f"dictionary_{dict_value}", current_items + [payload])
    return {"status": "created", "item": payload, "raw": result}


def ensure_dictionary_item(dict_value: str, text: str, auto_create: bool = False) -> dict:
    item = find_dictionary_item(dict_value, text, use_cache=True)
    if item:
        return {"status": "exists", "item": item}
    item = find_dictionary_item(dict_value, text, use_cache=False)
    if item:
        return {"status": "exists", "item": item}
    if not auto_create:
        raise JackyunValidationError(
            f"数据字典「{dict_value}」中没有「{text}」。如确认要新增，请开启 auto_create_dictionary=True 后再执行。"
        )
    return add_dictionary_item(dict_value, text)
