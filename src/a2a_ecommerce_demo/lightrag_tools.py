from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from src.a2a_ecommerce_demo.human_approval_tools import request_human_approval
from src.a2a_ecommerce_demo.state_io import atomic_write_json, load_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WIKI_DIR = Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).resolve()
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
CLEANED_DIR = Path(os.getenv("A2A_CLEANED_DIR", DATA_DIR / "cleaned")).resolve()
WAREHOUSE_DIR = Path(os.getenv("A2A_WAREHOUSE_DIR", DATA_DIR / "warehouse")).resolve()
LIGHTRAG_DIR = Path(os.getenv("A2A_LIGHTRAG_DIR", DATA_DIR / "lightrag")).resolve()
INDEX_PATH = LIGHTRAG_DIR / "index.json"
OFFICIAL_SYNC_PATH = LIGHTRAG_DIR / "official_sync.json"
LIGHTRAG_API_URL = os.getenv("LIGHTRAG_API_URL", "http://127.0.0.1:9621").rstrip("/")
LIGHTRAG_API_KEY = os.getenv("LIGHTRAG_API_KEY", "")
LIGHTRAG_MODE = os.getenv("A2A_LIGHTRAG_MODE", "auto").lower()
HTTP_TIMEOUT_SECONDS = float(os.getenv("A2A_LIGHTRAG_HTTP_TIMEOUT", "60"))
LIGHTRAG_AUTO_SUMMARY_MAX_CHARS = int(os.getenv("A2A_LIGHTRAG_AUTO_SUMMARY_MAX_CHARS", "5000"))
LIGHTRAG_AUTO_SUMMARY_TARGET_CHARS = int(os.getenv("A2A_LIGHTRAG_AUTO_SUMMARY_TARGET_CHARS", "1200"))
LIGHTRAG_AUTO_SUMMARY_PATH_PATTERNS = [
    "field-dictionary",
    "large-excel-profile",
    "销售日报",
    "sheet-erp",
]

ENTITY_PATTERNS = {
    "sku": re.compile(r"\b[A-Z0-9][A-Z0-9_-]{3,}\b"),
    "currency": re.compile(r"(?:USD|RMB|CNY|JPY|EUR|GBP|\$|￥)\s?\d+(?:\.\d+)?", re.IGNORECASE),
    "percent": re.compile(r"\b\d+(?:\.\d+)?%"),
    "file": re.compile(r"[\w\u4e00-\u9fff 、&.-]+\.(?:xlsx|csv|docx|pptx|pdf|md)", re.IGNORECASE),
}

BUSINESS_TERMS = {
    "inventory": ["库存", "仓库", "在库", "出库", "入库", "补货", "断货", "周转"],
    "finance": ["收入", "成本", "毛利", "现金", "利润", "费用", "采购价", "销售额"],
    "ads": ["广告", "acos", "roas", "关键词", "投放", "预算", "竞价"],
    "supplier": ["供应商", "交期", "采购", "延期", "工厂"],
    "product": ["产品", "SKU", "listing", "标题", "卖点", "差评", "评论"],
    "decision": ["决策", "建议", "风险", "方案", "优先级", "复盘"],
}


def _ensure_dirs() -> None:
    LIGHTRAG_DIR.mkdir(parents=True, exist_ok=True)
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_under(path: Path, roots: list[Path]) -> Path:
    resolved = path.resolve()
    if not any(root in [resolved, *resolved.parents] for root in roots):
        raise ValueError(f"Refusing to access outside allowed directories: {resolved}")
    return resolved


def _relative(path: Path) -> str:
    for root_name, root in [("wiki", WIKI_DIR), ("cleaned", CLEANED_DIR), ("warehouse", WAREHOUSE_DIR), ("data", DATA_DIR)]:
        try:
            return f"{root_name}/{path.relative_to(root).as_posix()}"
        except ValueError:
            continue
    return path.as_posix()


def _read_markdown(path: Path, max_chars: int) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]


def _read_csv_preview(path: Path, max_rows: int = 120) -> str:
    lines = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        for row_index, row in enumerate(reader):
            if row_index >= max_rows:
                lines.append(f"... {row_index} rows previewed; remaining rows omitted ...")
                break
            lines.append(" | ".join(str(cell).strip() for cell in row[:80]))
    return "\n".join(lines)


def _http_json(method: str, endpoint: str, payload: dict[str, Any] | None = None, timeout: float = HTTP_TIMEOUT_SECONDS) -> dict[str, Any]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if LIGHTRAG_API_KEY:
        headers["X-API-Key"] = LIGHTRAG_API_KEY
    request = urllib.request.Request(
        f"{LIGHTRAG_API_URL}{endpoint}",
        data=body,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}


def _official_enabled() -> bool:
    return LIGHTRAG_MODE in {"auto", "official", "server", "full"}


def _load_sync_state() -> dict[str, Any]:
    _ensure_dirs()
    return load_json(OFFICIAL_SYNC_PATH, {"schema": "a2a_lightrag_official_sync_v1", "documents": {}})


def _save_sync_state(state: dict[str, Any]) -> None:
    _ensure_dirs()
    atomic_write_json(OFFICIAL_SYNC_PATH, state)


def _document_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _document_text_for_official(doc: dict[str, Any]) -> str:
    escaped_path = html.escape(doc["path"])
    escaped_title = html.escape(doc["title"])
    return (
        f"---\n"
        f"source_path: {doc['path']}\n"
        f"source_kind: {doc['kind']}\n"
        f"title: {doc['title']}\n"
        f"---\n\n"
        f"# {escaped_title}\n\n"
        f"Source: `{escaped_path}`\n\n"
        f"{doc['text']}"
    )


def _lightrag_doc_status_path() -> Path:
    return Path(os.getenv("WORKING_DIR", DATA_DIR / "lightrag_official")).resolve() / "kv_store_doc_status.json"


def _load_lightrag_doc_status() -> dict[str, Any]:
    path = _lightrag_doc_status_path()
    return load_json(path, {})


def _save_lightrag_doc_status(statuses: dict[str, Any]) -> None:
    path = _lightrag_doc_status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, statuses)


def _dataset_registry_path() -> Path:
    return Path(os.getenv("A2A_DATASET_REGISTRY", WAREHOUSE_DIR / "dataset_registry.json")).resolve()


