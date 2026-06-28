from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from dotenv import load_dotenv
from src.a2a_ecommerce_demo.connector_registry import PROJECT_ROOT
from src.a2a_ecommerce_demo.connector_tools import preview_erp_connector_sync, sync_connector_dataset
from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event

CONNECTOR_ID = "wecom_smartsheet"
DEFAULT_DATASET = "smart_records"
CHANNEL_DAILY_SALES_DATASET = "channel_daily_sales"
MAX_QUERY_LIMIT = 2000
MAX_SYNC_LIMIT = 5000
DEFAULT_SOURCE_CONFIG_PATH = PROJECT_ROOT / "config" / "wecom_smartsheet_sources.json"
MCP_URL_ENV_NAMES = (
    "WECOM_SMARTSHEET_MCP_URL",
    "WEWORK_SMARTSHEET_MCP_URL",
    "WEDOC_MCP_URL",
    "WEWORK_WEDOC_MCP_URL",
)

CHANNEL_DAILY_SALES_SCHEMA = {
    "f36FQs": "年月",
    "fw7LDe": "范围",
    "feptYR": "月目标（万）",
    "fGxWct": "渠道编码",
    "fruYTq": "1日",
    "fGLszy": "2日",
    "fbS0QE": "3日",
    "fTIa9W": "4日",
    "fIGkaM": "5日",
    "fEgBWt": "6日",
    "fqUJX1": "7日",
    "fo2SwQ": "8日",
    "fltogT": "9日",
    "fl0OI7": "10日",
    "fszh6G": "11日",
    "fqsbAc": "12日",
    "fEsCjt": "13日",
    "fyTFlw": "14日",
    "fPvzlN": "15日",
    "fRAaTY": "16日",
    "ftcnQ1": "17日",
    "fU74r3": "18日",
    "fUZkY4": "19日",
    "f77K21": "20日",
    "fcXurq": "21日",
    "fIycPk": "22日",
    "fVhXov": "23日",
    "fRjdML": "24日",
    "f7VaUg": "25日",
    "fDAkpB": "26日",
    "fohNih": "27日",
    "f0V2K0": "28日",
    "fSlqT1": "29日",
    "fe8AgT": "30日",
    "fjFa9P": "31日",
    "f8DdYJ": "月最后一天",
}


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _load_env() -> None:
    env_path = Path(os.getenv("A2A_ENV_PATH", PROJECT_ROOT / ".env")).expanduser()
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


def _no_proxy_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _safe_limit(limit: int | str | None, *, maximum: int) -> int:
    try:
        value = int(limit or 100)
    except (TypeError, ValueError):
        value = 100
    return max(1, min(value, maximum))


def _safe_offset(offset: int | str | None) -> int:
    try:
        value = int(offset or 0)
    except (TypeError, ValueError):
        value = 0
    return max(0, value)


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _parse_sheet_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[,;\s]+", value)
    elif isinstance(value, list | tuple):
        raw_items = [str(item.get("sheet_id", item.get("id", ""))) if isinstance(item, dict) else str(item) for item in value]
    else:
        raw_items = []
    sheet_ids = []
    seen: set[str] = set()
    for item in raw_items:
        sheet_id = str(item).strip()
        if not sheet_id or sheet_id in seen:
            continue
        seen.add(sheet_id)
        sheet_ids.append(sheet_id)
    return sheet_ids


def _display_value(value: Any) -> Any:
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("title") or item.get("name") or json.dumps(item, ensure_ascii=False)))
            else:
                parts.append(str(item))
        return ",".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "title", "name"):
            if key in value:
                return value[key]
        return json.dumps(value, ensure_ascii=False)
    return value


def _docid_from_url(doc_url: str) -> str:
    path = urlparse(doc_url or "").path.strip("/")
    return path.split("/")[-1] if path else ""


def _sheet_id_from_url(doc_url: str) -> str:
    query = parse_qs(urlparse(doc_url or "").query)
    return (query.get("tab") or [""])[0]


