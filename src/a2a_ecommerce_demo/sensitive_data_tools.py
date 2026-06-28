from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
WAREHOUSE_DIR = Path(os.getenv("A2A_WAREHOUSE_DIR", DATA_DIR / "warehouse")).resolve()

SENSITIVE_FIELD_RULES: dict[str, dict[str, Any]] = {
    "customer_pii": {
        "label": "客户个人信息",
        "risk_level": "high",
        "handling": "mask_values",
        "patterns": [
            "手机号",
            "手机",
            "电话",
            "收货人",
            "客户姓名",
            "姓名",
            "地址",
            "身份证",
            "会员id",
            "会员_id",
            "openid",
            "买家账号",
            "收件人",
        ],
    },
    "procurement_price": {
        "label": "采购价/供应商报价",
        "risk_level": "medium",
        "handling": "aggregate_or_audit",
        "patterns": [
            "采购单价",
            "采购价",
            "进价",
            "成本价",
            "供应商报价",
            "采购金额",
            "含税单价",
            "未税单价",
        ],
    },
    "finance": {
        "label": "财务数据",
        "risk_level": "medium",
        "handling": "aggregate_or_audit",
        "patterns": [
            "毛利",
            "净利",
            "利润",
            "回款",
            "应收",
            "应付",
            "现金流",
            "账期",
            "收入",
            "费用",
            "成本",
        ],
    },
}

MASKING_REQUIRED_CATEGORIES = {"customer_pii"}
PHONE_VALUE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_VALUE_PATTERN = re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}")
ID_VALUE_PATTERN = re.compile(r"(?<![0-9Xx])\d{17}[0-9Xx](?![0-9Xx])")


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _parse_json(value: str, fallback: Any) -> Any:
    if not value.strip():
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        if isinstance(fallback, list):
            return [item.strip() for item in re.split(r"[,，\n]", value) if item.strip()]
        return fallback


def _normalize_field(field: Any) -> str:
    return re.sub(r"[\s_\-]+", "", str(field or "").strip().lower())


def classify_field_name(field: str) -> dict[str, str] | None:
    """Return lightweight sensitive-field classification for one field name."""
    normalized = _normalize_field(field)
    if not normalized:
        return None
    for category, rule in SENSITIVE_FIELD_RULES.items():
        patterns = [_normalize_field(pattern) for pattern in rule["patterns"]]
        if any(pattern and pattern in normalized for pattern in patterns):
            return {
                "field": str(field),
                "category": category,
                "label": str(rule["label"]),
                "risk_level": str(rule["risk_level"]),
                "handling": str(rule["handling"]),
            }
    return None


def summarize_field_classifications(fields: list[str]) -> dict[str, Any]:
    seen: set[tuple[str, str]] = set()
    sensitive_fields: list[dict[str, str]] = []
    for field in fields:
        classification = classify_field_name(field)
        if not classification:
            continue
        key = (classification["field"], classification["category"])
        if key in seen:
            continue
        seen.add(key)
        sensitive_fields.append(classification)

    category_counts = Counter(item["category"] for item in sensitive_fields)
    categories = sorted(category_counts)
    return {
        "status": "success",
        "sensitive_fields": sensitive_fields,
        "total_sensitive_fields": len(sensitive_fields),
        "categories": categories,
        "category_counts": dict(sorted(category_counts.items())),
        "requires_masking_categories": [
            category for category in categories if category in MASKING_REQUIRED_CATEGORIES
        ],
    }


def classify_sensitive_fields(fields_json: str) -> str:
    """Classify field names into lightweight internal sensitive-data categories."""
    raw_fields = _parse_json(fields_json, [])
    if isinstance(raw_fields, dict):
        fields = [str(key) for key in raw_fields]
    elif isinstance(raw_fields, list):
        fields = [str(field) for field in raw_fields]
    else:
        fields = [str(raw_fields)]
    return _json(summarize_field_classifications(fields))


def _mask_phone(value: str) -> str:
    return re.sub(r"(\d{3})\d{4}(\d{4})", r"\1****\2", value)


def _mask_customer_value(field: str, value: Any) -> Any:
    if value is None:
        return value
    text = str(value)
    normalized = _normalize_field(field)
    if "地址" in normalized:
        return "***REDACTED_ADDRESS***"
    if "身份证" in normalized:
        return "***REDACTED_ID***"
    if any(token in normalized for token in ["手机", "电话"]):
        masked = _mask_phone(text)
        return masked if masked != text else "***REDACTED_PHONE***"
    if any(token in normalized for token in ["姓名", "收货人", "收件人"]):
        return f"{text[:1]}*" if text else ""
    if any(token in normalized for token in ["会员", "openid", "买家账号"]):
        return "***REDACTED_CUSTOMER_ID***"
    return "***REDACTED_PII***"


