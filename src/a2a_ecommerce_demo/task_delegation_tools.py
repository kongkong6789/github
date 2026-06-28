from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.a2a_ecommerce_demo.business_tools import (
    _format_evidence_chain_markdown,
    analyze_company_financial_position,
    analyze_company_strategy,
    assess_data_quality,
    list_business_files,
    register_all_fact_datasets,
    save_decision_report,
)
from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event
from src.a2a_ecommerce_demo.intent_router import classify_user_intent
from src.a2a_ecommerce_demo.knowledge_tools import (
    append_decision_note,
    ingest_all_raw_files,
    list_raw_files,
    list_wiki_pages,
)
from src.a2a_ecommerce_demo.large_excel_tools import process_all_large_excel_files
from src.a2a_ecommerce_demo.lightrag_tools import (
    summarize_lightrag_processing_status,
    sync_obsidian_to_official_lightrag,
)
from src.a2a_ecommerce_demo.state_io import atomic_write_json
from src.a2a_ecommerce_demo.table_cleaning_tools import clean_all_excel_files, profile_excel_file
from src.a2a_ecommerce_demo.task_queue import TaskQueue, get_task_queue
from src.a2a_ecommerce_demo.wiki_memory_tools import generate_cleaning_rules, generate_data_dictionary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
TASK_DIR = Path(os.getenv("A2A_TASK_DIR", DATA_DIR / "tasks")).resolve()
RAW_DIR = Path(os.getenv("A2A_RAW_DIR", PROJECT_ROOT / "raw")).resolve()
INTERACTIVE_EXCEL_BYTES = int(os.getenv("A2A_INTERACTIVE_EXCEL_BYTES", str(10 * 1024 * 1024)))
HUGE_FILE_BYTES = 100 * 1024 * 1024
_BACKGROUND_THREADS: dict[str, threading.Thread] = {}
_WORKFLOW_QUEUE_LOCK = threading.Lock()
_RECOVERABLE_STATUSES = {"queued", "running", "recoverable"}
_TERMINAL_STATUSES = {"success", "completed", "failed", "cancelled"}
_WORKFLOW_RUNNER: Callable[[str, int], str] | None = None
_DURABLE_LEASE_SECONDS = int(os.getenv("A2A_TASK_QUEUE_LEASE_SECONDS", str(6 * 60 * 60)))


def _task_queue() -> TaskQueue:
    return get_task_queue()


def _workflow_idempotency_key(goal: str, requested_by: str) -> str:
    digest = hashlib.sha256(goal.strip().encode("utf-8")).hexdigest()[:20]
    return f"workflow:{requested_by}:{digest}"


def _durable_worker_id(task_id: str) -> str:
    try:
        task = _load_task(task_id)
    except FileNotFoundError:
        return f"pid-{os.getpid()}:{task_id}"
    return str(task.get("durable_worker_id") or task.get("claim_worker_id") or f"pid-{os.getpid()}:{task_id}")


def _durable_task_snapshot(task_id: str) -> dict[str, Any]:
    try:
        queue = _task_queue()
        task = queue.get_task(task_id)
        return {
            **task,
            "events": queue.list_events(task_id),
            "artifacts": queue.list_artifacts(task_id),
            "retries": queue.list_retries(task_id),
        }
    except FileNotFoundError:
        return {}


def _should_start_background_company_workflow(goal: str) -> bool:
    """Only start the expensive raw/wiki/LightRAG workflow for explicit ingest requests."""
    return classify_user_intent(goal).start_background_workflow


def _ensure_task_dir() -> None:
    TASK_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(value: str, fallback: str = "workflow") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", value).strip("-")
    return slug[:60] or fallback


