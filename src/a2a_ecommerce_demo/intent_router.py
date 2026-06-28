from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserIntent:
    intent: str
    start_background_workflow: bool
    read_only: bool
    reason: str


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_user_intent(text: str) -> UserIntent:
    """Classify user text into stable front-door intents.

    The important product boundary is read-only analysis vs expensive data ingestion.
    Both supervisor routing and workflow tools should call this single function so the
    two guards cannot drift.
    """
    normalized = text.lower()
    if _contains_any(normalized, ["任务进度", "进度", "完成了吗", "完成没有", "查一下", "处理到哪", "现在怎么样"]):
        return UserIntent("workflow_progress", False, True, "workflow_progress_request")

    analysis_signal = _contains_any(normalized, ["分析", "决策", "优先级", "执行清单", "建议", "提升", "风险", "缺口"])
    existing_context_signal = _contains_any(normalized, ["当前", "已有", "现有", "已经", "已", "所有数据", "全部数据"])
    direct_answer_signal = _contains_any(normalized, ["直接", "不要重新", "不用重新", "不要启动", "不要后台"])
    new_material_signal = _contains_any(normalized, ["刚放", "我放", "上传", "新资料", "新文件", "raw", "excel", "xlsx", "xmind", "脑图"])
    rebuild_signal = _contains_any(normalized, ["整理", "入库", "同步", "重新处理", "重新从", "清洗"])
    source_signal = _contains_any(normalized, ["source", "数据源", "源文件", "日报源", "销售日报源", "微盘", "导出目录"])

    if source_signal and rebuild_signal and not direct_answer_signal:
        return UserIntent("source_sync", True, False, "explicit_source_sync")

    if analysis_signal and (existing_context_signal or direct_answer_signal) and not (new_material_signal and rebuild_signal):
        return UserIntent("existing_data_analysis", False, True, "analysis_over_existing_data")

    file_signal = _contains_any(normalized, ["资料", "文件", "raw", "excel", "xlsx", "xmind", "脑图", "obsidian", "知识库"])
    action_signal = _contains_any(normalized, ["刚放", "我放", "上传", "整理", "入库", "同步", "清洗", "重新处理", "重新从"])
    if file_signal and action_signal:
        return UserIntent("new_material_ingest", True, False, "explicit_file_ingest_or_sync")

    if analysis_signal:
        return UserIntent("analysis", False, True, "analysis_without_ingest_signal")

    return UserIntent("general", False, True, "default_read_only")