def _doc_url_from_docid(docid: str, sheet_id: str = "") -> str:
    clean_docid = str(docid or "").strip()
    if not clean_docid:
        return ""
    query = urlencode({"tab": sheet_id}) if sheet_id else ""
    return urlunparse(("https", "doc.weixin.qq.com", f"/smartsheet/{clean_docid}", "", query, ""))


def _validate_smartsheet_doc_url(doc_url: str) -> None:
    parsed = urlparse(doc_url or "")
    if parsed.scheme != "https" or parsed.netloc.lower() != "doc.weixin.qq.com":
        raise PermissionError("企业微信智能表 URL 必须使用 https://doc.weixin.qq.com。")
    if not parsed.path.strip("/").startswith("smartsheet/"):
        raise PermissionError("企业微信智能表 URL 路径必须位于 /smartsheet/ 下。")


def _source_config_path() -> Path:
    configured = os.getenv("A2A_WECOM_SMARTSHEET_SOURCE_CONFIG", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_SOURCE_CONFIG_PATH


def _load_source_configs() -> dict[str, dict[str, Any]]:
    path = _source_config_path()
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_sources = payload.get("sources", payload) if isinstance(payload, dict) else payload
    if isinstance(raw_sources, dict):
        iterable = raw_sources.values()
    elif isinstance(raw_sources, list):
        iterable = raw_sources
    else:
        return {}
    sources: dict[str, dict[str, Any]] = {}
    for source in iterable:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id") or source.get("id") or "").strip()
        if source_id:
            sources[source_id] = dict(source)
    return sources


def _env_source() -> dict[str, Any]:
    return {
        "source_id": _first_env("WECOM_SMARTSHEET_SOURCE_ID", "WEWORK_SMARTSHEET_SOURCE_ID") or "env_default",
        "name": _first_env("WECOM_SMARTSHEET_NAME", "WEWORK_SMARTSHEET_NAME") or "企业微信智能表默认源",
        "dataset": _first_env("WECOM_SMARTSHEET_DATASET", "WEWORK_SMARTSHEET_DATASET") or DEFAULT_DATASET,
        "doc_url": _first_env("WECOM_SMARTSHEET_URL", "WEWORK_SMARTSHEET_URL"),
        "docid": _first_env("WECOM_SMARTSHEET_DOCID", "WEWORK_SMARTSHEET_DOCID"),
        "sheet_id": _first_env("WECOM_SMARTSHEET_SHEET_ID", "WEWORK_SMARTSHEET_SHEET_ID"),
        "sheet_ids": _parse_sheet_ids(_first_env("WECOM_SMARTSHEET_SHEET_IDS", "WEWORK_SMARTSHEET_SHEET_IDS")),
        "mcp_url": _first_env(*MCP_URL_ENV_NAMES),
    }


def _apply_indirect_env(source: dict[str, Any]) -> dict[str, Any]:
    source = dict(source)
    for value_key, env_key in [
        ("mcp_url", "mcp_url_env"),
        ("doc_url", "doc_url_env"),
        ("docid", "docid_env"),
        ("sheet_id", "sheet_id_env"),
        ("sheet_ids", "sheet_ids_env"),
    ]:
        current_value = source.get(value_key, "")
        has_value = bool(_parse_sheet_ids(current_value)) if value_key == "sheet_ids" else bool(str(current_value).strip())
        if not has_value and source.get(env_key):
            value = os.getenv(str(source[env_key]), "").strip()
            source[value_key] = _parse_sheet_ids(value) if value_key == "sheet_ids" else value
    return source


def _finalize_source(source: dict[str, Any], *, source_id: str = "") -> dict[str, Any]:
    source = dict(source)
    source["sheet_ids"] = _parse_sheet_ids(source.get("sheet_ids", []))
    doc_url = str(source.get("doc_url", "")).strip()
    source["docid"] = str(source.get("docid") or _docid_from_url(doc_url)).strip()
    source["sheet_id"] = str(
        source.get("sheet_id")
        or _sheet_id_from_url(doc_url)
        or (source["sheet_ids"][0] if source["sheet_ids"] else "")
    ).strip()
    if not doc_url and source["docid"]:
        doc_url = _doc_url_from_docid(str(source["docid"]), str(source["sheet_id"]))
        source["doc_url"] = doc_url
    source["dataset"] = str(source.get("dataset") or DEFAULT_DATASET).strip()
    source["source_id"] = str(source.get("source_id") or source_id or "env_default").strip()
    return source


def _resolve_source(
    *,
    source_id: str = "",
    doc_url: str = "",
    docid: str = "",
    sheet_id: str = "",
    dataset: str = "",
) -> dict[str, Any]:
    sources = _load_source_configs()
    source = dict(sources.get(source_id, {})) if source_id else {}
    env_source = _env_source()
    if not source:
        source = env_source
    else:
        source = {**env_source, **source}
    source = _finalize_source(_apply_indirect_env(source), source_id=source_id)
    configured_docid = str(source.get("docid") or "").strip()
    if doc_url:
        _validate_smartsheet_doc_url(doc_url)
        requested_docid = _docid_from_url(doc_url)
        if not configured_docid or requested_docid != configured_docid:
            raise PermissionError("运行时 doc_url 必须匹配已登记的企业微信智能表 source。")
        source["doc_url"] = doc_url
    if docid:
        if not configured_docid or docid != configured_docid:
            raise PermissionError("运行时 docid 必须匹配已登记的企业微信智能表 source。")
        source["docid"] = docid
    if sheet_id:
        source["sheet_id"] = sheet_id
    if dataset:
        source["dataset"] = dataset
    return _finalize_source(source, source_id=source_id)


def _sheet_ids_for_query(source: dict[str, Any]) -> list[str]:
    sheet_ids = _parse_sheet_ids(source.get("sheet_ids", []))
    sheet_id = str(source.get("sheet_id", "")).strip()
    if sheet_id and sheet_id not in sheet_ids:
        sheet_ids.insert(0, sheet_id)
    return sheet_ids


def _doc_url_for_sheet(doc_url: str, sheet_id: str) -> str:
    parsed = urlparse(doc_url or "")
    if not parsed.scheme or not parsed.netloc:
        return doc_url
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["tab"] = [sheet_id]
    flat_query = urlencode([(key, item) for key, values in query.items() for item in values])
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", flat_query, parsed.fragment))


def _schema_for(source: dict[str, Any]) -> dict[str, str]:
    schema = source.get("schema")
    if isinstance(schema, dict):
        return {str(key): str(value) for key, value in schema.items()}
    if source.get("dataset") == CHANNEL_DAILY_SALES_DATASET:
        return CHANNEL_DAILY_SALES_SCHEMA
    return {}


def _redact_url(url: str) -> str:
    parsed = urlparse(url or "")
    if not parsed.scheme or not parsed.netloc:
        return ""
    query = "..." if parsed.query else ""
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, ""))