def _mask_detected_pii_value(value: Any) -> tuple[Any, bool]:
    if value is None:
        return value, False
    text = str(value)
    changed = False
    masked = PHONE_VALUE_PATTERN.sub(lambda match: _mask_phone(match.group(0)), text)
    if masked != text:
        changed = True
    masked_email = EMAIL_VALUE_PATTERN.sub("***REDACTED_EMAIL***", masked)
    if masked_email != masked:
        changed = True
    masked_id = ID_VALUE_PATTERN.sub("***REDACTED_ID***", masked_email)
    if masked_id != masked_email:
        changed = True
    return (masked_id, True) if changed else (value, False)


def mask_sensitive_record(record_json: str) -> str:
    """Mask customer PII values in one record while leaving business aggregates intact."""
    record = _parse_json(record_json, {})
    if not isinstance(record, dict):
        return _json({"status": "error", "error": "record_json must be a JSON object", "record": {}})

    masked: dict[str, Any] = {}
    masked_categories: set[str] = set()
    sensitive_fields: list[dict[str, str]] = []
    for key, value in record.items():
        classification = classify_field_name(str(key))
        if classification:
            sensitive_fields.append(classification)
        if classification and classification["category"] in MASKING_REQUIRED_CATEGORIES:
            masked[str(key)] = _mask_customer_value(str(key), value)
            masked_categories.add(classification["category"])
        else:
            masked_value, detected = _mask_detected_pii_value(value)
            masked[str(key)] = masked_value
            if detected:
                masked_categories.add("customer_pii")

    return _json(
        {
            "status": "success",
            "record": masked,
            "masked_categories": sorted(masked_categories),
            "sensitive_fields": sensitive_fields,
        }
    )


def summarize_sensitive_fields_from_registry(registry_path: str = "") -> str:
    """Summarize sensitive field names from a dataset registry JSON file."""
    path = Path(registry_path).expanduser() if registry_path else WAREHOUSE_DIR / "dataset_registry.json"
    path = path.resolve(strict=False)
    warehouse_root = WAREHOUSE_DIR.resolve(strict=False)
    try:
        relative = path.relative_to(warehouse_root)
        if str(relative).startswith(".."):
            raise ValueError("registry_path must be under warehouse directory")
    except ValueError:
        return _json(
            {
                "status": "error",
                "registry_path": str(path),
                "error": "registry_path must be under warehouse directory",
            }
        )
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _json({"status": "error", "registry_path": str(path), "error": str(exc)})

    datasets = registry.get("datasets", {})
    dataset_values = list(datasets.values()) if isinstance(datasets, dict) else datasets
    if not isinstance(dataset_values, list):
        dataset_values = []
    summary_items = []
    all_fields: list[str] = []
    for dataset in dataset_values:
        if not isinstance(dataset, dict):
            continue
        fields = [
            str(profile.get("field"))
            for profile in dataset.get("field_profiles", [])
            if isinstance(profile, dict) and profile.get("field")
        ]
        field_summary = summarize_field_classifications(fields)
        if field_summary["total_sensitive_fields"] == 0:
            continue
        all_fields.extend(fields)
        summary_items.append(
            {
                "slug": dataset.get("dataset_slug") or dataset.get("slug") or "",
                "source": dataset.get("relative_source") or dataset.get("source") or "",
                "sensitive_fields": field_summary["sensitive_fields"],
                "category_counts": field_summary["category_counts"],
            }
        )

    overall = summarize_field_classifications(all_fields)
    return _json({"status": "success", "registry_path": str(path), **overall, "datasets": summary_items})


def record_sensitive_field_access(
    actor: str = "agent",
    task_id: str = "",
    dataset: str = "",
    fields_json: str = "",
    purpose: str = "",
) -> str:
    """Record that an Agent used sensitive fields, without logging row values."""
    from src.a2a_ecommerce_demo.enterprise_audit_tools import record_audit_event

    summary = json.loads(classify_sensitive_fields(fields_json))
    categories = sorted(summary.get("categories", []))
    fields = sorted({item["field"] for item in summary.get("sensitive_fields", [])})
    return record_audit_event(
        "sensitive_field_accessed",
        actor=actor,
        summary=purpose or "Sensitive field categories used by agent.",
        task_id=task_id,
        risks=[f"sensitive:{category}" for category in categories],
        metadata={
            "dataset": dataset,
            "fields": fields,
            "categories": categories,
            "category_counts": summary.get("category_counts", {}),
            "masking_required_categories": summary.get("requires_masking_categories", []),
        },
    )
