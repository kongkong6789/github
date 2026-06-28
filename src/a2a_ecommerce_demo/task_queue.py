from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TERMINAL_STATUSES = {"success", "completed", "failed", "cancelled"}
CLAIMABLE_STATUSES = {"queued", "recoverable", "retrying"}
TASK_QUEUE_SCHEMA_VERSION = 1
P17_TASK_EVENT_TYPES = {
    "handoff.created",
    "qa.pass",
    "qa.fail",
    "qa.escalated",
}


def default_task_db_path() -> Path:
    data_dir = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
    task_dir = Path(os.getenv("A2A_TASK_DIR", data_dir / "tasks")).resolve()
    configured = os.getenv("A2A_TASK_QUEUE_DB") or os.getenv("A2A_TASK_DB")
    return Path(configured).expanduser().resolve() if configured else task_dir / "tasks.sqlite"


def _slugify(value: str, fallback: str = "workflow") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", value).strip("-")
    return slug[:48] or fallback


def _now_datetime() -> datetime:
    return datetime.now()


def _coerce_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return _now_datetime()
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(value)


def _format_time(value: datetime | str | None = None) -> str:
    return _coerce_datetime(value).strftime("%Y-%m-%d %H:%M:%S")


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _json_load(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _make_task_id(goal: str, now: datetime | str | None = None) -> str:
    timestamp = _format_time(now).replace("-", "").replace(":", "").replace(" ", "-")
    digest = hashlib.sha256(f"{goal}:{timestamp}".encode("utf-8")).hexdigest()[:8]
    return f"{timestamp}-{digest}-{_slugify(goal)}"


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


class TaskQueue:
    """SQLite-backed durable queue for long-running workflow tasks."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or default_task_db_path()).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _migrate(self) -> None:
        with self._transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    current_step TEXT,
                    error_code TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    json_path TEXT
                );

                CREATE TABLE IF NOT EXISTS task_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    step_name TEXT,
                    status TEXT,
                    summary TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    error_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_artifacts (
                    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    label TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS task_retries (
                    retry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_name TEXT,
                    attempt INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status_created
                    ON tasks(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_task_events_task_timestamp
                    ON task_events(task_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_task_claims_active
                    ON task_claims(task_id, status, expires_at);
                CREATE INDEX IF NOT EXISTS idx_task_artifacts_task
                    ON task_artifacts(task_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_task_retries_task
                    ON task_retries(task_id, attempt);
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (TASK_QUEUE_SCHEMA_VERSION, _format_time()),
            )

    def _row_to_task(self, row: sqlite3.Row) -> dict[str, Any]:
        task = dict(row)
        task["cancel_requested"] = bool(task.get("cancel_requested"))
        task["payload"] = _json_load(task.pop("payload_json", "{}"))
        task["result"] = _json_load(task.pop("result_json", "{}"))
        return task

    def _insert_event(
        self,
        conn: sqlite3.Connection,
        task_id: str,
        *,
        event_type: str,
        timestamp: str,
        step_name: str = "",
        status: str = "",
        summary: str = "",
        payload: Any = None,
        error: Any = None,
    ) -> dict[str, Any]:
        cursor = conn.execute(
            """
            INSERT INTO task_events(
                task_id, timestamp, event_type, step_name, status, summary, payload_json, error_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, timestamp, event_type, step_name, status, summary, _json_dump(payload), _json_dump(error)),
        )
        return {
            "event_id": cursor.lastrowid,
            "task_id": task_id,
            "timestamp": timestamp,
            "event_type": event_type,
            "step_name": step_name,
            "status": status,
            "summary": summary,
            "payload": payload or {},
            "error": error or {},
        }

    def enqueue(
        self,
        *,
        goal: str,
        requested_by: str,
        idempotency_key: str,
        task_id: str = "",
        status: str = "queued",
        max_attempts: int = 3,
        payload: dict[str, Any] | None = None,
        json_path: str = "",
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required for durable workflow tasks")
        timestamp = _format_time(now)
        final_task_id = task_id.strip() or _make_task_id(goal, timestamp)
        with self._transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM tasks WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                return self._row_to_task(existing)
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, goal, status, requested_by, created_at, updated_at, idempotency_key,
                    max_attempts, payload_json, json_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    final_task_id,
                    goal,
                    status,
                    requested_by,
                    timestamp,
                    timestamp,
                    idempotency_key,
                    max(1, int(max_attempts)),
                    _json_dump(payload),
                    json_path,
                ),
            )
            self._insert_event(
                conn,
                final_task_id,
                event_type="task_enqueued",
                timestamp=timestamp,
                status=status,
                summary=goal,
                payload={"requested_by": requested_by, "idempotency_key": idempotency_key},
            )
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (final_task_id,)).fetchone()
            return self._row_to_task(row)

    def upsert_from_json(
        self,
        task: dict[str, Any],
        *,
        idempotency_key: str = "",
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        task_id = str(task.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("task_id is required to import a JSON task")
        final_key = (idempotency_key or str(task.get("idempotency_key") or "") or f"legacy:{task_id}").strip()
        current_step = ""
        raw_steps = task.get("steps")
        steps: list[dict[str, Any]] = raw_steps if isinstance(raw_steps, list) else []
        if steps:
            current_step = str(steps[-1].get("task") or "")
        timestamp = _format_time(task.get("updated_at") or None)
        with self._transaction() as conn:
            existing = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO tasks(
                        task_id, goal, status, requested_by, created_at, updated_at, started_at, finished_at,
                        cancel_requested, idempotency_key, current_step, error_code, max_attempts, json_path
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        str(task.get("goal") or ""),
                        str(task.get("status") or "queued"),
                        str(task.get("requested_by") or "json_import"),
                        str(task.get("created_at") or timestamp),
                        timestamp,
                        task.get("started_at") or None,
                        task.get("finished_at") or None,
                        1 if task.get("cancel_requested") else 0,
                        final_key,
                        current_step,
                        task.get("error_code") or None,
                        max(1, int(max_attempts)),
                        str(task.get("path") or ""),
                    ),
                )
                self._insert_event(
                    conn,
                    task_id,
                    event_type="task_imported_from_json",
                    timestamp=timestamp,
                    status=str(task.get("status") or "queued"),
                    summary=str(task.get("goal") or ""),
                    payload={"steps": len(steps)},
                )
            else:
                conn.execute(
                    """
                    UPDATE tasks
                    SET goal = ?, status = ?, requested_by = ?, updated_at = ?, started_at = COALESCE(?, started_at),
                        finished_at = COALESCE(?, finished_at), cancel_requested = ?, current_step = ?,
                        error_code = COALESCE(?, error_code), json_path = COALESCE(NULLIF(?, ''), json_path)
                    WHERE task_id = ?
                    """,
                    (
                        str(task.get("goal") or existing["goal"]),
                        str(task.get("status") or existing["status"]),
                        str(task.get("requested_by") or existing["requested_by"]),
                        timestamp,
                        task.get("started_at") or None,
                        task.get("finished_at") or None,
                        1 if task.get("cancel_requested") else 0,
                        current_step or existing["current_step"],
                        task.get("error_code") or None,
                        str(task.get("path") or ""),
                        task_id,
                    ),
                )
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return self._row_to_task(row)

    def count_tasks(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(f"Task not found in durable queue: {task_id}")
            return self._row_to_task(row)

    def list_tasks(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY updated_at DESC, created_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
            return [self._row_to_task(row) for row in rows]

    def mark_queued(self, task_id: str, *, recovered: bool = False, now: datetime | str | None = None) -> dict[str, Any]:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(f"Task not found in durable queue: {task_id}")
            if row["status"] in TERMINAL_STATUSES:
                return self._row_to_task(row)
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                ("recoverable" if recovered else "queued", timestamp, task_id),
            )
            self._insert_event(
                conn,
                task_id,
                event_type="task_recovered" if recovered else "task_queued",
                timestamp=timestamp,
                status="recoverable" if recovered else "queued",
                summary="Task returned to durable queue.",
            )
            updated = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return self._row_to_task(updated)

    def _active_claim(self, conn: sqlite3.Connection, task_id: str, now: str) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT * FROM task_claims
            WHERE task_id = ? AND status = 'active' AND expires_at > ?
            ORDER BY claim_id DESC
            LIMIT 1
            """,
            (task_id, now),
        ).fetchone()

    def _claim_row(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        worker_id: str,
        lease_seconds: int,
        now: datetime | str | None,
    ) -> dict[str, Any]:
        timestamp = _format_time(now)
        expires_at = _format_time(_coerce_datetime(now) + timedelta(seconds=max(1, int(lease_seconds))))
        task_id = str(row["task_id"])
        conn.execute(
            "UPDATE task_claims SET status = 'expired' WHERE task_id = ? AND status = 'active'",
            (task_id,),
        )
        cursor = conn.execute(
            """
            INSERT INTO task_claims(task_id, worker_id, claimed_at, heartbeat_at, expires_at, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (task_id, worker_id, timestamp, timestamp, expires_at),
        )
        conn.execute(
            """
            UPDATE tasks
            SET status = 'running',
                started_at = COALESCE(started_at, ?),
                updated_at = ?,
                attempt_count = attempt_count + 1
            WHERE task_id = ?
            """,
            (timestamp, timestamp, task_id),
        )
        self._insert_event(
            conn,
            task_id,
            event_type="task_claimed",
            timestamp=timestamp,
            status="running",
            summary=f"Claimed by {worker_id}.",
            payload={"worker_id": worker_id, "claim_id": cursor.lastrowid, "expires_at": expires_at},
        )
        return {
            "claim_id": cursor.lastrowid,
            "task_id": task_id,
            "worker_id": worker_id,
            "claimed_at": timestamp,
            "heartbeat_at": timestamp,
            "expires_at": expires_at,
            "status": "active",
        }

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 300,
        now: datetime | str | None = None,
    ) -> dict[str, Any] | None:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status IN ('queued', 'recoverable', 'retrying')
                  AND cancel_requested = 0
                  AND NOT EXISTS (
                    SELECT 1 FROM task_claims
                    WHERE task_claims.task_id = tasks.task_id
                      AND task_claims.status = 'active'
                      AND task_claims.expires_at > ?
                  )
                ORDER BY created_at ASC, task_id ASC
                LIMIT 1
                """,
                (timestamp,),
            ).fetchone()
            if row is None:
                return None
            return self._claim_row(conn, row, worker_id=worker_id, lease_seconds=lease_seconds, now=timestamp)

    def claim_task(
        self,
        task_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 300,
        now: datetime | str | None = None,
    ) -> dict[str, Any] | None:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None or row["status"] in TERMINAL_STATUSES or row["cancel_requested"]:
                return None
            active = self._active_claim(conn, task_id, timestamp)
            if active is not None:
                return None
            if row["status"] not in CLAIMABLE_STATUSES and row["status"] != "running":
                return None
            return self._claim_row(conn, row, worker_id=worker_id, lease_seconds=lease_seconds, now=timestamp)

    def heartbeat(
        self,
        task_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 300,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_time(now)
        expires_at = _format_time(_coerce_datetime(now) + timedelta(seconds=max(1, int(lease_seconds))))
        with self._transaction() as conn:
            claim = conn.execute(
                """
                SELECT * FROM task_claims
                WHERE task_id = ? AND worker_id = ? AND status = 'active'
                ORDER BY claim_id DESC
                LIMIT 1
                """,
                (task_id, worker_id),
            ).fetchone()
            if claim is None:
                return {"ok": False, "task_id": task_id, "worker_id": worker_id, "reason": "active_claim_not_found"}
            conn.execute(
                "UPDATE task_claims SET heartbeat_at = ?, expires_at = ? WHERE claim_id = ?",
                (timestamp, expires_at, claim["claim_id"]),
            )
            conn.execute("UPDATE tasks SET updated_at = ? WHERE task_id = ?", (timestamp, task_id))
            self._insert_event(
                conn,
                task_id,
                event_type="task_heartbeat",
                timestamp=timestamp,
                status="running",
                summary=f"Heartbeat from {worker_id}.",
                payload={"worker_id": worker_id, "expires_at": expires_at},
            )
            return {
                "ok": True,
                "task_id": task_id,
                "worker_id": worker_id,
                "heartbeat_at": timestamp,
                "expires_at": expires_at,
            }

    def set_current_step(
        self,
        task_id: str,
        *,
        step_name: str,
        worker_id: str = "",
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            conn.execute(
                "UPDATE tasks SET current_step = ?, updated_at = ? WHERE task_id = ?",
                (step_name, timestamp, task_id),
            )
            self._insert_event(
                conn,
                task_id,
                event_type="task_step_started",
                timestamp=timestamp,
                step_name=step_name,
                status="running",
                summary=f"Started step {step_name}.",
                payload={"worker_id": worker_id} if worker_id else {},
            )
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return self._row_to_task(row)

    def append_event(
        self,
        task_id: str,
        *,
        event_type: str,
        step_name: str = "",
        status: str = "",
        summary: str = "",
        payload: Any = None,
        error: Any = None,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            event = self._insert_event(
                conn,
                task_id,
                event_type=event_type,
                timestamp=timestamp,
                step_name=step_name,
                status=status,
                summary=summary,
                payload=payload,
                error=error,
            )
            conn.execute("UPDATE tasks SET updated_at = ? WHERE task_id = ?", (timestamp, task_id))
            return event

    def append_handoff_event(
        self,
        task_id: str,
        *,
        from_agent: str,
        to_agent: str,
        summary: str = "",
        evidence_paths: list[str] | None = None,
        next_actions: list[str] | None = None,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "evidence_paths": _as_text_list(evidence_paths),
            "next_actions": _as_text_list(next_actions),
        }
        return self.append_event(
            task_id,
            event_type="handoff.created",
            step_name="handoff",
            status="success",
            summary=summary or f"Handoff from {from_agent} to {to_agent}.",
            payload=payload,
            now=now,
        )

    def append_qa_gate_event(
        self,
        task_id: str,
        *,
        verdict: str,
        checked_by: str = "",
        summary: str = "",
        evidence_paths: list[str] | None = None,
        retry_count: int = 0,
        next_actions: list[str] | None = None,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        normalized = verdict.strip().upper()
        event_type_by_verdict = {
            "PASS": "qa.pass",
            "FAIL": "qa.fail",
            "ESCALATED": "qa.escalated",
        }
        event_type = event_type_by_verdict.get(normalized)
        if event_type is None:
            raise ValueError("verdict must be PASS, FAIL, or ESCALATED")
        payload = {
            "verdict": normalized,
            "checked_by": checked_by,
            "evidence_paths": _as_text_list(evidence_paths),
            "retry_count": max(0, int(retry_count)),
            "next_actions": _as_text_list(next_actions),
        }
        status = "success" if normalized == "PASS" else "failed" if normalized == "FAIL" else "warning"
        return self.append_event(
            task_id,
            event_type=event_type,
            step_name="qa_gate",
            status=status,
            summary=summary or f"QA gate {normalized}.",
            payload=payload,
            now=now,
        )

    def append_artifact(
        self,
        task_id: str,
        *,
        kind: str,
        path: str,
        label: str = "",
        metadata: dict[str, Any] | None = None,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO task_artifacts(task_id, kind, path, label, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, kind, path, label, timestamp, _json_dump(metadata)),
            )
            return {
                "artifact_id": cursor.lastrowid,
                "task_id": task_id,
                "kind": kind,
                "path": path,
                "label": label,
                "created_at": timestamp,
                "metadata": metadata or {},
            }

    def complete(
        self,
        task_id: str,
        *,
        worker_id: str = "",
        summary: str = "",
        result: dict[str, Any] | None = None,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'success', updated_at = ?, finished_at = ?, result_json = ?
                WHERE task_id = ? AND status NOT IN ('failed', 'cancelled')
                """,
                (timestamp, timestamp, _json_dump(result), task_id),
            )
            if worker_id:
                conn.execute(
                    """
                    UPDATE task_claims
                    SET status = 'completed', heartbeat_at = ?
                    WHERE task_id = ? AND worker_id = ? AND status = 'active'
                    """,
                    (timestamp, task_id, worker_id),
                )
            self._insert_event(
                conn,
                task_id,
                event_type="task_completed",
                timestamp=timestamp,
                status="success",
                summary=summary,
                payload=result or {},
            )
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return self._row_to_task(row)

    def fail(
        self,
        task_id: str,
        *,
        worker_id: str = "",
        step_name: str = "",
        reason: str = "",
        retryable: bool = True,
        error_code: str = "workflow_failed",
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(f"Task not found in durable queue: {task_id}")
            should_retry = bool(retryable and int(row["attempt_count"]) < int(row["max_attempts"]))
            next_status = "queued" if should_retry else "failed"
            finished_at = None if should_retry else timestamp
            if should_retry:
                conn.execute(
                    "INSERT INTO task_retries(task_id, step_name, attempt, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                    (task_id, step_name, int(row["attempt_count"]), reason, timestamp),
                )
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = ?, finished_at = COALESCE(?, finished_at),
                    error_code = CASE WHEN ? = 'failed' THEN ? ELSE error_code END
                WHERE task_id = ?
                """,
                (next_status, timestamp, finished_at, next_status, error_code, task_id),
            )
            if worker_id:
                conn.execute(
                    """
                    UPDATE task_claims
                    SET status = ?
                    WHERE task_id = ? AND worker_id = ? AND status = 'active'
                    """,
                    ("retry_scheduled" if should_retry else "failed", task_id, worker_id),
                )
            self._insert_event(
                conn,
                task_id,
                event_type="task_retry_scheduled" if should_retry else "task_failed",
                timestamp=timestamp,
                step_name=step_name,
                status=next_status,
                summary=reason,
                error={"reason": reason, "error_code": error_code},
            )
            updated = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return self._row_to_task(updated)

    def cancel(
        self,
        task_id: str,
        *,
        requested_by: str,
        final: bool = False,
        now: datetime | str | None = None,
    ) -> dict[str, Any]:
        timestamp = _format_time(now)
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise FileNotFoundError(f"Task not found in durable queue: {task_id}")
            if row["status"] in TERMINAL_STATUSES:
                return self._row_to_task(row)
            next_status = "running" if row["status"] == "running" and not final else "cancelled"
            conn.execute(
                """
                UPDATE tasks
                SET cancel_requested = 1, status = ?, updated_at = ?,
                    finished_at = CASE WHEN ? = 'cancelled' THEN ? ELSE finished_at END
                WHERE task_id = ?
                """,
                (next_status, timestamp, next_status, timestamp, task_id),
            )
            if next_status == "cancelled":
                conn.execute(
                    "UPDATE task_claims SET status = 'cancelled' WHERE task_id = ? AND status = 'active'",
                    (task_id,),
                )
            self._insert_event(
                conn,
                task_id,
                event_type="task_cancel_requested",
                timestamp=timestamp,
                status=next_status,
                summary=f"Cancel requested by {requested_by}.",
                payload={"requested_by": requested_by},
            )
            updated = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return self._row_to_task(updated)

    def reclaim_expired(self, *, now: datetime | str | None = None) -> list[dict[str, Any]]:
        timestamp = _format_time(now)
        reclaimed: list[dict[str, Any]] = []
        with self._transaction() as conn:
            rows = conn.execute(
                """
                SELECT claims.*, tasks.status AS task_status
                FROM task_claims AS claims
                JOIN tasks ON tasks.task_id = claims.task_id
                WHERE claims.status = 'active'
                  AND claims.expires_at <= ?
                  AND tasks.status = 'running'
                ORDER BY claims.expires_at ASC, claims.claim_id ASC
                """,
                (timestamp,),
            ).fetchall()
            for row in rows:
                task_id = str(row["task_id"])
                conn.execute("UPDATE task_claims SET status = 'expired' WHERE claim_id = ?", (row["claim_id"],))
                conn.execute(
                    "UPDATE tasks SET status = 'recoverable', updated_at = ? WHERE task_id = ?",
                    (timestamp, task_id),
                )
                self._insert_event(
                    conn,
                    task_id,
                    event_type="task_reclaimed",
                    timestamp=timestamp,
                    status="recoverable",
                    summary=f"Expired claim from {row['worker_id']} was reclaimed.",
                    payload={"worker_id": row["worker_id"], "expired_at": row["expires_at"]},
                )
                updated = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                reclaimed.append(self._row_to_task(updated))
        return reclaimed

    def list_events(self, task_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_events
                WHERE task_id = ?
                ORDER BY event_id ASC
                LIMIT ?
                """,
                (task_id, max(1, int(limit))),
            ).fetchall()
            return [
                {
                    **dict(row),
                    "payload": _json_load(row["payload_json"]),
                    "error": _json_load(row["error_json"]),
                }
                for row in rows
            ]

    def list_artifacts(self, task_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_artifacts
                WHERE task_id = ?
                ORDER BY artifact_id ASC
                LIMIT ?
                """,
                (task_id, max(1, int(limit))),
            ).fetchall()
            return [{**dict(row), "metadata": _json_load(row["metadata_json"])} for row in rows]

    def list_retries(self, task_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_retries
                WHERE task_id = ?
                ORDER BY retry_id ASC
                LIMIT ?
                """,
                (task_id, max(1, int(limit))),
            ).fetchall()
            return [dict(row) for row in rows]


def get_task_queue(db_path: Path | str | None = None) -> TaskQueue:
    return TaskQueue(db_path or default_task_db_path())