def _redact_error_text(value: Any) -> str:
    text = str(value or "")[:800]
    patterns = [
        r"(?i)(access_token=)[^&\s]+",
        r"(?i)(apikey=)[^&\s]+",
        r"(?i)(corpsecret['\"=:\s]+)[^,'\"\s]+",
        r"(?i)(secret['\"=:\s]+)[^,'\"\s]+",
        r"(?i)(token['\"=:\s]+)[^,'\"\s]+",
        r"(?i)(key=)[^&\s]+",
        r"(?i)(scode=)[^&\s]+",
    ]
    for pattern in patterns:
        text = re.sub(pattern, r"\1***REDACTED***", text)
    return text


def _extract_records(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(response_data.get("records"), list):
        return response_data.get("records", [])
    data = response_data.get("data") or {}
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return data.get("records", [])
    get_records_data = data.get("getRecords") if isinstance(data, dict) else {}
    if isinstance(get_records_data, dict) and isinstance(get_records_data.get("records"), list):
        return get_records_data.get("records", [])
    return []


def _flatten_record(record: dict[str, Any], schema: dict[str, str], source: dict[str, Any]) -> dict[str, Any]:
    values = record.get("values") or record.get("fields") or {}
    row: dict[str, Any] = {
        "record_id": record.get("record_id") or record.get("recordID") or record.get("id") or "",
        "_source_docid": source.get("docid", ""),
        "_source_sheet_id": source.get("sheet_id", ""),
    }
    if isinstance(values, dict):
        for key, value in values.items():
            label = schema.get(str(key), str(key))
            row[label] = _display_value(value)
    return row


def _mcp_post(session: requests.Session, mcp_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = session.post(
        mcp_url,
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json() if response.text.strip() else {}


def _init_mcp_session(mcp_url: str) -> requests.Session:
    session = _no_proxy_session()
    _mcp_post(
        session,
        mcp_url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "a2a-wecom-smartsheet", "version": "1.0.0"},
            },
        },
    )
    _mcp_post(session, mcp_url, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    return session


def _mcp_text_result(result: dict[str, Any]) -> dict[str, Any]:
    if "error" in result:
        raise RuntimeError(f"MCP 查询失败：{json.dumps(result['error'], ensure_ascii=False)}")
    content = (result.get("result") or {}).get("content") or []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            return json.loads(str(item.get("text") or "{}"))
    raise RuntimeError(f"MCP 返回中没有文本数据：{json.dumps(result, ensure_ascii=False)}")


def _query_records_by_mcp(source: dict[str, Any]) -> dict[str, Any]:
    mcp_url = str(source.get("mcp_url", "")).strip()
    doc_url = str(source.get("doc_url", "")).strip()
    sheet_id = str(source.get("sheet_id", "")).strip()
    if not mcp_url:
        raise ValueError(
            "缺少 WECOM_SMARTSHEET_MCP_URL 或 source.mcp_url。"
            f"请在 {PROJECT_ROOT / '.env'} 配置 WeDoc MCP 服务地址，"
            f"或在 {_source_config_path()} 的 source.mcp_url/source.mcp_url_env 配置。"
            f"可识别的 MCP URL 环境变量：{', '.join(MCP_URL_ENV_NAMES)}。"
        )
    if not doc_url:
        raise ValueError("MCP 查询需要 WECOM_SMARTSHEET_URL 或 source.doc_url。")
    if not sheet_id:
        raise ValueError("缺少 sheet_id；可在文档 URL tab 参数或 WECOM_SMARTSHEET_SHEET_ID 中配置。")
    session = _init_mcp_session(mcp_url)
    result = _mcp_post(
        session,
        mcp_url,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "smartsheet_get_records", "arguments": {"url": doc_url, "sheet_id": sheet_id}},
        },
    )
    return _mcp_text_result(result)


