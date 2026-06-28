from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
AUDIT_DIR = Path(os.getenv("A2A_AUDIT_DIR", DATA_DIR / "audit")).resolve()
AUDIT_LOG = AUDIT_DIR / "events.jsonl"

SENSITIVE_PATTERNS = [
    re.compile(r"(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^,'\"\s]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"tp-[A-Za-z0-9_-]{12,}"),
]
SENSITIVE_KEY_MARKERS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}


def _ensure_dir() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized_key = str(key).lower().replace("-", "_")
            if any(marker in normalized_key for marker in SENSITIVE_KEY_MARKERS):
                redacted[key] = "***REDACTED***" if item else item
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if not isinstance(value, str):
        return value
    redacted = value
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(lambda match: match.group(0).split("=", 1)[0] + "=***REDACTED***" if "=" in match.group(0) else "***REDACTED***", redacted)
    return redacted


def record_audit_event(
    event_type: str,
    actor: str = "agent",
    summary: str = "",
    level: str = "info",
    agent_id: str = "",
    thread_id: str = "",
    task_id: str = "",
    tool_name: str = "",
    risk_level: str = "",
    data_sources: list[str] | None = None,
    paths: list[str] | None = None,
    risks: list[str] | None = None,
    status: str = "",
    duration_ms: int | float | None = None,
    error_code: str = "",
    metadata: dict[str, Any] | None = None,
) -> str:
    """记录企业级审计事件。会自动脱敏 token/key/password。"""
    _ensure_dir()
    timestamp = datetime.now().isoformat(timespec="seconds")
    normalized_risks = risks or []
    event = {
        "timestamp": timestamp,
        "created_at": timestamp,
        "level": level or "info",
        "event_type": event_type,
        "actor": actor,
        "agent_id": agent_id,
        "thread_id": thread_id,
        "task_id": task_id,
        "tool_name": tool_name,
        "risk_level": risk_level or (normalized_risks[0] if normalized_risks else ""),
        "data_sources": data_sources or [],
        "paths": paths or [],
        "status": status,
        "duration_ms": duration_ms,
        "error_code": error_code,
        "summary": summary,
        "risks": normalized_risks,
        "metadata": metadata or {},
    }
    event = _redact(event)
    with AUDIT_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
    return json.dumps({"status": "success", "audit_log": str(AUDIT_LOG), "event": event}, ensure_ascii=False, indent=2)


def list_audit_events(limit: int = 50, event_type: str = "") -> str:
    """读取最近审计事件，支持按事件类型过滤。"""
    _ensure_dir()
    if not AUDIT_LOG.exists():
        return json.dumps({"audit_log": str(AUDIT_LOG), "events": []}, ensure_ascii=False, indent=2)
    events = []
    for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event_type and event.get("event_type") != event_type:
            continue
        events.append(event)
    return json.dumps({"audit_log": str(AUDIT_LOG), "events": events[-limit:]}, ensure_ascii=False, indent=2)
