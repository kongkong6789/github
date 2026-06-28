from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


class WikiLifecycleToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            key: os.environ.get(key)
            for key in ["A2A_DATA_DIR", "A2A_DOCS_DIR", "A2A_WIKI_DIR"]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.docs_dir = self.root / "docs"
        self.wiki_dir = self.root / "wiki"
        self.data_dir.mkdir(parents=True)
        self.docs_dir.mkdir(parents=True)
        self.wiki_dir.mkdir(parents=True)
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_DOCS_DIR"] = str(self.docs_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)

        import src.a2a_ecommerce_demo.wiki_lifecycle_tools as wiki_lifecycle_tools

        self.tools = importlib.reload(wiki_lifecycle_tools)

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_scaffold_refresh_index_and_lint_report_wiki_health(self) -> None:
        decision = self.wiki_dir / "decisions" / "unove-stock.md"
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(
            "# UNOVE 库存判断\n\n"
            "UNOVE 麦歌仓库存充足，但需要继续观察抖音渠道动销。\n",
            encoding="utf-8",
        )
        product = self.wiki_dir / "products" / "UNOVE.md"
        product.parent.mkdir(parents=True)
        product.write_text(
            "---\n"
            "type: brand\n"
            "updated_at: 2026-05-20T00:00:00Z\n"
            "evidence:\n"
            "  - wiki/decisions/unove-stock.md\n"
            "---\n\n"
            "# UNOVE\n\n"
            "UNOVE 品牌页。\n",
            encoding="utf-8",
        )

        scaffold = json.loads(self.tools.ensure_wiki_knowledge_scaffold())
        self.assertEqual("success", scaffold["status"])
        self.assertTrue((self.docs_dir / "wiki_schema.md").exists())
        self.assertTrue((self.wiki_dir / "AGENTS.md").exists())
        self.assertTrue((self.wiki_dir / "log.md").exists())

        index = json.loads(self.tools.refresh_wiki_index())
        self.assertEqual("success", index["status"])
        index_text = (self.wiki_dir / "index.md").read_text(encoding="utf-8")
        self.assertIn("[[products/UNOVE|UNOVE]]", index_text)
        self.assertIn("[[decisions/unove-stock|UNOVE 库存判断]]", index_text)

        health = json.loads(self.tools.lint_wiki_knowledge_base())
        self.assertEqual("warning", health["status"])
        self.assertGreaterEqual(health["page_count"], 4)
        self.assertGreaterEqual(health["missing_frontmatter_count"], 1)
        self.assertIn("知识库复盘问题", "\n".join(health["review_questions"]))

    def test_archive_decision_and_claim_evidence_update_log(self) -> None:
        json.loads(self.tools.ensure_wiki_knowledge_scaffold())

        claim_result = json.loads(
            self.tools.register_wiki_claim_evidence(
                claim="UNOVE 大贸库存主要集中在麦歌仓",
                evidence_paths=["wiki/decisions/source-report.md"],
                data_source="ERP_live_readonly",
                status="current",
                query_time="2026-05-20T08:00:00Z",
                row_count=2364,
                filters={"brand": "UNOVE", "warehouse_scope": "大贸"},
                object_refs=["UNOVE", "麦歌仓"],
            )
        )
        self.assertEqual("success", claim_result["status"])
        claim_path = Path(claim_result["saved_to"])
        self.assertTrue(claim_path.exists())
        claim_text = claim_path.read_text(encoding="utf-8")
        self.assertIn("type: claim", claim_text)
        self.assertIn("row_count: 2364", claim_text)
        self.assertIn("live_read_only_fallback", claim_text)

        archive_result = json.loads(
            self.tools.archive_decision_to_wiki(
                title="UNOVE 全渠道库存快照",
                content="## 结论\n\nUNOVE 当前总可用库存约 96.8 万，麦歌仓为主要大贸库存。",
                evidence_paths=[claim_result["wiki_path"]],
                source_query="使用吉客云查询下unove当前全渠道库存信息",
                live_snapshot=True,
                query_time="2026-05-20T08:00:00Z",
                row_count=4727,
                filters={"brand": "UNOVE"},
            )
        )
        self.assertEqual("success", archive_result["status"])
        decision_path = Path(archive_result["saved_to"])
        self.assertTrue(decision_path.exists())
        decision_text = decision_path.read_text(encoding="utf-8")
        self.assertIn("type: decision", decision_text)
        self.assertIn("live_read_only_fallback", decision_text)
        self.assertIn("使用吉客云查询", decision_text)

        log_text = (self.wiki_dir / "log.md").read_text(encoding="utf-8")
        self.assertIn("claim | UNOVE 大贸库存主要集中在麦歌仓", log_text)
        self.assertIn("decision | UNOVE 全渠道库存快照", log_text)

    def test_normalize_legacy_wiki_pages_adds_frontmatter_and_evidence(self) -> None:
        json.loads(self.tools.ensure_wiki_knowledge_scaffold())
        decision = self.wiki_dir / "decisions" / "legacy-report.md"
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(
            "# 旧经营报告\n\n"
            "- Task ID: `20260515-legacy-task`\n"
            "- Report: `/tmp/workspace/data/reports/legacy-report.md`\n\n"
            "## Consolidated View\n"
            "- Evidence: /tmp/workspace/data/warehouse/a2a.duckdb, "
            "/tmp/workspace/data/warehouse/dataset_registry.json\n",
            encoding="utf-8",
        )
        dataset_page = self.wiki_dir / "datasets" / "legacy" / "overview.md"
        dataset_page.parent.mkdir(parents=True)
        dataset_page.write_text(
            "# Dataset Overview - legacy\n\n"
            "- Source file: `/tmp/workspace/raw/legacy.xlsx`\n"
            "- DuckDB: `warehouse/a2a.duckdb`\n",
            encoding="utf-8",
        )
        existing = self.wiki_dir / "decisions" / "existing.md"
        existing.write_text(
            "---\n"
            "type: decision\n"
            "updated_at: 2026-05-20T00:00:00Z\n"
            "---\n\n"
            "# Existing Decision\n\n"
            "- Raw: `legacy.xlsx`\n",
            encoding="utf-8",
        )

        before = json.loads(self.tools.lint_wiki_knowledge_base())
        self.assertGreaterEqual(before["missing_frontmatter_count"], 2)
        self.assertGreaterEqual(before["unsourced_claim_count"], 2)

        preview = json.loads(self.tools.normalize_legacy_wiki_pages(dry_run=True))
        self.assertEqual("success", preview["status"])
        self.assertEqual(3, preview["candidate_count"])
        self.assertFalse(decision.read_text(encoding="utf-8").startswith("---"))

        result = json.loads(self.tools.normalize_legacy_wiki_pages(dry_run=False))
        self.assertEqual("success", result["status"])
        self.assertEqual(3, result["updated_count"])
        decision_text = decision.read_text(encoding="utf-8")
        self.assertTrue(decision_text.startswith("---\ntype: decision\n"))
        self.assertIn("evidence:", decision_text)
        self.assertIn("data/reports/legacy-report.md", decision_text)
        self.assertIn("data/warehouse/a2a.duckdb", decision_text)
        self.assertIn("data/warehouse/dataset_registry.json", decision_text)
        self.assertIn("source_boundary: legacy_wiki_backfill", decision_text)
        self.assertIn("type: dataset", dataset_page.read_text(encoding="utf-8"))
        self.assertIn("raw/legacy.xlsx", dataset_page.read_text(encoding="utf-8"))
        self.assertIn("evidence:", existing.read_text(encoding="utf-8"))

        health = json.loads(self.tools.lint_wiki_knowledge_base())
        self.assertEqual("success", health["status"])
        self.assertEqual(0, health["missing_frontmatter_count"])
        self.assertEqual(0, health["unsourced_claim_count"])


if __name__ == "__main__":
    unittest.main()
