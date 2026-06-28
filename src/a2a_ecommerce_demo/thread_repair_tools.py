from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from src.a2a_ecommerce_demo.checkpoint_tools import migrate_checkpoint_pickles
from src.a2a_ecommerce_demo.state_io import atomic_write_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
THREAD_ARCHIVE_DIR = Path(os.getenv("A2A_THREAD_ARCHIVE_DIR", DATA_DIR / "thread_archive")).resolve()
LANGGRAPH_API_DIR = Path(os.getenv("A2A_LANGGRAPH_API_DIR", PROJECT_ROOT / ".langgraph_api")).resolve()
BACKUP_ROOT = Path(os.getenv("A2A_THREAD_REPAIR_BACKUP_DIR", DATA_DIR / "thread_archive_backups")).resolve()
SYNTHETIC_TOOL_CONTENT = "Synthetic tool response inserted by offline thread repair."
DEFAULT_MAX_MESSAGES = 80
DEFAULT_MAX_TEXT_LENGTH = 12_000


@dataclass
class RepairStats:
    scanned_files: int = 0
    changed_files: int = 0
    backup_files: int = 0
    messages_before: int = 0
    messages_after: int = 0
    orphan_tool_messages_removed: int = 0
    missing_tool_responses_inserted: int = 0
    overlong_messages_truncated: int = 0
    old_messages_compacted: int = 0
    sensitive_urls_redacted: int = 0
    large_tool_results_compacted: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "scanned_files": self.scanned_files,
            "changed_files": self.changed_files,
            "backup_files": self.backup_files,
            "messages_before": self.messages_before,
            "messages_after": self.messages_after,
            "orphan_tool_messages_removed": self.orphan_tool_messages_removed,
            "missing_tool_responses_inserted": self.missing_tool_responses_inserted,
            "overlong_messages_truncated": self.overlong_messages_truncated,
            "old_messages_compacted": self.old_messages_compacted,
            "sensitive_urls_redacted": self.sensitive_urls_redacted,
            "large_tool_results_compacted": self.large_tool_results_compacted,
        }


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _message_type(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("type") or message.get("role") or "")
    return ""


def _is_ai_message_type(message_type: str) -> bool:
    return message_type in {"ai", "assistant"}


def _tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    value = message.get("tool_calls") or []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _tool_call_id(tool_call: dict[str, Any]) -> str:
    return str(tool_call.get("id") or "")


def _tool_call_name(tool_call: dict[str, Any]) -> str:
    return str(tool_call.get("name") or "")


def _message_tool_call_id(message: dict[str, Any]) -> str:
    return str(message.get("tool_call_id") or "")


_SENSITIVE_QUERY_KEYS = {"scode", "apikey", "access_token", "token", "secret", "key"}
_REDACTED_MARKER = "***REDACTED***"


def _is_redacted_marker(value: str) -> bool:
    return unquote(value).strip().casefold() == _REDACTED_MARKER.casefold()


def _redact_sensitive_url_queries(text: str, stats: RepairStats) -> str:
    def redact_url(match: Any) -> str:
        raw_url = str(match.group(0))
        try:
            parts = urlsplit(raw_url)
        except ValueError:
            return raw_url
        if not parts.query:
            return raw_url
        redacted = False
        pairs: list[tuple[str, str]] = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            key_lower = key.lower()
            if key_lower in _SENSITIVE_QUERY_KEYS or any(marker in key_lower for marker in _SENSITIVE_QUERY_KEYS):
                if _is_redacted_marker(value):
                    pairs.append((key, value))
                else:
                    pairs.append((key, _REDACTED_MARKER))
                    redacted = True
            else:
                pairs.append((key, value))
        if not redacted:
            return raw_url
        stats.sensitive_urls_redacted += 1
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))

    redacted = re.sub(r"https?://[^\s\"'<>]+", redact_url, text)

    def redact_bare_query(match: Any) -> str:
        if _is_redacted_marker(str(match.group(2))):
            return str(match.group(0))
        stats.sensitive_urls_redacted += 1
        return f"{match.group(1)}={_REDACTED_MARKER}"

    return re.sub(
        r"(?i)\b(scode|apikey|access_token|token|secret|key)=([^&\s\"']+)",
        redact_bare_query,
        redacted,
    )


