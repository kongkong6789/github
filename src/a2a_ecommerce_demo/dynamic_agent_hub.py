from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
REGISTRY_DIR = Path(os.getenv("A2A_AGENT_REGISTRY_DIR", DATA_DIR / "agent_registry")).resolve()
TEMPLATE_DIR = Path(os.getenv("A2A_AGENT_TEMPLATE_DIR", DATA_DIR / "agent_templates")).resolve()
SEED_TEMPLATE_DIR = Path(os.getenv("A2A_AGENT_TEMPLATE_SEED_DIR", PROJECT_ROOT / "config" / "agent_templates")).resolve()

REGISTRY_SCHEMA = "a2a_dynamic_agent_registry_v1"
AGENT_SCHEMA = "a2a_dynamic_agent_v1"
EXECUTION_MODE = "local_mock"

READ_ONLY_DYNAMIC_TOOLS = {
    "assess_data_quality",
    "assess_decision_risks",
    "audit_fact_source_readiness",
    "diagnose_lightrag_failures",
    "get_lightrag_entity",
    "list_fact_tables",
    "list_lightrag_entities",
    "list_registered_datasets",
    "list_wiki_pages",
    "plan_fact_query",
    "query_ads_history",
    "query_fact_layer",
    "query_fact_layer_from_question",
    "query_finance_history",
    "query_inventory_anomalies",
    "query_inventory_history",
    "query_inventory_snapshot",
    "query_lightrag",
    "query_official_lightrag",
    "query_sales_history",
    "query_sku_snapshot",
    "read_wiki_page",
    "search_wiki",
    "simulate_decision_scenarios",
    "summarize_brand_coverage",
    "summarize_business_data",
    "summarize_lightrag_processing_status",
}

