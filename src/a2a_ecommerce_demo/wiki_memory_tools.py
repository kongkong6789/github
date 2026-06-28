from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
CLEANED_DIR = Path(os.getenv("A2A_CLEANED_DIR", DATA_DIR / "cleaned")).resolve()
WIKI_DIR = Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).resolve()


def _ensure_dirs() -> None:
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    (WIKI_DIR / "data-dictionary").mkdir(parents=True, exist_ok=True)
    (WIKI_DIR / "cleaning-rules").mkdir(parents=True, exist_ok=True)


def _safe_under(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if root not in [resolved, *resolved.parents]:
        raise ValueError(f"Refusing to access outside {root}: {resolved}")
    return resolved


def _slugify(value: str, fallback: str = "note") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", value).strip("-")
    return slug[:80] or fallback


def _cleaned_files() -> list[Path]:
    _ensure_dirs()
    return sorted(
        path
        for path in CLEANED_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".tsv"}
    )


def _sample_csv(path: Path, max_rows: int = 200) -> tuple[list[str], list[dict[str, str]], int]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=delimiter)
        rows = []
        for index, row in enumerate(reader):
            if index < max_rows:
                rows.append({str(key): str(value or "") for key, value in row.items()})
        headers = list(reader.fieldnames or [])
    total_rows = sum(1 for _ in path.open("r", encoding="utf-8-sig", errors="ignore")) - 1
    return headers, rows, max(total_rows, 0)


def _infer_semantic_type(field: str, samples: list[str]) -> str:
    lowered = field.lower()
    if any(token in lowered for token in ["sku", "asin", "msku", "id", "编码", "货品id", "条码", "code"]):
        return "identifier_text"
    if any(token in lowered for token in ["date", "日期", "月份", "账期"]):
        return "date"
    if any(token in lowered for token in ["库存", "期末", "期初", "入库", "出库", "销量", "数量", "在途"]):
        return "quantity"
    if any(token in lowered for token in ["金额", "收入", "成本", "利润", "现金", "售价", "价格", "花费"]):
        return "money"
    numeric_count = 0
    for sample in samples:
        try:
            float(str(sample).replace(",", "").replace("%", ""))
            numeric_count += 1
        except ValueError:
            pass
    if samples and numeric_count / len(samples) >= 0.8:
        return "number"
    return "text"


def _field_profile(field: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    values = [row.get(field, "") for row in rows]
    non_empty = [value for value in values if value not in {"", None}]
    unique_examples = []
    for value in non_empty:
        if value not in unique_examples:
            unique_examples.append(value)
        if len(unique_examples) >= 5:
            break
    return {
        "field": field,
        "semantic_type": _infer_semantic_type(field, non_empty[:50]),
        "sample_values": unique_examples,
        "empty_rate_in_sample": round(1 - (len(non_empty) / len(values)), 4) if values else 0,
    }


def generate_data_dictionary(file_path: str = "") -> str:
    """根据 data/cleaned 中的 CSV/TSV 自动生成 Obsidian 字段字典页面。"""
    _ensure_dirs()
    targets = [_safe_under(CLEANED_DIR / file_path, CLEANED_DIR)] if file_path else _cleaned_files()
    results = []
    for target in targets:
        if not target.exists() or target.suffix.lower() not in {".csv", ".tsv"}:
            continue
        headers, rows, total_rows = _sample_csv(target)
        profiles = [_field_profile(field, rows) for field in headers]
        title = f"字段字典 - {target.stem}"
        wiki_path = _safe_under(WIKI_DIR / "data-dictionary" / f"{_slugify(target.stem)}.md", WIKI_DIR)
        rel_data = str(target.relative_to(DATA_DIR)).replace("\\", "/")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "---",
            "type: data-dictionary",
            f"source: {rel_data}",
            f"generated_at: {generated_at}",
            "tags:",
            "  - data-dictionary",
            "---",
            "",
            f"# {title}",
            "",
            "## Source",
            "",
            f"- Cleaned file: `{rel_data}`",
            f"- Rows: {total_rows}",
            f"- Columns: {len(headers)}",
            "",
            "## Fields",
            "",
        ]
        for profile in profiles:
            examples = ", ".join(f"`{value}`" for value in profile["sample_values"]) or "无样例"
            lines.extend(
                [
                    f"### {profile['field']}",
                    "",
                    f"- Type: `{profile['semantic_type']}`",
                    f"- Empty rate in sample: {profile['empty_rate_in_sample']}",
                    f"- Examples: {examples}",
                    "",
                ]
            )
        wiki_path.write_text("\n".join(lines), encoding="utf-8")
        results.append({"source": rel_data, "wiki_path": str(wiki_path.relative_to(WIKI_DIR)).replace("\\", "/"), "fields": len(headers), "rows": total_rows})
    return json.dumps({"generated": results}, ensure_ascii=False, indent=2)


