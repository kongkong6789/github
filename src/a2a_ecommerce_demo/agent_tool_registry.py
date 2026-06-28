from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass

Tool = Callable[..., object]


@dataclass(frozen=True)
class ToolEntry:
    name: str
    handler: str
    description: str
    group: str
    read_only: bool
    risk_level: str
    requires_confirmation: bool
    data_sources: tuple[str, ...]
    max_result_size: int
    availability_check: str
    owner_module: str


TOOL_REGISTRY_SCHEMA = "a2a_tool_registry_v2"
ALLOWED_TOOL_RISK_LEVELS = frozenset({"low", "medium", "high", "destructive"})
ALLOWED_TOOL_GROUPS = frozenset(
    {
        "read_fact",
        "read_knowledge",
        "write_local_state",
        "external_read",
        "external_write_request",
        "destructive_maintenance",
        "governance",
        "workflow",
    }
)
ALLOWED_TOOL_DATA_SOURCES = frozenset(
    {
        "DuckDB",
        "wiki",
        "LightRAG",
        "raw",
        "ERP_live_readonly",
        "WeCom_smartsheet",
        "audit",
        "tasks",
        "reports",
        "MCP_policy",
        "source_registry",
        "agent_reach",
        "agent_reach_public_web",
        "agent_reach_public_search",
        "agent_reach_public_video",
        "agent_reach_social",
        "reference_platform",
    }
)

AGENT_REACH_PUBLIC_READ_TOOLS: tuple[str, ...] = (
    "agent_reach_get_status",
    "agent_reach_read_public_web",
    "agent_reach_search_public_sources",
    "agent_reach_read_video_transcript",
)
AGENT_REACH_CONFIRMATION_TOOLS: tuple[str, ...] = (
    "agent_reach_read_logged_in_social",
)
AGENT_REACH_ALL_TOOLS: tuple[str, ...] = (
    *AGENT_REACH_PUBLIC_READ_TOOLS,
    *AGENT_REACH_CONFIRMATION_TOOLS,
)

TOP_SUPERVISOR_AGENT_NAME = "top_company_brain_supervisor"
TOP_SUPERVISOR_SAFE_READ_TOOLS: tuple[str, ...] = (
    "list_mcp_tool_policy",
    "check_mcp_tool_permission",
    "list_business_files",
    "summarize_business_data",
    "assess_data_quality",
    "summarize_brand_coverage",
    "list_registered_datasets",
    "list_runtime_capabilities",
    "invoke_runtime_capability",
    "list_fact_tables",
    "plan_fact_query",
    "query_fact_layer",
    "query_fact_layer_from_question",
    "query_inventory_anomalies",
    "query_inventory_history",
    "query_inventory_snapshot",
    "query_sales_history",
    "query_finance_history",
    "query_ads_history",
    "query_sku_snapshot",
    "analyze_company_financial_position",
    "analyze_company_strategy",
    "analyze_restock_decision",
    "assess_decision_risks",
    "list_erp_connectors",
    "get_erp_connector_health",
    "preview_erp_connector_sync",
    "list_erp_live_query_capabilities",
    "test_erp_live_connection",
    "route_erp_live_query",
    "query_erp_live_snapshot",
    "query_inventory_cost_reference",
    "query_jackyun_channel_sales_summary",
    "verify_erp_supplier_terms_mapping",
    "list_wecom_smartsheet_sources",
    "test_wecom_smartsheet_connection",
    "query_wecom_smartsheet_records",
    "list_wiki_pages",
    "search_wiki",
    "read_wiki_page",
    "summarize_lightrag_processing_status",
    "diagnose_lightrag_failures",
    "list_failed_lightrag_docs",
    "lightrag_server_status",
    "query_lightrag",
    "query_official_lightrag",
    "build_evidence_graph",
    "list_evidence_graph_nodes",
    "list_evidence_graph_edges",
    "list_lightrag_entities",
    "get_lightrag_entity",
    "list_sources",
    "get_source",
    "list_source_snapshots",
    "check_source_registry_health",
    "list_reference_platforms",
    "check_reference_platform_health",
    "route_knowledge_stack",
    *AGENT_REACH_ALL_TOOLS,
)


