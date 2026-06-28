from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


def _reload_external_memory_modules():
    import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools
    import src.a2a_ecommerce_demo.external_memory_tools as external_memory_tools

    enterprise_audit_tools = importlib.reload(enterprise_audit_tools)
    external_memory_tools = importlib.reload(external_memory_tools)
    return external_memory_tools, enterprise_audit_tools


class ExternalMemoryToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        os.environ["A2A_DATA_DIR"] = str(self.root / "data")
        os.environ["A2A_AUDIT_DIR"] = str(self.root / "data" / "audit")
        self.memory_tools, self.audit_tools = _reload_external_memory_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_external_memory_save_blocks_sensitive_business_details(self) -> None:
        blocked = json.loads(
            self.memory_tools.request_external_memory_save(
                "客户手机号 13800138000，采购价 12.3，库存明细 100 件",
                container_tag="a2a-test",
                source="unit",
                requested_by="tester",
            )
        )

        self.assertEqual("blocked_sensitive", blocked["status"])
        self.assertTrue(blocked["scan"]["blocked"])
        self.assertIn("客户信息", blocked["scan"]["blocked_categories"])
        self.assertIn("采购价", blocked["scan"]["blocked_categories"])
        self.assertIn("库存明细", blocked["scan"]["blocked_categories"])

        events = json.loads(self.audit_tools.list_audit_events(limit=10))["events"]
        self.assertTrue(any(event["event_type"] == "external_memory_blocked_sensitive" for event in events))

    def test_external_memory_save_request_returns_confirmation_preview(self) -> None:
        approval = json.loads(
            self.memory_tools.request_external_memory_save(
                "用户偏好：老板报告先给结论，再给证据和数据缺口。",
                container_tag="a2a-test",
                source="retro",
                requested_by="tester",
            )
        )

        self.assertEqual("confirmation_required", approval["status"])
        self.assertEqual("external_memory_save_requested", approval["audit_event_type"])
        action = approval["interrupt"]["value"]["action_requests"][0]
        self.assertEqual("supermemory_save_memory", action["name"])
        self.assertIn("container_tag", action["args"])

        recalled = json.loads(
            self.memory_tools.record_external_memory_recall(
                query="老板报告格式偏好",
                container_tag="a2a-test",
                result_count=2,
                actor="tester",
            )
        )
        self.assertEqual("success", recalled["status"])


if __name__ == "__main__":
    unittest.main()