def _fetch_smartsheet_rows(source: dict[str, Any], *, offset: int, limit: int) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    raw = _query_records_by_mcp(source)
    records = _extract_records(raw)
    page = records[offset : offset + limit]
    return "wecom_wedoc_mcp", page, {"raw_total_count": len(records), "page_count": len(page)}


def _record_wecom_audit(result: dict[str, Any], *, event_name: str, requested_by: str) -> None:
    try:
        record_audit_event(
            event_name,
            summary=f"WeCom smartsheet {result.get('status', 'unknown')}: {result.get('source_id', '')}/{result.get('dataset', '')}",
            actor=requested_by,
            tool_name="query_wecom_smartsheet_records",
            data_sources=["WeCom_smartsheet"],
            metadata={
                "connector_id": CONNECTOR_ID,
                "source_id": result.get("source_id", ""),
                "dataset": result.get("dataset", ""),
                "row_count": result.get("row_count", 0),
                "read_only": True,
                "transport": result.get("transport", ""),
            },
        )
    except Exception:
        return


def list_wecom_smartsheet_sources() -> str:
    """列出可用的企业微信智能表数据源配置，不返回 MCP apikey、scode 或 secret。"""
    _load_env()
    configs = _load_source_configs()
    env_source = _env_source()
    sources = list(configs.values())
    if env_source.get("doc_url") or env_source.get("docid") or env_source.get("sheet_id"):
        sources.append(env_source)
    if env_source.get("sheet_ids") and env_source not in sources:
        sources.append(env_source)
    resolved_sources = [_finalize_source(_apply_indirect_env(source)) for source in sources]
    return _json(
        {
            "connector_id": CONNECTOR_ID,
            "display_name": "企业微信智能表",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "source_config_path": str(_source_config_path()),
            "configured_source_count": len(resolved_sources),
            "sources": [
                {
                    "source_id": source.get("source_id") or source.get("id") or "",
                    "name": source.get("name", ""),
                    "dataset": source.get("dataset", DEFAULT_DATASET),
                    "docid_configured": bool(source.get("docid") or _docid_from_url(str(source.get("doc_url", "")))),
                    "sheet_id": source.get("sheet_id") or _sheet_id_from_url(str(source.get("doc_url", ""))),
                    "sheet_ids": _parse_sheet_ids(source.get("sheet_ids", []))
                    or _parse_sheet_ids(os.getenv(str(source.get("sheet_ids_env", "")), "")),
                    "mcp_configured": bool(
                        source.get("mcp_url")
                        or os.getenv(str(source.get("mcp_url_env", "")), "")
                        or _first_env(*MCP_URL_ENV_NAMES)
                    ),
                    "doc_url": _redact_url(str(source.get("doc_url", ""))),
                }
                for source in resolved_sources
            ],
            "env": {
                "WECOM_SMARTSHEET_MCP_URL": bool(_first_env(*MCP_URL_ENV_NAMES)),
                "WECOM_SMARTSHEET_URL": bool(_first_env("WECOM_SMARTSHEET_URL", "WEWORK_SMARTSHEET_URL")),
                "WECOM_SMARTSHEET_DOCID": bool(_first_env("WECOM_SMARTSHEET_DOCID", "WEWORK_SMARTSHEET_DOCID")),
                "WECOM_SMARTSHEET_SHEET_ID": bool(_first_env("WECOM_SMARTSHEET_SHEET_ID", "WEWORK_SMARTSHEET_SHEET_ID")),
                "WECOM_SMARTSHEET_SHEET_IDS": bool(_first_env("WECOM_SMARTSHEET_SHEET_IDS", "WEWORK_SMARTSHEET_SHEET_IDS")),
            },
            "accepted_mcp_url_env_names": list(MCP_URL_ENV_NAMES),
        }
    )


