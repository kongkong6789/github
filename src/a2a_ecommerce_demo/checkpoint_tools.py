from __future__ import annotations

import hashlib
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.a2a_ecommerce_demo.state_io import atomic_write_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
DEFAULT_CHECKPOINT_DIR = Path(os.getenv("A2A_LANGGRAPH_API_DIR", PROJECT_ROOT / ".langgraph_api")).resolve()
DEFAULT_MIGRATION_ROOT = Path(
    os.getenv("A2A_CHECKPOINT_MIGRATION_DIR", DATA_DIR / "thread_checkpoint_migrations")
).resolve()
MIGRATION_SCHEMA = "a2a_langgraph_checkpoint_migration_v1"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkpoint_files(checkpoint_dir: Path) -> list[Path]:
    if not checkpoint_dir.exists():
        return []
    files = list(checkpoint_dir.glob("*.pckl")) + list(checkpoint_dir.glob("*.pckl.tmp"))
    return sorted({path.resolve() for path in files})


def prepare_langgraph_checkpoint_dir(
    checkpoint_dir: Path | str | None = None,
    *,
    stale_tmp_seconds: int = 3600,
) -> dict[str, Any]:
    """Create and preflight LangGraph's local checkpoint directory."""
    directory = Path(checkpoint_dir or DEFAULT_CHECKPOINT_DIR).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    removed_temp_files: list[str] = []
    warnings: list[str] = []
    now = time.time()

    for temp_file in directory.glob("*.pckl.tmp"):
        try:
            age_seconds = now - temp_file.stat().st_mtime
            if stale_tmp_seconds <= 0 or age_seconds >= stale_tmp_seconds:
                temp_file.unlink()
                removed_temp_files.append(str(temp_file))
        except OSError as exc:
            warnings.append(f"failed_to_remove_temp_file:{temp_file}:{exc}")

    probe = directory / f".write-probe-{os.getpid()}.tmp"
    writable = False
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable = True
    except OSError as exc:
        warnings.append(f"checkpoint_dir_not_writable:{exc}")

    return {
        "status": "success" if writable else "warning",
        "checkpoint_dir": str(directory),
        "writable": writable,
        "removed_temp_files": removed_temp_files,
        "warnings": warnings,
    }


def _manifest_entry(source: Path, archive_dir: Path | None = None) -> dict[str, Any]:
    stat = source.stat()
    archived_to = ""
    if archive_dir is not None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        destination = archive_dir / source.name
        shutil.copy2(source, destination)
        archived_to = str(destination)
    return {
        "name": source.name,
        "source_path": str(source),
        "archived_to": archived_to,
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "sha256": _sha256(source),
        "format": "raw_langgraph_pickle",
        "migration_action": "archived_with_structured_manifest",
    }


def migrate_checkpoint_pickles(
    *,
    checkpoint_dir: Path | str | None = None,
    migration_root: Path | str | None = None,
    dry_run: bool = True,
    confirm: bool = False,
) -> dict[str, Any]:
    """Archive LangGraph pickle checkpoints with a structured JSON manifest."""
    if not dry_run and not confirm:
        return {
            "status": "confirmation_required",
            "message": "Set confirm=true to archive checkpoint pickles and write a migration manifest.",
        }

    source_dir = Path(checkpoint_dir or DEFAULT_CHECKPOINT_DIR).resolve()
    target_root = Path(migration_root or DEFAULT_MIGRATION_ROOT).resolve()
    files = _checkpoint_files(source_dir)

    if dry_run:
        entries = [_manifest_entry(path) for path in files]
        return {
            "status": "dry_run",
            "source_dir": str(source_dir),
            "checkpoint_count": len(entries),
            "files": entries,
            "manifest_path": "",
        }

    migration_dir = target_root / _now_stamp()
    raw_archive_dir = migration_dir / "raw_pickles"
    entries = [_manifest_entry(path, raw_archive_dir) for path in files]
    manifest = {
        "schema": MIGRATION_SCHEMA,
        "generated_at": datetime.now().isoformat(),
        "source_dir": str(source_dir),
        "checkpoint_count": len(entries),
        "files": entries,
        "notes": [
            "Pickle internals are not mutated because they are runtime-specific.",
            "This archive is the migration handoff format; repaired JSON thread archives remain the editable source of truth.",
        ],
    }
    manifest_path = migration_dir / "manifest.json"
    atomic_write_json(manifest_path, manifest)
    return {
        "status": "success",
        "source_dir": str(source_dir),
        "checkpoint_count": len(entries),
        "migration_dir": str(migration_dir),
        "manifest_path": str(manifest_path),
        "files": entries,
    }
