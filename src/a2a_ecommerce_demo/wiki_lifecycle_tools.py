from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.a2a_ecommerce_demo.state_io import atomic_write_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
DOCS_DIR = Path(os.getenv("A2A_DOCS_DIR", PROJECT_ROOT / "docs")).resolve()
WIKI_DIR = Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).resolve()
HEALTH_PATH = DATA_DIR / "wiki_knowledge_health.json"

WIKI_PAGE_TYPES = (
    "source",
    "dataset",
    "brand",
    "sku",
    "channel",
    "warehouse",
    "supplier",
    "decision",
    "claim",
    "contradiction",
    "playbook",
    "index",
    "log",
    "schema",
)
DECISION_READY_TYPES = {
    "brand",
    "channel",
    "claim",
    "dataset",
    "decision",
    "playbook",
    "sku",
    "supplier",
    "warehouse",
}
CORE_DIRS = (
    "brands",
    "claims",
    "contradictions",
    "playbooks",
    "sources",
    "skus",
    "channels",
    "warehouses",
    "suppliers",
    "decisions",
    "datasets",
    "products",
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _safe_under(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if root not in [resolved, *resolved.parents]:
        raise ValueError(f"Refusing to access outside {root}: {resolved}")
    return resolved


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    for directory in CORE_DIRS:
        (WIKI_DIR / directory).mkdir(parents=True, exist_ok=True)


def _slugify(value: str, fallback: str = "note") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", value).strip("-").lower()
    return slug[:90] or fallback


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _write_text_if_missing(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return True


def _relative_wiki_path(path: Path) -> str:
    return path.relative_to(WIKI_DIR).as_posix()


def _wiki_link(path: str, title: str) -> str:
    target = path.removesuffix(".md")
    alias = title.replace("|", "/").strip() or target.rsplit("/", 1)[-1]
    return f"[[{target}|{alias}]]"


def _markdown_files() -> list[Path]:
    _ensure_dirs()
    return sorted(
        path
        for path in WIKI_DIR.rglob("*.md")
        if ".obsidian" not in path.parts
    )


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


def _parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    frontmatter = text[3:end].strip("\n")
    parsed: dict[str, Any] = {}
    current_list_key = ""
    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            parsed.setdefault(current_list_key, []).append(line[4:].strip().strip('"'))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_list_key = ""
        if value == "":
            parsed[key] = []
            current_list_key = key
        elif value.startswith("[") and value.endswith("]"):
            parsed[key] = [
                item.strip().strip('"')
                for item in value[1:-1].split(",")
                if item.strip()
            ]
        else:
            parsed[key] = value.strip('"')
    return parsed


def _first_heading(text: str, fallback: str) -> str:
    body = _strip_frontmatter(text)
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def _first_summary(text: str) -> str:
    body = _strip_frontmatter(text)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("- "):
            continue
        return stripped[:160]
    return ""


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _infer_page_type(rel_path: str, frontmatter: dict[str, Any]) -> str:
    explicit = str(frontmatter.get("type") or "").strip()
    if explicit in WIKI_PAGE_TYPES:
        return explicit
    first = rel_path.split("/", 1)[0]
    return {
        "brands": "brand",
        "claims": "claim",
        "contradictions": "contradiction",
        "data-dictionary": "dataset",
        "datasets": "dataset",
        "decisions": "decision",
        "inventory": "warehouse",
        "logs": "source",
        "platform-rules": "playbook",
        "playbooks": "playbook",
        "products": "brand",
        "skus": "sku",
        "sources": "source",
        "suppliers": "supplier",
        "warehouses": "warehouse",
    }.get(first, "source")


def _has_evidence(text: str, frontmatter: dict[str, Any]) -> bool:
    if _as_list(frontmatter.get("evidence")) or str(frontmatter.get("source") or "").strip():
        return True
    lowered = text.lower()
    return any(
        token in lowered
        for token in ["## evidence", "## 关键证据", "数据源", "source:", "row_count", "live_read_only_fallback"]
    )


def _page_record(path: Path) -> dict[str, Any]:
    rel_path = _relative_wiki_path(path)
    text = _read_text(path)
    frontmatter = _parse_frontmatter(text)
    page_type = _infer_page_type(rel_path, frontmatter)
    title = _first_heading(text, path.stem)
    has_evidence = _has_evidence(text, frontmatter)
    updated_at = str(frontmatter.get("updated_at") or datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z"))
    status = str(frontmatter.get("status") or "current")
    return {
        "path": rel_path,
        "title": title,
        "type": page_type,
        "summary": _first_summary(text),
        "updated_at": updated_at,
        "evidence": _as_list(frontmatter.get("evidence")),
        "has_frontmatter": bool(frontmatter),
        "has_evidence": has_evidence,
        "decision_ready": page_type in DECISION_READY_TYPES and has_evidence,
        "status": status,
    }


def _schema_markdown() -> str:
    page_types = "\n".join(f"- `{page_type}`" for page_type in WIKI_PAGE_TYPES)
    return f"""# Wiki Schema

This document defines the local LLM Wiki discipline for the ecommerce workbench.

## Principle

The wiki is a durable knowledge codebase, not a dump of chat answers. Raw files remain immutable sources, DuckDB/ERP own numeric facts, LightRAG owns semantic retrieval, and Agent-written wiki pages own reusable business understanding.

## Page Types

{page_types}

## Required Frontmatter

```yaml
---
type: decision
updated_at: 2026-05-20T00:00:00Z
source: wiki/log.md
evidence:
  - wiki/datasets/example/overview.md
status: current
---
```

## Evidence Rules

- ERP live reads must be marked `live_read_only_fallback` and include query time, filters and row count.
- DuckDB mart claims must include the mart/view name, SQL summary and registry update time.
- Durable claims use `status: current`, `status: stale` or `status: contradicted`.
- Every high-value answer should be archived to `wiki/decisions/` and linked from `wiki/log.md`.
"""


def _agents_markdown() -> str:
    return """# Wiki Agent Rules

Agents maintaining this vault must follow `docs/wiki_schema.md`.

- Search `wiki/index.md` first for reusable pages.
- Append every ingest, query archive, lint pass, claim update and rule change to `wiki/log.md`.
- Use `wiki/claims/` for atomic business claims with evidence.
- Use `wiki/decisions/` for decision reports and high-value archived answers.
- Do not treat ERP live snapshots as permanent facts unless they are later registered into DuckDB.
- Refresh `wiki/index.md` after creating or materially updating pages.
"""


def _log_initial_markdown() -> str:
    return f"""---
type: log
updated_at: {_now()}
---

# Wiki Log

## [{_now()[:10]}] system | P15 wiki lifecycle initialized

- Summary: Created append-only knowledge evolution log.
- Links: [[index|Wiki Index]]
"""


def ensure_wiki_knowledge_scaffold() -> str:
    """Create P15 wiki schema, core directories, index/log placeholders and Agent rules."""
    _ensure_dirs()
    created = []
    if _write_text_if_missing(DOCS_DIR / "wiki_schema.md", _schema_markdown()):
        created.append(str((DOCS_DIR / "wiki_schema.md").resolve()))
    if _write_text_if_missing(WIKI_DIR / "AGENTS.md", _agents_markdown()):
        created.append(str((WIKI_DIR / "AGENTS.md").resolve()))
    if _write_text_if_missing(WIKI_DIR / "log.md", _log_initial_markdown()):
        created.append(str((WIKI_DIR / "log.md").resolve()))
    if _write_text_if_missing(
        WIKI_DIR / "index.md",
        f"---\ntype: index\nupdated_at: {_now()}\n---\n\n# Wiki Index\n\nRun `refresh_wiki_index` to populate this catalog.\n",
    ):
        created.append(str((WIKI_DIR / "index.md").resolve()))
    return _json(
        {
            "status": "success",
            "created": created,
            "docs_schema": str((DOCS_DIR / "wiki_schema.md").resolve()),
            "wiki_agents": str((WIKI_DIR / "AGENTS.md").resolve()),
            "wiki_index": str((WIKI_DIR / "index.md").resolve()),
            "wiki_log": str((WIKI_DIR / "log.md").resolve()),
            "page_types": list(WIKI_PAGE_TYPES),
        }
    )


def refresh_wiki_index() -> str:
    """Rebuild `wiki/index.md` as the content-oriented catalog for Agent navigation."""
    _ensure_dirs()
    records = [
        _page_record(path)
        for path in _markdown_files()
        if _relative_wiki_path(path) != "index.md"
    ]
    records.sort(key=lambda item: (item["type"], item["path"]))
    generated_at = _now()
    lines = [
        "---",
        "type: index",
        f"updated_at: {generated_at}",
        "source: wiki",
        "---",
        "",
        "# Wiki Index",
        "",
        "This index is generated from local wiki pages for Agent navigation.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Pages indexed: `{len(records)}`",
        "",
    ]
    for page_type in sorted({record["type"] for record in records}):
        lines.extend([f"## {page_type}", "", "| Page | Summary | Evidence | Decision Ready | Updated |", "| --- | --- | --- | --- | --- |"])
        for record in [item for item in records if item["type"] == page_type]:
            evidence = "yes" if record["has_evidence"] else "no"
            decision_ready = "yes" if record["decision_ready"] else "no"
            summary = str(record["summary"]).replace("|", "/") or "-"
            lines.append(
                f"| {_wiki_link(record['path'], record['title'])} | {summary} | {evidence} | {decision_ready} | `{record['updated_at']}` |"
            )
        lines.append("")
    (WIKI_DIR / "index.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    append_wiki_log_event(
        event_type="lint",
        title="Wiki index refreshed",
        summary=f"Indexed {len(records)} wiki pages.",
        links=["wiki/index.md"],
    )
    return _json({"status": "success", "indexed_count": len(records), "index_path": str((WIKI_DIR / "index.md").resolve())})


def append_wiki_log_event(
    event_type: str,
    title: str,
    summary: str = "",
    links: list[str] | None = None,
    evidence_paths: list[str] | None = None,
    actor: str = "agent",
    occurred_at: str = "",
) -> str:
    """Append a parseable event to `wiki/log.md`."""
    _ensure_dirs()
    log_path = WIKI_DIR / "log.md"
    if not log_path.exists():
        log_path.write_text(_log_initial_markdown(), encoding="utf-8")
    timestamp = occurred_at or _now()
    link_lines = [f"- Link: `{link}`" for link in links or []]
    evidence_lines = [f"- Evidence: `{path}`" for path in evidence_paths or []]
    block = [
        "",
        f"## [{timestamp[:10]}] {event_type} | {title}",
        "",
        f"- Time: `{timestamp}`",
        f"- Actor: `{actor}`",
    ]
    if summary:
        block.append(f"- Summary: {summary}")
    block.extend(link_lines)
    block.extend(evidence_lines)
    with log_path.open("a", encoding="utf-8") as file:
        file.write("\n".join(block).rstrip() + "\n")
    return _json({"status": "success", "log_path": str(log_path.resolve()), "event_type": event_type, "title": title})


def _indexed_targets(index_text: str) -> set[str]:
    return {match.group(1).strip() for match in re.finditer(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", index_text)}


def _wikilinks(text: str) -> set[str]:
    return {match.group(1).strip() for match in re.finditer(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", text)}


def _normalize_link_target(target: str) -> str:
    normalized = target.split("#", 1)[0].strip()
    if normalized and not normalized.endswith(".md"):
        normalized = f"{normalized}.md"
    return normalized


def lint_wiki_knowledge_base() -> str:
    """Run a lightweight wiki lint pass for P15 knowledge health."""
    _ensure_dirs()
    pages = [_page_record(path) for path in _markdown_files()]
    page_paths = {record["path"] for record in pages}
    content_by_path = {record["path"]: _read_text(WIKI_DIR / record["path"]) for record in pages}
    index_text = _read_text(WIKI_DIR / "index.md") if (WIKI_DIR / "index.md").exists() else ""
    indexed = {_normalize_link_target(target) for target in _indexed_targets(index_text)}
    inbound: dict[str, int] = {path: 0 for path in page_paths}
    unresolved_links: set[str] = set()
    for text in content_by_path.values():
        for target in _wikilinks(text):
            normalized = _normalize_link_target(target)
            if normalized in inbound:
                inbound[normalized] += 1
            elif normalized:
                unresolved_links.add(normalized)
    core_pages = {"index.md", "log.md", "AGENTS.md"}
    missing_frontmatter = [page for page in pages if page["path"] not in core_pages and not page["has_frontmatter"]]
    unsourced_claims = [
        page
        for page in pages
        if page["type"] in {"claim", "decision"} and not page["has_evidence"]
    ]
    orphan_pages = [
        page
        for page in pages
        if page["path"] not in core_pages and inbound.get(page["path"], 0) == 0
    ]
    missing_index = [
        page
        for page in pages
        if page["path"] != "index.md" and page["path"] not in indexed
    ]
    stale_claims = [page for page in pages if page["type"] == "claim" and page["status"] == "stale"]
    contradicted_claims = [page for page in pages if page["type"] == "claim" and page["status"] == "contradicted"]
    warnings = []
    if not (DOCS_DIR / "wiki_schema.md").exists():
        warnings.append("docs/wiki_schema.md is missing.")
    if not (WIKI_DIR / "index.md").exists():
        warnings.append("wiki/index.md is missing.")
    if not (WIKI_DIR / "log.md").exists():
        warnings.append("wiki/log.md is missing.")
    if missing_frontmatter:
        warnings.append(f"{len(missing_frontmatter)} wiki pages are missing frontmatter.")
    if unsourced_claims:
        warnings.append(f"{len(unsourced_claims)} decision/claim pages have no evidence.")
    if missing_index:
        warnings.append(f"{len(missing_index)} wiki pages are not listed in index.md.")
    if unresolved_links:
        warnings.append(f"{len(unresolved_links)} wikilinks point to missing pages.")
    if contradicted_claims:
        warnings.append(f"{len(contradicted_claims)} claims are contradicted.")
    status = "success" if not warnings and not stale_claims else "warning"
    review_questions = generate_wiki_review_questions_from_counts(
        {
            "missing_frontmatter_count": len(missing_frontmatter),
            "unsourced_claim_count": len(unsourced_claims),
            "orphan_count": len(orphan_pages),
            "missing_index_count": len(missing_index),
            "unresolved_link_count": len(unresolved_links),
            "stale_claim_count": len(stale_claims),
            "contradicted_claim_count": len(contradicted_claims),
        }
    )
    payload = {
        "status": status,
        "schema": "a2a_wiki_knowledge_health_v1",
        "checked_at": _now(),
        "wiki_dir": str(WIKI_DIR),
        "schema_present": (DOCS_DIR / "wiki_schema.md").exists(),
        "index_present": (WIKI_DIR / "index.md").exists(),
        "log_present": (WIKI_DIR / "log.md").exists(),
        "page_count": len(pages),
        "indexed_count": len(indexed),
        "missing_frontmatter_count": len(missing_frontmatter),
        "unsourced_claim_count": len(unsourced_claims),
        "orphan_count": len(orphan_pages),
        "missing_index_count": len(missing_index),
        "unresolved_link_count": len(unresolved_links),
        "stale_claim_count": len(stale_claims),
        "contradicted_claim_count": len(contradicted_claims),
        "warnings": warnings,
        "review_questions": review_questions,
        "examples": {
            "missing_frontmatter": [page["path"] for page in missing_frontmatter[:8]],
            "unsourced_claims": [page["path"] for page in unsourced_claims[:8]],
            "orphans": [page["path"] for page in orphan_pages[:8]],
            "missing_index": [page["path"] for page in missing_index[:8]],
            "unresolved_links": sorted(unresolved_links)[:8],
        },
    }
    atomic_write_json(HEALTH_PATH, payload)
    return _json(payload)


def generate_wiki_review_questions_from_counts(counts: dict[str, int]) -> list[str]:
    questions = ["知识库复盘问题：本周新增结论是否都能追溯到 DuckDB、ERP 或 wiki 证据？"]
    if counts.get("unsourced_claim_count", 0) > 0:
        questions.append("哪些 decision/claim 页面还缺少 evidence、row_count、查询时间或数据源？")
    if counts.get("orphan_count", 0) > 0:
        questions.append("哪些孤立页面应该链接到品牌、SKU、渠道、仓库或供应商实体页？")
    if counts.get("missing_index_count", 0) > 0:
        questions.append("是否需要刷新 wiki/index.md，让 Agent 查询前能发现最新页面？")
    if counts.get("stale_claim_count", 0) or counts.get("contradicted_claim_count", 0):
        questions.append("哪些过期或被推翻的 claim 需要更新经营建议或通知 PM？")
    if counts.get("missing_frontmatter_count", 0) > 0:
        questions.append("哪些旧 wiki 页面需要补 type、updated_at、source 和 evidence frontmatter？")
    return questions[:12]


def generate_wiki_review_questions() -> str:
    """Return follow-up questions produced from the latest wiki lint state."""
    health = json.loads(lint_wiki_knowledge_base())
    return _json({"status": "success", "questions": health["review_questions"], "checked_at": health["checked_at"]})


def _yaml_list(key: str, values: list[str]) -> list[str]:
    if not values:
        return [f"{key}: []"]
    return [f"{key}:"] + [f"  - {value}" for value in values]


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        clean = value.strip().strip("`").strip().rstrip(".,;，；)")
        if clean and clean not in seen:
            unique.append(clean)
            seen.add(clean)
    return unique


def _normalize_evidence_path(raw_value: str) -> str:
    value = raw_value.strip().strip("`").strip().rstrip(".,;，；)")
    if not value:
        return ""
    value = value.replace("\\", "/")
    project_root = PROJECT_ROOT.as_posix()
    if value.startswith(project_root + "/"):
        value = value[len(project_root) + 1 :]
    else:
        for marker in ("/data/", "/raw/", "/wiki/", "/docs/", "/config/"):
            if marker in value:
                value = value[value.index(marker) + 1 :]
                break
    if value.startswith("warehouse/"):
        value = f"data/{value}"
    if value.startswith(".obsidian/"):
        value = f"wiki/{value}"
    if re.search(r"\.(xlsx|xls|csv|json|md|pdf|docx|pptx|xmind)$", value, re.I):
        if "/" not in value and not value.startswith(("raw/", "data/", "wiki/", "docs/", "config/")):
            value = f"raw/{value}"
    if value.startswith(("raw/", "data/", "wiki/", "docs/", "config/")):
        return value
    return ""


def _extract_wiki_evidence_paths(text: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", text):
        target = match.group(1).split("#", 1)[0].strip()
        if target:
            if not target.endswith(".md"):
                target = f"{target}.md"
            candidates.append(f"wiki/{target}")
    for match in re.finditer(r"`([^`]+)`", text):
        candidates.append(match.group(1))
    for match in re.finditer(r"Task ID:\s*`?([^`\n]+)`?", text):
        task_id = match.group(1).strip()
        if task_id:
            candidates.append(f"data/tasks/{task_id}.json")
    for line in text.splitlines():
        if re.search(r"\b(Evidence|Report|Raw|Source file|Manifest|Quality report|DuckDB)\b", line, re.I):
            for piece in re.split(r"[,，]\s*", line):
                candidates.append(piece.split(":", 1)[-1].strip())
    normalized = [_normalize_evidence_path(candidate) for candidate in candidates]
    return _ordered_unique([candidate for candidate in normalized if candidate])[:16]


def _format_frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.extend(_yaml_list(key, [str(item) for item in value]))
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _frontmatter_bounds(text: str) -> tuple[int, int] | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    return 0, end + 4


def _merge_frontmatter(text: str, additions: dict[str, Any]) -> str:
    bounds = _frontmatter_bounds(text)
    if bounds is None:
        return f"{_format_frontmatter(additions)}\n\n{text.lstrip()}"
    start, end = bounds
    frontmatter = text[start:end]
    parsed = _parse_frontmatter(text)
    insertions: list[str] = []
    for key, value in additions.items():
        if key == "evidence":
            if _as_list(parsed.get("evidence")):
                continue
            insertions.extend(_yaml_list(key, [str(item) for item in value]))
            continue
        if str(parsed.get(key) or "").strip():
            continue
        insertions.append(f"{key}: {value}")
    if not insertions:
        return text
    return f"{frontmatter.rstrip()}\n" + "\n".join(insertions) + text[end:]


def normalize_legacy_wiki_pages(dry_run: bool = True) -> str:
    """Backfill P15 frontmatter/evidence metadata for legacy wiki pages."""
    _ensure_dirs()
    candidates: list[dict[str, Any]] = []
    updated_count = 0
    for path in _markdown_files():
        rel_path = _relative_wiki_path(path)
        if rel_path in {"index.md", "log.md", "AGENTS.md"}:
            continue
        text = _read_text(path)
        frontmatter = _parse_frontmatter(text)
        page_type = _infer_page_type(rel_path, frontmatter)
        has_frontmatter = bool(frontmatter)
        has_evidence = _has_evidence(text, frontmatter)
        needs_frontmatter = not has_frontmatter
        needs_evidence = page_type in {"claim", "decision"} and not has_evidence
        if not needs_frontmatter and not needs_evidence:
            continue
        evidence = _extract_wiki_evidence_paths(text)
        updated_at = str(
            frontmatter.get("updated_at")
            or datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")
        )
        additions: dict[str, Any] = {
            "type": page_type,
            "updated_at": updated_at,
            "status": str(frontmatter.get("status") or "current"),
            "source_boundary": "legacy_wiki_backfill",
        }
        if evidence:
            additions["source"] = evidence[0]
            additions["evidence"] = evidence
        elif needs_frontmatter and page_type not in {"claim", "decision"}:
            additions["source"] = "legacy_wiki_backfill"
        candidates.append(
            {
                "path": rel_path,
                "type": page_type,
                "needs_frontmatter": needs_frontmatter,
                "needs_evidence": needs_evidence,
                "evidence_count": len(evidence),
                "evidence": evidence[:6],
            }
        )
        if dry_run:
            continue
        next_text = _merge_frontmatter(text, additions)
        if next_text != text:
            path.write_text(next_text.rstrip() + "\n", encoding="utf-8")
            updated_count += 1
    if not dry_run:
        refresh_wiki_index()
        append_wiki_log_event(
            event_type="lint",
            title="Legacy wiki pages normalized",
            summary=f"Backfilled P15 metadata for {updated_count} legacy wiki pages.",
            links=["wiki/index.md", "data/wiki_knowledge_health.json"],
        )
        lint_wiki_knowledge_base()
    return _json(
        {
            "status": "success",
            "dry_run": dry_run,
            "candidate_count": len(candidates),
            "updated_count": updated_count,
            "remaining_without_evidence": [
                item["path"]
                for item in candidates
                if item["needs_evidence"] and item["evidence_count"] == 0
            ],
            "examples": candidates[:12],
        }
    )


def register_wiki_claim_evidence(
    claim: str,
    evidence_paths: list[str] | None = None,
    data_source: str = "wiki",
    status: str = "current",
    query_time: str = "",
    row_count: int = 0,
    filters: dict[str, Any] | None = None,
    object_refs: list[str] | None = None,
) -> str:
    """Write an atomic claim page with evidence and lifecycle metadata."""
    _ensure_dirs()
    safe_status = status if status in {"current", "stale", "contradicted"} else "current"
    slug = _slugify(claim, "claim")
    rel_path = f"claims/{slug}.md"
    path = _safe_under(WIKI_DIR / rel_path, WIKI_DIR)
    source_boundary = "live_read_only_fallback" if data_source == "ERP_live_readonly" else "registered_or_wiki_fact"
    evidence = evidence_paths or []
    refs = object_refs or []
    now = _now()
    lines = [
        "---",
        "type: claim",
        f"updated_at: {now}",
        f"status: {safe_status}",
        f"data_source: {data_source}",
        f"source_boundary: {source_boundary}",
        f"query_time: {query_time or now}",
        f"row_count: {int(row_count or 0)}",
        *_yaml_list("evidence", evidence),
        *_yaml_list("object_refs", refs),
        "---",
        "",
        f"# {claim}",
        "",
        "## Claim",
        "",
        claim,
        "",
        "## Evidence",
        "",
    ]
    lines.extend([f"- `{item}`" for item in evidence] or ["- Evidence pending."])
    lines.extend(["", "## Query Context", "", f"- Data source: `{data_source}`", f"- Source boundary: `{source_boundary}`", f"- Query time: `{query_time or now}`", f"- Row count: `{int(row_count or 0)}`"])
    if filters:
        lines.extend(["- Filters:", "```json", json.dumps(filters, ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    append_wiki_log_event("claim", claim, summary=f"Claim registered with {len(evidence)} evidence paths.", links=[f"wiki/{rel_path}"], evidence_paths=evidence)
    refresh_wiki_index()
    return _json({"status": "success", "wiki_path": f"wiki/{rel_path}", "saved_to": str(path.resolve())})


def archive_decision_to_wiki(
    title: str,
    content: str,
    evidence_paths: list[str] | None = None,
    source_query: str = "",
    decision_type: str = "decision",
    live_snapshot: bool = False,
    query_time: str = "",
    row_count: int = 0,
    filters: dict[str, Any] | None = None,
) -> str:
    """Archive a high-value answer or decision report into `wiki/decisions`."""
    _ensure_dirs()
    now = _now()
    slug = _slugify(title, "decision")
    rel_path = f"decisions/{now[:10].replace('-', '')}-{slug}.md"
    path = _safe_under(WIKI_DIR / rel_path, WIKI_DIR)
    evidence = evidence_paths or []
    source_boundary = "live_read_only_fallback" if live_snapshot else "registered_or_wiki_fact"
    lines = [
        "---",
        "type: decision",
        f"decision_type: {decision_type}",
        f"updated_at: {now}",
        f"source_boundary: {source_boundary}",
        f"query_time: {query_time or now}",
        f"row_count: {int(row_count or 0)}",
        *_yaml_list("evidence", evidence),
        "---",
        "",
        f"# {title}",
        "",
    ]
    if source_query:
        lines.extend(["## Source Query", "", source_query, ""])
    lines.extend(["## Decision Content", "", content.strip(), "", "## Evidence", ""])
    lines.extend([f"- `{item}`" for item in evidence] or ["- Evidence pending."])
    lines.extend(["", "## Archive Boundary", "", f"- Source boundary: `{source_boundary}`", f"- Query time: `{query_time or now}`", f"- Row count: `{int(row_count or 0)}`"])
    if filters:
        lines.extend(["- Filters:", "```json", json.dumps(filters, ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    append_wiki_log_event("decision", title, summary=f"Archived decision with {len(evidence)} evidence paths.", links=[f"wiki/{rel_path}"], evidence_paths=evidence)
    refresh_wiki_index()
    return _json({"status": "success", "wiki_path": f"wiki/{rel_path}", "saved_to": str(path.resolve())})
