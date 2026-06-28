"""
Official JackYun CLI runtime wrapper.

Packaged CLI zips live in tools/jkyuncli. At runtime the matching archive is
extracted into data/runtime/jkyuncli so the release zip stays portable.
"""
from __future__ import annotations

import json
import hashlib
import os
import platform
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import config
from helpers.local_store import DATA_DIR


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_ARCHIVE_DIR = PROJECT_ROOT / "tools" / "jkyuncli"


class JackyunCLIUnavailable(Exception):
    pass


def _platform_archive_name() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "jky-cli-windows-amd64.zip", "jky-cli.exe"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "jky-cli-darwin-arm64.zip", "jky-cli"
    if system == "darwin":
        return "jky-cli-darwin-amd64.zip", "jky-cli"
    if system == "linux":
        return "jky-cli-linux-amd64.zip", "jky-cli"
    raise JackyunCLIUnavailable(f"unsupported platform: {system}/{machine}")


def ensure_cli_executable() -> Path:
    archive_name, exe_name = _platform_archive_name()
    archive_path = CLI_ARCHIVE_DIR / archive_name
    if not archive_path.exists():
        raise JackyunCLIUnavailable(f"packaged CLI archive not found: {archive_path}")

    runtime_dir = DATA_DIR / "runtime" / "jkyuncli" / archive_name.replace(".zip", "")
    exe_path = runtime_dir / exe_name
    if exe_path.exists():
        return exe_path

    runtime_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as zf:
        zf.extractall(runtime_dir)

    if not exe_path.exists():
        matches = list(runtime_dir.rglob(exe_name))
        if matches:
            shutil.copy2(matches[0], exe_path)
    if not exe_path.exists():
        archive_stem = archive_name.replace(".zip", "")
        matches = [
            path for path in runtime_dir.rglob("*")
            if path.is_file() and path.name in {archive_stem, f"{archive_stem}.exe"}
        ]
        if matches:
            exe_path = matches[0]
    if not exe_path.exists():
        matches = [
            path for path in runtime_dir.rglob("*")
            if path.is_file() and path.name.startswith("jky-cli") and "README" not in path.name
        ]
        if matches:
            exe_path = matches[0]
    if not exe_path.exists():
        raise JackyunCLIUnavailable(f"CLI executable not found after extracting {archive_name}")

    if platform.system().lower() != "windows":
        exe_path.chmod(exe_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return exe_path


def _prepare_cli_env() -> dict[str, str]:
    env = os.environ.copy()
    runtime_home = DATA_DIR / "runtime" / "jkyuncli" / "home"
    runtime_home.mkdir(parents=True, exist_ok=True)
    env.setdefault("HOME", str(runtime_home))
    env.setdefault("XDG_CONFIG_HOME", str(runtime_home / ".config"))
    env.setdefault("app_key", config.JACKYUN_APP_KEY)
    env.setdefault("app_secret", config.JACKYUN_APP_SECRET)
    env.setdefault("appkey", config.JACKYUN_APP_KEY)
    env.setdefault("appsecret", config.JACKYUN_APP_SECRET)
    env.setdefault("JACKYUN_APP_KEY", config.JACKYUN_APP_KEY)
    env.setdefault("JACKYUN_APP_SECRET", config.JACKYUN_APP_SECRET)
    return env


def _ensure_cli_configured(exe_path: Path, env: dict[str, str]):
    marker_dir = DATA_DIR / "runtime" / "jkyuncli"
    marker_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{config.JACKYUN_APP_KEY}:{config.JACKYUN_APP_SECRET}".encode("utf-8")).hexdigest()
    marker_path = marker_dir / ".configured"
    if marker_path.exists() and marker_path.read_text(encoding="utf-8").strip() == digest:
        return

    completed = subprocess.run(
        [str(exe_path), "configure"],
        input=f"{config.JACKYUN_APP_KEY}\n{config.JACKYUN_APP_SECRET}\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=config.JACKYUN_CLI_TIMEOUT,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise JackyunCLIUnavailable(f"jky-cli configure failed: {detail}")
    marker_path.write_text(digest, encoding="utf-8")


def call_cli(method: str, bizcontent: dict[str, Any]) -> dict[str, Any]:
    exe_path = ensure_cli_executable()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fp:
        json.dump(bizcontent or {}, fp, ensure_ascii=False)
        payload_path = fp.name

    env = _prepare_cli_env()
    _ensure_cli_configured(exe_path, env)
    try:
        completed = subprocess.run(
            [str(exe_path), "api", "call", "--method", method, "--file", payload_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=config.JACKYUN_CLI_TIMEOUT,
            env=env,
            check=False,
        )
    finally:
        Path(payload_path).unlink(missing_ok=True)

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise JackyunCLIUnavailable(f"jky-cli failed: {detail}")
    return _parse_cli_stdout(completed.stdout)


def _parse_cli_stdout(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        raise JackyunCLIUnavailable("jky-cli returned empty output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise JackyunCLIUnavailable(f"cannot parse jky-cli output: {text[:300]}")
