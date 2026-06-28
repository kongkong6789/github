"""
Local persistent state for this skill.

The files here are intentionally small JSON files under data/ so the skill can
remember the confirmed operator and reuse stable master data between runs.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILE_PATH = DATA_DIR / "profile.json"
CACHE_DIR = DATA_DIR / "cache"
TEMPLATE_DIR = DATA_DIR / "templates"
EXPERIENCE_DIR = DATA_DIR / "experiences"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_data_dirs():
    for path in (DATA_DIR, CACHE_DIR, TEMPLATE_DIR, EXPERIENCE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any):
    ensure_data_dirs()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_profile() -> dict[str, Any]:
    return read_json(PROFILE_PATH, {})


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    payload = {"updated_at": _now_iso(), **profile}
    write_json(PROFILE_PATH, payload)
    return payload


def set_default_operator(user_name: str, user_record: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = get_profile()
    profile["default_operator_name"] = str(user_name or "").strip()
    if user_record:
        profile["default_operator"] = user_record
    return save_profile(profile)


def get_default_operator_name() -> str:
    return str(get_profile().get("default_operator_name") or "").strip()


def get_user_preferences() -> dict[str, Any]:
    preferences = get_profile().get("usage_preferences", {})
    return preferences if isinstance(preferences, dict) else {}


def save_user_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    profile = get_profile()
    profile["usage_preferences"] = preferences or {}
    return save_profile(profile)


def set_user_preference(key: str, value: Any) -> dict[str, Any]:
    preferences = get_user_preferences()
    preferences[key] = value
    save_user_preferences(preferences)
    return preferences


def get_user_preference(key: str, default: Any = None) -> Any:
    return get_user_preferences().get(key, default)


def increment_user_preference_counter(group: str, key: str, value: Any) -> dict[str, Any]:
    """
    Remember frequently used values without overwriting user data.

    Example groups: sales_order.shopName, sales_order.warehouseName.
    """
    value_text = str(value or "").strip()
    if not value_text:
        return get_user_preferences()
    preferences = get_user_preferences()
    counters = preferences.setdefault("counters", {})
    group_counters = counters.setdefault(group, {})
    group_counters[value_text] = int(group_counters.get(value_text, 0) or 0) + 1
    preferences["last_used"] = preferences.get("last_used", {})
    preferences["last_used"][group] = value_text
    save_user_preferences(preferences)
    return preferences


def get_user_preference_counter(group: str) -> dict[str, int]:
    counters = get_user_preferences().get("counters", {})
    group_counters = counters.get(group, {}) if isinstance(counters, dict) else {}
    return group_counters if isinstance(group_counters, dict) else {}


def get_most_used_preference(group: str, default: Any = None) -> Any:
    group_counters = get_user_preference_counter(group)
    if not group_counters:
        return default
    return sorted(group_counters.items(), key=lambda item: (-int(item[1] or 0), item[0]))[0][0]


def _cache_path(name: str) -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
    return CACHE_DIR / f"{safe_name}.json"


def get_cached_master_data(name: str) -> list[dict[str, Any]]:
    payload = read_json(_cache_path(name), {})
    items = payload.get("items") if isinstance(payload, dict) else None
    return items if isinstance(items, list) else []


def save_cached_master_data(name: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    write_json(_cache_path(name), {"updated_at": _now_iso(), "items": items or []})
    return items or []


def get_master_data(
    name: str,
    fetcher: Callable[[], list[dict[str, Any]]],
    matcher: Callable[[dict[str, Any]], bool] | None = None,
    save_fresh: bool = True,
) -> list[dict[str, Any]]:
    cached = get_cached_master_data(name)
    if cached:
        matched = [item for item in cached if matcher(item)] if matcher else cached
        if matched:
            return matched

    fresh = fetcher()
    if fresh:
        if save_fresh:
            save_cached_master_data(name, fresh)
        return [item for item in fresh if matcher(item)] if matcher else fresh
    return []


def append_experience(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_data_dirs()
    record = {"timestamp": _now_iso(), "kind": kind, **payload}
    path = EXPERIENCE_DIR / f"{kind}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_experiences(kind: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    Read recent local experience records.

    Invalid lines are ignored so one broken runtime write will not block future
    workflows.
    """
    path = EXPERIENCE_DIR / f"{kind}.jsonl"
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
        if len(records) >= limit:
            break
    return records
