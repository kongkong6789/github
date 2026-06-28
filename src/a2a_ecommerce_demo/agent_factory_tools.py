from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
WIKI_DIR = Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).resolve()
TEMPLATE_DIR = Path(os.getenv("A2A_AGENT_TEMPLATE_DIR", DATA_DIR / "agent_templates")).resolve()

TEMPLATE_LIBRARY: dict[str, dict[str, Any]] = {
    "excel_cleaning": {
        "role": "复杂 Excel 数据清洗 Agent",
        "goal": "识别表头、合并单元格、空行空列、公式风险，并输出 cleaned CSV 与清洗报告。",
        "tools": ["profile_excel_file", "clean_excel_to_csv", "write_cleaning_report", "generate_cleaning_rules"],
        "output_schema": ["cleaned_files", "detected_headers", "quality_warnings", "manual_questions"],
    },
    "wiki_ingest": {
        "role": "Obsidian 知识入库 Agent",
        "goal": "把 raw 资料转成可检索、可引用、可复盘的 Obsidian wiki 页面。",
        "tools": ["list_raw_files", "ingest_raw_file", "ingest_all_raw_files", "rebuild_lightrag_index", "diagnose_lightrag_failures", "list_failed_lightrag_docs", "retry_failed_lightrag_docs"],
        "output_schema": ["generated_pages", "source_files", "entities", "open_questions"],
    },
    "inventory_decision": {
        "role": "库存辅助决策 Agent",
        "goal": "判断断货、积压、补货数量、安全库存和采购节奏。",
        "tools": ["query_inventory_history", "query_sales_history", "query_sku_snapshot", "analyze_restock_decision", "simulate_decision_scenarios", "query_lightrag"],
        "output_schema": ["decision", "evidence", "scenarios", "risks", "next_actions"],
    },
    "financial_planning": {
        "role": "公司级财务规划 Agent",
        "goal": "分析现金流、库存占用、广告支出、收入成本和采购资金压力。",
        "tools": ["assess_data_quality", "list_fact_tables", "query_finance_history", "query_ads_history", "plan_fact_query", "query_fact_layer", "analyze_company_financial_position", "query_lightrag"],
        "output_schema": ["financial_snapshot", "cash_risks", "missing_data", "actions"],
    },
    "company_strategy": {
        "role": "公司经营策略 Agent",
        "goal": "综合产品、库存、财务、广告、供应商、历史决策，给出公司级辅助决策。",
        "tools": ["assess_data_quality", "list_registered_datasets", "list_fact_tables", "query_fact_layer", "analyze_company_strategy", "query_lightrag", "save_decision_report"],
        "output_schema": ["conclusion", "evidence_chain", "priorities", "risks", "human_confirmation"],
    },
    "risk_review": {
        "role": "风险审查 Agent",
        "goal": "反驳方案，检查数据缺失、现金流、合规、库存积压和执行风险。",
        "tools": ["assess_data_quality", "assess_decision_risks", "query_lightrag"],
        "output_schema": ["risk_level", "blocked_items", "low_confidence_claims", "mitigations"],
    },
}


def _ensure_dir() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(value: str, fallback: str = "agent-template") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", value).strip("-")
    return slug[:80] or fallback


def _resolve_wiki_path(path: str) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        resolved = raw.resolve()
    elif raw.parts and raw.parts[0] == "wiki":
        resolved = (WIKI_DIR / Path(*raw.parts[1:])).resolve()
    else:
        resolved = (WIKI_DIR / raw).resolve()
    if WIKI_DIR not in [resolved, *resolved.parents]:
        raise ValueError(f"Refusing to read outside wiki directory: {resolved}")
    return resolved


def _relative_wiki_path(path: Path) -> str:
    try:
        return f"wiki/{path.resolve().relative_to(WIKI_DIR).as_posix()}"
    except ValueError:
        return path.as_posix()


