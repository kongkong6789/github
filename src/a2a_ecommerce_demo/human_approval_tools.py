from __future__ import annotations

import json
from typing import Any


def build_human_approval_request(
    *,
    action_name: str,
    args: dict[str, Any],
    description: str,
    destructive_effects: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    allowed_decisions: list[str] | None = None,
) -> dict[str, Any]:
    """Build the HITL request shape consumed by the Agent Inbox UI."""
    decisions = allowed_decisions or ["approve", "reject"]
    return {
        "action_requests": [
            {
                "name": action_name,
                "args": args,
                "description": description,
            }
        ],
        "review_configs": [
            {
                "action_name": action_name,
                "allowed_decisions": decisions,
            }
        ],
        "metadata": {
            **(metadata or {}),
            "destructive_effects": destructive_effects or [],
        },
    }


def _first_decision(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "approve" if value else "reject"}
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"approve", "approved", "yes", "true"}:
            return {"type": "approve"}
        if lowered in {"reject", "rejected", "no", "false"}:
            return {"type": "reject", "message": value}
    if isinstance(value, list) and value:
        return _first_decision(value[0])
    if isinstance(value, dict):
        if isinstance(value.get("decisions"), list) and value["decisions"]:
            return _first_decision(value["decisions"][0])
        if value.get("type"):
            return value
    return {"type": "reject", "message": "Unsupported or empty human approval decision."}


def parse_human_approval_decision(value: Any) -> dict[str, Any]:
    """Normalize LangGraph resume payloads from the Agent Inbox into one decision."""
    decision = _first_decision(value)
    decision_type = str(decision.get("type") or "").lower()
    if decision_type == "approve":
        return {"type": "approve", "approved": True, "edited_args": {}, "message": ""}
    if decision_type == "edit":
        edited_action = decision.get("edited_action") if isinstance(decision.get("edited_action"), dict) else {}
        edited_args = edited_action.get("args") if isinstance(edited_action, dict) else {}
        return {
            "type": "edit",
            "approved": True,
            "edited_args": edited_args if isinstance(edited_args, dict) else {},
            "message": "",
        }
    return {
        "type": "reject",
        "approved": False,
        "edited_args": {},
        "message": str(decision.get("message") or "Rejected by human reviewer."),
    }


def request_human_approval(
    *,
    action_name: str,
    args: dict[str, Any],
    description: str,
    destructive_effects: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    allowed_decisions: list[str] | None = None,
) -> dict[str, Any]:
    """Pause a LangGraph run for human approval, or return preview outside a run.

    Outside LangGraph's runnable context, `interrupt()` raises RuntimeError. In
    that case we return the same payload for tools/tests/CLI callers to render.
    """
    request = build_human_approval_request(
        action_name=action_name,
        args=args,
        description=description,
        destructive_effects=destructive_effects,
        metadata=metadata,
        allowed_decisions=allowed_decisions,
    )
    try:
        from langgraph.types import interrupt

        decision_payload = interrupt(request)
    except RuntimeError as exc:
        if "outside of a runnable context" not in str(exc).lower():
            raise
        return {
            "status": "confirmation_required",
            "requires_confirmation": True,
            "interrupt": {"value": request},
            "resume_shape": {"decisions": [{"type": "approve"}]},
        }
    decision = parse_human_approval_decision(decision_payload)
    return {
        **decision,
        "status": "approved" if decision["approved"] else "rejected",
        "interrupt": {"value": request},
        "raw_resume": json.loads(json.dumps(decision_payload, ensure_ascii=False, default=str)),
    }
