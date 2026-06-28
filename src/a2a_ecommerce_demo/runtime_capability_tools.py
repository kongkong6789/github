from __future__ import annotations

import importlib
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from src.a2a_ecommerce_demo.agent_tool_registry import (
    AGENT_TOOL_ALLOWLISTS,
    TOOL_REGISTRY,
    ToolEntry,
)
from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event
from src.a2a_ecommerce_demo.mcp_governance_tools import (
    MCP_POLICY_PATH,
    check_mcp_tool_permission,
    list_mcp_tool_policy,
    request_mcp_write_approval,
)
from src.a2a_ecommerce_demo.skill_registry_tools import get_agent_skill, list_agent_skills

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
TEMPLATE_DIR = Path(os.getenv("A2A_AGENT_TEMPLATE_DIR", DATA_DIR / "agent_templates")).resolve()
CAPABILITY_SCHEMA = "a2a_runtime_capability_registry_v1"
MCP_POLICY_ACTIONS = {"read", "query", "preview", "write", "create", "update", "delete"}
MCP_POLICY_EXECUTION_MODES = {"mcp_jsonrpc_tool", "approval_request_only", "blocked_unknown_tool"}
MCP_POLICY_RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_args(args_json: str = "") -> dict[str, Any]:
    if not args_json.strip():
        return {}
    try:
        value = json.loads(args_json)
    except json.JSONDecodeError as exc:
        raise ValueError("args_json must be a JSON object.") from exc
    if not isinstance(value, dict):
        raise ValueError("args_json must be a JSON object.")
    return value


def _parse_json_object(value: str, *, field_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value) if value.strip() else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be a JSON object.") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object.")
    return parsed


def _strict_bool(value: Any, *, field_name: str, default: bool | None = None) -> bool:
    if value is None and default is not None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a JSON boolean.")


def _strict_text_list(value: Any, *, field_name: str, default: list[str]) -> list[str]:
    raw = default if value is None else value
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{field_name} must be a JSON string array.")
    return [item.strip() for item in raw if item.strip()]


def _validated_runtime_mcp_policy(raw_rule: dict[str, Any], tool_name: str) -> dict[str, Any]:
    read_only = _strict_bool(raw_rule.get("read_only"), field_name="read_only", default=True)
    action = str(raw_rule.get("action") or ("read" if read_only else "write")).strip().lower()
    if action not in MCP_POLICY_ACTIONS:
        raise ValueError(f"action must be one of: {', '.join(sorted(MCP_POLICY_ACTIONS))}.")
    execution_mode = str(raw_rule.get("execution_mode") or "mcp_jsonrpc_tool").strip()
    if execution_mode not in MCP_POLICY_EXECUTION_MODES:
        raise ValueError(f"execution_mode must be one of: {', '.join(sorted(MCP_POLICY_EXECUTION_MODES))}.")
    requires_confirmation = _strict_bool(
        raw_rule.get("requires_human_confirmation"),
        field_name="requires_human_confirmation",
        default=not read_only,
    )
    if not read_only:
        requires_confirmation = True
    risk_level = str(raw_rule.get("risk_level") or ("low" if read_only else "high")).strip().lower()
    if risk_level not in MCP_POLICY_RISK_LEVELS:
        raise ValueError(f"risk_level must be one of: {', '.join(sorted(MCP_POLICY_RISK_LEVELS))}.")
    data_sources = _strict_text_list(raw_rule.get("data_sources"), field_name="data_sources", default=["uploaded_mcp"])
    allowed_callers = [
        caller
        for caller in _strict_text_list(
            raw_rule.get("allowed_callers"),
            field_name="allowed_callers",
            default=["top_company_brain_supervisor", "agent_factory_agent"],
        )
        if caller != "agent"
    ]
    if not allowed_callers:
        raise ValueError("allowed_callers must include at least one explicit non-agent caller.")
    destructive_effects = _strict_text_list(
        raw_rule.get("destructive_effects"),
        field_name="destructive_effects",
        default=[] if read_only else ["用户上传 MCP/API 写入工具，默认需要人工确认。"],
    )
    policy_rule = {
        **raw_rule,
        "description": str(raw_rule.get("description") or f"Runtime MCP/API tool: {tool_name}"),
        "action": action,
        "read_only": read_only,
        "external_write_enabled": False,
        "execution_mode": execution_mode,
        "requires_human_confirmation": requires_confirmation,
        "risk_level": risk_level,
        "data_sources": data_sources,
        "allowed_callers": allowed_callers,
        "destructive_effects": destructive_effects,
    }
    if policy_rule.get("mcp_url") is not None:
        policy_rule["mcp_url"] = str(policy_rule.get("mcp_url") or "").strip()
    if policy_rule.get("mcp_url_env") is not None:
        policy_rule["mcp_url_env"] = str(policy_rule.get("mcp_url_env") or "").strip()
    if policy_rule.get("mcp_tool_name") is not None:
        policy_rule["mcp_tool_name"] = str(policy_rule.get("mcp_tool_name") or "").strip()
    return policy_rule


