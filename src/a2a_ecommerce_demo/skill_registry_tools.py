from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event
from src.a2a_ecommerce_demo.human_approval_tools import request_human_approval

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
WIKI_DIR = Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).resolve()
SKILL_REGISTRY_DIR = Path(os.getenv("A2A_SKILL_REGISTRY_DIR", DATA_DIR / "skill_registry")).resolve()
TEMPLATE_DIR = Path(os.getenv("A2A_AGENT_TEMPLATE_DIR", DATA_DIR / "agent_templates")).resolve()

REGISTRY_SCHEMA = "a2a_agent_skill_registry_v1"
SKILL_SCHEMA = "a2a_agent_skill_v1"
VALID_SKILL_STATUSES = {"draft", "active", "paused", "disabled", "archived"}

READ_ONLY_SKILL_TOOLS = {
    "assess_data_quality",
    "audit_fact_source_readiness",
    "get_erp_connector_health",
    "list_erp_connectors",
    "list_fact_tables",
    "list_registered_datasets",
    "list_runtime_capabilities",
    "list_wiki_pages",
    "plan_fact_query",
    "preview_erp_connector_sync",
    "list_erp_live_query_capabilities",
    "test_erp_live_connection",
    "route_erp_live_query",
    "query_ads_history",
    "query_erp_live_snapshot",
    "query_inventory_cost_reference",
    "query_fact_layer",
    "query_fact_layer_from_question",
    "query_finance_history",
    "query_inventory_anomalies",
    "query_inventory_history",
    "query_inventory_snapshot",
    "query_lightrag",
    "query_official_lightrag",
    "invoke_runtime_capability",
    "query_sales_history",
    "verify_erp_supplier_terms_mapping",
    "read_wiki_page",
    "search_wiki",
    "summarize_brand_coverage",
    "summarize_business_data",
}

