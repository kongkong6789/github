from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from src.a2a_ecommerce_demo.active_skill_resolver import inject_active_skill_messages
from src.a2a_ecommerce_demo.agent_factory_tools import (
    list_agent_skill_templates,
    save_agent_skill_template,
    save_wiki_page_as_prompt_template,
    suggest_agent_team,
)
from src.a2a_ecommerce_demo.agent_reach_tools import (
    agent_reach_get_status,
    agent_reach_read_logged_in_social,
    agent_reach_read_public_web,
    agent_reach_read_video_transcript,
    agent_reach_search_public_sources,
)
from src.a2a_ecommerce_demo.agent_tool_registry import (
    TOOL_REGISTRY,
    TOP_SUPERVISOR_AGENT_NAME,
    TOP_SUPERVISOR_SAFE_READ_TOOLS,
    resolve_agent_tools,
    validate_agent_tool_registry,
)
from src.a2a_ecommerce_demo.business_tools import (
    analyze_company_financial_position,
    analyze_company_strategy,
    analyze_restock_decision,
    assess_data_quality,
    assess_decision_risks,
    audit_fact_source_readiness,
    list_business_files,
    list_fact_tables,
    list_registered_datasets,
    plan_fact_query,
    query_ads_history,
    query_fact_layer,
    query_fact_layer_from_question,
    query_finance_history,
    query_inventory_anomalies,
    query_inventory_history,
    query_inventory_snapshot,
    query_sales_history,
    query_sku_snapshot,
    register_all_fact_datasets,
    save_decision_report,
    simulate_decision_scenarios,
    summarize_brand_coverage,
    summarize_business_data,
)
from src.a2a_ecommerce_demo.connector_live_tools import (
    format_jackyun_warehouse_scope_rules_for_prompt,
    list_erp_live_query_capabilities,
    query_erp_live_snapshot,
    query_inventory_cost_reference,
    query_jackyun_channel_sales_summary,
    route_erp_live_query,
    test_erp_live_connection,
    verify_erp_supplier_terms_mapping,
)
from src.a2a_ecommerce_demo.connector_registry import ensure_connector_registry
from src.a2a_ecommerce_demo.connector_tools import (
    get_erp_connector_health,
    list_erp_connectors,
    preview_erp_connector_sync,
    sync_connector_dataset,
)
from src.a2a_ecommerce_demo.dynamic_agent_hub import (
    confirm_dynamic_agent_spec,
    draft_dynamic_agent_spec,
    draft_dynamic_agent_spec_from_template,
    get_dynamic_agent,
    list_dynamic_agents,
    promote_dynamic_agent_to_template,
    rollback_dynamic_agent,
    run_dynamic_agent,
    set_dynamic_agent_status,
    update_dynamic_agent_spec,
)
from src.a2a_ecommerce_demo.enterprise_audit_tools import list_audit_events, record_audit_event
from src.a2a_ecommerce_demo.evidence_graph_tools import (
    build_evidence_graph,
    list_evidence_graph_edges,
    list_evidence_graph_nodes,
)
from src.a2a_ecommerce_demo.friendly_task_tools import (
    explain_friendly_task,
    list_friendly_task_templates,
    start_friendly_task,
)
from src.a2a_ecommerce_demo.intent_router import classify_user_intent
from src.a2a_ecommerce_demo.knowledge_tools import (
    append_dataset_insight,
    append_decision_note,
    append_durable_insight,
    ingest_all_raw_files,
    ingest_raw_file,
    list_raw_files,
    list_wiki_pages,
    read_wiki_page,
    search_wiki,
)
from src.a2a_ecommerce_demo.large_excel_tools import (
    assess_large_excel_quality,
    process_all_large_excel_files,
    process_large_excel_file,
    profile_large_excel_file,
)
from src.a2a_ecommerce_demo.lightrag_tools import (
    auto_recover_lightrag_timeouts,
    cleanup_confirmed_lightrag_failed_history,
    diagnose_lightrag_failures,
    get_lightrag_entity,
    get_lightrag_track_status,
    lightrag_server_status,
    list_failed_lightrag_docs,
    list_lightrag_entities,
    query_lightrag,
    query_official_lightrag,
    rebuild_lightrag_index,
    resolve_lightrag_reference_paths,
    retry_failed_lightrag_docs,
    summarize_lightrag_processing_status,
    sync_obsidian_to_official_lightrag,
)
from src.a2a_ecommerce_demo.mcp_governance_tools import (
    check_mcp_tool_permission,
    list_mcp_tool_policy,
    record_mcp_tool_audit,
    request_mcp_write_approval,
)
from src.a2a_ecommerce_demo.permission_tools import check_path_permission, list_permission_policy
from src.a2a_ecommerce_demo.platform_integration_tools import (
    check_reference_platform_health,
    list_reference_platforms,
    query_external_platform_readonly,
    route_knowledge_stack,
)
from src.a2a_ecommerce_demo.runtime_capability_tools import (
    invoke_runtime_capability,
    list_runtime_capabilities,
    register_runtime_mcp_tool,
)
from src.a2a_ecommerce_demo.sensitive_data_tools import (
    classify_sensitive_fields,
    mask_sensitive_record,
    record_sensitive_field_access,
    summarize_sensitive_fields_from_registry,
)
from src.a2a_ecommerce_demo.skill_registry_tools import (
    approve_agent_skill,
    create_agent_skill_from_wiki,
    get_agent_skill,
    list_agent_skills,
    rollback_agent_skill,
    set_agent_skill_status,
    update_agent_skill,
)
from src.a2a_ecommerce_demo.source_registry_tools import (
    check_source_registry_health,
    get_source,
    list_source_snapshots,
    list_sources,
    register_source,
    run_source_sync_workflow,
    set_source_status,
    sync_source,
)
from src.a2a_ecommerce_demo.table_cleaning_tools import (
    clean_all_excel_files,
    clean_excel_to_csv,
    profile_excel_file,
    write_cleaning_report,
)
from src.a2a_ecommerce_demo.task_delegation_tools import (
    cancel_workflow_task,
    create_workflow_task,
    finalize_workflow_report,
    get_workflow_task_status,
    list_workflow_tasks,
    recover_workflow_queue,
    run_company_strategy_task,
    run_excel_cleaning_task,
    run_fact_layer_registration_task,
    run_finance_task,
    run_full_company_workflow,
    run_large_excel_pipeline_task,
    run_lightrag_index_task,
    run_quality_task,
    run_raw_discovery_task,
    run_wiki_ingest_task,
    run_wiki_memory_task,
    start_company_workflow_task,
)
from src.a2a_ecommerce_demo.wecom_smartsheet_tools import (
    list_wecom_smartsheet_sources,
    query_wecom_smartsheet_records,
    sync_wecom_smartsheet_snapshot,
    test_wecom_smartsheet_connection,
)
from src.a2a_ecommerce_demo.wiki_lifecycle_tools import (
    append_wiki_log_event,
    archive_decision_to_wiki,
    ensure_wiki_knowledge_scaffold,
    generate_wiki_review_questions,
    lint_wiki_knowledge_base,
    normalize_legacy_wiki_pages,
    refresh_wiki_index,
    register_wiki_claim_evidence,
)
from src.a2a_ecommerce_demo.wiki_memory_tools import generate_cleaning_rules, generate_data_dictionary


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _last_user_text(state: MessagesState) -> str:
    for message in reversed(state.get("messages", [])):
        message_type = getattr(message, "type", None) or getattr(message, "role", None)
        if isinstance(message, dict):
            message_type = message.get("type") or message.get("role")
            content = message.get("content")
        else:
            content = getattr(message, "content", "")
        if message_type in {"human", "user"}:
            return _message_text(content)
    return ""


def _message_type(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("type") or message.get("role") or "")
    return str(getattr(message, "type", None) or getattr(message, "role", "") or "")


def _is_ai_message_type(message_type: str) -> bool:
    return message_type in {"ai", "assistant"}


def _message_tool_calls(message: Any) -> list[Any]:
    if isinstance(message, dict):
        value = message.get("tool_calls") or []
    else:
        value = getattr(message, "tool_calls", []) or []
    return value if isinstance(value, list) else []


