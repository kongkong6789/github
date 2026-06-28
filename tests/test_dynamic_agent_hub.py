from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


def _reload_dynamic_agent_hub():
    import src.a2a_ecommerce_demo.dynamic_agent_hub as dynamic_agent_hub
    import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools

    enterprise_audit_tools = importlib.reload(enterprise_audit_tools)
    dynamic_agent_hub = importlib.reload(dynamic_agent_hub)
    return dynamic_agent_hub, enterprise_audit_tools


class DynamicAgentHubTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_AGENT_REGISTRY_DIR"] = str(self.data_dir / "agent_registry")
        os.environ["A2A_AGENT_TEMPLATE_DIR"] = str(self.data_dir / "agent_templates")
        os.environ["A2A_AUDIT_DIR"] = str(self.data_dir / "audit")
        self.dynamic_agent_hub, self.audit_tools = _reload_dynamic_agent_hub()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_one_sentence_agent_flow_requires_confirmation_then_executes_with_trace(self) -> None:
        draft = json.loads(
            self.dynamic_agent_hub.draft_dynamic_agent_spec(
                "创建一个库存风险 Agent，只能查询库存、销量和 LightRAG 证据",
                created_by="tester",
            )
        )

        self.assertEqual(draft["spec"]["status"], "draft")
        self.assertIn("query_inventory_snapshot", draft["spec"]["tool_allowlist"])
        self.assertTrue(draft["permission_preview"]["requires_human_confirmation"])

        confirmed = json.loads(
            self.dynamic_agent_hub.confirm_dynamic_agent_spec(
                json.dumps(draft["spec"], ensure_ascii=False),
                confirmed_by="tester",
            )
        )
        agent_id = confirmed["spec"]["agent_id"]
        self.assertEqual(confirmed["spec"]["status"], "active")
        self.assertEqual(confirmed["spec"]["version"], 1)

        run = json.loads(
            self.dynamic_agent_hub.run_dynamic_agent(
                agent_id,
                json.dumps({"sku": "SKU-001"}, ensure_ascii=False),
                requested_by="tester",
            )
        )
        self.assertEqual(run["status"], "success")
        self.assertEqual(run["trace"]["agent_id"], agent_id)
        self.assertEqual(run["trace"]["tool_allowlist"], confirmed["spec"]["tool_allowlist"])

        events = json.loads(self.audit_tools.list_audit_events(limit=20))["events"]
        event_types = {event["event_type"] for event in events}
        self.assertIn("dynamic_agent_registered", event_types)
        self.assertIn("dynamic_agent_invoked", event_types)

    def test_dynamic_agent_lifecycle_version_rollback_and_template_promotion(self) -> None:
        draft = json.loads(self.dynamic_agent_hub.draft_dynamic_agent_spec("财务分析 Agent", created_by="tester"))
        confirmed = json.loads(self.dynamic_agent_hub.confirm_dynamic_agent_spec(draft["spec"], confirmed_by="tester"))
        agent_id = confirmed["spec"]["agent_id"]

        updated = json.loads(
            self.dynamic_agent_hub.update_dynamic_agent_spec(
                agent_id,
                {"goal": "分析现金、毛利和广告预算压力"},
                updated_by="tester",
            )
        )
        self.assertEqual(updated["spec"]["version"], 2)
        self.assertEqual(updated["spec"]["goal"], "分析现金、毛利和广告预算压力")

        paused = json.loads(self.dynamic_agent_hub.set_dynamic_agent_status(agent_id, "paused", changed_by="tester"))
        self.assertEqual(paused["spec"]["status"], "paused")
        with self.assertRaises(ValueError):
            self.dynamic_agent_hub.run_dynamic_agent(agent_id, "{}", requested_by="tester")

        rolled_back = json.loads(self.dynamic_agent_hub.rollback_dynamic_agent(agent_id, 1, changed_by="tester"))
        self.assertEqual(rolled_back["spec"]["version"], 3)
        self.assertEqual(rolled_back["spec"]["previous_version"], 1)
        self.assertEqual(rolled_back["spec"]["status"], "active")

        promoted = json.loads(self.dynamic_agent_hub.promote_dynamic_agent_to_template(agent_id, notes="validated in test"))
        self.assertEqual(promoted["status"], "success")
        self.assertTrue(Path(promoted["saved_to"]).exists())


if __name__ == "__main__":
    unittest.main()
