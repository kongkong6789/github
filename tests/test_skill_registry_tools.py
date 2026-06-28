from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


def _reload_skill_modules():
    import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools
    import src.a2a_ecommerce_demo.skill_registry_tools as skill_registry_tools

    enterprise_audit_tools = importlib.reload(enterprise_audit_tools)
    skill_registry_tools = importlib.reload(skill_registry_tools)
    return skill_registry_tools, enterprise_audit_tools


class SkillRegistryToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.wiki_dir = self.root / "wiki"
        self.strategy_page = self.wiki_dir / "strategy" / "unove-domestic-channel-strategy.md"
        self.strategy_page.parent.mkdir(parents=True, exist_ok=True)
        self.strategy_page.write_text(
            "# UNOVE 国内渠道经营策略\n\n"
            "天猫主要靠日销和推广；抖音每月目标 200 万+，主要靠达播和千川。\n"
            "得物和唯品会不考虑，天猫超市不需要建议。\n",
            encoding="utf-8",
        )
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_SKILL_REGISTRY_DIR"] = str(self.data_dir / "skill_registry")
        os.environ["A2A_AGENT_TEMPLATE_DIR"] = str(self.data_dir / "agent_templates")
        os.environ["A2A_AUDIT_DIR"] = str(self.data_dir / "audit")
        self.skill_tools, self.audit_tools = _reload_skill_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_wiki_page_becomes_approved_enableable_agent_skill_and_active_template(self) -> None:
        draft = json.loads(
            self.skill_tools.create_agent_skill_from_wiki(
                "strategy/unove-domestic-channel-strategy.md",
                skill_id="unove_domestic_channel_strategy",
                name="UNOVE 国内渠道经营策略 Skill",
                scenarios_json=json.dumps(["渠道分析", "月度计划", "分销线下跟进"], ensure_ascii=False),
                tool_allowlist_json=json.dumps(
                    [
                        "summarize_business_data",
                        "query_fact_layer",
                        "query_lightrag",
                        "query_erp_live_snapshot",
                        "list_runtime_capabilities",
                        "invoke_runtime_capability",
                    ],
                    ensure_ascii=False,
                ),
                output_schema_json=json.dumps(["channel_rules", "targets", "data_gaps", "next_actions"], ensure_ascii=False),
                created_by="tester",
            )
        )

        self.assertEqual("draft", draft["skill"]["status"])
        self.assertEqual(0, draft["skill"]["version"])
        self.assertTrue(draft["skill"]["permission_preview"]["requires_human_confirmation"])
        self.assertEqual("wiki/strategy/unove-domestic-channel-strategy.md", draft["skill"]["source_wiki_path"])
        self.assertIn("list_runtime_capabilities", draft["skill"]["tool_allowlist"])
        self.assertIn("invoke_runtime_capability", draft["skill"]["tool_allowlist"])
        self.assertTrue(Path(draft["registry_path"]).exists())

        approved = json.loads(
            self.skill_tools.approve_agent_skill(
                "unove_domestic_channel_strategy",
                approved_by="tester",
                decision="approve",
            )
        )

        self.assertEqual("active", approved["skill"]["status"])
        self.assertEqual(1, approved["skill"]["version"])
        self.assertTrue(Path(approved["template_path"]).exists())
        template = json.loads(Path(approved["template_path"]).read_text(encoding="utf-8"))
        self.assertEqual("active", template["status"])
        self.assertIn("天猫主要靠日销和推广", template["prompt"])

        disabled = json.loads(
            self.skill_tools.set_agent_skill_status(
                "unove_domestic_channel_strategy",
                "disabled",
                changed_by="tester",
            )
        )
        self.assertEqual("disabled", disabled["skill"]["status"])

        updated = json.loads(
            self.skill_tools.update_agent_skill(
                "unove_domestic_channel_strategy",
                updates_json=json.dumps({"scenarios": ["渠道分析", "月度计划", "竞品监控"]}, ensure_ascii=False),
                updated_by="tester",
            )
        )
        self.assertEqual(2, updated["skill"]["version"])
        self.assertIn("竞品监控", updated["skill"]["scenarios"])

        rolled_back = json.loads(
            self.skill_tools.rollback_agent_skill(
                "unove_domestic_channel_strategy",
                target_version=1,
                changed_by="tester",
            )
        )
        self.assertEqual(3, rolled_back["skill"]["version"])
        self.assertEqual(1, rolled_back["skill"]["previous_version"])
        self.assertEqual("active", rolled_back["skill"]["status"])

        skills = json.loads(self.skill_tools.list_agent_skills())["skills"]
        self.assertEqual(["unove_domestic_channel_strategy"], [item["skill_id"] for item in skills])

        event_types = {event["event_type"] for event in json.loads(self.audit_tools.list_audit_events())["events"]}
        self.assertIn("agent_skill_drafted", event_types)
        self.assertIn("agent_skill_approved", event_types)
        self.assertIn("agent_skill_status_changed", event_types)
        self.assertIn("agent_skill_updated", event_types)
        self.assertIn("agent_skill_rolled_back", event_types)

    def test_new_skill_approval_without_decision_returns_agent_inbox_interrupt_shape(self) -> None:
        json.loads(
            self.skill_tools.create_agent_skill_from_wiki(
                "strategy/unove-domestic-channel-strategy.md",
                skill_id="needs_review_skill",
                name="Needs Review Skill",
                created_by="tester",
            )
        )

        approval = json.loads(self.skill_tools.approve_agent_skill("needs_review_skill", approved_by="tester"))

        self.assertEqual("confirmation_required", approval["status"])
        self.assertTrue(approval["requires_confirmation"])
        self.assertEqual("approve_agent_skill", approval["interrupt"]["value"]["action_requests"][0]["name"])
        self.assertEqual(["approve", "reject"], approval["interrupt"]["value"]["review_configs"][0]["allowed_decisions"])


if __name__ == "__main__":
    unittest.main()
