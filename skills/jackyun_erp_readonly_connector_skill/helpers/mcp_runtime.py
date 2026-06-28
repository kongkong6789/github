"""
JackYun MCP tool registry and best-effort HTTP MCP caller.

The official MCP service is a remote HTTP MCP server. This module only attempts
MCP calls when a token is configured and the method appears in the official MCP
tool list bundled under docs/jackyun_mcp_tools.json.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import requests

import config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_TOOL_LIST_PATH = PROJECT_ROOT / "docs" / "jackyun_mcp_tools.json"


class JackyunMCPUnavailable(Exception):
    pass


def load_mcp_tools() -> list[dict[str, Any]]:
    if not MCP_TOOL_LIST_PATH.exists():
        return []
    payload = json.loads(MCP_TOOL_LIST_PATH.read_text(encoding="utf-8-sig"))
    data = payload.get("result", {}).get("data", [])
    return data if isinstance(data, list) else []


def get_tool_for_method(method: str) -> dict[str, Any] | None:
    for item in load_mcp_tools():
        if item.get("enabled") == 1 and item.get("methodName") == method:
            return item
    return None


def supports_method(method: str) -> bool:
    return get_tool_for_method(method) is not None


def call_mcp_tool(method: str, arguments: dict[str, Any]) -> dict[str, Any]:
    token = config.JACKYUN_MCP_TOKEN
    if not token:
        raise JackyunMCPUnavailable("JACKYUN_MCP_TOKEN is not configured")

    tool = get_tool_for_method(method)
    if not tool:
        raise JackyunMCPUnavailable(f"method is not in official MCP tool list: {method}")

    tool_name = tool.get("toolName")
    if not tool_name:
        raise JackyunMCPUnavailable(f"MCP toolName is empty for method: {method}")

    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {},
        },
    }
    resp = requests.post(
        config.JACKYUN_MCP_URL,
        headers=headers,
        json=payload,
        timeout=config.JACKYUN_MCP_TIMEOUT,
    )
    resp.raise_for_status()
    return _decode_mcp_response(resp.text)


def _decode_mcp_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise JackyunMCPUnavailable("empty MCP response")

    if stripped.startswith("data:"):
        chunks = []
        for line in stripped.splitlines():
            if line.startswith("data:"):
                value = line[5:].strip()
                if value and value != "[DONE]":
                    chunks.append(value)
        stripped = chunks[-1] if chunks else ""

    payload = json.loads(stripped)
    if "error" in payload:
        raise JackyunMCPUnavailable(str(payload["error"]))

    result = payload.get("result", payload)
    if isinstance(result, dict) and "content" in result:
        return _decode_tool_content(result)
    if isinstance(payload, dict) and "content" in payload:
        return _decode_tool_content(payload)
    return result if isinstance(result, dict) else {"result": result}


def _decode_tool_content(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content") or []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "json" and isinstance(item.get("json"), dict):
            return _normalize_tool_payload(item["json"])
        if item.get("type") == "text":
            text = str(item.get("text") or "").strip()
            if text:
                return _normalize_tool_payload(json.loads(text))
    return {"result": result}


def _normalize_tool_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and "content" in payload:
        return _decode_tool_content(payload)
    if isinstance(payload, dict) and ("code" in payload or "result" in payload):
        return payload
    if isinstance(payload, dict):
        return {"code": "200", "result": {"data": payload}}
    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], dict):
            return {"code": "200", "result": {"data": payload[0]}}
        return {"code": "200", "result": {"data": payload}}
    return {"code": "200", "result": {"data": payload}}