def query_wecom_smartsheet_records(
    source_id: str = "",
    doc_url: str = "",
    docid: str = "",
    sheet_id: str = "",
    sheet_ids: str = "",
    dataset: str = "",
    limit: int = 100,
    offset: int = 0,
    requested_by: str = "agent",
) -> str:
    """通过 WeDoc MCP 读取企业微信智能表记录。

    本工具只读，不调用 webhook，不新增、修改或删除智能表记录。
    """
    _load_env()
    capped_limit = _safe_limit(limit, maximum=MAX_QUERY_LIMIT)
    safe_offset = _safe_offset(offset)
    try:
        source = _resolve_source(
            source_id=source_id,
            doc_url=doc_url,
            docid=docid,
            sheet_id=sheet_id,
            dataset=dataset,
        )
        if sheet_ids:
            source["sheet_ids"] = _parse_sheet_ids(sheet_ids)
        schema = _schema_for(source)
        target_sheet_ids = _sheet_ids_for_query(source)
        if not target_sheet_ids:
            target_sheet_ids = [""]
        rows: list[dict[str, Any]] = []
        sheet_summaries = []
        transports: list[str] = []
        raw_total_count = 0
        for target_sheet_id in target_sheet_ids:
            sheet_source = dict(source)
            if target_sheet_id:
                sheet_source["sheet_id"] = target_sheet_id
                sheet_source["doc_url"] = _doc_url_for_sheet(str(source.get("doc_url", "")), target_sheet_id)
            transport, raw_records, page = _fetch_smartsheet_rows(sheet_source, offset=safe_offset, limit=capped_limit)
            transports.append(transport)
            raw_total_count += int(page.get("raw_total_count", len(raw_records)) or 0)
            sheet_rows = [_flatten_record(record, schema, sheet_source) for record in raw_records]
            rows.extend(sheet_rows)
            sheet_summaries.append(
                {
                    "sheet_id": sheet_source.get("sheet_id", ""),
                    "row_count": len(sheet_rows),
                    "raw_total_count": page.get("raw_total_count", len(raw_records)),
                }
            )
        transport = transports[0] if transports and len(set(transports)) == 1 else ",".join(sorted(set(transports)))
        result = {
            "status": "success",
            "mode": "live_read_only_mcp",
            "connector_id": CONNECTOR_ID,
            "display_name": "企业微信智能表",
            "source_id": source.get("source_id", ""),
            "source_name": source.get("name", ""),
            "dataset": source.get("dataset", DEFAULT_DATASET),
            "transport": transport,
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "query": {
                "docid_configured": bool(source.get("docid")),
                "sheet_id": source.get("sheet_id", ""),
                "sheet_ids": target_sheet_ids,
                "offset": safe_offset,
                "limit": capped_limit,
                "doc_url": _redact_url(str(source.get("doc_url", ""))),
            },
            "schema_columns": list(schema.values()) if schema else [],
            "sheet_count": len(target_sheet_ids),
            "sheets": sheet_summaries,
            "row_count": len(rows),
            "raw_total_count": raw_total_count or len(rows),
            "queried_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rows": rows,
        }
        _record_wecom_audit(result, event_name="wecom_smartsheet_read", requested_by=requested_by)
        return _json(result)
    except Exception as exc:
        result = {
            "status": "error",
            "mode": "live_read_only_mcp",
            "connector_id": CONNECTOR_ID,
            "dataset": dataset or DEFAULT_DATASET,
            "transport": "",
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "error_type": type(exc).__name__,
            "error": _redact_error_text(exc),
        }
        _record_wecom_audit(result, event_name="wecom_smartsheet_read_failed", requested_by=requested_by)
        return _json(result)