_LEGACY_AGENT_TOOL_ALLOWLISTS: dict[str, tuple[str, ...]] = {
    TOP_SUPERVISOR_AGENT_NAME: TOP_SUPERVISOR_SAFE_READ_TOOLS,
    "market_research_agent": ("search_competitors",),
    "data_agent": (
        "list_business_files",
        "summarize_business_data",
        "summarize_brand_coverage",
        "audit_fact_source_readiness",
        "register_all_fact_datasets",
        "list_registered_datasets",
        "list_fact_tables",
        "summarize_sensitive_fields_from_registry",
        "classify_sensitive_fields",
        "mask_sensitive_record",
        "record_sensitive_field_access",
        "list_erp_connectors",
        "get_erp_connector_health",
        "preview_erp_connector_sync",
        "list_erp_live_query_capabilities",
        "test_erp_live_connection",
        "route_erp_live_query",
        "query_erp_live_snapshot",
        "query_inventory_cost_reference",
        "query_jackyun_channel_sales_summary",
        "verify_erp_supplier_terms_mapping",
        "list_wecom_smartsheet_sources",
        "test_wecom_smartsheet_connection",
        "query_wecom_smartsheet_records",
        "plan_fact_query",
        "query_fact_layer",
        "query_fact_layer_from_question",
        "query_inventory_anomalies",
        "query_inventory_history",
        "query_inventory_snapshot",
        "query_sales_history",
        "query_finance_history",
        "query_ads_history",
        "query_sku_snapshot",
        "list_sources",
        "get_source",
        "list_source_snapshots",
        "check_source_registry_health",
        "list_reference_platforms",
        "check_reference_platform_health",
        "route_knowledge_stack",
        *AGENT_REACH_PUBLIC_READ_TOOLS,
    ),
    "knowledge_agent": (
        "list_wiki_pages",
        "search_wiki",
        "read_wiki_page",
        "ensure_wiki_knowledge_scaffold",
        "refresh_wiki_index",
        "append_wiki_log_event",
        "normalize_legacy_wiki_pages",
        "lint_wiki_knowledge_base",
        "archive_decision_to_wiki",
        "register_wiki_claim_evidence",
        "generate_wiki_review_questions",
        "append_decision_note",
        "append_dataset_insight",
        "append_durable_insight",
        "rebuild_lightrag_index",
        "sync_obsidian_to_official_lightrag",
        "summarize_lightrag_processing_status",
        "diagnose_lightrag_failures",
        "list_failed_lightrag_docs",
        "retry_failed_lightrag_docs",
        "auto_recover_lightrag_timeouts",
        "cleanup_confirmed_lightrag_failed_history",
        "lightrag_server_status",
        "record_audit_event",
        "query_lightrag",
        "query_official_lightrag",
        "resolve_lightrag_reference_paths",
        "build_evidence_graph",
        "list_evidence_graph_nodes",
        "list_evidence_graph_edges",
        "list_lightrag_entities",
        "get_lightrag_entity",
        "get_lightrag_track_status",
        "list_sources",
        "get_source",
        "list_source_snapshots",
        "list_reference_platforms",
        "check_reference_platform_health",
        "route_knowledge_stack",
        "query_external_platform_readonly",
        *AGENT_REACH_ALL_TOOLS,
    ),
    "wiki_ingest_agent": (
        "list_raw_files",
        "ingest_raw_file",
        "ingest_all_raw_files",
        "list_wiki_pages",
        "search_wiki",
        "rebuild_lightrag_index",
        "sync_obsidian_to_official_lightrag",
        "summarize_lightrag_processing_status",
        "diagnose_lightrag_failures",
        "list_failed_lightrag_docs",
        "retry_failed_lightrag_docs",
        "auto_recover_lightrag_timeouts",
        "append_durable_insight",
        "sync_source",
        "run_source_sync_workflow",
    ),
    "data_cleaning_agent": (
        "profile_excel_file",
        "profile_large_excel_file",
        "process_large_excel_file",
        "process_all_large_excel_files",
        "assess_large_excel_quality",
        "clean_excel_to_csv",
        "clean_all_excel_files",
        "write_cleaning_report",
        "sync_source",
        "run_source_sync_workflow",
    ),
    "quality_gate_agent": (
        "list_business_files",
        "summarize_business_data",
        "assess_data_quality",
        "profile_excel_file",
        "profile_large_excel_file",
        "assess_large_excel_quality",
        "summarize_sensitive_fields_from_registry",
        "classify_sensitive_fields",
        "record_sensitive_field_access",
        "search_wiki",
        "append_decision_note",
        "list_sources",
        "get_source",
        "list_source_snapshots",
        "check_source_registry_health",
        *AGENT_REACH_ALL_TOOLS,
    ),
    "inventory_agent": (
        "list_erp_live_query_capabilities",
        "test_erp_live_connection",
        "route_erp_live_query",
        "query_erp_live_snapshot",
        "query_inventory_cost_reference",
        "query_jackyun_channel_sales_summary",
        "verify_erp_supplier_terms_mapping",
        "query_inventory_anomalies",
        "query_sku_snapshot",
        "analyze_restock_decision",
        "simulate_decision_scenarios",
    ),
    "finance_agent": (
        "route_erp_live_query",
        "query_inventory_cost_reference",
        "query_sku_snapshot",
        "analyze_restock_decision",
        "simulate_decision_scenarios",
        "analyze_company_financial_position",
        "assess_data_quality",
    ),
    "financial_planning_agent": (
        "list_business_files",
        "summarize_business_data",
        "assess_data_quality",
        "route_erp_live_query",
        "query_inventory_cost_reference",
        "analyze_company_financial_position",
        "save_decision_report",
        "append_decision_note",
    ),
    "risk_agent": (
        "query_sku_snapshot",
        "assess_decision_risks",
        "simulate_decision_scenarios",
    ),
    "listing_agent": (),
    "ads_agent": ("analyze_ads",),
    "company_strategy_agent": (
        "list_business_files",
        "summarize_business_data",
        "assess_data_quality",
        "summarize_brand_coverage",
        "audit_fact_source_readiness",
        "register_all_fact_datasets",
        "list_registered_datasets",
        "list_fact_tables",
        "summarize_sensitive_fields_from_registry",
        "classify_sensitive_fields",
        "mask_sensitive_record",
        "record_sensitive_field_access",
        "list_erp_connectors",
        "get_erp_connector_health",
        "preview_erp_connector_sync",
        "list_erp_live_query_capabilities",
        "test_erp_live_connection",
        "route_erp_live_query",
        "query_erp_live_snapshot",
        "query_inventory_cost_reference",
        "query_jackyun_channel_sales_summary",
        "verify_erp_supplier_terms_mapping",
        "list_wecom_smartsheet_sources",
        "test_wecom_smartsheet_connection",
        "query_wecom_smartsheet_records",
        "plan_fact_query",
        "query_fact_layer",
        "query_fact_layer_from_question",
        "query_inventory_anomalies",
        "query_inventory_history",
        "query_inventory_snapshot",
        "query_sales_history",
        "query_finance_history",
        "query_ads_history",
        "analyze_company_financial_position",
        "analyze_company_strategy",
        "search_wiki",
        "read_wiki_page",
        "ensure_wiki_knowledge_scaffold",
        "refresh_wiki_index",
        "append_wiki_log_event",
        "normalize_legacy_wiki_pages",
        "lint_wiki_knowledge_base",
        "archive_decision_to_wiki",
        "register_wiki_claim_evidence",
        "generate_wiki_review_questions",
        "save_decision_report",
        "append_decision_note",
        "append_dataset_insight",
        "list_sources",
        "get_source",
        "list_source_snapshots",
        "check_source_registry_health",
        "get_workflow_task_status",
        "finalize_workflow_report",
        "generate_data_dictionary",
        "generate_cleaning_rules",
        "summarize_lightrag_processing_status",
        "diagnose_lightrag_failures",
        "list_failed_lightrag_docs",
        "query_lightrag",
        "query_official_lightrag",
        "build_evidence_graph",
        "list_evidence_graph_nodes",
        "list_evidence_graph_edges",
        "list_lightrag_entities",
        "get_lightrag_entity",
        "route_knowledge_stack",
        "list_reference_platforms",
        "check_reference_platform_health",
        *AGENT_REACH_ALL_TOOLS,
    ),
    "decision_agent": (
        "summarize_business_data",
        "assess_data_quality",
        "summarize_brand_coverage",
        "audit_fact_source_readiness",
        "register_all_fact_datasets",
        "list_registered_datasets",
        "list_fact_tables",
        "summarize_sensitive_fields_from_registry",
        "classify_sensitive_fields",
        "mask_sensitive_record",
        "record_sensitive_field_access",
        "list_erp_connectors",
        "get_erp_connector_health",
        "preview_erp_connector_sync",
        "list_erp_live_query_capabilities",
        "test_erp_live_connection",
        "route_erp_live_query",
        "query_erp_live_snapshot",
        "query_inventory_cost_reference",
        "query_jackyun_channel_sales_summary",
        "verify_erp_supplier_terms_mapping",
        "list_wecom_smartsheet_sources",
        "test_wecom_smartsheet_connection",
        "query_wecom_smartsheet_records",
        "plan_fact_query",
        "query_fact_layer",
        "query_fact_layer_from_question",
        "query_inventory_anomalies",
        "query_inventory_history",
        "query_inventory_snapshot",
        "query_sales_history",
        "query_finance_history",
        "query_ads_history",
        "analyze_company_financial_position",
        "analyze_company_strategy",
        "summarize_lightrag_processing_status",
        "diagnose_lightrag_failures",
        "list_failed_lightrag_docs",
        "lightrag_server_status",
        "query_lightrag",
        "query_official_lightrag",
        "build_evidence_graph",
        "list_evidence_graph_nodes",
        "list_evidence_graph_edges",
        "list_lightrag_entities",
        "get_lightrag_entity",
        "get_workflow_task_status",
        "list_workflow_tasks",
        "finalize_workflow_report",
        "search_wiki",
        "read_wiki_page",
        "ensure_wiki_knowledge_scaffold",
        "refresh_wiki_index",
        "append_wiki_log_event",
        "normalize_legacy_wiki_pages",
        "lint_wiki_knowledge_base",
        "archive_decision_to_wiki",
        "register_wiki_claim_evidence",
        "generate_wiki_review_questions",
        "query_sku_snapshot",
        "analyze_restock_decision",
        "simulate_decision_scenarios",
        "assess_decision_risks",
        "save_decision_report",
        "append_decision_note",
        "append_dataset_insight",
        "list_sources",
        "get_source",
        "list_source_snapshots",
        "check_source_registry_health",
        "route_knowledge_stack",
        "list_reference_platforms",
        "check_reference_platform_health",
        "query_external_platform_readonly",
        *AGENT_REACH_ALL_TOOLS,
    ),
    "auto_workflow_agent": (
        "list_permission_policy",
        "check_path_permission",
        "record_audit_event",
        "list_audit_events",
        "list_mcp_tool_policy",
        "check_mcp_tool_permission",
        "request_mcp_write_approval",
        "record_mcp_tool_audit",
        "suggest_agent_team",
        "save_agent_skill_template",
        "list_agent_skill_templates",
        "create_agent_skill_from_wiki",
        "approve_agent_skill",
        "set_agent_skill_status",
        "update_agent_skill",
        "rollback_agent_skill",
        "get_agent_skill",
        "list_agent_skills",
        "list_raw_files",
        "register_source",
        "list_sources",
        "get_source",
        "set_source_status",
        "sync_source",
        "run_source_sync_workflow",
        "list_source_snapshots",
        "check_source_registry_health",
        "list_reference_platforms",
        "check_reference_platform_health",
        "route_knowledge_stack",
        "query_external_platform_readonly",
        "create_workflow_task",
        "get_workflow_task_status",
        "list_workflow_tasks",
        "recover_workflow_queue",
        "cancel_workflow_task",
        "start_company_workflow_task",
        "run_full_company_workflow",
        "run_raw_discovery_task",
        "run_excel_cleaning_task",
        "run_wiki_ingest_task",
        "run_wiki_memory_task",
        "run_lightrag_index_task",
        "run_quality_task",
        "run_finance_task",
        "run_company_strategy_task",
        "run_large_excel_pipeline_task",
        "run_fact_layer_registration_task",
        "finalize_workflow_report",
        "profile_excel_file",
        "profile_large_excel_file",
        "process_large_excel_file",
        "process_all_large_excel_files",
        "assess_large_excel_quality",
        "clean_excel_to_csv",
        "clean_all_excel_files",
        "write_cleaning_report",
        "ingest_raw_file",
        "ingest_all_raw_files",
        "list_wiki_pages",
        "search_wiki",
        "read_wiki_page",
        "ensure_wiki_knowledge_scaffold",
        "refresh_wiki_index",
        "append_wiki_log_event",
        "normalize_legacy_wiki_pages",
        "lint_wiki_knowledge_base",
        "archive_decision_to_wiki",
        "register_wiki_claim_evidence",
        "generate_wiki_review_questions",
        "rebuild_lightrag_index",
        "sync_obsidian_to_official_lightrag",
        "summarize_lightrag_processing_status",
        "diagnose_lightrag_failures",
        "list_failed_lightrag_docs",
        "retry_failed_lightrag_docs",
        "auto_recover_lightrag_timeouts",
        "lightrag_server_status",
        "query_lightrag",
        "query_official_lightrag",
        "build_evidence_graph",
        "list_evidence_graph_nodes",
        "list_evidence_graph_edges",
        "list_lightrag_entities",
        "get_lightrag_entity",
        "summarize_business_data",
        "list_business_files",
        "assess_data_quality",
        "summarize_brand_coverage",
        "audit_fact_source_readiness",
        "register_all_fact_datasets",
        "list_registered_datasets",
        "list_fact_tables",
        "summarize_sensitive_fields_from_registry",
        "classify_sensitive_fields",
        "mask_sensitive_record",
        "record_sensitive_field_access",
        "list_erp_connectors",
        "get_erp_connector_health",
        "preview_erp_connector_sync",
        "sync_connector_dataset",
        "list_erp_live_query_capabilities",
        "test_erp_live_connection",
        "route_erp_live_query",
        "query_erp_live_snapshot",
        "query_inventory_cost_reference",
        "query_jackyun_channel_sales_summary",
        "verify_erp_supplier_terms_mapping",
        "list_wecom_smartsheet_sources",
        "test_wecom_smartsheet_connection",
        "query_wecom_smartsheet_records",
        "sync_wecom_smartsheet_snapshot",
        "plan_fact_query",
        "query_fact_layer",
        "query_fact_layer_from_question",
        "query_inventory_anomalies",
        "query_inventory_history",
        "query_sales_history",
        "query_finance_history",
        "query_ads_history",
        "analyze_company_financial_position",
        "analyze_company_strategy",
        "query_sku_snapshot",
        "analyze_restock_decision",
        "simulate_decision_scenarios",
        "assess_decision_risks",
        "save_decision_report",
        "append_decision_note",
        "append_dataset_insight",
        "list_sources",
        "get_source",
        "list_source_snapshots",
        "check_source_registry_health",
        "list_reference_platforms",
        "check_reference_platform_health",
        "route_knowledge_stack",
        "query_external_platform_readonly",
    ),
    "lightrag_agent": (
        "lightrag_server_status",
        "sync_obsidian_to_official_lightrag",
        "summarize_lightrag_processing_status",
        "diagnose_lightrag_failures",
        "list_failed_lightrag_docs",
        "retry_failed_lightrag_docs",
        "auto_recover_lightrag_timeouts",
        "cleanup_confirmed_lightrag_failed_history",
        "rebuild_lightrag_index",
        "query_lightrag",
        "query_official_lightrag",
        "resolve_lightrag_reference_paths",
        "list_lightrag_entities",
        "get_lightrag_entity",
        "get_lightrag_track_status",
        "record_audit_event",
        "search_wiki",
        "read_wiki_page",
    ),
    "agent_factory_agent": (
        "suggest_agent_team",
        "draft_dynamic_agent_spec",
        "draft_dynamic_agent_spec_from_template",
        "confirm_dynamic_agent_spec",
        "run_dynamic_agent",
        "update_dynamic_agent_spec",
        "set_dynamic_agent_status",
        "rollback_dynamic_agent",
        "promote_dynamic_agent_to_template",
        "list_dynamic_agents",
        "get_dynamic_agent",
        "save_agent_skill_template",
        "save_wiki_page_as_prompt_template",
        "list_agent_skill_templates",
        "create_agent_skill_from_wiki",
        "approve_agent_skill",
        "set_agent_skill_status",
        "update_agent_skill",
        "rollback_agent_skill",
        "get_agent_skill",
        "list_agent_skills",
        "list_permission_policy",
        "list_mcp_tool_policy",
        "check_mcp_tool_permission",
        "request_mcp_write_approval",
        "record_mcp_tool_audit",
        "list_erp_connectors",
        "get_erp_connector_health",
        "preview_erp_connector_sync",
        "list_erp_live_query_capabilities",
        "test_erp_live_connection",
        "route_erp_live_query",
        "query_erp_live_snapshot",
        "query_inventory_cost_reference",
        "query_jackyun_channel_sales_summary",
        "verify_erp_supplier_terms_mapping",
        "list_wecom_smartsheet_sources",
        "test_wecom_smartsheet_connection",
        "query_wecom_smartsheet_records",
        "list_sources",
        "get_source",
        "list_source_snapshots",
        "list_reference_platforms",
        "check_reference_platform_health",
        "route_knowledge_stack",
        "query_external_platform_readonly",
    ),
    "friendly_router_agent": (
        "explain_friendly_task",
        "start_friendly_task",
        "list_friendly_task_templates",
        "start_company_workflow_task",
        "get_workflow_task_status",
        "list_workflow_tasks",
        "list_permission_policy",
        "record_audit_event",
    ),
}