def suggest_agent_team(task_description: str) -> str:
    """根据任务内容自动建议临时 Agent 团队、工具范围和输出格式。"""
    text = task_description.lower()
    selected = []
    rules = [
        ("excel_cleaning", ["excel", "xlsx", "表格", "清洗", "字段", "表头", "乱表"]),
        ("wiki_ingest", ["obsidian", "wiki", "知识库", "入库", "资料", "raw"]),
        ("inventory_decision", ["库存", "补货", "断货", "出库", "sku"]),
        ("financial_planning", ["财务", "现金", "利润", "毛利", "成本", "预算"]),
        ("company_strategy", ["公司", "经营", "战略", "辅助决策", "老板", "优先级"]),
        ("risk_review", ["风险", "审查", "合规", "不确定", "缺失"]),
    ]
    for key, keywords in rules:
        if any(keyword in text for keyword in keywords):
            selected.append(key)
    if not selected:
        selected = ["wiki_ingest", "company_strategy", "risk_review"]
    if "company_strategy" in selected and "risk_review" not in selected:
        selected.append("risk_review")

    agents = [{**TEMPLATE_LIBRARY[key], "template_id": key} for key in dict.fromkeys(selected)]
    return json.dumps(
        {
            "task": task_description,
            "recommended_agents": agents,
            "handoff_contract": {
                "input": ["task_id", "task_description", "authorized_paths", "evidence_paths"],
                "output": ["status", "summary", "evidence", "risks", "missing_data", "next_actions"],
                "rule": "临时 Agent 只返回结构化结果，不把大量原文塞回主上下文。",
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def save_agent_skill_template(template_id: str, notes: str = "") -> str:
    """把推荐的 Agent 模板保存为可复用 skill/prompt 草稿。"""
    _ensure_dir()
    if template_id not in TEMPLATE_LIBRARY:
        raise ValueError(f"Unknown template_id: {template_id}. Available: {', '.join(TEMPLATE_LIBRARY)}")
    template = TEMPLATE_LIBRARY[template_id]
    content = {
        "template_id": template_id,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "template": template,
        "notes": notes,
        "prompt": (
            f"你是{template['role']}。目标：{template['goal']}\n"
            f"允许工具：{', '.join(template['tools'])}\n"
            f"输出字段：{', '.join(template['output_schema'])}\n"
            "必须说明证据来源；数据不足时必须列出缺口；高风险动作必须要求人工确认。"
        ),
    }
    path = TEMPLATE_DIR / f"{_slugify(template_id)}.json"
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.dumps({"status": "success", "saved_to": str(path), "template": content}, ensure_ascii=False, indent=2)


def save_wiki_page_as_prompt_template(wiki_path: str, template_id: str = "", notes: str = "", status: str = "draft") -> str:
    """把高复用 wiki 页面保存为 prompt 模板草稿，供后续 Agent/Skill 复用。"""
    _ensure_dir()
    source_path = _resolve_wiki_path(wiki_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Wiki page not found: {wiki_path}")
    content = source_path.read_text(encoding="utf-8", errors="ignore")
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else source_path.stem
    template_key = _slugify(template_id or title, "wiki-prompt-template")
    prompt_body = content.strip()
    if len(prompt_body) > 12000:
        prompt_body = prompt_body[:11800].rstrip() + "\n\n... omitted from prompt template draft ..."
    template = {
        "template_id": template_key,
        "status": status if status in {"draft", "active", "paused"} else "draft",
        "source_wiki_path": _relative_wiki_path(source_path),
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": title,
        "notes": notes,
        "prompt": (
            f"你将复用 wiki 页面《{title}》中的方法和口径。\n"
            "必须保留证据路径；数据不足时列出缺口；高风险动作必须要求人工确认。\n\n"
            f"{prompt_body}"
        ),
    }
    path = TEMPLATE_DIR / f"{template_key}.json"
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.dumps({"status": "success", "saved_to": str(path), "template": template}, ensure_ascii=False, indent=2)


def list_agent_skill_templates() -> str:
    """列出内置和已保存的 Agent/Skill 模板。"""
    _ensure_dir()
    saved = []
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        try:
            saved.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            saved.append({"path": str(path), "error": "invalid json"})
    return json.dumps(
        {
            "built_in": TEMPLATE_LIBRARY,
            "saved_dir": str(TEMPLATE_DIR),
            "saved": saved,
        },
        ensure_ascii=False,
        indent=2,
    )