def test_wecom_smartsheet_connection(source_id: str = "") -> str:
    """对企业微信智能表做最小只读连通性检查，只返回状态和行数，不返回密钥。"""
    payload = json.loads(query_wecom_smartsheet_records(source_id=source_id, limit=1))
    return _json(
        {
            "connector_id": CONNECTOR_ID,
            "source_id": source_id or payload.get("source_id", ""),
            "ok": payload.get("status") == "success",
            "status": payload.get("status"),
            "read_only": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "transport": payload.get("transport", ""),
            "row_count": payload.get("row_count", 0),
            "error_type": payload.get("error_type", ""),
            "error": payload.get("error", ""),
        }
    )


def sync_wecom_smartsheet_snapshot(
    source_id: str = "",
    dataset: str = "",
    limit: int = 1000,
    dry_run: bool = True,
    requested_by: str = "agent",
) -> str:
    """把企业微信智能表只读快照写入 staging，并注册到 DuckDB fact layer。"""
    _load_env()
    source = _resolve_source(source_id=source_id, dataset=dataset)
    target_dataset = str(dataset or source.get("dataset") or DEFAULT_DATASET)
    if dry_run:
        preview = json.loads(preview_erp_connector_sync(CONNECTOR_ID, target_dataset))
        preview["source_id"] = source.get("source_id", "")
        preview["docid_configured"] = bool(source.get("docid"))
        preview["sheet_id"] = source.get("sheet_id", "")
        preview["mcp_configured"] = bool(source.get("mcp_url"))
        return _json(preview)

    capped_limit = _safe_limit(limit, maximum=MAX_SYNC_LIMIT)
    payload = json.loads(
        query_wecom_smartsheet_records(
            source_id=source_id,
            dataset=target_dataset,
            limit=capped_limit,
            requested_by=requested_by,
        )
    )
    if payload.get("status") != "success":
        return _json({**payload, "sync_status": "skipped"})
    rows = payload.get("rows", [])
    result = json.loads(
        sync_connector_dataset(
            CONNECTOR_ID,
            target_dataset,
            rows_json=json.dumps(rows, ensure_ascii=False),
            dry_run=False,
        )
    )
    result["source_id"] = payload.get("source_id", source.get("source_id", ""))
    result["transport"] = payload.get("transport", "")
    result["read_only"] = True
    result["external_write_enabled"] = False
    result["permission_scope"] = "read_only"
    _record_wecom_audit(result, event_name="wecom_smartsheet_snapshot_synced", requested_by=requested_by)
    return _json(result)