READ_ONLY_ANALYSIS_AGENTS = {"company_strategy_agent", "decision_agent"}
READ_ONLY_AGENT_NAMES = READ_ONLY_ANALYSIS_AGENTS | {
    "ads_agent",
    "data_agent",
    "finance_agent",
    "financial_planning_agent",
    "inventory_agent",
    "market_research_agent",
    "quality_gate_agent",
    "risk_agent",
    TOP_SUPERVISOR_AGENT_NAME,
}
WRITE_OR_BACKGROUND_TOOLS = {
    "auto_recover_lightrag_timeouts",
    "cancel_workflow_task",
    "clean_all_excel_files",
    "clean_excel_to_csv",
    "create_workflow_task",
    "approve_agent_skill",
    "create_agent_skill_from_wiki",
    "ingest_all_raw_files",
    "ingest_raw_file",
    "process_all_large_excel_files",
    "process_large_excel_file",
    "request_mcp_write_approval",
    "rollback_agent_skill",
    "rebuild_lightrag_index",
    "record_mcp_tool_audit",
    "retry_failed_lightrag_docs",
    "recover_workflow_queue",
    "run_fact_layer_registration_task",
    "run_full_company_workflow",
    "run_large_excel_pipeline_task",
    "set_agent_skill_status",
    "start_company_workflow_task",
    "register_source",
    "set_source_status",
    "sync_connector_dataset",
    "sync_source",
    "run_source_sync_workflow",
    "sync_wecom_smartsheet_snapshot",
    "sync_obsidian_to_official_lightrag",
    "update_agent_skill",
}

