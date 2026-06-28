from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def _pid_is_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _try_recover_stale_lock(lock_path: Path) -> bool:
    """Attempt to remove a stale lock file left by a dead process. Returns True if removed."""
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
        owner_pid = int(raw)
    except (OSError, ValueError):
        return False
    if _pid_is_alive(owner_pid):
        return False
    try:
        lock_path.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


@contextmanager
def file_lock(path: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("utf-8"))
        except FileExistsError:
            if _try_recover_stale_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    with file_lock(path):
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    with file_lock(path):
        return json.loads(path.read_text(encoding="utf-8"))
