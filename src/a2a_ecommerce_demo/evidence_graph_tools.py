from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.a2a_ecommerce_demo.sensitive_data_tools import classify_field_name

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_SCHEMA = "a2a_evidence_graph_v1"
NODE_TYPES = {
    "brand",
    "channel",
    "sku",
    "warehouse",
    "supplier",
    "dataset",
    "mart",
    "wiki_page",
    "report",
    "decision",
    "risk",
    "field",
}
EDGE_TYPES = {
    "derived_from",
    "summarizes",
    "references",
    "affects",
    "belongs_to",
    "has_risk",
    "needs_confirmation",
    "uses_sensitive_field",
}
CHANNEL_KEYWORDS = ["天猫", "淘宝", "抖音", "京东", "拼多多", "唯品会", "小红书", "线下", "外贸", "大贸", "ERP"]
KNOWN_BRANDS = ["UNOVE", "narka", "LABO-H", "Dr.BangGiWon", "AESTURA", "2AST"]
HIGH_RISK_WORDS = ["手机号", "电话", "地址", "身份证", "采购价", "采购单价", "进价", "成本价", "毛利", "利润", "现金流"]
CONFIRMATION_WORDS = ["人工确认", "确认", "大额采购", "融资", "税务", "合同", "外发", "真实订单", "采购"]


@dataclass
class EvidenceGraphNode:
    id: str
    type: str
    label: str
    source_path: str
    summary: str
    risk_level: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceGraphEdge:
    id: str
    type: str
    source: str
    target: str
    label: str
    source_path: str
    summary: str
    risk_level: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _data_dir() -> Path:
    return Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()


def _wiki_dir() -> Path:
    return Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).resolve()


def _task_dir() -> Path:
    return Path(os.getenv("A2A_TASK_DIR", _data_dir() / "tasks")).resolve()


def _registry_path() -> Path:
    return Path(os.getenv("A2A_DATASET_REGISTRY", _data_dir() / "warehouse" / "dataset_registry.json")).resolve()


def _audit_path() -> Path:
    return Path(os.getenv("A2A_AUDIT_LOG", _data_dir() / "audit" / "events.jsonl")).resolve()


def _reports_dir() -> Path:
    return _data_dir() / "reports"


def _lightrag_index_path() -> Path:
    return _data_dir() / "lightrag" / "index.json"


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _safe_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _short_hash(text: str) -> str:
    import hashlib

    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _slug(value: str) -> str:
    normalized = re.sub(r"\s+", "-", value.strip())
    normalized = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_.:/\\-]+", "-", normalized).strip("-")
    return normalized[:96] or _short_hash(value)


def _node_id(node_type: str, key: str) -> str:
    return f"{node_type}:{_slug(key).lower()}"


def _edge_id(edge_type: str, source: str, target: str) -> str:
    return f"{edge_type}:{source}->{target}"


def _redact_sensitive_text(value: str, fallback: str = "Sensitive evidence") -> str:
    text = _safe_text(value)
    if not text:
        return ""
    text = re.sub(r"1[3-9]\d{9}", "***REDACTED_PHONE***", text)
    text = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "***REDACTED_EMAIL***", text)
    text = re.sub(r"(身份证|id_card|ID)[：:=]?\s*[0-9Xx]{8,}", r"\1: ***REDACTED_ID***", text, flags=re.IGNORECASE)
    text = re.sub(r"(地址|收货地址)[：:=]?\s*[^,，;；\n]{4,}", r"\1: ***REDACTED_ADDRESS***", text)
    text = re.sub(r"(采购价|采购单价|进价|成本价|供应商报价)[：:=]?\s*\d+(?:\.\d+)?", r"\1: ***REDACTED_PRICE***", text)
    if any(token in text for token in ["***REDACTED_PHONE***", "***REDACTED_ADDRESS***", "***REDACTED_PRICE***"]):
        return text if len(text) <= 120 else fallback
    return text[:160]