_KNOWLEDGE_TOOL_HINTS = ("wiki", "lightrag", "durable_insight", "evidence_graph")
_FACT_TOOL_HINTS = (
    "ads",
    "business",
    "company_financial",
    "company_strategy",
    "data_quality",
    "fact",
    "finance",
    "inventory",
    "large_excel_quality",
    "registered_datasets",
    "restock",
    "sales",
    "sku",
)
_WORKFLOW_TOOL_HINTS = (
    "friendly_task",
    "workflow",
    "run_",
    "start_",
    "recover_workflow_queue",
    "cancel_workflow_task",
    "dynamic_agent",
)
_GOVERNANCE_TOOL_HINTS = (
    "agent_skill",
    "audit",
    "capability",
    "mcp",
    "permission",
    "sensitive",
    "template",
)
_DESTRUCTIVE_TOOL_NAMES = {
    "cleanup_confirmed_lightrag_failed_history",
    "rollback_agent_skill",
    "rollback_dynamic_agent",
}
_CONFIRMATION_TOOL_NAMES = WRITE_OR_BACKGROUND_TOOLS | _DESTRUCTIVE_TOOL_NAMES | {
    *AGENT_REACH_CONFIRMATION_TOOLS,
    "approve_agent_skill",
    "cancel_workflow_task",
    "confirm_dynamic_agent_spec",
    "promote_dynamic_agent_to_template",
    "register_runtime_mcp_tool",
    "request_mcp_write_approval",
    "rollback_dynamic_agent",
    "run_company_strategy_task",
    "run_excel_cleaning_task",
    "run_finance_task",
    "run_lightrag_index_task",
    "run_quality_task",
    "run_raw_discovery_task",
    "run_wiki_ingest_task",
    "run_wiki_memory_task",
    "set_dynamic_agent_status",
    "start_friendly_task",
    "update_dynamic_agent_spec",
}
_LOCAL_WRITE_TOOL_NAMES = {
    "append_dataset_insight",
    "append_decision_note",
    "append_durable_insight",
    "append_wiki_log_event",
    "archive_decision_to_wiki",
    "clean_all_excel_files",
    "clean_excel_to_csv",
    "ensure_wiki_knowledge_scaffold",
    "generate_cleaning_rules",
    "generate_data_dictionary",
    "ingest_all_raw_files",
    "ingest_raw_file",
    "mask_sensitive_record",
    "normalize_legacy_wiki_pages",
    "process_all_large_excel_files",
    "process_large_excel_file",
    "rebuild_lightrag_index",
    "refresh_wiki_index",
    "register_wiki_claim_evidence",
    "record_audit_event",
    "record_mcp_tool_audit",
    "record_sensitive_field_access",
    "register_runtime_mcp_tool",
    "register_all_fact_datasets",
    "retry_failed_lightrag_docs",
    "save_agent_skill_template",
    "save_decision_report",
    "save_wiki_page_as_prompt_template",
    "sync_connector_dataset",
    "register_source",
    "set_source_status",
    "sync_source",
    "run_source_sync_workflow",
    "sync_wecom_smartsheet_snapshot",
    "sync_obsidian_to_official_lightrag",
    "write_cleaning_report",
}

