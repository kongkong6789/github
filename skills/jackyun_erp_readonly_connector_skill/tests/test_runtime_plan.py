import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.runtime_plan import method_route_plan, workflow_route_plan


class TestRuntimePlan(unittest.TestCase):
    @patch("helpers.runtime_plan.config.JACKYUN_CALL_STRATEGY", "auto")
    @patch("helpers.runtime_plan.config.JACKYUN_MCP_TOKEN", "token")
    @patch("helpers.runtime_plan.config.JACKYUN_CLI_ENABLED", True)
    def test_mcp_supported_method_prefers_mcp(self):
        plan = method_route_plan("erp.stockquantity.get")

        self.assertTrue(plan["mcp_supported"])
        self.assertTrue(plan["mcp_ready"])
        self.assertEqual(plan["primary"], "mcp")
        self.assertIn("http", plan["fallback"])

    @patch("helpers.runtime_plan.config.JACKYUN_CALL_STRATEGY", "auto")
    @patch("helpers.runtime_plan.config.JACKYUN_MCP_TOKEN", "")
    @patch("helpers.runtime_plan.config.JACKYUN_CLI_ENABLED", True)
    def test_cli_enabled_without_mcp_token_prefers_cli(self):
        plan = method_route_plan("erp.stockquantity.get")

        self.assertEqual(plan["primary"], "cli")
        self.assertEqual(plan["fallback"], ["http"])

    def test_workflow_plan_contains_methods(self):
        plan = workflow_route_plan("transfer")

        self.assertEqual(plan["workflow"], "transfer")
        self.assertTrue(any(item["method"] == "erp.allocate.create" for item in plan["methods"]))


if __name__ == "__main__":
    unittest.main()
