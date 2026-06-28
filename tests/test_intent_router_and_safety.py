from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


class IntentRouterAndSafetyTests(unittest.TestCase):
    def test_existing_data_analysis_is_read_only_intent_everywhere(self) -> None:
        from src.a2a_ecommerce_demo.intent_router import classify_user_intent

        intent = classify_user_intent(
            "基于所有已有数据，分析 5/6 月 UNOVE 销售提升决策，输出优先级、执行清单、关键依据、风险和数据缺口。"
        )

        self.assertEqual("existing_data_analysis", intent.intent)
        self.assertFalse(intent.start_background_workflow)
        self.assertTrue(intent.read_only)

    def test_new_raw_ingest_intent_still_starts_background_workflow(self) -> None:
        from src.a2a_ecommerce_demo.intent_router import classify_user_intent

        intent = classify_user_intent("我刚放了 raw Excel，帮我整理入库并同步知识库")

        self.assertEqual("new_material_ingest", intent.intent)
        self.assertTrue(intent.start_background_workflow)
        self.assertFalse(intent.read_only)

    def test_atomic_json_write_replaces_complete_document(self) -> None:
        from src.a2a_ecommerce_demo.state_io import atomic_write_json, load_json

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            atomic_write_json(path, {"version": 1, "items": [1]})
            atomic_write_json(path, {"version": 2, "items": [1, 2, 3]})

            self.assertEqual({"version": 2, "items": [1, 2, 3]}, load_json(path))
            self.assertFalse(any(path.parent.glob("*.tmp")))

    def test_fact_query_rejects_external_file_functions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["A2A_DATA_DIR"] = tmp
            os.environ["A2A_WAREHOUSE_DIR"] = str(Path(tmp) / "warehouse")
            import src.a2a_ecommerce_demo.fact_layer_tools as fact_layer_tools

            fact_layer_tools = importlib.reload(fact_layer_tools)

            with self.assertRaisesRegex(ValueError, "not allowed"):
                fact_layer_tools.query_fact_layer("SELECT * FROM read_csv_auto('/tmp/secret.csv')")
            blocked_sql = [
                "SELECT * FROM '/tmp/secret.csv'",
                "COPY (SELECT 1) TO '/tmp/out.csv'",
                "INSTALL httpfs",
                "LOAD httpfs",
                "ATTACH '/tmp/other.duckdb' AS other",
                "SELECT * FROM main.some_table",
            ]
            for sql in blocked_sql:
                with self.subTest(sql=sql):
                    with self.assertRaisesRegex(ValueError, "not allowed|Only SELECT/CTE|Only datasets.* and marts.*"):
                        fact_layer_tools.query_fact_layer(sql)

    def test_workflow_rejection_uses_unified_intent_router(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["A2A_DATA_DIR"] = tmp
            os.environ["A2A_TASK_DIR"] = str(Path(tmp) / "tasks")
            import src.a2a_ecommerce_demo.task_delegation_tools as task_delegation_tools

            task_delegation_tools = importlib.reload(task_delegation_tools)
            result = json.loads(
                task_delegation_tools.start_company_workflow_task("基于所有已有数据分析 UNOVE 销售提升决策")
            )

            self.assertEqual("rejected", result["status"])
            self.assertEqual("analysis_request_should_use_existing_data", result["reason"])


if __name__ == "__main__":
    unittest.main()
