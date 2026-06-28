from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast


def _reload_connector_modules():
    import src.a2a_ecommerce_demo.connector_live_tools as connector_live_tools
    import src.a2a_ecommerce_demo.connector_registry as connector_registry
    import src.a2a_ecommerce_demo.connector_tools as connector_tools
    import src.a2a_ecommerce_demo.fact_layer_tools as fact_layer_tools

    fact_layer_tools = importlib.reload(fact_layer_tools)
    connector_registry = importlib.reload(connector_registry)
    connector_live_tools = importlib.reload(connector_live_tools)
    connector_tools = importlib.reload(connector_tools)
    return {
        "connector_registry": connector_registry,
        "connector_live_tools": connector_live_tools,
        "connector_tools": connector_tools,
        "fact_layer_tools": fact_layer_tools,
    }


class ConnectorRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in [
                "A2A_DATA_DIR",
                "A2A_WAREHOUSE_DIR",
                "A2A_WIKI_DIR",
                "A2A_DUCKDB_PATH",
                "A2A_DATASET_REGISTRY",
                "A2A_CONNECTOR_REGISTRY",
                "A2A_ENV_PATH",
                "A2A_JACKYUN_SKILL_DIR",
                "A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH",
                "A2A_TRUSTED_SKILL_DIRS",
                "A2A_KINGDEE_SKILL_DIR",
                "A2A_WECOM_SMARTSHEET_SOURCE_CONFIG",
                "JACKYUN_APP_KEY",
                "JACKYUN_APP_SECRET",
                "KINGDEE_BASE_URL",
                "KINGDEE_ACCT_ID",
                "KINGDEE_USERNAME",
                "KINGDEE_PASSWORD",
                "WECOM_SMARTSHEET_MCP_URL",
                "WECOM_SMARTSHEET_URL",
                "WECOM_SMARTSHEET_SHEET_ID",
                "WECOM_SMARTSHEET_SHEET_IDS",
            ]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.warehouse_dir = self.data_dir / "warehouse"
        self.wiki_dir = self.root / "wiki"
        self.jackyun_dir = self.root / "jackyun-skill-project"
        self.kingdee_dir = self.root / "Finance"
        self.warehouse_dir.mkdir(parents=True, exist_ok=True)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.jackyun_dir.mkdir(parents=True, exist_ok=True)
        self.kingdee_dir.mkdir(parents=True, exist_ok=True)
        for file_name in ["SKILL.md", "jackyun_api.py", "config.py", "ARCHITECTURE.md"]:
            (self.jackyun_dir / file_name).write_text("stub\n", encoding="utf-8")
        for file_name in ["SKILL.md", "auth.py", "api.py", "config.py"]:
            (self.kingdee_dir / file_name).write_text("stub\n", encoding="utf-8")
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_WAREHOUSE_DIR"] = str(self.warehouse_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_DUCKDB_PATH"] = str(self.warehouse_dir / "a2a.duckdb")
        os.environ["A2A_DATASET_REGISTRY"] = str(self.warehouse_dir / "dataset_registry.json")
        os.environ["A2A_CONNECTOR_REGISTRY"] = str(self.warehouse_dir / "connector_registry.json")
        os.environ["A2A_ENV_PATH"] = str(self.root / ".env")
        (self.root / ".env").write_text("", encoding="utf-8")
        os.environ["A2A_JACKYUN_SKILL_DIR"] = str(self.jackyun_dir)
        os.environ.pop("A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH", None)
        os.environ["A2A_KINGDEE_SKILL_DIR"] = str(self.kingdee_dir)
        os.environ["A2A_WECOM_SMARTSHEET_SOURCE_CONFIG"] = str(self.root / "wecom_smartsheet_sources.json")
        for key in [
            "JACKYUN_APP_KEY",
            "JACKYUN_APP_SECRET",
            "KINGDEE_BASE_URL",
            "KINGDEE_ACCT_ID",
            "KINGDEE_USERNAME",
            "KINGDEE_PASSWORD",
            "WECOM_SMARTSHEET_MCP_URL",
            "WECOM_SMARTSHEET_URL",
            "WECOM_SMARTSHEET_SHEET_ID",
            "WECOM_SMARTSHEET_SHEET_IDS",
        ]:
            os.environ.pop(key, None)
        self.modules = _reload_connector_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_default_registry_tracks_jackyun_and_kingdee_as_read_only_domestic_connectors(self) -> None:
        connector_registry = cast(Any, self.modules["connector_registry"])

        registry = connector_registry.ensure_connector_registry()

        self.assertEqual(registry["schema"], "a2a_connector_registry_v1")
        self.assertEqual(set(registry["connectors"]), {"jackyun_erp", "kingdee_erp", "wecom_smartsheet"})
        jackyun = registry["connectors"]["jackyun_erp"]
        self.assertTrue(jackyun["read_only_default"])
        self.assertFalse(jackyun["external_write_enabled"])
        self.assertEqual("read_only", jackyun["permission_scope"])
        self.assertFalse(jackyun["permission_policy"]["can_call_external_write_api"])
        self.assertEqual(
            ["health", "capability_preview", "live_readonly_query", "sync_readonly_snapshot"],
            jackyun["allowed_actions"],
        )
        self.assertIn("天猫", jackyun["domestic_platforms"])
        self.assertIn("抖音", jackyun["domestic_platforms"])
        self.assertNotIn("Amazon", json.dumps(jackyun, ensure_ascii=False))
        self.assertIn("batch_inventory", jackyun["datasets"])
        self.assertIn("stock_inbound", jackyun["datasets"])
        self.assertIn("stock_outbound", jackyun["datasets"])
        self.assertIn("sales_report", jackyun["datasets"])

        kingdee = registry["connectors"]["kingdee_erp"]
        self.assertTrue(kingdee["read_only_default"])
        self.assertFalse(kingdee["external_write_enabled"])
        self.assertEqual("read_only", kingdee["permission_scope"])
        self.assertFalse(kingdee["permission_policy"]["can_call_external_write_api"])
        self.assertIn("other_payables", kingdee["datasets"])
        self.assertIn("sales_returns", kingdee["datasets"])
        self.assertIn("organizations", kingdee["datasets"])
        self.assertIn("customers", kingdee["datasets"])
        self.assertIn("supplier_procurement_terms", kingdee["datasets"])

        wecom = registry["connectors"]["wecom_smartsheet"]
        self.assertTrue(wecom["read_only_default"])
        self.assertFalse(wecom["external_write_enabled"])
        self.assertEqual("read_only", wecom["permission_scope"])
        self.assertIn("smart_records", wecom["datasets"])
        self.assertIn("channel_daily_sales", wecom["datasets"])
        self.assertIn("WECOM_SMARTSHEET_MCP_URL", wecom["credential_env_names"])
        self.assertIn("WEDOC_MCP_URL", wecom["credential_env_names"])
        self.assertIn("WECOM_SMARTSHEET_DOCID", wecom["credential_env_names"])
        self.assertIn(["WEDOC_MCP_URL"], wecom["credential_alternative_sets"])
        self.assertIn(
            ["WECOM_SMARTSHEET_MCP_URL", "WECOM_SMARTSHEET_URL", "WECOM_SMARTSHEET_SHEET_IDS"],
            wecom["credential_alternative_sets"],
        )
        self.assertIn(
            ["WECOM_SMARTSHEET_MCP_URL", "WECOM_SMARTSHEET_DOCID", "WECOM_SMARTSHEET_SHEET_IDS"],
            wecom["credential_alternative_sets"],
        )
        self.assertIn("智能表新增记录", wecom["denied_write_actions"])

        p3_policy = registry["p3_ingestion_policy"]
        blocked_ids = {item["source_id"] for item in p3_policy["not_direct_api_sources"]}
        self.assertIn("domestic_marketplace_api", blocked_ids)
        self.assertIn("domestic_ads_api", blocked_ids)
        self.assertIn("customer_service_review_api", blocked_ids)
        manual_ids = {item["source_id"] for item in p3_policy["manual_export_sources"]}
        self.assertIn("domestic_marketplace_exports", manual_ids)
        self.assertIn("ads_report_exports", manual_ids)
        self.assertIn("customer_service_after_sales_exports", manual_ids)

    def test_registry_sanitizes_existing_connector_write_overrides(self) -> None:
        connector_registry = cast(Any, self.modules["connector_registry"])
        unsafe_registry = {
            "schema": "a2a_connector_registry_v1",
            "updated_at": "2026-05-19 00:00:00",
            "registry_path": str(connector_registry.CONNECTOR_REGISTRY_PATH),
            "connectors": {
                "jackyun_erp": {
                    "connector_id": "jackyun_erp",
                    "read_only_default": False,
                    "external_write_enabled": True,
                    "permission_scope": "read_write",
                    "allowed_actions": ["health", "live_readonly_query", "创建销售单"],
                },
                "kingdee_erp": {
                    "connector_id": "kingdee_erp",
                    "read_only_default": False,
                    "external_write_enabled": True,
                    "permission_scope": "read_write",
                    "allowed_actions": ["ExecuteBillQuery", "Save", "Submit"],
                },
            },
        }
        connector_registry.CONNECTOR_REGISTRY_PATH.write_text(json.dumps(unsafe_registry, ensure_ascii=False), encoding="utf-8")

        registry = connector_registry.ensure_connector_registry()

        for connector_id in ["jackyun_erp", "kingdee_erp"]:
            connector = registry["connectors"][connector_id]
            self.assertTrue(connector["read_only_default"])
            self.assertFalse(connector["external_write_enabled"])
            self.assertEqual("read_only", connector["permission_scope"])
            self.assertFalse(connector["permission_policy"]["can_call_external_write_api"])
            self.assertNotIn("创建销售单", connector["allowed_actions"])
            self.assertNotIn("Save", connector["allowed_actions"])
            self.assertNotIn("Submit", connector["allowed_actions"])

    def test_registry_rebinds_stale_jackyun_skill_dir_to_project_skill(self) -> None:
        connector_registry = cast(Any, self.modules["connector_registry"])
        project_skill_dir = self.root / "skills" / "jackyun_erp_readonly_connector_skill"
        project_skill_dir.mkdir(parents=True, exist_ok=True)
        for file_name in ["SKILL.md", "jackyun_api.py", "ARCHITECTURE.md"]:
            (project_skill_dir / file_name).write_text("stub\n", encoding="utf-8")
        connector_registry.PROJECT_ROOT = self.root
        connector_registry.PROJECT_JACKYUN_SKILL_DIR = project_skill_dir
        stale_registry = {
            "schema": "a2a_connector_registry_v1",
            "updated_at": "2026-05-19 00:00:00",
            "registry_path": str(connector_registry.CONNECTOR_REGISTRY_PATH),
            "connectors": {
                "jackyun_erp": {
                    "connector_id": "jackyun_erp",
                    "skill_dir": "/Users/seven/Desktop/jackyun-skill-project",
                    "required_files": ["SKILL.md", "jackyun_api.py", "config.py", "ARCHITECTURE.md"],
                }
            },
        }
        connector_registry.CONNECTOR_REGISTRY_PATH.write_text(
            json.dumps(stale_registry, ensure_ascii=False),
            encoding="utf-8",
        )
        os.environ.pop("A2A_JACKYUN_SKILL_DIR", None)

        registry = connector_registry.ensure_connector_registry()

        jackyun = registry["connectors"]["jackyun_erp"]
        self.assertEqual(str(project_skill_dir), jackyun["skill_dir"])
        self.assertNotIn("config.py", jackyun["required_files"])

    def test_jackyun_config_loader_uses_skill_local_example_config(self) -> None:
        connector_live_tools = self.modules["connector_live_tools"]
        skill_dir = self.root / "skill-with-example-config"
        skill_dir.mkdir(parents=True, exist_ok=True)
        os.environ["A2A_TRUSTED_SKILL_DIRS"] = str(self.root)
        (skill_dir / "config.example.py").write_text(
            "JACKYUN_APP_KEY = 'key-from-skill-example'\n"
            "JACKYUN_APP_SECRET = 'secret-from-skill-example'\n"
            "JACKYUN_API_URL = 'https://example.invalid'\n"
            "JACKYUN_CALL_STRATEGY = 'http'\n",
            encoding="utf-8",
        )
        sys.modules.pop("config", None)

        config = connector_live_tools._import_jackyun_config(skill_dir)

        self.assertEqual("key-from-skill-example", config.JACKYUN_APP_KEY)
        self.assertEqual(str(skill_dir / "config.example.py"), config.__file__)

    def test_health_and_preview_are_read_only_and_do_not_expose_secret_values(self) -> None:
        connector_tools = self.modules["connector_tools"]

        listing = json.loads(connector_tools.list_erp_connectors())
        self.assertEqual("a2a_p3_ingestion_policy_v1", listing["p3_ingestion_policy"]["schema"])
        self.assertIn("manual_export_sources", listing["p3_ingestion_policy"])
        for connector in listing["connectors"]:
            self.assertFalse(connector["external_write_enabled"])
            self.assertEqual("read_only", connector["permission_scope"])
            self.assertFalse(connector["permission_policy"]["can_call_external_write_api"])

        health = json.loads(connector_tools.get_erp_connector_health())
        jackyun_health = next(item for item in health["connectors"] if item["connector_id"] == "jackyun_erp")
        kingdee_health = next(item for item in health["connectors"] if item["connector_id"] == "kingdee_erp")
        self.assertEqual(jackyun_health["status"], "needs_config")
        self.assertTrue(jackyun_health["skill_dir_exists"])
        self.assertFalse(jackyun_health["credential_config"]["JACKYUN_APP_SECRET"])
        self.assertNotIn("KINGDEE_ACCT_ID", kingdee_health["credential_config"])
        self.assertNotIn("secret=", json.dumps(health, ensure_ascii=False).lower())

        preview = json.loads(connector_tools.preview_erp_connector_sync("jackyun_erp", "inventory_stock"))
        self.assertEqual(preview["status"], "preview")
        self.assertTrue(preview["read_only"])
        self.assertFalse(preview["external_write_enabled"])
        self.assertEqual("read_only", preview["permission_scope"])
        self.assertTrue(preview["can_register_fact_layer"])
        self.assertIn("SKU", preview["schema"]["columns"])
        self.assertIn("创建销售单", preview["denied_write_actions"])

    def test_jackyun_connector_aliases_work_for_health_and_preview(self) -> None:
        connector_registry = self.modules["connector_registry"]
        connector_tools = self.modules["connector_tools"]

        self.assertEqual(connector_registry.normalize_connector_id("jikeyun"), "jackyun_erp")
        self.assertEqual(connector_registry.normalize_connector_id("吉客云"), "jackyun_erp")
        self.assertEqual(connector_registry.get_connector_spec("jikeyun")["connector_id"], "jackyun_erp")

        health = json.loads(connector_tools.get_erp_connector_health("jikeyun"))
        self.assertEqual(health["connector_count"], 1)
        self.assertEqual(health["connectors"][0]["connector_id"], "jackyun_erp")

        preview = json.loads(connector_tools.preview_erp_connector_sync("吉客云", "inventory_stock"))
        self.assertEqual(preview["connector_id"], "jackyun_erp")
        self.assertIn("jackyun_erp", preview["target_snapshot_path"])

    def test_connector_snapshot_path_sanitizes_dataset_name(self) -> None:
        connector_registry = self.modules["connector_registry"]

        snapshot_path = connector_registry.connector_snapshot_path(
            "jackyun_erp",
            "../../outside",
            timestamp="20260622-120000",
        )

        root = connector_registry.CONNECTOR_STAGING_DIR.resolve(strict=False)
        relative = os.path.relpath(snapshot_path, root)
        self.assertFalse(relative == ".." or relative.startswith(f"..{os.sep}"))
        self.assertNotIn("..", snapshot_path.name)

    def test_connector_snapshot_can_register_into_fact_layer(self) -> None:
        fact_layer_tools = self.modules["fact_layer_tools"]
        if not fact_layer_tools.duckdb_installed():
            self.skipTest("duckdb is not installed")
        connector_tools = self.modules["connector_tools"]

        rows = [
            {
                "日期": "2026-05-19",
                "SKU": "SKU-ERP",
                "商品名称": "UNOVE test item",
                "仓库": "华东仓",
                "销售渠道": "天猫",
                "期初总量": 10,
                "入库总量": 5,
                "出库总量": -3,
                "期末总量": 12,
                "在途": 2,
            }
        ]
        result = json.loads(
            connector_tools.sync_connector_dataset(
                "jackyun_erp",
                "inventory_stock",
                rows_json=json.dumps(rows, ensure_ascii=False),
                dry_run=False,
            )
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["dataset"]["source_kind"], "connector_snapshot")
        self.assertTrue(Path(result["snapshot_path"]).exists())
        inventory = json.loads(
            fact_layer_tools.query_fact_layer(
                "SELECT sku, warehouse, ending_inventory FROM marts.current_inventory_snapshot WHERE sku = 'SKU-ERP'",
                limit=5,
            )
        )
        self.assertEqual(inventory["rows"][0]["warehouse"], "华东仓")
        self.assertEqual(inventory["rows"][0]["ending_inventory"], 12.0)

    def test_live_query_capabilities_are_read_only_and_hide_secrets(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        capabilities = json.loads(connector_live_tools.list_erp_live_query_capabilities())

        self.assertEqual(capabilities["mode"], "live_read_only_fallback")
        self.assertTrue(capabilities["read_only"])
        self.assertFalse(capabilities["external_write_enabled"])
        self.assertEqual("read_only", capabilities["permission_scope"])
        for connector in capabilities["connectors"]:
            self.assertFalse(connector["external_write_enabled"])
            self.assertEqual("read_only", connector["permission_scope"])
            for dataset in connector["datasets"]:
                self.assertTrue(dataset["read_only"])
                self.assertFalse(dataset["write_enabled"])
        method_text = json.dumps(capabilities, ensure_ascii=False).lower()
        self.assertIn("erp.stockquantity.get", method_text)
        self.assertIn("erp.batchstockquantity.get", method_text)
        self.assertIn("oms.trade.fullinfoget", method_text)
        self.assertIn("erp.stockin.get.v2", method_text)
        self.assertIn("erp.stockout.get.v2", method_text)
        self.assertIn("executebillquery", method_text)
        self.assertIn("supplier_procurement_terms", method_text)
        self.assertNotIn("save", method_text)
        self.assertNotIn("submit", method_text)
        self.assertNotIn("push", method_text)
        self.assertNotIn("secret", method_text)

    def test_route_erp_live_query_recommends_inventory_cost_and_wecom_daily_sales(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        route = json.loads(
            connector_live_tools.route_erp_live_query(
                "使用吉客云份仓库查询功能筛选品牌是Unove柔诺伊，"
                "选择所有仓库的库存信息先分析库存，再结合企业微信智能表日销表，"
                "补充采购价/成本价，输出 PM 运营方案。"
            )
        )

        self.assertEqual(route["status"], "success")
        self.assertEqual(route["primary_tool"], "query_inventory_cost_reference")
        self.assertTrue(route["intent"]["inventory"])
        self.assertTrue(route["intent"]["cost_or_purchase_price"])
        self.assertTrue(route["intent"]["wecom_daily_sales"])
        self.assertIn("query_inventory_cost_reference", route["recommended_tools"])
        self.assertIn("query_wecom_smartsheet_records", route["recommended_tools"])
        self.assertIn("jackyun_erp", route["data_sources"])
        self.assertIn("kingdee_erp", route["data_sources"])
        self.assertIn("WeCom_smartsheet", route["data_sources"])
        self.assertEqual(route["suggested_filters"]["brand"], "Unove柔诺伊")

    def test_route_erp_live_query_passes_runtime_wecom_url_instead_of_fixed_source(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        doc_url = "https://doc.weixin.qq.com/smartsheet/s3_doc?scode=secret-code&tab=sheetB&viewId=view1"

        route = json.loads(
            connector_live_tools.route_erp_live_query(
                f"结合企业微信智能表日销表 {doc_url} 和吉客云库存做分析",
                filters_json=json.dumps({"brand": "Unove柔诺伊"}, ensure_ascii=False),
            )
        )

        daily_sales_step = next(item for item in route["plan"] if item["step"] == "daily_sales")
        self.assertEqual(daily_sales_step["tool"], "query_wecom_smartsheet_records")
        self.assertEqual(daily_sales_step["doc_url"], doc_url)
        self.assertEqual(daily_sales_step["dataset"], "channel_daily_sales")
        self.assertNotIn("source_id", daily_sales_step)

    def test_route_erp_live_query_recommends_jackyun_sales_summary_for_realtime_sku_sales(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        route = json.loads(
            connector_live_tools.route_erp_live_query(
                "用吉客云实时查 UNOVE SKU 日销和各渠道销量金额",
                filters_json=json.dumps(
                    {"start_time": "2026-05-01", "end_time": "2026-05-22"},
                    ensure_ascii=False,
                ),
            )
        )

        self.assertEqual(route["status"], "success")
        self.assertEqual(route["primary_tool"], "query_jackyun_channel_sales_summary")
        self.assertTrue(route["intent"]["sales_or_turnover"])
        self.assertTrue(route["intent"]["live_erp"])
        self.assertIn("query_jackyun_channel_sales_summary", route["recommended_tools"])
        self.assertIn("jackyun_erp", route["data_sources"])
        sales_step = next(item for item in route["plan"] if item["step"] == "jackyun_channel_sales_summary")
        self.assertEqual(sales_step["tool"], "query_jackyun_channel_sales_summary")
        self.assertEqual(sales_step["dimension"], "channel_goods_daily")
        self.assertIn("start_time", route["suggested_filters"])

    def test_jackyun_channel_sales_summary_wraps_skill_workflow_as_read_only_query(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, dict[str, object]]] = []

        def fake_summary(skill_dir: str, query_kwargs: dict[str, object]) -> dict[str, object]:
            calls.append((skill_dir, query_kwargs))
            return {
                "method": "birc.report.needauth.goodsMultiDimensionalAnalysis",
                "primary_method": "birc.report.needauth.goodsMultiDimensionalAnalysis",
                "source_method": "primary_report",
                "dimension": "channel_goods_daily",
                "row_count": 1,
                "summary_rows": [
                    {
                        "time": "2026-05-21",
                        "shopName": "抖音UNOVE",
                        "goodsNo": "8809669502427",
                        "goodsName": "UNOVE柔诺伊发膜",
                        "goodsQty": 12,
                        "goodsAmtCompanyCurrency": 1800,
                        "sellAmtCompanyCurrency": 1900,
                        "deliveryGoodsQty": 12,
                        "raw": {"goodsNo": "8809669502427"},
                    }
                ],
                "total_goods_qty": 12.0,
                "total_goods_amount": 1800.0,
                "warnings": ["AppKey TEST_APP_KEY_DO_NOT_USE 缺少报表权限"],
                "request": {
                    "startTime": "2026-05-21",
                    "endTime": "2026-05-21",
                    "summaryType": "time,channel,goods",
                },
                "resolved_shops": [{"shopName": "抖音UNOVE", "shopId": "1"}],
            }

        had_original = hasattr(connector_live_tools, "_call_jackyun_channel_sales_summary")
        original = getattr(connector_live_tools, "_call_jackyun_channel_sales_summary", None)
        connector_live_tools._call_jackyun_channel_sales_summary = fake_summary
        try:
            result = json.loads(
                connector_live_tools.query_jackyun_channel_sales_summary(
                    filters_json=json.dumps(
                        {
                            "start_time": "2026-05-21",
                            "end_time": "2026-05-21",
                            "channel_include_keyword": "UNOVE",
                        },
                        ensure_ascii=False,
                    ),
                    dimension="channel_goods_daily",
                    limit=50,
                    requested_by="tester",
                )
            )
        finally:
            if had_original:
                connector_live_tools._call_jackyun_channel_sales_summary = original
            else:
                delattr(connector_live_tools, "_call_jackyun_channel_sales_summary")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["mode"], "live_read_only_sales_summary")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["external_write_enabled"])
        self.assertEqual(result["permission_scope"], "read_only")
        self.assertEqual(result["connector_id"], "jackyun_erp")
        self.assertEqual(result["dataset"], "channel_sales_summary")
        self.assertEqual(result["dimension"], "channel_goods_daily")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["returned_row_count"], 1)
        self.assertEqual(result["totals"]["goods_qty"], 12.0)
        self.assertEqual(result["totals"]["goods_amount"], 1800.0)
        self.assertEqual(result["rows"][0]["goodsNo"], "8809669502427")
        self.assertIn("***REDACTED***", result["warnings"][0])
        self.assertNotIn("TEST_APP_KEY_DO_NOT_USE", json.dumps(result, ensure_ascii=False))
        self.assertIn("日期", result["grain"])
        self.assertIn("SKU", result["grain"])
        self.assertEqual(calls[0][0], str(self.jackyun_dir))
        self.assertEqual(calls[0][1]["dimension"], "channel_goods_daily")
        self.assertEqual(calls[0][1]["start_time"], "2026-05-21")
        self.assertEqual(calls[0][1]["end_time"], "2026-05-21")
        self.assertEqual(calls[0][1]["page_size"], 50)
        self.assertTrue(calls[0][1]["use_udr_fallback"])

    def test_inventory_cost_reference_falls_back_to_kingdee_when_jackyun_cost_is_empty(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, str, dict[str, object]]] = []

        def fake_snapshot(
            connector_id: str,
            dataset: str,
            filters_json: str = "",
            limit: int = 20,
            requested_by: str = "agent",
        ) -> str:
            filters = json.loads(filters_json) if filters_json else {}
            calls.append((connector_id, dataset, filters))
            rows_by_dataset = {
                ("jackyun_erp", "inventory_stock"): [
                    {
                        "goodsNo": "SKU-001",
                        "goodsName": "UNOVE柔诺伊发膜",
                        "warehouseName": "麦歌仓",
                        "currentQuantity": 100,
                        "costPrice": "",
                    }
                ],
                ("jackyun_erp", "batch_inventory"): [
                    {
                        "goodsNo": "SKU-001",
                        "batchNo": "B001",
                        "currentQuantity": 100,
                        "monthEndCost": "",
                    }
                ],
                ("jackyun_erp", "purchase_orders"): [
                    {
                        "purchNo": "PO-JK-001",
                        "goodsNo": "SKU-001",
                        "price": "",
                    }
                ],
                ("kingdee_erp", "supplier_procurement_terms"): [
                    {
                        "FBillNo": "PO-KD-001",
                        "FMaterialId.FNumber": "SKU-001",
                        "FMaterialId.FName": "UNOVE柔诺伊发膜",
                        "FTaxPrice": 12.5,
                        "FAllAmount": 1250,
                        "FDeliveryDate": "2026-05-15",
                    }
                ],
            }
            rows = rows_by_dataset.get((connector_id, dataset), [])
            return json.dumps(
                {
                    "status": "success",
                    "connector_id": connector_id,
                    "dataset": dataset,
                    "read_only": True,
                    "row_count": len(rows),
                    "rows": rows,
                },
                ensure_ascii=False,
            )

        original = connector_live_tools.query_erp_live_snapshot
        connector_live_tools.query_erp_live_snapshot = fake_snapshot
        try:
            result = json.loads(
                connector_live_tools.query_inventory_cost_reference(
                    filters_json=json.dumps({"brand": "Unove柔诺伊", "goods_name": "UNOVE"}, ensure_ascii=False),
                    limit=10,
                )
            )
        finally:
            connector_live_tools.query_erp_live_snapshot = original

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["read_only"])
        self.assertEqual(result["inventory"]["row_count"], 1)
        self.assertEqual(result["cost_reference"]["selected_source"], "kingdee_erp/supplier_procurement_terms")
        self.assertEqual(result["cost_reference"]["selected_field"], "FTaxPrice")
        self.assertEqual(result["cost_reference"]["selected_value"], 12.5)
        self.assertIn("采购订单含税单价参考", result["cost_reference"]["semantic_boundary"])
        self.assertIn("derived_reference_filters", result["cost_reference"]["scope_note"])
        self.assertIn("不能代表整个品牌", result["cost_reference"]["scope_note"])
        self.assertIn(("jackyun_erp", "inventory_stock"), [(item[0], item[1]) for item in calls])
        self.assertIn(("jackyun_erp", "batch_inventory"), [(item[0], item[1]) for item in calls])
        self.assertIn(("jackyun_erp", "purchase_orders"), [(item[0], item[1]) for item in calls])
        self.assertIn(("kingdee_erp", "supplier_procurement_terms"), [(item[0], item[1]) for item in calls])
        kingdee_call = next(call for call in calls if call[0] == "kingdee_erp")
        self.assertEqual(kingdee_call[2]["goods_no"], "SKU-001")

    def test_inventory_cost_reference_continues_to_kingdee_when_jackyun_cost_is_partial(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, str, dict[str, object]]] = []

        def fake_snapshot(
            connector_id: str,
            dataset: str,
            filters_json: str = "",
            limit: int = 20,
            requested_by: str = "agent",
        ) -> str:
            filters = json.loads(filters_json) if filters_json else {}
            calls.append((connector_id, dataset, filters))
            rows_by_dataset = {
                ("jackyun_erp", "inventory_stock"): [
                    {
                        "goodsNo": "SKU-001",
                        "goodsName": "UNOVE柔诺伊发膜",
                        "warehouseName": "麦歌仓",
                        "currentQuantity": 100,
                        "costPrice": 10,
                    },
                    {
                        "goodsNo": "SKU-002",
                        "goodsName": "UNOVE柔诺伊洗发水",
                        "warehouseName": "麦歌仓",
                        "currentQuantity": 80,
                        "costPrice": "",
                    },
                ],
                ("jackyun_erp", "batch_inventory"): [],
                ("jackyun_erp", "purchase_orders"): [],
                ("kingdee_erp", "supplier_procurement_terms"): [
                    {
                        "FBillNo": "PO-KD-002",
                        "FMaterialId.FNumber": "SKU-002",
                        "FMaterialId.FName": "UNOVE柔诺伊洗发水",
                        "FTaxPrice": 13.5,
                    }
                ],
            }
            rows = rows_by_dataset.get((connector_id, dataset), [])
            return json.dumps(
                {
                    "status": "success",
                    "connector_id": connector_id,
                    "dataset": dataset,
                    "read_only": True,
                    "row_count": len(rows),
                    "rows": rows,
                },
                ensure_ascii=False,
            )

        original = connector_live_tools.query_erp_live_snapshot
        connector_live_tools.query_erp_live_snapshot = fake_snapshot
        try:
            result = json.loads(
                connector_live_tools.query_inventory_cost_reference(
                    filters_json=json.dumps({"brand": "Unove柔诺伊"}, ensure_ascii=False),
                    limit=10,
                )
            )
        finally:
            connector_live_tools.query_erp_live_snapshot = original

        self.assertEqual(result["inventory_cost_coverage"]["priced_row_count"], 1)
        self.assertEqual(result["inventory_cost_coverage"]["missing_row_count"], 1)
        self.assertFalse(result["inventory_cost_coverage"]["complete_for_returned_rows"])
        self.assertIn(("kingdee_erp", "supplier_procurement_terms"), [(item[0], item[1]) for item in calls])
        self.assertEqual(result["cost_reference"]["selected_source"], "kingdee_erp/supplier_procurement_terms")
        self.assertEqual(result["cost_reference"]["selected_field"], "FTaxPrice")
        self.assertEqual(result["cost_reference"]["selected_value"], 13.5)
        self.assertIn(
            "jackyun_erp/inventory_stock",
            {item["selected_source"] for item in result["price_references"]},
        )
        self.assertIn(
            "kingdee_erp/supplier_procurement_terms",
            {item["selected_source"] for item in result["price_references"]},
        )

    def test_inventory_cost_reference_exposes_brand_expansion_summary_when_rows_are_capped(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        def fake_snapshot(
            connector_id: str,
            dataset: str,
            filters_json: str = "",
            limit: int = 20,
            requested_by: str = "agent",
        ) -> str:
            rows_by_dataset = {
                ("jackyun_erp", "inventory_stock"): [
                    {
                        "goodsNo": "SKU-001",
                        "goodsName": "UNOVE柔诺伊发膜",
                        "warehouseName": "麦歌仓",
                        "currentQuantity": 10,
                        "useQuantity": 8,
                        "costPrice": "",
                    }
                ],
                ("jackyun_erp", "batch_inventory"): [],
                ("jackyun_erp", "purchase_orders"): [],
                ("kingdee_erp", "supplier_procurement_terms"): [],
            }
            rows = rows_by_dataset.get((connector_id, dataset), [])
            payload: dict[str, object] = {
                "status": "success",
                "connector_id": connector_id,
                "dataset": dataset,
                "read_only": True,
                "row_count": 3791 if dataset == "inventory_stock" else len(rows),
                "rows": rows,
            }
            if dataset == "inventory_stock":
                payload["brand_expansion"] = {
                    "enabled": True,
                    "matched_goods_count": 42,
                    "queried_goods_count": 42,
                    "inventory_row_count": 3791,
                    "incomplete": False,
                    "warnings": [],
                    "summary": {
                        "totals": {
                            "row_count": 3791,
                            "current_quantity": 123456,
                            "available_quantity": 120000,
                        },
                        "by_business_scope": [
                            {
                                "business_scope": "大贸",
                                "current_quantity": 100000,
                                "available_quantity": 98000,
                            }
                        ],
                        "top_goods": [
                            {
                                "goodsNo": "SKU-001",
                                "goodsName": "UNOVE柔诺伊发膜",
                                "current_quantity": 50000,
                                "available_quantity": 48000,
                            }
                        ],
                    },
                }
            return json.dumps(payload, ensure_ascii=False)

        original = connector_live_tools.query_erp_live_snapshot
        connector_live_tools.query_erp_live_snapshot = fake_snapshot
        try:
            result = json.loads(
                connector_live_tools.query_inventory_cost_reference(
                    filters_json=json.dumps({"brand": "Unove柔诺伊"}, ensure_ascii=False),
                    limit=10,
                )
            )
        finally:
            connector_live_tools.query_erp_live_snapshot = original

        self.assertEqual(result["inventory"]["row_count"], 3791)
        self.assertEqual(result["inventory"]["returned_row_count"], 1)
        self.assertEqual(result["inventory"]["brand_expansion"]["summary"]["totals"]["row_count"], 3791)
        self.assertEqual(result["inventory"]["brand_expansion"]["summary"]["top_goods"][0]["goodsNo"], "SKU-001")
        self.assertIn("全量品牌展开汇总", result["inventory"]["analysis_notes"][0])

    def test_jackyun_openapi_guard_blocks_non_whitelisted_write_methods_before_skill_call(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        with self.assertRaises(PermissionError):
            connector_live_tools._call_jackyun_openapi("erp.purch.add", {}, str(self.jackyun_dir))

    def test_live_snapshot_errors_redact_erp_credentials(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            raise RuntimeError("appKey=TEST_APP_KEY_DO_NOT_USE,appSecret=super-secret,password=plain-token,未查询到应用或应用未订阅此API")

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    limit=1,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        self.assertEqual(result["status"], "error")
        text = json.dumps(result, ensure_ascii=False)
        self.assertIn("未查询到应用或应用未订阅此API", text)
        self.assertNotIn("TEST_APP_KEY_DO_NOT_USE", text)
        self.assertNotIn("super-secret", text)
        self.assertNotIn("plain-token", text)

    def test_jackyun_live_snapshot_uses_only_whitelisted_read_api(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            calls.append((method, bizcontent, skill_dir))
            return {
                "code": "200",
                "msg": "查询成功",
                "result": {
                    "data": {
                        "goodsStockQuantity": [
                            {
                                "warehouseCode": "WH001",
                                "goodsNo": "SKU-001",
                                "currentQuantity": 12,
                            }
                        ]
                    }
                },
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    filters_json=json.dumps({"goods_no": "SKU-001", "warehouse_code": "WH001"}),
                    limit=200,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["read_only"])
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(calls[0][0], "erp.stockquantity.get")
        self.assertEqual(calls[0][1]["goodsNo"], "SKU-001")
        self.assertEqual(calls[0][1]["warehouseCode"], "WH001")
        self.assertEqual(calls[0][1]["pageSize"], 100)

    def test_jackyun_live_snapshot_accepts_common_connector_alias(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            return {
                "code": "200",
                "msg": "查询成功",
                "result": {
                    "data": {
                        "goodsStockQuantity": [
                            {
                                "warehouseCode": "WH001",
                                "goodsNo": "SKU-001",
                                "currentQuantity": 12,
                            }
                        ]
                    }
                },
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jikeyun",
                    "inventory_stock",
                    filters_json=json.dumps({"goods_no": "SKU-001"}),
                    limit=1,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["connector_id"], "jackyun_erp")
        self.assertEqual(result["requested_connector_id"], "jikeyun")
        self.assertEqual(result["row_count"], 1)

    def test_jackyun_live_snapshot_empty_nested_collection_has_zero_rows(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            return {
                "code": "200",
                "msg": "查询成功",
                "result": {"data": {"goodsStockQuantity": []}},
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    filters_json=json.dumps({"goods_name": "UNOVE"}),
                    limit=5,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["row_count"], 0)
        self.assertEqual(result["rows"], [])

    def test_jackyun_inventory_goods_name_brand_falls_back_to_goods_master_lookup(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            calls.append((method, bizcontent, skill_dir))
            if method == "erp.storage.goodslist":
                return {
                    "code": "200",
                    "result": {
                        "data": {
                            "goods": [
                                {
                                    "goodsNo": "880A",
                                    "goodsName": "UNOVE柔诺伊发膜 320ml",
                                    "skuBarcode": "880A",
                                },
                                {
                                    "goodsNo": "880B",
                                    "goodsName": "柔诺伊小样 10ml",
                                    "skuBarcode": "880B",
                                },
                            ]
                        }
                    },
                }
            if method == "erp.stockquantity.get" and bizcontent.get("goodsNos") == "880A,880B":
                return {
                    "code": "200",
                    "result": {
                        "data": {
                            "goodsStockQuantity": [
                                {
                                    "goodsNo": "880A",
                                    "goodsName": "UNOVE柔诺伊发膜 320ml",
                                    "warehouseName": "面护部天猫UNOVE旗舰店-麦歌",
                                    "currentQuantity": 93,
                                    "useQuantity": 90,
                                },
                                {
                                    "goodsNo": "880B",
                                    "goodsName": "柔诺伊小样 10ml",
                                    "warehouseName": "韩国申通仓",
                                    "currentQuantity": 40,
                                    "useQuantity": 35,
                                }
                            ]
                        }
                    },
                }
            return {
                "code": "200",
                "msg": "查询成功",
                "result": {"data": {"goodsStockQuantity": []}},
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    filters_json=json.dumps({"goods_name": "UNOVE"}),
                    limit=10,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["row_count"], 2)
        self.assertTrue(result["brand_expansion"]["enabled"])
        self.assertIn("UNOVE", result["brand_expansion"]["search_terms"])
        self.assertIn("柔诺伊", result["brand_expansion"]["search_terms"])
        self.assertEqual(result["brand_expansion"]["matched_goods_count"], 2)
        self.assertEqual(result["brand_expansion"]["queried_goods_count"], 2)
        by_scope = {
            item["business_scope"]: item
            for item in result["brand_expansion"]["summary"]["by_business_scope"]
        }
        self.assertEqual(by_scope["大贸"]["current_quantity"], 93)
        self.assertEqual(by_scope["大贸"]["available_quantity"], 90)
        self.assertEqual(by_scope["跨境"]["current_quantity"], 40)
        self.assertEqual(by_scope["跨境"]["available_quantity"], 35)
        self.assertEqual(result["rows"][0]["warehouseBusinessScope"], "大贸")
        self.assertEqual(result["rows"][1]["warehouseBusinessScope"], "跨境")
        self.assertEqual(calls[0][0], "erp.stockquantity.get")
        self.assertEqual(calls[0][1]["goodsName"], "UNOVE")
        self.assertIn("erp.storage.goodslist", [call[0] for call in calls])
        inventory_goods_nos_calls = [
            call for call in calls if call[0] == "erp.stockquantity.get" and "goodsNos" in call[1]
        ]
        self.assertEqual(len(inventory_goods_nos_calls), 1)
        self.assertEqual(inventory_goods_nos_calls[0][1]["goodsNos"], "880A,880B")

    def test_jackyun_brand_inventory_expansion_summarizes_recent_sales_fields(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            if method == "erp.storage.goodslist":
                return {
                    "code": "200",
                    "result": {
                        "data": {
                            "goods": [
                                {
                                    "goodsNo": "880A",
                                    "goodsName": "UNOVE柔诺伊发膜 320ml",
                                    "skuBarcode": "880A",
                                },
                                {
                                    "goodsNo": "880B",
                                    "goodsName": "柔诺伊小样 10ml",
                                    "skuBarcode": "880B",
                                },
                            ]
                        }
                    },
                }
            if method == "erp.stockquantity.get" and bizcontent.get("goodsNos") == "880A,880B":
                return {
                    "code": "200",
                    "result": {
                        "data": {
                            "goodsStockQuantity": [
                                {
                                    "goodsNo": "880A",
                                    "goodsName": "UNOVE柔诺伊发膜 320ml",
                                    "warehouseName": "面护部天猫UNOVE旗舰店-麦歌",
                                    "currentQuantity": 93,
                                    "useQuantity": 90,
                                    "yesterdayQuantity": 4,
                                    "threedayQuantity": 10,
                                    "weekQuantity": 28,
                                    "stockOutuantity": 3,
                                },
                                {
                                    "goodsNo": "880B",
                                    "goodsName": "柔诺伊小样 10ml",
                                    "warehouseName": "韩国申通仓",
                                    "currentQuantity": 40,
                                    "useQuantity": 35,
                                    "yesterdayQuantity": 2,
                                    "threedayQuantity": 6,
                                    "weekQuantity": 14,
                                    "stockOutuantity": 1,
                                },
                            ]
                        }
                    },
                }
            return {
                "code": "200",
                "msg": "查询成功",
                "result": {"data": {"goodsStockQuantity": []}},
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    filters_json=json.dumps({"goods_name": "UNOVE"}),
                    limit=10,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        summary = result["brand_expansion"]["summary"]
        self.assertEqual(summary["totals"]["yesterday_quantity"], 6)
        self.assertEqual(summary["totals"]["three_day_quantity"], 16)
        self.assertEqual(summary["totals"]["week_quantity"], 42)
        self.assertEqual(summary["totals"]["stock_out_quantity"], 4)
        by_scope = {
            item["business_scope"]: item
            for item in summary["by_business_scope"]
        }
        self.assertEqual(by_scope["大贸"]["week_quantity"], 28)
        self.assertEqual(by_scope["跨境"]["three_day_quantity"], 6)
        self.assertEqual(summary["top_goods"][0]["goodsNo"], "880A")
        self.assertEqual(summary["top_goods"][0]["week_quantity"], 28)

    def test_jackyun_brand_inventory_expansion_excludes_material_goods_from_returned_rows(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            calls.append((method, bizcontent, skill_dir))
            if method == "erp.storage.goodslist":
                return {
                    "code": "200",
                    "result": {
                        "data": {
                            "goods": [
                                {
                                    "goodsNo": "880A",
                                    "goodsName": "UNOVE柔诺伊发膜 320ml",
                                    "skuBarcode": "880A",
                                },
                                {
                                    "goodsNo": "880M",
                                    "goodsName": "UNOVE柔诺伊深层修护安瓶洗发水 500g-塑料薄膜",
                                    "skuBarcode": "880M",
                                },
                            ]
                        }
                    },
                }
            if method == "erp.stockquantity.get" and bizcontent.get("goodsNos") == "880A":
                return {
                    "code": "200",
                    "result": {
                        "data": {
                            "goodsStockQuantity": [
                                {
                                    "goodsNo": "880A",
                                    "goodsName": "UNOVE柔诺伊发膜 320ml",
                                    "warehouseName": "面护部天猫UNOVE旗舰店-麦歌",
                                    "currentQuantity": 93,
                                    "useQuantity": 90,
                                }
                            ]
                        }
                    },
                }
            if method == "erp.stockquantity.get" and bizcontent.get("goodsNos") == "880A,880M":
                return {
                    "code": "200",
                    "result": {
                        "data": {
                            "goodsStockQuantity": [
                                {
                                    "goodsNo": "880A",
                                    "goodsName": "UNOVE柔诺伊发膜 320ml",
                                    "warehouseName": "面护部天猫UNOVE旗舰店-麦歌",
                                    "currentQuantity": 93,
                                    "useQuantity": 90,
                                },
                                {
                                    "goodsNo": "880M",
                                    "goodsName": "UNOVE柔诺伊深层修护安瓶洗发水 500g-塑料薄膜",
                                    "warehouseName": "STILL-宝鼎售后仓",
                                    "currentQuantity": 7,
                                    "useQuantity": 7,
                                },
                            ]
                        }
                    },
                }
            return {
                "code": "200",
                "msg": "查询成功",
                "result": {"data": {"goodsStockQuantity": []}},
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    filters_json=json.dumps({"goods_name": "UNOVE"}),
                    limit=10,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["brand_expansion"]["matched_goods_count"], 1)
        self.assertEqual(result["brand_expansion"]["excluded_goods_counts"]["material_goods"], 1)
        self.assertNotIn("塑料薄膜", json.dumps(result["rows"], ensure_ascii=False))
        inventory_goods_nos_calls = [
            call for call in calls if call[0] == "erp.stockquantity.get" and "goodsNos" in call[1]
        ]
        self.assertEqual(inventory_goods_nos_calls[0][1]["goodsNos"], "880A")

    def test_jackyun_live_snapshot_passes_read_only_page_index_filter(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            calls.append((method, bizcontent, skill_dir))
            return {
                "code": "200",
                "result": {
                    "data": {
                        "goodsStockQuantity": [
                            {"goodsNo": "SKU-002", "warehouseName": "麦歌仓", "currentQuantity": 12}
                        ]
                    }
                },
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    filters_json=json.dumps({"goods_no": "SKU-002", "page_index": 3}),
                    limit=5,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(calls[0][1]["pageIndex"], 3)
        self.assertEqual(calls[0][1]["pageSize"], 5)
        self.assertNotIn("page_index", calls[0][1])
        self.assertEqual(result["query"]["page_index"], 3)

    def test_jackyun_inventory_rows_include_business_warehouse_scope(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            return {
                "code": "200",
                "result": {
                    "data": {
                        "goodsStockQuantity": [
                            {"goodsNo": "SKU-DM", "warehouseName": "面护部天猫UNOVE旗舰店-麦歌"},
                            {"goodsNo": "SKU-KJ", "warehouseName": "韩国申通仓"},
                            {"goodsNo": "SKU-BS", "warehouseName": "天猫国际菜鸟仓"},
                            {"goodsNo": "SKU-SH", "warehouseName": "STILL-宝鼎售后仓"},
                        ]
                    }
                },
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    limit=10,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        scopes = {row["goodsNo"]: row["warehouseBusinessScope"] for row in result["rows"]}
        canonical = {row["goodsNo"]: row["warehouseCanonicalName"] for row in result["rows"]}
        self.assertEqual(scopes["SKU-DM"], "大贸")
        self.assertEqual(scopes["SKU-KJ"], "跨境")
        self.assertEqual(scopes["SKU-BS"], "保税")
        self.assertEqual(scopes["SKU-SH"], "售后")
        self.assertEqual(canonical["SKU-DM"], "麦歌仓")
        self.assertEqual(canonical["SKU-SH"], "宝鼎仓（售后仓）")
        self.assertTrue(result["warehouse_scope_rules"])

    def test_jackyun_warehouse_scope_rules_can_be_overridden_by_config_file(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        rules_path = self.root / "custom-warehouse-scope.json"
        rules_path.write_text(
            json.dumps(
                {
                    "schema": "a2a_jackyun_warehouse_scope_rules_v1",
                    "rules": [
                        {
                            "business_scope": "大贸",
                            "canonical_warehouse": "华东大贸仓",
                            "keywords": ["华东大贸"],
                        },
                        {
                            "business_scope": "跨境",
                            "canonical_warehouse": "仁川新仓",
                            "keywords": ["仁川"],
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.environ["A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH"] = str(rules_path)

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            return {
                "code": "200",
                "result": {
                    "data": {
                        "goodsStockQuantity": [
                            {"goodsNo": "SKU-DM", "warehouseName": "UNOVE-华东大贸-正品仓"},
                            {"goodsNo": "SKU-KJ", "warehouseName": "UNOVE-仁川-跨境仓"},
                        ]
                    }
                },
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "inventory_stock",
                    limit=10,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        scopes = {row["goodsNo"]: row["warehouseBusinessScope"] for row in result["rows"]}
        canonical = {row["goodsNo"]: row["warehouseCanonicalName"] for row in result["rows"]}
        self.assertEqual(scopes["SKU-DM"], "大贸")
        self.assertEqual(canonical["SKU-DM"], "华东大贸仓")
        self.assertEqual(scopes["SKU-KJ"], "跨境")
        self.assertEqual(canonical["SKU-KJ"], "仁川新仓")
        self.assertEqual(result["warehouse_scope_rules"][0]["canonical_warehouse"], "华东大贸仓")

    def test_jackyun_sales_orders_live_snapshot_uses_read_only_trade_query(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_call(method: str, bizcontent: dict[str, object], skill_dir: str) -> dict[str, object]:
            calls.append((method, bizcontent, skill_dir))
            return {
                "code": "200",
                "result": {
                    "data": {
                        "trades": [
                            {
                                "tradeNo": "SO001",
                                "shopName": "天猫旗舰店",
                                "payment": 199,
                            }
                        ]
                    }
                },
            }

        original = connector_live_tools._call_jackyun_openapi
        connector_live_tools._call_jackyun_openapi = fake_call
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "jackyun_erp",
                    "sales_orders",
                    filters_json=json.dumps({"date_from": "2026-05-01", "date_to": "2026-05-19", "shop_name": "天猫"}),
                    limit=10,
                )
            )
        finally:
            connector_live_tools._call_jackyun_openapi = original

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["read_only"])
        self.assertEqual(calls[0][0], "oms.trade.fullinfoget")
        self.assertEqual(calls[0][1]["startTradeTime"], "2026-05-01")
        self.assertEqual(calls[0][1]["endTradeTime"], "2026-05-19")
        self.assertEqual(calls[0][1]["shopName"], "天猫")
        self.assertEqual(result["rows"][0]["tradeNo"], "SO001")

    def test_kingdee_live_snapshot_uses_execute_bill_query_only(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[dict[str, object]] = []

        def fake_query(
            *,
            form_id: str,
            field_keys: str,
            filter_string: str,
            limit: int,
            start_row: int,
            skill_dir: str,
        ) -> list[list[object]]:
            calls.append(
                {
                    "form_id": form_id,
                    "field_keys": field_keys,
                    "filter_string": filter_string,
                    "limit": limit,
                    "start_row": start_row,
                    "skill_dir": skill_dir,
                }
            )
            return [["VEN001", "测试供应商", "A"]]

        original = connector_live_tools._execute_kingdee_bill_query
        connector_live_tools._execute_kingdee_bill_query = fake_query
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "kingdee_erp",
                    "suppliers",
                    filters_json=json.dumps({"keyword": "测试'供应商"}),
                    limit=5,
                )
            )
        finally:
            connector_live_tools._execute_kingdee_bill_query = original

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["read_only"])
        self.assertEqual(result["query"]["method"], "ExecuteBillQuery")
        self.assertEqual(result["query"]["form_id"], "BD_Supplier")
        self.assertEqual(result["rows"][0]["FNumber"], "VEN001")
        self.assertIn("测试''供应商", str(calls[0]["filter_string"]))

    def test_kingdee_supplier_procurement_terms_expose_purchase_price_and_delivery_fields(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[dict[str, object]] = []

        def fake_query(
            *,
            form_id: str,
            field_keys: str,
            filter_string: str,
            limit: int,
            start_row: int,
            skill_dir: str,
        ) -> list[list[object]]:
            calls.append(
                {
                    "form_id": form_id,
                    "field_keys": field_keys,
                    "filter_string": filter_string,
                    "limit": limit,
                    "start_row": start_row,
                    "skill_dir": skill_dir,
                }
            )
            return [["PO001", "2026-05-01", "测试供应商", "SKU-001", "UNOVE", 100, 12.5, 1250, "2026-05-15"]]

        original = connector_live_tools._execute_kingdee_bill_query
        connector_live_tools._execute_kingdee_bill_query = fake_query
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "kingdee_erp",
                    "supplier_procurement_terms",
                    filters_json=json.dumps({"keyword": "测试供应商", "date_from": "2026-05-01"}),
                    limit=5,
                )
            )
        finally:
            connector_live_tools._execute_kingdee_bill_query = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["query"]["form_id"], "PUR_PurchaseOrder")
        field_keys = str(calls[0]["field_keys"])
        self.assertIn("FTaxPrice", field_keys)
        self.assertIn("FDeliveryDate", field_keys)
        self.assertNotIn("FPOOrderEntry", field_keys)
        self.assertIn("FSupplierId.FName like '%测试供应商%'", str(calls[0]["filter_string"]))
        self.assertEqual(result["coverage"]["historical_delay"], "requires_purchase_vs_receipt_join")
        self.assertNotIn("moq", result["coverage"])

    def test_kingdee_purchase_price_query_supports_material_filters(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[dict[str, object]] = []

        def fake_query(
            *,
            form_id: str,
            field_keys: str,
            filter_string: str,
            limit: int,
            start_row: int,
            skill_dir: str,
        ) -> list[list[object]]:
            calls.append(
                {
                    "form_id": form_id,
                    "field_keys": field_keys,
                    "filter_string": filter_string,
                    "limit": limit,
                    "start_row": start_row,
                    "skill_dir": skill_dir,
                }
            )
            return [["PO001", "2026-05-01", "测试供应商", "SKU-001", "UNOVE 发膜", 100, 12.5, 1250, "2026-05-15"]]

        original = connector_live_tools._execute_kingdee_bill_query
        connector_live_tools._execute_kingdee_bill_query = fake_query
        try:
            result = json.loads(
                connector_live_tools.query_erp_live_snapshot(
                    "kingdee_erp",
                    "supplier_procurement_terms",
                    filters_json=json.dumps(
                        {
                            "keyword": "测试供应商",
                            "goods_no": "SKU-001",
                            "goods_name": "UNOVE",
                            "date_from": "2026-05-01",
                        }
                    ),
                    limit=5,
                )
            )
        finally:
            connector_live_tools._execute_kingdee_bill_query = original

        self.assertEqual(result["status"], "success")
        filter_string = str(calls[0]["filter_string"])
        self.assertIn("FSupplierId.FName like '%测试供应商%'", filter_string)
        self.assertIn("FMaterialId.FNumber = 'SKU-001'", filter_string)
        self.assertIn("FMaterialId.FName like '%UNOVE%'", filter_string)
        self.assertIn("FDate >= '2026-05-01'", filter_string)

    def test_supplier_terms_mapping_verification_omits_moq_from_current_scope(self) -> None:
        connector_live_tools = cast(Any, self.modules["connector_live_tools"])
        calls: list[tuple[str, str]] = []

        def fake_snapshot(
            connector_id: str,
            dataset: str,
            filters_json: str = "",
            limit: int = 20,
            requested_by: str = "agent",
        ) -> str:
            calls.append((connector_id, dataset))
            rows_by_dataset = {
                ("jackyun_erp", "suppliers"): [
                    {"vendInfo": {"vendCode": "V001", "vendName": "测试供应商", "arrivePeriod": "15"}}
                ],
                ("jackyun_erp", "purchase_orders"): [
                    {"purchOrder": {"purchNo": "PO-JK-1", "details": [{"price": 12.5, "planInDate": "2026-05-20"}]}}
                ],
                ("jackyun_erp", "stock_inbound"): [{"inNo": "IN-JK-1", "gmtCreate": "2026-05-22"}],
                (
                    "kingdee_erp",
                    "supplier_procurement_terms",
                ): [
                    {
                        "FBillNo": "PO-KD-1",
                        "FTaxPrice": 13.5,
                        "FDeliveryDate": "2026-05-20",
                    }
                ],
                ("kingdee_erp", "purchase_orders"): [{"FAllAmount": 1350}],
            }
            rows = rows_by_dataset[(connector_id, dataset)]
            return json.dumps(
                {
                    "status": "success",
                    "connector_id": connector_id,
                    "dataset": dataset,
                    "read_only": True,
                    "row_count": len(rows),
                    "rows": rows,
                },
                ensure_ascii=False,
            )

        original = connector_live_tools.query_erp_live_snapshot
        connector_live_tools.query_erp_live_snapshot = fake_snapshot
        try:
            result = json.loads(connector_live_tools.verify_erp_supplier_terms_mapping(limit=3))
        finally:
            connector_live_tools.query_erp_live_snapshot = original

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["external_write_enabled"])
        self.assertEqual("confirmed", result["findings"]["purchase_price"]["status"])
        self.assertEqual("confirmed", result["findings"]["lead_time"]["status"])
        self.assertEqual("derived_required", result["findings"]["historical_delay"]["status"])
        self.assertNotIn("moq", result["findings"])
        self.assertNotIn("MOQ", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("最小起订", json.dumps(result, ensure_ascii=False))
        self.assertIn(("jackyun_erp", "suppliers"), calls)
        jackyun_supplier_check = next(
            check for check in result["checks"] if check["connector_id"] == "jackyun_erp" and check["dataset"] == "suppliers"
        )
        jackyun_purchase_check = next(
            check
            for check in result["checks"]
            if check["connector_id"] == "jackyun_erp" and check["dataset"] == "purchase_orders"
        )
        self.assertIn("vendInfo.arrivePeriod", jackyun_supplier_check["fields"])
        self.assertIn("purchOrder.details.price", jackyun_purchase_check["fields"])
        self.assertNotIn("测试供应商", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
