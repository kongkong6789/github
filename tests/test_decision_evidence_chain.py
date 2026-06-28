from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _reload_modules():
    import src.a2a_ecommerce_demo.business_tools as business_tools
    import src.a2a_ecommerce_demo.task_delegation_tools as task_delegation_tools

    business_tools = importlib.reload(business_tools)
    task_delegation_tools = importlib.reload(task_delegation_tools)
    return business_tools, task_delegation_tools


class DecisionEvidenceChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            key: os.environ.get(key)
            for key in [
                "A2A_DATA_DIR",
                "A2A_WAREHOUSE_DIR",
                "A2A_TASK_DIR",
                "A2A_WIKI_DIR",
                "A2A_DUCKDB_PATH",
                "A2A_DATASET_REGISTRY",
            ]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.warehouse_dir = self.data_dir / "warehouse"
        self.task_dir = self.data_dir / "tasks"
        self.wiki_dir = self.root / "wiki"
        self.warehouse_dir.mkdir(parents=True)
        self.task_dir.mkdir(parents=True)
        self.wiki_dir.mkdir(parents=True)
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_WAREHOUSE_DIR"] = str(self.warehouse_dir)
        os.environ["A2A_TASK_DIR"] = str(self.task_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_DUCKDB_PATH"] = str(self.warehouse_dir / "a2a.duckdb")
        os.environ["A2A_DATASET_REGISTRY"] = str(self.warehouse_dir / "dataset_registry.json")
        self._write_registry()
        self.business_tools, self.task_delegation_tools = _reload_modules()

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def _write_registry(self) -> None:
        registry = {
            "schema": "a2a_dataset_registry_v1",
            "datasets": {
                "ops-mart": {
                    "dataset_slug": "ops-mart",
                    "manifest_path": str(self.warehouse_dir / "large_excel" / "ops" / "manifest.json"),
                    "quality_report_path": str(self.warehouse_dir / "large_excel" / "ops" / "quality_report.json"),
                    "duckdb_path": str(self.warehouse_dir / "a2a.duckdb"),
                    "wiki_pages": {
                        "overview": "wiki/datasets/ops-mart/overview.md",
                        "field_dictionary": "wiki/datasets/ops-mart/field-dictionary.md",
                        "quality_report": "wiki/datasets/ops-mart/quality-report.md",
                    },
                    "sheet_views": [
                        {
                            "sheet_name": "Inventory",
                            "headers": ["SKU", "日期", "期末库存", "销量"],
                        }
                    ],
                    "mart_views": [
                        {"category": "fact_inventory_daily", "view_name": "ops_inventory"},
                    ],
                }
            },
        }
        (self.warehouse_dir / "dataset_registry.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

    def test_analyze_company_strategy_outputs_structured_evidence_chain(self) -> None:
        quality = {
            "quality_level": "medium",
            "missing_field_groups": ["cash", "supplier"],
            "warnings": [],
            "fact_layer": {
                "available": True,
                "registry_path": str(self.warehouse_dir / "dataset_registry.json"),
                "duckdb_path": str(self.warehouse_dir / "a2a.duckdb"),
                "datasets": [
                    {
                        "dataset_slug": "ops-mart",
                        "overview_page": "wiki/datasets/ops-mart/overview.md",
                        "mart_views": ["fact_inventory_daily"],
                    }
                ],
                "tables": [{"schema": "marts", "name": "fact_inventory_daily"}],
            },
        }
        finance = {"metrics": {"cash": 0, "ad_spend_to_revenue": 0.1}}

        with (
            patch.object(self.business_tools, "_load_business_data", return_value={"inventory": []}),
            patch.object(self.business_tools, "assess_data_quality", return_value=json.dumps(quality, ensure_ascii=False)),
            patch.object(self.business_tools, "analyze_company_financial_position", return_value=json.dumps(finance, ensure_ascii=False)),
            patch.object(self.business_tools, "_has_fact_table", return_value=False),
        ):
            result = json.loads(self.business_tools.analyze_company_strategy("next_month"))

        chain = result["evidence_chain"]
        self.assertIn("wiki/datasets/ops-mart/overview.md", chain["wiki_pages"])
        self.assertEqual(["cash", "supplier"], chain["data_gaps"])
        self.assertIn(str(self.warehouse_dir / "large_excel" / "ops" / "manifest.json"), chain["manifest_paths"])
        self.assertIn(str(self.warehouse_dir / "large_excel" / "ops" / "quality_report.json"), chain["report_paths"])
        self.assertEqual(str(self.warehouse_dir / "dataset_registry.json"), chain["registry_path"])
        self.assertIn("fact_inventory_daily", {mart["mart"] for mart in chain["duckdb_marts"]})
        self.assertIn("SKU", chain["duckdb_marts"][0]["fields"])

    def test_save_decision_report_appends_evidence_section_and_returns_chain(self) -> None:
        result = json.loads(self.business_tools.save_decision_report("Boss Report", "# Boss Report\n\nDecision."))
        saved_path = Path(result["saved_to"])
        content = saved_path.read_text(encoding="utf-8")

        self.assertIn("## Evidence Chain", content)
        self.assertIn("### Wiki pages", content)
        self.assertIn("### DuckDB marts and fields", content)
        self.assertIn("### Manifest/report paths", content)
        self.assertIn("wiki/datasets/ops-mart/field-dictionary.md", content)
        self.assertIn(str(saved_path), result["evidence_chain"]["report_paths"])

    def test_finalize_workflow_report_preserves_evidence_chain_fields(self) -> None:
        task = {
            "task_id": "task-001",
            "goal": "经营决策",
            "requested_by": "test",
            "status": "running",
            "created_at": "2026-05-15 10:00:00",
            "updated_at": "2026-05-15 10:01:00",
            "steps": [
                {
                    "task": "company_strategy",
                    "status": "success",
                    "summary": "done",
                    "evidence": ["wiki/datasets/ops-mart/overview.md"],
                    "risks": [],
                    "missing_data": ["cash"],
                    "next_actions": ["补齐现金字段"],
                    "data": {
                        "evidence_chain": {
                            "wiki_pages": ["wiki/datasets/ops-mart/overview.md"],
                            "duckdb_marts": [{"mart": "fact_inventory_daily", "fields": ["SKU", "期末库存"]}],
                            "data_gaps": ["cash"],
                            "manifest_paths": [str(self.warehouse_dir / "large_excel" / "ops" / "manifest.json")],
                            "report_paths": [str(self.warehouse_dir / "large_excel" / "ops" / "quality_report.json")],
                        }
                    },
                }
            ],
            "notes": [],
        }
        (self.task_dir / "task-001.json").write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")

        with patch.object(self.task_delegation_tools, "append_decision_note", return_value="{}"):
            result = json.loads(self.task_delegation_tools.finalize_workflow_report("task-001", "经营报告"))

        saved_path = Path(result["report"]["saved_to"])
        content = saved_path.read_text(encoding="utf-8")
        self.assertIn("## Evidence Chain", content)
        self.assertIn("wiki/datasets/ops-mart/overview.md", content)
        self.assertIn("fact_inventory_daily", content)
        self.assertIn("SKU", content)
        self.assertIn(str(self.warehouse_dir / "large_excel" / "ops" / "manifest.json"), content)


if __name__ == "__main__":
    unittest.main()
