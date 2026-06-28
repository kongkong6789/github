from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "config" / "reference_platforms.json"
REGISTRY_SCHEMA = "a2a_reference_platform_registry_v1"


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _load_env() -> None:
    env_path = Path(os.getenv("A2A_ENV_PATH", PROJECT_ROOT / ".env")).expanduser()
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


def _registry_path() -> Path:
    configured = os.getenv("A2A_REFERENCE_PLATFORMS_CONFIG", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_REGISTRY_PATH


def _default_registry() -> dict[str, Any]:
    return {"schema": REGISTRY_SCHEMA, "platforms": {}}


def load_reference_platform_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return _default_registry()
    registry = json.loads(path.read_text(encoding="utf-8"))
    registry.setdefault("schema", REGISTRY_SCHEMA)
    registry.setdefault("platforms", {})
    registry["registry_path"] = str(path)
    return registry


def _platform_env(platform: dict[str, Any]) -> dict[str, str]:
    _load_env()
    prefix = str(platform.get("env_prefix") or "").strip()
    url_env = str(platform.get("default_url_env") or f"{prefix}_API_URL").strip()
    key_env = f"{prefix}_API_KEY"
    return {
        "url_env": url_env,
        "key_env": key_env,
        "url": os.getenv(url_env, "").strip(),
        "api_key": os.getenv(key_env, "").strip(),
    }


def _platform_record(platform_id: str, platform: dict[str, Any]) -> dict[str, Any]:
    env = _platform_env(platform)
    mode = str(platform.get("integration_mode") or "")
    configured = mode in {"embedded", "embedded_sidecar"} or bool(env["url"])
    return {
        "platform_id": platform_id,
        "display_name": platform.get("display_name", platform_id),
        "source_repo": platform.get("source_repo", ""),
        "source_url": platform.get("source_url", ""),
        "integration_mode": mode,
        "role": platform.get("role", ""),
        "local_module": platform.get("local_module", ""),
        "primary_tools": list(platform.get("primary_tools") or []),
        "local_fallback_tools": list(platform.get("local_fallback_tools") or []),
        "configured": configured,
        "url_env": env["url_env"],
        "url_set": bool(env["url"]),
        "notes": platform.get("notes", ""),
    }


def _probe_sidecar(platform_id: str, platform: dict[str, Any]) -> dict[str, Any]:
    env = _platform_env(platform)
    base_url = env["url"].rstrip("/")
    if not base_url:
        return {
            "platform_id": platform_id,
            "status": "not_configured",
            "reachable": False,
            "warnings": [f"Set {env['url_env']} to enable this sidecar."],
        }

    health_path = str(platform.get("health_path") or "/").strip() or "/"
    url = urljoin(f"{base_url}/", health_path.lstrip("/"))
    headers: dict[str, str] = {}
    if env["api_key"]:
        headers["Authorization"] = f"Bearer {env['api_key']}"

    try:
        response = requests.get(url, headers=headers, timeout=8)
        reachable = response.status_code < 500
        status = "ready" if response.status_code < 400 else "degraded"
        return {
            "platform_id": platform_id,
            "status": status,
            "reachable": reachable,
            "http_status": response.status_code,
            "health_url": url,
            "warnings": [] if response.status_code < 400 else [f"Health check returned HTTP {response.status_code}."],
        }
    except requests.RequestException as exc:
        return {
            "platform_id": platform_id,
            "status": "unavailable",
            "reachable": False,
            "health_url": url,
            "warnings": [str(exc)],
        }


def _embedded_health(platform_id: str, platform: dict[str, Any]) -> dict[str, Any]:
    if platform_id == "duckdb":
        try:
            from src.a2a_ecommerce_demo.fact_layer_tools import duckdb_installed

            ready = duckdb_installed()
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "platform_id": platform_id,
                "status": "unavailable",
                "reachable": False,
                "warnings": [str(exc)],
            }
        return {
            "platform_id": platform_id,
            "status": "ready" if ready else "needs_install",
            "reachable": ready,
            "warnings": [] if ready else ["Install duckdb via requirements.txt."],
        }

    if platform_id == "karpathy_llm_wiki":
        wiki_dir = Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).expanduser()
        index_path = wiki_dir / "index.md"
        schema_path = wiki_dir / "AGENTS.md"
        missing = []
        if not wiki_dir.exists():
            missing.append("wiki directory is missing")
        if not index_path.exists():
            missing.append("wiki/index.md is missing")
        if not schema_path.exists():
            missing.append("wiki/AGENTS.md is missing")
        ready = not missing
        return {
            "platform_id": platform_id,
            "status": "ready" if ready else "needs_scaffold",
            "reachable": ready,
            "warnings": missing,
        }

    if platform_id == "lightrag":
        _load_env()
        api_url = (os.getenv("LIGHTRAG_API_URL") or f"http://127.0.0.1:{os.getenv('LIGHTRAG_PORT', '9621')}").rstrip("/")
        url = f"{api_url}/health"
        try:
            response = requests.get(url, timeout=8)
            ready = response.status_code < 400
            status = "ready" if ready else "degraded"
            return {
                "platform_id": platform_id,
                "status": status,
                "reachable": ready,
                "http_status": response.status_code,
                "health_url": url,
                "warnings": [] if ready else [f"LightRAG health returned HTTP {response.status_code}."],
            }
        except requests.RequestException as exc:
            return {
                "platform_id": platform_id,
                "status": "fallback_local",
                "reachable": False,
                "health_url": url,
                "warnings": [str(exc), "Local lightrag index fallback remains available."],
            }

    return {
        "platform_id": platform_id,
        "status": "unknown",
        "reachable": False,
        "warnings": ["No embedded health probe implemented."],
    }


