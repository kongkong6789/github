#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.a2a_ecommerce_demo.task_queue import TaskQueue, default_task_db_path  # noqa: E402


def _default_task_dir() -> Path:
    data_dir = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
    return Path(os.getenv("A2A_TASK_DIR", data_dir / "tasks")).resolve()


def _load_task(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except json.JSONDecodeError as exc:
        return None, f"invalid_json: {exc}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import existing data/tasks/*.json task logs into the SQLite durable queue.")
    parser.add_argument("--task-dir", type=Path, default=_default_task_dir(), help="Directory containing task JSON files.")
    parser.add_argument("--db-path", type=Path, default=default_task_db_path(), help="SQLite queue database path.")
    parser.add_argument("--write", action="store_true", help="Write imports. Omit this flag for a dry run.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of JSON task files to scan.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    task_dir = args.task_dir.expanduser().resolve()
    db_path = args.db_path.expanduser().resolve()
    files = sorted(task_dir.glob("*.json"), key=lambda item: item.stat().st_mtime)
    if args.limit > 0:
        files = files[: args.limit]

    queue = TaskQueue(db_path) if args.write else None
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    planned: list[dict[str, Any]] = []

    for path in files:
        task, error = _load_task(path)
        if task is None:
            skipped.append({"path": str(path), "reason": error})
            continue
        task_id = str(task.get("task_id") or "").strip()
        if not task_id:
            skipped.append({"path": str(path), "reason": "missing_task_id"})
            continue
        summary = {
            "task_id": task_id,
            "goal": task.get("goal", ""),
            "status": task.get("status", ""),
            "path": str(path),
            "idempotency_key": task.get("idempotency_key") or f"legacy:{task_id}",
        }
        if not args.write:
            planned.append(summary)
            continue
        task["path"] = str(path)
        durable = queue.upsert_from_json(task) if queue else {}
        imported.append({**summary, "durable_status": durable.get("status", "")})

    print(
        json.dumps(
            {
                "status": "success",
                "dry_run": not args.write,
                "task_dir": str(task_dir),
                "db_path": str(db_path),
                "scanned": len(files),
                "planned": planned,
                "imported": imported,
                "skipped": skipped,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
