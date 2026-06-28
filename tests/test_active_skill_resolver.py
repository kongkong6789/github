from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from langchain_core.messages import HumanMessage


def _reload_modules():
    import src.a2a_ecommerce_demo.active_skill_resolver as active_skill_resolver
    import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools
    import src.a2a_ecommerce_demo.skill_registry_tools as skill_registry_tools
    import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

    enterprise_audit_tools = importlib.reload(enterprise_audit_tools)
    skill_registry_tools = importlib.reload(skill_registry_tools)
    active_skill_resolver = importlib.reload(active_skill_resolver)
    supervisor_app = importlib.reload(supervisor_app)
    return active_skill_resolver, skill_registry_tools, supervisor_app


class ActiveSkillResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.wiki_dir = self.root / "wiki"
        page = self.wiki_dir / "strategy" / "unove-domestic-channel-strategy.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            "# UNOVE 国内渠道经营策略\n\n"
            "天猫主要靠日销和推广。抖音每月目标 200 万+，主要靠达播和千川。\n"
            "分销和线下客户要跟进销售进度、客户分层和很久没下单客户。\n",
            encoding="utf-8",
        )
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_SKILL_REGISTRY_DIR"] = str(self.data_dir / "skill_registry")
        os.environ["A2A_AGENT_TEMPLATE_DIR"] = str(self.data_dir / "agent_templates")
        os.environ["A2A_AUDIT_DIR"] = str(self.data_dir / "audit")
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["OPENAI_MODEL"] = "deepseek-v4-pro"
        os.environ["OPENAI_BASE_URL"] = "https://api.deepseek.com"
        self.resolver, self.skill_tools, self.supervisor_app = _reload_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _create_active_unove_skill(self) -> None:
        json.loads(
            self.skill_tools.create_agent_skill_from_wiki(
                "strategy/unove-domestic-channel-strategy.md",
                skill_id="unove_domestic_channel_strategy",
                name="UNOVE 国内渠道经营策略 Skill",
                scenarios_json=json.dumps(["渠道分析", "月度计划", "分销线下跟进"], ensure_ascii=False),
                tool_allowlist_json=json.dumps(
                    ["summarize_business_data", "query_fact_layer", "query_lightrag", "query_erp_live_snapshot"],
                    ensure_ascii=False,
                ),
                output_schema_json=json.dumps(["channel_rules", "monthly_targets", "next_actions"], ensure_ascii=False),
                created_by="tester",
            )
        )
        json.loads(
            self.skill_tools.approve_agent_skill(
                "unove_domestic_channel_strategy",
                approved_by="tester",
                decision="approve",
            )
        )

    def test_active_skill_matches_user_prompt_and_builds_injection_message(self) -> None:
        self._create_active_unove_skill()

        matches = self.resolver.resolve_active_skills_for_prompt("帮我按 UNOVE 抖音和天猫 6 月目标做渠道计划", limit=3)

        self.assertEqual(["unove_domestic_channel_strategy"], [item["skill_id"] for item in matches])
        injection = self.resolver.build_active_skill_system_message(matches)
        self.assertIsNotNone(injection)
        self.assertEqual("system", injection.type)
        self.assertIn("Active Skill matched", injection.content)
        self.assertIn("UNOVE 国内渠道经营策略", injection.content)
        self.assertIn("抖音每月目标 200 万+", injection.content)

    def test_inactive_skill_does_not_match(self) -> None:
        self._create_active_unove_skill()
        json.loads(
            self.skill_tools.set_agent_skill_status(
                "unove_domestic_channel_strategy",
                "disabled",
                changed_by="tester",
            )
        )

        matches = self.resolver.resolve_active_skills_for_prompt("帮我按 UNOVE 抖音和天猫 6 月目标做渠道计划")

        self.assertEqual([], matches)

    def test_supervisor_model_hook_injects_active_skill_without_mutating_state_messages(self) -> None:
        self._create_active_unove_skill()
        original_messages = [HumanMessage(content="帮我按 UNOVE 抖音和天猫 6 月目标做渠道计划")]

        hook_result = self.supervisor_app._sanitize_model_input_hook({"messages": original_messages})
        llm_messages = hook_result["llm_input_messages"]

        self.assertEqual(1, len(original_messages))
        self.assertEqual("system", llm_messages[0].type)
        self.assertIn("unove_domestic_channel_strategy", llm_messages[0].content)
        self.assertEqual("human", llm_messages[-1].type)

    def test_folder_skill_metadata_is_injected_for_multi_agent_context(self) -> None:
        skill_dir = self.root / "skills" / "retail-ops"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("# 零售运营 Skill\n\n门店库存和渠道销售联动分析。", encoding="utf-8")
        registry_dir = self.data_dir / "skill_registry"
        record_path = registry_dir / "skills" / "retail_ops.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "schema": "a2a_agent_skill_v1",
            "skill": {
                "skill_id": "retail_ops",
                "name": "零售运营 Skill",
                "status": "active",
                "version": 1,
                "source_wiki_path": "wiki/skills/imported/retail_ops.md",
                "source_type": "skill_directory",
                "source_skill_path": "skills/retail-ops",
                "managed_skill_dir": "data/skill_registry/imports/retail_ops",
                "scenarios": ["门店库存", "渠道销售"],
                "tool_allowlist": ["query_fact_layer"],
                "output_schema": ["summary", "evidence"],
                "updated_at": "2026-05-22T00:00:00.000Z",
            },
            "versions": [],
            "wiki_content": "门店库存和渠道销售联动分析。",
        }
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        (registry_dir / "registry.json").write_text(
            json.dumps(
                {
                    "schema": "a2a_agent_skill_registry_v1",
                    "skills": {
                        "retail_ops": {
                            "skill_id": "retail_ops",
                            "name": "零售运营 Skill",
                            "status": "active",
                            "version": 1,
                            "source_wiki_path": "wiki/skills/imported/retail_ops.md",
                            "source_type": "skill_directory",
                            "source_skill_path": "skills/retail-ops",
                            "managed_skill_dir": "data/skill_registry/imports/retail_ops",
                            "tool_count": 1,
                            "updated_at": "2026-05-22T00:00:00.000Z",
                            "path": str(record_path),
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.data_dir / "agent_templates").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "agent_templates" / "retail_ops.json").write_text(
            json.dumps({"prompt": "门店库存和渠道销售联动分析。"}, ensure_ascii=False),
            encoding="utf-8",
        )

        matches = self.resolver.resolve_active_skills_for_prompt("帮我分析门店库存和渠道销售", limit=3)
        injection = self.resolver.build_active_skill_system_message(matches)

        self.assertEqual(["retail_ops"], [item["skill_id"] for item in matches])
        self.assertEqual("skills/retail-ops", matches[0]["source_skill_path"])
        self.assertEqual("data/skill_registry/imports/retail_ops", matches[0]["managed_skill_dir"])
        self.assertIsNotNone(injection)
        self.assertIn("source_skill_path: skills/retail-ops", injection.content)
        self.assertIn("managed_skill_dir: data/skill_registry/imports/retail_ops", injection.content)


if __name__ == "__main__":
    unittest.main()
