"""
Fetch JackYun OpenAPI documentation from the official web doc backend.

Usage examples:
  python scripts/fetch_jackyun_openapi_docs.py --method erp.allocate.create
  python scripts/fetch_jackyun_openapi_docs.py --url "https://open.jackyun.com/developer/apidocinfo.html?from=self&value=undefined&id=erp.warehouse.get&name=true"
  python scripts/fetch_jackyun_openapi_docs.py --urls-file methods.txt --output-dir dist/jackyun_docs
  python scripts/fetch_jackyun_openapi_docs.py --all-methods --output-dir dist/jackyun_all_docs
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse

import requests


BASE_URL = "https://open.jackyun.com"
API_LIST_ENDPOINT = "/open-platform/errorcode/jOpenErrorCode/getApiAll"
DOC_DETAIL_ENDPOINT = "/open-platform/doc/getAllDocByMethod"
SECRET_SALT = "e48f22be42de690a149c8df522969fd0"


def build_secret(timestamp_ms: str) -> str:
    return hashlib.md5((SECRET_SALT + timestamp_ms).lower().encode("utf-8")).hexdigest()


def normalize_method(value: str) -> str:
    value = (value or "").replace("\ufeff", "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return parse_method_from_url(value)
    return value


def parse_method_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query)
    method = (query.get("id") or [""])[0].strip()
    if not method:
        raise ValueError(f"Cannot parse method id from URL: {url}")
    return method


def load_methods_from_file(path: Path) -> list[str]:
    methods: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        methods.append(normalize_method(line))
    return methods


def ensure_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def sanitize_filename(method: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", method)


def fetch_all_methods(session: requests.Session) -> list[str]:
    response = session.post(BASE_URL + API_LIST_ENDPOINT, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"Failed to fetch method catalog: {payload}")
    return ensure_unique(payload.get("result", {}).get("data", []) or [])


def fetch_doc_detail(session: requests.Session, method: str) -> dict:
    timestamp_ms = str(int(time.time() * 1000))
    params = {
        "method": method,
        "secret": build_secret(timestamp_ms),
        "timestamp": timestamp_ms,
    }
    response = session.get(BASE_URL + DOC_DETAIL_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200:
        raise RuntimeError(f"Failed to fetch {method}: {payload}")
    return payload


def build_method_summary(doc_payload: dict) -> dict:
    data = doc_payload.get("result", {}).get("data", {}) or {}
    doc_entity = data.get("docEntity", {}) or {}
    parameter_infos = data.get("docParameterInfos", []) or []

    request_params = []
    response_params = []
    for item in parameter_infos:
        summary_item = {
            "full_parameter_name": item.get("fullParameterName"),
            "parameter_name": item.get("parameterName"),
            "parent_name": item.get("parentName"),
            "data_type": item.get("dataType"),
            "required": item.get("bRequired"),
            "remark": item.get("remark"),
            "demo_value": item.get("demoValue"),
        }
        if item.get("bRequest"):
            request_params.append(summary_item)
        else:
            response_params.append(summary_item)

    return {
        "method": doc_entity.get("method"),
        "name": doc_entity.get("name"),
        "directory_code": doc_entity.get("directoryCode"),
        "remark": doc_entity.get("remark"),
        "data_version": doc_entity.get("dataVersion"),
        "authorized": doc_entity.get("bAuthorized"),
        "request_params": request_params,
        "response_params": response_params,
    }


def save_doc_payload(output_dir: Path, method: str, doc_payload: dict):
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_filename(method)
    raw_path = output_dir / f"{base_name}.raw.json"
    summary_path = output_dir / f"{base_name}.summary.json"
    raw_path.write_text(json.dumps(doc_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(build_method_summary(doc_payload), ensure_ascii=False, indent=2), encoding="utf-8")


def write_index(output_dir: Path, summaries: list[dict]):
    index = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_methods": len(summaries),
        "methods": [
            {
                "method": item.get("method"),
                "name": item.get("name"),
                "data_version": item.get("data_version"),
                "request_param_count": len(item.get("request_params", [])),
                "response_param_count": len(item.get("response_params", [])),
            }
            for item in summaries
        ],
    }
    (output_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch JackYun OpenAPI docs from official backend.")
    parser.add_argument("--method", action="append", default=[], help="Method name, repeatable.")
    parser.add_argument("--url", action="append", default=[], help="Doc page URL, repeatable.")
    parser.add_argument("--methods-file", type=Path, help="UTF-8 text file with one method per line.")
    parser.add_argument("--urls-file", type=Path, help="UTF-8 text file with one doc URL per line.")
    parser.add_argument("--all-methods", action="store_true", help="Fetch the entire published method catalog.")
    parser.add_argument("--output-dir", type=Path, default=Path("dist/jackyun_openapi_docs"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_methods: list[str] = []
    requested_methods.extend(normalize_method(item) for item in args.method)
    requested_methods.extend(normalize_method(item) for item in args.url)

    if args.methods_file:
        requested_methods.extend(load_methods_from_file(args.methods_file))
    if args.urls_file:
        requested_methods.extend(load_methods_from_file(args.urls_file))

    session = requests.Session()
    session.headers.update({
        "User-Agent": "jackyun-skill-project-doc-fetcher/1.0",
    })

    if args.all_methods:
        requested_methods.extend(fetch_all_methods(session))

    methods = ensure_unique(requested_methods)
    if not methods:
        print("No methods provided. Use --method, --url, --methods-file, --urls-file, or --all-methods.", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict] = []
    failures: list[dict] = []

    for index, method in enumerate(methods, start=1):
        try:
            payload = fetch_doc_detail(session, method)
            save_doc_payload(args.output_dir, method, payload)
            summary = build_method_summary(payload)
            summaries.append(summary)
            print(f"[{index}/{len(methods)}] fetched {method}")
        except Exception as exc:  # pragma: no cover - CLI fallback path
            failures.append({"method": method, "error": str(exc)})
            print(f"[{index}/{len(methods)}] failed {method}: {exc}", file=sys.stderr)

    write_index(args.output_dir, summaries)
    if failures:
        (args.output_dir / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
