"""
Reader for the official JackYun CLI machine-readable docs.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGED_CLI_DOCS_DIR = PROJECT_ROOT / "docs" / "jackyun_cli_docs"
DIST_CLI_DOCS_DIR = PROJECT_ROOT / "dist" / "jackyun_cli_docs"
CLI_DOCS_DIR = PACKAGED_CLI_DOCS_DIR if PACKAGED_CLI_DOCS_DIR.exists() else DIST_CLI_DOCS_DIR
METHOD_INDEX_PATH = CLI_DOCS_DIR / "methods-index.json"


def load_methods_index() -> list[dict]:
    if not METHOD_INDEX_PATH.exists():
        return []
    payload = json.loads(METHOD_INDEX_PATH.read_text(encoding="utf-8"))
    methods = payload.get("methods", [])
    return methods if isinstance(methods, list) else []


def find_methods(keyword: str) -> list[dict]:
    needle = str(keyword or "").lower()
    if not needle:
        return []
    matches = []
    for item in load_methods_index():
        text = json.dumps(item, ensure_ascii=False).lower()
        if needle in text:
            matches.append(item)
    return matches


def method_exists(method: str) -> bool:
    return any(item.get("method") == method for item in load_methods_index())


def _detail_filename(method_or_url: str) -> str:
    value = str(method_or_url or "").strip()
    if value.startswith("http://") or value.startswith("https://"):
        return Path(urlparse(value).path).name
    return f"{value}.json"


def load_method_detail(method_or_url: str) -> dict:
    path = CLI_DOCS_DIR / _detail_filename(method_or_url)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def request_properties(method_or_url: str) -> dict:
    detail = load_method_detail(method_or_url)
    schema = detail.get("request", {}).get("schema", {})
    return schema.get("properties", {}) if isinstance(schema, dict) else {}
