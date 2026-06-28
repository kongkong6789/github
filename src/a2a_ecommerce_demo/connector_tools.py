from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from src.a2a_ecommerce_demo.connector_registry import (
    CONNECTOR_REGISTRY_PATH,
    PROJECT_ROOT,
    connector_snapshot_path,
    ensure_connector_registry,
    get_connector_dataset,
    get_connector_spec,
    normalize_connector_id,
    record_connector_sync,
)
from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event
from src.a2a_ecommerce_demo.fact_layer_tools import register_connector_snapshot_dataset


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_env() -> None:
    env_path = Path(os.getenv("A2A_ENV_PATH", PROJECT_ROOT / ".env")).expanduser()
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


def _configured_env(names: list[str]) -> dict[str, bool]:
    _load_env()
    return {name: bool(os.getenv(name, "").strip()) for name in names}


def _credential_status(connector: dict[str, Any], credential_config: dict[str, bool]) -> tuple[bool, list[str]]:
    alternative_sets = [
        [str(name) for name in item if str(name)]
        for item in connector.get("credential_alternative_sets", [])
        if isinstance(item, list | tuple)
    ]
    if not alternative_sets:
        missing = [name for name, configured in credential_config.items() if not configured]
        return not missing, missing

    for candidate in alternative_sets:
        if candidate and all(credential_config.get(name, False) for name in candidate):
            return True, []
    missing_by_candidate = [
        [name for name in candidate if not credential_config.get(name, False)]
        for candidate in alternative_sets
        if candidate
    ]
    shortest_missing = min(missing_by_candidate, key=len) if missing_by_candidate else []
    return False, shortest_missing


def _connector_health(connector: dict[str, Any]) -> dict[str, Any]:
    skill_dir_text = str(connector.get("skill_dir", "")).strip()
    skill_dir = Path(skill_dir_text).expanduser() if skill_dir_text else Path(".").resolve()
    required_files = [str(item) for item in connector.get("required_files", [])]
    skill_dir_required = bool(skill_dir_text or required_files)
    missing_files = [file_name for file_name in required_files if not (skill_dir / file_name).exists()]
    credential_config = _configured_env([str(item) for item in connector.get("credential_env_names", [])])
    credential_ready, missing_credentials = _credential_status(connector, credential_config)
    warnings = []
    if skill_dir_required and not skill_dir.exists():
        warnings.append("Skill/API directory is missing.")
    if missing_files:
        warnings.append(f"Missing required files: {', '.join(missing_files)}.")
    if missing_credentials:
        warnings.append(f"Missing credential env vars: {', '.join(missing_credentials)}.")
    status = "ready"
    if skill_dir_required and (not skill_dir.exists() or missing_files):
        status = "missing_skill"
    elif not credential_ready:
        status = "needs_config"
    return {
        "connector_id": connector.get("connector_id", ""),
        "display_name": connector.get("display_name", ""),
        "system": connector.get("system", ""),
        "status": status,
        "read_only": bool(connector.get("read_only_default", True)),
        "write_requires_confirmation": bool(connector.get("write_requires_confirmation", True)),
        "external_write_enabled": bool(connector.get("external_write_enabled", False)),
        "permission_scope": connector.get("permission_scope", "read_only"),
        "permission_policy": connector.get("permission_policy", {}),
        "skill_dir": str(skill_dir),
        "skill_dir_exists": skill_dir.exists(),
        "missing_files": missing_files,
        "credential_config": credential_config,
        "datasets": sorted(connector.get("datasets", {}).keys()),
        "last_sync": connector.get("last_sync", {}),
        "warnings": warnings,
    }


def list_erp_connectors() -> str:
    """列出已纳管的 ERP/API connector，不返回任何密钥值。"""
    registry = ensure_connector_registry()
    connectors = list(registry.get("connectors", {}).values())
    return _json(
        {
            "registry_path": str(CONNECTOR_REGISTRY_PATH),
            "connector_count": len(connectors),
            "p3_ingestion_policy": registry.get("p3_ingestion_policy", {}),
            "connectors": [
                {
                    "connector_id": connector.get("connector_id", ""),
                    "display_name": connector.get("display_name", ""),
                    "system": connector.get("system", ""),
                    "kind": connector.get("kind", ""),
                    "source": connector.get("source", ""),
                    "read_only_default": bool(connector.get("read_only_default", True)),
                    "write_requires_confirmation": bool(connector.get("write_requires_confirmation", True)),
                    "external_write_enabled": bool(connector.get("external_write_enabled", False)),
                    "permission_scope": connector.get("permission_scope", "read_only"),
                    "permission_policy": connector.get("permission_policy", {}),
                    "allowed_actions": connector.get("allowed_actions", []),
                    "datasets": sorted(connector.get("datasets", {}).keys()),
                    "domestic_platforms": connector.get("domestic_platforms", []),
                }
                for connector in connectors
            ],
        }
    )


