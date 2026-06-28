"""
Experience storage helpers for real-world skill usage feedback.

Design goals:
- append raw runtime feedback automatically to JSONL
- keep curated markdown docs separate from raw logs
- avoid writing unstable one-off behavior directly into SKILL.md
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FEEDBACK_LOG_PATH = PROJECT_ROOT / "FEEDBACK_LOG.jsonl"
LEARNINGS_PATH = PROJECT_ROOT / "LEARNINGS.md"
PLAYBOOK_PATH = PROJECT_ROOT / "PLAYBOOK.md"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_feedback_log(entry: dict[str, Any]) -> dict[str, Any]:
    """
    Append a raw feedback/event entry to FEEDBACK_LOG.jsonl.
    """
    payload = {
        "timestamp": _utc_now_iso(),
        **entry,
    }
    with FEEDBACK_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def build_workflow_feedback_entry(
    workflow: str,
    status: str,
    summary: str,
    *,
    action: str | None = None,
    order_type: str | None = None,
    trade_no: str | None = None,
    document_no: str | None = None,
    next_action: str | None = None,
    requires_finance_review: bool | None = None,
    requires_approval_flow: bool | None = None,
    submit_target: str | None = None,
    input_summary: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    pain_points: list[str] | None = None,
    reuse_hints: list[str] | None = None,
    auto_fill_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a normalized workflow feedback payload before appending it.
    """
    payload: dict[str, Any] = {
        "source": "workflow",
        "workflow": workflow,
        "status": status,
        "summary": summary,
    }
    if action:
        payload["action"] = action
    if order_type:
        payload["order_type"] = order_type
    if trade_no:
        payload["trade_no"] = trade_no
    if document_no:
        payload["document_no"] = document_no
    if next_action:
        payload["next_action"] = next_action
    if requires_finance_review is not None:
        payload["requires_finance_review"] = requires_finance_review
    if requires_approval_flow is not None:
        payload["requires_approval_flow"] = requires_approval_flow
    if submit_target:
        payload["submit_target"] = submit_target
    if input_summary:
        payload["input_summary"] = input_summary
    if steps:
        payload["steps"] = steps
    if pain_points:
        payload["pain_points"] = pain_points
    if reuse_hints:
        payload["reuse_hints"] = reuse_hints
    if auto_fill_summary:
        payload["auto_fill_summary"] = auto_fill_summary
    return payload
