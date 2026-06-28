from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


class P2KnowledgeMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            key: os.environ.get(key)
            for key in [
                "A2A_DATA_DIR",
                "A2A_WIKI_DIR",
                "A2A_AGENT_TEMPLATE_DIR",
            ]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.wiki_dir = self.root / "wiki"
        self.template_dir = self.data_dir / "agent_templates"
        self.wiki_dir.mkdir(parents=True)
        self.data_dir.mkdir(parents=True)
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_AGENT_TEMPLATE_DIR"] = str(self.template_dir)

        import src.a2a_ecommerce_demo.agent_factory_tools as agent_factory_tools
        import src.a2a_ecommerce_demo.knowledge_tools as knowledge_tools

        self.agent_factory_tools = importlib.reload(agent_factory_tools)
        self.knowledge_tools = importlib.reload(knowledge_tools)

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_append_durable_insight_only_accepts_reusable_knowledge_types(self) -> None:
        rejected = json.loads(
            self.knowledge_tools.append_durable_insight(
                dataset_slug="unove",
                title="临时想法",
                content="今天随手猜测一下。",
                insight_type="temporary_observation",
            )
        )
        self.assertEqual("rejected", rejected["status"])
        self.assertIn("field_definition", rejected["allowed_types"])

        saved = json.loads(
            self.knowledge_tools.append_durable_insight(
                dataset_slug="unove",
                title="库存字段口径",
                content="`ending_inventory` 使用期末可用库存，不等于采购在途。",
                insight_type="field_definition",
                evidence_paths=["wiki/datasets/unove/field-dictionary.md"],
            )
        )

        self.assertEqual("success", saved["status"])
        path = Path(saved["saved_to"])
        content = path.read_text(encoding="utf-8")
        self.assertIn("durable-insight", content)
        self.assertIn("field_definition", content)
        self.assertIn("wiki/datasets/unove/field-dictionary.md", content)

    def test_save_wiki_page_as_prompt_template_creates_draft_template(self) -> None:
        page = self.wiki_dir / "decisions" / "restock-playbook.md"
        page.parent.mkdir(parents=True)
        page.write_text(
            "# 补货分析模板\n\n"
            "## 适用场景\n"
            "- UNOVE SKU 补货、断货、库存周转分析。\n\n"
            "## 输出要求\n"
            "- 必须引用 DuckDB mart 和 wiki 证据。\n",
            encoding="utf-8",
        )

        result = json.loads(
            self.agent_factory_tools.save_wiki_page_as_prompt_template(
                wiki_path="wiki/decisions/restock-playbook.md",
                template_id="unove_restock_playbook",
                notes="来自 P2 durable knowledge。",
            )
        )

        self.assertEqual("success", result["status"])
        self.assertEqual("draft", result["template"]["status"])
        self.assertEqual("wiki/decisions/restock-playbook.md", result["template"]["source_wiki_path"])
        self.assertIn("UNOVE SKU 补货", result["template"]["prompt"])
        self.assertTrue(Path(result["saved_to"]).exists())


if __name__ == "__main__":
    unittest.main()
