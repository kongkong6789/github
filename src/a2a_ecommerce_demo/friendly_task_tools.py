from __future__ import annotations

import json
import re
from typing import Any

from src.a2a_ecommerce_demo.task_delegation_tools import start_company_workflow_task

TASK_TEMPLATES: dict[str, dict[str, Any]] = {
    "organize_company_files": {
        "label": "整理公司资料",
        "plain_examples": ["我放了一些资料，帮我整理一下", "把这些文件整理进知识库", "帮我归档公司资料", "我上传了脑图，帮我整理一下"],
        "system_prompt": (
            "请处理 raw 目录里的所有资料：先列出文件，再把资料整理进 Obsidian 知识库，"
            "如果发现 50MB+ Excel，先走离线大表管道生成 profile、分块 CSV、manifest、质量报告，并注册到 DuckDB/Parquet 事实层，"
            "然后同步到完整 LightRAG。完成后告诉我使用了哪些文件、生成了哪些 wiki 页面、"
            "LightRAG 是否同步成功，以及有哪些需要人工确认的问题。"
        ),
        "route": "auto_workflow_agent",
        "expected_steps": ["列出 raw 文件", "大表离线处理", "整理到 Obsidian", "同步 LightRAG", "输出生成页面和风险"],
    },
    "clean_spreadsheets": {
        "label": "清洗表格",
        "plain_examples": ["这些表有点乱，帮我整理成能分析的数据", "帮我清洗表格", "这个 Excel 看不懂，帮我处理"],
        "system_prompt": (
            "请检查 raw 目录里的 Excel/XLSX 表格，识别表头、空行空列、合并单元格、公式和字段风险。"
            "50MB+ 大文件请不要在前端直接完整解析，先走离线大表管道，输出到 data/warehouse/large_excel，"
            "生成 manifest、quality_report 和 Obsidian 摘要；普通表格清洗到 data/cleaned。"
            "最后生成清洗报告、字段字典和需要人工确认的问题。"
        ),
        "route": "data_pipeline_team",
        "expected_steps": ["表格画像", "大表分块/普通表清洗", "生成字段字典", "输出人工确认项"],
    },
    "inventory_risk": {
        "label": "分析库存风险",
        "plain_examples": ["帮我看看库存有没有风险", "哪些货可能断货或积压", "库存要不要补"],
        "system_prompt": (
            "请基于 cleaned 数据、Obsidian 和完整 LightRAG，分析当前库存风险。"
            "默认不要假设只有一个品牌；如果当前资料涉及多个品牌，先识别品牌范围，再决定是否拆开分析。"
            "如果问题涉及全量大表库存、最近 30 天变化、某仓或某 SKU 聚合，请优先查询 DuckDB fact layer。"
            "请先检查数据质量，再输出断货风险、积压风险、补货优先级、现金占用影响、"
            "保守/平衡/激进方案，以及需要补充的数据。"
        ),
        "route": "decision_team",
        "expected_steps": ["数据质量门", "库存分析", "现金占用检查", "风险审查", "输出方案"],
    },
    "company_brain": {
        "label": "公司经营分析",
        "plain_examples": ["帮我做个公司经营分析", "根据这些资料给老板一份建议", "公司现在最应该关注什么", "帮我评估运营渠道展会营销方案"],
        "system_prompt": (
            "请先处理 raw 资料并同步 Obsidian/完整 LightRAG，再基于公司背景、库存、销售、广告、财务、"
            "供应商和历史决策做公司经营辅助决策。大 Excel 先离线分块进入 data/warehouse，并注册到 DuckDB/Parquet 事实层，"
            "默认不要把任何单一品牌当作隐含上下文；如果有多个品牌，要先识别品牌范围，再决定按品牌拆分或跨品牌汇总。"
            "再把高信号摘要页同步进 LightRAG。输出：公司级结论、关键证据、经营问题、"
            "产品线/库存/现金流/广告/供应商风险、行动优先级、数据缺口和人工确认项，并保存报告。"
        ),
        "route": "auto_workflow_agent",
        "expected_steps": ["资料入库", "大表离线处理", "LightRAG 证据检索", "数据质量门", "多 Agent 分析", "保存报告"],
    },
    "sync_lightrag": {
        "label": "同步知识库",
        "plain_examples": ["把知识库更新一下", "同步一下 LightRAG", "我改了 Obsidian，帮我刷新索引"],
        "system_prompt": (
            "请检查完整 LightRAG 服务状态，然后把 Obsidian wiki 里的高信号知识页同步到完整 LightRAG。"
            "完成后告诉我同步了哪些页面、是否有失败文件、track_id 或索引状态，以及下一步能查询什么。"
        ),
        "route": "data_pipeline_team",
        "expected_steps": ["检查 LightRAG", "同步高信号 wiki 页面", "输出状态"],
    },
    "boss_report": {
        "label": "老板决策报告",
        "plain_examples": ["帮我出一份给老板看的报告", "整理成老板能看的建议", "给我一个最终建议"],
        "system_prompt": (
            "请基于当前 Obsidian、完整 LightRAG 和 cleaned 数据生成一份老板可读的辅助决策报告。"
            "默认不要假设只有一个品牌；如果数据涉及多个品牌，要先说明报告覆盖范围。"
            "报告要包含：一句话结论、关键证据、三种方案对比、风险、需要老板拍板的事项、"
            "下一步行动清单。不要输出技术细节，除非它会影响决策可靠性。"
        ),
        "route": "strategy_team",
        "expected_steps": ["检索证据", "形成结论", "方案对比", "风险审查", "保存报告"],
    },
}


