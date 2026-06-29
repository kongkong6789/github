#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_ORDER = {"ok": 0, "skipped": 0, "warn": 1, "fail": 2}
SENSITIVE_KEY_PATTERN = re.compile(r"(api[_-]?key|token|secret|password)", re.IGNORECASE)
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^,'\"\s]+", re.IGNORECASE),
    re.compile(r"(?i)(apikey=|scode=|access_token=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"tp-[A-Za-z0-9_-]{12,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]
REQUIRED_ENV_KEYS = ["OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"]
PYTHON_DEPS = ["duckdb", "langgraph", "openpyxl"]
OPTIONAL_PYTHON_DEPS = ["lightrag", "pandas", "pyarrow"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SENSITIVE_VALUE_PATTERNS:
        def replace(match: re.Match[str]) -> str:
            text = match.group(0)
            if "=" in text:
                return f"{text.split('=', 1)[0]}=***REDACTED***"
            if ":" in text and SENSITIVE_KEY_PATTERN.search(text.split(":", 1)[0]):
                return f"{text.split(':', 1)[0]}: ***REDACTED***"
            return "***REDACTED***"

        redacted = pattern.sub(replace, redacted)
    return redacted


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def check(
    check_id: str,
    label: str,
    status: str,
    summary: str,
    *,
    suggestion: str = "",
    files: list[str] | None = None,
    commands: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return redact(
        {
            "id": check_id,
            "label": label,
            "status": status,
            "summary": summary,
            "suggestion": suggestion,
            "files": files or [],
            "commands": commands or [],
            "metadata": metadata or {},
        },
    )


def read_json_file(path: Path) -> tuple[Any | None, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON at line {exc.lineno}: {exc.msg}"
    except OSError as exc:
        return None, str(exc)


def safe_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def lightrag_health_url(env: dict[str, str]) -> str:
    api_url = (env.get("LIGHTRAG_API_URL") or f"http://127.0.0.1:{env.get('LIGHTRAG_PORT', '9621')}").rstrip("/")
    return f"{api_url}/health"


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        value = raw_value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def resolve_data_dir(project_root: Path, env: dict[str, str]) -> Path:
    return Path(env.get("A2A_DATA_DIR") or project_root / "data").resolve()


def validate_env_file(env_path: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    file_values = parse_env_file(env_path)
    merged = {**file_values, **(env or {})}
    if not env_path.exists():
        return check(
            "env",
            ".env",
            "warn",
            ".env is missing; defaults may still work for local read-only checks.",
            suggestion="Copy .env.example to .env and fill only the keys you need.",
            files=[str(env_path), str(env_path.with_name(".env.example"))],
            commands=["cp .env.example .env"],
        )

    missing = [key for key in REQUIRED_ENV_KEYS if not merged.get(key)]
    placeholders = [
        key
        for key, value in merged.items()
        if SENSITIVE_KEY_PATTERN.search(key) and value.lower().startswith(("your_", "replace_me", "changeme"))
    ]
    sensitive_state = {
        key: ("set (***REDACTED***)" if merged.get(key) else "not set")
        for key in sorted(merged)
        if SENSITIVE_KEY_PATTERN.search(key)
    }
    if missing:
        return check(
            "env",
            ".env",
            "fail",
            f"Missing required env keys: {', '.join(missing)}.",
            suggestion="Set the missing keys in .env; secret values are only shown as set/not set.",
            files=[str(env_path)],
            commands=["cp .env.example .env"],
            metadata={"sensitive_keys": sensitive_state, "missing": missing},
        )
    if placeholders:
        return check(
            "env",
            ".env",
            "warn",
            f"Placeholder sensitive env values are still present: {', '.join(placeholders)}.",
            suggestion="Replace placeholder values before running real LLM or embedding calls.",
            files=[str(env_path)],
            metadata={"sensitive_keys": sensitive_state, "placeholder_keys": placeholders},
        )
    return check(
        "env",
        ".env",
        "ok",
        "Required env keys are present; sensitive values are redacted.",
        files=[str(env_path)],
        metadata={"sensitive_keys": sensitive_state},
    )


def check_repository_secret_hygiene(project_root: Path) -> dict[str, Any]:
    gitignore_path = project_root / ".gitignore"
    try:
        gitignore_lines = set(gitignore_path.read_text(encoding="utf-8").splitlines())
    except OSError:
        gitignore_lines = set()

    missing_patterns = [pattern for pattern in [".env", ".env.*", "!.env.example"] if pattern not in gitignore_lines]
    tracked_env = False
    tracked_skill_configs: list[str] = []
    git_error = ""
    if (project_root / ".git").exists() and shutil.which("git"):
        result = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=project_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        tracked_env = bool(result.stdout.strip())
        git_error = result.stderr.strip()
        config_result = subprocess.run(
            ["git", "ls-files", "skills/*/config.py"],
            cwd=project_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        tracked_skill_configs = [line.strip() for line in config_result.stdout.splitlines() if line.strip()]

    high_risk_patterns = [
        re.compile(r"6be140cc09f441978a1ff6727367dda2", re.IGNORECASE),
        re.compile(r"\b37811901\b"),
        re.compile(r"159\.75\.104\.61"),
        re.compile(r"65405d0ec432ee", re.IGNORECASE),
        re.compile(
            r"https://[^\s\"']*(?:apikey=|scode=)(?!secret-key|secret-code)[^&\s\"']{8,}",
            re.IGNORECASE,
        ),
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        re.compile(r"token-plan-cn\.xiaomimimo\.com", re.IGNORECASE),
    ]
    redaction_definition_files = {
        "doctor.py",
        "enterprise_audit_tools.py",
        "thread_repair_tools.py",
        "wecom_smartsheet_tools.py",
        "logs.ts",
        "agent-reach.ts",
        "route.ts",
    }
    scan_roots = [
        project_root / "README.md",
        project_root / "TODO.md",
        project_root / "docs",
        project_root / "tests",
        project_root / "skills",
        project_root / "src",
        project_root / "config",
        project_root / "agent-chat-ui" / "src",
        project_root / "scripts",
    ]
    sensitive_hits: list[str] = []
    for root in scan_roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*")) if root.exists() else []
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in {
                ".md",
                ".py",
                ".json",
                ".txt",
                ".example",
                ".ts",
                ".tsx",
            }:
                continue
            if path.name == "test_p7_engineering_guardrails.py":
                continue
            if path.name in redaction_definition_files:
                continue
            if path.name.startswith("test_") or path.name.endswith(".test.ts"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(pattern.search(text) for pattern in high_risk_patterns):
                sensitive_hits.append(str(path.relative_to(project_root)))

    problems = []
    if missing_patterns:
        problems.append(f".gitignore missing: {', '.join(missing_patterns)}")
    if tracked_env:
        problems.append("root .env is tracked by Git")
    if tracked_skill_configs:
        problems.append(f"local skill config.py tracked by Git: {', '.join(tracked_skill_configs[:4])}")
    if sensitive_hits:
        problems.append(f"high-risk literal(s): {', '.join(sensitive_hits[:8])}")
    if problems:
        return check(
            "repository_secret_hygiene",
            "Repository secret hygiene",
            "fail",
            "; ".join(problems),
            suggestion="Remove .env from Git, keep only placeholder examples, and rotate any exposed live credentials.",
            files=[str(gitignore_path), str(project_root / ".env"), *sensitive_hits[:8]],
            commands=["git rm --cached .env", "python -m unittest tests.test_p7_engineering_guardrails"],
            metadata={"git_error": git_error} if git_error else {},
        )
    return check(
        "repository_secret_hygiene",
        "Repository secret hygiene",
        "ok",
        ".env is ignored/untracked and no known high-risk literals were found in docs/tests/skills.",
        files=[str(gitignore_path), str(project_root / ".env.example")],
    )


def validate_connector_registry(path: Path) -> dict[str, Any]:
    payload, error = read_json_file(path)
    if error == "missing":
        return check(
            "connector_registry",
            "Connector registry",
            "warn",
            "Connector registry is missing.",
            suggestion="Run connector registration or preview sync once to create the registry.",
            files=[str(path)],
        )
    if error:
        return check(
            "connector_registry",
            "Connector registry",
            "fail",
            f"Connector registry is not valid JSON: {error}.",
            suggestion="Fix the JSON syntax or regenerate the connector registry.",
            files=[str(path)],
        )
    connectors = safe_record(safe_record(payload).get("connectors"))
    unsafe = [
        connector_id
        for connector_id, raw in connectors.items()
        if safe_record(raw).get("external_write_enabled") is True
    ]
    if unsafe:
        return check(
            "connector_registry",
            "Connector registry",
            "fail",
            f"external_write_enabled is true for: {', '.join(sorted(unsafe))}.",
            suggestion="Keep connector external writes disabled; use approval requests for write actions.",
            files=[str(path)],
        )
    return check(
        "connector_registry",
        "Connector registry",
        "ok",
        f"Connector registry is valid with {len(connectors)} connector(s); external writes are disabled.",
        files=[str(path)],
    )


def validate_source_registry(registry_path: Path, snapshot_manifest_path: Path) -> dict[str, Any]:
    payload, error = read_json_file(registry_path)
    if error == "missing":
        return check(
            "source_registry",
            "Source Registry",
            "warn",
            "Source registry is missing; P16 sources have not been registered yet.",
            suggestion="Register a local folder, manual upload, WeCom Wedrive, WeCom smartsheet, or ERP readonly source.",
            files=[str(registry_path), str(snapshot_manifest_path)],
            commands=["python -m src.a2a_ecommerce_demo.source_registry_tools list-sources"],
        )
    if error:
        return check(
            "source_registry",
            "Source Registry",
            "fail",
            f"Source registry is not valid JSON: {error}.",
            suggestion="Fix JSON syntax or regenerate the registry from source_registry_tools.",
            files=[str(registry_path)],
        )
    registry = safe_record(payload)
    sources = safe_record(registry.get("sources"))
    problems: list[str] = []
    source_ids = [str(source_id) for source_id in sources]
    if len(source_ids) != len(set(source_ids)):
        problems.append("duplicate source_id")
    for source_id, raw in sources.items():
        source = safe_record(raw)
        if not source.get("owner"):
            problems.append(f"{source_id}: missing owner")
        if not source.get("freshness_sla"):
            problems.append(f"{source_id}: missing freshness_sla")
        if source.get("status") == "failed":
            problems.append(f"{source_id}: failed status")
        for key in source.get("credential_env_keys") or []:
            if not isinstance(key, str) or not re.match(r"^[A-Z][A-Z0-9_]*$", key) or key.startswith(("sk-", "tp-")):
                problems.append(f"{source_id}: credential plaintext")
        uri = str(source.get("uri") or "")
        if re.search(r"(?i)(access_token|apikey|api_key|scode|token|secret|password)=", uri):
            problems.append(f"{source_id}: unsafe uri")
        if source.get("source_type") in {"local_file", "local_folder", "manual_upload"}:
            allowed_root = Path(str(source.get("allowed_root") or "")).expanduser()
            target = Path(uri).expanduser()
            try:
                allowed_resolved = allowed_root.resolve(strict=False)
                target_resolved = target.resolve(strict=False)
                if allowed_resolved not in [target_resolved, *target_resolved.parents]:
                    problems.append(f"{source_id}: path outside allowed_root")
            except OSError as exc:
                problems.append(f"{source_id}: invalid path {exc}")
    invalid_snapshot_lines = 0
    if snapshot_manifest_path.exists():
        for line in snapshot_manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                snapshot = json.loads(line)
            except json.JSONDecodeError:
                invalid_snapshot_lines += 1
                continue
            if not isinstance(snapshot, dict) or not snapshot.get("source_id") or not snapshot.get("snapshot_id"):
                invalid_snapshot_lines += 1
    if invalid_snapshot_lines:
        problems.append(f"invalid snapshot manifest lines: {invalid_snapshot_lines}")
    if problems:
        return check(
            "source_registry",
            "Source Registry",
            "fail",
            "; ".join(problems[:8]),
            suggestion="Fix source metadata, remove plaintext credentials, and keep local paths inside allowlisted roots.",
            files=[str(registry_path), str(snapshot_manifest_path)],
            commands=["python -m unittest tests.test_source_registry tests.test_source_snapshots tests.test_source_sync_workflow"],
            metadata={"source_count": len(sources), "problem_count": len(problems)},
        )
    return check(
        "source_registry",
        "Source Registry",
        "ok",
        f"Source registry is valid with {len(sources)} source(s).",
        files=[str(registry_path), str(snapshot_manifest_path)],
        metadata={"source_count": len(sources)},
    )


def validate_mcp_policy(path: Path) -> dict[str, Any]:
    payload, error = read_json_file(path)
    if error == "missing":
        return check(
            "mcp_policy",
            "MCP policy",
            "warn",
            "MCP policy file is missing.",
            suggestion="Open /governance once or create data/mcp/tool_policy.json from the default policy.",
            files=[str(path)],
        )
    if error:
        return check(
            "mcp_policy",
            "MCP policy",
            "fail",
            f"MCP policy is not valid JSON: {error}.",
            suggestion="Fix the JSON syntax before using governance checks.",
            files=[str(path)],
        )
    tools = safe_record(safe_record(payload).get("tools"))
    external_writes = [
        name for name, raw in tools.items() if safe_record(raw).get("external_write_enabled") is True
    ]
    missing_confirmation = [
        name
        for name, raw in tools.items()
        if safe_record(raw).get("read_only") is False and safe_record(raw).get("requires_human_confirmation") is not True
    ]
    problems = []
    if external_writes:
        problems.append(f"external_write_enabled true: {', '.join(sorted(external_writes))}")
    if missing_confirmation:
        problems.append(f"write tools without confirmation: {', '.join(sorted(missing_confirmation))}")
    if problems:
        return check(
            "mcp_policy",
            "MCP policy",
            "fail",
            "; ".join(problems),
            suggestion="Disable external writes and require human confirmation for non-read-only tools.",
            files=[str(path)],
        )
    return check(
        "mcp_policy",
        "MCP policy",
        "ok",
        f"MCP policy is valid with {len(tools)} tool(s); external writes are disabled.",
        files=[str(path)],
    )


def validate_reference_platforms(project_root: Path, env: dict[str, str]) -> dict[str, Any]:
    configured = env.get("A2A_REFERENCE_PLATFORMS_CONFIG", "").strip()
    registry_path = Path(configured).expanduser() if configured else project_root / "config" / "reference_platforms.json"
    payload, error = read_json_file(registry_path)
    if error == "missing":
        return check(
            "reference_platforms",
            "Reference platform registry",
            "fail",
            "Missing config/reference_platforms.json.",
            suggestion="Restore the P18 registry or set A2A_REFERENCE_PLATFORMS_CONFIG.",
            files=[str(registry_path)],
        )
    if error:
        return check(
            "reference_platforms",
            "Reference platform registry",
            "fail",
            f"Reference platform registry is not valid JSON: {error}.",
            files=[str(registry_path)],
        )
    platforms = payload.get("platforms") if isinstance(payload, dict) else None
    if not isinstance(platforms, dict) or len(platforms) < 6:
        return check(
            "reference_platforms",
            "Reference platform registry",
            "fail",
            "Reference platform registry must define six merged platforms.",
            files=[str(registry_path)],
        )
    expected = {"duckdb", "lightrag", "karpathy_llm_wiki", "mirofish", "ruoyi_ai", "maxkb"}
    missing = sorted(expected - set(platforms))
    if missing:
        return check(
            "reference_platforms",
            "Reference platform registry",
            "fail",
            f"Missing platform entries: {', '.join(missing)}.",
            files=[str(registry_path)],
        )
    sidecars = []
    for platform_id in ("ruoyi_ai", "maxkb", "mirofish"):
        prefix = str(platforms[platform_id].get("env_prefix") or platform_id.upper())
        url_env = str(platforms[platform_id].get("default_url_env") or f"{prefix}_API_URL")
        if env.get(url_env, "").strip():
            sidecars.append(platform_id)
    message = f"Registry covers {len(platforms)} platforms; optional sidecars configured: {', '.join(sidecars) or 'none'}."
    return check(
        "reference_platforms",
        "Reference platform registry",
        "ok",
        message,
        files=[str(registry_path)],
        metadata={"configured_sidecars": sidecars},
    )


def validate_skill_registry(registry_path: Path, template_dir: Path) -> dict[str, Any]:
    payload, error = read_json_file(registry_path)
    if error == "missing":
        return check(
            "skill_registry",
            "Skill registry",
            "warn",
            "Skill registry is missing.",
            suggestion="Import or create a project Skill from /governance.",
            files=[str(registry_path)],
        )
    if error:
        return check(
            "skill_registry",
            "Skill registry",
            "fail",
            f"Skill registry is not valid JSON: {error}.",
            suggestion="Fix the JSON syntax or regenerate the Skill registry from /governance.",
            files=[str(registry_path)],
        )
    skills = safe_record(safe_record(payload).get("skills"))
    missing_templates: list[str] = []
    for skill_id, raw in skills.items():
        record = safe_record(raw)
        normalized_id = str(record.get("skill_id") or skill_id)
        if record.get("status") == "active" and not (template_dir / f"{normalized_id}.json").exists():
            missing_templates.append(normalized_id)
    if missing_templates:
        return check(
            "skill_registry",
            "Skill registry",
            "fail",
            f"Active Skill missing template: {', '.join(sorted(missing_templates))}.",
            suggestion="Deactivate the Skill or regenerate its active agent template from /governance.",
            files=[str(registry_path), str(template_dir)],
            commands=["Open /governance and re-activate the Skill"],
        )
    return check(
        "skill_registry",
        "Skill registry",
        "ok",
        f"Skill registry is valid with {len(skills)} skill(s).",
        files=[str(registry_path), str(template_dir)],
    )


def validate_lightrag_settings(env: dict[str, str], data_dir: Path) -> dict[str, Any]:
    api_url = env.get("LIGHTRAG_API_URL") or f"http://127.0.0.1:{env.get('LIGHTRAG_PORT', '9621')}"
    working_dir = Path(env.get("WORKING_DIR") or data_dir / "lightrag_official")
    doc_status = working_dir / "kv_store_doc_status.json"
    status = "ok" if api_url and (doc_status.exists() or working_dir.exists()) else "warn"
    return check(
        "lightrag_settings",
        "LightRAG settings",
        status,
        f"LightRAG API is configured as {api_url}; working dir {'exists' if working_dir.exists() else 'is missing'}.",
        suggestion="" if status == "ok" else "Set LIGHTRAG_API_URL/LIGHTRAG_PORT and run a LightRAG sync once.",
        files=[str(doc_status)],
    )


def check_python_runtime(project_root: Path) -> dict[str, Any]:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    venv_active = sys.prefix != sys.base_prefix
    local_venv = (project_root / ".venv").exists()
    if sys.version_info < (3, 11):
        return check(
            "python_runtime",
            "Python runtime",
            "fail",
            f"Python {version} is too old.",
            suggestion="Use Python 3.12 and recreate the local virtual environment.",
            commands=["python3.12 -m venv .venv", "./scripts/verify_python.sh"],
        )
    status = "ok" if venv_active or local_venv else "warn"
    return check(
        "python_runtime",
        "Python runtime",
        status,
        f"Python {version}; virtualenv {'active' if venv_active else 'detected' if local_venv else 'not detected'}.",
        suggestion="" if status == "ok" else "Create .venv and install the project dependencies.",
        commands=[] if status == "ok" else ["python3 -m venv .venv", "./scripts/verify_python.sh"],
    )


def check_python_deps() -> dict[str, Any]:
    missing = [name for name in PYTHON_DEPS if importlib.util.find_spec(name) is None]
    optional_missing = [name for name in OPTIONAL_PYTHON_DEPS if importlib.util.find_spec(name) is None]
    if missing:
        return check(
            "python_deps",
            "Python dependencies",
            "fail",
            f"Missing required imports: {', '.join(missing)}.",
            suggestion="Install project dependencies in .venv.",
            commands=["pip install -e .", "./scripts/verify_python.sh"],
            metadata={"optional_missing": optional_missing},
        )
    return check(
        "python_deps",
        "Python dependencies",
        "ok",
        "Required Python dependencies are importable."
        + (f" Optional missing: {', '.join(optional_missing)}." if optional_missing else ""),
        metadata={"optional_missing": optional_missing},
    )


def check_node_frontend(project_root: Path) -> dict[str, Any]:
    ui_dir = project_root / "agent-chat-ui"
    missing_required_tools = [name for name in ["node", "npm"] if shutil.which(name) is None]
    pnpm_available = shutil.which("pnpm") is not None
    node_modules = ui_dir / "node_modules"
    if missing_required_tools:
        return check(
            "node_frontend",
            "Node/frontend",
            "fail",
            f"Missing frontend command(s): {', '.join(missing_required_tools)}.",
            suggestion="Install Node.js and pnpm, then install frontend dependencies.",
            commands=["corepack enable", "cd agent-chat-ui && pnpm install"],
        )
    if ui_dir.exists() and not node_modules.exists():
        return check(
            "node_frontend",
            "Node/frontend",
            "fail",
            "agent-chat-ui exists but node_modules is missing.",
            suggestion="Install frontend dependencies before building or opening the UI.",
            files=[str(ui_dir / "package.json")],
            commands=["cd agent-chat-ui && pnpm install"],
        )
    if not pnpm_available:
        return check(
            "node_frontend",
            "Node/frontend",
            "ok",
            "Node/npm are available and frontend dependencies are installed; pnpm is not on PATH.",
            files=[str(ui_dir / "package.json")],
            metadata={"pnpm_available": False},
        )
    return check(
        "node_frontend",
        "Node/frontend",
        "ok",
        "Node/npm/pnpm are available and frontend dependencies are installed.",
        files=[str(ui_dir / "package.json")],
        metadata={"pnpm_available": True},
    )


def check_http_port(check_id: str, label: str, url: str, command: str, skip: bool) -> dict[str, Any]:
    if skip:
        return check(
            check_id,
            label,
            "skipped",
            f"Skipped port check for {url}.",
            suggestion="Unset A2A_DOCTOR_SKIP_PORT_CHECKS to check local services.",
        )
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return check(check_id, label, "ok", f"{url} responded with HTTP {response.status}.")
    except Exception as exc:
        return check(
            check_id,
            label,
            "warn",
            f"{url} is not reachable: {exc}.",
            suggestion="Start the service if you need it for the current workflow.",
            commands=[command],
        )


def check_duckdb(data_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    duckdb_path = Path(env.get("A2A_DUCKDB_PATH") or data_dir / "warehouse" / "a2a.duckdb")
    if not duckdb_path.exists():
        return check(
            "duckdb",
            "DuckDB",
            "warn",
            "DuckDB file is missing.",
            suggestion="Run the data ingestion pipeline to create the local warehouse.",
            files=[str(duckdb_path)],
        )
    if importlib.util.find_spec("duckdb") is None:
        return check(
            "duckdb",
            "DuckDB",
            "skipped",
            "DuckDB file exists, but the duckdb Python package is not importable.",
            suggestion="Install Python dependencies, then rerun doctor.",
            files=[str(duckdb_path)],
            commands=["./scripts/verify_python.sh"],
        )
    try:
        import duckdb  # type: ignore[import-not-found]

        with duckdb.connect(str(duckdb_path), read_only=True) as connection:
            tables = connection.execute("show all tables").fetchall()
    except Exception as exc:
        return check(
            "duckdb",
            "DuckDB",
            "fail",
            f"DuckDB file exists but cannot be opened: {exc}.",
            suggestion="Regenerate or repair the DuckDB warehouse.",
            files=[str(duckdb_path)],
            commands=["./scripts/verify_python.sh"],
        )
    mart_like = [row for row in tables if "mart" in " ".join(map(str, row)).lower() or "__" in " ".join(map(str, row))]
    status = "ok" if mart_like else "warn"
    return check(
        "duckdb",
        "DuckDB",
        status,
        f"DuckDB opened successfully with {len(tables)} table/view row(s); mart-like entries: {len(mart_like)}.",
        suggestion="" if status == "ok" else "Register datasets into the fact layer so mart views are available.",
        files=[str(duckdb_path)],
    )


def check_dataset_registry(path: Path) -> dict[str, Any]:
    payload, error = read_json_file(path)
    if error == "missing":
        return check(
            "dataset_registry",
            "Dataset registry",
            "warn",
            "Dataset registry is missing.",
            suggestion="Run dataset registration after cleaning raw files.",
            files=[str(path)],
        )
    if error:
        return check(
            "dataset_registry",
            "Dataset registry",
            "fail",
            f"Dataset registry is not valid JSON: {error}.",
            suggestion="Fix or regenerate data/warehouse/dataset_registry.json.",
            files=[str(path)],
        )
    datasets = safe_record(safe_record(payload).get("datasets"))
    return check(
        "dataset_registry",
        "Dataset registry",
        "ok",
        f"Dataset registry is valid with {len(datasets)} dataset(s).",
        files=[str(path)],
    )


def check_task_json(tasks_dir: Path) -> dict[str, Any]:
    if not tasks_dir.exists():
        return check("tasks_json", "Task JSON", "skipped", "data/tasks does not exist.", files=[str(tasks_dir)])
    invalid: list[str] = []
    count = 0
    for path in sorted(tasks_dir.glob("*.json")):
        count += 1
        _, error = read_json_file(path)
        if error:
            invalid.append(path.name)
    if invalid:
        return check(
            "tasks_json",
            "Task JSON",
            "fail",
            f"Invalid task JSON file(s): {', '.join(invalid[:10])}.",
            suggestion="Fix malformed task files or move them out of data/tasks.",
            files=[str(tasks_dir)],
        )
    return check("tasks_json", "Task JSON", "ok", f"{count} task JSON file(s) are valid.", files=[str(tasks_dir)])


def check_audit_jsonl(path: Path, limit: int) -> dict[str, Any]:
    if not path.exists():
        return check("audit_jsonl", "Audit events", "warn", "Audit event log is missing.", files=[str(path)])
    invalid = 0
    total = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError as exc:
        return check(
            "audit_jsonl",
            "Audit events",
            "fail",
            f"Audit log cannot be read: {exc}.",
            suggestion="Check file permissions and recreate data/audit if needed.",
            files=[str(path)],
        )
    for line in lines:
        if not line.strip():
            continue
        total += 1
        try:
            json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
    if invalid:
        return check(
            "audit_jsonl",
            "Audit events",
            "warn",
            f"{invalid}/{total} recent audit line(s) are invalid JSON.",
            suggestion="Keep future audit writes JSONL-compatible; old bad lines can remain for forensics.",
            files=[str(path)],
        )
    return check("audit_jsonl", "Audit events", "ok", f"{total} recent audit event line(s) are valid.", files=[str(path)])


def check_thread_archive(data_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    candidates = [
        Path(env.get("A2A_THREAD_ARCHIVE_DIR") or data_dir / "thread_archive"),
        data_dir / "local_threads",
    ]
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return check("thread_archive", "Thread archive", "skipped", "No old thread archive directory found.")
    orphan_count = 0
    missing_count = 0
    mismatched_count = 0
    duplicate_count = 0
    scanned = 0
    for directory in existing:
        for path in directory.rglob("*.json"):
            scanned += 1
            payload, error = read_json_file(path)
            if error:
                continue
            if isinstance(payload, list):
                messages = payload
            else:
                record = safe_record(payload)
                values = safe_record(record.get("values"))
                messages = record.get("messages") if isinstance(record.get("messages"), list) else values.get("messages")
            if not isinstance(messages, list):
                continue
            index = 0
            while index < len(messages):
                message = messages[index]
                record = safe_record(message)
                role = str(record.get("role") or record.get("type") or "")
                if role in {"assistant", "ai"}:
                    tool_calls = record.get("tool_calls") if isinstance(record.get("tool_calls"), list) else []
                    expected_ids = [str(call.get("id") or "") for call in tool_calls if isinstance(call, dict)]
                    expected_ids = [tool_call_id for tool_call_id in expected_ids if tool_call_id]
                    if not expected_ids:
                        index += 1
                        continue
                    seen_ids: set[str] = set()
                    lookahead = index + 1
                    while lookahead < len(messages):
                        tool_record = safe_record(messages[lookahead])
                        tool_role = str(tool_record.get("role") or tool_record.get("type") or "")
                        if tool_role != "tool":
                            break
                        tool_call_id = str(tool_record.get("tool_call_id") or "")
                        if tool_call_id not in expected_ids:
                            mismatched_count += 1
                        elif tool_call_id in seen_ids:
                            duplicate_count += 1
                        else:
                            seen_ids.add(tool_call_id)
                        lookahead += 1
                    missing_count += len([tool_call_id for tool_call_id in expected_ids if tool_call_id not in seen_ids])
                    index = lookahead
                    continue
                if role == "tool":
                    orphan_count += 1
                index += 1
    if orphan_count or missing_count or mismatched_count or duplicate_count:
        summary_parts = []
        if orphan_count:
            summary_parts.append(f"orphan={orphan_count}")
        if missing_count:
            summary_parts.append(f"missing={missing_count}")
        if mismatched_count:
            summary_parts.append(f"mismatched={mismatched_count}")
        if duplicate_count:
            summary_parts.append(f"duplicate={duplicate_count}")
        return check(
            "thread_archive",
            "Thread archive",
            "warn",
            f"Found tool protocol issue(s) across {scanned} archived thread file(s): {', '.join(summary_parts)}.",
            suggestion="Run the local archive repair flow before replaying old threads.",
            files=[str(path) for path in existing],
            metadata={
                "orphan_tool_messages": orphan_count,
                "missing_tool_responses": missing_count,
                "mismatched_tool_responses": mismatched_count,
                "duplicate_tool_responses": duplicate_count,
            },
        )
    return check("thread_archive", "Thread archive", "ok", f"Scanned {scanned} archived thread file(s); no orphan tool messages found.")


def check_desktop_harness_availability(platform_name: str | None = None) -> dict[str, Any]:
    platform = (platform_name or sys.platform).lower()
    is_windows = platform.startswith("win")
    harnesses = {
        "wps_office": "available_if_installed" if is_windows else "unavailable",
        "photoshop": "available_if_installed" if is_windows else "unavailable",
        "illustrator": "available_if_installed" if is_windows else "unavailable",
    }
    if not is_windows:
        return check(
            "desktop_harness_availability",
            "Desktop harness availability",
            "ok",
            "WPS/Photoshop/Illustrator harnesses require a Windows worker and are marked unavailable on this platform.",
            suggestion="Use report quality templates locally; run write/export harnesses only inside an approved Windows worker.",
            metadata={"platform": platform, "harnesses": harnesses},
        )
    return check(
        "desktop_harness_availability",
        "Desktop harness availability",
        "ok",
        "Windows worker platform detected; desktop harnesses still require explicit installation and approval before write/export use.",
        suggestion="Keep ordinary analysis Agents away from WPS/Photoshop/Illustrator write tools; route them through approval executor only.",
        metadata={"platform": platform, "harnesses": harnesses},
    )


def check_script_pairing(project_root: Path) -> dict[str, Any]:
    scripts_dir = project_root / "scripts"
    sh_stems = {path.stem for path in scripts_dir.glob("*.sh")}
    ps1_stems = {path.stem for path in scripts_dir.glob("*.ps1")}
    missing_ps1 = sorted(sh_stems - ps1_stems)
    missing_sh = sorted(ps1_stems - sh_stems)
    if missing_ps1 or missing_sh:
        return check(
            "script_pairing",
            "P7 script pairing",
            "fail",
            f"Missing script pairs: ps1={missing_ps1 or []}; sh={missing_sh or []}.",
            suggestion="Every operational script needs both .sh and .ps1 wrappers.",
            files=[str(scripts_dir)],
            commands=["python -m unittest tests.test_p7_engineering_guardrails"],
        )
    return check("script_pairing", "P7 script pairing", "ok", f"{len(sh_stems)} script pair(s) are present.", files=[str(scripts_dir)])


def aggregate_status(checks: list[dict[str, Any]]) -> str:
    if any(item["status"] == "fail" for item in checks):
        return "fail"
    if any(item["status"] == "warn" for item in checks):
        return "warn"
    return "ok"


def run_doctor(
    project_root: str | Path | None = None,
    env: dict[str, str] | None = None,
    recent_audit_lines: int = 200,
) -> dict[str, Any]:
    root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    merged_env = {**os.environ, **(env or {})}
    data_dir = resolve_data_dir(root, merged_env)
    warehouse_dir = Path(merged_env.get("A2A_WAREHOUSE_DIR") or data_dir / "warehouse")
    tasks_dir = Path(merged_env.get("A2A_TASK_DIR") or data_dir / "tasks")
    mcp_policy_path = Path(merged_env.get("A2A_MCP_POLICY_PATH") or data_dir / "mcp" / "tool_policy.json")
    skill_registry_dir = Path(merged_env.get("A2A_SKILL_REGISTRY_DIR") or data_dir / "skill_registry")
    template_dir = Path(merged_env.get("A2A_AGENT_TEMPLATE_DIR") or data_dir / "agent_templates")
    source_registry_dir = Path(merged_env.get("A2A_SOURCE_REGISTRY_DIR") or data_dir / "source_registry")
    source_registry_path = Path(merged_env.get("A2A_SOURCE_REGISTRY_PATH") or source_registry_dir / "sources.json")
    source_snapshot_manifest = Path(
        merged_env.get("A2A_SOURCE_SNAPSHOT_MANIFEST") or source_registry_dir / "snapshots.jsonl"
    )
    skip_ports = truthy(merged_env.get("A2A_DOCTOR_SKIP_PORT_CHECKS"))

    checks = [
        check_python_runtime(root),
        check_python_deps(),
        check_node_frontend(root),
        validate_env_file(root / ".env", merged_env),
        check_repository_secret_hygiene(root),
        check_http_port(
            "backend_port",
            "LangGraph backend port",
            f"http://127.0.0.1:{merged_env.get('A2A_BACKEND_PORT', '2024')}/ok",
            "./scripts/start_backend.sh",
            skip_ports,
        ),
        check_http_port(
            "frontend_port",
            "Frontend port",
            f"http://127.0.0.1:{merged_env.get('A2A_FRONTEND_PORT', '3000')}",
            "./scripts/start_frontend.sh",
            skip_ports,
        ),
        check_http_port(
            "lightrag_port",
            "LightRAG port",
            lightrag_health_url(merged_env),
            "./scripts/start_lightrag_server.sh",
            skip_ports,
        ),
        check_duckdb(data_dir, merged_env),
        check_dataset_registry(warehouse_dir / "dataset_registry.json"),
        check_task_json(tasks_dir),
        check_audit_jsonl(Path(merged_env.get("A2A_AUDIT_LOG") or data_dir / "audit" / "events.jsonl"), recent_audit_lines),
        validate_mcp_policy(mcp_policy_path),
        validate_connector_registry(Path(merged_env.get("A2A_CONNECTOR_REGISTRY") or warehouse_dir / "connector_registry.json")),
        validate_source_registry(source_registry_path, source_snapshot_manifest),
        validate_reference_platforms(root, merged_env),
        validate_skill_registry(skill_registry_dir / "registry.json", template_dir),
        validate_lightrag_settings(merged_env, data_dir),
        check_thread_archive(data_dir, merged_env),
        check_desktop_harness_availability(),
        check_script_pairing(root),
    ]
    counts = {status: sum(1 for item in checks if item["status"] == status) for status in ["ok", "warn", "fail", "skipped"]}
    return {
        "schema": "a2a_doctor_report_v1",
        "checked_at": now_iso(),
        "project_root": str(root),
        "data_dir": str(data_dir),
        "status": aggregate_status(checks),
        "counts": counts,
        "checks": checks,
    }


def format_human(report: dict[str, Any]) -> str:
    lines = [
        f"A2A Doctor - {report.get('status', 'unknown').upper()}",
        f"checked_at: {report.get('checked_at', '')}",
        f"project_root: {report.get('project_root', '')}",
        "",
    ]
    for item in report.get("checks", []):
        lines.append(f"[{item.get('status', 'unknown')}] {item.get('label', item.get('id'))}: {item.get('summary', '')}")
        if item.get("suggestion"):
            lines.append(f"  suggestion: {item['suggestion']}")
        if item.get("files"):
            lines.append(f"  files: {', '.join(item['files'])}")
        if item.get("commands"):
            lines.append(f"  commands: {' && '.join(item['commands'])}")
        metadata = item.get("metadata") or {}
        if metadata:
            lines.append(f"  metadata: {json.dumps(redact(metadata), ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local A2A Workbench diagnostics.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--recent-audit-lines", type=int, default=200)
    args = parser.parse_args(argv)

    report = run_doctor(recent_audit_lines=args.recent_audit_lines)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_human(report))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
