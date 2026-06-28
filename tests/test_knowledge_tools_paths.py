from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook


class KnowledgeToolsPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.wiki_dir = self.root / "wiki"
        self.raw_dir = self.root / "raw"
        self.wiki_dir.mkdir(parents=True)
        self.raw_dir.mkdir(parents=True)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_RAW_DIR"] = str(self.raw_dir)

        import src.a2a_ecommerce_demo.knowledge_tools as knowledge_tools

        self.knowledge_tools = importlib.reload(knowledge_tools)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_read_wiki_page_accepts_paths_prefixed_with_wiki(self) -> None:
        page = self.wiki_dir / "decisions" / "report.md"
        page.parent.mkdir(parents=True)
        page.write_text("# Report\n\nDecision evidence.", encoding="utf-8")

        result = json.loads(self.knowledge_tools.read_wiki_page("wiki/decisions/report.md"))

        self.assertEqual("decisions/report.md", result["path"])
        self.assertIn("Decision evidence.", result["content"])

    def test_raw_excel_ingest_falls_back_to_ooxml_when_styles_are_invalid(self) -> None:
        path = self.raw_dir / "外贸组-各品牌GMV.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "GMV"
        sheet.append(["日期", "品牌", "GMV"])
        sheet.append(["2026-05-01", "UNOVE", 1200])
        workbook.save(path)

        with patch("openpyxl.load_workbook", side_effect=TypeError("expected <class 'openpyxl.styles.fills.Fill'>")):
            result = json.loads(self.knowledge_tools.ingest_raw_file(path.name))

        content = (self.wiki_dir / result["wiki_path"]).read_text(encoding="utf-8")
        self.assertIn("OOXML fallback", content)
        self.assertIn("UNOVE", content)


if __name__ == "__main__":
    unittest.main()
