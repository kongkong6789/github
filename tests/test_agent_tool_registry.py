from __future__ import annotations

import unittest
from typing import Any, cast


class AgentToolRegistryTests(unittest.TestCase):
    def test_registry_resolves_named_tools_and_blocks_decision_write_tools(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import resolve_agent_tools

        def safe_tool() -> str:
            return "ok"

        def start_company_workflow_task() -> str:
            return "unsafe"

        tools = resolve_agent_tools(
            "decision_agent",
            {
                "summarize_business_data": safe_tool,
                "start_company_workflow_task": start_company_workflow_task,
            },
        )

        self.assertEqual([safe_tool], tools)
        with self.assertRaises(KeyError):
            resolve_agent_tools("missing_agent", {"summarize_business_data": safe_tool})

    def test_registry_has_all_expected_primary_agents(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import AGENT_TOOL_ALLOWLISTS

        self.assertIn("data_agent", AGENT_TOOL_ALLOWLISTS)
        self.assertIn("decision_agent", AGENT_TOOL_ALLOWLISTS)
        self.assertIn("company_strategy_agent", AGENT_TOOL_ALLOWLISTS)
        self.assertIn("auto_workflow_agent", AGENT_TOOL_ALLOWLISTS)
        self.assertIn("lightrag_agent", AGENT_TOOL_ALLOWLISTS)
        self.assertIn("top_company_brain_supervisor", AGENT_TOOL_ALLOWLISTS)

    def test_connector_tools_follow_read_only_agent_boundaries(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import AGENT_TOOL_ALLOWLISTS

        self.assertIn("list_erp_connectors", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("get_erp_connector_health", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("preview_erp_connector_sync", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("list_erp_live_query_capabilities", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("test_erp_live_connection", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("query_erp_live_snapshot", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("verify_erp_supplier_terms_mapping", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("list_wecom_smartsheet_sources", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("test_wecom_smartsheet_connection", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("query_wecom_smartsheet_records", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("route_erp_live_query", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("query_inventory_cost_reference", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("query_jackyun_channel_sales_summary", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("query_erp_live_snapshot", AGENT_TOOL_ALLOWLISTS["inventory_agent"])
        self.assertIn("verify_erp_supplier_terms_mapping", AGENT_TOOL_ALLOWLISTS["inventory_agent"])
        self.assertIn("route_erp_live_query", AGENT_TOOL_ALLOWLISTS["inventory_agent"])
        self.assertIn("query_inventory_cost_reference", AGENT_TOOL_ALLOWLISTS["inventory_agent"])
        self.assertIn("query_jackyun_channel_sales_summary", AGENT_TOOL_ALLOWLISTS["inventory_agent"])
        self.assertIn("query_inventory_cost_reference", AGENT_TOOL_ALLOWLISTS["finance_agent"])
        self.assertIn("query_inventory_cost_reference", AGENT_TOOL_ALLOWLISTS["financial_planning_agent"])
        self.assertIn("query_erp_live_snapshot", AGENT_TOOL_ALLOWLISTS["decision_agent"])
        self.assertIn("query_wecom_smartsheet_records", AGENT_TOOL_ALLOWLISTS["decision_agent"])
        self.assertIn("verify_erp_supplier_terms_mapping", AGENT_TOOL_ALLOWLISTS["decision_agent"])
        self.assertIn("query_inventory_cost_reference", AGENT_TOOL_ALLOWLISTS["decision_agent"])
        self.assertIn("query_jackyun_channel_sales_summary", AGENT_TOOL_ALLOWLISTS["decision_agent"])
        self.assertIn("query_erp_live_snapshot", AGENT_TOOL_ALLOWLISTS["company_strategy_agent"])
        self.assertIn("query_wecom_smartsheet_records", AGENT_TOOL_ALLOWLISTS["company_strategy_agent"])
        self.assertIn("verify_erp_supplier_terms_mapping", AGENT_TOOL_ALLOWLISTS["company_strategy_agent"])
        self.assertIn("query_inventory_cost_reference", AGENT_TOOL_ALLOWLISTS["company_strategy_agent"])
        self.assertIn("query_jackyun_channel_sales_summary", AGENT_TOOL_ALLOWLISTS["company_strategy_agent"])
        self.assertIn("sync_connector_dataset", AGENT_TOOL_ALLOWLISTS["auto_workflow_agent"])
        self.assertIn("sync_wecom_smartsheet_snapshot", AGENT_TOOL_ALLOWLISTS["auto_workflow_agent"])
        self.assertIn("run_fact_layer_registration_task", AGENT_TOOL_ALLOWLISTS["auto_workflow_agent"])
        self.assertIn("query_erp_live_snapshot", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])
        self.assertIn("route_erp_live_query", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])
        self.assertIn("query_inventory_cost_reference", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])
        self.assertIn("query_jackyun_channel_sales_summary", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])
        self.assertIn("query_wecom_smartsheet_records", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])
        self.assertIn("list_runtime_capabilities", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])
        self.assertIn("invoke_runtime_capability", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])
        self.assertIn("list_runtime_capabilities", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("invoke_runtime_capability", AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertIn("register_runtime_mcp_tool", AGENT_TOOL_ALLOWLISTS["agent_factory_agent"])
        self.assertNotIn("sync_connector_dataset", AGENT_TOOL_ALLOWLISTS["decision_agent"])
        self.assertNotIn("sync_wecom_smartsheet_snapshot", AGENT_TOOL_ALLOWLISTS["decision_agent"])
        self.assertNotIn("sync_connector_dataset", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])
        self.assertNotIn("sync_wecom_smartsheet_snapshot", AGENT_TOOL_ALLOWLISTS["top_company_brain_supervisor"])

    def test_p6_skill_and_mcp_tools_are_scoped_to_factory_and_workflow_agents(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import AGENT_TOOL_ALLOWLISTS

        for agent_name in ["agent_factory_agent", "auto_workflow_agent"]:
            self.assertIn("create_agent_skill_from_wiki", AGENT_TOOL_ALLOWLISTS[agent_name])
            self.assertIn("approve_agent_skill", AGENT_TOOL_ALLOWLISTS[agent_name])
            self.assertIn("update_agent_skill", AGENT_TOOL_ALLOWLISTS[agent_name])
            self.assertIn("rollback_agent_skill", AGENT_TOOL_ALLOWLISTS[agent_name])
            self.assertIn("list_mcp_tool_policy", AGENT_TOOL_ALLOWLISTS[agent_name])
            self.assertIn("check_mcp_tool_permission", AGENT_TOOL_ALLOWLISTS[agent_name])
            self.assertIn("request_mcp_write_approval", AGENT_TOOL_ALLOWLISTS[agent_name])

        self.assertNotIn("request_mcp_write_approval", AGENT_TOOL_ALLOWLISTS["decision_agent"])
        self.assertNotIn("approve_agent_skill", AGENT_TOOL_ALLOWLISTS["company_strategy_agent"])

    def test_p4_sensitive_field_tools_are_available_to_analysis_agents(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import (
            AGENT_TOOL_ALLOWLISTS,
            WRITE_OR_BACKGROUND_TOOLS,
        )

        expected_tools = {
            "summarize_sensitive_fields_from_registry",
            "classify_sensitive_fields",
            "mask_sensitive_record",
            "record_sensitive_field_access",
        }
        for agent_name in ["data_agent", "company_strategy_agent", "decision_agent", "auto_workflow_agent"]:
            self.assertTrue(expected_tools.issubset(AGENT_TOOL_ALLOWLISTS[agent_name]))

        self.assertFalse(expected_tools.intersection(WRITE_OR_BACKGROUND_TOOLS))

    def test_p14_evidence_graph_tools_are_read_only_analysis_tools(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import AGENT_TOOL_ALLOWLISTS, TOOL_REGISTRY

        expected_tools = {
            "build_evidence_graph",
            "list_evidence_graph_nodes",
            "list_evidence_graph_edges",
        }
        for agent_name in ["knowledge_agent", "company_strategy_agent", "decision_agent", "auto_workflow_agent"]:
            self.assertTrue(expected_tools.issubset(AGENT_TOOL_ALLOWLISTS[agent_name]))
        for tool_name in expected_tools:
            entry = TOOL_REGISTRY[tool_name]
            self.assertTrue(entry.read_only)
            self.assertEqual("read_knowledge", entry.group)
            self.assertEqual("evidence_graph_tools", entry.owner_module)
            self.assertTrue({"DuckDB", "wiki", "LightRAG", "audit", "tasks", "reports"}.issubset(entry.data_sources))

    def test_p15_wiki_lifecycle_tools_are_agent_visible(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import AGENT_TOOL_ALLOWLISTS, TOOL_REGISTRY

        read_tools = {
            "lint_wiki_knowledge_base",
            "generate_wiki_review_questions",
        }
        write_tools = {
            "ensure_wiki_knowledge_scaffold",
            "refresh_wiki_index",
            "append_wiki_log_event",
            "normalize_legacy_wiki_pages",
            "archive_decision_to_wiki",
            "register_wiki_claim_evidence",
        }
        expected_tools = read_tools | write_tools
        for agent_name in ["knowledge_agent", "company_strategy_agent", "decision_agent", "auto_workflow_agent"]:
            self.assertTrue(expected_tools.issubset(AGENT_TOOL_ALLOWLISTS[agent_name]))

        for tool_name in read_tools:
            entry = TOOL_REGISTRY[tool_name]
            self.assertTrue(entry.read_only)
            self.assertEqual("read_knowledge", entry.group)
            self.assertEqual("wiki_lifecycle_tools", entry.owner_module)

        for tool_name in write_tools:
            entry = TOOL_REGISTRY[tool_name]
            self.assertFalse(entry.read_only)
            self.assertEqual("write_local_state", entry.group)
            self.assertEqual("wiki_lifecycle_tools", entry.owner_module)
            self.assertIn("wiki", entry.data_sources)

    def test_p11_tool_registry_entries_are_complete_and_enum_bounded(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import (
            AGENT_TOOL_ALLOWLISTS,
            ALLOWED_TOOL_DATA_SOURCES,
            ALLOWED_TOOL_GROUPS,
            ALLOWED_TOOL_RISK_LEVELS,
            TOOL_REGISTRY,
            ToolEntry,
        )

        allowlist_tools = {tool for tools in AGENT_TOOL_ALLOWLISTS.values() for tool in tools}
        self.assertEqual(allowlist_tools - set(TOOL_REGISTRY), set())

        for name, entry in TOOL_REGISTRY.items():
            self.assertIsInstance(entry, ToolEntry)
            self.assertEqual(name, entry.name)
            self.assertTrue(entry.handler)
            self.assertTrue(entry.description)
            self.assertIn(entry.group, ALLOWED_TOOL_GROUPS)
            self.assertIn(entry.risk_level, ALLOWED_TOOL_RISK_LEVELS)
            self.assertTrue(set(entry.data_sources).issubset(ALLOWED_TOOL_DATA_SOURCES))
            self.assertGreater(entry.max_result_size, 0)
            self.assertTrue(entry.availability_check)
            self.assertTrue(entry.owner_module)

    def test_p11_agent_entries_resolve_from_groups_without_losing_compatibility(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import (
            AGENT_TOOL_ALLOWLISTS,
            AGENT_TOOL_GROUPS,
            resolve_agent_tool_entries,
        )

        self.assertIn("read_fact", AGENT_TOOL_GROUPS["data_agent"])
        self.assertIn("external_read", AGENT_TOOL_GROUPS["data_agent"])
        self.assertIn("read_knowledge", AGENT_TOOL_GROUPS["knowledge_agent"])
        self.assertIn("workflow", AGENT_TOOL_GROUPS["auto_workflow_agent"])

        for agent_name, allowlist in AGENT_TOOL_ALLOWLISTS.items():
            self.assertEqual([entry.name for entry in resolve_agent_tool_entries(agent_name)], list(allowlist))

    def test_p11_read_only_agents_do_not_get_external_write_or_destructive_tools(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import (
            READ_ONLY_AGENT_NAMES,
            resolve_agent_tool_entries,
        )

        unsafe_groups = {"external_write_request", "destructive_maintenance"}
        for agent_name in READ_ONLY_AGENT_NAMES:
            unsafe = {entry.name for entry in resolve_agent_tool_entries(agent_name) if entry.group in unsafe_groups}
            self.assertEqual(unsafe, set(), agent_name)

    def test_p11_confirmation_tools_are_not_in_direct_execution_entries(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import (
            resolve_agent_tool_entries,
            resolve_agent_tools,
            resolve_direct_agent_tool_entries,
        )

        confirmation_required = {
            entry.name for entry in resolve_agent_tool_entries("auto_workflow_agent") if entry.requires_confirmation
        }
        self.assertIn("sync_connector_dataset", confirmation_required)
        self.assertIn("sync_wecom_smartsheet_snapshot", confirmation_required)
        self.assertIn("run_fact_layer_registration_task", confirmation_required)
        self.assertIn("cancel_workflow_task", confirmation_required)

        direct_names = {entry.name for entry in resolve_direct_agent_tool_entries("auto_workflow_agent")}
        self.assertFalse(confirmation_required.intersection(direct_names))

        fake_catalog = {entry.handler: entry.name for entry in resolve_agent_tool_entries("auto_workflow_agent")}
        mounted_names = set(cast(list[str], resolve_agent_tools("auto_workflow_agent", cast(Any, fake_catalog))))
        self.assertFalse(confirmation_required.intersection(mounted_names))

    def test_p11_erp_external_write_policy_stays_disabled(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import export_tool_registry_payload
        from src.a2a_ecommerce_demo.mcp_governance_tools import DEFAULT_MCP_TOOL_POLICY

        payload = export_tool_registry_payload()
        tools = cast(dict[str, dict[str, Any]], payload["tools"])
        self.assertEqual(payload["schema"], "a2a_tool_registry_v2")
        self.assertEqual(tools["query_erp_live_snapshot"]["group"], "external_read")
        self.assertEqual(tools["query_erp_live_snapshot"]["read_only"], True)
        self.assertEqual(tools["route_erp_live_query"]["group"], "external_read")
        self.assertEqual(tools["route_erp_live_query"]["owner_module"], "connector_live_tools")
        self.assertEqual(tools["query_inventory_cost_reference"]["group"], "external_read")
        self.assertEqual(tools["query_inventory_cost_reference"]["owner_module"], "connector_live_tools")
        self.assertEqual(tools["query_jackyun_channel_sales_summary"]["group"], "external_read")
        self.assertEqual(tools["query_jackyun_channel_sales_summary"]["owner_module"], "connector_live_tools")
        self.assertEqual(tools["query_jackyun_channel_sales_summary"]["data_sources"], ["ERP_live_readonly"])
        self.assertEqual(tools["list_runtime_capabilities"]["group"], "governance")
        self.assertTrue(tools["list_runtime_capabilities"]["read_only"])
        self.assertEqual(tools["invoke_runtime_capability"]["owner_module"], "runtime_capability_tools")
        self.assertTrue(tools["invoke_runtime_capability"]["read_only"])
        self.assertEqual(tools["register_runtime_mcp_tool"]["group"], "write_local_state")
        self.assertTrue(tools["register_runtime_mcp_tool"]["requires_confirmation"])
        self.assertEqual(tools["query_wecom_smartsheet_records"]["group"], "external_read")
        self.assertEqual(tools["query_wecom_smartsheet_records"]["owner_module"], "wecom_smartsheet_tools")
        self.assertEqual(tools["query_wecom_smartsheet_records"]["data_sources"], ["WeCom_smartsheet"])

        for tool_name in ["create_purchase_order", "update_ad_budget", "send_external_message"]:
            self.assertFalse(DEFAULT_MCP_TOOL_POLICY[tool_name]["external_write_enabled"])
            self.assertTrue(DEFAULT_MCP_TOOL_POLICY[tool_name]["requires_human_confirmation"])

    def test_agent_reach_tools_are_registered_as_read_only_external_research(self) -> None:
        from src.a2a_ecommerce_demo.agent_tool_registry import (
            AGENT_TOOL_ALLOWLISTS,
            TOOL_REGISTRY,
            export_tool_registry_payload,
            resolve_agent_tools,
        )

        public_tools = {
            "agent_reach_get_status",
            "agent_reach_read_public_web",
            "agent_reach_search_public_sources",
            "agent_reach_read_video_transcript",
        }
        for agent_name in ["knowledge_agent", "company_strategy_agent", "decision_agent", "top_company_brain_supervisor"]:
            self.assertTrue(public_tools.issubset(AGENT_TOOL_ALLOWLISTS[agent_name]))

        social_tool = TOOL_REGISTRY["agent_reach_read_logged_in_social"]
        self.assertEqual(social_tool.group, "external_read")
        self.assertTrue(social_tool.read_only)
        self.assertTrue(social_tool.requires_confirmation)
        self.assertEqual(social_tool.risk_level, "medium")
        self.assertIn("agent_reach_social", social_tool.data_sources)

        fake_catalog = {name: (lambda name=name: name) for name in TOOL_REGISTRY}
        direct_names = {tool() for tool in resolve_agent_tools("decision_agent", fake_catalog)}
        self.assertTrue(public_tools.issubset(direct_names))
        self.assertNotIn("agent_reach_read_logged_in_social", direct_names)

        payload = export_tool_registry_payload()
        tools = cast(dict[str, dict[str, Any]], payload["tools"])
        self.assertEqual(tools["agent_reach_read_public_web"]["owner_module"], "agent_reach_tools")
        self.assertEqual(tools["agent_reach_search_public_sources"]["owner_module"], "agent_reach_tools")
        self.assertEqual(tools["agent_reach_search_public_sources"]["group"], "external_read")
        self.assertEqual(tools["agent_reach_search_public_sources"]["data_sources"], ["agent_reach_public_search"])
        self.assertEqual(tools["agent_reach_get_status"]["data_sources"], ["agent_reach"])

    def test_agent_reach_registry_handlers_are_importable(self) -> None:
        import importlib

        from src.a2a_ecommerce_demo.agent_tool_registry import TOOL_REGISTRY

        for tool_name in [
            "agent_reach_get_status",
            "agent_reach_read_public_web",
            "agent_reach_search_public_sources",
            "agent_reach_read_video_transcript",
            "agent_reach_read_logged_in_social",
        ]:
            entry = TOOL_REGISTRY[tool_name]
            module = importlib.import_module(f"src.a2a_ecommerce_demo.{entry.owner_module}")
            handler = getattr(module, entry.handler, None)
            self.assertTrue(callable(handler), f"{entry.owner_module}.{entry.handler} must be callable")


if __name__ == "__main__":
    unittest.main()
