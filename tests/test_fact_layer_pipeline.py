from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from openpyxl import Workbook


def _reload_project_modules():
    import src.a2a_ecommerce_demo.business_tools as business_tools
    import src.a2a_ecommerce_demo.fact_layer_tools as fact_layer_tools
    import src.a2a_ecommerce_demo.knowledge_tools as knowledge_tools
    import src.a2a_ecommerce_demo.large_excel_tools as large_excel_tools
    import src.a2a_ecommerce_demo.lightrag_tools as lightrag_tools

    fact_layer_tools = importlib.reload(fact_layer_tools)
    knowledge_tools = importlib.reload(knowledge_tools)
    large_excel_tools = importlib.reload(large_excel_tools)
    business_tools = importlib.reload(business_tools)
    lightrag_tools = importlib.reload(lightrag_tools)
    return {
        "fact_layer_tools": fact_layer_tools,
        "knowledge_tools": knowledge_tools,
        "large_excel_tools": large_excel_tools,
        "business_tools": business_tools,
        "lightrag_tools": lightrag_tools,
    }


class FactLayerPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.raw_dir = self.root / "raw"
        self.data_dir = self.root / "data"
        self.warehouse_dir = self.data_dir / "warehouse"
        self.cleaned_dir = self.data_dir / "cleaned"
        self.wiki_dir = self.root / "wiki"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.warehouse_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        os.environ["A2A_RAW_DIR"] = str(self.raw_dir)
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_WAREHOUSE_DIR"] = str(self.warehouse_dir)
        os.environ["A2A_CLEANED_DIR"] = str(self.cleaned_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_DUCKDB_PATH"] = str(self.warehouse_dir / "a2a.duckdb")
        self.modules = _reload_project_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _build_workbook(self, path: Path) -> None:
        workbook = Workbook()
        inventory = workbook.active
        assert inventory is not None
        inventory.title = "Inventory Ledger"
        inventory.append(["日期", "SKU", "商品名称", "仓库", "期初总量", "入库总量", "出库总量", "期末总量", "在途"])
        inventory.append(["2026-05-01", "SKU-001", "Pet Fountain", "WH-A", 100, 20, 10, 110, 5])
        inventory.append(["2026-05-02", "SKU-001", "Pet Fountain", "WH-A", 110, 0, 15, 95, 8])
        sales = workbook.create_sheet("Sales Daily")
        sales.append(["日期", "SKU", "商品名称", "仓库", "销量", "销售额"])
        sales.append(["2026-05-01", "SKU-001", "Pet Fountain", "WH-A", 10, 500])
        sales.append(["2026-05-02", "SKU-001", "Pet Fountain", "WH-A", 15, 750])
        workbook.save(path)

    def _write_standard_csvs(self) -> None:
        (self.cleaned_dir / "inventory_cleaned.csv").write_text(
            "\n".join(
                [
                    "日期范围,货品编码,货品名称,仓库名称,期初总量,入库总量,出库总量,期末总量,在途",
                    "2026-05-01,SKU-001,Pet Fountain,WH-A,10,2,-1,11,3",
                    "2026-05-02,SKU-001,Pet Fountain,WH-A,11,0,-3,8,1",
                    "2026-05-02,SKU-002,Pet Feeder,WH-B,20,5,-2,23,0",
                    "2026-05-02,SKU-003,Slow Mover,WH-C,900,100,0,1000,0",
                    "2026-05-02,SKU-NEG,Negative Stock,WH-E,5,0,-2,-3,0",
                    "2026-05-02,SKU-IMB,Imbalanced Stock,WH-D,10,0,-2,20,0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (self.data_dir / "sales.csv").write_text(
            "\n".join(
                [
                    "日期,SKU,商品名称,仓库,销售渠道,销量,销售额",
                    "2026-05-01,SKU-001,Pet Fountain,WH-A,天猫,10,500",
                    "2026-05-02,SKU-001,Pet Fountain,WH-A,天猫,15,750",
                    "2026-05-02,SKU-002,Pet Feeder,WH-B,抖音,6,360",
                    "2026-05-08,SKU-001,Pet Fountain,WH-A,天猫,20,1000",
                    "2026-05-08,SKU-002,Pet Feeder,WH-B,抖音,4,240",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (self.data_dir / "ads.csv").write_text(
            "\n".join(
                [
                    "日期,SKU,商品名称,仓库,销售渠道,广告花费,ACOS,ROAS",
                    "2026-05-01,SKU-001,Pet Fountain,WH-A,天猫,120,0.25,4.0",
                    "2026-05-02,SKU-001,Pet Fountain,WH-A,天猫,80,0.20,5.0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (self.data_dir / "profit.csv").write_text(
            "\n".join(
                [
                    "日期,SKU,商品名称,仓库,销售渠道,收入,成本,毛利,现金",
                    "2026-05-01,SKU-001,Pet Fountain,WH-A,天猫,500,300,200,1000",
                    "2026-05-02,SKU-001,Pet Fountain,WH-A,天猫,750,420,330,1080",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_xmind_file(self, path: Path) -> None:
        content = [
            {
                "title": "运营方案",
                "rootTopic": {
                    "title": "年度增长计划",
                    "children": {
                        "attached": [
                            {
                                "title": "渠道",
                                "labels": ["重点"],
                                "children": {
                                    "attached": [
                                        {"title": "展会"},
                                        {"title": "达人合作"},
                                    ]
                                },
                            },
                            {"title": "营销"},
                        ]
                    },
                },
            }
        ]
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("content.json", json.dumps(content, ensure_ascii=False))

    def test_large_excel_pipeline_registers_fact_layer_and_wiki_pages(self) -> None:
        workbook_path = self.raw_dir / "fact-input.xlsx"
        self._build_workbook(workbook_path)

        large_excel_tools = self.modules["large_excel_tools"]
        business_tools = self.modules["business_tools"]

        result = json.loads(large_excel_tools.process_large_excel_file("fact-input.xlsx", rows_per_chunk=1))
        dataset_registry = result.get("dataset_registry", {})

        self.assertEqual(dataset_registry.get("dataset_slug"), "fact-input")
        self.assertTrue(Path(dataset_registry.get("duckdb_path", "")).exists())
        self.assertTrue(Path(self.wiki_dir / "datasets" / "fact-input" / "overview.md").exists())
        self.assertTrue(Path(self.wiki_dir / "datasets" / "fact-input" / "field-dictionary.md").exists())

        inventory_history = json.loads(business_tools.query_inventory_history("SKU-001", days=30, limit=20))
        self.assertGreater(inventory_history.get("row_count", 0), 0)

        registered = json.loads(business_tools.list_registered_datasets())
        self.assertEqual(len(registered.get("datasets", [])), 1)
        self.assertIn("fact_inventory_daily", {item.get("name") for item in json.loads(business_tools.list_fact_tables()).get("tables", [])})

    def test_lightrag_index_uses_wiki_only(self) -> None:
        workbook_path = self.raw_dir / "fact-input.xlsx"
        self._build_workbook(workbook_path)

        large_excel_tools = self.modules["large_excel_tools"]
        lightrag_tools = self.modules["lightrag_tools"]

        large_excel_tools.process_large_excel_file("fact-input.xlsx", rows_per_chunk=2)
        (self.cleaned_dir / "sample.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (self.warehouse_dir / "sample.csv").write_text("a,b\n3,4\n", encoding="utf-8")

        rebuild = json.loads(lightrag_tools.rebuild_lightrag_index())
        self.assertGreater(rebuild.get("documents", 0), 0)

        index_path = Path(rebuild["index_path"])
        index = json.loads(index_path.read_text(encoding="utf-8"))
        paths = [doc.get("path", "") for doc in index.get("documents", [])]
        self.assertTrue(all(path.startswith("wiki/") for path in paths))

    def test_standard_structured_files_register_finance_and_ads_marts(self) -> None:
        self._write_standard_csvs()
        fact_layer_tools = self.modules["fact_layer_tools"]
        business_tools = self.modules["business_tools"]

        result = json.loads(fact_layer_tools.register_all_fact_datasets())
        self.assertEqual(result["structured"]["status"], "success")

        finance = json.loads(business_tools.query_finance_history("SKU-001", days=30, limit=10))
        ads = json.loads(business_tools.query_ads_history("SKU-001", days=30, limit=10))
        inventory_snapshot = json.loads(business_tools.query_inventory_snapshot("SKU-001", nonzero_only=True, limit=10))
        self.assertGreater(finance.get("row_count", 0), 0)
        self.assertGreater(ads.get("row_count", 0), 0)
        self.assertGreater(inventory_snapshot.get("row_count", 0), 0)

        tables = {item.get("name") for item in json.loads(business_tools.list_fact_tables()).get("tables", [])}
        self.assertIn("fact_finance_daily", tables)
        self.assertIn("fact_ads_daily", tables)
        self.assertIn("dim_product_master", tables)
        self.assertIn("dim_channel", tables)
        self.assertIn("inventory_current", tables)

    def test_structured_registration_preserves_chinese_headers(self) -> None:
        source = self.cleaned_dir / "外贸组-各品牌GMV__26-UNOVE-GMV.csv"
        source.write_text(
            "条码,产品名称,活动价格,1,销售额合计\n"
            "8809669502571,UNOVE深层修护安瓶洗发水 500g,109,500,54500\n",
            encoding="utf-8-sig",
        )
        fact_layer_tools = self.modules["fact_layer_tools"]

        dataset = fact_layer_tools.register_structured_file_dataset(str(source))

        self.assertIn("条码", dataset["sheet_views"][0]["headers"])
        self.assertIn("产品名称", dataset["sheet_views"][0]["headers"])

    def test_controlled_question_planner_returns_safe_sql(self) -> None:
        self._write_standard_csvs()
        fact_layer_tools = self.modules["fact_layer_tools"]
        business_tools = self.modules["business_tools"]
        fact_layer_tools.register_all_fact_datasets()

        plan = json.loads(business_tools.plan_fact_query("最近30天 SKU-001 的广告表现", limit=20))
        self.assertTrue(plan.get("available"))
        self.assertEqual(plan.get("table"), "fact_ads_daily")
        self.assertIn("SELECT", plan.get("sql", ""))

        result = json.loads(business_tools.query_fact_layer_from_question("最近30天 SKU-001 的广告表现", limit=20))
        self.assertEqual(result["plan"]["table"], "fact_ads_daily")
        self.assertGreaterEqual(result["result"].get("row_count", 0), 1)

    def test_fact_layer_builds_operational_aggregate_views(self) -> None:
        self._write_standard_csvs()
        fact_layer_tools = self.modules["fact_layer_tools"]
        fact_layer_tools.register_all_fact_datasets()

        tables = {item.get("name") for item in json.loads(fact_layer_tools.list_fact_tables()).get("tables", [])}
        self.assertIn("agg_sku_daily_sales", tables)
        self.assertIn("agg_warehouse_inventory", tables)
        self.assertIn("agg_inbound_outbound_daily", tables)
        self.assertIn("agg_channel_sales", tables)

        sku_daily = json.loads(
            fact_layer_tools.query_fact_layer(
                "SELECT sku, date_value, sales_qty, revenue FROM marts.agg_sku_daily_sales WHERE sku = 'SKU-001' ORDER BY date_value",
                limit=10,
            )
        )
        self.assertEqual([row["sales_qty"] for row in sku_daily["rows"]], [10.0, 15.0, 20.0])

        warehouse_inventory = json.loads(
            fact_layer_tools.query_fact_layer(
                "SELECT warehouse, ending_inventory, inbound, outbound, in_transit FROM marts.agg_warehouse_inventory WHERE warehouse = 'WH-A'",
                limit=10,
            )
        )
        self.assertEqual(warehouse_inventory["rows"][0]["ending_inventory"], 8.0)
        self.assertEqual(warehouse_inventory["rows"][0]["in_transit"], 1.0)

        movement = json.loads(
            fact_layer_tools.query_fact_layer(
                "SELECT warehouse, inbound, outbound, net_movement FROM marts.agg_inbound_outbound_daily WHERE date_value = DATE '2026-05-02' AND warehouse = 'WH-B'",
                limit=10,
            )
        )
        self.assertEqual(movement["rows"][0]["inbound"], 5.0)
        self.assertEqual(movement["rows"][0]["net_movement"], 3.0)

        channel_sales = json.loads(
            fact_layer_tools.query_fact_layer(
                "SELECT channel, sales_qty, revenue FROM marts.agg_channel_sales ORDER BY sales_qty DESC",
                limit=10,
            )
        )
        self.assertEqual(channel_sales["rows"][0]["channel"], "天猫")
        self.assertEqual(channel_sales["rows"][0]["sales_qty"], 45.0)

    def test_fact_layer_missing_table_returns_recoverable_error(self) -> None:
        self._write_standard_csvs()
        fact_layer_tools = self.modules["fact_layer_tools"]
        fact_layer_tools.register_all_fact_datasets()

        with self.assertRaisesRegex(ValueError, "Only datasets.* and marts.*"):
            fact_layer_tools.query_fact_layer('SELECT * FROM "inventory_cleaned"', limit=10)

    def test_agent_fact_layer_tool_returns_recoverable_policy_error(self) -> None:
        self._write_standard_csvs()
        fact_layer_tools = self.modules["fact_layer_tools"]
        business_tools = self.modules["business_tools"]
        fact_layer_tools.register_all_fact_datasets()

        result = json.loads(
            business_tools.query_fact_layer(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'marts'",
                limit=10,
            )
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "fact_layer_policy_violation")
        self.assertIn("Only datasets.* and marts.*", result["error"])
        self.assertIn("list_fact_tables", result["recovery_hint"])

    def test_fact_layer_builds_secondary_partition_index_and_inventory_anomaly_mart(self) -> None:
        self._write_standard_csvs()
        fact_layer_tools = self.modules["fact_layer_tools"]
        fact_layer_tools.register_all_fact_datasets()

        tables = {item.get("name") for item in json.loads(fact_layer_tools.list_fact_tables()).get("tables", [])}
        self.assertIn("inventory_partition_index", tables)
        self.assertIn("inventory_anomalies", tables)

        partition_rows = json.loads(
            fact_layer_tools.query_fact_layer(
                """
                SELECT effective_month, warehouse, sku_hash_bucket, row_count
                FROM marts.inventory_partition_index
                WHERE warehouse = 'WH-A'
                ORDER BY effective_month, sku_hash_bucket
                """,
                limit=10,
            )
        )["rows"]
        self.assertTrue(partition_rows)
        self.assertTrue(all(row["effective_month"] == "2026-05-01" for row in partition_rows))
        self.assertTrue(all(row["sku_hash_bucket"] for row in partition_rows))

        anomaly_rows = json.loads(
            fact_layer_tools.query_fact_layer(
                """
                SELECT anomaly_type, sku, warehouse
                FROM marts.inventory_anomalies
                ORDER BY anomaly_type, sku
                """,
                limit=20,
            )
        )["rows"]
        anomalies = {(row["anomaly_type"], row["sku"]) for row in anomaly_rows}
        self.assertIn(("negative_inventory", "SKU-NEG"), anomalies)
        self.assertIn(("inbound_outbound_imbalance", "SKU-IMB"), anomalies)
        self.assertIn(("no_sales_30d_high_inventory", "SKU-003"), anomalies)
        self.assertIn(("stockout_risk", "SKU-001"), anomalies)

    def test_controlled_question_planner_routes_top_group_and_time_compare(self) -> None:
        self._write_standard_csvs()
        fact_layer_tools = self.modules["fact_layer_tools"]
        business_tools = self.modules["business_tools"]
        fact_layer_tools.register_all_fact_datasets()

        top_plan = json.loads(business_tools.plan_fact_query("最近30天销量 Top 1 SKU", limit=20))
        self.assertEqual(top_plan["query_kind"], "top")
        self.assertEqual(top_plan["table"], "agg_sku_daily_sales")
        top_result = json.loads(business_tools.query_fact_layer_from_question("最近30天销量 Top 1 SKU", limit=20))
        self.assertEqual(top_result["result"]["rows"][0]["sku"], "SKU-001")
        self.assertEqual(top_result["result"]["rows"][0]["sales_qty"], 45.0)

        group_plan = json.loads(business_tools.plan_fact_query("最近30天按渠道汇总销量", limit=20))
        self.assertEqual(group_plan["query_kind"], "group")
        self.assertEqual(group_plan["group_by"], ["channel"])
        group_result = json.loads(business_tools.query_fact_layer_from_question("最近30天按渠道汇总销量", limit=20))
        channels = {row["channel"]: row["sales_qty"] for row in group_result["result"]["rows"]}
        self.assertEqual(channels["天猫"], 45.0)
        self.assertEqual(channels["抖音"], 10.0)

        compare_plan = json.loads(business_tools.plan_fact_query("SKU-001 本周和上周销量对比", limit=20))
        self.assertEqual(compare_plan["query_kind"], "time_compare")
        compare_result = json.loads(business_tools.query_fact_layer_from_question("SKU-001 本周和上周销量对比", limit=20))
        row = compare_result["result"]["rows"][0]
        self.assertEqual(row["current_period_sales_qty"], 20.0)
        self.assertEqual(row["previous_period_sales_qty"], 25.0)
        self.assertAlmostEqual(row["sales_qty_delta"], -5.0)

        warehouse_plan = json.loads(business_tools.plan_fact_query("按仓库汇总库存", limit=20))
        self.assertEqual(warehouse_plan["query_kind"], "group")
        self.assertEqual(warehouse_plan["group_by"], ["warehouse"])
        warehouse_result = json.loads(business_tools.query_fact_layer_from_question("按仓库汇总库存", limit=20))
        warehouses = {row["warehouse"]: row["ending_inventory"] for row in warehouse_result["result"]["rows"]}
        self.assertEqual(warehouses["WH-A"], 8.0)
        self.assertEqual(warehouses["WH-B"], 23.0)

    def test_controlled_question_planner_routes_inventory_anomalies(self) -> None:
        self._write_standard_csvs()
        fact_layer_tools = self.modules["fact_layer_tools"]
        business_tools = self.modules["business_tools"]
        fact_layer_tools.register_all_fact_datasets()

        for question, expected_type in [
            ("有哪些负库存 SKU", "negative_inventory"),
            ("出入库不平的 SKU", "inbound_outbound_imbalance"),
            ("近30天无销量高库存 SKU", "no_sales_30d_high_inventory"),
            ("断货风险 SKU", "stockout_risk"),
        ]:
            with self.subTest(question=question):
                plan = json.loads(business_tools.plan_fact_query(question, limit=20))
                self.assertEqual(plan["table"], "inventory_anomalies")
                self.assertEqual(plan["query_kind"], "anomaly")
                self.assertIn(expected_type, plan["anomaly_types"])
                result = json.loads(business_tools.query_fact_layer_from_question(question, limit=20))
                anomaly_types = {row["anomaly_type"] for row in result["result"]["rows"]}
                self.assertIn(expected_type, anomaly_types)

    def test_xmind_raw_ingest_creates_wiki_page(self) -> None:
        xmind_path = self.raw_dir / "strategy.xmind"
        self._write_xmind_file(xmind_path)

        knowledge_tools = self.modules["knowledge_tools"]
        result = json.loads(knowledge_tools.ingest_raw_file("strategy.xmind"))
        wiki_path = self.wiki_dir / result["wiki_path"]
        content = wiki_path.read_text(encoding="utf-8")

        self.assertTrue(wiki_path.exists())
        self.assertIn("年度增长计划", content)
        self.assertIn("渠道", content)
        self.assertIn("展会", content)


if __name__ == "__main__":
    unittest.main()
