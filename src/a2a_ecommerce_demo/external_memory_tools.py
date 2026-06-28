from __future__ import annotations

import json
import re
from typing import Any

from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event
from src.a2a_ecommerce_demo.human_approval_tools import request_human_approval

SENSITIVE_MEMORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ERP 行级数据", re.compile(r"\b(ERP|订单号|单据编号|出库单|入库单)\b", re.IGNORECASE)),
    ("客户信息", re.compile(r"(客户|手机号|手机|电话|1[3-9]\d{9})", re.IGNORECASE)),
    ("采购价", re.compile(r"(采购价|采购单价|采购成本|成本价)", re.IGNORECASE)),
    ("供应商报价", re.compile(r"(供应商报价|报价单|供应商价格)", re.IGNORECASE)),
    ("财务明细", re.compile(r"(财务明细|银行流水|付款账号|回款明细|现金流明细)", re.IGNORECASE)),
    ("库存明细", re.compile(r"(库存明细|库存数量|可用库存|锁定待发)", re.IGNORECASE)),
    ("私密智能表 URL", re.compile(r"doc\.weixin\.qq\.com/(?:smartsheet|sheet)", re.IGNORECASE)),
)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _preview(text: str, limit: int = 600) -> str:
    stripped = " ".join(str(text or "").split())
    return stripped[:limit]


def scan_external_memory_payload(content: str) -> str:
    """Scan hosted-memory content for data that must never leave the local workspace."""
    text = str(content or "")
    categories = [label for label, pattern in SENSITIVE_MEMORY_RULES if pattern.search(text)]
    return _json(
        {
            "status": "success",
            "blocked": bool(categories),
            "blocked_categories": categories,
            "policy": "external_memory_context_only",
        }
    )


def request_external_memory_save(
    content: str,
    *,
    container_tag: str = "",
    source: str = "",
    requested_by: str = "agent",
) -> str:
    """Create a confirmation request for hosted memory writes, or block sensitive content locally."""
    scan = json.loads(scan_external_memory_payload(content))
    if scan["blocked"]:
        record_audit_event(
            "external_memory_blocked_sensitive",
            actor=requested_by,
            summary="Blocked hosted memory save because sensitive business details were detected.",
            risk_level="high",
            data_sources=["external_memory"],
            risks=scan["blocked_categories"],
            metadata={
                "container_tag": container_tag,
                "source": source,
                "blocked_categories": scan["blocked_categories"],
            },
        )
        return _json(
            {
                "status": "blocked_sensitive",
                "requires_confirmation": False,
                "scan": scan,
                "reason": "Hosted Supermemory cannot receive ERP rows, customer data, prices, financial details, inventory details, or private smartsheet URLs.",
            }
        )

    approval = request_human_approval(
        action_name="supermemory_save_memory",
        args={
            "memory_preview": _preview(content),
            "container_tag": container_tag,
            "source": source,
            "scan": scan,
        },
        description="保存长期记忆到 Supermemory 前需要人工确认。",
        destructive_effects=["会把确认后的长期记忆写入 hosted Supermemory。"],
        metadata={
            "container_tag": container_tag,
            "source": source,
            "risk_level": "high",
            "data_sources": ["external_memory"],
        },
        allowed_decisions=["edit", "approve", "reject"],
    )
    record_audit_event(
        "external_memory_save_requested",
        actor=requested_by,
        summary="External memory save requested and sent to human confirmation.",
        risk_level="high",
        data_sources=["external_memory"],
        metadata={"container_tag": container_tag, "source": source, "scan": scan},
    )
    return _json({**approval, "audit_event_type": "external_memory_save_requested", "scan": scan})


def record_external_memory_recall(
    *,
    query: str = "",
    container_tag: str = "",
    result_count: int = 0,
    actor: str = "agent",
) -> str:
    """Record that hosted memory was recalled as context-only information."""
    audit = record_audit_event(
        "external_memory_recalled",
        actor=actor,
        summary="External memory recalled as context only.",
        risk_level="low",
        data_sources=["external_memory"],
        metadata={
            "query_preview": _preview(query, 200),
            "container_tag": container_tag,
            "result_count": max(0, int(result_count)),
            "evidence_policy": "context_only_not_business_evidence",
        },
    )
    return _json({"status": "success", "audit": json.loads(audit)})


def record_external_memory_save_approved(
    *,
    memory_id: str = "",
    container_tag: str = "",
    actor: str = "agent",
) -> str:
    """Record approval after an external memory write has been reviewed."""
    audit = record_audit_event(
        "external_memory_save_approved",
        actor=actor,
        summary="External memory save approved by human reviewer.",
        risk_level="high",
        data_sources=["external_memory"],
        metadata={"memory_id": memory_id, "container_tag": container_tag},
    )
    return _json({"status": "success", "audit": json.loads(audit)})