def _redact_nested_values(value: Any, stats: RepairStats) -> Any:
    if isinstance(value, dict):
        return {key: _redact_nested_values(item, stats) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_nested_values(item, stats) for item in value]
    if isinstance(value, str):
        return _redact_sensitive_url_queries(value, stats)
    return value


def _compact_tool_result_payload(payload: Any, stats: RepairStats) -> Any:
    if not isinstance(payload, dict):
        return payload
    row_key = next(
        (
            key
            for key in ("rows", "records", "data")
            if isinstance(payload.get(key), list) and len(payload.get(key) or []) > 0
        ),
        "",
    )
    if not row_key:
        return payload

    keep_keys = {
        "status",
        "mode",
        "transport",
        "source_id",
        "dataset",
        "row_count",
        "raw_total_count",
        "schema",
        "source_sheet_ids",
        "doc_url",
        "mcp_url",
        "warnings",
    }
    compacted = {key: payload[key] for key in keep_keys if key in payload}
    rows = payload.get(row_key)
    compacted["sample_rows"] = rows[:3] if isinstance(rows, list) else []
    compacted["omitted_row_count"] = max(0, len(rows) - len(compacted["sample_rows"])) if isinstance(rows, list) else 0
    compacted["archive_compacted"] = True
    stats.large_tool_results_compacted += 1
    return compacted


def _synthetic_tool_message(tool_call: dict[str, Any], parent_id: str, offset: int) -> dict[str, Any]:
    tool_call_id = _tool_call_id(tool_call)
    return {
        "id": f"offline-repair-{parent_id or 'ai'}-{tool_call_id or offset}",
        "type": "tool",
        "content": SYNTHETIC_TOOL_CONTENT,
        "name": _tool_call_name(tool_call),
        "tool_call_id": tool_call_id,
        "tool_calls": [],
        "invalid_tool_calls": [],
        "metadata": {"source": "offline_thread_repair"},
    }