def _load_dataset_registry() -> dict[str, Any]:
    path = _dataset_registry_path()
    if not path.exists():
        return {"datasets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _status_counts(statuses: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in statuses.values():
        if isinstance(record, dict):
            status = str(record.get("status") or "unknown")
        else:
            status = "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _status_bucket(status: str) -> str:
    normalized = status.lower()
    if normalized in {"processed", "failed"}:
        return normalized
    if normalized in {"pending", "processing", "queued", "created", "running"}:
        return "pending"
    return "unknown"


def _resolve_lightrag_source_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return _safe_under(path, [WIKI_DIR, DATA_DIR])
    if path.parts and path.parts[0] == "wiki":
        return _safe_under(WIKI_DIR / Path(*path.parts[1:]), [WIKI_DIR])
    if path.parts and path.parts[0] == "data":
        return _safe_under(DATA_DIR / Path(*path.parts[1:]), [DATA_DIR])
    if path.parts and path.parts[0] == "cleaned":
        return _safe_under(CLEANED_DIR / Path(*path.parts[1:]), [CLEANED_DIR])
    if path.parts and path.parts[0] == "warehouse":
        return _safe_under(WAREHOUSE_DIR / Path(*path.parts[1:]), [WAREHOUSE_DIR])
    return _safe_under(WIKI_DIR / path, [WIKI_DIR])


def _slugify_retry_path(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "_", value).strip("_")
    return slug[:100] or "lightrag_retry"


def _compact_markdown_for_lightrag_retry(text: str, max_chars: int) -> str:
    max_chars = max(400, max_chars)
    normalized_lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    business_tokens = {
        token.lower()
        for tokens in BUSINESS_TERMS.values()
        for token in tokens
    } | {"unove", "sku", "gmv", "roi", "acos", "roas", "风险", "建议", "结论", "证据", "库存", "销售"}
    selected: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        stripped = line.strip()
        if not stripped or stripped in seen:
            return
        seen.add(stripped)
        selected.append(stripped[:500])

    for line in normalized_lines[:80]:
        if line.lstrip().startswith("#"):
            add(line)

    for line in normalized_lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped.startswith(("#", "-", "*", "|")) and any(token in lowered for token in business_tokens):
            add(stripped)
        if sum(len(item) + 1 for item in selected) >= max_chars:
            break

    if sum(len(item) + 1 for item in selected) < max_chars:
        for line in normalized_lines:
            add(line)
            if sum(len(item) + 1 for item in selected) >= max_chars:
                break

    compacted = "\n".join(selected)
    if len(compacted) > max_chars:
        compacted = compacted[: max_chars - 80].rstrip() + "\n\n... omitted for LightRAG retry ..."
    return compacted


def _should_auto_summarize_for_lightrag(doc: dict[str, Any], text: str) -> tuple[bool, str]:
    path = str(doc.get("path") or "").lower()
    if path.startswith(("wiki/lightrag-auto-summary/", "wiki/lightrag-retry/")):
        return False, ""
    title = str(doc.get("title") or "").lower()
    haystack = f"{path} {title}"
    matched_pattern = next((pattern for pattern in LIGHTRAG_AUTO_SUMMARY_PATH_PATTERNS if pattern.lower() in haystack), "")
    if matched_pattern:
        return True, f"path_pattern:{matched_pattern}"
    if len(text) > LIGHTRAG_AUTO_SUMMARY_MAX_CHARS:
        return True, f"content_length>{LIGHTRAG_AUTO_SUMMARY_MAX_CHARS}"
    return False, ""


def _build_lightrag_summary_page(
    source_path_label: str,
    source_path: Path,
    source_text: str,
    *,
    summary_dir_name: str,
    source_key: str,
    reason: str,
    max_chars: int,
) -> tuple[Path, str]:
    summary_dir = WIKI_DIR / summary_dir_name
    summary_dir.mkdir(parents=True, exist_ok=True)
    checksum = _document_checksum(source_text + reason)
    summary_path = summary_dir / f"{_slugify_retry_path(source_path_label)}-{checksum[:12]}.md"
    compacted = _compact_markdown_for_lightrag_retry(source_text, max_chars=max_chars)
    body = (
        "---\n"
        f"source_kind: {summary_dir_name}\n"
        f"{source_key}: {source_path_label}\n"
        f"summary_reason: {reason}\n"
        f"generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "---\n\n"
        f"# LightRAG Summary - {source_path.stem}\n\n"
        f"Source: `{source_path_label}`\n\n"
        "This compact page is generated for LightRAG indexing so large tabular/wiki pages do not repeatedly timeout during entity extraction.\n\n"
        "## Compacted Evidence\n\n"
        f"{compacted}\n"
    )
    summary_path.write_text(body, encoding="utf-8")
    return summary_path, body


def _failed_lightrag_records(limit: int) -> list[dict[str, Any]]:
    statuses = _load_lightrag_doc_status()
    records = []
    for doc_id, record in statuses.items():
        if not isinstance(record, dict) or record.get("status") != "failed":
            continue
        file_path = str(record.get("file_path") or record.get("source") or "")
        if not file_path:
            continue
        records.append(
            {
                "doc_id": doc_id,
                "file_path": file_path,
                "error": str(record.get("error") or record.get("error_msg") or record.get("message") or ""),
                "raw_status": record,
            }
        )
        if len(records) >= limit:
            break
    return records


def _classify_lightrag_error(error: str) -> str:
    lowered = error.lower()
    if "insufficient balance" in lowered or "error code: 402" in lowered:
        return "llm_insufficient_balance"
    if (
        "modelnotfound" in lowered
        or "model not found" in lowered
        or "model unavailable" in lowered
        or "model is unavailable" in lowered
        or "invalid model" in lowered
        or "does not exist" in lowered
    ):
        return "model_unavailable"
    if "embedding func" in lowered and "timeout" in lowered:
        return "embedding_timeout"
    if "llm func" in lowered and "timeout" in lowered:
        return "llm_timeout"
    if "api status" in lowered or "apistatuserror" in lowered:
        return "provider_api_error"
    if "timeout" in lowered:
        return "timeout"
    return "unknown"


def _lightrag_failure_action(root_cause: str) -> str:
    actions = {
        "llm_insufficient_balance": "先处理 LLM 供应商余额或切换可用模型；在修复前不要继续重试，否则会把待处理文档批量打成 failed。",
        "model_unavailable": "先确认 LLM/Embedding 模型名称、供应商可用性和 API 权限；模型恢复前暂停 retry。",
        "embedding_timeout": "检查 EMBEDDING_BINDING_HOST/API_KEY/MODEL 是否匹配，并降低单文档长度或分批同步后重试。",
        "llm_timeout": "把超长页面拆小或使用 retry_failed_lightrag_docs 生成摘要页后重试。",
        "provider_api_error": "检查模型供应商返回的 API 错误、限流和认证配置，再重试失败文档。",
        "timeout": "降低 max_chars_per_doc 或分批同步，避免单批文档处理时间过长。",
        "unknown": "查看 error_msg 原文，确认是配置、模型供应商还是文档内容问题。",
    }
    return actions.get(root_cause, actions["unknown"])


def _lightrag_retry_guard(root_cause_counts: Counter[str]) -> dict[str, Any]:
    blocking_root_causes = [
        root_cause
        for root_cause in ["llm_insufficient_balance", "model_unavailable"]
        if root_cause_counts.get(root_cause, 0) > 0
    ]
    if blocking_root_causes:
        return {
            "retry_allowed": False,
            "blocking_root_causes": blocking_root_causes,
            "recommendation": "暂停 retry：先处理余额、模型可用性或供应商权限问题；恢复后再调用 retry_failed_lightrag_docs(force=true)。",
        }
    return {
        "retry_allowed": True,
        "blocking_root_causes": [],
        "recommendation": "未发现余额不足或模型不可用阻断；可按需重试 failed 文档，并继续观察 pending 数量。",
    }


def summarize_lightrag_processing_status(limit: int = 50) -> str:
    """汇总完整 LightRAG processed/failed/pending 状态，并给出 retry 保护建议。"""
    statuses = _load_lightrag_doc_status()
    status_counts = _status_counts(statuses)
    bucket_counts: Counter[str] = Counter()
    root_cause_counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, str]]] = {"failed": [], "pending": []}

    for doc_id, record in statuses.items():
        if not isinstance(record, dict):
            bucket_counts["unknown"] += 1
            continue
        status = str(record.get("status") or "unknown")
        bucket = _status_bucket(status)
        bucket_counts[bucket] += 1
        file_path = str(record.get("file_path") or record.get("source") or "")
        if bucket == "failed":
            error = str(record.get("error") or record.get("error_msg") or record.get("message") or "")
            root_cause = _classify_lightrag_error(error)
            root_cause_counts[root_cause] += 1
            if len(examples["failed"]) < limit:
                examples["failed"].append(
                    {
                        "doc_id": str(doc_id),
                        "file_path": file_path,
                        "root_cause": root_cause,
                        "error": error[:500],
                    }
                )
        elif bucket == "pending" and len(examples["pending"]) < limit:
            examples["pending"].append({"doc_id": str(doc_id), "file_path": file_path, "status": status})

    retry_guard = _lightrag_retry_guard(root_cause_counts)
    next_actions = [
        retry_guard["recommendation"],
        "如果 pending 长时间不变，先检查 LightRAG Server worker 和模型供应商日志，再决定是否人工 reprocess。",
        "如果 failed 主要是 timeout，可降低 max_chars_per_doc 或生成 retry 摘要页后再重试。",
    ]
    return json.dumps(
        {
            "status": "warning" if bucket_counts.get("failed", 0) or not retry_guard["retry_allowed"] else "success",
            "api_url": LIGHTRAG_API_URL,
            "doc_status_path": str(_lightrag_doc_status_path()),
            "status_counts": status_counts,
            "processed_count": bucket_counts.get("processed", 0),
            "failed_count": bucket_counts.get("failed", 0),
            "pending_count": bucket_counts.get("pending", 0),
            "unknown_count": bucket_counts.get("unknown", 0),
            "root_cause_counts": dict(root_cause_counts),
            "retry_guard": retry_guard,
            "examples": examples,
            "next_actions": next_actions,
        },
        ensure_ascii=False,
        indent=2,
    )