def _task_path(task_id: str) -> Path:
    _ensure_task_dir()
    safe = _slugify(task_id, "task")
    path = (TASK_DIR / f"{safe}.json").resolve()
    if TASK_DIR not in [path, *path.parents]:
        raise ValueError(f"Refusing to access outside task directory: {path}")
    return path


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_task(task_id: str) -> dict[str, Any]:
    path = _task_path(task_id)
    if not path.exists():
        raise FileNotFoundError(f"Task not found: {task_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_task(task: dict[str, Any]) -> None:
    path = _task_path(task["task_id"])
    task["path"] = str(path)
    atomic_write_json(path, task)
    if task.get("task_id"):
        _task_queue().upsert_from_json(task)


def _is_cancelled(task_id: str) -> bool:
    try:
        task = _load_task(task_id)
    except FileNotFoundError:
        return False
    return bool(task.get("cancel_requested"))


def _mark_cancelled(task_id: str) -> None:
    task = _load_task(task_id)
    _task_queue().cancel(task_id, requested_by=str(task.get("requested_by") or "workflow"), final=True)
    task["status"] = "cancelled"
    task["updated_at"] = _now()
    task.setdefault("steps", []).append(
        {
            "task": "workflow_cancelled",
            "status": "cancelled",
            "summary": "任务已按用户请求取消，已完成的步骤保留在 task log 中。",
            "completed_at": _now(),
            "evidence": [],
            "risks": [],
            "missing_data": [],
            "next_actions": [],
            "data": {},
        }
    )
    _save_task(task)


def _append_result(task_id: str, result: dict[str, Any]) -> dict[str, Any]:
    task = _load_task(task_id)
    result = {
        "completed_at": _now(),
        **result,
    }
    task.setdefault("steps", []).append(result)
    if result.get("status") == "failed":
        task["status"] = "warning"
    elif task.get("status") == "created":
        task["status"] = "running"
    task["updated_at"] = _now()
    _save_task(task)
    queue = _task_queue()
    queue.append_event(
        task_id,
        event_type="task_step_completed",
        step_name=str(result.get("task") or ""),
        status=str(result.get("status") or ""),
        summary=str(result.get("summary") or ""),
        payload=result.get("data") or {},
        error={"risks": result.get("risks", [])} if result.get("status") == "failed" else {},
    )
    for evidence_path in result.get("evidence", []):
        if evidence_path:
            queue.append_artifact(
                task_id,
                kind="evidence",
                path=str(evidence_path),
                label=str(result.get("task") or "workflow_step"),
                metadata={"step": result.get("task"), "status": result.get("status")},
            )
    return result


def _json_tool(name: str, fn: Callable[[], str]) -> dict[str, Any]:
    try:
        parsed = json.loads(fn())
        return {
            "task": name,
            "status": "success",
            "summary": f"{name} completed.",
            "evidence": [],
            "risks": [],
            "missing_data": [],
            "next_actions": [],
            "data": parsed,
        }
    except Exception as exc:
        return {
            "task": name,
            "status": "failed",
            "summary": str(exc),
            "evidence": [],
            "risks": [str(exc)],
            "missing_data": [],
            "next_actions": ["检查输入文件、路径或数据格式后重试。"],
            "data": {},
        }


def _huge_raw_files() -> list[dict[str, Any]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(RAW_DIR.rglob("*")):
        if path.is_file() and path.stat().st_size >= HUGE_FILE_BYTES:
            files.append(
                {
                    "path": str(path.relative_to(RAW_DIR)).replace("\\", "/"),
                    "size_mb": round(path.stat().st_size / 1024 / 1024, 2),
                }
            )
    return files


def create_workflow_task(goal: str, requested_by: str = "frontend", idempotency_key: str = "") -> str:
    """创建一个可追踪的全链路任务，返回 task_id 和任务文件路径。"""
    _ensure_task_dir()
    final_idempotency_key = idempotency_key.strip() or _workflow_idempotency_key(goal, requested_by)
    candidate_task_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{_slugify(goal)}"
    durable = _task_queue().enqueue(
        goal=goal,
        requested_by=requested_by,
        idempotency_key=final_idempotency_key,
        task_id=candidate_task_id,
        status="created",
        json_path=str(_task_path(candidate_task_id)),
    )
    task_id = str(durable["task_id"])
    path = _task_path(task_id)
    if path.exists():
        existing = _load_task(task_id)
        return json.dumps({"task_id": task_id, "saved_to": str(path), "status": existing.get("status", durable["status"])}, ensure_ascii=False, indent=2)
    task = {
        "task_id": task_id,
        "goal": goal,
        "requested_by": requested_by,
        "status": durable["status"],
        "created_at": durable["created_at"],
        "updated_at": durable["updated_at"],
        "idempotency_key": final_idempotency_key,
        "steps": [],
        "notes": [
            "This task log follows DeepAgents-style task delegation: each subtask returns a compact structured result.",
            "Large Excel files are handled by the offline large_excel_pipeline before normal cleaning and decision analysis.",
        ],
    }
    _save_task(task)
    record_audit_event("workflow_task_created", actor=requested_by, summary=goal, task_id=task_id, paths=[str(path)])
    return json.dumps({"task_id": task_id, "saved_to": str(path), "status": "created"}, ensure_ascii=False, indent=2)


def get_workflow_task_status(task_id: str) -> str:
    """读取全链路任务状态和所有子任务结果。"""
    durable = _durable_task_snapshot(task_id)
    try:
        task = _load_task(task_id)
        task["storage"] = "sqlite+json" if durable else "json"
    except FileNotFoundError:
        if not durable:
            raise
        task = {
            "task_id": durable["task_id"],
            "goal": durable.get("goal", ""),
            "requested_by": durable.get("requested_by", ""),
            "status": durable.get("status", ""),
            "created_at": durable.get("created_at", ""),
            "updated_at": durable.get("updated_at", ""),
            "started_at": durable.get("started_at", ""),
            "finished_at": durable.get("finished_at", ""),
            "cancel_requested": durable.get("cancel_requested", False),
            "idempotency_key": durable.get("idempotency_key", ""),
            "steps": [],
            "notes": ["This task exists in the SQLite durable queue but has no JSON export yet."],
            "storage": "sqlite",
        }
    task["background_running"] = bool(task_id in _BACKGROUND_THREADS and _BACKGROUND_THREADS[task_id].is_alive())
    task["recoverable"] = task.get("status") in _RECOVERABLE_STATUSES or durable.get("status") == "recoverable"
    if durable:
        task["durable_queue"] = durable
    return json.dumps(task, ensure_ascii=False, indent=2)


def list_workflow_tasks(limit: int = 30) -> str:
    """列出最近的全链路任务。"""
    _ensure_task_dir()
    tasks_by_id: dict[str, dict[str, Any]] = {}
    invalid_tasks: list[dict[str, Any]] = []
    for path in sorted(TASK_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
            task_id = str(task.get("task_id") or "")
            tasks_by_id[task_id] = {
                "task_id": task_id,
                "goal": task.get("goal"),
                "status": task.get("status"),
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
                "steps": len(task.get("steps", [])),
                "path": str(path),
                "storage": "json",
                "background_running": bool(task_id in _BACKGROUND_THREADS and _BACKGROUND_THREADS[task_id].is_alive()),
                "recoverable": task.get("status") in _RECOVERABLE_STATUSES,
                "idempotency_key": task.get("idempotency_key", ""),
            }
        except json.JSONDecodeError:
            invalid_tasks.append({"path": str(path), "status": "invalid_json", "storage": "json"})
    for durable in _task_queue().list_tasks(limit=max(limit * 3, limit, 30)):
        task_id = str(durable.get("task_id") or "")
        existing = tasks_by_id.get(task_id)
        if existing:
            existing["storage"] = "sqlite+json"
            existing["durable_status"] = durable.get("status")
            existing["durable_updated_at"] = durable.get("updated_at")
            existing["recoverable"] = bool(existing.get("recoverable") or durable.get("status") == "recoverable")
            if not existing.get("idempotency_key"):
                existing["idempotency_key"] = durable.get("idempotency_key", "")
            continue
        tasks_by_id[task_id] = {
            "task_id": task_id,
            "goal": durable.get("goal"),
            "status": durable.get("status"),
            "created_at": durable.get("created_at"),
            "updated_at": durable.get("updated_at"),
            "steps": 0,
            "path": durable.get("json_path") or "",
            "storage": "sqlite",
            "background_running": bool(task_id in _BACKGROUND_THREADS and _BACKGROUND_THREADS[task_id].is_alive()),
            "recoverable": durable.get("status") == "recoverable",
            "idempotency_key": durable.get("idempotency_key", ""),
        }
    tasks = sorted(
        [*tasks_by_id.values(), *invalid_tasks],
        key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""),
        reverse=True,
    )[:limit]
    return json.dumps({"task_dir": str(TASK_DIR), "durable_queue": str(_task_queue().db_path), "tasks": tasks}, ensure_ascii=False, indent=2)


def cancel_workflow_task(task_id: str) -> str:
    """请求取消后台全链路任务。取消会在当前子任务结束后生效。"""
    task = _load_task(task_id)
    task["cancel_requested"] = True
    worker = _BACKGROUND_THREADS.get(task_id)
    if task.get("status") == "queued" or not (worker and worker.is_alive()):
        _task_queue().cancel(task_id, requested_by="user", final=True)
        task["status"] = "cancelled"
        message = "任务尚未运行或 worker 不在运行，已直接标记为 cancelled。"
    else:
        _task_queue().cancel(task_id, requested_by="user")
        task["status"] = "running"
        message = "已请求取消；如果当前步骤正在处理文件，会在该步骤结束后停止后续步骤。"
    task["updated_at"] = _now()
    _save_task(task)
    return json.dumps(
        {
            "task_id": task_id,
            "status": task["status"],
            "cancel_requested": True,
            "message": message,
        },
        ensure_ascii=False,
        indent=2,
    )


def run_raw_discovery_task(task_id: str) -> str:
    """子任务：列出 raw 文件，并识别超大文件。"""
    result = _json_tool("raw_discovery", list_raw_files)
    huge_files = _huge_raw_files()
    if huge_files:
        result["status"] = "warning"
        result["risks"].append("raw 目录存在超过 100MB 的文件，不会在前端请求里直接解析，后续会进入离线大表管道。")
        result["next_actions"].append("等待 large_excel_pipeline 输出 profile、分块 CSV、manifest、quality_report 和 Obsidian 摘要。")
        result["data"]["huge_files"] = huge_files
    large_interactive_files = [
        file_info
        for file_info in result.get("data", {}).get("files", [])
        if file_info.get("type") in {".xlsx", ".xlsm"} and int(file_info.get("size_bytes") or 0) >= INTERACTIVE_EXCEL_BYTES
    ]
    if large_interactive_files:
        result["status"] = "warning"
        result["risks"].append("raw 目录存在 10MB+ Excel，普通清洗会跳过它们，改由 large_excel_pipeline 离线处理。")
        result["data"]["large_interactive_files"] = large_interactive_files
    return json.dumps(_append_result(task_id, result), ensure_ascii=False, indent=2)


def run_excel_cleaning_task(task_id: str, limit: int = 20) -> str:
    """子任务：批量画像/清洗 raw 目录中的 Excel；超大文件会被安全跳过并记录建议。"""
    profile_results = []
    for file_info in json.loads(list_raw_files()).get("files", []):
        if file_info.get("type") not in {".xlsx", ".xlsm"}:
            continue
        if int(file_info.get("size_bytes") or 0) >= INTERACTIVE_EXCEL_BYTES:
            profile_results.append(
                {
                    "file": file_info.get("path"),
                    "file_size_mb": round(int(file_info.get("size_bytes") or 0) / 1024 / 1024, 2),
                    "skipped_for_large_file_pipeline": True,
                    "recommendation": "Use large_excel_pipeline for this workbook.",
                }
            )
            continue
        try:
            profile_results.append(json.loads(profile_excel_file(file_info["path"])))
        except Exception as exc:
            profile_results.append({"file": file_info.get("path"), "error": str(exc)})
    cleaning_result = _json_tool("excel_cleaning", lambda: clean_all_excel_files(limit=limit))
    cleaning_result["data"]["profiles"] = profile_results
    if any(item.get("too_large_for_interactive_profile") for item in profile_results):
        cleaning_result["status"] = "warning"
        cleaning_result["risks"].append("存在超大 Excel，普通清洗会跳过它以避免前端卡死；请以 large_excel_pipeline 的分块结果为准。")
        cleaning_result["next_actions"].append("用 large_excel_pipeline 的 manifest/quality_report 判断大表是否可进入辅助决策。")
    return json.dumps(_append_result(task_id, cleaning_result), ensure_ascii=False, indent=2)


def run_large_excel_pipeline_task(task_id: str, limit: int = 10, min_size_mb: int = 10, rows_per_chunk: int = 50000) -> str:
    """子任务：离线处理大 Excel，输出 profile、分块 CSV、质量报告和 Obsidian 摘要。"""
    result = _json_tool(
        "large_excel_pipeline",
        lambda: process_all_large_excel_files(limit=limit, min_size_mb=min_size_mb, rows_per_chunk=rows_per_chunk),
    )
    data = result.get("data", {})
    processed = data.get("processed", 0)
    result["summary"] = f"Large Excel pipeline completed: {processed} large workbook(s) processed."
    result["evidence"] = []
    for item in data.get("results", []):
        processed_data = item.get("processed", {})
        if processed_data.get("manifest_path"):
            result["evidence"].append(processed_data["manifest_path"])
        if processed_data.get("wiki_path"):
            result["evidence"].append(processed_data["wiki_path"])
        quality = processed_data.get("quality", {})
        if quality.get("quality_report_path"):
            result["evidence"].append(quality["quality_report_path"])
        dataset_registry = processed_data.get("dataset_registry", {})
        if dataset_registry.get("duckdb_path"):
            result["evidence"].append(dataset_registry["duckdb_path"])
        overview_page = dataset_registry.get("wiki_pages", {}).get("overview", "")
        if overview_page:
            result["evidence"].append(overview_page)
        if item.get("status") == "failed":
            result["status"] = "warning"
            result["risks"].append(item.get("error", "Large Excel processing failed."))
    if processed == 0:
        result["summary"] = "No large Excel files found; skipped large Excel pipeline."
        result["next_actions"].append("如果后续放入 50MB+ Excel，会自动进入离线大文件管道。")
    else:
        result["next_actions"].append("大表明细已进入 DuckDB/Parquet 事实层；Obsidian/LightRAG 只同步摘要、字段字典、质量页和可复用结论。")
    return json.dumps(_append_result(task_id, result), ensure_ascii=False, indent=2)


def run_fact_layer_registration_task(task_id: str) -> str:
    """子任务：把大表 manifest 和标准结构化文件统一注册进 DuckDB fact layer。"""
    result = _json_tool("fact_layer_registration", register_all_fact_datasets)
    data = result.get("data", {})
    large_excel = data.get("large_excel", {})
    structured = data.get("structured", {})
    result["summary"] = (
        f"Fact layer registration finished: large_excel={large_excel.get('processed', 0)}, "
        f"structured={structured.get('processed', 0)}."
    )
    result["evidence"] = [
        data.get("duckdb_path", ""),
        data.get("registry_path", ""),
    ]
    for bucket in [large_excel, structured]:
        for item in bucket.get("results", []):
            dataset = item.get("dataset", {})
            overview = dataset.get("wiki_pages", {}).get("overview", "")
            if overview:
                result["evidence"].append(overview)
            if item.get("status") == "failed":
                result["status"] = "warning"
                result["risks"].append(item.get("error", "Fact-layer registration failed."))
    result["next_actions"].append("后续库存/销量/财务/广告查询应优先走 DuckDB marts。")
    return json.dumps(_append_result(task_id, result), ensure_ascii=False, indent=2)


def run_wiki_ingest_task(task_id: str, limit: int = 10) -> str:
    """子任务：把 raw 资料整理进 Obsidian，并返回生成的 wiki 页面。"""
    result = _json_tool("wiki_ingest", lambda: ingest_all_raw_files(limit=limit))
    pages = json.loads(list_wiki_pages()).get("pages", [])
    result["evidence"] = [page["path"] for page in pages]
    result["data"]["wiki_pages_after_ingest"] = pages
    return json.dumps(_append_result(task_id, result), ensure_ascii=False, indent=2)


def run_quality_task(task_id: str, decision_goal: str = "company_decision") -> str:
    """子任务：执行数据质量门，判断是否能进入辅助决策。"""
    result = _json_tool("data_quality", lambda: assess_data_quality(decision_goal))
    quality = result.get("data", {})
    missing = quality.get("missing_field_groups", [])
    warnings = quality.get("warnings", [])
    if quality.get("quality_level") in {"low", "medium"}:
        result["status"] = "warning"
    result["summary"] = f"Data quality is {quality.get('quality_level', 'unknown')}."
    result["missing_data"] = missing
    result["risks"] = warnings
    result["evidence"] = [item.get("path", item.get("name", "")) for item in json.loads(list_business_files()).get("files", [])]
    if missing:
        result["next_actions"].append(f"补齐关键字段组：{', '.join(missing)}。")
    return json.dumps(_append_result(task_id, result), ensure_ascii=False, indent=2)


def run_wiki_memory_task(task_id: str) -> str:
    """子任务：从 cleaned 数据生成字段字典和清洗规则，沉淀到 Obsidian。"""
    dictionary_result = _json_tool("data_dictionary_generation", generate_data_dictionary)
    rules_result = _json_tool("cleaning_rules_generation", generate_cleaning_rules)
    combined = {
        "task": "wiki_memory",
        "status": "success" if dictionary_result["status"] == "success" and rules_result["status"] == "success" else "warning",
        "summary": "Generated Obsidian data dictionaries and cleaning rules from cleaned files.",
        "evidence": [
            item["wiki_path"]
            for result in [dictionary_result, rules_result]
            for item in result.get("data", {}).get("generated", [])
        ],
        "risks": dictionary_result.get("risks", []) + rules_result.get("risks", []),
        "missing_data": [],
        "next_actions": ["检查 data-dictionary 与 cleaning-rules 页面，把业务口径补充完整。"],
        "data": {
            "data_dictionary": dictionary_result.get("data", {}),
            "cleaning_rules": rules_result.get("data", {}),
        },
    }
    return json.dumps(_append_result(task_id, combined), ensure_ascii=False, indent=2)


def run_lightrag_index_task(task_id: str) -> str:
    """子任务：同步完整 LightRAG Server；不可用时重建本地兜底索引。"""
    result = _json_tool("lightrag_index", sync_obsidian_to_official_lightrag)
    data = result.get("data", {})
    try:
        data["processing_status"] = json.loads(summarize_lightrag_processing_status(limit=20))
    except Exception as exc:
        data["processing_status"] = {"status": "unavailable", "error": str(exc)}
    result["data"] = data
    fallback = data.get("local_fallback_index", {})
    if data.get("status") == "unavailable":
        result["status"] = "warning"
        result["summary"] = "Official LightRAG Server is unavailable; rebuilt local fallback index."
    else:
        result["summary"] = (
            f"LightRAG sync completed: {len(data.get('inserted', []))} inserted, "
            f"{len(data.get('skipped', []))} skipped, {len(data.get('failed', []))} failed."
        )
        if data.get("failed"):
            result["status"] = "warning"
            result["risks"].append("部分文档同步完整 LightRAG 失败，已保留本地兜底索引。")
    result["evidence"] = [data.get("sync_state_path", ""), fallback.get("index_path", "")]
    appended = _append_result(task_id, result)
    record_audit_event(
        "lightrag_sync_completed",
        summary=appended.get("summary", ""),
        task_id=task_id,
        paths=[item for item in appended.get("evidence", []) if item],
        risks=appended.get("risks", []),
    )
    return json.dumps(appended, ensure_ascii=False, indent=2)


def run_finance_task(task_id: str) -> str:
    """子任务：公司级财务和现金流分析。"""
    result = _json_tool("finance_analysis", analyze_company_financial_position)
    data = result.get("data", {})
    result["risks"] = data.get("risks", [])
    result["evidence"] = data.get("data_sources", [])
    return json.dumps(_append_result(task_id, result), ensure_ascii=False, indent=2)


def run_company_strategy_task(task_id: str, focus: str = "next_month") -> str:
    """子任务：公司级经营策略分析。"""
    result = _json_tool("company_strategy", lambda: analyze_company_strategy(focus))
    data = result.get("data", {})
    result["summary"] = f"Company decision readiness: {data.get('company_decision_readiness', 'unknown')}."
    result["missing_data"] = data.get("key_data_gaps", [])
    result["next_actions"] = data.get("recommended_actions", [])
    evidence_chain = data.get("evidence_chain", {})
    result["evidence"] = [
        *evidence_chain.get("wiki_pages", []),
        evidence_chain.get("duckdb_path", ""),
        evidence_chain.get("registry_path", ""),
        *evidence_chain.get("manifest_paths", []),
        *evidence_chain.get("report_paths", []),
    ]
    return json.dumps(_append_result(task_id, result), ensure_ascii=False, indent=2)


def _merge_step_evidence_chains(steps: list[dict[str, Any]]) -> dict[str, Any]:
    merged = {
        "wiki_pages": [],
        "duckdb_path": "",
        "registry_path": "",
        "duckdb_marts": [],
        "data_gaps": [],
        "manifest_paths": [],
        "report_paths": [],
    }
    mart_fields: dict[str, set[str]] = {}
    for step in steps:
        chain = step.get("data", {}).get("evidence_chain", {})
        if not chain:
            continue
        for key in ["wiki_pages", "data_gaps", "manifest_paths", "report_paths"]:
            merged[key].extend(chain.get(key, []))
        merged["duckdb_path"] = merged["duckdb_path"] or chain.get("duckdb_path", "")
        merged["registry_path"] = merged["registry_path"] or chain.get("registry_path", "")
        for mart in chain.get("duckdb_marts", []):
            mart_name = str(mart.get("mart", "")).strip()
            if mart_name:
                mart_fields.setdefault(mart_name, set()).update(str(field) for field in mart.get("fields", []) if str(field).strip())

    for key in ["wiki_pages", "data_gaps", "manifest_paths", "report_paths"]:
        seen = set()
        merged[key] = [item for item in merged[key] if item and not (item in seen or seen.add(item))]
    merged["duckdb_marts"] = [{"mart": mart, "fields": sorted(fields)} for mart, fields in sorted(mart_fields.items())]
    return merged


def finalize_workflow_report(task_id: str, title: str = "") -> str:
    """汇总所有子任务结果，保存公司级辅助决策报告，并把关键结论写入 Obsidian。"""
    task = _load_task(task_id)
    final_title = title.strip() or f"Workflow report: {task['goal']}"
    lines = [
        f"# {final_title}",
        "",
        f"- Task ID: `{task_id}`",
        f"- Goal: {task.get('goal', '')}",
        f"- Created at: {task.get('created_at', '')}",
        f"- Updated at: {_now()}",
        "",
        "## Subtask Results",
    ]
    overall_risks = []
    missing_data = []
    next_actions = []
    evidence = []
    for step in task.get("steps", []):
        lines.extend(
            [
                "",
                f"### {step.get('task', 'unknown')}",
                f"- Status: {step.get('status', '')}",
                f"- Summary: {step.get('summary', '')}",
            ]
        )
        if step.get("risks"):
            lines.append(f"- Risks: {'; '.join(step['risks'][:8])}")
            overall_risks.extend(step["risks"])
        if step.get("missing_data"):
            lines.append(f"- Missing data: {', '.join(step['missing_data'])}")
            missing_data.extend(step["missing_data"])
        if step.get("next_actions"):
            lines.append(f"- Next actions: {'; '.join(step['next_actions'][:8])}")
            next_actions.extend(step["next_actions"])
        evidence.extend(step.get("evidence", []))

    lines.extend(
        [
            "",
            "## Consolidated View",
            f"- Evidence: {', '.join(sorted({item for item in evidence if item})[:30]) or 'None'}",
            f"- Missing data: {', '.join(sorted(set(missing_data))) or 'None'}",
            f"- Key risks: {'; '.join(overall_risks[:12]) or 'None'}",
            f"- Recommended next actions: {'; '.join(next_actions[:12]) or 'None'}",
            "",
            "## Human Confirmation",
            "- 大额采购、融资、税务、合同、外发消息和真实订单必须人工确认。",
        ]
    )
    step_evidence_chain = _merge_step_evidence_chains(task.get("steps", []))
    if any(step_evidence_chain.get(key) for key in ["wiki_pages", "duckdb_marts", "data_gaps", "manifest_paths", "report_paths"]):
        lines.extend(["", _format_evidence_chain_markdown(step_evidence_chain)])
    content = "\n".join(lines)
    report_result = json.loads(save_decision_report(final_title, content))
    append_decision_note(final_title, f"- Task ID: `{task_id}`\n- Report: `{report_result['saved_to']}`\n\n{content[:3000]}")
    record_audit_event(
        "workflow_report_finalized",
        summary=final_title,
        task_id=task_id,
        paths=[report_result.get("saved_to", "")],
        risks=overall_risks[:20],
        metadata={"missing_data": sorted(set(missing_data))[:50]},
    )
    task["status"] = "success"
    task["updated_at"] = _now()
    task["final_report"] = report_result
    _save_task(task)
    _task_queue().complete(
        task_id,
        worker_id=_durable_worker_id(task_id),
        summary=final_title,
        result=report_result,
    )
    return json.dumps({"task_id": task_id, "status": "success", "report": report_result, "summary": content[:2500]}, ensure_ascii=False, indent=2)


def run_full_company_workflow(task_id: str, limit: int = 10) -> str:
    """同步执行完整公司经营大脑流水线，适合脚本或可恢复后台队列调用。"""
    task = _load_task(task_id)
    if task.get("status") in _TERMINAL_STATUSES:
        return get_workflow_task_status(task_id)

    step_functions: list[tuple[str, Callable[[], str]]] = [
        ("raw_discovery", lambda: run_raw_discovery_task(task_id)),
        ("large_excel_pipeline", lambda: run_large_excel_pipeline_task(task_id)),
        ("excel_cleaning", lambda: run_excel_cleaning_task(task_id)),
        ("fact_layer_registration", lambda: run_fact_layer_registration_task(task_id)),
        ("wiki_ingest", lambda: run_wiki_ingest_task(task_id, limit=limit)),
        ("wiki_memory", lambda: run_wiki_memory_task(task_id)),
        ("lightrag_index", lambda: run_lightrag_index_task(task_id)),
        ("data_quality", lambda: run_quality_task(task_id, "company_decision")),
        ("finance_analysis", lambda: run_finance_task(task_id)),
        ("company_strategy", lambda: run_company_strategy_task(task_id, "next_month")),
    ]
    completed_steps = {
        str(step.get("task"))
        for step in task.get("steps", [])
        if step.get("status") in {"success", "warning"}
    }
    for _name, fn in step_functions:
        if _name in completed_steps:
            continue
        if _is_cancelled(task_id):
            _mark_cancelled(task_id)
            return get_workflow_task_status(task_id)
        worker_id = _durable_worker_id(task_id)
        _task_queue().set_current_step(task_id, step_name=_name, worker_id=worker_id)
        _task_queue().heartbeat(task_id, worker_id=worker_id, lease_seconds=_DURABLE_LEASE_SECONDS)
        fn()
        _task_queue().heartbeat(task_id, worker_id=worker_id, lease_seconds=_DURABLE_LEASE_SECONDS)
    if _is_cancelled(task_id):
        _mark_cancelled(task_id)
        return get_workflow_task_status(task_id)
    latest = _load_task(task_id)
    if not latest.get("final_report"):
        finalize_workflow_report(task_id, title="公司经营大脑全链路辅助决策报告")
    return get_workflow_task_status(task_id)


def _workflow_runner(task_id: str, limit: int) -> str:
    runner = _WORKFLOW_RUNNER or run_full_company_workflow
    return runner(task_id, limit)


def _enqueue_workflow_task(task_id: str, *, limit: int = 10, recovered: bool = False) -> bool:
    with _WORKFLOW_QUEUE_LOCK:
        existing = _BACKGROUND_THREADS.get(task_id)
        if existing and existing.is_alive():
            return False

        task = _load_task(task_id)
        if task.get("status") in _TERMINAL_STATUSES:
            return False
        queue = _task_queue()
        task.setdefault("idempotency_key", _workflow_idempotency_key(str(task.get("goal") or task_id), str(task.get("requested_by") or "workflow")))
        queue.upsert_from_json(task)
        previous_status = task.get("status")
        task["status"] = "queued"
        task["run_mode"] = "recoverable_worker_queue"
        task["queued_at"] = task.get("queued_at") or _now()
        task["updated_at"] = _now()
        if recovered:
            task["recovered_from_interrupted_run"] = True
            task["recovered_at"] = _now()
            task["previous_status_before_recovery"] = previous_status
        _save_task(task)
        queue.mark_queued(task_id, recovered=recovered)
        worker_id = f"pid-{os.getpid()}:{task_id}"

        def _runner() -> None:
            try:
                claim = queue.claim_task(task_id, worker_id=worker_id, lease_seconds=_DURABLE_LEASE_SECONDS)
                if claim is None:
                    return
                task_inner = _load_task(task_id)
                if task_inner.get("status") in _TERMINAL_STATUSES:
                    return
                task_inner["status"] = "running"
                task_inner["started_at"] = task_inner.get("started_at") or _now()
                task_inner["last_worker_started_at"] = _now()
                task_inner["durable_worker_id"] = worker_id
                task_inner["durable_claim"] = claim
                task_inner["updated_at"] = _now()
                _save_task(task_inner)
                _workflow_runner(task_id, limit)
            except Exception as exc:
                task_failed = _load_task(task_id)
                task_failed["status"] = "failed"
                task_failed["updated_at"] = _now()
                task_failed.setdefault("steps", []).append(
                    {
                        "task": "background_workflow",
                        "status": "failed",
                        "summary": str(exc),
                        "completed_at": _now(),
                        "evidence": [],
                        "risks": [str(exc)],
                        "missing_data": [],
                        "next_actions": ["检查后端日志和 task JSON 后重试。"],
                        "data": {},
                    }
                )
                _save_task(task_failed)
                queue.fail(
                    task_id,
                    worker_id=worker_id,
                    step_name="background_workflow",
                    reason=str(exc),
                    retryable=False,
                )

        thread = threading.Thread(target=_runner, name=f"a2a-workflow-{task_id[:20]}", daemon=True)
        _BACKGROUND_THREADS[task_id] = thread
        thread.start()
        return True


def recover_workflow_queue(limit: int = 10) -> str:
    """恢复磁盘上 queued/running 的全链路任务，适合后端启动时调用。"""
    _ensure_task_dir()
    queue = _task_queue()
    reclaimed = queue.reclaim_expired()
    recovered = []
    skipped = []
    for path in sorted(TASK_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            skipped.append({"path": str(path), "reason": "invalid_json"})
            continue
        task_id = str(task.get("task_id") or "")
        status = str(task.get("status") or "")
        if status == "cancelling":
            task["status"] = "cancelled"
            task["updated_at"] = _now()
            atomic_write_json(path, task)
            skipped.append({"task_id": task_id, "reason": "legacy_cancelling_marked_cancelled"})
            continue
        if not task_id or status not in _RECOVERABLE_STATUSES:
            continue
        task["path"] = str(path)
        task.setdefault("idempotency_key", _workflow_idempotency_key(str(task.get("goal") or task_id), str(task.get("requested_by") or "workflow")))
        queue.upsert_from_json(task)
        if _enqueue_workflow_task(task_id, limit=limit, recovered=status == "running"):
            recovered.append({"task_id": task_id, "previous_status": status})
        else:
            skipped.append({"task_id": task_id, "reason": "already_running_or_terminal"})
    return json.dumps(
        {
            "status": "success",
            "task_dir": str(TASK_DIR),
            "durable_queue": str(queue.db_path),
            "reclaimed": len(reclaimed),
            "recovered": len(recovered),
            "tasks": recovered,
            "skipped": skipped,
        },
        ensure_ascii=False,
        indent=2,
    )


def start_company_workflow_task(goal: str, limit: int = 10) -> str:
    """创建并后台启动完整公司经营大脑流水线，前端可用 task_id 查询进度。"""
    if not _should_start_background_company_workflow(goal):
        return json.dumps(
            {
                "status": "rejected",
                "reason": "analysis_request_should_use_existing_data",
                "message": "这是基于已有数据的分析问题，已拒绝启动 raw/Obsidian/LightRAG 后台重处理流程。",
                "recommended_action": "直接调用数据、知识库和决策分析工具回答用户问题。",
            },
            ensure_ascii=False,
            indent=2,
        )
    created = json.loads(
        create_workflow_task(
            goal,
            requested_by="frontend_background",
            idempotency_key=_workflow_idempotency_key(goal, "frontend_background"),
        )
    )
    task_id = created["task_id"]
    task = _load_task(task_id)
    if task.get("status") in _TERMINAL_STATUSES:
        return json.dumps(
            {
                "task_id": task_id,
                "status": task.get("status"),
                "message": "同一个 idempotency key 的任务已存在且处于终态，未重复创建。",
                "saved_to": created["saved_to"],
            },
            ensure_ascii=False,
            indent=2,
        )
    if task.get("status") in _RECOVERABLE_STATUSES:
        _enqueue_workflow_task(task_id, limit=limit, recovered=task.get("status") == "running")
        return json.dumps(
            {
                "task_id": task_id,
                "status": task.get("status"),
                "message": "同一个 idempotency key 的任务已存在，未重复创建。",
                "saved_to": created["saved_to"],
            },
            ensure_ascii=False,
            indent=2,
        )
    task["status"] = "queued"
    task["run_mode"] = "recoverable_worker_queue"
    task["updated_at"] = _now()
    _save_task(task)
    _enqueue_workflow_task(task_id, limit=limit)
    return json.dumps(
        {
            "task_id": task_id,
            "status": "queued",
            "message": "可恢复后台任务已入队。请用 get_workflow_task_status 或 list_workflow_tasks 查看进度。",
            "saved_to": created["saved_to"],
        },
        ensure_ascii=False,
        indent=2,
    )