def _sanitize_content(content: Any, max_text_length: int, stats: RepairStats) -> Any:
    if isinstance(content, str):
        redacted = _redact_sensitive_url_queries(content, stats)
        try:
            parsed = json.loads(redacted)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None:
            compacted = _compact_tool_result_payload(_redact_nested_values(parsed, stats), stats)
            redacted = json.dumps(compacted, ensure_ascii=False, sort_keys=True)
        if len(redacted) <= max_text_length:
            return redacted
        stats.overlong_messages_truncated += 1
        return redacted[:max_text_length] + "\n\n[offline thread repair: truncated long message]"
    if isinstance(content, list):
        truncated: list[Any] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str) and len(item["text"]) > max_text_length:
                next_item = dict(item)
                redacted_text = _redact_sensitive_url_queries(item["text"], stats)
                next_item["text"] = redacted_text[:max_text_length] + "\n\n[offline thread repair: truncated long text block]"
                stats.overlong_messages_truncated += 1
                truncated.append(next_item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                next_item = dict(item)
                next_item["text"] = _redact_sensitive_url_queries(item["text"], stats)
                truncated.append(next_item)
            else:
                truncated.append(item)
        return truncated
    return content


def repair_messages(
    messages: list[Any],
    *,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
) -> tuple[list[dict[str, Any]], RepairStats]:
    stats = RepairStats(messages_before=len(messages))
    repaired: list[dict[str, Any]] = []
    index = 0

    while index < len(messages):
        message = messages[index]
        if not isinstance(message, dict):
            index += 1
            continue

        message_type = _message_type(message)
        if message_type == "tool":
            stats.orphan_tool_messages_removed += 1
            index += 1
            continue

        next_message = dict(message)
        next_message["content"] = _sanitize_content(next_message.get("content"), max_text_length, stats)
        repaired.append(next_message)

        if not _is_ai_message_type(message_type):
            index += 1
            continue

        tool_calls = _tool_calls(message)
        if not tool_calls:
            index += 1
            continue

        expected_ids = [_tool_call_id(tool_call) for tool_call in tool_calls]
        seen_ids: set[str] = set()
        lookahead = index + 1
        while lookahead < len(messages) and isinstance(messages[lookahead], dict) and _message_type(messages[lookahead]) == "tool":
            tool_message = dict(messages[lookahead])
            tool_call_id = _message_tool_call_id(tool_message)
            if tool_call_id in expected_ids and tool_call_id not in seen_ids:
                tool_message["content"] = _sanitize_content(tool_message.get("content"), max_text_length, stats)
                repaired.append(tool_message)
                seen_ids.add(tool_call_id)
            else:
                stats.orphan_tool_messages_removed += 1
            lookahead += 1

        for offset, tool_call in enumerate(tool_calls):
            tool_call_id = _tool_call_id(tool_call)
            if tool_call_id and tool_call_id not in seen_ids:
                repaired.append(_synthetic_tool_message(tool_call, str(message.get("id") or ""), offset))
                stats.missing_tool_responses_inserted += 1

        index = lookahead

    if len(repaired) > max_messages:
        stats.old_messages_compacted = len(repaired) - max_messages
        repaired = repaired[-max_messages:]

    stats.messages_after = len(repaired)
    return repaired, stats


def _merge_stats(target: RepairStats, source: RepairStats) -> None:
    for key, value in source.to_dict().items():
        if key in {"scanned_files", "changed_files", "backup_files"}:
            continue
        setattr(target, key, getattr(target, key) + value)


def _checkpoint_files() -> list[Path]:
    if not LANGGRAPH_API_DIR.exists():
        return []
    return sorted(LANGGRAPH_API_DIR.glob("*.pckl"))


def _archive_files() -> list[Path]:
    if not THREAD_ARCHIVE_DIR.exists():
        return []
    return sorted(THREAD_ARCHIVE_DIR.glob("*.json"))


def _backup_file(source: Path, backup_dir: Path) -> Path:
    relative_name = source.name
    destination = backup_dir / relative_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def repair_thread_archives(
    *,
    dry_run: bool = True,
    confirm: bool = False,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
) -> dict[str, Any]:
    """Repair local thread archive JSON files and safely snapshot LangGraph checkpoint files.

    Pickle checkpoint internals are intentionally not modified here. The runtime
    sanitizer protects model calls; this offline tool makes local JSON archives
    clean and stores checkpoint backups so future migration can operate safely.
    """
    if not dry_run and not confirm:
        return {
            "status": "confirmation_required",
            "message": "Set confirm=true to write repaired archives. Dry-run mode is safe and default.",
        }

    backup_dir = BACKUP_ROOT / _now_stamp()
    stats = RepairStats()
    changed_files: list[str] = []
    preview: list[dict[str, Any]] = []

    for archive_path in _archive_files():
        stats.scanned_files += 1
        try:
            record = json.loads(archive_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            preview.append({"path": str(archive_path), "error": f"invalid_json: {exc}"})
            continue

        messages = record.get("values", {}).get("messages", [])
        if not isinstance(messages, list):
            continue

        repaired_messages, file_stats = repair_messages(
            messages,
            max_messages=max_messages,
            max_text_length=max_text_length,
        )
        _merge_stats(stats, file_stats)
        changed = repaired_messages != messages
        if not changed:
            continue

        stats.changed_files += 1
        changed_files.append(str(archive_path))
        preview.append({"path": str(archive_path), **file_stats.to_dict()})

        if dry_run:
            continue

        _backup_file(archive_path, backup_dir / "thread_archive")
        stats.backup_files += 1
        next_record = dict(record)
        next_values = dict(next_record.get("values") or {})
        next_values["messages"] = repaired_messages
        next_record["values"] = next_values
        next_record["updated_at"] = datetime.now().isoformat()
        next_record["offline_repair"] = {
            "repaired_at": datetime.now().isoformat(),
            "backup_dir": str(backup_dir),
            "stats": file_stats.to_dict(),
        }
        atomic_write_json(archive_path, next_record)

    checkpoint_files = [str(path) for path in _checkpoint_files()]
    checkpoint_migration = migrate_checkpoint_pickles(dry_run=dry_run, confirm=confirm)
    if not dry_run:
        stats.backup_files += int(checkpoint_migration.get("checkpoint_count", 0))

    return {
        "status": "dry_run" if dry_run else "success",
        "thread_archive_dir": str(THREAD_ARCHIVE_DIR),
        "langgraph_api_dir": str(LANGGRAPH_API_DIR),
        "backup_dir": "" if dry_run else str(backup_dir),
        "stats": stats.to_dict(),
        "changed_files": changed_files,
        "checkpoint_files": checkpoint_files,
        "checkpoint_migration": checkpoint_migration,
        "preview": preview[:40],
        "notes": [
            "Local JSON thread archives are repaired in confirm mode.",
            "LangGraph .pckl checkpoint files are archived with a structured migration manifest but not mutated.",
        ],
    }
