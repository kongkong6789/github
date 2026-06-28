from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast


def _reload_wecom_modules() -> dict[str, Any]:
    import src.a2a_ecommerce_demo.connector_registry as connector_registry
    import src.a2a_ecommerce_demo.connector_tools as connector_tools
    import src.a2a_ecommerce_demo.wecom_smartsheet_tools as wecom_smartsheet_tools

    connector_registry = importlib.reload(connector_registry)
    connector_tools = importlib.reload(connector_tools)
    wecom_smartsheet_tools = importlib.reload(wecom_smartsheet_tools)
    return {
        "connector_registry": connector_registry,
        "connector_tools": connector_tools,
        "wecom_smartsheet_tools": wecom_smartsheet_tools,
    }


class WeComSmartSheetToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in [
                "A2A_DATA_DIR",
                "A2A_ENV_PATH",
                "A2A_WAREHOUSE_DIR",
                "A2A_WIKI_DIR",
                "A2A_DUCKDB_PATH",
                "A2A_DATASET_REGISTRY",
                "A2A_CONNECTOR_REGISTRY",
                "A2A_WECOM_SMARTSHEET_SOURCE_CONFIG",
                "WECOM_SMARTSHEET_MCP_URL",
                "WEWORK_SMARTSHEET_MCP_URL",
                "WEDOC_MCP_URL",
                "WEWORK_WEDOC_MCP_URL",
                "WECOM_SMARTSHEET_URL",
                "WECOM_SMARTSHEET_DOCID",
                "WECOM_SMARTSHEET_SHEET_ID",
                "WECOM_SMARTSHEET_SHEET_IDS",
            ]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.warehouse_dir = self.data_dir / "warehouse"
        self.wiki_dir = self.root / "wiki"
        self.config_path = self.root / "wecom_smartsheet_sources.json"
        self.env_path = self.root / ".env"
        self.warehouse_dir.mkdir(parents=True, exist_ok=True)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text("", encoding="utf-8")
        self.config_path.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "source_id": "daily_sales",
                            "name": "渠道每日销售",
                            "dataset": "channel_daily_sales",
                            "doc_url": "https://doc.weixin.qq.com/smartsheet/s3_doc?scode=secret-code&tab=sheetA",
                            "sheet_id": "sheetA",
                            "mcp_url": "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=secret-key",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_ENV_PATH"] = str(self.env_path)
        os.environ["A2A_WAREHOUSE_DIR"] = str(self.warehouse_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_DUCKDB_PATH"] = str(self.warehouse_dir / "a2a.duckdb")
        os.environ["A2A_DATASET_REGISTRY"] = str(self.warehouse_dir / "dataset_registry.json")
        os.environ["A2A_CONNECTOR_REGISTRY"] = str(self.warehouse_dir / "connector_registry.json")
        os.environ["A2A_WECOM_SMARTSHEET_SOURCE_CONFIG"] = str(self.config_path)
        for key in [
            "WECOM_SMARTSHEET_MCP_URL",
            "WEWORK_SMARTSHEET_MCP_URL",
            "WEDOC_MCP_URL",
            "WEWORK_WEDOC_MCP_URL",
            "WECOM_SMARTSHEET_URL",
            "WECOM_SMARTSHEET_DOCID",
            "WECOM_SMARTSHEET_SHEET_ID",
            "WECOM_SMARTSHEET_SHEET_IDS",
        ]:
            os.environ.pop(key, None)
        self.modules = _reload_wecom_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_list_sources_redacts_sensitive_url_parts(self) -> None:
        wecom_tools = self.modules["wecom_smartsheet_tools"]

        result = json.loads(wecom_tools.list_wecom_smartsheet_sources())

        self.assertEqual(result["connector_id"], "wecom_smartsheet")
        self.assertEqual(result["configured_source_count"], 1)
        self.assertEqual(result["sources"][0]["source_id"], "daily_sales")
        self.assertTrue(result["sources"][0]["mcp_configured"])
        text = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("secret-code", text)
        self.assertNotIn("secret-key", text)
        self.assertIn("doc.weixin.qq.com/smartsheet/s3_doc?...", text)

    def test_query_by_mcp_flattens_records_with_schema_and_redacts_secrets(self) -> None:
        wecom_tools = cast(Any, self.modules["wecom_smartsheet_tools"])

        def fake_query_by_mcp(source: dict[str, Any]) -> dict[str, Any]:
            self.assertEqual(source["sheet_id"], "sheetA")
            return {
                "data": {
                    "getRecords": {
                        "records": [
                            {
                                "record_id": "rec-1",
                                "values": {
                                    "f36FQs": [{"text": "2026年5月"}],
                                    "fGxWct": "13CHAN10165",
                                    "fruYTq": 679.9,
                                    "渠道名称": [{"text": "抖音旗舰店"}],
                                },
                            }
                        ]
                    }
                }
            }

        original = wecom_tools._query_records_by_mcp
        wecom_tools._query_records_by_mcp = fake_query_by_mcp
        try:
            result = json.loads(wecom_tools.query_wecom_smartsheet_records(source_id="daily_sales"))
        finally:
            wecom_tools._query_records_by_mcp = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["mode"], "live_read_only_mcp")
        self.assertEqual(result["transport"], "wecom_wedoc_mcp")
        self.assertEqual(result["dataset"], "channel_daily_sales")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["rows"][0]["record_id"], "rec-1")
        self.assertEqual(result["rows"][0]["年月"], "2026年5月")
        self.assertEqual(result["rows"][0]["渠道编码"], "13CHAN10165")
        self.assertEqual(result["rows"][0]["1日"], 679.9)
        self.assertEqual(result["rows"][0]["渠道名称"], "抖音旗舰店")
        text = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("secret-code", text)
        self.assertNotIn("secret-key", text)

    def test_sync_dry_run_uses_connector_preview_without_external_write(self) -> None:
        wecom_tools = self.modules["wecom_smartsheet_tools"]

        result = json.loads(wecom_tools.sync_wecom_smartsheet_snapshot(source_id="daily_sales", dry_run=True))

        self.assertEqual(result["status"], "preview")
        self.assertEqual(result["connector_id"], "wecom_smartsheet")
        self.assertEqual(result["dataset"], "channel_daily_sales")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["external_write_enabled"])
        self.assertEqual(result["permission_scope"], "read_only")

    def test_query_without_mcp_does_not_fallback_to_direct_api(self) -> None:
        wecom_tools = self.modules["wecom_smartsheet_tools"]
        os.environ["WECOM_SMARTSHEET_DOCID"] = "s3_doc"
        os.environ["WECOM_SMARTSHEET_SHEET_IDS"] = "sheetA,sheetB"

        result = json.loads(wecom_tools.query_wecom_smartsheet_records(limit=10))

        self.assertEqual(result["status"], "error")
        self.assertEqual(result.get("transport", ""), "")
        self.assertEqual(result["error_type"], "ValueError")
        self.assertIn("WECOM_SMARTSHEET_MCP_URL", result["error"])
        self.assertIn(".env", result["error"])
        self.assertIn("wecom_smartsheet_sources", result["error"])
        self.assertNotIn("直连企业微信 API", result["error"])

    def test_query_with_runtime_doc_url_without_registered_docid_is_rejected(self) -> None:
        self.config_path.write_text(json.dumps({"sources": []}, ensure_ascii=False), encoding="utf-8")
        os.environ["WECOM_SMARTSHEET_MCP_URL"] = "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=secret-key"
        wecom_tools = cast(Any, _reload_wecom_modules()["wecom_smartsheet_tools"])

        result = json.loads(
            wecom_tools.query_wecom_smartsheet_records(
                doc_url="https://doc.weixin.qq.com/smartsheet/s3_doc?scode=secret-code&tab=sheetB&viewId=view1",
                dataset="channel_daily_sales",
                limit=10,
            )
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "PermissionError")
        self.assertIn("已登记", result["error"])
        self.assertNotIn("secret-code", json.dumps(result, ensure_ascii=False))

    def test_query_with_runtime_doc_url_matching_env_docid_uses_mcp(self) -> None:
        self.config_path.write_text(json.dumps({"sources": []}, ensure_ascii=False), encoding="utf-8")
        os.environ["WECOM_SMARTSHEET_MCP_URL"] = "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=secret-key"
        os.environ["WECOM_SMARTSHEET_DOCID"] = "s3_doc"
        wecom_tools = cast(Any, _reload_wecom_modules()["wecom_smartsheet_tools"])
        seen_source: dict[str, Any] = {}

        def fake_query_by_mcp(source: dict[str, Any]) -> dict[str, Any]:
            seen_source.update(source)
            return {
                "data": {
                    "getRecords": {
                        "records": [
                            {
                                "record_id": "rec-url-1",
                                "values": {
                                    "fGxWct": "13CHAN10165",
                                    "fruYTq": 679.9,
                                },
                            }
                        ]
                    }
                }
            }

        original = wecom_tools._query_records_by_mcp
        wecom_tools._query_records_by_mcp = fake_query_by_mcp
        try:
            result = json.loads(
                wecom_tools.query_wecom_smartsheet_records(
                    doc_url="https://doc.weixin.qq.com/smartsheet/s3_doc?scode=secret-code&tab=sheetB&viewId=view1",
                    dataset="channel_daily_sales",
                    limit=10,
                )
            )
        finally:
            wecom_tools._query_records_by_mcp = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source_id"], "env_default")
        self.assertEqual(result["dataset"], "channel_daily_sales")
        self.assertEqual(result["query"]["sheet_ids"], ["sheetB"])
        self.assertEqual(result["rows"][0]["渠道编码"], "13CHAN10165")
        self.assertEqual(result["rows"][0]["1日"], 679.9)
        self.assertEqual(seen_source["sheet_id"], "sheetB")
        self.assertEqual(seen_source["docid"], "s3_doc")
        self.assertIn("apikey=secret-key", seen_source["mcp_url"])
        self.assertNotIn("secret-code", json.dumps(result, ensure_ascii=False))

    def test_docid_and_sheet_ids_config_generate_doc_url_without_scode(self) -> None:
        self.config_path.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "source_id": "daily_sales_docid_only",
                            "name": "渠道每日销售",
                            "dataset": "channel_daily_sales",
                            "docid": "s3_docid_only",
                            "sheet_ids": ["sheetA", "sheetB"],
                            "mcp_url": "https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=secret-key",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        wecom_tools = cast(Any, _reload_wecom_modules()["wecom_smartsheet_tools"])
        seen_urls: list[str] = []

        def fake_query_by_mcp(source: dict[str, Any]) -> dict[str, Any]:
            seen_urls.append(source["doc_url"])
            return {"data": {"getRecords": {"records": []}}}

        original = wecom_tools._query_records_by_mcp
        wecom_tools._query_records_by_mcp = fake_query_by_mcp
        try:
            result = json.loads(wecom_tools.query_wecom_smartsheet_records(source_id="daily_sales_docid_only"))
        finally:
            wecom_tools._query_records_by_mcp = original

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["query"]["sheet_ids"], ["sheetA", "sheetB"])
        self.assertEqual(
            seen_urls,
            [
                "https://doc.weixin.qq.com/smartsheet/s3_docid_only?tab=sheetA",
                "https://doc.weixin.qq.com/smartsheet/s3_docid_only?tab=sheetB",
            ],
        )
        self.assertNotIn("scode=", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