DEFAULT_OUTPUT_SCHEMA = ["summary", "evidence", "risks", "next_actions", "human_confirmation"]
VALID_STATUSES = {"draft", "active", "paused", "disabled", "archived"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_dirs() -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    _agents_dir().mkdir(parents=True, exist_ok=True)


def _agents_dir() -> Path:
    return REGISTRY_DIR / "agents"


def _registry_path() -> Path:
    return REGISTRY_DIR / "registry.json"


def _agent_path(agent_id: str) -> Path:
    return _agents_dir() / f"{_slugify(agent_id, 'dynamic-agent')}.json"


def _template_path(template_id: str) -> Path:
    slug = _slugify(template_id, "agent-template")
    runtime_path = TEMPLATE_DIR / f"{slug}.json"
    if runtime_path.exists():
        return runtime_path
    seed_path = SEED_TEMPLATE_DIR / f"{slug}.json"
    if seed_path.exists():
        return seed_path
    return runtime_path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slugify(value: str, fallback: str = "dynamic-agent") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", str(value)).strip("-")
    return slug[:96] or fallback


def _stable_id(value: str, prefix: str = "agent") -> str:
    text = str(value or "dynamic-agent")
    slug = _slugify(text, "dynamic-agent")[:56]
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{slug}-{digest}"


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _load_registry() -> dict[str, Any]:
    _ensure_dirs()
    path = _registry_path()
    if not path.exists():
        return {"schema": REGISTRY_SCHEMA, "updated_at": "", "agents": {}}
    try:
        registry = _read_json(path)
    except json.JSONDecodeError:
        registry = {"schema": REGISTRY_SCHEMA, "updated_at": "", "agents": {}}
    registry.setdefault("schema", REGISTRY_SCHEMA)
    registry.setdefault("agents", {})
    return registry


def _save_registry(registry: dict[str, Any]) -> None:
    registry["schema"] = REGISTRY_SCHEMA
    registry["updated_at"] = _now()
    _write_json(_registry_path(), registry)


def _load_record(agent_id: str) -> dict[str, Any]:
    path = _agent_path(agent_id)
    if not path.exists():
        raise KeyError(f"Unknown dynamic agent: {agent_id}")
    record = _read_json(path)
    record.setdefault("schema", AGENT_SCHEMA)
    record.setdefault("versions", [])
    record.setdefault("runs", [])
    return record


def _save_record(record: dict[str, Any]) -> Path:
    _ensure_dirs()
    spec = record["spec"]
    path = _agent_path(spec["agent_id"])
    record["schema"] = AGENT_SCHEMA
    record["updated_at"] = _now()
    _write_json(path, record)

    registry = _load_registry()
    registry.setdefault("agents", {})[spec["agent_id"]] = {
        "agent_id": spec["agent_id"],
        "name": spec.get("name", ""),
        "goal": spec.get("goal", ""),
        "status": spec.get("status", ""),
        "version": spec.get("version", 0),
        "updated_at": spec.get("updated_at", record["updated_at"]),
        "path": str(path),
    }
    _save_registry(registry)
    return path


def _audit(
    event_type: str,
    *,
    actor: str,
    summary: str,
    agent_id: str = "",
    paths: list[str] | None = None,
    risks: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event

    audit_metadata = dict(metadata or {})
    if agent_id:
        audit_metadata["agent_id"] = agent_id
    record_audit_event(
        event_type,
        actor=actor,
        summary=summary,
        task_id=agent_id,
        paths=paths or [],
        risks=risks or [],
        metadata=audit_metadata,
    )


def _parse_jsonish(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return copy.deepcopy(default)
    if isinstance(value, (dict, list)):
        return copy.deepcopy(value)
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return copy.deepcopy(default)
    return copy.deepcopy(default)


def _as_list(value: Any) -> list[str]:
    parsed = _parse_jsonish(value, [])
    if isinstance(parsed, str):
        parsed = [item.strip() for item in parsed.split(",")]
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _infer_name(task_description: str) -> str:
    text = task_description.strip()
    match = re.search(r"([\u4e00-\u9fffA-Za-z0-9 _-]{2,40}Agent)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if "库存" in text:
        return "库存风险 Agent"
    if "财务" in text or "现金" in text:
        return "财务分析 Agent"
    if "经营" in text or "公司" in text or "战略" in text:
        return "经营策略 Agent"
    return "动态业务 Agent"


def _infer_tools(task_description: str) -> list[str]:
    text = task_description.lower()
    tools: list[str] = []
    if any(keyword in text for keyword in ["库存", "补货", "断货", "sku", "销量", "sales", "inventory"]):
        tools.extend(["query_inventory_snapshot", "query_inventory_history", "query_sales_history", "query_sku_snapshot"])
    if any(keyword in text for keyword in ["财务", "现金", "利润", "毛利", "成本", "预算", "finance", "cash"]):
        tools.extend(["query_finance_history", "query_ads_history", "list_fact_tables", "plan_fact_query", "query_fact_layer", "assess_data_quality"])
    if any(keyword in text for keyword in ["风险", "审查", "risk"]):
        tools.append("assess_decision_risks")
    if any(keyword in text for keyword in ["公司", "经营", "战略", "老板", "strategy"]):
        tools.extend(["summarize_business_data", "summarize_brand_coverage", "assess_data_quality", "query_fact_layer"])
    if any(keyword in text for keyword in ["lightrag", "证据", "知识", "wiki", "历史"]):
        tools.extend(["query_lightrag", "query_official_lightrag", "search_wiki", "read_wiki_page"])
    if not tools:
        tools.extend(["summarize_business_data", "search_wiki", "query_lightrag"])
    return _unique([tool for tool in tools if tool in READ_ONLY_DYNAMIC_TOOLS])


def _permission_preview(tool_allowlist: list[str]) -> dict[str, Any]:
    allowed = [tool for tool in tool_allowlist if tool in READ_ONLY_DYNAMIC_TOOLS]
    blocked = [tool for tool in tool_allowlist if tool not in READ_ONLY_DYNAMIC_TOOLS]
    risks = ["dynamic agent execution requires human confirmation before activation"]
    if blocked:
        risks.append("blocked tools were removed because they are not read-only dynamic-agent tools")
    return {
        "execution_mode": EXECUTION_MODE,
        "requires_human_confirmation": True,
        "approved_tools": allowed,
        "blocked_tools": blocked,
        "tool_count": len(allowed),
        "risks": risks,
        "confirmation_required_before": ["status=active", "run_dynamic_agent"],
    }


def _normalize_spec(raw_spec: dict[str, Any]) -> dict[str, Any]:
    spec = copy.deepcopy(raw_spec)
    description = str(spec.get("description") or spec.get("goal") or spec.get("name") or "dynamic agent")
    agent_id = str(spec.get("agent_id") or _stable_id(description))
    requested_tools = _as_list(spec.get("tool_allowlist"))
    preview = _permission_preview(requested_tools)
    spec["agent_id"] = _slugify(agent_id, "dynamic-agent")
    spec["name"] = str(spec.get("name") or _infer_name(description))
    spec["role"] = str(spec.get("role") or spec["name"])
    spec["goal"] = str(spec.get("goal") or description)
    spec["description"] = str(spec.get("description") or description)
    spec["tool_allowlist"] = preview["approved_tools"]
    spec["output_schema"] = _as_list(spec.get("output_schema")) or list(DEFAULT_OUTPUT_SCHEMA)
    spec["execution_mode"] = EXECUTION_MODE
    spec["permission_preview"] = preview
    spec.setdefault("metadata", {})
    return spec


def _spec_from_input(agent_spec: Any) -> dict[str, Any]:
    if isinstance(agent_spec, dict):
        return _normalize_spec(agent_spec)
    if isinstance(agent_spec, str):
        parsed = json.loads(agent_spec)
        if not isinstance(parsed, dict):
            raise ValueError("agent_spec must decode to a JSON object")
        return _normalize_spec(parsed)
    raise TypeError("agent_spec must be a JSON string or dict")


def draft_dynamic_agent_spec(
    task_description: str,
    created_by: str = "agent",
    requested_tools_json: str = "",
    output_schema_json: str = "",
) -> str:
    """Draft a dynamic Agent spec and permission preview without enabling execution."""
    inferred_tools = _as_list(requested_tools_json) or _infer_tools(task_description)
    output_schema = _as_list(output_schema_json) or list(DEFAULT_OUTPUT_SCHEMA)
    now = _now()
    spec = _normalize_spec(
        {
            "agent_id": _stable_id(task_description),
            "name": _infer_name(task_description),
            "role": _infer_name(task_description),
            "goal": task_description,
            "description": task_description,
            "status": "draft",
            "version": 0,
            "tool_allowlist": inferred_tools,
            "output_schema": output_schema,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
    )
    spec["status"] = "draft"
    spec["version"] = 0
    spec["created_by"] = created_by
    spec["created_at"] = now
    spec["updated_at"] = now

    record = {"schema": AGENT_SCHEMA, "spec": spec, "versions": [], "runs": []}
    path = _save_record(record)
    _audit(
        "dynamic_agent_drafted",
        actor=created_by,
        summary=f"Drafted dynamic agent spec: {spec['name']}",
        agent_id=spec["agent_id"],
        paths=[str(path)],
        risks=spec["permission_preview"].get("risks", []),
        metadata={"tool_allowlist": spec["tool_allowlist"], "status": "draft"},
    )
    return _json_response(
        {
            "status": "draft",
            "registry_path": str(path),
            "spec": spec,
            "permission_preview": spec["permission_preview"],
        }
    )


def _load_agent_template(template_id: str) -> dict[str, Any]:
    path = _template_path(template_id)
    if not path.exists():
        raise FileNotFoundError(f"Agent template not found: {template_id}")
    template = _read_json(path)
    if template.get("status") not in {"draft", "active"}:
        raise ValueError(f"Agent template is not draft/active: {template_id}")
    if str(template.get("template_id") or "") != template_id:
        raise ValueError(f"Agent template id mismatch: {template_id}")
    return template


def draft_dynamic_agent_spec_from_template(
    template_id: str,
    task_description: str = "",
    created_by: str = "agent",
    requested_tools_json: str = "",
    output_schema_json: str = "",
) -> str:
    """Draft a dynamic Agent spec from a controlled local template without activating it."""
    template = _load_agent_template(template_id)
    requested_tools = _as_list(requested_tools_json) or _as_list(template.get("tool_allowlist"))
    output_schema = _as_list(output_schema_json) or _as_list(template.get("output_schema")) or list(DEFAULT_OUTPUT_SCHEMA)
    now = _now()
    prompt = str(template.get("prompt") or "").strip()
    description = str(task_description or template.get("description") or prompt or template.get("role") or template_id)
    role = str(template.get("role") or template.get("name") or _infer_name(description))
    spec = _normalize_spec(
        {
            "agent_id": _stable_id(f"{template_id}:{description}"),
            "name": role,
            "role": role,
            "goal": description,
            "description": description,
            "status": "draft",
            "version": 0,
            "tool_allowlist": requested_tools,
            "output_schema": output_schema,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
            "source_template_id": template_id,
            "source_repo": str(template.get("source_repo") or ""),
            "source_path": str(template.get("source_path") or ""),
            "scenarios": _as_list(template.get("scenarios")),
            "risk_level": str(template.get("risk_level") or "medium"),
            "evidence_required": bool(template.get("evidence_required", True)),
            "owner": str(template.get("owner") or ""),
            "template_prompt": prompt,
            "metadata": {
                "template_id": template_id,
                "template_schema": str(template.get("schema") or ""),
                "source_repo": str(template.get("source_repo") or ""),
                "source_path": str(template.get("source_path") or ""),
                "template_status": str(template.get("status") or ""),
            },
        }
    )
    spec["status"] = "draft"
    spec["version"] = 0
    spec["created_by"] = created_by
    spec["created_at"] = now
    spec["updated_at"] = now
    spec["source_template_id"] = template_id
    spec["source_repo"] = str(template.get("source_repo") or "")
    spec["source_path"] = str(template.get("source_path") or "")
    spec["scenarios"] = _as_list(template.get("scenarios"))
    spec["risk_level"] = str(template.get("risk_level") or "medium")
    spec["evidence_required"] = bool(template.get("evidence_required", True))
    spec["owner"] = str(template.get("owner") or "")
    spec["template_prompt"] = prompt

    record = {"schema": AGENT_SCHEMA, "spec": spec, "versions": [], "runs": []}
    path = _save_record(record)
    _audit(
        "dynamic_agent_template_drafted",
        actor=created_by,
        summary=f"Drafted dynamic agent from template: {template_id}",
        agent_id=spec["agent_id"],
        paths=[str(_template_path(template_id)), str(path)],
        risks=spec["permission_preview"].get("risks", []),
        metadata={
            "template_id": template_id,
            "source_repo": spec["source_repo"],
            "tool_allowlist": spec["tool_allowlist"],
            "blocked_tools": spec["permission_preview"].get("blocked_tools", []),
        },
    )
    return _json_response(
        {
            "status": "draft",
            "template_path": str(_template_path(template_id)),
            "registry_path": str(path),
            "spec": spec,
            "permission_preview": spec["permission_preview"],
        }
    )


def confirm_dynamic_agent_spec(agent_spec: Any, confirmed_by: str = "agent") -> str:
    """Confirm a drafted dynamic Agent spec and activate version 1."""
    spec = _spec_from_input(agent_spec)
    preview = spec["permission_preview"]
    if preview["blocked_tools"]:
        raise ValueError(f"Blocked tools cannot be confirmed: {', '.join(preview['blocked_tools'])}")

    now = _now()
    spec["status"] = "active"
    spec["version"] = 1
    spec["confirmed_by"] = confirmed_by
    spec["confirmed_at"] = now
    spec["updated_at"] = now
    spec["human_confirmation"] = {"confirmed_by": confirmed_by, "confirmed_at": now}

    try:
        record = _load_record(spec["agent_id"])
    except KeyError:
        record = {"schema": AGENT_SCHEMA, "versions": [], "runs": []}
    record["spec"] = spec
    record["versions"] = [copy.deepcopy(spec)]
    path = _save_record(record)
    _audit(
        "dynamic_agent_registered",
        actor=confirmed_by,
        summary=f"Confirmed dynamic agent: {spec['name']}",
        agent_id=spec["agent_id"],
        paths=[str(path)],
        risks=preview.get("risks", []),
        metadata={"version": spec["version"], "tool_allowlist": spec["tool_allowlist"]},
    )
    return _json_response(
        {
            "status": "success",
            "registry_path": str(path),
            "spec": spec,
            "permission_preview": preview,
        }
    )


def get_dynamic_agent(agent_id: str, include_versions: bool = False) -> str:
    """Return one dynamic Agent registry record."""
    record = _load_record(agent_id)
    payload = {
        "status": "success",
        "registry_path": str(_agent_path(agent_id)),
        "spec": record["spec"],
        "run_count": len(record.get("runs", [])),
    }
    if include_versions:
        payload["versions"] = record.get("versions", [])
    return _json_response(payload)


def list_dynamic_agents(status: str = "", limit: int = 100) -> str:
    """List dynamic Agent specs from the local registry."""
    registry = _load_registry()
    rows = list(registry.get("agents", {}).values())
    if status:
        rows = [row for row in rows if row.get("status") == status]
    rows = sorted(rows, key=lambda row: str(row.get("updated_at", "")), reverse=True)
    return _json_response(
        {
            "status": "success",
            "registry_path": str(_registry_path()),
            "agents": rows[: max(0, int(limit))],
        }
    )


def update_dynamic_agent_spec(agent_id: str, updates: Any, updated_by: str = "agent") -> str:
    """Update mutable fields on an active or paused dynamic Agent and create a new version."""
    record = _load_record(agent_id)
    current = copy.deepcopy(record["spec"])
    if current.get("status") == "archived":
        raise ValueError(f"Cannot update archived dynamic agent: {agent_id}")

    parsed_updates = _parse_jsonish(updates, {})
    if not isinstance(parsed_updates, dict):
        raise ValueError("updates must be a JSON object or dict")

    mutable_fields = {"description", "goal", "metadata", "name", "output_schema", "role", "tool_allowlist"}
    next_spec = copy.deepcopy(current)
    for field, value in parsed_updates.items():
        if field in mutable_fields:
            next_spec[field] = value

    next_spec = _normalize_spec(next_spec)
    next_spec["status"] = current.get("status", "active")
    next_spec["version"] = int(current.get("version", 0)) + 1
    next_spec["previous_version"] = current.get("version", 0)
    next_spec["updated_by"] = updated_by
    next_spec["updated_at"] = _now()

    record["spec"] = next_spec
    record.setdefault("versions", []).append(copy.deepcopy(next_spec))
    path = _save_record(record)
    _audit(
        "dynamic_agent_updated",
        actor=updated_by,
        summary=f"Updated dynamic agent: {next_spec['name']}",
        agent_id=agent_id,
        paths=[str(path)],
        risks=next_spec["permission_preview"].get("risks", []),
        metadata={"version": next_spec["version"], "updated_fields": sorted(set(parsed_updates) & mutable_fields)},
    )
    return _json_response({"status": "success", "registry_path": str(path), "spec": next_spec})


def set_dynamic_agent_status(agent_id: str, status: str, changed_by: str = "agent") -> str:
    """Set dynamic Agent lifecycle status without changing the spec version."""
    normalized_status = str(status).strip().lower()
    if normalized_status not in VALID_STATUSES:
        raise ValueError(f"Invalid dynamic agent status: {status}. Expected one of: {', '.join(sorted(VALID_STATUSES))}")
    record = _load_record(agent_id)
    spec = copy.deepcopy(record["spec"])
    spec["status"] = normalized_status
    spec["status_changed_by"] = changed_by
    spec["status_changed_at"] = _now()
    spec["updated_at"] = spec["status_changed_at"]
    record["spec"] = spec
    path = _save_record(record)
    _audit(
        "dynamic_agent_status_changed",
        actor=changed_by,
        summary=f"Changed dynamic agent status to {normalized_status}: {spec['name']}",
        agent_id=agent_id,
        paths=[str(path)],
        metadata={"status": normalized_status, "version": spec.get("version", 0)},
    )
    return _json_response({"status": "success", "registry_path": str(path), "spec": spec})


def rollback_dynamic_agent(agent_id: str, target_version: int, changed_by: str = "agent") -> str:
    """Create a new active version from an earlier confirmed dynamic Agent version."""
    record = _load_record(agent_id)
    versions = record.get("versions", [])
    target = None
    for version_spec in versions:
        if int(version_spec.get("version", -1)) == int(target_version):
            target = copy.deepcopy(version_spec)
            break
    if target is None:
        raise ValueError(f"Version {target_version} not found for dynamic agent: {agent_id}")

    current = record["spec"]
    now = _now()
    target["status"] = "active"
    target["version"] = int(current.get("version", 0)) + 1
    target["previous_version"] = int(target_version)
    target["rolled_back_by"] = changed_by
    target["rolled_back_at"] = now
    target["updated_at"] = now
    target = _normalize_spec(target)
    target["status"] = "active"
    target["version"] = int(current.get("version", 0)) + 1
    target["previous_version"] = int(target_version)
    target["rolled_back_by"] = changed_by
    target["rolled_back_at"] = now
    target["updated_at"] = now

    record["spec"] = target
    record.setdefault("versions", []).append(copy.deepcopy(target))
    path = _save_record(record)
    _audit(
        "dynamic_agent_rolled_back",
        actor=changed_by,
        summary=f"Rolled back dynamic agent to version {target_version}: {target['name']}",
        agent_id=agent_id,
        paths=[str(path)],
        metadata={"target_version": int(target_version), "new_version": target["version"]},
    )
    return _json_response({"status": "success", "registry_path": str(path), "spec": target})


def _parse_input_payload(input_payload: str) -> Any:
    if not input_payload:
        return {}
    if isinstance(input_payload, str):
        try:
            return json.loads(input_payload)
        except json.JSONDecodeError:
            return {"text": input_payload}
    return input_payload


def run_dynamic_agent(agent_id: str, input_payload: str = "", requested_by: str = "agent") -> str:
    """Execute an active dynamic Agent through a deterministic local mock trace."""
    record = _load_record(agent_id)
    spec = record["spec"]
    if spec.get("status") != "active":
        raise ValueError(f"Dynamic agent {agent_id} is not active: {spec.get('status')}")

    parsed_input = _parse_input_payload(input_payload)
    normalized_input = json.dumps(parsed_input, ensure_ascii=False, sort_keys=True)
    run_digest = hashlib.sha1(f"{agent_id}|{spec.get('version')}|{normalized_input}".encode("utf-8")).hexdigest()[:12]
    planned_steps = [
        {
            "tool": tool,
            "mode": EXECUTION_MODE,
            "reason": "declared in confirmed dynamic agent tool_allowlist",
        }
        for tool in spec.get("tool_allowlist", [])
    ]
    trace = {
        "run_id": f"run-{run_digest}",
        "agent_id": agent_id,
        "agent_name": spec.get("name", ""),
        "version": spec.get("version", 0),
        "execution_mode": EXECUTION_MODE,
        "input": parsed_input,
        "tool_allowlist": list(spec.get("tool_allowlist", [])),
        "planned_steps": planned_steps,
        "output_schema": list(spec.get("output_schema", [])),
        "result": {
            "summary": f"{spec.get('name', 'Dynamic Agent')} handled the request with deterministic local_mock execution.",
            "evidence": planned_steps,
            "risks": spec.get("permission_preview", {}).get("risks", []),
            "next_actions": ["review trace", "run with real tools only after explicit platform integration"],
            "human_confirmation": spec.get("human_confirmation", {}),
        },
    }

    record.setdefault("runs", []).append({"run_id": trace["run_id"], "requested_by": requested_by, "trace": trace, "created_at": _now()})
    path = _save_record(record)
    _audit(
        "dynamic_agent_invoked",
        actor=requested_by,
        summary=f"Invoked dynamic agent: {spec.get('name', agent_id)}",
        agent_id=agent_id,
        paths=[str(path)],
        risks=trace["result"]["risks"],
        metadata={"run_id": trace["run_id"], "version": spec.get("version", 0), "tool_count": len(spec.get("tool_allowlist", []))},
    )
    return _json_response({"status": "success", "trace": trace})


def promote_dynamic_agent_to_template(agent_id: str, notes: str = "", promoted_by: str = "agent") -> str:
    """Promote a confirmed dynamic Agent spec into a reusable local template."""
    record = _load_record(agent_id)
    spec = record["spec"]
    if spec.get("status") not in {"active", "paused"}:
        raise ValueError(f"Only active or paused dynamic agents can be promoted to templates: {agent_id}")

    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    template_id = _slugify(spec.get("name") or agent_id, "dynamic-agent-template")
    content = {
        "template_id": template_id,
        "status": "draft",
        "source_agent_id": agent_id,
        "source_version": spec.get("version", 0),
        "saved_at": _now(),
        "role": spec.get("role", ""),
        "goal": spec.get("goal", ""),
        "tools": list(spec.get("tool_allowlist", [])),
        "output_schema": list(spec.get("output_schema", [])),
        "notes": notes,
        "prompt": (
            f"你是{spec.get('role', spec.get('name', '动态 Agent'))}。目标：{spec.get('goal', '')}\n"
            f"允许工具：{', '.join(spec.get('tool_allowlist', []))}\n"
            f"输出字段：{', '.join(spec.get('output_schema', []))}\n"
            "必须说明证据来源；数据不足时列出缺口；高风险动作必须要求人工确认。"
        ),
    }
    path = TEMPLATE_DIR / f"{template_id}.json"
    _write_json(path, content)
    _audit(
        "dynamic_agent_template_promoted",
        actor=promoted_by,
        summary=f"Promoted dynamic agent to template: {spec.get('name', agent_id)}",
        agent_id=agent_id,
        paths=[str(path)],
        metadata={"template_id": template_id, "source_version": spec.get("version", 0)},
    )
    return _json_response({"status": "success", "saved_to": str(path), "template": content})