def _maybe_parse_result(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _safe_error_text(value: Any) -> str:
    text = str(value or "")[:800]
    patterns = [
        r"(?i)(api[_-]?key|token|secret|password|authorization|cookie)(['\"=:\s]+)[^,'\"\s]+",
        r"sk-[A-Za-z0-9_-]{12,}",
        r"tp-[A-Za-z0-9_-]{12,}",
    ]
    for pattern in patterns:
        text = re.sub(pattern, lambda match: f"{match.group(1)}{match.group(2)}***REDACTED***" if match.lastindex and match.lastindex >= 2 else "***REDACTED***", text)
    return text


def _capability_parts(capability_id: str) -> tuple[str, str]:
    if ":" in capability_id:
        kind, name = capability_id.split(":", 1)
        return kind.strip().lower(), name.strip()
    if capability_id in TOOL_REGISTRY:
        return "tool", capability_id
    skills = json.loads(list_agent_skills(limit=1000)).get("skills", [])
    if any(item.get("skill_id") == capability_id for item in skills):
        return "skill", capability_id
    return "mcp", capability_id


def _visible_agents(tool_name: str) -> list[str]:
    return sorted(agent for agent, allowlist in AGENT_TOOL_ALLOWLISTS.items() if tool_name in allowlist)


def _tool_capabilities() -> list[dict[str, Any]]:
    return [
        {
            "capability_id": f"tool:{name}",
            "type": "local_tool",
            "name": name,
            "description": entry.description,
            "read_only": entry.read_only,
            "requires_confirmation": entry.requires_confirmation,
            "risk_level": entry.risk_level,
            "execution_mode": "local_python_tool",
            "data_sources": list(entry.data_sources),
            "owner_module": entry.owner_module,
            "visible_agents": _visible_agents(name),
            "status": "available",
        }
        for name, entry in sorted(TOOL_REGISTRY.items())
    ]


def _skill_capabilities(status: str = "", limit: int = 1000) -> list[dict[str, Any]]:
    skills = json.loads(list_agent_skills(status=status, limit=limit)).get("skills", [])
    return [
        {
            "capability_id": f"skill:{skill.get('skill_id', '')}",
            "type": "agent_skill",
            "name": skill.get("name", ""),
            "description": f"Agent Skill: {skill.get('name', skill.get('skill_id', ''))}",
            "read_only": True,
            "requires_confirmation": skill.get("status") != "active",
            "risk_level": "low",
            "execution_mode": "skill_prompt_bundle",
            "data_sources": ["wiki"],
            "owner_module": "skill_registry_tools",
            "visible_agents": ["all_agents"],
            "status": skill.get("status", ""),
            "skill_id": skill.get("skill_id", ""),
            "source_wiki_path": skill.get("source_wiki_path", ""),
            "source_type": skill.get("source_type", ""),
            "source_skill_path": skill.get("source_skill_path", ""),
            "managed_skill_dir": skill.get("managed_skill_dir", ""),
            "tool_count": skill.get("tool_count", 0),
        }
        for skill in skills
        if skill.get("skill_id")
    ]


def _mcp_capabilities() -> list[dict[str, Any]]:
    policy = json.loads(list_mcp_tool_policy())
    tools = policy.get("tools", {})
    capabilities = []
    for tool_name, rule in sorted(tools.items()):
        if not isinstance(rule, dict):
            continue
        capabilities.append(
            {
                "capability_id": f"mcp:{tool_name}",
                "type": "mcp_api",
                "name": tool_name,
                "description": rule.get("description", ""),
                "read_only": rule.get("read_only") is True,
                "requires_confirmation": rule.get("requires_human_confirmation") is True,
                "risk_level": rule.get("risk_level", "unknown"),
                "execution_mode": rule.get("execution_mode", ""),
                "data_sources": rule.get("data_sources", []),
                "owner_module": "mcp_governance_tools",
                "visible_agents": rule.get("allowed_callers", []),
                "status": "registered",
                "tool_name": tool_name,
            }
        )
    return capabilities


def list_runtime_capabilities(
    type_filter: str = "",
    status: str = "",
    include_tools: bool = True,
    include_skills: bool = True,
    include_mcp: bool = True,
    limit: int = 500,
) -> str:
    """列出当前运行时可发现的本地工具、active/draft Skill 和 MCP/API policy 能力。"""
    capabilities: list[dict[str, Any]] = []
    if include_tools:
        capabilities.extend(_tool_capabilities())
    if include_skills:
        capabilities.extend(_skill_capabilities(status=status or "", limit=1000))
    if include_mcp:
        capabilities.extend(_mcp_capabilities())
    if type_filter:
        capabilities = [item for item in capabilities if item.get("type") == type_filter]
    if status:
        capabilities = [item for item in capabilities if item.get("status") == status]
    capabilities = capabilities[: max(0, int(limit))]
    return _json(
        {
            "schema": CAPABILITY_SCHEMA,
            "status": "success",
            "mode": "runtime_capability_discovery",
            "summary": {
                "capability_count": len(capabilities),
                "read_only_count": sum(1 for item in capabilities if item.get("read_only")),
                "confirmation_required_count": sum(1 for item in capabilities if item.get("requires_confirmation")),
                "types": sorted({str(item.get("type", "")) for item in capabilities}),
            },
            "capabilities": capabilities,
        }
    )


def _load_tool_handler(entry: ToolEntry) -> Any:
    module = importlib.import_module(f"src.a2a_ecommerce_demo.{entry.owner_module}")
    handler = getattr(module, entry.handler, None)
    if handler is None:
        raise KeyError(f"Registered handler not found: {entry.owner_module}.{entry.handler}")
    return handler


def _audit_runtime_invocation(
    *,
    capability_id: str,
    capability_type: str,
    status: str,
    caller: str,
    args: dict[str, Any],
) -> None:
    try:
        record_audit_event(
            "runtime_capability_invoked",
            actor=caller,
            summary=f"{capability_id} {status}",
            metadata={
                "capability_id": capability_id,
                "capability_type": capability_type,
                "status": status,
                "arg_keys": sorted(args),
            },
        )
    except Exception:
        return


def _invoke_local_tool(capability_id: str, tool_name: str, args: dict[str, Any], caller: str) -> dict[str, Any]:
    entry = TOOL_REGISTRY[tool_name]
    allowed_callers = _visible_agents(tool_name)
    capability = {
        "capability_id": capability_id,
        "type": "local_tool",
        "tool_name": tool_name,
        "read_only": entry.read_only,
        "requires_confirmation": entry.requires_confirmation,
        "risk_level": entry.risk_level,
        "owner_module": entry.owner_module,
    }
    if allowed_callers and caller not in allowed_callers:
        _audit_runtime_invocation(
            capability_id=capability_id,
            capability_type="local_tool",
            status="not_allowed",
            caller=caller,
            args=args,
        )
        return {
            "status": "not_allowed",
            "mode": "local_tool_caller_gate",
            "requires_confirmation": True,
            "capability": capability,
            "permission": {
                "allowed": False,
                "caller": caller,
                "allowed_callers": allowed_callers,
                "reason": "caller is not allowed for this local tool",
            },
        }
    if not entry.read_only or entry.requires_confirmation:
        _audit_runtime_invocation(
            capability_id=capability_id,
            capability_type="local_tool",
            status="confirmation_required",
            caller=caller,
            args=args,
        )
        return {
            "status": "confirmation_required",
            "mode": "local_tool_confirmation_gate",
            "requires_confirmation": True,
            "capability": capability,
            "reason": "写入或需确认的本地工具不能通过 runtime capability 直接执行。",
        }
    handler = _load_tool_handler(entry)
    value = handler(**args)
    result = _maybe_parse_result(value)
    _audit_runtime_invocation(
        capability_id=capability_id,
        capability_type="local_tool",
        status="success",
        caller=caller,
        args=args,
    )
    return {
        "status": "success",
        "mode": "local_tool",
        "capability_id": capability_id,
        "capability": capability,
        "result": result,
    }


def _template_path(skill_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", str(skill_id)).strip("-")[:96]
    return TEMPLATE_DIR / f"{safe or 'agent-skill'}.json"


def _invoke_skill(capability_id: str, skill_id: str, args: dict[str, Any], caller: str) -> dict[str, Any]:
    record = json.loads(get_agent_skill(skill_id))
    skill = record["skill"]
    if skill.get("status") != "active":
        return {
            "status": "not_available",
            "mode": "skill_prompt_bundle",
            "requires_confirmation": True,
            "capability_id": capability_id,
            "skill": skill,
            "reason": "只有 active Skill 可以直接调用；draft/paused/disabled/archived 需要先审批或启用。",
        }
    template_path = _template_path(skill_id)
    template = json.loads(template_path.read_text(encoding="utf-8")) if template_path.exists() else {}
    prompt = str(template.get("prompt") or record.get("wiki_content") or "")
    user_task = str(args.get("user_task") or args.get("task") or args.get("query") or "")
    _audit_runtime_invocation(
        capability_id=capability_id,
        capability_type="agent_skill",
        status="success",
        caller=caller,
        args=args,
    )
    return {
        "status": "success",
        "mode": "skill_prompt_bundle",
        "capability_id": capability_id,
        "skill": skill,
        "template_path": str(template_path) if template_path.exists() else "",
        "source_type": skill.get("source_type", ""),
        "source_wiki_path": skill.get("source_wiki_path", ""),
        "source_skill_path": skill.get("source_skill_path", ""),
        "managed_skill_dir": skill.get("managed_skill_dir", ""),
        "prompt": prompt,
        "tool_allowlist": skill.get("tool_allowlist", []),
        "output_schema": skill.get("output_schema", []),
        "user_task": user_task,
        "usage_policy": "把 prompt bundle 作为本轮专用 Skill 指令；仍需遵守工具权限和数据缺口标注。",
    }


def _mcp_rule(tool_name: str) -> dict[str, Any]:
    policy = json.loads(list_mcp_tool_policy())
    rule = policy.get("tools", {}).get(tool_name)
    if not isinstance(rule, dict):
        raise KeyError(f"Unknown MCP/API capability: {tool_name}")
    return rule


def _mcp_url(rule: dict[str, Any]) -> str:
    url = str(rule.get("mcp_url") or "").strip()
    env_name = str(rule.get("mcp_url_env") or "").strip()
    if not url and env_name:
        url = str(os.getenv(env_name, "")).strip()
    return url


def _invoke_mcp_jsonrpc_tool(tool_name: str, rule: dict[str, Any], args: dict[str, Any]) -> Any:
    url = _mcp_url(rule)
    if not url:
        raise RuntimeError(f"MCP tool {tool_name} missing mcp_url or mcp_url_env.")
    mcp_tool_name = str(rule.get("mcp_tool_name") or tool_name)
    session = requests.Session()
    init_payload = {
        "jsonrpc": "2.0",
        "id": "init",
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "a2a-runtime", "version": "1"}},
    }
    init_response = session.post(url, json=init_payload, timeout=20)
    init_response.raise_for_status()
    initialized_response = session.post(
        url,
        json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        timeout=20,
    )
    initialized_response.raise_for_status()
    response = session.post(
        url,
        json={"jsonrpc": "2.0", "id": "call", "method": "tools/call", "params": {"name": mcp_tool_name, "arguments": args}},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"MCP tool call failed: {json.dumps(payload['error'], ensure_ascii=False)}")
    return payload.get("result", payload)