DEFAULT_OUTPUT_SCHEMA = ["summary", "evidence", "data_gaps", "risks", "next_actions"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _skills_dir() -> Path:
    return SKILL_REGISTRY_DIR / "skills"


def _registry_path() -> Path:
    return SKILL_REGISTRY_DIR / "registry.json"


def _skill_path(skill_id: str) -> Path:
    return _skills_dir() / f"{_slugify(skill_id, 'agent-skill')}.json"


def _ensure_dirs() -> None:
    _skills_dir().mkdir(parents=True, exist_ok=True)
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slugify(value: str, fallback: str = "agent-skill") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", str(value)).strip("-")
    return slug[:96] or fallback


def _stable_id(value: str, prefix: str = "skill") -> str:
    slug = _slugify(value, "agent-skill")[:56]
    digest = hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{slug}-{digest}"


def _parse_jsonish(value: str | list[Any] | dict[str, Any] | None, default: Any) -> Any:
    if value in (None, ""):
        return copy.deepcopy(default)
    if isinstance(value, (list, dict)):
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


def _resolve_wiki_path(path: str) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        resolved = raw.resolve()
    elif raw.parts and raw.parts[0] == "wiki":
        resolved = (WIKI_DIR / Path(*raw.parts[1:])).resolve()
    else:
        resolved = (WIKI_DIR / raw).resolve()
    if WIKI_DIR not in [resolved, *resolved.parents]:
        raise ValueError(f"Refusing to read outside wiki directory: {resolved}")
    return resolved


def _relative_wiki_path(path: Path) -> str:
    try:
        return f"wiki/{path.resolve().relative_to(WIKI_DIR).as_posix()}"
    except ValueError:
        return path.as_posix()


def _title_from_markdown(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def _skill_permission_preview(tool_allowlist: list[str]) -> dict[str, Any]:
    allowed = [tool for tool in tool_allowlist if tool in READ_ONLY_SKILL_TOOLS]
    blocked = [tool for tool in tool_allowlist if tool not in READ_ONLY_SKILL_TOOLS]
    risks = ["new reusable skill requires human approval before activation"]
    if blocked:
        risks.append("blocked tools removed because this skill registry currently admits read-only analysis tools")
    return {
        "requires_human_confirmation": True,
        "approved_tools": allowed,
        "blocked_tools": blocked,
        "tool_count": len(allowed),
        "risks": risks,
        "confirmation_required_before": ["status=active", "skill_used_by_agent"],
    }


def _load_registry() -> dict[str, Any]:
    _ensure_dirs()
    path = _registry_path()
    if not path.exists():
        return {"schema": REGISTRY_SCHEMA, "updated_at": "", "skills": {}}
    try:
        registry = _read_json(path)
    except json.JSONDecodeError:
        registry = {"schema": REGISTRY_SCHEMA, "updated_at": "", "skills": {}}
    registry.setdefault("schema", REGISTRY_SCHEMA)
    registry.setdefault("skills", {})
    return registry


def _save_registry(registry: dict[str, Any]) -> None:
    registry["schema"] = REGISTRY_SCHEMA
    registry["updated_at"] = _now()
    _write_json(_registry_path(), registry)


def _load_record(skill_id: str) -> dict[str, Any]:
    path = _skill_path(skill_id)
    if not path.exists():
        raise KeyError(f"Unknown agent skill: {skill_id}")
    record = _read_json(path)
    record.setdefault("schema", SKILL_SCHEMA)
    record.setdefault("versions", [])
    return record


def _save_record(record: dict[str, Any]) -> Path:
    _ensure_dirs()
    skill = record["skill"]
    path = _skill_path(skill["skill_id"])
    record["schema"] = SKILL_SCHEMA
    record["updated_at"] = _now()
    _write_json(path, record)

    registry = _load_registry()
    registry.setdefault("skills", {})[skill["skill_id"]] = {
        "skill_id": skill["skill_id"],
        "name": skill.get("name", ""),
        "status": skill.get("status", ""),
        "version": skill.get("version", 0),
        "source_wiki_path": skill.get("source_wiki_path", ""),
        "source_type": skill.get("source_type", ""),
        "source_skill_path": skill.get("source_skill_path", ""),
        "managed_skill_dir": skill.get("managed_skill_dir", ""),
        "asset_count": skill.get("asset_count", 0),
        "tool_count": len(skill.get("tool_allowlist", [])),
        "updated_at": record["updated_at"],
        "path": str(path),
    }
    _save_registry(registry)
    return path


def _prompt_template_from_skill(skill: dict[str, Any], wiki_content: str) -> dict[str, Any]:
    prompt_body = wiki_content.strip()
    if len(prompt_body) > 12000:
        prompt_body = prompt_body[:11800].rstrip() + "\n\n... omitted from active skill prompt ..."
    return {
        "template_id": skill["skill_id"],
        "status": skill["status"],
        "source_skill_id": skill["skill_id"],
        "source_version": skill.get("version", 0),
        "source_wiki_path": skill.get("source_wiki_path", ""),
        "saved_at": _now(),
        "role": skill.get("role", skill.get("name", "")),
        "goal": skill.get("goal", ""),
        "scenarios": skill.get("scenarios", []),
        "tools": skill.get("tool_allowlist", []),
        "output_schema": skill.get("output_schema", []),
        "prompt": (
            f"你是{skill.get('role', skill.get('name', '可复用 Agent Skill'))}。\n"
            f"目标：{skill.get('goal', '')}\n"
            f"适用场景：{', '.join(skill.get('scenarios', []))}\n"
            f"允许工具：{', '.join(skill.get('tool_allowlist', []))}\n"
            f"输出字段：{', '.join(skill.get('output_schema', []))}\n"
            "必须遵守下方业务规则；数据不足时列出缺口；实时 ERP 只作为只读兜底；高风险动作必须要求人工确认。\n\n"
            f"{prompt_body}"
        ),
    }


def _template_path(skill_id: str) -> Path:
    return TEMPLATE_DIR / f"{_slugify(skill_id, 'agent-skill')}.json"


def _sync_template_from_record(record: dict[str, Any]) -> Path:
    skill = record["skill"]
    template = _prompt_template_from_skill(skill, str(record.get("wiki_content", "")))
    path = _template_path(skill["skill_id"])
    _write_json(path, template)
    return path


def create_agent_skill_from_wiki(
    wiki_path: str,
    skill_id: str = "",
    name: str = "",
    scenarios_json: str = "",
    tool_allowlist_json: str = "",
    output_schema_json: str = "",
    created_by: str = "agent",
) -> str:
    """把高复用 wiki 页面注册成 draft Agent Skill，默认不会启用。"""
    source_path = _resolve_wiki_path(wiki_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Wiki page not found: {wiki_path}")
    content = source_path.read_text(encoding="utf-8", errors="ignore")
    title = _title_from_markdown(content, source_path.stem)
    normalized_id = _slugify(skill_id or _stable_id(title), "agent-skill")
    scenarios = _as_list(scenarios_json) or ["经营分析", "辅助决策"]
    requested_tools = _as_list(tool_allowlist_json) or ["summarize_business_data", "query_fact_layer", "query_lightrag"]
    preview = _skill_permission_preview(requested_tools)
    now = _now()
    skill = {
        "skill_id": normalized_id,
        "name": name or title,
        "role": name or title,
        "goal": f"复用 wiki 页面《{title}》中的业务规则、口径和执行边界。",
        "status": "draft",
        "version": 0,
        "source_wiki_path": _relative_wiki_path(source_path),
        "scenarios": scenarios,
        "tool_allowlist": preview["approved_tools"],
        "output_schema": _as_list(output_schema_json) or list(DEFAULT_OUTPUT_SCHEMA),
        "permission_preview": preview,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    record = {"schema": SKILL_SCHEMA, "skill": skill, "versions": [], "wiki_content": content}
    path = _save_record(record)
    record_audit_event(
        "agent_skill_drafted",
        actor=created_by,
        summary=f"Drafted agent skill: {skill['name']}",
        task_id=skill["skill_id"],
        paths=[str(path), str(source_path)],
        risks=preview["risks"],
        metadata={"skill_id": skill["skill_id"], "status": "draft", "tool_allowlist": skill["tool_allowlist"]},
    )
    return _json({"status": "draft", "registry_path": str(path), "skill": skill})


def approve_agent_skill(skill_id: str, approved_by: str = "agent", decision: str = "") -> str:
    """审批 draft Agent Skill；无 decision 时返回 Agent Inbox 人工确认请求。"""
    record = _load_record(skill_id)
    skill = copy.deepcopy(record["skill"])
    if skill.get("status") == "active":
        return _json({"status": "success", "registry_path": str(_skill_path(skill_id)), "skill": skill})
    if not decision:
        approval = request_human_approval(
            action_name="approve_agent_skill",
            args={"skill_id": skill_id, "name": skill.get("name", ""), "target_status": "active"},
            description=f"启用可复用 Agent Skill：{skill.get('name', skill_id)}",
            destructive_effects=["启用后，Agent 可在匹配场景中复用该业务规则和 prompt template。"],
            metadata={"skill_id": skill_id, "source_wiki_path": skill.get("source_wiki_path", "")},
        )
        return _json(approval)
    if decision.strip().lower() not in {"approve", "approved", "yes", "true"}:
        skill["status"] = "draft"
        skill["last_rejected_by"] = approved_by
        skill["last_rejected_at"] = _now()
        record["skill"] = skill
        path = _save_record(record)
        return _json({"status": "rejected", "registry_path": str(path), "skill": skill})

    now = _now()
    skill["status"] = "active"
    skill["version"] = max(1, int(skill.get("version", 0)) + 1)
    skill["approved_by"] = approved_by
    skill["approved_at"] = now
    skill["updated_at"] = now
    skill["human_confirmation"] = {"approved_by": approved_by, "approved_at": now}
    record["skill"] = skill
    record.setdefault("versions", []).append(copy.deepcopy(skill))
    path = _save_record(record)

    template_path = _sync_template_from_record(record)
    record_audit_event(
        "agent_skill_approved",
        actor=approved_by,
        summary=f"Approved agent skill: {skill['name']}",
        task_id=skill["skill_id"],
        paths=[str(path), str(template_path)],
        risks=skill.get("permission_preview", {}).get("risks", []),
        metadata={"skill_id": skill["skill_id"], "status": "active", "version": skill["version"]},
    )
    return _json({"status": "success", "registry_path": str(path), "template_path": str(template_path), "skill": skill})


def update_agent_skill(skill_id: str, updates_json: str = "", updated_by: str = "agent") -> str:
    """更新 Agent Skill 可变字段并创建新版本。"""
    record = _load_record(skill_id)
    current = copy.deepcopy(record["skill"])
    if current.get("status") == "archived":
        raise ValueError(f"Cannot update archived agent skill: {skill_id}")
    updates = _parse_jsonish(updates_json, {})
    if not isinstance(updates, dict):
        raise ValueError("updates_json must decode to a JSON object")
    mutable_fields = {"goal", "name", "output_schema", "role", "scenarios", "tool_allowlist"}
    next_skill = copy.deepcopy(current)
    for field, value in updates.items():
        if field not in mutable_fields:
            continue
        if field in {"output_schema", "scenarios", "tool_allowlist"}:
            next_skill[field] = _as_list(value)
        else:
            next_skill[field] = str(value)
    preview = _skill_permission_preview([str(item) for item in next_skill.get("tool_allowlist", [])])
    next_skill["tool_allowlist"] = preview["approved_tools"]
    next_skill["permission_preview"] = preview
    next_skill["version"] = int(current.get("version", 0)) + 1
    next_skill["previous_version"] = int(current.get("version", 0))
    next_skill["updated_by"] = updated_by
    next_skill["updated_at"] = _now()
    record["skill"] = next_skill
    record.setdefault("versions", []).append(copy.deepcopy(next_skill))
    path = _save_record(record)
    template_path = _sync_template_from_record(record) if next_skill.get("status") == "active" else ""
    record_audit_event(
        "agent_skill_updated",
        actor=updated_by,
        summary=f"Updated agent skill: {next_skill.get('name', skill_id)}",
        task_id=skill_id,
        paths=[str(path)] + ([str(template_path)] if template_path else []),
        risks=preview["risks"],
        metadata={"skill_id": skill_id, "version": next_skill["version"], "updated_fields": sorted(set(updates) & mutable_fields)},
    )
    return _json({"status": "success", "registry_path": str(path), "template_path": str(template_path), "skill": next_skill})


def rollback_agent_skill(skill_id: str, target_version: int, changed_by: str = "agent") -> str:
    """从历史版本创建新的 active 版本。"""
    record = _load_record(skill_id)
    versions = record.get("versions", [])
    target = None
    for version in versions:
        if int(version.get("version", -1)) == int(target_version):
            target = copy.deepcopy(version)
            break
    if target is None:
        raise ValueError(f"Version {target_version} not found for agent skill: {skill_id}")
    current = record["skill"]
    now = _now()
    target["status"] = "active"
    target["version"] = int(current.get("version", 0)) + 1
    target["previous_version"] = int(target_version)
    target["rolled_back_by"] = changed_by
    target["rolled_back_at"] = now
    target["updated_at"] = now
    record["skill"] = target
    record.setdefault("versions", []).append(copy.deepcopy(target))
    path = _save_record(record)
    template_path = _sync_template_from_record(record)
    record_audit_event(
        "agent_skill_rolled_back",
        actor=changed_by,
        summary=f"Rolled back agent skill to version {target_version}: {target.get('name', skill_id)}",
        task_id=skill_id,
        paths=[str(path), str(template_path)],
        metadata={"skill_id": skill_id, "target_version": int(target_version), "new_version": target["version"]},
    )
    return _json({"status": "success", "registry_path": str(path), "template_path": str(template_path), "skill": target})


def set_agent_skill_status(skill_id: str, status: str, changed_by: str = "agent") -> str:
    """启用、暂停、禁用或归档 Agent Skill，不改变 prompt 内容版本。"""
    normalized = status.strip().lower()
    if normalized not in VALID_SKILL_STATUSES:
        raise ValueError(f"Invalid agent skill status: {status}. Expected one of: {', '.join(sorted(VALID_SKILL_STATUSES))}")
    record = _load_record(skill_id)
    skill = copy.deepcopy(record["skill"])
    skill["status"] = normalized
    skill["status_changed_by"] = changed_by
    skill["status_changed_at"] = _now()
    skill["updated_at"] = skill["status_changed_at"]
    record["skill"] = skill
    path = _save_record(record)
    template_path = _template_path(skill_id)
    if template_path.exists():
        template = _read_json(template_path)
        template["status"] = normalized
        template["status_changed_at"] = skill["status_changed_at"]
        _write_json(template_path, template)
    record_audit_event(
        "agent_skill_status_changed",
        actor=changed_by,
        summary=f"Changed agent skill status to {normalized}: {skill.get('name', skill_id)}",
        task_id=skill_id,
        paths=[str(path)] + ([str(template_path)] if template_path.exists() else []),
        metadata={"skill_id": skill_id, "status": normalized, "version": skill.get("version", 0)},
    )
    return _json({"status": "success", "registry_path": str(path), "skill": skill})


def get_agent_skill(skill_id: str, include_versions: bool = False) -> str:
    """读取单个 Agent Skill 注册记录。"""
    record = _load_record(skill_id)
    payload: dict[str, Any] = {"status": "success", "registry_path": str(_skill_path(skill_id)), "skill": record["skill"]}
    if include_versions:
        payload["versions"] = record.get("versions", [])
    return _json(payload)


def list_agent_skills(status: str = "", limit: int = 100) -> str:
    """列出 Agent Skill 注册表。"""
    registry = _load_registry()
    skills = list(registry.get("skills", {}).values())
    if status:
        skills = [skill for skill in skills if skill.get("status") == status]
    skills = sorted(skills, key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return _json({"status": "success", "registry_path": str(_registry_path()), "skills": skills[: max(0, int(limit))]})