def list_reference_platforms() -> str:
    """List the six merged reference platforms and how each one is integrated locally."""
    registry = load_reference_platform_registry()
    platforms = [
        _platform_record(platform_id, platform)
        for platform_id, platform in sorted(registry.get("platforms", {}).items())
    ]
    return _json(
        {
            "schema": registry.get("schema", REGISTRY_SCHEMA),
            "registry_path": registry.get("registry_path", str(_registry_path())),
            "hub_model": registry.get("hub_model", "53aihub-style sidecar integration"),
            "platform_count": len(platforms),
            "platforms": platforms,
        }
    )


def check_reference_platform_health(platform_id: str = "") -> str:
    """Check health for embedded platforms and optional sidecars without returning secrets."""
    registry = load_reference_platform_registry()
    platforms = registry.get("platforms", {})
    selected = {platform_id: platforms[platform_id]} if platform_id.strip() else platforms
    if platform_id.strip() and platform_id not in platforms:
        return _json({"status": "error", "reason": f"Unknown platform_id: {platform_id}"})

    results = []
    for pid, platform in selected.items():
        mode = str(platform.get("integration_mode") or "")
        if mode in {"embedded", "embedded_sidecar"}:
            results.append(_embedded_health(pid, platform))
        else:
            results.append(_probe_sidecar(pid, platform))

    statuses = [item.get("status", "") for item in results]
    overall = "ready"
    if any(status in {"unavailable", "needs_install", "needs_scaffold"} for status in statuses):
        overall = "warn"
    if platform_id.strip() and results and results[0].get("status") == "not_configured":
        overall = "not_configured"
    return _json({"status": overall, "platforms": results})