RUNTIME_CAPABILITY_READ_TOOLS = (
    "list_runtime_capabilities",
    "invoke_runtime_capability",
)
RUNTIME_CAPABILITY_ADMIN_TOOLS = ("register_runtime_mcp_tool",)
RUNTIME_CAPABILITY_READ_AGENTS = {
    TOP_SUPERVISOR_AGENT_NAME,
    "data_agent",
    "inventory_agent",
    "company_strategy_agent",
    "decision_agent",
    "auto_workflow_agent",
    "agent_factory_agent",
}
RUNTIME_CAPABILITY_ADMIN_AGENTS = {"auto_workflow_agent", "agent_factory_agent"}


def _all_tool_names() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                tool
                for allowlist in _LEGACY_AGENT_TOOL_ALLOWLISTS.values()
                for tool in allowlist
            }
            | set(RUNTIME_CAPABILITY_READ_TOOLS)
            | set(RUNTIME_CAPABILITY_ADMIN_TOOLS)
        )
    )


def _has_any_hint(tool_name: str, hints: tuple[str, ...]) -> bool:
    return any(hint in tool_name for hint in hints)


def _infer_group(tool_name: str) -> str:
    if tool_name.startswith("agent_reach_"):
        return "external_read"
    if tool_name in RUNTIME_CAPABILITY_READ_TOOLS:
        return "governance"
    if tool_name in {"sync_source", "run_source_sync_workflow"}:
        return "workflow"
    if tool_name in {"register_source", "set_source_status"}:
        return "write_local_state"
    if tool_name in {"list_sources", "get_source", "list_source_snapshots", "check_source_registry_health"}:
        return "governance"
    if tool_name in _DESTRUCTIVE_TOOL_NAMES:
        return "destructive_maintenance"
    if tool_name == "request_mcp_write_approval":
        return "external_write_request"
    if _has_any_hint(tool_name, _WORKFLOW_TOOL_HINTS):
        return "workflow"
    if tool_name in _LOCAL_WRITE_TOOL_NAMES:
        return "write_local_state"
    if tool_name.startswith(("list_erp", "get_erp", "preview_erp", "test_erp", "route_erp", "query_erp", "verify_erp")):
        return "external_read"
    if tool_name.startswith(("list_reference", "check_reference", "route_knowledge")):
        return "external_read"
    if tool_name == "query_external_platform_readonly":
        return "external_read"
    if tool_name in {"query_inventory_cost_reference", "query_jackyun_channel_sales_summary"}:
        return "external_read"
    if tool_name.startswith(("list_wecom", "test_wecom", "query_wecom")):
        return "external_read"
    if tool_name == "search_competitors":
        return "external_read"
    if _has_any_hint(tool_name, _GOVERNANCE_TOOL_HINTS):
        return "governance"
    if _has_any_hint(tool_name, _KNOWLEDGE_TOOL_HINTS):
        return "read_knowledge"
    if _has_any_hint(tool_name, _FACT_TOOL_HINTS):
        return "read_fact"
    if tool_name.startswith(("list_", "get_", "query_", "search_", "summarize_", "assess_", "profile_", "analyze_", "plan_")):
        return "read_fact"
    return "governance"


