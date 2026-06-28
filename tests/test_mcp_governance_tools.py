from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


def _reload_mcp_modules():
    import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools
    import src.a2a_ecommerce_demo.mcp_governance_tools as mcp_governance_tools

    enterprise_audit_tools = importlib.reload(enterprise_audit_tools)
    mcp_governance_tools = importlib.reload(mcp_governance_tools)
    return mcp_governance_tools, enterprise_audit_tools


class MCPGovernanceToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        os.environ["A2A_DATA_DIR"] = str(self.root / "data")
        os.environ["A2A_MCP_POLICY_PATH"] = str(self.root / "data" / "mcp" / "tool_policy.json")
        os.environ["A2A_AUDIT_DIR"] = str(self.root / "data" / "audit")
        self.mcp_tools, self.audit_tools = _reload_mcp_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_mcp_policy_distinguishes_read_only_and_write_confirmation_tools(self) -> None:
        policy = json.loads(self.mcp_tools.list_mcp_tool_policy())
        self.assertIn("query_erp_live_snapshot", policy["tools"])
        self.assertIn("query_wecom_smartsheet_records", policy["tools"])
        self.assertIn("list_erp_live_query_capabilities", policy["tools"])
        self.assertIn("test_erp_live_connection", policy["tools"])
        self.assertIn("route_erp_live_query", policy["tools"])
        self.assertIn("query_inventory_cost_reference", policy["tools"])
        self.assertIn("query_jackyun_channel_sales_summary", policy["tools"])
        self.assertIn("list_wecom_smartsheet_sources", policy["tools"])
        self.assertIn("test_wecom_smartsheet_connection", policy["tools"])
        self.assertIn("sync_wecom_smartsheet_snapshot", policy["tools"])
        self.assertIn("agent_reach_get_status", policy["tools"])
        self.assertIn("agent_reach_read_public_web", policy["tools"])
        self.assertIn("agent_reach_search_public_sources", policy["tools"])
        self.assertIn("agent_reach_read_video_transcript", policy["tools"])
        self.assertIn("agent_reach_read_logged_in_social", policy["tools"])
        self.assertTrue(policy["tools"]["query_erp_live_snapshot"]["read_only"])
        self.assertFalse(policy["tools"]["query_erp_live_snapshot"]["external_write_enabled"])
        self.assertTrue(policy["tools"]["query_wecom_smartsheet_records"]["read_only"])
        self.assertFalse(policy["tools"]["query_wecom_smartsheet_records"]["external_write_enabled"])
        self.assertEqual(policy["tools"]["query_wecom_smartsheet_records"]["data_sources"], ["WeCom_smartsheet"])
        self.assertTrue(policy["tools"]["list_wecom_smartsheet_sources"]["read_only"])
        self.assertTrue(policy["tools"]["test_wecom_smartsheet_connection"]["read_only"])
        self.assertTrue(policy["tools"]["sync_wecom_smartsheet_snapshot"]["requires_human_confirmation"])
        self.assertIn("top_company_brain_supervisor", policy["tools"]["query_erp_live_snapshot"]["allowed_callers"])
        self.assertIn("top_company_brain_supervisor", policy["tools"]["query_wecom_smartsheet_records"]["allowed_callers"])
        self.assertTrue(policy["tools"]["verify_erp_supplier_terms_mapping"]["read_only"])
        self.assertFalse(policy["tools"]["verify_erp_supplier_terms_mapping"]["external_write_enabled"])
        self.assertTrue(policy["tools"]["route_erp_live_query"]["read_only"])
        self.assertTrue(policy["tools"]["query_inventory_cost_reference"]["read_only"])
        self.assertTrue(policy["tools"]["query_jackyun_channel_sales_summary"]["read_only"])
        self.assertFalse(policy["tools"]["query_jackyun_channel_sales_summary"]["external_write_enabled"])
        self.assertEqual(policy["tools"]["query_jackyun_channel_sales_summary"]["data_sources"], ["jackyun_erp"])
        self.assertTrue(policy["tools"]["supermemory_profile"]["read_only"])
        self.assertTrue(policy["tools"]["supermemory_recall"]["read_only"])
        self.assertTrue(policy["tools"]["supermemory_context"]["read_only"])
        self.assertFalse(policy["tools"]["supermemory_save_memory"]["read_only"])
        self.assertTrue(policy["tools"]["supermemory_save_memory"]["requires_human_confirmation"])
        self.assertFalse(policy["tools"]["supermemory_save_memory"]["external_write_enabled"])
        self.assertIn("ERP 行级数据", policy["tools"]["supermemory_save_memory"]["blocked_sensitive_data"])
        self.assertIn("inventory_agent", policy["tools"]["query_erp_live_snapshot"]["allowed_callers"])
        self.assertIn("inventory_agent", policy["tools"]["verify_erp_supplier_terms_mapping"]["allowed_callers"])
        self.assertIn("data_agent", policy["tools"]["query_jackyun_channel_sales_summary"]["allowed_callers"])
        self.assertIn("finance_agent", policy["tools"]["query_inventory_cost_reference"]["allowed_callers"])
        self.assertFalse(policy["tools"]["query_erp_live_snapshot"]["requires_human_confirmation"])
        self.assertFalse(policy["tools"]["query_wecom_smartsheet_records"]["requires_human_confirmation"])
        self.assertFalse(policy["tools"]["query_inventory_cost_reference"]["requires_human_confirmation"])
        self.assertFalse(policy["tools"]["query_jackyun_channel_sales_summary"]["requires_human_confirmation"])
        self.assertTrue(policy["tools"]["agent_reach_get_status"]["read_only"])
        self.assertFalse(policy["tools"]["agent_reach_get_status"]["requires_human_confirmation"])
        self.assertEqual(policy["tools"]["agent_reach_get_status"]["data_sources"], ["agent_reach"])
        self.assertTrue(policy["tools"]["agent_reach_read_public_web"]["read_only"])
        self.assertFalse(policy["tools"]["agent_reach_read_public_web"]["external_write_enabled"])
        self.assertFalse(policy["tools"]["agent_reach_read_public_web"]["requires_human_confirmation"])
        self.assertEqual(policy["tools"]["agent_reach_read_public_web"]["data_sources"], ["agent_reach_public_web"])
        self.assertIn("knowledge_agent", policy["tools"]["agent_reach_read_public_web"]["allowed_callers"])
        self.assertTrue(policy["tools"]["agent_reach_read_logged_in_social"]["read_only"])
        self.assertFalse(policy["tools"]["agent_reach_read_logged_in_social"]["external_write_enabled"])
        self.assertTrue(policy["tools"]["agent_reach_read_logged_in_social"]["requires_human_confirmation"])
        self.assertEqual(policy["tools"]["agent_reach_read_logged_in_social"]["risk_level"], "medium")
        self.assertIn("需要专用账号", policy["tools"]["agent_reach_read_logged_in_social"]["destructive_effects"][0])
        self.assertTrue(policy["tools"]["create_purchase_order"]["requires_human_confirmation"])
        self.assertFalse(policy["tools"]["create_purchase_order"]["external_write_enabled"])
        self.assertEqual("approval_request_only", policy["tools"]["create_purchase_order"]["execution_mode"])

        read_check = json.loads(self.mcp_tools.check_mcp_tool_permission("query_erp_live_snapshot", "read"))
        self.assertTrue(read_check["allowed"])
        self.assertFalse(read_check["requires_human_confirmation"])
        self.assertFalse(read_check["external_write_enabled"])

        wecom_check = json.loads(self.mcp_tools.check_mcp_tool_permission("query_wecom_smartsheet_records", "read"))
        self.assertTrue(wecom_check["allowed"])
        self.assertFalse(wecom_check["requires_human_confirmation"])
        self.assertEqual(wecom_check["data_sources"], ["WeCom_smartsheet"])
        workflow_wecom_check = json.loads(
            self.mcp_tools.check_mcp_tool_permission("query_wecom_smartsheet_records", "read", caller="auto_workflow_agent")
        )
        self.assertTrue(workflow_wecom_check["allowed"])
        public_web_check = json.loads(
            self.mcp_tools.check_mcp_tool_permission("agent_reach_read_public_web", "read", caller="knowledge_agent")
        )
        self.assertTrue(public_web_check["allowed"])
        self.assertFalse(public_web_check["requires_human_confirmation"])
        social_check = json.loads(
            self.mcp_tools.check_mcp_tool_permission("agent_reach_read_logged_in_social", "read", caller="knowledge_agent")
        )
        self.assertFalse(social_check["allowed"])
        self.assertTrue(social_check["requires_human_confirmation"])
        self.assertTrue(json.loads(self.mcp_tools.check_mcp_tool_permission("test_erp_live_connection", "read"))["allowed"])
        self.assertTrue(json.loads(self.mcp_tools.check_mcp_tool_permission("list_wecom_smartsheet_sources", "read"))["allowed"])
        self.assertTrue(
            json.loads(
                self.mcp_tools.check_mcp_tool_permission(
                    "query_inventory_cost_reference", "read", caller="finance_agent"
                )
            )["allowed"]
        )

        write_check = json.loads(self.mcp_tools.check_mcp_tool_permission("create_purchase_order", "write"))
        self.assertFalse(write_check["allowed"])
        self.assertTrue(write_check["requires_human_confirmation"])
        self.assertEqual("high", write_check["risk_level"])
        self.assertFalse(write_check["external_write_enabled"])

        memory_check = json.loads(
            self.mcp_tools.check_mcp_tool_permission(
                "supermemory_recall",
                "read",
                caller="top_company_brain_supervisor",
            )
        )
        self.assertTrue(memory_check["allowed"])
        self.assertFalse(memory_check["requires_human_confirmation"])

        memory_write_check = json.loads(
            self.mcp_tools.check_mcp_tool_permission(
                "supermemory_save_memory",
                "write",
                caller="top_company_brain_supervisor",
            )
        )
        self.assertFalse(memory_write_check["allowed"])
        self.assertTrue(memory_write_check["requires_human_confirmation"])

        generic_agent_check = json.loads(
            self.mcp_tools.check_mcp_tool_permission(
                "query_erp_live_snapshot",
                "read",
                caller="agent",
            )
        )
        self.assertFalse(generic_agent_check["allowed"])
        self.assertTrue(generic_agent_check["requires_human_confirmation"])

    def test_empty_allowed_callers_blocks_instead_of_allowing_everyone(self) -> None:
        policy_path = self.root / "data" / "mcp" / "tool_policy.json"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            json.dumps(
                {
                    "schema": "a2a_mcp_tool_policy_v1",
                    "tools": {
                        "empty_callers_tool": {
                            "description": "bad policy",
                            "action": "read",
                            "read_only": True,
                            "requires_human_confirmation": False,
                            "allowed_callers": [],
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        check = json.loads(
            self.mcp_tools.check_mcp_tool_permission(
                "empty_callers_tool",
                "read",
                caller="data_agent",
            )
        )

        self.assertFalse(check["allowed"])
        self.assertTrue(check["requires_human_confirmation"])

    def test_listing_mcp_policy_is_read_only_and_does_not_create_policy_file(self) -> None:
        policy = json.loads(self.mcp_tools.list_mcp_tool_policy())

        self.assertEqual("a2a_mcp_tool_policy_v1", policy["schema"])
        self.assertFalse((self.root / "data" / "mcp" / "tool_policy.json").exists())

    def test_write_mcp_approval_uses_agent_inbox_shape_and_audit_is_redacted(self) -> None:
        approval = json.loads(
            self.mcp_tools.request_mcp_write_approval(
                "create_purchase_order",
                "write",
                args_json=json.dumps({"sku": "SKU-001", "api_key": "sk-secret-value"}, ensure_ascii=False),
                description="创建采购单前请人工确认。",
                requested_by="tester",
            )
        )

        self.assertEqual("confirmation_required", approval["status"])
        action_request = approval["interrupt"]["value"]["action_requests"][0]
        self.assertEqual("create_purchase_order", action_request["name"])
        self.assertEqual("high", action_request["args"]["risk_level"])
        self.assertEqual("blocked", action_request["args"]["permission"]["status"])
        self.assertNotIn("sk-secret-value", json.dumps(action_request["args"], ensure_ascii=False))
        self.assertIn("创建采购单", approval["interrupt"]["value"]["metadata"]["destructive_effects"][0])
        self.assertIn("edit", approval["interrupt"]["value"]["review_configs"][0]["allowed_decisions"])

        audit = json.loads(
            self.mcp_tools.record_mcp_tool_audit(
                "create_purchase_order",
                "write",
                status="blocked",
                args_json=json.dumps({"api_key": "sk-secret-value"}, ensure_ascii=False),
                result_summary="blocked before external call",
                actor="tester",
            )
        )
        self.assertEqual("mcp_tool_called", audit["event"]["event_type"])
        self.assertIn("***REDACTED***", json.dumps(audit, ensure_ascii=False))

        events = json.loads(self.audit_tools.list_audit_events())["events"]
        self.assertTrue(any(event["event_type"] == "mcp_tool_called" for event in events))


if __name__ == "__main__":
    unittest.main()