def generate_cleaning_rules(file_path: str = "") -> str:
    """根据 data/cleaned 中的 CSV/TSV 自动生成 Obsidian 清洗规则页面。"""
    _ensure_dirs()
    targets = [_safe_under(CLEANED_DIR / file_path, CLEANED_DIR)] if file_path else _cleaned_files()
    results = []
    for target in targets:
        if not target.exists() or target.suffix.lower() not in {".csv", ".tsv"}:
            continue
        headers, rows, total_rows = _sample_csv(target)
        profiles = [_field_profile(field, rows) for field in headers]
        id_fields = [profile["field"] for profile in profiles if profile["semantic_type"] == "identifier_text"]
        quantity_fields = [profile["field"] for profile in profiles if profile["semantic_type"] == "quantity"]
        date_fields = [profile["field"] for profile in profiles if profile["semantic_type"] == "date"]
        title = f"清洗规则 - {target.stem}"
        wiki_path = _safe_under(WIKI_DIR / "cleaning-rules" / f"{_slugify(target.stem)}.md", WIKI_DIR)
        rel_data = str(target.relative_to(DATA_DIR)).replace("\\", "/")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "---",
            "type: cleaning-rule",
            f"source: {rel_data}",
            f"generated_at: {generated_at}",
            "tags:",
            "  - cleaning-rule",
            "---",
            "",
            f"# {title}",
            "",
            "## Source",
            "",
            f"- Cleaned file: `{rel_data}`",
            f"- Rows: {total_rows}",
            f"- Columns: {len(headers)}",
            "",
            "## Rules",
            "",
            "- 保留原始 raw 文件，不覆盖源文件。",
            "- ID、SKU、ASIN、货品编码、条码类字段必须按文本处理，避免变成科学计数法或浮点数。",
            "- 金额、库存、销量、出库、入库、在途字段可按数值分析，但要保留负数业务含义。",
            "- 如果源 Excel 超过 100MB，先拆分或导出 CSV，再进入交互式清洗。",
            "- 公司级决策前必须先运行数据质量门，标注缺失字段和置信度。",
            "",
            "## Detected Field Groups",
            "",
            f"- Identifier fields: {', '.join(id_fields) or '未识别'}",
            f"- Date fields: {', '.join(date_fields) or '未识别'}",
            f"- Quantity fields: {', '.join(quantity_fields[:30]) or '未识别'}",
            "",
            "## Follow-up",
            "",
            "- 如果表头识别错误，重新指定 header_row 清洗。",
            "- 如果字段含义不清，补充到 data-dictionary 页面。",
            "- 如果同一字段存在多个名称，建立字段映射规则。",
        ]
        wiki_path.write_text("\n".join(lines), encoding="utf-8")
        results.append({"source": rel_data, "wiki_path": str(wiki_path.relative_to(WIKI_DIR)).replace("\\", "/"), "fields": len(headers), "rows": total_rows})
    return json.dumps({"generated": results}, ensure_ascii=False, indent=2)
