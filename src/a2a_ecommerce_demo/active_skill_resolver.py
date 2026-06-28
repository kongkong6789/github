from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
SKILL_REGISTRY_DIR = Path(os.getenv("A2A_SKILL_REGISTRY_DIR", DATA_DIR / "skill_registry")).resolve()
TEMPLATE_DIR = Path(os.getenv("A2A_AGENT_TEMPLATE_DIR", DATA_DIR / "agent_templates")).resolve()

ACTIVE_SKILL_STATUSES = {"active"}
MAX_SKILL_PROMPT_CHARS = 6000
MAX_INJECTED_SKILLS = 2

BUSINESS_KEYWORDS = {
    "UNOVE",
    "天猫",
    "淘宝",
    "天猫国际",
    "抖音",
    "拼多多",
    "京东",
    "唯品会",
    "得物",
    "小红书",
    "快手",
    "李佳琦",
    "千川",
    "达播",
    "店播",
    "百补",
    "大贸",
    "分销",
    "外贸",
    "线下",
    "客户",
    "客户分层",
    "渠道",
    "月度",
    "计划",
    "目标",
    "竞品",
    "舆情",
    "营销",
    "库存",
    "补货",
    "采购",
    "广告",
    "投放",
    "销售",
    "日销",
    "推广",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _skill_path(skill_id: str) -> Path:
    return SKILL_REGISTRY_DIR / "skills" / f"{_slugify(skill_id)}.json"


def _template_path(skill_id: str) -> Path:
    return TEMPLATE_DIR / f"{_slugify(skill_id)}.json"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", str(value)).strip("-")
    return slug[:96] or "agent-skill"


def _safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _latin_tokens(value: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", value)}


def _cjk_chunks(value: str) -> set[str]:
    chunks: set[str] = set()
    for part in re.findall(r"[\u4e00-\u9fff]{2,}", value):
        if len(part) <= 8:
            chunks.add(part)
        for size in (2, 3, 4):
            for index in range(0, max(0, len(part) - size + 1)):
                chunks.add(part[index : index + size])
    return chunks


def _load_skill_records() -> list[dict[str, Any]]:
    registry = _read_json(SKILL_REGISTRY_DIR / "registry.json")
    skill_ids = [str(item.get("skill_id", "")).strip() for item in registry.get("skills", {}).values()]
    skill_ids = [skill_id for skill_id in skill_ids if skill_id]
    if not skill_ids:
        skills_dir = SKILL_REGISTRY_DIR / "skills"
        skill_ids = [path.stem for path in skills_dir.glob("*.json")] if skills_dir.exists() else []

    records: list[dict[str, Any]] = []
    for skill_id in sorted(set(skill_ids)):
        record = _read_json(_skill_path(skill_id))
        skill = record.get("skill")
        if isinstance(skill, dict):
            records.append(record)
    return records


def _load_template(skill_id: str) -> dict[str, Any]:
    return _read_json(_template_path(skill_id))


def _candidate_keywords(skill: dict[str, Any], wiki_content: str, template: dict[str, Any]) -> dict[str, int]:
    weighted: dict[str, int] = {}

    def add(keyword: str, weight: int) -> None:
        keyword = keyword.strip()
        if len(keyword) < 2:
            return
        current = weighted.get(keyword, 0)
        weighted[keyword] = max(current, weight)

    for token in _latin_tokens(" ".join([str(skill.get("skill_id", "")), str(skill.get("name", "")), str(skill.get("role", ""))])):
        add(token, 5)
    for token in _cjk_chunks(" ".join([str(skill.get("name", "")), str(skill.get("role", ""))])):
        add(token, 4)

    for scenario in _as_list(skill.get("scenarios")):
        add(scenario, 4)
        for token in _latin_tokens(scenario):
            add(token, 4)
        for token in _cjk_chunks(scenario):
            add(token, 2)

    searchable_content = "\n".join(
        [
            wiki_content[:12000],
            str(template.get("prompt", ""))[:12000],
            str(skill.get("goal", "")),
            str(skill.get("source_wiki_path", "")),
            str(skill.get("source_skill_path", "")),
        ]
    )
    for keyword in BUSINESS_KEYWORDS:
        if keyword in searchable_content:
            add(keyword, 2)
    for token in _latin_tokens(searchable_content):
        if len(token) >= 3:
            add(token, 2)

    return weighted


def _score_skill(prompt: str, skill: dict[str, Any], wiki_content: str, template: dict[str, Any]) -> tuple[int, list[str]]:
    normalized_prompt = _normalize_text(prompt)
    raw_prompt = prompt
    score = 0
    matched: list[str] = []
    for keyword, weight in _candidate_keywords(skill, wiki_content, template).items():
        if not keyword:
            continue
        haystack = normalized_prompt if re.search(r"[a-zA-Z]", keyword) else raw_prompt
        needle = keyword.lower() if re.search(r"[a-zA-Z]", keyword) else keyword
        if needle in haystack:
            score += weight
            matched.append(keyword)
    matched = sorted(set(matched), key=lambda item: (-len(item), item))[:12]
    return score, matched


def resolve_active_skills_for_prompt(prompt: str, limit: int = MAX_INJECTED_SKILLS) -> list[dict[str, Any]]:
    """Resolve active project skills that should be injected for a user prompt."""
    prompt = prompt.strip()
    if not prompt:
        return []

    matches: list[dict[str, Any]] = []
    for record in _load_skill_records():
        skill = record.get("skill", {})
        if skill.get("status") not in ACTIVE_SKILL_STATUSES:
            continue
        skill_id = str(skill.get("skill_id", "")).strip()
        if not skill_id:
            continue
        template = _load_template(skill_id)
        wiki_content = str(record.get("wiki_content", ""))
        score, matched_keywords = _score_skill(prompt, skill, wiki_content, template)
        if score < 5:
            continue
        matches.append(
            {
                "skill_id": skill_id,
                "name": skill.get("name", skill_id),
                "version": skill.get("version", 0),
                "status": skill.get("status", ""),
                "score": score,
                "matched_keywords": matched_keywords,
                "source_wiki_path": skill.get("source_wiki_path", ""),
                "source_type": skill.get("source_type", ""),
                "source_skill_path": skill.get("source_skill_path", ""),
                "managed_skill_dir": skill.get("managed_skill_dir", ""),
                "tool_allowlist": _as_list(skill.get("tool_allowlist")),
                "output_schema": _as_list(skill.get("output_schema")),
                "updated_at": skill.get("updated_at", ""),
                "prompt": str(template.get("prompt") or wiki_content).strip(),
            }
        )

    matches.sort(key=lambda item: (int(item.get("score", 0)), str(item.get("updated_at", ""))), reverse=True)
    return matches[: max(0, int(limit))]


def build_active_skill_system_message(matches: list[dict[str, Any]]) -> SystemMessage | None:
    """Build a SystemMessage containing matched active Skill instructions."""
    active_matches = [match for match in matches if match.get("status") == "active"]
    if not active_matches:
        return None

    sections = [
        "Active Skill matched for this user request.",
        "Apply these project Skill rules as durable business context. They do not grant extra tool permissions.",
        "Use local DuckDB/wiki evidence first; use live ERP/MCP read-only tools only when the user asks for realtime data or local evidence is missing.",
        "Any write/external action still requires human confirmation.",
    ]
    for match in active_matches[:MAX_INJECTED_SKILLS]:
        prompt = str(match.get("prompt", "")).strip()
        if len(prompt) > MAX_SKILL_PROMPT_CHARS:
            prompt = prompt[:MAX_SKILL_PROMPT_CHARS].rstrip() + "\n... skill prompt truncated ..."
        sections.append(
            "\n".join(
                [
                    "",
                    f"Skill: {match.get('name', match.get('skill_id', ''))}",
                    f"skill_id: {match.get('skill_id', '')}",
                    f"version: {match.get('version', 0)}",
                    f"source_wiki_path: {match.get('source_wiki_path', '')}",
                    f"source_type: {match.get('source_type', '')}",
                    f"source_skill_path: {match.get('source_skill_path', '')}",
                    f"managed_skill_dir: {match.get('managed_skill_dir', '')}",
                    f"matched_keywords: {', '.join(_as_list(match.get('matched_keywords')))}",
                    f"tool_allowlist: {', '.join(_as_list(match.get('tool_allowlist')))}",
                    f"output_schema: {', '.join(_as_list(match.get('output_schema')))}",
                    "Skill prompt:",
                    prompt,
                ]
            )
        )

    return SystemMessage(content="\n".join(sections))


def inject_active_skill_messages(messages: list[Any], prompt: str) -> list[Any]:
    """Return model input messages with matched active Skill SystemMessage prepended."""
    injection = build_active_skill_system_message(resolve_active_skills_for_prompt(prompt))
    if injection is None:
        return messages
    return [injection, *messages]