def _tool_call_id(tool_call: Any) -> str:
    if isinstance(tool_call, dict):
        return str(tool_call.get("id") or "")
    return str(getattr(tool_call, "id", "") or "")


def _tool_call_name(tool_call: Any) -> str | None:
    if isinstance(tool_call, dict):
        name = tool_call.get("name")
    else:
        name = getattr(tool_call, "name", None)
    return str(name) if name else None


def _message_tool_call_id(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("tool_call_id") or "")
    return str(getattr(message, "tool_call_id", "") or "")


def _sanitize_messages_for_llm(messages: list[Any]) -> list[Any]:
    """Return OpenAI-compatible chat history for model calls.

    Older UI builds could persist synthetic tool messages without the adjacent
    assistant tool call. DeepSeek/OpenAI rejects that history, so model input is
    repaired here without mutating the stored thread checkpoint.
    """
    sanitized: list[Any] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        message_type = _message_type(message)

        if message_type == "system":
            index += 1
            continue

        if message_type == "tool":
            index += 1
            continue

        sanitized.append(message)

        if not _is_ai_message_type(message_type):
            index += 1
            continue

        tool_calls = _message_tool_calls(message)
        if not tool_calls:
            index += 1
            continue

        expected_tool_call_ids = [_tool_call_id(tool_call) for tool_call in tool_calls]
        seen_tool_call_ids: set[str] = set()
        lookahead = index + 1
        while lookahead < len(messages) and _message_type(messages[lookahead]) == "tool":
            tool_message = messages[lookahead]
            tool_call_id = _message_tool_call_id(tool_message)
            if tool_call_id in expected_tool_call_ids and tool_call_id not in seen_tool_call_ids:
                sanitized.append(tool_message)
                seen_tool_call_ids.add(tool_call_id)
            lookahead += 1

        for tool_call in tool_calls:
            tool_call_id = _tool_call_id(tool_call)
            if tool_call_id and tool_call_id not in seen_tool_call_ids:
                sanitized.append(
                    ToolMessage(
                        content="Synthetic tool response inserted to repair stored chat history before model input.",
                        tool_call_id=tool_call_id,
                        name=_tool_call_name(tool_call),
                    )
                )

        index = lookahead

    return sanitized


def _jackyun_warehouse_scope_guard_text() -> str:
    rules_text = format_jackyun_warehouse_scope_rules_for_prompt()
    return (
        "仓库业务口径以配置化 warehouse_scope_rules 为准；"
        f"当前规则：{rules_text}；未命中映射的仓库单独列为未映射。"
    )


def _jackyun_inventory_analysis_guard_text() -> str:
    return (
        "吉客云库存分析口径：如果品牌字段 brandName 为空，必须说明当前是通过 master_data goodsName/alias"
        " 扩展到 goodsNo 后查询库存，并把可能遗漏列为品牌识别缺口。costPrice/采购价缺失或覆盖不全只影响库存金额、"
        "成本金额、毛利和金额口径周转；如果有近 N 天销量/出库数据，仍可计算数量口径周转和覆盖天数。"
        "吉客云 inventory_stock 可能返回 yesterdayQuantity/threedayQuantity/weekQuantity/stockOutuantity；"
        "这些字段可作为实时 SKU+仓库近销/出库口径，brand_expansion.summary 中的 "
        "yesterday_quantity/three_day_quantity/week_quantity/stock_out_quantity 可用于全品牌数量口径估算，"
        "但不得写成完整销售订单明细。"
        "当用户要求补采购价/成本价或做金额口径库存分析时，先调用 verify_erp_supplier_terms_mapping；"
        "更稳的默认动作是直接调用 query_inventory_cost_reference，它会按只读白名单自动组合吉客云库存、"
        "吉客云批次/采购和金蝶采购订单价参考。"
        "若金蝶采购订单字段可用，再调用 query_erp_live_snapshot 查询 kingdee_erp 的 supplier_procurement_terms"
        " 或 purchase_orders，并优先用 goods_no/material_no/material_keyword 过滤物料；FTaxPrice 只能作为"
        "采购订单含税采购单价参考，不等同于最终库存核算成本。"
        "query_inventory_cost_reference 的 cost_reference.selected_value 只代表 derived_reference_filters"
        " 命中的物料/SKU参考价格，不得当成全品牌统一采购价或最终库存成本。"
        "当用户明确要求吉客云实时 SKU 日销、渠道销量或销售金额时，调用 query_jackyun_channel_sales_summary；"
        "该工具只封装吉客云 Skill 销售汇总查询，不开放写入，输出日期+渠道/店铺+SKU+销量/金额口径。"
        "当 query_inventory_cost_reference 或 query_erp_live_snapshot 返回 brand_expansion.summary 时，"
        "全仓/全品牌库存结论必须优先使用 brand_expansion.summary；rows 只是 limit 截断样例，"
        "不得把前 100 行当成全量 SKU 或全量仓库。"
        "未读取销量/出库数据时，不得声称已完成库存周转计算。批次效期只能来自 batch_inventory/"
        "erp.batchstockquantity.get；如果只读取 inventory_stock/erp.stockquantity.get，必须把临期风险列为未量化缺口。"
    )


def _sanitize_model_input_hook(state: MessagesState) -> dict[str, list[Any]]:
    sanitized = _sanitize_messages_for_llm(list(state.get("messages", [])))
    user_text = _last_user_text(state)
    llm_messages = inject_active_skill_messages(sanitized, user_text)
    if _is_explicit_wecom_smartsheet_read_request(user_text):
        llm_messages = [
            SystemMessage(content=_wecom_smartsheet_runtime_url_guard_text()),
            *llm_messages,
        ]
    if _is_explicit_live_erp_read_request(user_text):
        llm_messages = [
            SystemMessage(
                content=(
                    "本轮用户明确要求读取实时 ERP/吉客云/金蝶当前数据。若你是路由主管，必须把任务交给"
                    "具备实时只读 ERP 工具的 Agent；若你有工具权限，必须先调用 query_erp_live_snapshot"
                    " 并基于工具返回回答。handoff/transfer 成功消息不是数据证据；没有 query_erp_live_snapshot"
                    " 的工具结果时，最终回答不得提供库存、订单、仓库、渠道或 SKU 数字。吉客云库存按品牌查询时，"
                    "先用 master_data goods 找到 goodsNo/skuBarcode，再用 inventory_stock 按 goods_no 查询并标注"
                    "页码、过滤条件、row_count、查询时间语境和口径缺口。SKU 编码必须使用吉客云 goodsNo 或 skuBarcode；"
                    "产品名称必须使用 goodsName，不得编造 UNV-001/UNV-008 等占位 SKU。"
                    f"{_jackyun_warehouse_scope_guard_text()}"
                    f"{_jackyun_inventory_analysis_guard_text()}"
                    f"{_wecom_smartsheet_runtime_url_guard_text()}"
                )
            ),
            *llm_messages,
        ]
    return {"llm_input_messages": llm_messages}


def _is_explicit_wecom_smartsheet_read_request(text: str) -> bool:
    normalized = text.lower()
    return "doc.weixin.qq.com/smartsheet" in normalized or any(
        keyword in normalized for keyword in ["企业微信智能表", "企微智能表", "wedoc", "智能表"]
    )


def _wecom_smartsheet_runtime_url_guard_text() -> str:
    return (
        "企业微信智能表读取口径：如果用户提供 doc.weixin.qq.com/smartsheet URL，"
        "调用 query_wecom_smartsheet_records 时必须传 doc_url=用户原始URL；若用户说这是日销表，"
        "dataset 使用 channel_daily_sales；sheet_id 会从 URL 的 tab 参数自动识别，不依赖固定 source_id"
        " 或 config/wecom_smartsheet_sources.json。只有用户没有提供 URL 时，才先调用 list_wecom_smartsheet_sources"
        " 查可用 source_id。若 MCP 返回的公式列（如品牌、渠道名称）为空但渠道编码有值，不得判定日销不可用；"
        "应使用渠道编码作为唯一匹配键，回连用户提供的渠道映射或基础表维度。没有映射时，把渠道维表列为数据缺口。"
        "企业微信智能表结果是实时 MCP 读取；DuckDB 事实层是本地快照/历史聚合兜底。不得把 DuckDB "
        "agg_sku_daily_sales 描述成实时企业微信日销，也不得在实时日销已读到时用 DuckDB 替代它。"
    )