def diagnose_lightrag_failures(limit: int = 50) -> str:
    """诊断完整 LightRAG 文档失败原因，并给出恢复动作。"""
    statuses = _load_lightrag_doc_status()
    failed = _failed_lightrag_records(limit=limit)
    root_cause_counts: Counter[str] = Counter()
    examples: dict[str, dict[str, str]] = {}
    for item in failed:
        root_cause = _classify_lightrag_error(item["error"])
        root_cause_counts[root_cause] += 1
        examples.setdefault(
            root_cause,
            {
                "doc_id": item["doc_id"],
                "file_path": item["file_path"],
                "error": item["error"][:500],
            },
        )

    primary_actions = [
        _lightrag_failure_action(root_cause)
        for root_cause, _count in root_cause_counts.most_common()
    ]
    if failed and "llm_insufficient_balance" not in root_cause_counts:
        primary_actions.append("修复配置或拆分文档后，再调用 retry_failed_lightrag_docs 或 LightRAG WebUI 的 Scan/Retry。")
    elif "llm_insufficient_balance" in root_cause_counts:
        primary_actions.append("余额恢复或模型切换完成后，再调用 retry_failed_lightrag_docs(force=true) 或 LightRAG 的 reprocess_failed。")

    return json.dumps(
        {
            "status": "warning" if failed else "success",
            "api_url": LIGHTRAG_API_URL,
            "doc_status_path": str(_lightrag_doc_status_path()),
            "status_counts": _status_counts(statuses),
            "analyzed_failed_count": len(failed),
            "root_cause_counts": dict(root_cause_counts),
            "examples": examples,
            "retry_guard": _lightrag_retry_guard(root_cause_counts),
            "primary_recovery_actions": primary_actions,
        },
        ensure_ascii=False,
        indent=2,
    )