def _infer_data_sources(tool_name: str, group: str) -> tuple[str, ...]:
    if tool_name == "query_jackyun_channel_sales_summary":
        return ("ERP_live_readonly",)
    if tool_name in RUNTIME_CAPABILITY_READ_TOOLS or tool_name in RUNTIME_CAPABILITY_ADMIN_TOOLS:
        return ("MCP_policy", "wiki", "audit")
    if tool_name == "agent_reach_get_status":
        return ("agent_reach",)
    if tool_name == "agent_reach_read_public_web":
        return ("agent_reach_public_web",)
    if tool_name == "agent_reach_search_public_sources":
        return ("agent_reach_public_search",)
    if tool_name == "agent_reach_read_video_transcript":
        return ("agent_reach_public_video",)
    if tool_name == "agent_reach_read_logged_in_social":
        return ("agent_reach_social",)
    sources: list[str] = []
    if group == "read_fact" or _has_any_hint(tool_name, _FACT_TOOL_HINTS):
        sources.append("DuckDB")
    if group in {"read_knowledge", "write_local_state"} or _has_any_hint(tool_name, _KNOWLEDGE_TOOL_HINTS):
        if "wiki" in tool_name or "decision_note" in tool_name or "dataset_insight" in tool_name:
            sources.append("wiki")
        if "lightrag" in tool_name:
            sources.append("LightRAG")
        if "evidence_graph" in tool_name:
            sources.extend(["DuckDB", "wiki", "LightRAG", "audit", "tasks", "reports"])
    if "raw" in tool_name or "excel" in tool_name or "clean" in tool_name:
        sources.append("raw")
    if "erp" in tool_name or "connector" in tool_name or "jackyun" in tool_name:
        sources.append("ERP_live_readonly")
    if "wecom" in tool_name:
        sources.append("WeCom_smartsheet")
    if "audit" in tool_name or "sensitive" in tool_name:
        sources.append("audit")
    if "task" in tool_name or "workflow" in tool_name or tool_name.startswith(("run_", "start_", "recover_", "cancel_")):
        sources.append("tasks")
    if "report" in tool_name or "dictionary" in tool_name or "rules" in tool_name:
        sources.append("reports")
    if "mcp" in tool_name or "permission" in tool_name:
        sources.append("MCP_policy")
    if "source" in tool_name:
        sources.append("source_registry")
        if tool_name in {"sync_source", "run_source_sync_workflow"}:
            sources.extend(["raw", "tasks", "audit", "wiki"])
    if tool_name.startswith(("list_reference", "check_reference", "route_knowledge", "query_external_platform")):
        sources.append("reference_platform")
    if not sources:
        sources.append("DuckDB" if group == "read_fact" else "audit" if group == "governance" else "wiki")
    return tuple(dict.fromkeys(source for source in sources if source in ALLOWED_TOOL_DATA_SOURCES))


def _infer_owner_module(tool_name: str, group: str) -> str:
    if tool_name.startswith(("list_reference", "check_reference", "route_knowledge", "query_external_platform")):
        return "platform_integration_tools"
    if tool_name in RUNTIME_CAPABILITY_READ_TOOLS or tool_name in RUNTIME_CAPABILITY_ADMIN_TOOLS:
        return "runtime_capability_tools"
    if tool_name.startswith("agent_reach_"):
        return "agent_reach_tools"
    if "dynamic_agent" in tool_name:
        return "dynamic_agent_hub"
    if tool_name in {
        "append_wiki_log_event",
        "archive_decision_to_wiki",
        "ensure_wiki_knowledge_scaffold",
        "generate_wiki_review_questions",
        "lint_wiki_knowledge_base",
        "normalize_legacy_wiki_pages",
        "refresh_wiki_index",
        "register_wiki_claim_evidence",
    }:
        return "wiki_lifecycle_tools"
    if "mcp" in tool_name or "permission" in tool_name:
        return "mcp_governance_tools"
    if "source" in tool_name:
        return "source_registry_tools"
    if "agent_skill" in tool_name or "template" in tool_name:
        return "skill_registry_tools"
    if "wecom" in tool_name:
        return "wecom_smartsheet_tools"
    if (
        "erp" in tool_name
        or "connector" in tool_name
        or tool_name in {"query_inventory_cost_reference", "query_jackyun_channel_sales_summary"}
    ):
        return "connector_live_tools"
    if "lightrag" in tool_name:
        return "lightrag_tools"
    if "evidence_graph" in tool_name:
        return "evidence_graph_tools"
    if "wiki" in tool_name or "raw" in tool_name or "decision_note" in tool_name or "dataset_insight" in tool_name:
        return "knowledge_tools"
    if "excel" in tool_name or "clean" in tool_name:
        return "large_excel_tools"
    if "workflow" in tool_name or "task" in tool_name or tool_name.startswith(("run_", "start_", "recover_", "cancel_")):
        return "task_delegation_tools"
    if "audit" in tool_name or "sensitive" in tool_name:
        return "enterprise_audit_tools"
    if group == "read_fact":
        return "business_tools"
    return "supervisor_app"


def _infer_risk_level(tool_name: str, group: str, requires_confirmation: bool) -> str:
    if group == "destructive_maintenance":
        return "destructive"
    if group == "external_write_request":
        return "high"
    if tool_name in {
        "cancel_workflow_task",
        "recover_workflow_queue",
        "sync_source",
        "run_source_sync_workflow",
        "sync_connector_dataset",
        "sync_wecom_smartsheet_snapshot",
    }:
        return "high"
    if tool_name in AGENT_REACH_CONFIRMATION_TOOLS:
        return "medium"
    if requires_confirmation or group in {"workflow", "write_local_state"}:
        return "medium"
    return "low"