def _invoke_mcp(capability_id: str, tool_name: str, args: dict[str, Any], caller: str) -> dict[str, Any]:
    rule = _mcp_rule(tool_name)
    permission = json.loads(check_mcp_tool_permission(tool_name, str(rule.get("action", "read")), caller=caller))
    capability = {
        "capability_id": capability_id,
        "type": "mcp_api",
        "tool_name": tool_name,
        "read_only": rule.get("read_only") is True,
        "requires_confirmation": permission.get("requires_human_confirmation", True),
        "risk_level": rule.get("risk_level", "unknown"),
        "execution_mode": rule.get("execution_mode", ""),
    }
    if not permission.get("allowed"):
        approval = json.loads(
            request_mcp_write_approval(
                tool_name,
                str(rule.get("action", "write")),
                args_json=json.dumps(args, ensure_ascii=False),
                requested_by=caller,
            )
        )
        approval.update(
            {
                "capability_id": capability_id,
                "capability": capability,
                "permission": permission,
                "requires_confirmation": True,
            }
        )
        _audit_runtime_invocation(
            capability_id=capability_id,
            capability_type="mcp_api",
            status="confirmation_required",
            caller=caller,
            args=args,
        )
        return approval
    if tool_name in TOOL_REGISTRY:
        result = _invoke_local_tool(f"tool:{tool_name}", tool_name, args, caller)
        result["mode"] = "mcp_local_tool"
        result["capability_id"] = capability_id
        result["capability"] = capability
        result["permission"] = permission
        return result
    if rule.get("execution_mode") == "mcp_jsonrpc_tool":
        try:
            result = _invoke_mcp_jsonrpc_tool(tool_name, rule, args)
        except Exception as exc:
            _audit_runtime_invocation(
                capability_id=capability_id,
                capability_type="mcp_api",
                status="failed",
                caller=caller,
                args=args,
            )
            return {
                "status": "error",
                "mode": "mcp_jsonrpc_tool",
                "capability_id": capability_id,
                "capability": capability,
                "permission": permission,
                "error": _safe_error_text(exc),
            }
        _audit_runtime_invocation(
            capability_id=capability_id,
            capability_type="mcp_api",
            status="success",
            caller=caller,
            args=args,
        )
        return {
            "status": "success",
            "mode": "mcp_jsonrpc_tool",
            "capability_id": capability_id,
            "capability": capability,
            "permission": permission,
            "result": result,
        }
    return {
        "status": "not_executable",
        "mode": "mcp_policy_only",
        "capability_id": capability_id,
        "capability": capability,
        "permission": permission,
        "reason": "该 MCP/API policy 尚未配置本地 handler 或 mcp_jsonrpc_tool 执行参数。",
    }


