"""
用户档案模块

API: erp.user.search

当前用途：
- 在创建调拨单前校验申请人姓名 / ID / 部门是否一致
- 在创建销售单前校验业务员是否为当前确认的创建人本人
"""
from typing import Optional

from jackyun_api import JackyunValidationError, get_client
from helpers.constants import METHOD_USER_SEARCH
from helpers.local_store import (
    get_cached_master_data,
    get_default_operator_name,
    get_master_data,
    save_cached_master_data,
    set_default_operator,
)
from helpers.matching import best_match, normalize_lookup_text

DEFAULT_USER_COLS = ",".join([
    "companyId",
    "companyName",
    "email",
    "isBlockup",
    "mainDepartId",
    "mainDepartName",
    "mobile",
    "realName",
    "userId",
    "userName",
])

USER_FULL_CACHE_MIN_COUNT = 100


def _extract_user_items(data) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("userInfo", "users", "data", "records", "rows", "list"):
        items = data.get(key)
        if isinstance(items, list):
            return items
        if isinstance(items, dict) and items:
            return [items]
    return [data] if data else []


def query_users(
    name: str = None,
    user_id: str = None,
    mobile: str = None,
    cols: str = DEFAULT_USER_COLS,
    page_index: int = 0,
    page_size: int = 50,
    is_include_blockup: int = 1,
) -> list:
    client = get_client()
    bizcontent = {
        "cols": cols,
        "pageIndex": page_index,
        "pageSize": page_size,
        "isIncludeBlockup": is_include_blockup,
    }
    if name:
        bizcontent["realNames"] = name
    if user_id is not None:
        bizcontent["userIds"] = str(user_id)
    if mobile:
        bizcontent["mobile"] = mobile

    result = client.call(METHOD_USER_SEARCH, bizcontent)
    data = result.get("result", {}).get("data", {})
    return _extract_user_items(data)


def query_all_users() -> list:
    all_items = []
    page_index = 0
    page_size = 50
    while True:
        items = query_users(page_index=page_index, page_size=page_size)
        if not items:
            break
        all_items.extend(items)
        if len(items) < page_size:
            break
        page_index += 1
    return all_items


def query_users_cached(name: str = None, user_id: str = None) -> list:
    def matcher(item: dict) -> bool:
        if name and normalize_lookup_text(item.get("realName") or item.get("name") or item.get("userName")) != normalize_lookup_text(name):
            return False
        if user_id is not None and str(item.get("userId") or item.get("id") or "") != str(user_id):
            return False
        return True

    if not name and user_id is None:
        cached = get_cached_master_data("users")
        if len(cached) >= USER_FULL_CACHE_MIN_COUNT:
            return cached
        fresh = query_all_users()
        return save_cached_master_data("users", fresh) if fresh else cached

    def fetch():
        if name or user_id is not None:
            return query_users(name=name, user_id=user_id)
        return query_all_users()

    return get_master_data(
        "users",
        fetch,
        matcher if (name or user_id is not None) else None,
        save_fresh=not (name or user_id is not None),
    )


def resolve_user_identity(
    user_name: str,
    user_id: str = None,
    depart_code: str = None,
) -> dict:
    """
    Resolve a user by confirmed real name, then verify optional ID / department.

    This intentionally requires the caller to provide the confirmed user name first.
    """
    if not str(user_name or "").strip():
        raise JackyunValidationError("请先让用户确认创建人本人姓名，再创建单据")

    candidates = query_users_cached(name=user_name, user_id=user_id)
    exact_matches = [
        item for item in candidates
        if normalize_lookup_text(item.get("realName") or item.get("name") or item.get("userName")) == normalize_lookup_text(user_name)
    ]
    if not exact_matches:
        matched = best_match(user_name, candidates, ("realName", "name", "userName"), min_ratio=0.9)
        exact_matches = [matched] if matched else []
    if not exact_matches:
        raise JackyunValidationError(f"未找到申请人/业务员: {user_name}")

    if user_id is not None:
        exact_matches = [
            item for item in exact_matches
            if str(item.get("userId") or item.get("id") or "") == str(user_id)
        ]
        if not exact_matches:
            raise JackyunValidationError(f"申请人/业务员「{user_name}」与 userId={user_id} 不匹配")

    matched_user = exact_matches[0] if len(exact_matches) == 1 else None
    if depart_code:
        from modules.depart import resolve_department_or_raise

        department = resolve_department_or_raise(depart_code=depart_code)
        exact_matches = [
            item for item in exact_matches
            if (
                str(item.get("mainDepartId") or "") == str(department.get("departId") or "")
                or str(item.get("mainDepartName") or "") == str(department.get("departName") or "")
            )
        ]
        if not exact_matches:
            raise JackyunValidationError(f"申请人/业务员「{user_name}」与部门编码 {depart_code} 不匹配")
        matched_user = exact_matches[0] if len(exact_matches) == 1 else matched_user

    if len(exact_matches) > 1:
        raise JackyunValidationError(
            f"姓名「{user_name}」匹配到多个用户，请补充准确的 userId 或部门后再创建"
        )

    matched_user = exact_matches[0]
    if not depart_code:
        main_depart_id = matched_user.get("mainDepartId")
        main_depart_name = matched_user.get("mainDepartName")
        if main_depart_id or main_depart_name:
            from modules.depart import resolve_department

            department = resolve_department(
                depart_id=main_depart_id,
                depart_name=main_depart_name,
            )
            if department and department.get("departCode"):
                matched_user = dict(matched_user)
                matched_user["departCode"] = department.get("departCode")
    return matched_user


def resolve_default_operator(
    user_name: str = None,
    user_id: str = None,
    depart_code: str = None,
    persist: bool = True,
) -> dict:
    resolved_name = str(user_name or "").strip() or get_default_operator_name()
    if not resolved_name:
        raise JackyunValidationError("首次使用请先提供创建人/申请人姓名，后续会保存在 skill 本地配置中")
    user = resolve_user_identity(resolved_name, user_id=user_id, depart_code=depart_code)
    if persist:
        set_default_operator(resolved_name, user)
    return user