def _description_for(tool_name: str, group: str) -> str:
    labels = {
        "read_fact": "Read structured business facts",
        "read_knowledge": "Read wiki or LightRAG knowledge",
        "write_local_state": "Write local project state",
        "external_read": "Read approved external connector data",
        "external_write_request": "Request approval for external write",
        "destructive_maintenance": "Run destructive or rollback maintenance",
        "governance": "Inspect or update governance metadata",
        "workflow": "Coordinate background workflow state",
    }
    if tool_name.startswith("agent_reach_"):
        if tool_name == "agent_reach_get_status":
            return "Inspect Agent-Reach public research channel status."
        if tool_name == "agent_reach_read_logged_in_social":
            return "Read logged-in public social content via Agent-Reach after human confirmation."
        return "Read public internet research material via Agent-Reach."
    return f"{labels[group]} via `{tool_name}`."


def _make_tool_entry(tool_name: str) -> ToolEntry:
    group = _infer_group(tool_name)
    requires_confirmation = tool_name in _CONFIRMATION_TOOL_NAMES or group in {
        "destructive_maintenance",
        "external_write_request",
    }
    risk_level = _infer_risk_level(tool_name, group, requires_confirmation)
    return ToolEntry(
        name=tool_name,
        handler=tool_name,
        description=_description_for(tool_name, group),
        group=group,
        read_only=group in {"read_fact", "read_knowledge", "external_read"} or (
            group == "governance" and tool_name.startswith(("check_", "get_", "list_"))
        )
        or tool_name == "invoke_runtime_capability",
        risk_level=risk_level,
        requires_confirmation=requires_confirmation,
        data_sources=_infer_data_sources(tool_name, group),
        max_result_size=50000 if group in {"read_fact", "read_knowledge", "external_read"} else 20000,
        availability_check="runtime_catalog",
        owner_module=_infer_owner_module(tool_name, group),
    )


TOOL_REGISTRY: dict[str, ToolEntry] = {tool_name: _make_tool_entry(tool_name) for tool_name in _all_tool_names()}
TOOL_GROUPS: dict[str, tuple[str, ...]] = {
    group: tuple(name for name in _all_tool_names() if TOOL_REGISTRY[name].group == group)
    for group in sorted(ALLOWED_TOOL_GROUPS)
}

AGENT_TOOL_GROUPS: dict[str, tuple[str, ...]] = {
    TOP_SUPERVISOR_AGENT_NAME: ("read_fact", "read_knowledge", "external_read", "governance"),
    "market_research_agent": ("external_read",),
    "data_agent": ("read_fact", "external_read", "governance"),
    "knowledge_agent": ("read_knowledge",),
    "wiki_ingest_agent": ("read_knowledge", "write_local_state"),
    "data_cleaning_agent": ("read_fact", "write_local_state"),
    "quality_gate_agent": ("read_fact", "read_knowledge", "governance"),
    "inventory_agent": ("read_fact", "external_read"),
    "finance_agent": ("read_fact",),
    "financial_planning_agent": ("read_fact", "write_local_state"),
    "risk_agent": ("read_fact",),
    "listing_agent": ("read_fact",),
    "ads_agent": ("read_fact",),
    "company_strategy_agent": ("read_fact", "read_knowledge", "external_read", "governance"),
    "decision_agent": ("read_fact", "read_knowledge", "external_read", "governance", "workflow"),
    "auto_workflow_agent": tuple(sorted(ALLOWED_TOOL_GROUPS)),
    "lightrag_agent": ("read_knowledge", "write_local_state", "destructive_maintenance", "governance"),
    "agent_factory_agent": ("external_read", "external_write_request", "governance", "workflow", "write_local_state"),
    "friendly_router_agent": ("governance", "workflow"),
}

AGENT_TOOL_EXPLICIT_TOOLS: dict[str, tuple[str, ...]] = {
    agent_name: tuple(
        tool_name
        for tool_name in allowlist
        if TOOL_REGISTRY[tool_name].group not in AGENT_TOOL_GROUPS.get(agent_name, ())
    )
    for agent_name, allowlist in _LEGACY_AGENT_TOOL_ALLOWLISTS.items()
}


def _build_agent_allowlists() -> dict[str, tuple[str, ...]]:
    allowlists: dict[str, tuple[str, ...]] = {}
    for agent_name, legacy_allowlist in _LEGACY_AGENT_TOOL_ALLOWLISTS.items():
        runtime_tools: tuple[str, ...] = ()
        if agent_name in RUNTIME_CAPABILITY_READ_AGENTS:
            runtime_tools += RUNTIME_CAPABILITY_READ_TOOLS
        if agent_name in RUNTIME_CAPABILITY_ADMIN_AGENTS:
            runtime_tools += RUNTIME_CAPABILITY_ADMIN_TOOLS
        combined_allowlist = tuple(dict.fromkeys((*legacy_allowlist, *runtime_tools)))
        allowed_groups = set(AGENT_TOOL_GROUPS.get(agent_name, ()))
        explicit_tools = set(AGENT_TOOL_EXPLICIT_TOOLS.get(agent_name, ())) | set(runtime_tools)
        allowlists[agent_name] = tuple(
            tool_name
            for tool_name in combined_allowlist
            if TOOL_REGISTRY[tool_name].group in allowed_groups or tool_name in explicit_tools
        )
    return allowlists


AGENT_TOOL_ALLOWLISTS = _build_agent_allowlists()