def _is_explicit_live_erp_read_request(text: str) -> bool:
    normalized = text.lower()
    erp_signal = any(keyword in normalized for keyword in ["吉客云", "金蝶", "erp", "实时", "当前"])
    live_signal = any(keyword in normalized for keyword in ["吉客云", "金蝶", "实时", "当前", "现在", "最新"])
    metric_signal = any(
        keyword in normalized
        for keyword in [
            "库存",
            "订单",
            "全渠道",
            "仓库",
            "sku",
            "可用",
            "在途",
            "采购",
            "采购价",
            "成本",
            "成本价",
            "毛利",
            "库存金额",
            "金额周转",
            "日销",
            "周转",
            "出库",
            "入库",
            "应收",
        ]
    )
    return erp_signal and live_signal and metric_signal


def _is_friendly_background_request(text: str) -> bool:
    return classify_user_intent(text).start_background_workflow


def _is_workflow_progress_request(text: str) -> bool:
    return classify_user_intent(text).intent == "workflow_progress"


def _extract_task_id_from_state(state: MessagesState) -> str:
    texts = []
    for message in reversed(state.get("messages", [])):
        if isinstance(message, dict):
            content = message.get("content")
        else:
            content = getattr(message, "content", "")
        texts.append(_message_text(content))
    combined = "\n".join(texts)
    quoted_matches = re.findall(r"`(20\d{6}-\d{6}[^`]+)`", combined)
    if quoted_matches:
        return quoted_matches[0].strip()
    loose_match = re.search(r"(20\d{6}-\d{6}-[^\s，。；;]+)", combined)
    return loose_match.group(1).strip() if loose_match else ""


def _latest_task_id() -> str:
    tasks = json.loads(list_workflow_tasks(limit=1)).get("tasks", [])
    return str(tasks[0].get("task_id", "")) if tasks else ""


def _status_icon(status: str) -> str:
    if status == "success":
        return "✅"
    if status in {"warning", "running", "queued", "created"}:
        return "⏳" if status in {"running", "queued", "created"} else "⚠️"
    if status in {"failed", "cancelled", "cancelling"}:
        return "❌"
    return "•"


def _format_progress_summary(task: dict[str, Any]) -> str:
    lines = [
        "📋 **真实任务进度**",
        "",
        f"**任务ID：** `{task.get('task_id', '')}`",
        f"**状态：** `{task.get('status', 'unknown')}`",
        f"**更新时间：** {task.get('updated_at', '')}",
        "",
        "## 子任务状态",
    ]
    for index, step in enumerate(task.get("steps", []), start=1):
        status = str(step.get("status", ""))
        lines.append(f"{index}. {_status_icon(status)} `{step.get('task', 'unknown')}` - {status}")
        summary = str(step.get("summary", "")).strip()
        if summary:
            lines.append(f"   - {summary}")

        if step.get("task") == "large_excel_pipeline":
            for result in step.get("data", {}).get("results", []):
                processed = result.get("processed", {})
                quality = processed.get("quality", {})
                lines.extend(
                    [
                        f"   - 大表：`{result.get('file', '')}`",
                        f"   - Sheets：{len(processed.get('sheets', []))}；Chunks：{len(processed.get('chunks', []))}",
                        f"   - Rows：{sum(chunk.get('rows', 0) for chunk in processed.get('chunks', []))}",
                        f"   - Manifest：`{processed.get('manifest_path', '')}`",
                        f"   - Quality：{quality.get('quality_level', 'unknown')}；报告：`{quality.get('quality_report_path', '')}`",
                    ]
                )
                dataset_registry = processed.get("dataset_registry", {})
                if dataset_registry:
                    lines.append(f"   - Fact layer：dataset=`{dataset_registry.get('dataset_slug', '')}` duckdb=`{dataset_registry.get('duckdb_path', '')}`")
                    overview_page = dataset_registry.get("wiki_pages", {}).get("overview", "")
                    if overview_page:
                        lines.append(f"   - Dataset wiki：`{overview_page}`")
                warnings = quality.get("warnings", [])
                if warnings:
                    lines.append(f"   - 风险：{'; '.join(str(item) for item in warnings[:4])}")

        if step.get("task") == "wiki_ingest":
            results = step.get("data", {}).get("results", [])
            lines.append(f"   - 入库文件数：{len(results)}")
            for item in results[:8]:
                lines.append(f"   - `{item.get('raw_file', '')}` → `{item.get('wiki_path', '')}`")

        if step.get("task") == "fact_layer_registration":
            data = step.get("data", {})
            for bucket_name in ["large_excel", "structured"]:
                bucket = data.get(bucket_name, {})
                lines.append(f"   - {bucket_name} 注册数：{bucket.get('processed', 0)}")
                for item in bucket.get("results", [])[:6]:
                    dataset = item.get("dataset", {})
                    if dataset:
                        lines.append(f"   - `{item.get('path', item.get('manifest_path', ''))}` → dataset `{dataset.get('dataset_slug', '')}`")

        if step.get("task") == "lightrag_index":
            data = step.get("data", {})
            lines.append(
                f"   - LightRAG：inserted={len(data.get('inserted', []))}, "
                f"skipped={len(data.get('skipped', []))}, failed={len(data.get('failed', []))}"
            )

        if step.get("task") == "data_quality":
            data = step.get("data", {})
            missing = data.get("missing_field_groups", [])
            lines.append(f"   - 数据质量：{data.get('quality_level', 'unknown')}")
            if missing:
                lines.append(f"   - 缺少字段组：{', '.join(missing)}")

    final_report = task.get("final_report", {})
    if final_report:
        lines.extend(["", "## 最终报告", f"- `{final_report.get('saved_to', '')}`"])

    if task.get("background_running"):
        lines.append("")
        lines.append("后台 worker 仍在运行；请稍后再查一次确认最终状态。")
    return "\n".join(lines)


def _workflow_progress_node(state: MessagesState) -> dict[str, list[AIMessage]]:
    task_id = _extract_task_id_from_state(state) or _latest_task_id()
    if not task_id:
        content = "我现在没有找到可查询的后台任务。你可以先发“我刚放了资料，帮我整理进知识库”，系统会返回 task_id。"
        return {"messages": [AIMessage(content=content, name="friendly_router_agent")]}
    try:
        task = json.loads(get_workflow_task_status(task_id))
        content = _format_progress_summary(task)
    except Exception as exc:
        content = f"我找到了任务ID `{task_id}`，但读取任务状态失败：{exc}"
    return {"messages": [AIMessage(content=content, name="friendly_router_agent")]}


def _friendly_background_node(state: MessagesState) -> dict[str, list[AIMessage]]:
    user_text = _last_user_text(state)
    result = json.loads(start_friendly_task(user_text))
    task_id = result.get("background_task", {}).get("task_id", "未知")
    friendly_task = result.get("friendly_task", {})
    label = friendly_task.get("friendly_label", "资料整理")
    steps = friendly_task.get("expected_steps", [])
    step_text = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    content = (
        f"好的，已按“{label}”开始后台处理。\n\n"
        f"**任务ID：** `{task_id}`\n\n"
        f"**我会做这些事：**\n{step_text}\n\n"
        "你可以随时说“查一下任务进度”，我会读取后台任务状态并告诉你处理到哪一步。"
    )
    return {"messages": [AIMessage(content=content, name="friendly_router_agent")]}


def search_competitors(query: str) -> str:
    """Return a sample competitor research summary for a product query."""
    return (
        f"示例竞品调研：{query} 的主要竞争点通常包括价格、图片质感、差评痛点、"
        "物流时效、材质参数和售后承诺。正式接入时可替换为天猫/淘宝/抖音/京东/拼多多/ERP/API 数据。"
    )