def route_knowledge_stack(query_intent: str = "", question: str = "") -> str:
    """Recommend DuckDB, wiki, LightRAG, local scenario tools, or optional sidecars for a question."""
    text = f"{query_intent} {question}".strip().lower()
    routes: list[dict[str, str]] = []

    numeric_patterns = (
        r"\b(库存|销量|金额|毛利|周转|覆盖天数|top\s*\d+|聚合|最近\s*\d+\s*天|mart|duckdb)\b",
        r"\b(inventory|sales|revenue|margin|turnover|aggregate|sql|fact layer)\b",
    )
    semantic_patterns = (
        r"\b(口径|规则|背景|为什么|历史经验|关联|实体|关系|semantic|lightrag|wiki)\b",
        r"\b(context|relationship|entity|knowledge graph|retrieval)\b",
    )
    scenario_patterns = (
        r"(推演|情景|方案对比|what if|保守|激进|模拟|scenario|mirofish)",
    )
    portal_patterns = (
        r"(maxkb|ruoyi|若依|企业级智能体|workflow node|外部门户)",
    )

    if any(re.search(pattern, text, re.I) for pattern in numeric_patterns):
        routes.append(
            {
                "layer": "duckdb",
                "priority": "primary",
                "tools": "query_fact_layer, query_fact_layer_from_question, list_registered_datasets",
                "reason": "Question looks numeric or aggregation-oriented.",
            }
        )
    if any(re.search(pattern, text, re.I) for pattern in semantic_patterns):
        routes.append(
            {
                "layer": "lightrag_wiki",
                "priority": "primary",
                "tools": "search_wiki, query_lightrag, query_official_lightrag, resolve_lightrag_reference_paths",
                "reason": "Question needs semantic background, rules, or linked knowledge.",
            }
        )
        routes.append(
            {
                "layer": "karpathy_llm_wiki",
                "priority": "secondary",
                "tools": "read_wiki_page, register_wiki_claim_evidence, lint_wiki_knowledge_base",
                "reason": "Durable wiki pages should carry claim/evidence lifecycle.",
            }
        )
    if any(re.search(pattern, text, re.I) for pattern in scenario_patterns):
        routes.append(
            {
                "layer": "scenario_local",
                "priority": "primary",
                "tools": "simulate_decision_scenarios, assess_decision_risks, save_decision_report",
                "reason": "Use local evidence-first scenario comparison before optional MiroFish sidecar.",
            }
        )
        _load_env()
        if os.getenv("MIROFISH_API_URL", "").strip():
            routes.append(
                {
                    "layer": "mirofish_sidecar",
                    "priority": "optional",
                    "tools": "query_external_platform_readonly",
                    "reason": "MiroFish sidecar is configured for richer swarm simulation.",
                }
            )
    if any(re.search(pattern, text, re.I) for pattern in portal_patterns):
        for portal_id, env_name in (
            ("maxkb", "MAXKB_API_URL"),
            ("ruoyi_ai", "RUOYI_AI_API_URL"),
        ):
            if os.getenv(env_name, "").strip():
                routes.append(
                    {
                        "layer": portal_id,
                        "priority": "optional",
                        "tools": "query_external_platform_readonly, check_reference_platform_health",
                        "reason": f"{portal_id} sidecar is configured.",
                    }
                )

    if not routes:
        routes = [
            {
                "layer": "duckdb",
                "priority": "primary",
                "tools": "query_fact_layer_from_question",
                "reason": "Default to fact layer for business metrics.",
            },
            {
                "layer": "lightrag_wiki",
                "priority": "secondary",
                "tools": "search_wiki, query_lightrag",
                "reason": "Fallback to local knowledge retrieval for context.",
            },
        ]

    return _json(
        {
            "status": "success",
            "query_intent": query_intent,
            "question": question,
            "routes": routes,
            "policy": "External sidecars are optional context only; DuckDB/wiki/LightRAG/ERP remain local evidence sources.",
        }
    )


def query_external_platform_readonly(platform_id: str, query: str = "", path: str = "/") -> str:
    """Read-only proxy to optional RuoYi AI / MaxKB / MiroFish sidecars. Never used as numeric fact source."""
    registry = load_reference_platform_registry()
    platform = registry.get("platforms", {}).get(platform_id.strip())
    if platform is None:
        return _json({"status": "error", "reason": f"Unknown platform_id: {platform_id}"})

    mode = str(platform.get("integration_mode") or "")
    if mode not in {"sidecar_optional"}:
        return _json(
            {
                "status": "blocked",
                "reason": f"{platform_id} is embedded locally; use primary_tools instead of sidecar proxy.",
                "primary_tools": list(platform.get("primary_tools") or []),
            }
        )

    env = _platform_env(platform)
    base_url = env["url"].rstrip("/")
    if not base_url:
        fallbacks = list(platform.get("local_fallback_tools") or [])
        return _json(
            {
                "status": "not_configured",
                "platform_id": platform_id,
                "reason": f"Set {env['url_env']} to enable this sidecar.",
                "local_fallback_tools": fallbacks,
            }
        )

    request_path = path.strip() or "/"
    url = urljoin(f"{base_url}/", request_path.lstrip("/"))
    headers = {"Content-Type": "application/json"}
    if env["api_key"]:
        headers["Authorization"] = f"Bearer {env['api_key']}"

    payload = {"query": query, "mode": "read_only", "source": "a2a_workbench"}
    try:
        if query.strip():
            response = requests.post(url, headers=headers, json=payload, timeout=20)
        else:
            response = requests.get(url, headers=headers, timeout=20)
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = {"text": response.text[:4000]}
        return _json(
            {
                "status": "success" if response.status_code < 400 else "degraded",
                "platform_id": platform_id,
                "http_status": response.status_code,
                "request_url": url,
                "response_preview": body,
                "evidence_policy": "Treat sidecar output as supplemental context only; cite local DuckDB/wiki/LightRAG/ERP for decisions.",
            }
        )
    except requests.RequestException as exc:
        return _json(
            {
                "status": "unavailable",
                "platform_id": platform_id,
                "request_url": url,
                "reason": str(exc),
                "local_fallback_tools": list(platform.get("local_fallback_tools") or []),
            }
        )