def get_erp_connector_health(connector_id: str = "") -> str:
    """检查吉客云/金蝶 connector 的本地目录、必要文件和凭据环境变量配置。"""
    connector_id = normalize_connector_id(connector_id)
    registry = ensure_connector_registry()
    connectors = registry.get("connectors", {})
    selected = [get_connector_spec(connector_id)] if connector_id else list(connectors.values())
    health_items = [_connector_health(connector) for connector in selected]
    ready_count = sum(1 for item in health_items if item["status"] == "ready")
    record_audit_event(
        "connector_health_checked",
        summary="Checked ERP connector health.",
        metadata={"connector_id": connector_id or "all", "ready_count": ready_count, "connector_count": len(health_items)},
    )
    return _json(
        {
            "registry_path": str(CONNECTOR_REGISTRY_PATH),
            "connector_count": len(health_items),
            "ready_count": ready_count,
            "connectors": health_items,
        }
    )


def preview_erp_connector_sync(connector_id: str, dataset: str) -> str:
    """预览只读 connector 同步，不调用真实 ERP API，也不写业务数据。"""
    connector_id = normalize_connector_id(connector_id)
    connector = get_connector_spec(connector_id)
    dataset_spec = get_connector_dataset(connector_id, dataset)
    preview_path = connector_snapshot_path(connector_id, dataset, timestamp="preview")
    record_audit_event(
        "connector_sync_previewed",
        summary=f"Previewed {connector_id}/{dataset} connector sync.",
        metadata={"connector_id": connector_id, "dataset": dataset, "snapshot_path": str(preview_path)},
    )
    return _json(
        {
            "status": "preview",
            "connector_id": connector_id,
            "display_name": connector.get("display_name", ""),
            "dataset": dataset,
            "dataset_label": dataset_spec.get("label", ""),
            "description": dataset_spec.get("description", ""),
            "read_only": True,
            "external_write_enabled": bool(connector.get("external_write_enabled", False)),
            "permission_scope": connector.get("permission_scope", "read_only"),
            "permission_policy": connector.get("permission_policy", {}),
            "can_register_fact_layer": bool(dataset_spec.get("mart_candidates")),
            "schema": {
                "columns": dataset_spec.get("columns", []),
                "mart_candidates": dataset_spec.get("mart_candidates", []),
            },
            "target_snapshot_path": str(preview_path),
            "denied_write_actions": connector.get("denied_write_actions", []),
            "required_env": connector.get("credential_env_names", []),
            "configured_env": _configured_env([str(item) for item in connector.get("credential_env_names", [])]),
        }
    )


def _parse_rows(rows_json: str) -> list[dict[str, Any]]:
    try:
        rows = json.loads(rows_json)
    except json.JSONDecodeError as exc:
        raise ValueError("rows_json must be a JSON array of objects.") from exc
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("rows_json must be a JSON array of objects.")
    return rows


def _write_snapshot_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    extras = [key for row in rows for key in row if key not in columns]
    headers = columns + sorted(set(extras))
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def sync_connector_dataset(
    connector_id: str,
    dataset: str,
    rows_json: str = "",
    dry_run: bool = True,
) -> str:
    """把已获取的只读 ERP 快照写入 staging，并可注册进 DuckDB fact layer。

    这个工具当前不直接调用真实吉客云/金蝶 API。外部 adapter 或人工导出的
    只读结果应通过 rows_json 传入，写入类 ERP 动作仍由人工确认流程另行治理。
    """
    connector_id = normalize_connector_id(connector_id)
    connector = get_connector_spec(connector_id)
    dataset_spec = get_connector_dataset(connector_id, dataset)
    if dry_run or not rows_json.strip():
        return preview_erp_connector_sync(connector_id, dataset)
    rows = _parse_rows(rows_json)
    snapshot_path = connector_snapshot_path(connector_id, dataset)
    _write_snapshot_csv(snapshot_path, rows, [str(item) for item in dataset_spec.get("columns", [])])
    fact_dataset = register_connector_snapshot_dataset(str(snapshot_path), connector_id=connector_id, connector_dataset=dataset)
    run = {
        "dataset": dataset,
        "status": "success",
        "snapshot_path": str(snapshot_path),
        "row_count": len(rows),
        "dataset_slug": fact_dataset.get("dataset_slug", ""),
        "duckdb_path": fact_dataset.get("duckdb_path", ""),
        "registry_path": fact_dataset.get("registry_path", ""),
        "completed_at": _now(),
    }
    record_connector_sync(connector_id, run, status="ready")
    record_audit_event(
        "connector_sync_completed",
        summary=f"Registered {connector_id}/{dataset} connector snapshot.",
        paths=[str(snapshot_path)],
        metadata={
            "connector_id": connector_id,
            "dataset": dataset,
            "row_count": len(rows),
            "dataset_slug": fact_dataset.get("dataset_slug", ""),
        },
    )
    return _json(
        {
            "status": "success",
            "connector_id": connector_id,
            "display_name": connector.get("display_name", ""),
            "dataset_name": dataset,
            "read_only": True,
            "external_write_enabled": bool(connector.get("external_write_enabled", False)),
            "permission_scope": connector.get("permission_scope", "read_only"),
            "snapshot_path": str(snapshot_path),
            "row_count": len(rows),
            "dataset": fact_dataset,
        }
    )