def analyze_ads(metric_summary: str) -> str:
    """Return a sample ad optimization summary."""
    return (
        f"示例广告分析：{metric_summary}。建议按投产比、费比、GMV、转化率、UV 价值拆分计划，"
        "提高高转化人群/关键词预算，压低高花费低转化计划。"
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _chat_openai_kwargs() -> dict[str, Any]:
    model_name = os.getenv("OPENAI_MODEL", "").lower()
    base_url = os.getenv("OPENAI_BASE_URL", "").lower()
    kwargs: dict[str, Any] = {}
    if "deepseek-v4" in model_name:
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    if "deepseek" in model_name or "deepseek" in base_url:
        kwargs["disable_streaming"] = _env_bool("A2A_LLM_DISABLE_STREAMING", True)
        kwargs["max_retries"] = _env_int("A2A_LLM_MAX_RETRIES", 3)
        kwargs["timeout"] = _env_float("A2A_LLM_TIMEOUT_SECONDS", 180.0)
    return kwargs


def _tool_catalog() -> dict[str, Any]:
    return {
        tool.__name__: tool
        for tool in [
            agent_reach_get_status,
            agent_reach_read_logged_in_social,
            agent_reach_read_public_web,
            agent_reach_read_video_transcript,
            agent_reach_search_public_sources,
            analyze_ads,
            analyze_company_financial_position,
            analyze_company_strategy,
            analyze_restock_decision,
            append_wiki_log_event,
            append_dataset_insight,
            append_decision_note,
            append_durable_insight,
            archive_decision_to_wiki,
            assess_data_quality,
            assess_decision_risks,
            assess_large_excel_quality,
            audit_fact_source_readiness,
            auto_recover_lightrag_timeouts,
            cancel_workflow_task,
            check_mcp_tool_permission,
            check_path_permission,
            classify_sensitive_fields,
            clean_all_excel_files,
            clean_excel_to_csv,
            cleanup_confirmed_lightrag_failed_history,
            approve_agent_skill,
            build_evidence_graph,
            confirm_dynamic_agent_spec,
            create_agent_skill_from_wiki,
            create_workflow_task,
            diagnose_lightrag_failures,
            draft_dynamic_agent_spec,
            draft_dynamic_agent_spec_from_template,
            ensure_wiki_knowledge_scaffold,
            explain_friendly_task,
            finalize_workflow_report,
            generate_wiki_review_questions,
            generate_cleaning_rules,
            generate_data_dictionary,
            get_dynamic_agent,
            get_agent_skill,
            get_lightrag_entity,
            get_lightrag_track_status,
            get_source,
            get_workflow_task_status,
            get_erp_connector_health,
            ingest_all_raw_files,
            ingest_raw_file,
            list_erp_live_query_capabilities,
            verify_erp_supplier_terms_mapping,
            list_agent_skills,
            lightrag_server_status,
            list_agent_skill_templates,
            list_audit_events,
            list_business_files,
            list_dynamic_agents,
            list_erp_connectors,
            list_evidence_graph_edges,
            list_evidence_graph_nodes,
            list_fact_tables,
            list_failed_lightrag_docs,
            list_friendly_task_templates,
            list_lightrag_entities,
            list_mcp_tool_policy,
            list_permission_policy,
            list_raw_files,
            list_registered_datasets,
            list_runtime_capabilities,
            list_sources,
            list_source_snapshots,
            list_wecom_smartsheet_sources,
            list_wiki_pages,
            list_workflow_tasks,
            lint_wiki_knowledge_base,
            normalize_legacy_wiki_pages,
            recover_workflow_queue,
            plan_fact_query,
            preview_erp_connector_sync,
            process_all_large_excel_files,
            process_large_excel_file,
            promote_dynamic_agent_to_template,
            profile_excel_file,
            profile_large_excel_file,
            query_ads_history,
            query_erp_live_snapshot,
            query_fact_layer,
            query_fact_layer_from_question,
            query_finance_history,
            query_inventory_cost_reference,
            query_inventory_anomalies,
            query_inventory_history,
            query_inventory_snapshot,
            query_jackyun_channel_sales_summary,
            query_lightrag,
            query_official_lightrag,
            query_sales_history,
            query_sku_snapshot,
            query_wecom_smartsheet_records,
            rebuild_lightrag_index,
            refresh_wiki_index,
            record_audit_event,
            record_sensitive_field_access,
            record_mcp_tool_audit,
            register_source,
            register_all_fact_datasets,
            register_runtime_mcp_tool,
            register_wiki_claim_evidence,
            request_mcp_write_approval,
            invoke_runtime_capability,
            resolve_lightrag_reference_paths,
            retry_failed_lightrag_docs,
            route_erp_live_query,
            rollback_agent_skill,
            rollback_dynamic_agent,
            run_company_strategy_task,
            run_dynamic_agent,
            run_excel_cleaning_task,
            run_fact_layer_registration_task,
            run_finance_task,
            run_full_company_workflow,
            run_large_excel_pipeline_task,
            run_lightrag_index_task,
            run_quality_task,
            run_raw_discovery_task,
            run_source_sync_workflow,
            run_wiki_ingest_task,
            run_wiki_memory_task,
            save_agent_skill_template,
            save_decision_report,
            save_wiki_page_as_prompt_template,
            search_competitors,
            search_wiki,
            set_dynamic_agent_status,
            set_agent_skill_status,
            set_source_status,
            simulate_decision_scenarios,
            start_company_workflow_task,
            start_friendly_task,
            suggest_agent_team,
            summarize_brand_coverage,
            summarize_business_data,
            summarize_sensitive_fields_from_registry,
            summarize_lightrag_processing_status,
            sync_source,
            sync_connector_dataset,
            sync_wecom_smartsheet_snapshot,
            sync_obsidian_to_official_lightrag,
            test_erp_live_connection,
            test_wecom_smartsheet_connection,
            update_agent_skill,
            update_dynamic_agent_spec,
            write_cleaning_report,
            mask_sensitive_record,
            check_source_registry_health,
            check_reference_platform_health,
            list_reference_platforms,
            route_knowledge_stack,
            query_external_platform_readonly,
            read_wiki_page,
        ]
    }


def _agent_tools(agent_name: str, catalog: dict[str, Any]) -> list[Any]:
    return resolve_agent_tools(agent_name, catalog, strict=True, include_confirmation=False)


def _top_supervisor_safe_tools(catalog: dict[str, Any]) -> list[Any]:
    unregistered = [name for name in TOP_SUPERVISOR_SAFE_READ_TOOLS if name not in TOOL_REGISTRY]
    if unregistered:
        raise KeyError(f"{TOP_SUPERVISOR_AGENT_NAME} references unregistered tools: {', '.join(unregistered)}")
    unsafe = [name for name in TOP_SUPERVISOR_SAFE_READ_TOOLS if not TOOL_REGISTRY[name].read_only]
    if unsafe:
        raise ValueError(f"{TOP_SUPERVISOR_AGENT_NAME} only accepts read-only tools: {', '.join(unsafe)}")
    return resolve_agent_tools(TOP_SUPERVISOR_AGENT_NAME, catalog, strict=True, include_confirmation=False)


def build_supervisor_app():
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY. Copy .env.example to .env and fill it in.")

    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
        **_chat_openai_kwargs(),
    )
    tool_catalog = _tool_catalog()
    validate_agent_tool_registry(tool_catalog)
    if os.getenv("A2A_RECOVER_WORKFLOW_QUEUE_ON_STARTUP", "1") != "0":
        recover_workflow_queue()
    ensure_connector_registry()

    research_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("market_research_agent", tool_catalog),
        name="market_research_agent",
        prompt=(
            "你是国内多平台电商市场调研 Agent。你负责竞品、价格、评论痛点、卖点和趋势分析。"
            "输出要简洁、可执行。"
        ),
    )

    data_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("data_agent", tool_catalog),
        name="data_agent",
        prompt=(
            "你是国内多平台电商数据 Agent。你负责读取 D:\\A2A\\data 下的本地业务数据，"
            "包括库存、销量、广告、利润、商品资料。必须先说明你使用了哪些数据文件、DuckDB mart 或字段。"
            "如果字段名涉及客户个人信息、采购价/供应商报价或财务数据，先调用 classify_sensitive_fields 或 summarize_sensitive_fields_from_registry；"
            "使用这些字段后调用 record_sensitive_field_access 记录类别，不记录行值；输出客户个人信息明细前必须调用 mask_sensitive_record 脱敏。"
            "如果用户问 ERP/API 接入进度，先调用 list_erp_connectors、get_erp_connector_health 或 preview_erp_connector_sync。"
            "默认先查 DuckDB mart；只有用户明确说“实时 ERP/吉客云/金蝶当前数据”，或 DuckDB/fact layer 明确缺数据时，"
            "才调用 list_erp_live_query_capabilities、test_erp_live_connection、query_erp_live_snapshot 做实时只读兜底。"
            "当用户同时提到库存、成本价/采购价、日销、周转、企业微信智能表等组合需求时，先调用 route_erp_live_query；"
            "若路由建议 query_inventory_cost_reference，则直接用该语义工具组合查询，不要只靠文字判断。"
            "若路由或用户明确要求吉客云实时 SKU 日销/渠道销量/销售金额，调用 query_jackyun_channel_sales_summary，"
            "按日期+渠道/店铺+SKU+销量/金额返回，只读且不写入 ERP。"
            "如果用户问企业微信智能表、企微智能表或 WeDoc 表格，先调用 list_wecom_smartsheet_sources；"
            "用户明确要读当前智能表时调用 query_wecom_smartsheet_records，只读结果同样标注 live_read_only_mcp。"
            "如果用户问供应商交期、采购价或历史延误字段是否能映射，优先调用 verify_erp_supplier_terms_mapping 做只读字段验证。"
            "实时 ERP 工具只允许查询，不会写 ERP，也不会写本地快照；回答必须标注系统、查询时间语境和使用的只读接口。"
            "吉客云库存回答中，SKU 编码只能来自 goodsNo 或 skuBarcode，产品名称只能来自 goodsName，不得编造 UNV-00x 占位编码。"
            f"{_jackyun_warehouse_scope_guard_text()}"
            f"{_jackyun_inventory_analysis_guard_text()}"
            "默认不能假设只有一个品牌。用户没明确指定品牌时，先调用 summarize_brand_coverage 判断当前是单品牌、多品牌还是缺品牌字段。"
            "当问题是字段意义、历史结论、分析方法时，交给 wiki/LightRAG；"
            "当问题是全量库存、销量、聚合、过滤、最近 N 天变化时，优先调用 DuckDB 事实层工具。"
            "当用户直接用自然语言问指标问题时，优先调用 plan_fact_query 或 query_fact_layer_from_question，"
            "不要自由发挥 SQL。"
            "warehouse_sample 只作为回退，不要把它当成大表主查询路径。"
            "如果用户问为什么 ads/finance mart 还没起来，先调用 audit_fact_source_readiness。"
            "如果数据缺失，要明确标注缺口，不能假装已有数据。"
        ),
    )

    knowledge_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("knowledge_agent", tool_catalog),
        name="knowledge_agent",
        prompt=(
            "你是国内多平台电商知识库 Agent。你负责检索 D:\\A2A\\wiki Obsidian 知识库，"
            "包括 SOP、产品档案、供应商、平台规则、广告策略和历史决策。"
            "你遵循 Karpathy LLM Wiki 思想：wiki 是 Agent 的长期外部记忆，"
            "回答和写入时要尽量保留来源、生成可复用事实、建立产品/供应商/字段/决策之间的联系。"
            "LightRAG 只索引 wiki 里的高信号知识页和结论页，不再把 warehouse CSV 预览当成语义知识源。"
            "回答时必须说明引用了哪些 wiki 页面。"
            "只要 search_wiki/read_wiki_page 工具返回内容，就代表你已经成功访问本地 Obsidian 知识库，"
            "不要声称无法访问 Obsidian。"
            "如果用户要求沉淀经验或记录决策，可以调用 append_decision_note、append_dataset_insight；"
            "只有字段口径、质量异常、业务规则、分析模板、复盘结论这类长期复用内容才调用 append_durable_insight。"
            "当用户问跨资料关系、证据链、SKU/供应商/库存/财务之间的关联时，优先调用 query_lightrag。"
            "如果需要把 LightRAG 引用落到源数据，调用 resolve_lightrag_reference_paths。"
            "如果用户要求完整 LightRAG，先调用 lightrag_server_status，再调用 sync_obsidian_to_official_lightrag。"
            "如果要重试 failed 文档，先调用 summarize_lightrag_processing_status；余额不足或模型不可用时暂停 retry。"
            "如果 failed 根因是 timeout，先调用 auto_recover_lightrag_timeouts 发起 approve/reject interrupt；只有用户 approve 后才提交 retry 并清理 LightRAG 原始 failed 记录。"
        ),
    )

    wiki_ingest_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("wiki_ingest_agent", tool_catalog),
        name="wiki_ingest_agent",
        prompt=(
            "你是 Obsidian 知识入库 Agent。你负责把 D:\\A2A\\raw 目录里的原始资料"
            "整理成 D:\\A2A\\wiki 里的 Markdown 页面。"
            "入库时遵循 Karpathy LLM Wiki 思想：资料不是简单搬运，而是要变成未来可检索、可引用、可复盘的知识。"
            "优先识别产品、供应商、平台规则、字段字典、清洗规则、历史决策和待确认问题。"
            "默认流程：先 list_raw_files，再按用户要求调用 ingest_raw_file 或 ingest_all_raw_files。"
            "入库完成后要告诉用户生成了哪些 wiki 页面。"
            "入库完成后如果用户需要辅助决策，调用 sync_obsidian_to_official_lightrag 同步完整 LightRAG；服务不可用时会自动生成本地兜底索引。"
            "如果 LightRAG 出现 timeout failed，先诊断，再用 auto_recover_lightrag_timeouts 发起 approve/reject interrupt；用户确认后才压缩恢复。"
            "不要读取 raw/wiki 之外的路径。"
        ),
    )

    data_cleaning_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("data_cleaning_agent", tool_catalog),
        name="data_cleaning_agent",
        prompt=(
            "你是数据清洗 Agent，负责处理 D:\\A2A\\raw 中复杂、混乱、不规则的 Excel 表。"
            "如果 Excel 超过 50MB，必须优先使用 profile_large_excel_file/process_large_excel_file/process_all_large_excel_files，"
            "把它作为后台离线大文件处理，不要在前端聊天请求中直接完整解析。"
            "默认流程：先调用 profile_excel_file 做表结构体检，再按需要调用 clean_excel_to_csv 或 clean_all_excel_files，"
            "把干净 CSV 输出到 D:\\A2A\\data\\cleaned。"
            "大文件分块结果输出到 D:\\A2A\\data\\warehouse\\large_excel，并进一步注册到 DuckDB/Parquet 事实层，生成 manifest、quality_report 和数据集 wiki 页面。"
            "你必须说明识别到的表头、行列数量、清洗后的文件路径、丢弃了哪些空行/空列，以及哪些问题需要人工确认。"
            "不要覆盖原始 raw 文件。对于合并单元格、公式、重复表头、表头不清晰的情况，要明确标注风险。"
            "如果清洗规则对以后有复用价值，可以调用 write_cleaning_report 保存到 Obsidian logs。"
        ),
    )

    quality_gate_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("quality_gate_agent", tool_catalog),
        name="quality_gate_agent",
        prompt=(
            "你是数据质量门 Agent。公司级辅助决策、库存补货、财务判断、广告预算调整之前，"
            "你必须先检查数据是否足够可靠。重点检查：字段完整性、空值、重复数据、表头风险、"
            "公式风险、缺少收入/成本/现金/库存/销量/广告/供应商等关键字段。"
            "如果字段名涉及客户个人信息、采购价或财务数据，调用 classify_sensitive_fields 并在质量结论里标记敏感字段类型。"
            "输出必须包含：能否进入决策、缺哪些字段、哪些结论置信度低、下一步补救动作。"
            "如果发现可复用的数据问题或字段规则，可以调用 append_decision_note 沉淀到 Obsidian。"
        ),
    )

    inventory_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("inventory_agent", tool_catalog),
        name="inventory_agent",
        prompt=(
            "你是国内多平台电商库存与补货 Agent。你负责判断断货风险、库存覆盖天数、"
            "采购周期、安全库存和补货数量。用户明确要求实时 ERP/吉客云/当前库存时，"
            "必须先调用 query_erp_live_snapshot 做只读查询，并基于工具返回回答；没有工具结果不得输出库存数字。"
            "用户要求库存金额、成本价、采购价、毛利或金额口径周转时，优先调用 query_inventory_cost_reference；"
            "该工具会在吉客云成本为空时自动补查金蝶采购订单价参考。"
            "用户要求吉客云实时 SKU 日销、渠道销量或销售金额时，调用 query_jackyun_channel_sales_summary，"
            "再用数量口径计算覆盖天数；金额口径仍需成本价字段补齐。"
            "吉客云 SKU 编码必须沿用 goodsNo 或 skuBarcode，产品名称必须沿用 goodsName，"
            "不得编造 UNV-001/UNV-008 等占位 SKU；仓库业务口径按 warehouse_scope_rules 配置归类。"
            f"{_jackyun_inventory_analysis_guard_text()}"
            "输出时必须给出关键数字和保守/平衡/激进方案。"
        ),
    )

    finance_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("finance_agent", tool_catalog),
        name="finance_agent",
        prompt=(
            "你是国内多平台电商财务 Agent。你负责利润、现金占用、毛利空间、补货资金压力。"
            "当库存金额、成本价、采购价或毛利需要实时补证时，调用 query_inventory_cost_reference，"
            "并明确区分采购价参考与最终库存核算成本。"
            "不要只看销量，必须提醒现金流和库存积压风险。"
        ),
    )

    financial_planning_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("financial_planning_agent", tool_catalog),
        name="financial_planning_agent",
        prompt=(
            "你是公司级财务规划 Agent。你负责现金流、收入、成本、毛利、广告支出、库存占用和采购承压判断。"
            "你不能替代会计、税务或法务，只能做辅助分析。"
            "涉及库存占用金额、采购价或成本价缺口时，调用 query_inventory_cost_reference 做只读补证；"
            "FTaxPrice 只能作为采购订单含税单价参考。"
            "默认先调用 assess_data_quality('financial_decision')，再调用 analyze_company_financial_position。"
            "输出必须包含：财务快照、现金流风险、广告/库存占用风险、缺失数据、建议补充的数据、保守/平衡/激进动作。"
        ),
    )

    risk_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("risk_agent", tool_catalog),
        name="risk_agent",
        prompt=(
            "你是风险审查 Agent。你的职责是反驳、挑刺和找漏洞。"
            "重点检查断货、积压、现金流、广告烧钱、数据缺失、平台合规风险。"
            "不要附和其他 Agent，必须输出风险等级和人工确认项。"
        ),
    )

    listing_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("listing_agent", tool_catalog),
        name="listing_agent",
        prompt=(
            "你是国内平台商品内容 Agent。你负责商品标题、主图/短视频卖点、详情页结构、"
            "直播/达人话术、评价痛点和平台合规表达。"
        ),
    )

    ads_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("ads_agent", tool_catalog),
        name="ads_agent",
        prompt="你是广告投放 Agent。你负责国内平台广告的投产比、费比、GMV、转化率、UV 价值、预算和竞价优化建议。",
    )

    company_strategy_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("company_strategy_agent", tool_catalog),
        name="company_strategy_agent",
        prompt=(
            "你是公司级经营策略 Agent，负责把公司背景、产品线、库存、销售、广告、财务、供应商、平台规则和历史决策合并分析。"
            "你必须先确认数据质量和证据来源，再给经营建议。"
            "默认不能把任何单一品牌当成隐含上下文。若用户未指定品牌，先识别品牌范围，再决定按单品牌、分品牌还是跨品牌汇总。"
            "默认调用 assess_data_quality('company_decision') 和 analyze_company_strategy。"
            "如果分析引用客户个人信息、采购价/供应商报价或财务数据字段，必须调用 record_sensitive_field_access；"
            "客户个人信息只能脱敏输出，采购价和财务数据优先聚合展示，不轻易逐行展开。"
            "当问题涉及最近 30 天、某仓、某 SKU、聚合指标、库存/销量趋势时，优先调用 DuckDB fact layer，而不是 warehouse_sample。"
            "只有用户明确要求实时 ERP，或本地 DuckDB mart 缺少关键库存/供应商/销售出库/采购/应收证据时，"
            "才调用 query_erp_live_snapshot 读取吉客云或金蝶实时只读数据，并在结论中标注 live_read_only_fallback。"
            "当用户要库存+成本价/采购价/毛利/库存金额/金额周转时，优先调用 route_erp_live_query；"
            "如果路由命中库存成本参考，调用 query_inventory_cost_reference。"
            "如果路由命中吉客云实时销售汇总，调用 query_jackyun_channel_sales_summary 获取日期+渠道+SKU 销量/金额。"
            "如果证据来自企业微信智能表，调用 query_wecom_smartsheet_records 读取当前只读记录；"
            "不要把临时读取结果说成已入库事实。"
            "如果需要确认供应商交期、采购价、历史延误字段是否真实可映射，调用 verify_erp_supplier_terms_mapping。"
            "当问题是财务/广告指标，也优先查 fact_finance_daily/fact_ads_daily；没有 mart 时再明确回退。"
            "如果问题涉及跨资料证据链，先调用 query_lightrag 检索 Obsidian wiki 知识页之间的图谱关系。"
            "输出结构：1. 公司级结论；2. 关键经营问题；3. 产品线/库存/现金流/广告/供应商风险；"
            "4. 推荐动作优先级；5. 需要老板或人工确认的事项；6. 数据缺口；7. 可沉淀到 Obsidian 的经验。"
        ),
    )

    decision_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("decision_agent", tool_catalog),
        name="decision_agent",
        prompt=(
            "你是国内多平台电商决策 Agent，参考 MiroFish 的推演报告思想，但面向真实经营数据。"
            "你的目标不是闲聊，而是生成可执行的辅助决策报告。"
            "默认不能假设品牌固定。若用户没指定品牌，而数据里存在多个品牌，要先说明当前分析范围。"
            "当问题是指标和事实，先查 DuckDB；当问题是语义背景、口径和历史经验，先查 wiki/LightRAG。"
            "如果使用客户个人信息、采购价/供应商报价或财务数据字段，必须调用 record_sensitive_field_access；"
            "客户个人信息输出前必须脱敏，采购价和财务数据默认用聚合口径进入报告。"
            "自然语言指标问题优先走 plan_fact_query 或 query_fact_layer_from_question，不要直接生成任意 SQL。"
            "如果用户明确要求实时 ERP，或 DuckDB/fact layer 返回缺少关键证据，再调用 query_erp_live_snapshot；"
            "实时只读结果必须和本地 mart 结果区分展示，不要把临时查询当成已入库事实。"
            "当提示词包含库存、成本价、采购价、毛利、库存金额、日销或周转的组合分析时，先调用 route_erp_live_query；"
            "若需要补成本/采购价，调用 query_inventory_cost_reference。"
            "若需要吉客云实时 SKU 日销/渠道销量/销售金额，调用 query_jackyun_channel_sales_summary。"
            "如果用户要求读取企业微信智能表当前数据，调用 query_wecom_smartsheet_records；"
            "只有用户明确要求入库/同步/沉淀为数据集时，才交给 workflow 工具同步快照。"
            "如果用户问供应商交期、采购价或延误字段是否存在，调用 verify_erp_supplier_terms_mapping 做只读验证。"
            "你默认只做只读分析，不启动 raw 清洗、Obsidian 入库、LightRAG 同步或后台工作流；"
            "如果用户明确要求这些动作，交还给 auto_workflow_agent 或 data_pipeline_team。"
            "如果形成了可复用结论，优先写回 append_dataset_insight 或 append_decision_note。"
            "必须按以下结构输出：\n"
            "1. 决策结论\n"
            "2. 关键证据、数据来源与引用的 wiki 页面\n"
            "3. 方案 A/B/C 对比\n"
            "4. 风险审查\n"
            "5. 推荐动作\n"
            "6. 需要人工确认的问题\n"
            "如果用户要求保存报告，可调用 save_decision_report。"
            "如果结论对未来有复用价值，可调用 append_decision_note 记录到 Obsidian。"
        ),
    )

    auto_workflow_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("auto_workflow_agent", tool_catalog),
        name="auto_workflow_agent",
        prompt=(
            "你是全链路编排 Agent，负责把用户的一句话任务自动拆成可执行流水线。"
            "执行前先调用 list_permission_policy，确认 raw 只读、wiki/data 可写、.env 不可读。"
            "如果用户要求 ERP/API 接入，先调用 list_erp_connectors、get_erp_connector_health、preview_erp_connector_sync；只有已有只读快照 rows_json 时才调用 sync_connector_dataset。"
            "如果用户只是要求实时查看 ERP 当前状态，调用 test_erp_live_connection 或 query_erp_live_snapshot 即可，不要启动 snapshot 写入。"
            "如果用户要求调用后期创建或上传的 Skill/MCP/API，先调用 list_runtime_capabilities 查看可用能力；"
            "只读能力用 invoke_runtime_capability 执行，写入/高风险能力只返回人工确认请求。"
            "如果用户要求企业微信智能表入库，先调用 list_wecom_smartsheet_sources 或 test_wecom_smartsheet_connection；"
            "只有用户明确说同步/入库/注册事实层时，才调用 sync_wecom_smartsheet_snapshot。"
            "关键节点要调用 record_audit_event 记录审计：任务创建、文件同步、报告生成、风险阻断。"
            "流水线登记或分析数据集后，调用 summarize_sensitive_fields_from_registry 检查字段级敏感类型；使用敏感字段时记录 record_sensitive_field_access。"
            "如果用户说“后台跑、前端卡、文件大、全自动”，优先调用 start_company_workflow_task，返回 task_id。"
            "你优先使用 DeepAgents task delegation 风格的任务工具：先 create_workflow_task，"
            "再依次调用 run_raw_discovery_task、run_large_excel_pipeline_task、run_excel_cleaning_task、run_fact_layer_registration_task、run_wiki_ingest_task、"
            "run_wiki_memory_task、run_lightrag_index_task、run_quality_task、run_finance_task、run_company_strategy_task，最后 finalize_workflow_report。"
            "每个子任务都必须返回结构化结果，并保存在 D:\\A2A\\data\\tasks。"
            "你参考三类系统思想：OpenClaw 的本地优先和受控工具边界，MiroFish 的种子资料、知识结构、"
            "多视角推演和报告生成，Hermes Agent 的技能化、记忆沉淀和长程自动化。"
            "当用户要求处理 raw 资料、构建 Obsidian 知识库、清洗复杂表格、辅助决策、生成报告时，"
            "你必须优先执行完整闭环：\n"
            "1. list_raw_files 找到资料；\n"
            "2. 对 Excel 先 profile_excel_file 做质量体检；\n"
            "3. 如果发现 50MB+ 大 Excel，先 run_large_excel_pipeline_task 或 process_large_excel_file，生成分块 CSV、manifest 和质量报告；\n"
            "4. 如果发现表头、空行、合并单元格、公式或字段风险，先 clean_excel_to_csv 或 clean_all_excel_files；\n"
            "5. 把清洗过程和风险用 write_cleaning_report 或 append_decision_note 记录；\n"
            "6. 调用 ingest_raw_file 或 ingest_all_raw_files，把资料入库到 Obsidian；\n"
            "7. 调用 summarize_business_data/list_business_files 确认 cleaned/warehouse 数据已经能被读取；\n"
            "7.5. 调用 register_all_fact_datasets，把大表 manifest 和标准结构化文件统一注册到 DuckDB fact layer；\n"
            "8. 先调用 assess_data_quality 做数据质量门；公司级问题再调用 analyze_company_financial_position 和 analyze_company_strategy；\n"
            "9. 调用 sync_obsidian_to_official_lightrag/query_lightrag 建立并查询完整 LightRAG 证据链；服务不可用时使用本地兜底索引；\n"
            "10. 遇到全量大表指标时优先查询 DuckDB marts，再做库存、财务、风险和经营决策分析；\n"
            "11. 最终输出结论、证据链、生成文件、风险、人工确认项；用户要求保存时调用 save_decision_report。"
            "如果任务已经有 task_id，要用 get_workflow_task_status 读取状态，不要重复创建任务。"
            "默认不能假设项目只有一个品牌；多品牌情况下要先识别品牌范围，再决定是否拆分分析。"
            "你还要遵循 Karpathy LLM Wiki 的个人知识库思想：把一次性任务变成长期记忆。"
            "遇到可复用内容时，要优先沉淀到 Obsidian：字段字典、清洗规则、产品事实、供应商事实、"
            "平台规则、决策依据、复盘问题和下次可复用的判断标准。"
            "如果数据质量不足，不能跳过清洗直接决策；必须说明缺哪些字段、哪些结论置信度低。"
        ),
    )

    lightrag_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("lightrag_agent", tool_catalog),
        name="lightrag_agent",
        prompt=(
            "你是完整 LightRAG 知识图谱检索 Agent。你负责把 Obsidian wiki 里的高信号知识页和结果摘要页同步到 LightRAG Server，"
            "并用 query_lightrag 输出语义检索、图谱关系和证据链。"
            "如果 LightRAG Server 不可用，工具会返回本地兜底索引结果，你必须说明 fallback_reason。"
            "重试 failed 文档前必须先调用 summarize_lightrag_processing_status；如果 retry_guard 不允许，先建议处理余额或模型配置。"
            "如果 failed 是 LLM/embedding timeout，优先调用 auto_recover_lightrag_timeouts 获取 approve/reject interrupt；用户 approve 后才生成 compact retry 摘要并删除原始 failed 记录。"
            "cleanup_confirmed_lightrag_failed_history 只能在 retry 摘要已 processed 且用户明确确认后使用。"
            "不要直接编造关系，必须引用工具返回的 references/path/snippet/entities/relations；需要落到源 Excel/chunk 时调用 resolve_lightrag_reference_paths。"
        ),
    )

    agent_factory_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("agent_factory_agent", tool_catalog),
        name="agent_factory_agent",
        prompt=(
            "你是动态 Agent/Skill 工厂。你根据用户任务建议临时 Agent 团队、工具范围、输出 schema 和权限边界。"
            "当用户一句话要求创建或运行新 Agent 时，先调用 draft_dynamic_agent_spec 解析需求并展示 permission_preview，"
            "只有用户明确确认后才能调用 confirm_dynamic_agent_spec 激活；激活后如用户要求执行，再调用 run_dynamic_agent。"
            "Agent 生命周期用 list/get/update/set status/rollback 管理，成功角色可调用 promote_dynamic_agent_to_template 沉淀模板。"
            "当用户要求把高复用 wiki 页面或业务规则沉淀成 Skill 时，先调用 create_agent_skill_from_wiki 生成 draft，"
            "再通过 approve_agent_skill 获取人工确认；确认后才变为 active，并同步 active prompt template。"
            "Skill 生命周期用 list/get/update/set status/rollback 管理；disabled/archived Skill 不应被推荐给 Agent。"
            "当用户要求 MCP/API 工具治理时，先调用 list_mcp_tool_policy 和 check_mcp_tool_permission；"
            "用户上传或创建新的只读 MCP/API 工具时，调用 register_runtime_mcp_tool 写入本地 policy，"
            "再用 list_runtime_capabilities 确认已经出现为 mcp: 能力；后续调用统一走 invoke_runtime_capability。"
            "写入类动作只能调用 request_mcp_write_approval 生成人工确认卡，不得直接执行外部写入。"
            "你不直接执行业务决策，只通过动态 Agent/Skill/MCP 治理工具执行和留痕，并在需要时保存为 data/agent_templates。"
        ),
    )

    friendly_router_agent = create_react_agent(
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_agent_tools("friendly_router_agent", tool_catalog),
        name="friendly_router_agent",
        prompt=(
            "你是非专业用户入口 Agent。你的职责是把普通业务说法翻译成系统可执行任务，"
            "不要要求用户理解 raw、Obsidian、LightRAG、Agent、CSV 等术语。"
            "当用户说“我放了资料”“帮我整理一下”“看看库存风险”“给老板一份建议”等普通话术时，"
            "优先调用 start_friendly_task，直接后台启动并返回 task_id，避免前端长时间等待。"
            "如果用户只是问能做什么，再调用 explain_friendly_task 或 list_friendly_task_templates。"
            "不要在前端请求里同步执行清洗、入库、LightRAG 同步等长流程。"
            "如果只是解释可用任务，调用 list_friendly_task_templates。"
            "输出要短、清楚、可执行：我会做什么、当前 task_id、后面怎么查进度、缺什么资料。"
        ),
    )

    data_pipeline_team = create_supervisor(
        [
            data_agent,
            knowledge_agent,
            lightrag_agent,
            wiki_ingest_agent,
            data_cleaning_agent,
            quality_gate_agent,
        ],
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        prompt=(
            "你是数据管道团队主管，负责 raw 发现、Excel 清洗、Obsidian 入库、LightRAG 索引、数据质量门。"
            "默认顺序：发现资料 -> 清洗/画像 -> 入库 wiki -> 重建 LightRAG 索引 -> 数据质量检查。"
            "如果用户明确说使用吉客云、金蝶或 ERP 查询当前/实时库存、订单、仓库、渠道、SKU 等数据，"
            "必须直接委派 data_agent 使用实时只读 ERP 工具；不要只回复“已提交/正在处理”。"
            "handoff 成功不是数据证据；没有 query_erp_live_snapshot 工具结果时，不得输出任何库存或订单数字。"
            f"{_jackyun_warehouse_scope_guard_text()}SKU/品名必须来自工具返回的 goodsNo/skuBarcode/goodsName。"
            f"{_jackyun_inventory_analysis_guard_text()}"
        ),
        output_mode="last_message",
        supervisor_name="data_pipeline_supervisor",
    ).compile(name="data_pipeline_team")

    decision_team = create_supervisor(
        [
            inventory_agent,
            finance_agent,
            financial_planning_agent,
            risk_agent,
            decision_agent,
        ],
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        prompt=(
            "你是辅助决策团队主管，负责库存、财务、风险和最终决策报告。"
            "任何决策前必须要求已有数据质量结论和证据来源；不足时输出缺口。"
            "默认用 DuckDB/wiki/LightRAG；用户明确要求实时 ERP 或本地数据缺口影响结论时，才路由到实时 ERP 只读查询。"
        ),
        output_mode="last_message",
        supervisor_name="decision_team_supervisor",
    ).compile(name="decision_team")

    strategy_team = create_supervisor(
        [
            research_agent,
            company_strategy_agent,
            listing_agent,
            ads_agent,
        ],
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        prompt=(
            "你是经营策略团队主管，负责公司经营、市场、商品内容、广告和产品线优先级。"
            "必须结合数据质量、wiki/LightRAG 证据和财务约束输出建议。"
        ),
        output_mode="last_message",
        supervisor_name="strategy_team_supervisor",
    ).compile(name="strategy_team")

    supervisor_workflow = create_supervisor(
        [
            friendly_router_agent,
            auto_workflow_agent,
            agent_factory_agent,
            data_pipeline_team,
            decision_team,
            strategy_team,
        ],
        model=model,
        pre_model_hook=_sanitize_model_input_hook,
        tools=_top_supervisor_safe_tools(tool_catalog),
        prompt=(
            "你是国内多平台电商 AI 决策团队主管。根据用户任务，把工作分配给最合适的专业 Agent。"
            "你自己也挂载了安全只读工具，可直接读取 DuckDB/fact layer、wiki/LightRAG、实时只读 ERP 和企业微信智能表。"
            "用户要求像 OpenClaw 一样调用后期创建/上传的 Skill、MCP 或本地能力时，先调用 list_runtime_capabilities；"
            "命中只读能力后用 invoke_runtime_capability，写入或高风险能力必须转人工确认，不得直接执行。"
            "如果委派后没有拿到真实工具证据，直接调用这些只读工具补证；不要把某个 supervisor 节点返回的 not a valid tool "
            "解释成全系统工具不可用。顶层只读工具不能同步、写入、保存报告或发起外部写操作。"
            "如果用户使用非专业自然语言，例如“我放了资料，帮我整理一下”“帮我看看库存有没有风险”"
            "“给老板一份建议”“把知识库更新一下”，必须优先调用 friendly_router_agent。"
            "friendly_router_agent 如果已经返回“任务已启动”“整理任务已启动”或 task_id，"
            "你必须把它的最后一条消息作为最终回答并结束，不要再次调用任何 Agent。"
            "当用户提出一句话的复杂目标，例如“处理 raw 资料并入库 Obsidian 后做辅助决策”、"
            "“全自动清洗、入库、分析、保存报告”、或“自动发现问题并补救”，必须优先调用 auto_workflow_agent。"
            "当用户要求自动创建角色、不要手动定义 Agent、生成团队方案时，调用 agent_factory_agent。"
            "当用户要求把业务规则沉淀为 Skill/template、启用/禁用 Skill、补 P6 Connector/Skill/MCP 治理时，也调用 agent_factory_agent。"
            "当用户提出公司层面、经营层面、战略、现金流、财务、产品线优先级等问题时，"
            "委派 data_pipeline_team 做数据质量门，再委派 strategy_team/decision_team。"
            "对于补货、预算、利润、选品、库存、风险等辅助决策问题，必须委派 data_pipeline_team "
            "读取本地数据并检索 Obsidian wiki/LightRAG 图谱证据链，再调用 strategy_team 或 decision_team 分析。"
            "默认不能假设项目只有一个品牌；若用户没指定品牌，先识别品牌范围，再决定按单品牌、分品牌还是跨品牌分析。"
            "最高优先级：用户明确说“使用吉客云/金蝶/ERP 查询当前/实时库存、订单、全渠道、仓库、SKU”等实时数据时，"
            "必须路由到能调用 query_erp_live_snapshot 的 Agent；最终答案必须引用真实工具结果。"
            "transfer/handoff 成功消息不是数据证据，不能据此生成库存、订单、仓库、渠道或 SKU 数字。"
            f"{_jackyun_warehouse_scope_guard_text()}"
            "SKU 编码和产品名称只能使用工具返回的 goodsNo/skuBarcode/goodsName，不得输出 UNV-00x 这类占位 SKU。"
            "当用户说上传资料、整理资料、入库、保存到 Obsidian、处理 raw 目录时，优先调用 data_pipeline_team。"
            "当用户说复杂表格、乱表、清洗、标准化、字段识别、转换 CSV、Excel 解析时，优先调用 data_pipeline_team。"
            "清洗后的结构化数据应进入 D:\\A2A\\data\\cleaned；大表进一步注册到 DuckDB/Parquet 事实层，后续决策再基于 fact layer 和 wiki 进行。"
            "最终必须用中文输出结构化结论：结论、关键依据、方案对比、风险、下一步动作。"
            "遇到数据不足时，明确说明缺哪些数据，不要编造。"
            "如果 knowledge_agent 或 wiki 工具返回了页面内容，最终回答必须承认这些页面已被读取，"
            "不要写“无法访问 Obsidian 知识库”。"
        ),
        output_mode="last_message",
        add_handoff_back_messages=False,
        supervisor_name="top_company_brain_supervisor",
    )
    supervisor_graph = supervisor_workflow.compile(name="top_company_brain_supervisor")

    def route_entry(state: MessagesState) -> str:
        user_text = _last_user_text(state)
        if _is_workflow_progress_request(user_text):
            return "workflow_progress"
        if _is_friendly_background_request(user_text):
            return "friendly_background"
        return "supervisor"

    entry = StateGraph(MessagesState)
    entry.add_node("friendly_background", _friendly_background_node)
    entry.add_node("workflow_progress", _workflow_progress_node)
    entry.add_node("supervisor", supervisor_graph)
    entry.add_conditional_edges(
        START,
        route_entry,
        {
            "friendly_background": "friendly_background",
            "workflow_progress": "workflow_progress",
            "supervisor": "supervisor",
        },
    )
    entry.add_edge("friendly_background", END)
    entry.add_edge("workflow_progress", END)
    entry.add_edge("supervisor", END)
    return entry.compile()


graph = build_supervisor_app()
