from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _reload_dynamic_agent_hub():
    import src.a2a_ecommerce_demo.dynamic_agent_hub as dynamic_agent_hub
    import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools

    enterprise_audit_tools = importlib.reload(enterprise_audit_tools)
    dynamic_agent_hub = importlib.reload(dynamic_agent_hub)
    return dynamic_agent_hub


class P17ReferenceAbsorptionTests(unittest.TestCase):
    def test_seeded_agency_agent_templates_are_draft_evidence_first_specs(self) -> None:
        template_dir = PROJECT_ROOT / "data" / "agent_templates"
        expected = {
            "china_ecommerce_operator",
            "supply_chain_strategist",
            "fpa_analyst",
            "paid_media_auditor",
            "compliance_auditor",
            "data_consolidation_agent",
        }

        loaded = {}
        for template_id in expected:
            path = template_dir / f"{template_id}.json"
            self.assertTrue(path.exists(), template_id)
            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded[template_id] = payload

            self.assertEqual("a2a_agent_template_v1", payload["schema"])
            self.assertEqual(template_id, payload["template_id"])
            self.assertEqual("draft", payload["status"])
            self.assertEqual("agency-agents", payload["source_repo"])
            self.assertTrue(payload["evidence_required"])
            self.assertIn(payload["risk_level"], {"low", "medium"})
            self.assertTrue(payload["prompt"].strip())
            self.assertIn("DuckDB", payload["prompt"])
            self.assertIn("ERP", payload["prompt"])
            self.assertIn("缺数据", payload["prompt"])
            self.assertTrue(payload["tool_allowlist"])
            self.assertTrue(payload["output_schema"])

        self.assertEqual(set(loaded), expected)

    def test_dynamic_agent_can_draft_from_template_without_activating_or_writing_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            template_dir = data_dir / "agent_templates"
            template_dir.mkdir(parents=True)
            (template_dir / "supply_chain_strategist.json").write_text(
                json.dumps(
                    {
                        "schema": "a2a_agent_template_v1",
                        "template_id": "supply_chain_strategist",
                        "status": "draft",
                        "source_repo": "agency-agents",
                        "source_path": "supply-chain/strategist.md",
                        "role": "供应链策略 Agent",
                        "scenarios": ["库存周转", "供应商风险"],
                        "prompt": "必须优先查 DuckDB，ERP 只读兜底，缺数据必须列出。",
                        "tool_allowlist": [
                            "query_inventory_snapshot",
                            "query_sales_history",
                            "create_purchase_order",
                        ],
                        "output_schema": ["summary", "evidence", "risks", "next_actions"],
                        "risk_level": "medium",
                        "evidence_required": True,
                        "owner": "ops",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.environ["A2A_DATA_DIR"] = str(data_dir)
            os.environ["A2A_AGENT_REGISTRY_DIR"] = str(data_dir / "agent_registry")
            os.environ["A2A_AGENT_TEMPLATE_DIR"] = str(template_dir)
            os.environ["A2A_AUDIT_DIR"] = str(data_dir / "audit")
            dynamic_agent_hub = _reload_dynamic_agent_hub()

            draft = json.loads(
                dynamic_agent_hub.draft_dynamic_agent_spec_from_template(
                    "supply_chain_strategist",
                    task_description="给 UNOVE 核心款做补货和供应商风险复盘",
                    created_by="tester",
                )
            )

            self.assertEqual("draft", draft["status"])
            self.assertEqual("draft", draft["spec"]["status"])
            self.assertEqual("supply_chain_strategist", draft["spec"]["source_template_id"])
            self.assertEqual("agency-agents", draft["spec"]["source_repo"])
            self.assertIn("query_inventory_snapshot", draft["spec"]["tool_allowlist"])
            self.assertNotIn("create_purchase_order", draft["spec"]["tool_allowlist"])
            self.assertIn("create_purchase_order", draft["permission_preview"]["blocked_tools"])
            self.assertTrue(draft["permission_preview"]["requires_human_confirmation"])


if __name__ == "__main__":
    unittest.main()
