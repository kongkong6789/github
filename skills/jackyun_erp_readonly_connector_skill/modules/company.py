"""
公司档案模块

API: erp.company.query
"""
from typing import Optional

from jackyun_api import get_client
from helpers.constants import METHOD_COMPANY_QUERY
from helpers.local_store import get_master_data


def _extract_company_items(data) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("companyInfo", "data", "records", "rows", "list"):
        items = data.get(key)
        if isinstance(items, list):
            return items
        if isinstance(items, dict) and items:
            return [items]
    return [data] if data else []


def query_companies(
    company_code: str = None,
    company_name: str = None,
    company_codes: str = None,
    page_index: int = 0,
    page_size: int = 20,
) -> list:
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": str(page_size),
    }
    if company_code:
        bizcontent["companyCode"] = company_code
    if company_name:
        bizcontent["companyName"] = company_name
    if company_codes:
        bizcontent["companyCodes"] = company_codes

    result = client.call(METHOD_COMPANY_QUERY, bizcontent)
    data = result.get("result", {}).get("data", {})
    return _extract_company_items(data)


def resolve_company(company_code: str = None, company_name: str = None) -> Optional[dict]:
    def matcher(item: dict) -> bool:
        if company_code:
            return str(item.get("companyCode") or "") == company_code.replace("$eq$", "")
        if company_name:
            return str(item.get("companyName") or "") == company_name.replace("$eq$", "")
        return True

    def fetch():
        return query_companies(
            company_code=company_code,
            company_name=company_name,
            page_index=0,
            page_size=20,
        )

    items = get_master_data(
        "companies",
        fetch,
        matcher if (company_code or company_name) else None,
        save_fresh=not (company_code or company_name),
    )
    if company_code:
        normalized = company_code.replace("$eq$", "")
        for item in items:
            if str(item.get("companyCode") or "") == normalized:
                return item
    if company_name:
        normalized = company_name.replace("$eq$", "")
        for item in items:
            if str(item.get("companyName") or "") == normalized:
                return item
    return items[0] if items else None


def resolve_company_or_raise(company_code: str = None, company_name: str = None) -> dict:
    from jackyun_api import JackyunValidationError

    company = resolve_company(company_code=company_code, company_name=company_name)
    if not company:
        raise JackyunValidationError(f"未找到公司: {company_code or company_name or ''}")
    return company