def invoke_runtime_capability(
    capability_id: str,
    args_json: str = "",
    caller: str = "agent",
) -> str:
    """统一调用 runtime capability：只读直接执行，写入/高风险返回人工确认请求。"""
    args = _parse_args(args_json)
    kind, name = _capability_parts(capability_id)
    normalized_id = f"{kind}:{name}"
    if kind == "tool":
        if name not in TOOL_REGISTRY:
            raise KeyError(f"Unknown local tool capability: {name}")
        return _json(_invoke_local_tool(normalized_id, name, args, caller))
    if kind == "skill":
        return _json(_invoke_skill(normalized_id, name, args, caller))
    if kind in {"mcp", "api"}:
        return _json(_invoke_mcp(f"mcp:{name}", name, args, caller))
    raise ValueError(f"Unsupported capability type: {kind}")


def _load_policy_for_update() -> dict[str, Any]:
    if MCP_POLICY_PATH.exists():
        try:
            policy = json.loads(MCP_POLICY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            policy = {}
    else:
        policy = {}
    policy.setdefault("schema", "a2a_mcp_tool_policy_v1")
    policy.setdefault("policy_path", str(MCP_POLICY_PATH))
    policy.setdefault("tools", {})
    return policy


def _write_policy(policy: dict[str, Any]) -> None:
    MCP_POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MCP_POLICY_PATH.with_suffix(MCP_POLICY_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(MCP_POLICY_PATH)


def register_runtime_mcp_tool(
    tool_name: str,
    policy_json: str,
    registered_by: str = "agent",
) -> str:
    """登记用户上传/创建的 MCP/API 工具策略，使其进入 runtime capability discovery。"""
    normalized = tool_name.strip()
    if not normalized:
        raise ValueError("tool_name is required.")
    policy_rule = _validated_runtime_mcp_policy(
        _parse_json_object(policy_json, field_name="policy_json"),
        normalized,
    )

    policy = _load_policy_for_update()
    policy["tools"][normalized] = policy_rule
    _write_policy(policy)
    record_audit_event(
        "runtime_mcp_tool_registered",
        actor=registered_by,
        summary=f"Registered runtime MCP/API tool: {normalized}",
        paths=[str(MCP_POLICY_PATH)],
        metadata={
            "tool_name": normalized,
            "read_only": bool(policy_rule.get("read_only")),
            "execution_mode": policy_rule.get("execution_mode", ""),
            "requires_human_confirmation": bool(policy_rule.get("requires_human_confirmation")),
        },
    )
    return _json(
        {
            "status": "success",
            "tool_name": normalized,
            "policy_path": str(MCP_POLICY_PATH),
            "policy": policy_rule,
            "capability_id": f"mcp:{normalized}",
        }
    )