def _risk_level_from_text(text: str) -> str:
    if any(word in text for word in ["手机号", "地址", "身份证"]):
        return "high"
    if any(word in text for word in ["采购价", "采购单价", "进价", "成本价", "毛利", "利润", "现金流"]):
        return "medium"
    if any(word in text for word in ["风险", "缺失", "失败", "人工确认", "确认"]):
        return "medium"
    return ""


def _path_exists_text(path_value: str) -> str:
    path = Path(path_value)
    if path.is_absolute():
        return str(path)
    return path_value


def _path_to_key(path_value: str) -> str:
    return _path_exists_text(path_value).replace("\\", "/")


class EvidenceGraphBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, EvidenceGraphNode] = {}
        self.edges: dict[str, EvidenceGraphEdge] = {}
        self.warnings: list[str] = []

    def add_node(
        self,
        node_type: str,
        key: str,
        label: str,
        *,
        source_path: str = "",
        summary: str = "",
        risk_level: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if node_type not in NODE_TYPES:
            raise ValueError(f"Unsupported evidence graph node type: {node_type}")
        node_id = _node_id(node_type, key)
        safe_label = _redact_sensitive_text(label, fallback=f"{node_type} evidence") or node_type
        next_node = EvidenceGraphNode(
            id=node_id,
            type=node_type,
            label=safe_label,
            source_path=source_path,
            summary=_redact_sensitive_text(summary),
            risk_level=risk_level or _risk_level_from_text(f"{label} {summary}"),
            metadata=metadata or {},
        )
        existing = self.nodes.get(node_id)
        if existing is None:
            self.nodes[node_id] = next_node
            return node_id
        existing.summary = existing.summary or next_node.summary
        existing.source_path = existing.source_path or next_node.source_path
        existing.risk_level = existing.risk_level or next_node.risk_level
        existing.metadata = {**next_node.metadata, **existing.metadata}
        return node_id

    def add_edge(
        self,
        edge_type: str,
        source: str,
        target: str,
        *,
        label: str = "",
        source_path: str = "",
        summary: str = "",
        risk_level: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if edge_type not in EDGE_TYPES or not source or not target or source == target:
            return
        edge_id = _edge_id(edge_type, source, target)
        if edge_id in self.edges:
            return
        self.edges[edge_id] = EvidenceGraphEdge(
            id=edge_id,
            type=edge_type,
            source=source,
            target=target,
            label=_redact_sensitive_text(label) or edge_type,
            source_path=source_path,
            summary=_redact_sensitive_text(summary),
            risk_level=risk_level or _risk_level_from_text(f"{label} {summary}"),
            metadata=metadata or {},
        )

    def to_payload(
        self,
        *,
        scope: str,
        task_id: str,
        report_path: str,
        node_types: set[str],
        edge_types: set[str],
        limit: int,
    ) -> dict[str, Any]:
        nodes = [node for node in self.nodes.values() if not node_types or node.type in node_types]
        nodes.sort(key=lambda node: (node.type, node.label, node.id))
        truncated = len(nodes) > limit
        limited_nodes = nodes[:limit]
        allowed_ids = {node.id for node in limited_nodes}
        edges = [
            edge
            for edge in self.edges.values()
            if edge.source in allowed_ids
            and edge.target in allowed_ids
            and (not edge_types or edge.type in edge_types)
        ]
        edges.sort(key=lambda edge: (edge.type, edge.source, edge.target))
        return {
            "schema": GRAPH_SCHEMA,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scope": {
                "scope": scope,
                "task_id": task_id,
                "report_path": report_path,
                "limit": limit,
                "node_types": sorted(node_types),
                "edge_types": sorted(edge_types),
            },
            "counts": {
                "nodes": len(limited_nodes),
                "edges": len(edges),
                "total_nodes": len(nodes),
                "total_edges": len(self.edges),
                "truncated": truncated,
            },
            "nodes": [asdict(node) for node in limited_nodes],
            "edges": [asdict(edge) for edge in edges],
            "warnings": self.warnings,
        }


def _parse_types(value: Any, allowed: set[str]) -> set[str]:
    if value is None or value == "":
        return set()
    if isinstance(value, str):
        raw = re.split(r"[,，\s]+", value)
    else:
        raw = [str(item) for item in _safe_list(value)]
    return {item for item in (part.strip() for part in raw) if item in allowed}


def _normalize_limit(limit: Any) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = 300
    return max(1, min(parsed, 1000))


def _values_from_profiles(sheet_view: dict[str, Any], field_name: str) -> list[str]:
    values: list[str] = []
    normalized = field_name.lower()
    for profile in _safe_list(sheet_view.get("field_profiles")):
        record = _safe_record(profile)
        field_text = _safe_text(record.get("field"))
        if normalized not in field_text.lower():
            continue
        values.extend(_safe_text(item) for item in _safe_list(record.get("sample_values")))
    return [value for value in values if value]


def _extract_brands(*texts: str) -> list[str]:
    found: list[str] = []
    haystack = " ".join(texts)
    for brand in KNOWN_BRANDS:
        if brand.lower() in haystack.lower():
            found.append(brand)
    return list(dict.fromkeys(found))


def _extract_channels(*texts: str) -> list[str]:
    haystack = " ".join(texts)
    return [channel for channel in CHANNEL_KEYWORDS if channel.lower() in haystack.lower()]


def _first_safe(values: list[str], fallback: str = "") -> str:
    for value in values:
        text = _safe_text(value)
        if text and text not in {"(全部)", "全部", "未识别"}:
            return text
    return fallback


def _add_dataset_entities(builder: EvidenceGraphBuilder, dataset_id: str, dataset: dict[str, Any]) -> None:
    dataset_slug = _safe_text(dataset.get("dataset_slug")) or dataset_id.split(":", 1)[-1]
    for brand in _extract_brands(dataset_slug, _safe_text(dataset.get("source")), _safe_text(dataset.get("relative_source"))):
        brand_id = builder.add_node("brand", brand, brand, summary=f"Brand mentioned by dataset {dataset_slug}.")
        builder.add_edge("belongs_to", dataset_id, brand_id, label="dataset belongs to brand")
    for channel in _extract_channels(dataset_slug, _safe_text(dataset.get("source")), _safe_text(dataset.get("relative_source"))):
        channel_id = builder.add_node("channel", channel, channel, summary=f"Channel mentioned by dataset {dataset_slug}.")
        builder.add_edge("belongs_to", dataset_id, channel_id, label="dataset belongs to channel")

    for sheet_view in _safe_list(dataset.get("sheet_views")):
        sheet = _safe_record(sheet_view)
        headers = [_safe_text(header) for header in _safe_list(sheet.get("headers"))]
        sheet_text = " ".join([_safe_text(sheet.get("sheet")), *headers])
        for brand in _extract_brands(sheet_text, *_values_from_profiles(sheet, "品牌")):
            brand_id = builder.add_node("brand", brand, brand, source_path=_safe_text(dataset.get("source")))
            builder.add_edge("belongs_to", dataset_id, brand_id, label="dataset belongs to brand")
        for channel in _extract_channels(sheet_text, *_values_from_profiles(sheet, "渠道")):
            channel_id = builder.add_node("channel", channel, channel, source_path=_safe_text(dataset.get("source")))
            builder.add_edge("belongs_to", dataset_id, channel_id, label="dataset belongs to channel")
        sku = _first_safe(
            _values_from_profiles(sheet, "sku")
            + _values_from_profiles(sheet, "SKU")
            + _values_from_profiles(sheet, "商品")
            + [header for header in headers if "sku" in header.lower() or "商品" in header],
        )
        if sku:
            sku_id = builder.add_node("sku", sku, sku, source_path=_safe_text(dataset.get("source")), summary=f"SKU evidence from {dataset_slug}.")
            builder.add_edge("derived_from", sku_id, dataset_id, label="SKU derived from dataset")
            for brand in _extract_brands(sku, dataset_slug):
                brand_id = builder.add_node("brand", brand, brand)
                builder.add_edge("belongs_to", sku_id, brand_id, label="SKU belongs to brand")
        warehouse = _first_safe(_values_from_profiles(sheet, "仓库") + [header for header in headers if "仓" in header or "库存" in header])
        if warehouse:
            warehouse_id = builder.add_node("warehouse", warehouse, warehouse, source_path=_safe_text(dataset.get("source")))
            builder.add_edge("derived_from", warehouse_id, dataset_id, label="warehouse evidence derived from dataset")
        supplier = _first_safe(_values_from_profiles(sheet, "供应商") + [header for header in headers if "供应商" in header or "交期" in header])
        if supplier:
            supplier_id = builder.add_node("supplier", supplier, supplier, source_path=_safe_text(dataset.get("source")), risk_level="medium")
            builder.add_edge("derived_from", supplier_id, dataset_id, label="supplier evidence derived from dataset")
        for header in headers:
            classification = classify_field_name(header)
            if not classification:
                continue
            field_id = builder.add_node(
                "field",
                f"{dataset_slug}:{classification['category']}:{header}",
                f"Sensitive field: {classification['category']}",
                source_path=_safe_text(dataset.get("source")),
                summary=str(classification.get("label") or ""),
                risk_level=str(classification.get("risk_level") or "medium"),
                metadata={"dataset_slug": dataset_slug, "category": classification["category"], "handling": classification["handling"]},
            )
            builder.add_edge("uses_sensitive_field", dataset_id, field_id, label="dataset uses sensitive field", risk_level=str(classification.get("risk_level") or "medium"))


def _add_registry(builder: EvidenceGraphBuilder) -> None:
    registry_path = _registry_path()
    registry = _load_json(registry_path, {})
    datasets = _safe_record(registry).get("datasets", {})
    dataset_items = datasets.items() if isinstance(datasets, dict) else [(str(index), item) for index, item in enumerate(_safe_list(datasets))]
    for key, value in dataset_items:
        dataset = _safe_record(value)
        dataset_slug = _safe_text(dataset.get("dataset_slug")) or str(key)
        dataset_id = builder.add_node(
            "dataset",
            dataset_slug,
            dataset_slug,
            source_path=str(registry_path),
            summary=f"Dataset registered from {_safe_text(dataset.get('relative_source')) or _safe_text(dataset.get('source'))}.",
            metadata={"dataset_slug": dataset_slug, "registered_at": dataset.get("registered_at", "")},
        )
        source_path = _safe_text(dataset.get("source")) or _safe_text(dataset.get("relative_source"))
        if source_path:
            builder.add_edge("derived_from", dataset_id, dataset_id, label="dataset derived from source", source_path=source_path)
        for wiki_kind, wiki_path in _safe_record(dataset.get("wiki_pages")).items():
            wiki_text = _safe_text(wiki_path)
            if not wiki_text:
                continue
            node_type = "decision" if "/decisions/" in wiki_text else "wiki_page"
            wiki_id = builder.add_node(
                node_type,
                wiki_text,
                Path(wiki_text).stem,
                source_path=wiki_text,
                summary=f"{wiki_kind} page for {dataset_slug}.",
                metadata={"dataset_slug": dataset_slug, "wiki_kind": wiki_kind},
            )
            builder.add_edge("summarizes", wiki_id, dataset_id, label="wiki summarizes dataset", source_path=wiki_text)
            builder.add_edge("references", dataset_id, wiki_id, label="dataset references wiki", source_path=str(registry_path))
        for mart in _safe_list(dataset.get("mart_views")):
            mart_record = _safe_record(mart)
            view_name = _safe_text(mart_record.get("view_name"))
            if not view_name:
                continue
            mart_id = builder.add_node(
                "mart",
                view_name,
                view_name,
                source_path=_safe_text(dataset.get("duckdb_path")),
                summary=_safe_text(mart_record.get("category")),
                metadata={"dataset_slug": dataset_slug, "category": mart_record.get("category", ""), "source_view": mart_record.get("source_view", "")},
            )
            builder.add_edge("derived_from", mart_id, dataset_id, label="mart derived from dataset")
            builder.add_edge("references", dataset_id, mart_id, label="dataset references mart")
        _add_dataset_entities(builder, dataset_id, dataset)


def _iter_markdown_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def _relative_or_absolute(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _add_wiki_pages(builder: EvidenceGraphBuilder) -> None:
    wiki_dir = _wiki_dir()
    for path in _iter_markdown_paths(wiki_dir / "datasets"):
        key = _relative_or_absolute(path)
        wiki_id = builder.add_node("wiki_page", key, path.stem, source_path=key, summary="Dataset wiki page.")
        parts = path.relative_to(wiki_dir).parts
        if len(parts) >= 3:
            dataset_id = builder.add_node("dataset", parts[1], parts[1], source_path=str(_registry_path()))
            builder.add_edge("summarizes", wiki_id, dataset_id, label="wiki summarizes dataset", source_path=key)
    for path in _iter_markdown_paths(wiki_dir / "decisions"):
        key = _relative_or_absolute(path)
        decision_id = builder.add_node("decision", key, path.stem, source_path=key, summary="Decision wiki page.", risk_level=_risk_level_from_text(path.stem))
        for brand in _extract_brands(path.stem):
            brand_id = builder.add_node("brand", brand, brand, source_path=key)
            builder.add_edge("affects", decision_id, brand_id, label="decision affects brand", source_path=key)


def _path_mentions(text: str) -> list[str]:
    matches = re.findall(r"`([^`]+)`", text)
    matches.extend(re.findall(r"((?:wiki|data|raw|warehouse)/[^\s,，;；)]+)", text))
    return list(dict.fromkeys(_safe_text(item).strip("。.,，;；") for item in matches if _safe_text(item)))


def _add_report_file(builder: EvidenceGraphBuilder, path: Path) -> str:
    path_text = str(path)
    report_id = builder.add_node("report", path_text, path.stem, source_path=path_text, summary="Decision report.")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        content = ""
    for mentioned in _path_mentions(content):
        lower = mentioned.lower()
        if "wiki/" in lower:
            target_type = "decision" if "/decisions/" in mentioned else "wiki_page"
            target_id = builder.add_node(target_type, mentioned, Path(mentioned).stem, source_path=mentioned, summary="Referenced by report.")
            builder.add_edge("references", report_id, target_id, label="report references wiki", source_path=path_text)
        elif "duckdb" in lower or "mart" in lower or "__" in mentioned:
            target_id = builder.add_node("mart", mentioned, Path(mentioned).name, source_path=mentioned, summary="Referenced fact layer object.")
            builder.add_edge("references", report_id, target_id, label="report references mart", source_path=path_text)
        elif lower.endswith((".json", ".parquet", ".csv")):
            target_id = builder.add_node("dataset", mentioned, Path(mentioned).stem, source_path=mentioned, summary="Referenced dataset artifact.")
            builder.add_edge("references", report_id, target_id, label="report references dataset artifact", source_path=path_text)
    if "Missing data:" in content:
        missing_section = content.split("Missing data:", 1)[1].split("\n", 1)[0]
        for item in re.split(r"[,，、\s]+", missing_section):
            field_name = _safe_text(item.strip("`。.;；"))
            if not field_name or field_name.lower() in {"none", "无"}:
                continue
            field_id = builder.add_node("field", f"gap:{field_name}", f"Data gap: {field_name}", source_path=path_text, summary="Missing data in report.", risk_level="medium")
            builder.add_edge("has_risk", report_id, field_id, label="report has data gap", source_path=path_text, risk_level="medium")
    if any(word in content for word in CONFIRMATION_WORDS):
        risk_id = builder.add_node("risk", f"confirmation:{path_text}", "Needs human confirmation", source_path=path_text, summary="Report contains a human confirmation requirement.", risk_level="medium")
        builder.add_edge("needs_confirmation", report_id, risk_id, label="report needs confirmation", source_path=path_text, risk_level="medium")
    return report_id


def _add_reports(builder: EvidenceGraphBuilder, selected_report: str = "") -> None:
    selected = Path(selected_report).expanduser().resolve() if selected_report else None
    paths = [selected] if selected and selected.exists() else _iter_markdown_paths(_reports_dir())
    for path in paths:
        _add_report_file(builder, path)


def _add_task(builder: EvidenceGraphBuilder, path: Path, task: dict[str, Any]) -> None:
    task_id = _safe_text(task.get("task_id")) or path.stem
    decision_id = builder.add_node(
        "decision",
        f"task:{task_id}",
        task_id,
        source_path=str(path),
        summary=_safe_text(task.get("goal")),
        risk_level=_risk_level_from_text(_safe_text(task.get("goal"))),
        metadata={"task_id": task_id, "status": task.get("status", "")},
    )
    final_report = _safe_record(task.get("final_report"))
    report_path = _safe_text(final_report.get("saved_to"))
    if report_path:
        report_id = builder.add_node("report", report_path, Path(report_path).stem, source_path=report_path, summary="Task final report.")
        builder.add_edge("summarizes", report_id, decision_id, label="report summarizes task decision", source_path=str(path))
        builder.add_edge("references", decision_id, report_id, label="task references report", source_path=str(path))
    evidence_chain = _safe_record(final_report.get("evidence_chain"))
    for wiki_path in _safe_list(evidence_chain.get("wiki_pages")):
        wiki_text = _safe_text(wiki_path)
        if wiki_text:
            wiki_id = builder.add_node("wiki_page", wiki_text, Path(wiki_text).stem, source_path=wiki_text)
            builder.add_edge("references", decision_id, wiki_id, label="task references wiki evidence", source_path=str(path))
    for report_ref in _safe_list(evidence_chain.get("report_paths")):
        report_text = _safe_text(report_ref)
        if report_text:
            report_id = builder.add_node("report", report_text, Path(report_text).stem, source_path=report_text)
            builder.add_edge("references", decision_id, report_id, label="task references report evidence", source_path=str(path))
    for mart in _safe_list(evidence_chain.get("duckdb_marts")):
        mart_name = _safe_text(_safe_record(mart).get("mart"))
        if mart_name:
            mart_id = builder.add_node("mart", mart_name, mart_name, summary="Task evidence mart.")
            builder.add_edge("references", decision_id, mart_id, label="task references mart", source_path=str(path))
    for gap in _safe_list(evidence_chain.get("data_gaps")):
        gap_text = _safe_text(gap)
        if gap_text:
            field_id = builder.add_node("field", f"gap:{gap_text}", f"Data gap: {gap_text}", source_path=str(path), risk_level="medium")
            builder.add_edge("has_risk", decision_id, field_id, label="task has data gap", source_path=str(path), risk_level="medium")
    for step in _safe_list(task.get("steps")):
        step_record = _safe_record(step)
        for evidence in _safe_list(step_record.get("evidence")):
            evidence_path = _safe_text(evidence)
            if not evidence_path:
                continue
            if "wiki/" in evidence_path:
                target_id = builder.add_node("wiki_page", evidence_path, Path(evidence_path).stem, source_path=evidence_path)
            elif evidence_path.endswith(".md") and "report" in evidence_path.lower():
                target_id = builder.add_node("report", evidence_path, Path(evidence_path).stem, source_path=evidence_path)
            else:
                target_id = builder.add_node("dataset", evidence_path, Path(evidence_path).stem, source_path=evidence_path)
            builder.add_edge("references", decision_id, target_id, label="task step references evidence", source_path=str(path), metadata={"step": step_record.get("task", "")})
        for risk in _safe_list(step_record.get("risks")):
            risk_text = _redact_sensitive_text(_safe_text(risk), fallback="Task risk")
            if not risk_text:
                continue
            risk_id = builder.add_node("risk", f"{task_id}:{risk_text}", risk_text, source_path=str(path), summary=_safe_text(step_record.get("summary")), risk_level=_risk_level_from_text(risk_text) or "medium")
            builder.add_edge("has_risk", decision_id, risk_id, label="task has risk", source_path=str(path), risk_level="medium")
            if any(word in risk_text for word in CONFIRMATION_WORDS):
                builder.add_edge("needs_confirmation", decision_id, risk_id, label="task risk needs confirmation", source_path=str(path), risk_level="medium")
    for brand in _extract_brands(_safe_text(task.get("goal"))):
        brand_id = builder.add_node("brand", brand, brand, source_path=str(path))
        builder.add_edge("affects", decision_id, brand_id, label="task affects brand", source_path=str(path))
    for channel in _extract_channels(_safe_text(task.get("goal"))):
        channel_id = builder.add_node("channel", channel, channel, source_path=str(path))
        builder.add_edge("affects", decision_id, channel_id, label="task affects channel", source_path=str(path))


def _add_tasks(builder: EvidenceGraphBuilder, task_id_filter: str = "") -> None:
    task_dir = _task_dir()
    if not task_dir.exists():
        return
    for path in sorted(task_dir.glob("*.json")):
        task = _load_json(path, {})
        if not isinstance(task, dict):
            continue
        task_id = _safe_text(task.get("task_id")) or path.stem
        if task_id_filter and task_id != task_id_filter:
            continue
        _add_task(builder, path, task)


def _add_audit(builder: EvidenceGraphBuilder, task_id_filter: str = "") -> None:
    audit_path = _audit_path()
    try:
        lines = audit_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for index, line in enumerate(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_task_id = _safe_text(event.get("task_id"))
        if task_id_filter and event_task_id != task_id_filter:
            continue
        summary = _safe_text(event.get("summary")) or _safe_text(event.get("event_type"))
        risk_level = _safe_text(event.get("risk_level")) or _risk_level_from_text(summary)
        decision_id = ""
        if event_task_id:
            decision_id = builder.add_node("decision", f"task:{event_task_id}", event_task_id, source_path=str(audit_path), metadata={"task_id": event_task_id})
        for risk_text_raw in _safe_list(event.get("risks")) or ([summary] if risk_level else []):
            risk_text = _redact_sensitive_text(_safe_text(risk_text_raw), fallback="Audit risk")
            if not risk_text:
                continue
            risk_id = builder.add_node("risk", f"audit:{index}:{risk_text}", risk_text, source_path=str(audit_path), summary=summary, risk_level=risk_level or "medium")
            if decision_id:
                builder.add_edge("has_risk", decision_id, risk_id, label="audit risk", source_path=str(audit_path), risk_level=risk_level)
                if any(word in risk_text for word in CONFIRMATION_WORDS):
                    builder.add_edge("needs_confirmation", decision_id, risk_id, label="audit risk needs confirmation", source_path=str(audit_path), risk_level=risk_level)
        metadata = _safe_record(event.get("metadata"))
        fields = [_safe_text(item) for item in _safe_list(metadata.get("fields"))]
        category = _safe_text(metadata.get("category")) or "sensitive"
        if fields or "sensitive" in _safe_text(event.get("event_type")):
            field_id = builder.add_node(
                "field",
                f"audit:{event_task_id or index}:{category}",
                f"Sensitive field: {category}",
                source_path=str(audit_path),
                summary="Audit event recorded sensitive field usage.",
                risk_level=risk_level or "medium",
                metadata={"category": category, "field_count": len(fields)},
            )
            if decision_id:
                builder.add_edge("uses_sensitive_field", decision_id, field_id, label="task uses sensitive field", source_path=str(audit_path), risk_level=risk_level or "medium")
        for path_value in _safe_list(event.get("paths")):
            path_text = _safe_text(path_value)
            if not path_text:
                continue
            if path_text.endswith(".md"):
                target_type = "report" if "/reports/" in path_text else "wiki_page"
                target_id = builder.add_node(target_type, path_text, Path(path_text).stem, source_path=path_text)
            else:
                target_id = builder.add_node("dataset", path_text, Path(path_text).stem, source_path=path_text)
            if decision_id:
                builder.add_edge("references", decision_id, target_id, label="audit references path", source_path=str(audit_path))


def _add_lightrag_index(builder: EvidenceGraphBuilder) -> None:
    index_path = _lightrag_index_path()
    index = _load_json(index_path, {})
    documents = _safe_list(_safe_record(index).get("documents"))
    for document in documents[:300]:
        record = _safe_record(document)
        doc_path = _safe_text(record.get("path"))
        if not doc_path or not doc_path.endswith(".md"):
            continue
        node_type = "decision" if "/decisions/" in doc_path else "wiki_page"
        doc_id = builder.add_node(
            node_type,
            doc_path,
            _safe_text(record.get("title")) or Path(doc_path).stem,
            source_path=doc_path,
            summary="LightRAG indexed reference.",
            metadata={"lightrag_document_id": record.get("id", ""), "kind": record.get("kind", "")},
        )
        for entity in _safe_list(record.get("entities"))[:20]:
            entity_text = _safe_text(entity)
            if not entity_text:
                continue
            if "brand::" in entity_text.lower():
                target_id = builder.add_node("brand", entity_text.split("::", 1)[-1], entity_text.split("::", 1)[-1], source_path=str(index_path))
            elif "sku::" in entity_text.lower() or "product::" in entity_text.lower():
                target_id = builder.add_node("sku", entity_text.split("::", 1)[-1], entity_text.split("::", 1)[-1], source_path=str(index_path))
            else:
                continue
            builder.add_edge("references", doc_id, target_id, label="LightRAG reference entity", source_path=str(index_path))


def _build_graph(scope: str, task_id: str, report_path: str) -> EvidenceGraphBuilder:
    builder = EvidenceGraphBuilder()
    _add_registry(builder)
    _add_wiki_pages(builder)
    _add_lightrag_index(builder)
    _add_reports(builder, selected_report=report_path if scope == "report" else "")
    _add_tasks(builder, task_id_filter=task_id if scope == "task" else "")
    _add_audit(builder, task_id_filter=task_id if scope == "task" else "")
    return builder


def build_evidence_graph(
    scope: str = "global",
    task_id: str = "",
    report_path: str = "",
    limit: int = 300,
    node_types: list[str] | str | None = None,
    edge_types: list[str] | str | None = None,
) -> str:
    """Build a local evidence-navigation graph for datasets, tasks, wiki pages, reports, and audit risks."""
    final_scope = _safe_text(scope) or "global"
    final_task_id = _safe_text(task_id)
    final_report_path = _safe_text(report_path)
    parsed_limit = _normalize_limit(limit)
    parsed_node_types = _parse_types(node_types, NODE_TYPES)
    parsed_edge_types = _parse_types(edge_types, EDGE_TYPES)
    builder = _build_graph(final_scope, final_task_id, final_report_path)
    return _json(
        builder.to_payload(
            scope=final_scope,
            task_id=final_task_id,
            report_path=final_report_path,
            node_types=parsed_node_types,
            edge_types=parsed_edge_types,
            limit=parsed_limit,
        )
    )


def list_evidence_graph_nodes(
    node_types: list[str] | str | None = None,
    scope: str = "global",
    task_id: str = "",
    report_path: str = "",
    limit: int = 300,
) -> str:
    """Return evidence graph nodes with optional type filtering."""
    graph = json.loads(build_evidence_graph(scope=scope, task_id=task_id, report_path=report_path, limit=limit, node_types=node_types))
    return _json(
        {
            "schema": graph["schema"],
            "generated_at": graph["generated_at"],
            "scope": graph["scope"],
            "counts": {"nodes": graph["counts"]["nodes"], "total_nodes": graph["counts"]["total_nodes"], "truncated": graph["counts"]["truncated"]},
            "nodes": graph["nodes"],
            "warnings": graph["warnings"],
        }
    )


def list_evidence_graph_edges(
    edge_types: list[str] | str | None = None,
    scope: str = "global",
    task_id: str = "",
    report_path: str = "",
    limit: int = 300,
) -> str:
    """Return evidence graph edges with optional type filtering."""
    graph = json.loads(build_evidence_graph(scope=scope, task_id=task_id, report_path=report_path, limit=limit, edge_types=edge_types))
    return _json(
        {
            "schema": graph["schema"],
            "generated_at": graph["generated_at"],
            "scope": graph["scope"],
            "counts": {"edges": graph["counts"]["edges"], "total_edges": graph["counts"]["total_edges"], "truncated": graph["counts"]["truncated"]},
            "edges": graph["edges"],
            "warnings": graph["warnings"],
        }
    )
