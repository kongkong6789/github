from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


def _reload_sensitive_modules():
    import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools
    import src.a2a_ecommerce_demo.sensitive_data_tools as sensitive_data_tools

    enterprise_audit_tools = importlib.reload(enterprise_audit_tools)
    sensitive_data_tools = importlib.reload(sensitive_data_tools)
    return sensitive_data_tools, enterprise_audit_tools


class SensitiveDataToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in ["A2A_DATA_DIR", "A2A_WAREHOUSE_DIR", "A2A_AUDIT_DIR"]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        os.environ["A2A_DATA_DIR"] = str(self.root / "data")
        os.environ["A2A_WAREHOUSE_DIR"] = str(self.root / "data" / "warehouse")
        os.environ["A2A_AUDIT_DIR"] = str(self.root / "data" / "audit")
        self.sensitive_tools, self.audit_tools = _reload_sensitive_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_classifies_sensitive_fields_by_internal_pm_guardrail_categories(self) -> None:
        result = json.loads(
            self.sensitive_tools.classify_sensitive_fields(
                json.dumps(
                    [
                        "客户手机号",
                        "收货地址",
                        "会员ID",
                        "采购单价",
                        "供应商报价",
                        "毛利",
                        "现金流",
                        "SKU",
                    ],
                    ensure_ascii=False,
                )
            )
        )

        categories = {
            item["field"]: item["category"]
            for item in result["sensitive_fields"]
        }
        self.assertEqual("customer_pii", categories["客户手机号"])
        self.assertEqual("customer_pii", categories["收货地址"])
        self.assertEqual("customer_pii", categories["会员ID"])
        self.assertEqual("procurement_price", categories["采购单价"])
        self.assertEqual("procurement_price", categories["供应商报价"])
        self.assertEqual("finance", categories["毛利"])
        self.assertEqual("finance", categories["现金流"])
        self.assertNotIn("SKU", categories)
        self.assertEqual(3, result["category_counts"]["customer_pii"])
        self.assertIn("customer_pii", result["requires_masking_categories"])

    def test_masks_customer_pii_values_but_keeps_business_values_for_aggregation(self) -> None:
        result = json.loads(
            self.sensitive_tools.mask_sensitive_record(
                json.dumps(
                    {
                        "客户姓名": "张三",
                        "客户手机号": "13812345678",
                        "收货地址": "上海市静安区测试路 1 号",
                        "采购单价": 12.5,
                        "毛利": 8.2,
                    },
                    ensure_ascii=False,
                )
            )
        )

        masked = result["record"]
        self.assertEqual("张*", masked["客户姓名"])
        self.assertEqual("138****5678", masked["客户手机号"])
        self.assertEqual("***REDACTED_ADDRESS***", masked["收货地址"])
        self.assertEqual(12.5, masked["采购单价"])
        self.assertEqual(8.2, masked["毛利"])
        self.assertEqual(["customer_pii"], result["masked_categories"])

    def test_masks_pii_values_in_generic_fields(self) -> None:
        result = json.loads(
            self.sensitive_tools.mask_sensitive_record(
                json.dumps(
                    {
                        "备注": "客户手机号 13812345678，邮箱 buyer@example.com",
                        "SKU": "SKU-001",
                    },
                    ensure_ascii=False,
                )
            )
        )

        masked = result["record"]["备注"]
        self.assertIn("138****5678", masked)
        self.assertIn("***REDACTED_EMAIL***", masked)
        self.assertNotIn("buyer@example.com", masked)
        self.assertEqual(["customer_pii"], result["masked_categories"])

    def test_sensitive_field_access_is_audited_without_raw_values(self) -> None:
        event = json.loads(
            self.sensitive_tools.record_sensitive_field_access(
                actor="decision_agent",
                task_id="task-001",
                dataset="orders",
                fields_json=json.dumps(["客户手机号", "采购单价", "现金流"], ensure_ascii=False),
                purpose="生成老板报告前检查字段口径",
            )
        )["event"]

        self.assertEqual("sensitive_field_accessed", event["event_type"])
        self.assertEqual("decision_agent", event["actor"])
        self.assertEqual("task-001", event["task_id"])
        self.assertEqual(["customer_pii", "finance", "procurement_price"], event["metadata"]["categories"])
        self.assertEqual(["客户手机号", "现金流", "采购单价"], event["metadata"]["fields"])
        self.assertNotIn("13812345678", json.dumps(event, ensure_ascii=False))

        events = json.loads(self.audit_tools.list_audit_events(event_type="sensitive_field_accessed"))["events"]
        self.assertEqual(1, len(events))

    def test_registry_summary_rejects_paths_outside_warehouse(self) -> None:
        warehouse = self.root / "data" / "warehouse"
        warehouse.mkdir(parents=True, exist_ok=True)
        registry_path = warehouse / "dataset_registry.json"
        registry_path.write_text(
            json.dumps(
                {
                    "datasets": {
                        "orders": {
                            "field_profiles": [{"field": "客户手机号"}],
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        outside = self.root / "outside.json"
        outside.write_text(json.dumps({"datasets": {}}), encoding="utf-8")

        ok = json.loads(self.sensitive_tools.summarize_sensitive_fields_from_registry(str(registry_path)))
        denied = json.loads(self.sensitive_tools.summarize_sensitive_fields_from_registry(str(outside)))

        self.assertEqual(ok["status"], "success")
        self.assertEqual(ok["total_sensitive_fields"], 1)
        self.assertEqual(denied["status"], "error")
        self.assertIn("warehouse", denied["error"])


if __name__ == "__main__":
    unittest.main()
