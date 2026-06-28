"""
部门档案模块

API: erp.depart.query
"""
from typing import Optional

from jackyun_api import JackyunValidationError, get_client
from helpers.constants import METHOD_DEPART_QUERY
from helpers.local_store import get_master_data


def _extract_depart_items(data) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("departInfo", "data", "records", "rows", "list"):
        items = data.get(key)
        if isinstance(items, list):
            return items
        if isinstance(items, dict) and items:
            return [items]
    return [data] if data else []


def query_departments(
    depart_id: str = None,
    depart_code: str = None,
    depart_name: str = None,
    depart_ids: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if depart_id is not None:
        bizcontent["departId"] = str(depart_id)
    if depart_code:
        bizcontent["departCode"] = depart_code
    if depart_name:
        bizcontent["departName"] = depart_name
    if depart_ids:
        bizcontent["departIds"] = depart_ids

    result = client.call(METHOD_DEPART_QUERY, bizcontent)
    data = result.get("result", {}).get("data", {})
    return _extract_depart_items(data)


def resolve_department(
    depart_code: str = None,
    depart_id: str = None,
    depart_name: str = None,
) -> Optional[dict]:
    def matcher(item: dict) -> bool:
        if depart_code:
            return str(item.get("departCode") or "") == str(depart_code)
        if depart_id is not None:
            return str(item.get("departId") or "") == str(depart_id)
        if depart_name:
            return str(item.get("departName") or "") == str(depart_name)
        return True

    def fetch():
        return query_departments(
            depart_id=depart_id,
            depart_code=depart_code,
            depart_name=depart_name,
            depart_ids=None,
            page_index=0,
            page_size=20,
        )

    items = get_master_data(
        "departments",
        fetch,
        matcher if (depart_code or depart_id or depart_name) else None,
        save_fresh=not (depart_code or depart_id or depart_name),
    )
    if depart_code:
        for item in items:
            if str(item.get("departCode") or "") == str(depart_code):
                return item
    if depart_id is not None:
        for item in items:
            if str(item.get("departId") or "") == str(depart_id):
                return item
    if depart_name:
        for item in items:
            if str(item.get("departName") or "") == str(depart_name):
                return item
    return items[0] if items else None


def resolve_department_or_raise(
    depart_code: str = None,
    depart_id: str = None,
    depart_name: str = None,
) -> dict:
    department = resolve_department(
        depart_code=depart_code,
        depart_id=depart_id,
        depart_name=depart_name,
    )
    if not department:
        hint = depart_code or depart_id or depart_name or ""
        raise JackyunValidationError(f"未找到部门: {hint}")
    return department