KEYWORD_RULES = [
    ("clean_spreadsheets", ["表", "excel", "xlsx", "清洗", "字段", "乱", "看不懂"]),
    ("sync_lightrag", ["同步", "刷新", "light", "索引", "知识库更新"]),
    ("inventory_risk", ["库存", "补货", "断货", "积压", "出库"]),
    ("company_brain", ["经营", "公司", "老板", "战略", "现金流", "财务", "决策", "运营", "渠道", "展会", "营销", "脑图", "xmind"]),
    ("boss_report", ["报告", "建议书", "给老板", "最终建议"]),
    ("organize_company_files", ["资料", "文件", "整理", "归档", "入库", "脑图", "xmind"]),
]


def _score_template(text: str, template_id: str, keywords: list[str]) -> int:
    lowered = text.lower()
    score = sum(3 for keyword in keywords if keyword.lower() in lowered)
    for example in TASK_TEMPLATES[template_id]["plain_examples"]:
        example_terms = re.findall(r"[A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", example.lower())
        score += sum(1 for term in example_terms if term in lowered)
    return score


def list_friendly_task_templates() -> str:
    """列出给非专业用户使用的自然语言任务模板。"""
    return json.dumps(
        {
            "templates": [
                {
                    "id": template_id,
                    "label": template["label"],
                    "plain_examples": template["plain_examples"],
                    "expected_steps": template["expected_steps"],
                }
                for template_id, template in TASK_TEMPLATES.items()
            ],
            "guidance": "用户可以直接说普通业务目标，系统会自动翻译成清洗、入库、LightRAG 同步和辅助决策任务。",
        },
        ensure_ascii=False,
        indent=2,
    )


def explain_friendly_task(user_message: str) -> str:
    """把非专业自然语言解释成系统可执行任务。"""
    scored = []
    for template_id, keywords in KEYWORD_RULES:
        score = _score_template(user_message, template_id, keywords)
        if score:
            scored.append((score, template_id))
    if not scored:
        scored.append((1, "organize_company_files"))
    scored.sort(reverse=True)
    template_id = scored[0][1]
    template = TASK_TEMPLATES[template_id]
    confidence = "high" if scored[0][0] >= 6 else "medium" if scored[0][0] >= 3 else "low"
    return json.dumps(
        {
            "original_message": user_message,
            "matched_template_id": template_id,
            "confidence": confidence,
            "friendly_label": template["label"],
            "route": template["route"],
            "expanded_system_prompt": template["system_prompt"],
            "expected_steps": template["expected_steps"],
            "user_facing_reply": (
                f"我会按“{template['label']}”来处理："
                f"{' → '.join(template['expected_steps'])}。如果资料不够，我会用人话告诉你缺什么。"
            ),
            "human_confirmation_required": [
                "删除文件",
                "外发消息",
                "创建采购单",
                "修改广告预算",
                "大额采购或财务决策",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def start_friendly_task(user_message: str) -> str:
    """把普通业务说法翻译成任务，并直接后台启动，避免前端长时间等待。"""
    explanation = json.loads(explain_friendly_task(user_message))
    goal = (
        f"{explanation['friendly_label']}：{explanation['expanded_system_prompt']}\n\n"
        f"用户原话：{user_message}"
    )
    background = json.loads(start_company_workflow_task(goal))
    return json.dumps(
        {
            "status": "started",
            "friendly_task": explanation,
            "background_task": background,
            "message": (
                f"已按“{explanation['friendly_label']}”后台开始处理。"
                f"task_id: {background.get('task_id')}。"
                "你可以稍后让我查询这个 task_id 的进度。"
            ),
        },
        ensure_ascii=False,
        indent=2,
    )