def list_failed_lightrag_docs(limit: int = 50) -> str:
    """列出完整 LightRAG 内部索引失败的文档。"""
    statuses = _load_lightrag_doc_status()
    failed = _failed_lightrag_records(limit=limit)
    return json.dumps(
        {
            "status": "success",
            "doc_status_path": str(_lightrag_doc_status_path()),
            "status_counts": _status_counts(statuses),
            "failed": [
                {
                    "doc_id": item["doc_id"],
                    "file_path": item["file_path"],
                    "error": item["error"],
                }
                for item in failed
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _is_recoverable_lightrag_timeout(item: dict[str, Any]) -> bool:
    root_cause = _classify_lightrag_error(str(item.get("error") or ""))
    return root_cause in {"llm_timeout", "timeout", "embedding_timeout"}


def _lightrag_timeout_recovery_preview(limit: int) -> dict[str, Any]:
    failed_records = _failed_lightrag_records(limit=limit)
    recoverable = [item for item in failed_records if _is_recoverable_lightrag_timeout(item)]
    skipped = [
        {
            "doc_id": item["doc_id"],
            "path": item["file_path"],
            "reason": _classify_lightrag_error(item["error"]),
        }
        for item in failed_records
        if item not in recoverable
    ]
    return {
        "source_failed_count": len(failed_records),
        "recoverable_timeout_count": len(recoverable),
        "recoverable": [
            {
                "doc_id": item["doc_id"],
                "path": item["file_path"],
                "reason": _classify_lightrag_error(item["error"]),
                "error": item["error"][:500],
            }
            for item in recoverable
        ],
        "skipped": skipped,
    }


def auto_recover_lightrag_timeouts(
    limit: int = 20,
    max_chars_per_doc: int = 2500,
    delete_original_failed: bool = True,
    confirmation_token: str = "",
) -> str:
    """自动把 timeout failed 文档转为摘要页；确认后才提交摘要并删除原始 failed 记录。"""
    status = json.loads(lightrag_server_status())
    if not status.get("available"):
        return json.dumps(
            {
                "status": "unavailable",
                "api_url": LIGHTRAG_API_URL,
                "server_status": status,
                "failed_docs": json.loads(list_failed_lightrag_docs(limit=limit)),
            },
            ensure_ascii=False,
            indent=2,
        )

    required_token = "CONFIRM_LIGHTRAG_TIMEOUT_RECOVERY"
    preview = _lightrag_timeout_recovery_preview(limit)
    if confirmation_token != required_token:
        approval = request_human_approval(
            action_name="auto_recover_lightrag_timeouts",
            args={
                "limit": limit,
                "max_chars_per_doc": max_chars_per_doc,
                "delete_original_failed": delete_original_failed,
                "recoverable_doc_ids": [item["doc_id"] for item in preview["recoverable"]],
            },
            description="Recover timeout failed LightRAG documents by submitting compact retry summaries.",
            destructive_effects=[
                "提交 timeout failed 文档的 compact retry 摘要到 LightRAG。",
                "如果 delete_original_failed=true，会从 LightRAG Server 删除原始 failed 记录，但不会删除本地 wiki 源文件。",
            ],
            metadata={"preview": preview, "confirmation_token": required_token, "api_url": LIGHTRAG_API_URL},
        )
        if approval.get("status") == "confirmation_required":
            return json.dumps(
                {
                    "status": "confirmation_required",
                    "requires_confirmation": True,
                    "confirmation_token": required_token,
                    "api_url": LIGHTRAG_API_URL,
                    "action": "auto_recover_lightrag_timeouts",
                    "destructive_effects": [
                        "提交 timeout failed 文档的 compact retry 摘要到 LightRAG。",
                        "如果 delete_original_failed=true，会从 LightRAG Server 删除原始 failed 记录，但不会删除本地 wiki 源文件。",
                    ],
                    "interrupt": approval["interrupt"],
                    "resume_shape": approval.get("resume_shape", {"decisions": [{"type": "approve"}]}),
                    "preview": preview,
                    "next_actions": [
                        "在前端 approve/reject interrupt 中确认 preview 里的 doc_id 和 path。",
                        "兼容旧 CLI：也可以带 confirmation_token 调用本工具。",
                        "不确认时不会写 retry 页面、不会提交 LightRAG、不会删除 failed 记录。",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        if not approval.get("approved"):
            return json.dumps(
                {
                    "status": "cancelled",
                    "api_url": LIGHTRAG_API_URL,
                    "action": "auto_recover_lightrag_timeouts",
                    "rejection_reason": approval.get("message", "Rejected by human reviewer."),
                    "preview": preview,
                    "next_actions": ["用户拒绝后不会写 retry 页面、不会提交 LightRAG、不会删除 failed 记录。"],
                },
                ensure_ascii=False,
                indent=2,
            )
        raw_edited_args = approval.get("edited_args")
        edited_args: dict[str, Any] = raw_edited_args if isinstance(raw_edited_args, dict) else {}
        limit = int(edited_args.get("limit", limit))
        max_chars_per_doc = int(edited_args.get("max_chars_per_doc", max_chars_per_doc))
        delete_original_failed = bool(edited_args.get("delete_original_failed", delete_original_failed))

    _ensure_dirs()
    sync_state = _load_sync_state()
    known = sync_state.setdefault("documents", {})
    failed_records = _failed_lightrag_records(limit=limit)
    recoverable = [item for item in failed_records if _is_recoverable_lightrag_timeout(item)]
    skipped = [
        {
            "doc_id": item["doc_id"],
            "path": item["file_path"],
            "reason": _classify_lightrag_error(item["error"]),
        }
        for item in failed_records
        if item not in recoverable
    ]
    retried = []
    submit_failed = []

    for item in recoverable:
        source_path_label = item["file_path"]
        try:
            source_path = _resolve_lightrag_source_path(source_path_label)
        except Exception as exc:
            skipped.append({"doc_id": item["doc_id"], "path": source_path_label, "reason": f"source_path_not_allowed: {exc}"})
            continue
        if not source_path.exists():
            skipped.append({"doc_id": item["doc_id"], "path": source_path_label, "reason": "source_file_missing"})
            continue
        source_text = _read_markdown(source_path, max_chars=max(max_chars_per_doc * 8, max_chars_per_doc))
        retry_path, retry_body = _build_lightrag_summary_page(
            source_path_label,
            source_path,
            source_text,
            summary_dir_name="lightrag-retry",
            source_key="retry_of",
            reason=f"auto_recover_failed_doc_id={item['doc_id']}; {item['error']}",
            max_chars=max_chars_per_doc,
        )
        retry_doc = {
            "path": _relative(retry_path),
            "kind": "lightrag_retry_summary",
            "title": f"LightRAG Retry Summary - {source_path.stem}",
            "text": retry_body,
        }
        payload = {"text": _document_text_for_official(retry_doc), "file_source": retry_doc["path"]}
        try:
            result = _http_json("POST", "/documents/text", payload=payload, timeout=HTTP_TIMEOUT_SECONDS)
            track_id = result.get("track_id") or result.get("id") or result.get("data", {}).get("track_id")
            known[retry_doc["path"]] = {
                "checksum": _document_checksum(payload["text"]),
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "track_id": track_id,
                "retry_of": source_path_label,
                "failed_doc_id": item["doc_id"],
                "auto_recovered": True,
                "result": result,
            }
            retried.append({"doc_id": item["doc_id"], "path": source_path_label, "retry_path": retry_doc["path"], "track_id": track_id})
        except Exception as exc:
            submit_failed.append({"doc_id": item["doc_id"], "path": source_path_label, "retry_path": retry_doc["path"], "error": str(exc)})

    deleted_original_failed_docs = []
    delete_failed = []
    if delete_original_failed and retried:
        doc_ids = [item["doc_id"] for item in retried]
        try:
            delete_result = _http_json(
                "DELETE",
                "/documents/delete_document",
                payload={"doc_ids": doc_ids, "delete_file": False, "delete_llm_cache": False},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            deleted_original_failed_docs = [
                {"doc_id": item["doc_id"], "path": item["path"], "result": delete_result}
                for item in retried
            ]
        except Exception as exc:
            delete_failed.append({"doc_ids": doc_ids, "error": str(exc)})

    sync_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_state["api_url"] = LIGHTRAG_API_URL
    _save_sync_state(sync_state)
    final_status = {}
    try:
        final_status = _http_json("GET", "/documents/status_counts", timeout=20)
    except Exception:
        final_status = {"status_counts": _status_counts(_load_lightrag_doc_status())}

    return json.dumps(
        {
            "status": "success" if retried and not submit_failed and not delete_failed else "warning",
            "api_url": LIGHTRAG_API_URL,
            "source_failed_count": len(failed_records),
            "recoverable_timeout_count": len(recoverable),
            "retried": retried,
            "deleted_original_failed_docs": deleted_original_failed_docs,
            "skipped": skipped,
            "failed": submit_failed + delete_failed,
            "status_counts_after_recovery": final_status.get("status_counts", final_status),
            "next_actions": [
                "等待 retry 摘要页 processed；状态条应显示 failed 下降或为 0。",
                "如果摘要页仍 timeout，降低 max_chars_per_doc 后再次调用 auto_recover_lightrag_timeouts。",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def retry_failed_lightrag_docs(limit: int = 20, max_chars_per_doc: int = 12000, force: bool = False) -> str:
    """把 LightRAG 内部 failed 文档压缩为 retry 摘要页并重新提交。"""
    status = json.loads(lightrag_server_status())
    if not status.get("available"):
        return json.dumps(
            {
                "status": "unavailable",
                "api_url": LIGHTRAG_API_URL,
                "server_status": status,
                "failed_docs": json.loads(list_failed_lightrag_docs(limit=limit)),
            },
            ensure_ascii=False,
            indent=2,
        )

    _ensure_dirs()
    statuses = _load_lightrag_doc_status()
    status_summary = json.loads(summarize_lightrag_processing_status(limit=limit))
    retry_guard = status_summary.get("retry_guard", {})
    if not force and not retry_guard.get("retry_allowed", True):
        return json.dumps(
            {
                "status": "retry_paused",
                "api_url": LIGHTRAG_API_URL,
                "doc_status_path": str(_lightrag_doc_status_path()),
                "status_summary": status_summary,
                "retry_guard": retry_guard,
                "next_actions": [
                    retry_guard.get("recommendation", "暂停 retry，先处理 LightRAG 供应商或模型问题。"),
                    "确认余额/模型恢复后，再用 force=true 显式重试。",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    failed_records = _failed_lightrag_records(limit=limit)
    retry_dir = WIKI_DIR / "lightrag-retry"
    retry_dir.mkdir(parents=True, exist_ok=True)
    sync_state = _load_sync_state()
    known = sync_state.setdefault("documents", {})
    retried = []
    skipped = []
    failed = []

    for item in failed_records:
        source_path_label = item["file_path"]
        try:
            source_path = _resolve_lightrag_source_path(source_path_label)
        except Exception as exc:
            skipped.append({"path": source_path_label, "reason": f"source_path_not_allowed: {exc}"})
            continue
        if not source_path.exists():
            skipped.append({"path": source_path_label, "reason": "source_file_missing"})
            continue

        source_text = _read_markdown(source_path, max_chars=max(max_chars_per_doc * 8, max_chars_per_doc))
        retry_path, retry_body = _build_lightrag_summary_page(
            source_path_label,
            source_path,
            source_text,
            summary_dir_name="lightrag-retry",
            source_key="retry_of",
            reason=f"failed_doc_id={item['doc_id']}; {item['error']}",
            max_chars=max_chars_per_doc,
        )
        retry_doc = {
            "path": _relative(retry_path),
            "kind": "lightrag_retry_summary",
            "title": f"LightRAG Retry Summary - {source_path.stem}",
            "text": retry_body,
        }
        text = _document_text_for_official(retry_doc)
        checksum = _document_checksum(text)
        previous = known.get(retry_doc["path"], {})
        if not force and previous.get("checksum") == checksum:
            skipped.append({"path": source_path_label, "retry_path": retry_doc["path"], "reason": "retry_summary_unchanged"})
            continue

        payload = {"text": text, "file_source": retry_doc["path"]}
        try:
            result = _http_json("POST", "/documents/text", payload=payload, timeout=HTTP_TIMEOUT_SECONDS)
            track_id = result.get("track_id") or result.get("id") or result.get("data", {}).get("track_id")
            known[retry_doc["path"]] = {
                "checksum": checksum,
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "track_id": track_id,
                "retry_of": source_path_label,
                "failed_doc_id": item["doc_id"],
                "result": result,
            }
            retried.append({"path": source_path_label, "retry_path": retry_doc["path"], "track_id": track_id, "result": result})
        except Exception as exc:
            failed.append({"path": source_path_label, "retry_path": retry_doc["path"], "error": str(exc)})

    sync_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_state["api_url"] = LIGHTRAG_API_URL
    _save_sync_state(sync_state)
    return json.dumps(
        {
            "status": "success" if not failed else "warning",
            "api_url": LIGHTRAG_API_URL,
            "doc_status_path": str(_lightrag_doc_status_path()),
            "status_counts_before_retry": _status_counts(statuses),
            "retry_wiki_dir": _relative(retry_dir),
            "source_failed_count": len(failed_records),
            "retried": retried,
            "skipped": skipped,
            "failed": failed,
            "next_actions": [
                "稍后再次调用 list_failed_lightrag_docs，确认 failed 数量是否下降。",
                "用 get_lightrag_track_status 查看 retry track_id 的索引进度。",
                "如果 retry 摘要仍超时，继续降低 max_chars_per_doc 后重试。",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def cleanup_confirmed_lightrag_failed_history(
    confirm_phrase: str = "",
    confirmation_token: str = "",
    limit: int = 100,
    require_processed_retry: bool = True,
) -> str:
    """人工确认后清理已由 retry 摘要成功替代的原始 failed 历史记录。"""
    required_phrase = "DELETE_FAILED_HISTORY"
    statuses = _load_lightrag_doc_status()
    sync_state = _load_sync_state()
    retry_by_source: dict[str, list[str]] = {}
    for retry_path, record in sync_state.get("documents", {}).items():
        if not isinstance(record, dict):
            continue
        retry_of = str(record.get("retry_of") or "").strip()
        if retry_of:
            retry_by_source.setdefault(retry_of, []).append(str(retry_path))

    processed_retry_paths = {
        str(record.get("file_path") or record.get("source") or "")
        for record in statuses.values()
        if isinstance(record, dict) and str(record.get("status") or "").lower() == "processed"
    }
    candidates = []
    blocked = []
    for doc_id, record in statuses.items():
        if not isinstance(record, dict) or str(record.get("status") or "").lower() != "failed":
            continue
        file_path = str(record.get("file_path") or record.get("source") or "")
        retry_paths = retry_by_source.get(file_path, [])
        processed_retries = [path for path in retry_paths if path in processed_retry_paths]
        item = {
            "doc_id": str(doc_id),
            "file_path": file_path,
            "retry_paths": retry_paths,
            "processed_retry_paths": processed_retries,
        }
        if retry_paths and (processed_retries or not require_processed_retry):
            candidates.append(item)
        else:
            item["reason"] = "no_processed_retry_summary" if retry_paths else "no_retry_summary_found"
            blocked.append(item)

    confirmed = confirm_phrase == required_phrase or confirmation_token == required_phrase
    if not confirmed:
        return json.dumps(
            {
                "status": "confirmation_required",
                "requires_confirmation": True,
                "confirmation_token": required_phrase,
                "required_confirm_phrase": required_phrase,
                "doc_status_path": str(_lightrag_doc_status_path()),
                "candidate_count": len(candidates),
                "candidates": candidates[:limit],
                "blocked": blocked[:limit],
                "message": "This only removes local LightRAG failed history after a processed retry summary exists.",
            },
            ensure_ascii=False,
            indent=2,
        )

    to_remove = candidates[: max(0, limit)]
    archive_dir = LIGHTRAG_DIR / "doc_status_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"kv_store_doc_status-before-cleanup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    archive_path.write_text(json.dumps(statuses, ensure_ascii=False, indent=2), encoding="utf-8")

    for item in to_remove:
        statuses.pop(item["doc_id"], None)
    _save_lightrag_doc_status(statuses)
    return json.dumps(
        {
            "status": "success",
            "doc_status_path": str(_lightrag_doc_status_path()),
            "archive_path": str(archive_path),
            "removed": to_remove,
            "blocked": blocked[:limit],
            "remaining_status_counts": _status_counts(statuses),
        },
        ensure_ascii=False,
        indent=2,
    )


def _path_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", value).strip("_").lower()


def _collect_reference_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, str):
        if value.startswith(("wiki/", "warehouse/", "data/", "raw/")):
            paths.append(value)
        return paths
    if isinstance(value, list):
        for item in value:
            paths.extend(_collect_reference_paths(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "file_path", "source", "source_path", "file_source", "reference", "reference_path"}:
                paths.extend(_collect_reference_paths(item))
            else:
                paths.extend(_collect_reference_paths(item))
    return paths


def _match_reference_sheet(reference_path: str, dataset: dict[str, Any], manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    page_slug = _path_slug(Path(reference_path).stem.removeprefix("sheet-"))
    sheet_views = dataset.get("sheet_views", [])
    for sheet in manifest.get("sheets", []):
        sheet_name = str(sheet.get("sheet") or sheet.get("sheet_name") or "")
        sheet_slug = _path_slug(sheet_name)
        if sheet_slug and (sheet_slug in page_slug or page_slug in sheet_slug):
            matched_view = next((view for view in sheet_views if str(view.get("sheet_name") or view.get("sheet") or "") == sheet_name), None)
            return sheet, matched_view
    for view in sheet_views:
        sheet_name = str(view.get("sheet_name") or view.get("sheet") or "")
        sheet_slug = _path_slug(sheet_name)
        if sheet_slug and (sheet_slug in page_slug or page_slug in sheet_slug):
            matched_sheet = next((sheet for sheet in manifest.get("sheets", []) if str(sheet.get("sheet") or "") == sheet_name), None)
            return matched_sheet, view
    return None, None


def _chunk_source_rows(manifest: dict[str, Any], sheet_name: str) -> list[dict[str, Any]]:
    sheet_meta = next((sheet for sheet in manifest.get("sheets", []) if str(sheet.get("sheet") or "") == sheet_name), {})
    header_row = int(sheet_meta.get("detected_header_row") or 1)
    offset = 0
    chunks = []
    for chunk in manifest.get("chunks", []):
        if str(chunk.get("sheet") or "") != sheet_name:
            continue
        rows = int(chunk.get("rows") or 0)
        start = header_row + offset + 1
        end = start + max(rows - 1, 0)
        chunks.append(
            {
                "path": str(chunk.get("path") or ""),
                "rows": rows,
                "estimated_source_excel_rows": {"start": start, "end": end},
            }
        )
        offset += rows
    return chunks


def resolve_lightrag_reference_paths(reference_path: str = "", query_result_json: str = "", limit: int = 20) -> str:
    """把 LightRAG/wiki 引用定位到 dataset wiki、DuckDB mart、manifest、chunk 和源 Excel 行范围。"""
    references = []
    if reference_path.strip():
        references.append(reference_path.strip())
    if query_result_json.strip():
        try:
            references.extend(_collect_reference_paths(json.loads(query_result_json)))
        except json.JSONDecodeError:
            references.extend(re.findall(r"(?:wiki|warehouse|data|raw)/[^\s`'\"，。；;]+", query_result_json))
    seen = set()
    references = [item for item in references if item and not (item in seen or seen.add(item))]

    registry = _load_dataset_registry()
    resolved = []
    unresolved = []
    for ref in references[: max(1, limit)]:
        matched_dataset: dict[str, Any] | None = None
        dataset_slug = ""
        for slug, dataset in registry.get("datasets", {}).items():
            wiki_pages = [str(path) for path in dataset.get("wiki_pages", {}).values()]
            if ref in wiki_pages or f"wiki/datasets/{slug}/" in ref:
                matched_dataset = dataset
                dataset_slug = str(dataset.get("dataset_slug") or slug)
                break
        if matched_dataset is None:
            unresolved.append({"reference_path": ref, "reason": "dataset_not_found"})
            continue

        manifest_path = Path(str(matched_dataset.get("manifest_path") or ""))
        manifest = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sheet_meta, sheet_view = _match_reference_sheet(ref, matched_dataset, manifest) if manifest else (None, None)
        source_sheet = str((sheet_meta or {}).get("sheet") or (sheet_view or {}).get("sheet_name") or "")
        chunks = _chunk_source_rows(manifest, source_sheet) if source_sheet else []
        resolved.append(
            {
                "reference_path": ref,
                "dataset_slug": dataset_slug,
                "dataset_wiki_pages": matched_dataset.get("wiki_pages", {}),
                "manifest_path": str(manifest_path) if manifest_path else "",
                "quality_report_path": str(matched_dataset.get("quality_report_path") or ""),
                "source_excel": str(manifest.get("relative_source") or matched_dataset.get("source") or manifest.get("source") or ""),
                "source_sheet": source_sheet,
                "source_headers": (sheet_meta or {}).get("headers", (sheet_view or {}).get("headers", [])),
                "duckdb_dataset_view": str((sheet_view or {}).get("raw_view_name") or ""),
                "duckdb_marts": matched_dataset.get("mart_views", []),
                "chunks": chunks[:50],
            }
        )

    return json.dumps(
        {
            "status": "success" if resolved else "not_found",
            "registry_path": str(_dataset_registry_path()),
            "references": resolved,
            "unresolved": unresolved,
        },
        ensure_ascii=False,
        indent=2,
    )


def _iter_documents(max_docs: int, max_chars_per_doc: int) -> list[dict[str, Any]]:
    _ensure_dirs()
    documents = []
    for path in sorted(WIKI_DIR.rglob("*.md")):
        if ".obsidian" in path.parts:
            continue
        documents.append(
            {
                "path": _relative(path),
                "kind": "wiki",
                "title": path.stem,
                "text": _read_markdown(path, max_chars_per_doc),
            }
        )
        if len(documents) >= max_docs:
            return documents
    return documents


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", text.lower())
    return [token for token in tokens if len(token) <= 40]


def _extract_entities(text: str) -> list[dict[str, str]]:
    entities: dict[tuple[str, str], dict[str, str]] = {}
    for entity_type, pattern in ENTITY_PATTERNS.items():
        for match in pattern.findall(text):
            name = str(match).strip()
            if len(name) >= 3:
                entities[(entity_type, name)] = {"name": name, "type": entity_type}

    lowered = text.lower()
    for entity_type, terms in BUSINESS_TERMS.items():
        for term in terms:
            if term.lower() in lowered:
                entities[(entity_type, term)] = {"name": term, "type": entity_type}

    headings = re.findall(r"^#{1,3}\s+(.+)$", text, flags=re.MULTILINE)
    for heading in headings[:30]:
        name = heading.strip()[:80]
        if name:
            entities[("topic", name)] = {"name": name, "type": "topic"}

    return sorted(entities.values(), key=lambda item: (item["type"], item["name"]))[:80]


def _snippet(text: str, terms: list[str], max_chars: int = 700) -> str:
    lowered = text.lower()
    positions = [lowered.find(term.lower()) for term in terms if term and lowered.find(term.lower()) >= 0]
    start = max(min(positions) - 180, 0) if positions else 0
    snippet = text[start : start + max_chars].replace("\r", " ").strip()
    return re.sub(r"\n{3,}", "\n\n", snippet)


def rebuild_lightrag_index(max_docs: int = 300, max_chars_per_doc: int = 30000) -> str:
    """重建本地 LightRAG 风格索引：文档、实体、关系和关键词。"""
    documents = _iter_documents(max_docs=max_docs, max_chars_per_doc=max_chars_per_doc)
    entity_sources: dict[str, dict[str, Any]] = {}
    relation_counter: Counter[tuple[str, str]] = Counter()
    indexed_docs = []

    for doc in documents:
        text = doc["text"]
        entities = _extract_entities(text)
        terms = Counter(_tokenize(text)).most_common(80)
        source_path = doc["path"]
        for entity in entities:
            key = f"{entity['type']}::{entity['name']}"
            record = entity_sources.setdefault(
                key,
                {"id": key, "name": entity["name"], "type": entity["type"], "sources": [], "degree": 0},
            )
            record["sources"].append(source_path)

        entity_ids = [f"{entity['type']}::{entity['name']}" for entity in entities[:30]]
        for index, left in enumerate(entity_ids):
            for right in entity_ids[index + 1 : index + 8]:
                if left != right:
                    pair = (left, right) if left < right else (right, left)
                    relation_counter[pair] += 1

        indexed_docs.append(
            {
                "id": hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:16],
                "path": source_path,
                "kind": doc["kind"],
                "title": doc["title"],
                "keywords": [term for term, _count in terms[:30]],
                "entities": entity_ids,
                "char_count": len(text),
                "text_preview": text[:2000],
            }
        )

    relations = []
    for (left, right), weight in relation_counter.most_common(500):
        if left in entity_sources:
            entity_sources[left]["degree"] += weight
        if right in entity_sources:
            entity_sources[right]["degree"] += weight
        relations.append({"source": left, "target": right, "weight": weight})

    for record in entity_sources.values():
        record["sources"] = sorted(set(record["sources"]))[:20]

    index = {
        "schema": "a2a_lightrag_local_v1",
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_roots": {"wiki": str(WIKI_DIR)},
        "documents": indexed_docs,
        "entities": sorted(entity_sources.values(), key=lambda item: (-item["degree"], item["type"], item["name"])),
        "relations": relations,
    }
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.dumps(
        {
            "status": "success",
            "index_path": str(INDEX_PATH),
            "documents": len(indexed_docs),
            "entities": len(index["entities"]),
            "relations": len(relations),
            "built_at": index["built_at"],
        },
        ensure_ascii=False,
        indent=2,
    )


def lightrag_server_status() -> str:
    """检查完整 LightRAG Server 是否可用。"""
    if not _official_enabled():
        return json.dumps(
            {
                "mode": LIGHTRAG_MODE,
                "official_enabled": False,
                "available": False,
                "message": "A2A_LIGHTRAG_MODE is set to local/disabled; using local lightweight index only.",
                "api_url": LIGHTRAG_API_URL,
            },
            ensure_ascii=False,
            indent=2,
        )
    endpoints = ["/health", "/healthz", "/"]
    errors = []
    for endpoint in endpoints:
        try:
            result = _http_json("GET", endpoint, timeout=8)
            return json.dumps(
                {
                    "official_enabled": True,
                    "available": True,
                    "api_url": LIGHTRAG_API_URL,
                    "endpoint": endpoint,
                    "result": result,
                    "fallback": "local_lightrag_index",
                },
                ensure_ascii=False,
                indent=2,
            )
        except Exception as exc:
            errors.append(f"{endpoint}: {exc}")
    return json.dumps(
        {
            "official_enabled": True,
            "available": False,
            "api_url": LIGHTRAG_API_URL,
            "errors": errors,
            "fallback": "local_lightrag_index",
            "next_actions": [
                "运行 D:\\A2A\\scripts\\install_lightrag.ps1 安装完整 LightRAG Server。",
                "运行 D:\\A2A\\scripts\\start_lightrag_server.ps1 启动服务。",
                "确认 .env 中 LIGHTRAG_API_URL、LIGHTRAG_API_KEY、EMBEDDING_* 配置正确。",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def sync_obsidian_to_official_lightrag(max_docs: int = 300, force: bool = False) -> str:
    """把 Obsidian wiki 中的高信号知识页同步到完整 LightRAG Server。服务不可用时返回明确错误。"""
    status = json.loads(lightrag_server_status())
    if not status.get("available"):
        return json.dumps(
            {
                "status": "unavailable",
                "api_url": LIGHTRAG_API_URL,
                "server_status": status,
                "fallback_index": json.loads(rebuild_lightrag_index(max_docs=max_docs)),
            },
            ensure_ascii=False,
            indent=2,
        )

    documents = _iter_documents(max_docs=max_docs, max_chars_per_doc=120000)
    sync_state = _load_sync_state()
    known = sync_state.setdefault("documents", {})
    inserted = []
    skipped = []
    failed = []
    auto_summarized = []

    for doc in documents:
        source_text = _document_text_for_official(doc)
        should_summarize, summarize_reason = _should_auto_summarize_for_lightrag(doc, source_text)
        sync_doc = doc
        if should_summarize and not str(doc["path"]).startswith("wiki/lightrag-auto-summary/"):
            source_path = _resolve_lightrag_source_path(doc["path"])
            summary_path, summary_body = _build_lightrag_summary_page(
                doc["path"],
                source_path,
                source_text,
                summary_dir_name="lightrag-auto-summary",
                source_key="summary_of",
                reason=summarize_reason,
                max_chars=LIGHTRAG_AUTO_SUMMARY_TARGET_CHARS,
            )
            sync_doc = {
                "path": _relative(summary_path),
                "kind": "lightrag_auto_summary",
                "title": f"LightRAG Auto Summary - {source_path.stem}",
                "text": summary_body,
            }
            auto_summarized.append({"path": doc["path"], "summary_path": sync_doc["path"], "reason": summarize_reason})

        text = _document_text_for_official(sync_doc)
        checksum = _document_checksum(text)
        previous = known.get(sync_doc["path"], {})
        if not force and previous.get("checksum") == checksum:
            skipped.append({"path": sync_doc["path"], "reason": "unchanged", "track_id": previous.get("track_id")})
            continue
        payload = {"text": text, "file_source": sync_doc["path"]}
        try:
            result = _http_json("POST", "/documents/text", payload=payload, timeout=HTTP_TIMEOUT_SECONDS)
            track_id = result.get("track_id") or result.get("id") or result.get("data", {}).get("track_id")
            known_record = {
                "checksum": checksum,
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "track_id": track_id,
                "result": result,
            }
            if should_summarize:
                known_record["summary_of"] = doc["path"]
                known_record["summary_reason"] = summarize_reason
            known[sync_doc["path"]] = known_record
            inserted.append({"path": sync_doc["path"], "track_id": track_id, "result": result})
        except Exception as exc:
            failed.append({"path": sync_doc["path"], "error": str(exc)})

    sync_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_state["api_url"] = LIGHTRAG_API_URL
    _save_sync_state(sync_state)
    rebuild_result = json.loads(rebuild_lightrag_index(max_docs=max_docs))
    return json.dumps(
        {
            "status": "success" if not failed else "warning",
            "api_url": LIGHTRAG_API_URL,
            "sync_state_path": str(OFFICIAL_SYNC_PATH),
            "inserted": inserted,
            "skipped": skipped,
            "failed": failed,
            "auto_summarized": auto_summarized,
            "local_fallback_index": rebuild_result,
            "next_actions": [
                "用 get_lightrag_track_status 查看 track_id 的索引进度。",
                "用 query_lightrag 查询，系统会优先调用完整 LightRAG Server。",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def get_lightrag_track_status(track_id: str) -> str:
    """查询完整 LightRAG 文档索引进度。"""
    try:
        result = _http_json("GET", f"/track_status/{track_id}", timeout=20)
        return json.dumps({"status": "success", "track_id": track_id, "result": result}, ensure_ascii=False, indent=2)
    except Exception as exc:
        local_status_path = Path(os.getenv("WORKING_DIR", DATA_DIR / "lightrag_official")) / "kv_store_doc_status.json"
        if local_status_path.exists():
            statuses = json.loads(local_status_path.read_text(encoding="utf-8"))
            for doc_id, record in statuses.items():
                if record.get("track_id") == track_id:
                    return json.dumps(
                        {
                            "status": "success",
                            "track_id": track_id,
                            "source": "local_doc_status_store",
                            "doc_id": doc_id,
                            "result": record,
                            "api_error": str(exc),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
        return json.dumps({"status": "failed", "track_id": track_id, "error": str(exc)}, ensure_ascii=False, indent=2)


def query_official_lightrag(query: str, mode: str = "hybrid", include_references: bool = True) -> str:
    """直接查询完整 LightRAG Server。服务不可用时返回错误，不做本地兜底。"""
    payload = {
        "query": query,
        "mode": mode,
        "include_references": include_references,
    }
    result = _http_json("POST", "/query", payload=payload, timeout=max(HTTP_TIMEOUT_SECONDS, 120))
    return json.dumps(
        {
            "status": "success",
            "backend": "official_lightrag_server",
            "api_url": LIGHTRAG_API_URL,
            "query": query,
            "mode": mode,
            "result": result,
        },
        ensure_ascii=False,
        indent=2,
    )


def _official_result_has_context(official: dict[str, Any]) -> bool:
    result = official.get("result", {})
    references = result.get("references") or result.get("sources") or []
    if references:
        return True
    response = str(result.get("response") or result.get("answer") or result.get("raw") or "")
    no_context_markers = ["[no-context]", "no query context", "not able to provide an answer"]
    return bool(response.strip()) and not any(marker in response.lower() for marker in no_context_markers)


def _load_or_build_index() -> dict[str, Any]:
    _ensure_dirs()
    if not INDEX_PATH.exists():
        rebuild_lightrag_index()
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def query_lightrag(query: str, limit: int = 8) -> str:
    """查询 LightRAG。优先完整 LightRAG Server；不可用时使用本地轻量索引兜底。"""
    if _official_enabled():
        try:
            official = json.loads(query_official_lightrag(query=query))
            if _official_result_has_context(official):
                official["fallback_used"] = False
                official["answer_guidance"] = [
                    "优先引用完整 LightRAG 返回的 references/source/path。",
                    "如果 references 不足，再调用本地索引或 Obsidian 页面补证据。",
                    "数据不足时明确输出缺口，不要编造。",
                ]
                return json.dumps(official, ensure_ascii=False, indent=2)
            fallback_error = "official_lightrag_server_returned_no_context"
        except Exception as exc:
            fallback_error = str(exc)
    else:
        fallback_error = f"A2A_LIGHTRAG_MODE={LIGHTRAG_MODE}"

    index = _load_or_build_index()
    terms = _tokenize(query)
    entity_hits = []
    for entity in index.get("entities", []):
        name = entity["name"].lower()
        score = sum(3 for term in terms if term in name)
        score += sum(1 for term in terms if any(term in source.lower() for source in entity.get("sources", [])))
        if score:
            entity_hits.append({**entity, "score": score})
    entity_hits.sort(key=lambda item: (-item["score"], -item.get("degree", 0)))

    source_boost: Counter[str] = Counter()
    for entity in entity_hits[:20]:
        for source in entity.get("sources", []):
            source_boost[source] += entity["score"]

    document_hits = []
    for doc in index.get("documents", []):
        haystack = " ".join([doc.get("title", ""), doc.get("path", ""), " ".join(doc.get("keywords", [])), doc.get("text_preview", "")]).lower()
        score = sum(2 for term in terms if term in haystack) + source_boost[doc["path"]]
        if score:
            full_path = _resolve_source_path(doc["path"])
            text = full_path.read_text(encoding="utf-8", errors="ignore") if full_path and full_path.suffix == ".md" else doc.get("text_preview", "")
            document_hits.append(
                {
                    "path": doc["path"],
                    "kind": doc.get("kind", ""),
                    "title": doc.get("title", ""),
                    "score": score,
                    "matched_entities": [entity["id"] for entity in entity_hits if doc["path"] in entity.get("sources", [])][:8],
                    "snippet": _snippet(text or doc.get("text_preview", ""), terms),
                }
            )
    document_hits.sort(key=lambda item: (-item["score"], item["path"]))

    related_relations = []
    top_ids = {entity["id"] for entity in entity_hits[:20]}
    for relation in index.get("relations", []):
        if relation["source"] in top_ids or relation["target"] in top_ids:
            related_relations.append(relation)
            if len(related_relations) >= 20:
                break

    return json.dumps(
        {
            "query": query,
            "backend": "local_lightweight_lightrag_fallback",
            "fallback_reason": fallback_error,
            "index_path": str(INDEX_PATH),
            "built_at": index.get("built_at"),
            "documents": document_hits[:limit],
            "entities": entity_hits[:limit],
            "relations": related_relations,
            "answer_guidance": [
                "先引用 documents 中的 path/snippet 作为证据。",
                "再用 entities/relations 解释 SKU、供应商、库存、财务、广告、决策之间的关系。",
                "如果证据不足，要明确输出缺口，不要编造。",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _resolve_source_path(source: str) -> Path | None:
    if source.startswith("wiki/"):
        path = WIKI_DIR / source.removeprefix("wiki/")
    else:
        return None
    try:
        return _safe_under(path, [WIKI_DIR])
    except ValueError:
        return None


def list_lightrag_entities(limit: int = 80, entity_type: str = "") -> str:
    """列出本地 LightRAG 图谱实体，支持按类型过滤。"""
    index = _load_or_build_index()
    entities = index.get("entities", [])
    if entity_type:
        entities = [entity for entity in entities if entity.get("type") == entity_type]
    return json.dumps(
        {
            "index_path": str(INDEX_PATH),
            "built_at": index.get("built_at"),
            "count": len(entities),
            "entities": entities[:limit],
        },
        ensure_ascii=False,
        indent=2,
    )


def get_lightrag_entity(entity_name: str, limit: int = 20) -> str:
    """查看某个实体的来源文档和相关关系。"""
    index = _load_or_build_index()
    query = entity_name.lower()
    matches = [entity for entity in index.get("entities", []) if query in entity.get("name", "").lower() or query in entity.get("id", "").lower()]
    match_ids = {entity["id"] for entity in matches}
    relations = [
        relation
        for relation in index.get("relations", [])
        if relation["source"] in match_ids or relation["target"] in match_ids
    ][:limit]
    return json.dumps(
        {
            "entity_name": entity_name,
            "matches": matches[:limit],
            "relations": relations,
            "source_documents": sorted({source for entity in matches for source in entity.get("sources", [])})[:limit],
        },
        ensure_ascii=False,
        indent=2,
    )