def _validate_tool_entry(entry: ToolEntry) -> None:
    if entry.name != entry.handler:
        raise ValueError(f"{entry.name} handler must point at the registered tool name.")
    if entry.group not in ALLOWED_TOOL_GROUPS:
        raise ValueError(f"{entry.name} has invalid group: {entry.group}")
    if entry.risk_level not in ALLOWED_TOOL_RISK_LEVELS:
        raise ValueError(f"{entry.name} has invalid risk_level: {entry.risk_level}")
    if not entry.data_sources or not set(entry.data_sources).issubset(ALLOWED_TOOL_DATA_SOURCES):
        raise ValueError(f"{entry.name} has invalid data_sources: {entry.data_sources}")
    if not entry.description or not entry.owner_module or not entry.availability_check:
        raise ValueError(f"{entry.name} has incomplete registry metadata.")
    if entry.max_result_size <= 0:
        raise ValueError(f"{entry.name} max_result_size must be positive.")
    if entry.group in {"external_write_request", "destructive_maintenance"} and not entry.requires_confirmation:
        raise ValueError(f"{entry.name} requires confirmation for {entry.group}.")
    if entry.risk_level in {"high", "destructive"} and not entry.requires_confirmation:
        raise ValueError(f"{entry.name} requires confirmation for {entry.risk_level} risk.")


def resolve_agent_tool_entries(agent_name: str) -> list[ToolEntry]:
    allowlist = AGENT_TOOL_ALLOWLISTS[agent_name]
    return [TOOL_REGISTRY[tool_name] for tool_name in allowlist]


def resolve_direct_agent_tool_entries(agent_name: str) -> list[ToolEntry]:
    return [entry for entry in resolve_agent_tool_entries(agent_name) if not entry.requires_confirmation]


def resolve_direct_agent_tools(agent_name: str, catalog: Mapping[str, Tool], *, strict: bool = False) -> list[Tool]:
    entries = resolve_direct_agent_tool_entries(agent_name)
    missing = [entry.handler for entry in entries if entry.handler not in catalog]
    if strict and missing:
        raise KeyError(f"{agent_name} references unknown tools: {', '.join(missing)}")
    return [catalog[entry.handler] for entry in entries if entry.handler in catalog]


def export_tool_registry_payload() -> dict[str, object]:
    visible_agents: dict[str, list[str]] = {tool_name: [] for tool_name in TOOL_REGISTRY}
    for agent_name, allowlist in AGENT_TOOL_ALLOWLISTS.items():
        for tool_name in allowlist:
            visible_agents[tool_name].append(agent_name)

    return {
        "schema": TOOL_REGISTRY_SCHEMA,
        "risk_levels": sorted(ALLOWED_TOOL_RISK_LEVELS),
        "groups": sorted(ALLOWED_TOOL_GROUPS),
        "data_sources": sorted(ALLOWED_TOOL_DATA_SOURCES),
        "summary": {
            "tool_count": len(TOOL_REGISTRY),
            "read_only_count": sum(1 for entry in TOOL_REGISTRY.values() if entry.read_only),
            "write_count": sum(1 for entry in TOOL_REGISTRY.values() if not entry.read_only),
            "confirmation_count": sum(1 for entry in TOOL_REGISTRY.values() if entry.requires_confirmation),
            "high_risk_count": sum(1 for entry in TOOL_REGISTRY.values() if entry.risk_level in {"high", "destructive"}),
        },
        "tools": {
            name: {
                **asdict(entry),
                "data_sources": list(entry.data_sources),
                "visible_agents": visible_agents[name],
            }
            for name, entry in sorted(TOOL_REGISTRY.items())
        },
        "agents": {agent_name: list(allowlist) for agent_name, allowlist in sorted(AGENT_TOOL_ALLOWLISTS.items())},
        "agent_groups": {agent_name: list(groups) for agent_name, groups in sorted(AGENT_TOOL_GROUPS.items())},
        "agent_explicit_tools": {
            agent_name: list(tools) for agent_name, tools in sorted(AGENT_TOOL_EXPLICIT_TOOLS.items())
        },
    }


def validate_agent_tool_policy() -> None:
    for agent_name in READ_ONLY_ANALYSIS_AGENTS:
        unsafe = WRITE_OR_BACKGROUND_TOOLS.intersection(AGENT_TOOL_ALLOWLISTS[agent_name])
        if unsafe:
            unsafe_list = ", ".join(sorted(unsafe))
            raise ValueError(f"{agent_name} includes write/background tools: {unsafe_list}")
    unsafe_groups = {"external_write_request", "destructive_maintenance"}
    for agent_name in READ_ONLY_AGENT_NAMES:
        unsafe_entries = [entry.name for entry in resolve_agent_tool_entries(agent_name) if entry.group in unsafe_groups]
        if unsafe_entries:
            unsafe_list = ", ".join(sorted(unsafe_entries))
            raise ValueError(f"{agent_name} includes unsafe registry groups: {unsafe_list}")


def resolve_agent_tools(
    agent_name: str,
    catalog: Mapping[str, Tool],
    *,
    strict: bool = False,
    include_confirmation: bool = False,
) -> list[Tool]:
    entries = resolve_agent_tool_entries(agent_name)
    if not include_confirmation:
        entries = [entry for entry in entries if not entry.requires_confirmation]
    missing = [entry.handler for entry in entries if entry.handler not in catalog]
    if strict and missing:
        raise KeyError(f"{agent_name} references unknown tools: {', '.join(missing)}")
    return [catalog[entry.handler] for entry in entries if entry.handler in catalog]


def validate_agent_tool_registry(catalog: Mapping[str, Tool]) -> None:
    validate_agent_tool_policy()
    for entry in TOOL_REGISTRY.values():
        _validate_tool_entry(entry)
    allowlist_tools = {tool for allowlist in AGENT_TOOL_ALLOWLISTS.values() for tool in allowlist}
    missing_registry_entries = allowlist_tools - set(TOOL_REGISTRY)
    if missing_registry_entries:
        missing = ", ".join(sorted(missing_registry_entries))
        raise KeyError(f"AGENT_TOOL_ALLOWLISTS references tools missing from TOOL_REGISTRY: {missing}")
    for agent_name in AGENT_TOOL_ALLOWLISTS:
        resolve_agent_tools(agent_name, catalog, strict=True)
