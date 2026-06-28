from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event
from src.a2a_ecommerce_demo.human_approval_tools import request_human_approval

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
MCP_POLICY_PATH = Path(os.getenv("A2A_MCP_POLICY_PATH", DATA_DIR / "mcp" / "tool_policy.json")).resolve()

POLICY_SCHEMA = "a2a_mcp_tool_policy_v1"

DEFAULT_MCP_TOOL_POLICY: dict[str, dict[str, Any]] = {
    "query_erp_live_snapshot": {
        "description": "吉客云/金蝶实时只读 ERP 查询。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_query",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["jackyun_erp", "kingdee_erp"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "inventory_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "list_erp_live_query_capabilities": {
        "description": "列出吉客云/金蝶实时只读查询能力。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_query",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["jackyun_erp", "kingdee_erp"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "inventory_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "test_erp_live_connection": {
        "description": "只读测试吉客云/金蝶实时连接配置。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_connection_test",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["jackyun_erp", "kingdee_erp"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "inventory_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "route_erp_live_query": {
        "description": "确定性规划吉客云/金蝶/企业微信智能表/DuckDB 的只读查询路线。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_route_planning",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["jackyun_erp", "kingdee_erp", "WeCom_smartsheet", "duckdb"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "inventory_agent",
            "finance_agent",
            "financial_planning_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "query_inventory_cost_reference": {
        "description": "只读组合查询吉客云库存、吉客云批次/采购和金蝶采购订单价，输出库存成本/采购价参考。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_composed_query",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["jackyun_erp", "kingdee_erp"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "inventory_agent",
            "finance_agent",
            "financial_planning_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "query_jackyun_channel_sales_summary": {
        "description": "只读调用吉客云 Skill 销售汇总工作流，按日期、渠道/店铺、SKU 返回销量和金额。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_composed_query",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["jackyun_erp"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "inventory_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "verify_erp_supplier_terms_mapping": {
        "description": "只读验证吉客云/金蝶供应商交期、采购价和历史延误字段映射。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_query",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["jackyun_erp", "kingdee_erp"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "inventory_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "list_wecom_smartsheet_sources": {
        "description": "列出企业微信智能表 MCP 数据源配置。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_mcp_metadata",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["WeCom_smartsheet"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "query_wecom_smartsheet_records": {
        "description": "通过 WeDoc MCP 只读查询企业微信智能表记录。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_mcp_query",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["WeCom_smartsheet"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "test_wecom_smartsheet_connection": {
        "description": "只读测试企业微信智能表 MCP 连接。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_mcp_connection_test",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["WeCom_smartsheet"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "data_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "sync_wecom_smartsheet_snapshot": {
        "description": "把企业微信智能表只读快照写入本地 staging/DuckDB。",
        "action": "write_local_snapshot",
        "read_only": False,
        "external_write_enabled": False,
        "execution_mode": "local_snapshot_only",
        "requires_human_confirmation": True,
        "risk_level": "medium",
        "data_sources": ["local_staging", "duckdb", "WeCom_smartsheet"],
        "allowed_callers": ["auto_workflow_agent"],
        "destructive_effects": ["写入本地 WeCom snapshot 并注册 DuckDB fact layer。"],
    },
    "sync_connector_dataset": {
        "description": "把已获取的只读 ERP 快照注册进本地 staging/DuckDB。",
        "action": "write_local_snapshot",
        "read_only": False,
        "external_write_enabled": False,
        "execution_mode": "local_snapshot_only",
        "requires_human_confirmation": True,
        "risk_level": "medium",
        "data_sources": ["local_staging", "duckdb"],
        "allowed_callers": ["auto_workflow_agent"],
        "destructive_effects": ["写入本地 connector snapshot 并注册 DuckDB fact layer。"],
    },
    "agent_reach_get_status": {
        "description": "只读检查 Agent-Reach 外部公开资料能力状态。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_agent_reach_status",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["agent_reach"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "knowledge_agent",
            "data_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "agent_reach_read_public_web": {
        "description": "通过 Agent-Reach 只读读取公开网页内容。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_agent_reach_public_web",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["agent_reach_public_web"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "knowledge_agent",
            "data_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "agent_reach_search_public_sources": {
        "description": "通过 Agent-Reach 只读搜索公开网页、RSS、GitHub 和公开社区资料。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_agent_reach_public_search",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["agent_reach_public_search"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "knowledge_agent",
            "data_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "agent_reach_read_video_transcript": {
        "description": "通过 Agent-Reach 只读提取公开视频字幕和播客转写。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_agent_reach_public_video",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["agent_reach_public_video"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "knowledge_agent",
            "data_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
    },
    "agent_reach_read_logged_in_social": {
        "description": "通过 Agent-Reach 读取需登录态的平台公开内容；仅在人工确认专用账号和 Cookie 边界后允许。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_agent_reach_logged_in_social",
        "requires_human_confirmation": True,
        "risk_level": "medium",
        "data_sources": ["agent_reach_social"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "knowledge_agent",
            "data_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [
            "需要专用账号或浏览器登录态，禁止使用主账号 Cookie，禁止发帖、评论、点赞或私信。"
        ],
    },
    "create_purchase_order": {
        "description": "创建采购单，当前只允许生成审批请求，不允许直接执行。",
        "action": "write_external_erp",
        "read_only": False,
        "external_write_enabled": False,
        "execution_mode": "approval_request_only",
        "requires_human_confirmation": True,
        "risk_level": "high",
        "data_sources": ["erp"],
        "allowed_callers": ["auto_workflow_agent"],
        "destructive_effects": ["创建采购单会影响 ERP 业务单据。"],
    },
    "update_ad_budget": {
        "description": "修改广告预算，当前只允许生成审批请求，不允许直接执行。",
        "action": "write_external_ad_platform",
        "read_only": False,
        "external_write_enabled": False,
        "execution_mode": "approval_request_only",
        "requires_human_confirmation": True,
        "risk_level": "high",
        "data_sources": ["ad_platform"],
        "allowed_callers": ["auto_workflow_agent"],
        "destructive_effects": ["修改广告预算会影响实际花费。"],
    },
    "send_external_message": {
        "description": "外发消息，当前只允许生成审批请求，不允许直接执行。",
        "action": "write_external_message",
        "read_only": False,
        "external_write_enabled": False,
        "execution_mode": "approval_request_only",
        "requires_human_confirmation": True,
        "risk_level": "high",
        "data_sources": ["external_messaging"],
        "allowed_callers": ["auto_workflow_agent"],
        "destructive_effects": ["外发消息会触达外部人员或客户。"],
    },
    "supermemory_profile": {
        "description": "读取 Supermemory 用户/团队 profile，上下文只用于偏好和项目状态，不作为经营证据。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "mcp_jsonrpc_tool",
        "mcp_tool_name": "profile",
        "mcp_url_env": "SUPERMEMORY_MCP_URL",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["external_memory"],
        "allowed_callers": ["top_company_brain_supervisor", "agent_factory_agent"],
        "destructive_effects": [],
        "evidence_policy": "context_only_not_business_evidence",
    },
    "supermemory_recall": {
        "description": "只读召回 Supermemory 记忆，上下文不能写入 evidence 字段。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "mcp_jsonrpc_tool",
        "mcp_tool_name": "recall",
        "mcp_url_env": "SUPERMEMORY_MCP_URL",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["external_memory"],
        "allowed_callers": ["top_company_brain_supervisor", "agent_factory_agent"],
        "destructive_effects": [],
        "evidence_policy": "context_only_not_business_evidence",
    },
    "supermemory_context": {
        "description": "只读获取 Supermemory context，作为 supervisor pre-context，不替代 DuckDB/ERP/wiki/LightRAG。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "mcp_jsonrpc_tool",
        "mcp_tool_name": "context",
        "mcp_url_env": "SUPERMEMORY_MCP_URL",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["external_memory"],
        "allowed_callers": ["top_company_brain_supervisor", "agent_factory_agent"],
        "destructive_effects": [],
        "evidence_policy": "context_only_not_business_evidence",
    },
    "supermemory_save_memory": {
        "description": "写入 Supermemory 记忆请求；必须先人工确认并通过敏感字段扫描。",
        "action": "write_external_memory",
        "read_only": False,
        "external_write_enabled": False,
        "execution_mode": "approval_request_only",
        "mcp_tool_name": "save_memory",
        "mcp_url_env": "SUPERMEMORY_MCP_URL",
        "requires_human_confirmation": True,
        "risk_level": "high",
        "data_sources": ["external_memory"],
        "allowed_callers": ["top_company_brain_supervisor"],
        "destructive_effects": ["会把用户确认后的长期记忆写入 hosted Supermemory。"],
        "blocked_sensitive_data": [
            "ERP 行级数据",
            "客户信息",
            "采购价",
            "供应商报价",
            "财务明细",
            "库存明细",
            "私密智能表 URL",
        ],
        "evidence_policy": "memory_write_never_business_evidence",
    },
    "query_external_platform_readonly": {
        "description": "只读访问可选 RuoYi AI / MaxKB / MiroFish sidecar；输出只能作为补充上下文，不能替代 DuckDB/wiki/LightRAG/ERP 证据。",
        "action": "read",
        "read_only": True,
        "external_write_enabled": False,
        "execution_mode": "read_only_sidecar_proxy",
        "requires_human_confirmation": False,
        "risk_level": "low",
        "data_sources": ["reference_platform"],
        "allowed_callers": [
            "top_company_brain_supervisor",
            "knowledge_agent",
            "decision_agent",
            "company_strategy_agent",
            "auto_workflow_agent",
            "agent_factory_agent",
        ],
        "destructive_effects": [],
        "evidence_policy": "context_only_not_business_evidence",
    },
}


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_policy(*, persist: bool = False) -> dict[str, Any]:
    if MCP_POLICY_PATH.exists():
        try:
            policy = json.loads(MCP_POLICY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            policy = {}
    else:
        policy = {}
    policy.setdefault("schema", POLICY_SCHEMA)
    policy.setdefault("policy_path", str(MCP_POLICY_PATH))
    existing_tools = policy.setdefault("tools", {})
    for name, rule in DEFAULT_MCP_TOOL_POLICY.items():
        current = existing_tools.setdefault(name, copy.deepcopy(rule))
        for key, value in rule.items():
            if key in current and isinstance(current[key], list) and isinstance(value, list):
                for item in value:
                    if item not in current[key]:
                        current[key].append(copy.deepcopy(item))
            else:
                current.setdefault(key, copy.deepcopy(value))
        current["external_write_enabled"] = False
    if persist:
        _write_json(MCP_POLICY_PATH, policy)
    return policy


def _parse_args(args_json: str) -> dict[str, Any]:
    if not args_json.strip():
        return {}
    try:
        value = json.loads(args_json)
    except json.JSONDecodeError as exc:
        raise ValueError("args_json must be a JSON object.") from exc
    if not isinstance(value, dict):
        raise ValueError("args_json must be a JSON object.")
    return value


def _summarize_args(args: dict[str, Any]) -> dict[str, Any]:
    redacted_keys = {"api_key", "apikey", "password", "secret", "token", "access_token", "refresh_token"}
    summary: dict[str, Any] = {}
    for key, value in args.items():
        lowered = key.lower()
        if lowered in redacted_keys or any(secret_word in lowered for secret_word in ["secret", "token", "password"]):
            summary[key] = "***REDACTED***"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
        elif isinstance(value, list):
            summary[key] = f"list[{len(value)}]"
        elif isinstance(value, dict):
            summary[key] = f"object[{len(value)}]"
        else:
            summary[key] = type(value).__name__
    return summary


def _tool_rule(tool_name: str) -> dict[str, Any]:
    policy = _load_policy()
    tools = policy.get("tools", {})
    rule = tools.get(tool_name)
    if not isinstance(rule, dict):
        return {
            "description": "Unknown MCP/API tool.",
            "action": "unknown",
            "read_only": False,
            "external_write_enabled": False,
            "execution_mode": "blocked_unknown_tool",
            "requires_human_confirmation": True,
            "risk_level": "unknown",
            "data_sources": [],
            "allowed_callers": [],
            "destructive_effects": ["未知工具默认阻断，需先登记权限策略。"],
        }
    return rule


def list_mcp_tool_policy() -> str:
    """列出 MCP/API 工具权限配置。"""
    return _json(_load_policy())


def _policy_bool(value: Any) -> bool:
    return value is True


def _policy_callers(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def check_mcp_tool_permission(tool_name: str, action: str = "read", caller: str = "top_company_brain_supervisor") -> str:
    """检查 MCP/API 工具是否可直接执行，写入类默认只返回人工确认要求。"""
    rule = _tool_rule(tool_name)
    normalized_action = action.strip().lower()
    allowed_callers = _policy_callers(rule.get("allowed_callers"))
    caller_allowed = "*" in allowed_callers or caller in allowed_callers
    read_allowed = _policy_bool(rule.get("read_only")) and normalized_action in {"read", "query", "preview"}
    requires_confirmation = _policy_bool(rule.get("requires_human_confirmation")) or not read_allowed or not caller_allowed
    allowed = read_allowed and caller_allowed and not requires_confirmation
    return _json(
        {
            "tool_name": tool_name,
            "action": normalized_action,
            "mode": "read" if read_allowed else "write_or_unknown",
            "caller": caller,
            "allowed": allowed,
            "read_only": _policy_bool(rule.get("read_only")),
            "external_write_enabled": _policy_bool(rule.get("external_write_enabled")),
            "execution_mode": rule.get("execution_mode", ""),
            "requires_human_confirmation": requires_confirmation,
            "risk_level": rule.get("risk_level", "unknown"),
            "data_sources": rule.get("data_sources", []),
            "return_data_sources": rule.get("data_sources", []),
            "blocked_reason": ""
            if allowed
            else "caller is not allowed" if not caller_allowed else "write/unknown MCP/API tool requires human confirmation",
            "reason": "read-only MCP/API tool allowed"
            if allowed
            else "caller is not allowed" if not caller_allowed else "write/unknown MCP/API tool requires human confirmation",
            "policy": rule,
        }
    )


def request_mcp_write_approval(
    tool_name: str,
    action: str,
    args_json: str = "",
    description: str = "",
    requested_by: str = "agent",
) -> str:
    """为写入类 MCP/API 工具生成 Agent Inbox 人工确认请求。"""
    rule = _tool_rule(tool_name)
    args = _parse_args(args_json)
    check = json.loads(check_mcp_tool_permission(tool_name, action, caller=requested_by))
    if check["allowed"]:
        return _json({"status": "not_required", "requires_confirmation": False, "permission": check})
    approval = request_human_approval(
        action_name=tool_name,
        args={
            "tool_name": tool_name,
            "requested_action": action,
            "risk_level": rule.get("risk_level", "unknown"),
            "external_write_enabled": bool(rule.get("external_write_enabled", False)),
            "execution_mode": rule.get("execution_mode", ""),
            "permission": {
                "status": "allowed" if check.get("allowed") else "blocked",
                "requires_human_confirmation": check.get("requires_human_confirmation", True),
                "reason": check.get("reason", ""),
            },
            "parameter_summary": _summarize_args(args),
            "data_sources": rule.get("data_sources", []),
            "destructive_effects": rule.get("destructive_effects", []),
            "dry_run_preview": "This request only asks for human approval; no external MCP/API write is executed here.",
        },
        description=description or str(rule.get("description") or f"Confirm MCP/API action: {tool_name}"),
        destructive_effects=[str(item) for item in rule.get("destructive_effects", [])],
        metadata={
            "tool_name": tool_name,
            "action": action,
            "requested_by": requested_by,
            "risk_level": rule.get("risk_level", "unknown"),
            "execution_mode": rule.get("execution_mode", ""),
            "data_sources": rule.get("data_sources", []),
        },
        allowed_decisions=["edit", "approve", "reject"],
    )
    return _json(approval)


def record_mcp_tool_audit(
    tool_name: str,
    action: str,
    status: str,
    args_json: str = "",
    result_summary: str = "",
    actor: str = "agent",
) -> str:
    """记录 MCP/API 工具调用审计，参数会由企业审计工具统一脱敏。"""
    rule = _tool_rule(tool_name)
    args = _summarize_args(_parse_args(args_json))
    return record_audit_event(
        "mcp_tool_called",
        actor=actor,
        summary=result_summary or f"{tool_name} {action} {status}",
        risks=[str(rule.get("risk_level", "unknown"))],
        metadata={
            "tool_name": tool_name,
            "action": action,
            "status": status,
            "risk_level": rule.get("risk_level", "unknown"),
            "read_only": bool(rule.get("read_only")),
            "external_write_enabled": bool(rule.get("external_write_enabled", False)),
            "execution_mode": rule.get("execution_mode", ""),
            "requires_human_confirmation": bool(rule.get("requires_human_confirmation")),
            "data_sources": rule.get("data_sources", []),
            "args": args,
        },
    )
