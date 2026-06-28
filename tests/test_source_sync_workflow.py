from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast


def _reload_modules() -> dict[str, Any]:
    import src.a2a_ecommerce_demo.agent_tool_registry as agent_tool_registry
    import src.a2a_ecommerce_demo.intent_router as intent_router
    import src.a2a_ecommerce_demo.source_registry_tools as source_registry_tools

    intent_router = importlib.reload(intent_router)
    source_registry_tools = importlib.reload(source_registry_tools)
    agent_tool_registry = importlib.reload(agent_tool_registry)
    return {
        "source_registry_tools": source_registry_tools,
        "agent_tool_registry": agent_tool_registry,
        "intent_router": intent_router,
    }


class SourceSyncWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {
            key: os.environ.get(key)
            for key in [
                "A2A_DATA_DIR",
                "A2A_RAW_DIR",
                "A2A_SOURCE_REGISTRY_DIR",
                "A2A_SOURCE_REGISTRY_PATH",
                "A2A_SOURCE_SNAPSHOT_MANIFEST",
                "A2A_WAREHOUSE_DIR",
                "A2A_DATASET_REGISTRY",
                "A2A_WIKI_DIR",
                "A2A_AUDIT_DIR",
                "A2A_TASK_DIR",
                "A2A_TASK_QUEUE_DB",
            ]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.raw_dir = self.root / "raw"
        self.export_dir = self.root / "exports"
        self.warehouse_dir = self.data_dir / "warehouse"
        self.wiki_dir = self.root / "wiki"
        self.audit_dir = self.data_dir / "audit"
        self.task_dir = self.data_dir / "tasks"
        for path in [self.data_dir, self.raw_dir, self.export_dir, self.warehouse_dir, self.wiki_dir, self.audit_dir, self.task_dir]:
            path.mkdir(parents=True, exist_ok=True)
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_RAW_DIR"] = str(self.raw_dir)
        os.environ["A2A_SOURCE_REGISTRY_DIR"] = str(self.data_dir / "source_registry")
        os.environ["A2A_SOURCE_REGISTRY_PATH"] = str(self.data_dir / "source_registry" / "sources.json")
        os.environ["A2A_SOURCE_SNAPSHOT_MANIFEST"] = str(self.data_dir / "source_registry" / "snapshots.jsonl")
        os.environ["A2A_WAREHOUSE_DIR"] = str(self.warehouse_dir)
        os.environ["A2A_DATASET_REGISTRY"] = str(self.warehouse_dir / "dataset_registry.json")
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_AUDIT_DIR"] = str(self.audit_dir)
        os.environ["A2A_TASK_DIR"] = str(self.task_dir)
        os.environ["A2A_TASK_QUEUE_DB"] = str(self.task_dir / "tasks.sqlite")
        self.modules = _reload_modules()
        self.tools = self.modules["source_registry_tools"]

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _payload(self, text: str) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(text))

    def test_four_source_types_use_one_snapshot_manifest(self) -> None:
        local_file = self.export_dir / "local.csv"
        manual_file = self.export_dir / "manual.csv"
        local_file.write_text("sku,qty\nA001,1\n", encoding="utf-8")
        manual_file.write_text("sku,qty\nA002,2\n", encoding="utf-8")

        self.tools.register_source("local_sales", "本地导出", "local_file", str(local_file), str(self.export_dir), owner="ops", freshness_sla="24h")
        self.tools.register_source("manual_sales", "手工上传", "manual_upload", str(manual_file), str(self.export_dir), owner="ops", freshness_sla="24h")
        self.tools.register_source(
            "wedrive_sales",
            "微盘销售",
            "wecom_wedrive_file",
            owner="ops",
            freshness_sla="4h",
            metadata={"space_id": "space1", "file_id": "file1", "file_name": "wedrive.csv"},
        )
        self.tools.register_source(
            "wecom_sheet",
            "智能表销售",
            "wecom_smartsheet",
            owner="ops",
            freshness_sla="4h",
            credential_env_keys=["WECOM_SMARTSHEET_MCP_URL"],
            metadata={"docid": "doc1", "sheet_ids": ["sheet1"], "dataset": "channel_daily_sales"},
        )

        def fake_wedrive(source: dict[str, Any]) -> dict[str, Any]:
            self.assertEqual(source["metadata"]["space_id"], "space1")
            return {
                "file_name": "wedrive.csv",
                "content": b"sku,qty\nA003,3\n",
                "source_mtime": "2026-05-30T10:00:00",
                "source_size": 15,
                "remote_hash": "remote-md5",
            }

        def fake_smartsheet(source: dict[str, Any]) -> dict[str, Any]:
            self.assertEqual(source["metadata"]["docid"], "doc1")
            return {
                "file_name": "wecom_sheet.csv",
                "content": b"record_id,sku,qty\nr1,A004,4\n",
                "source_mtime": "2026-05-30T10:05:00",
                "source_size": 27,
                "profile": {"transport": "wecom_wedoc_mcp", "row_count": 1},
            }

        original_wedrive = self.tools._fetch_wecom_wedrive_source
        original_smartsheet = self.tools._fetch_wecom_smartsheet_source
        self.tools._fetch_wecom_wedrive_source = fake_wedrive
        self.tools._fetch_wecom_smartsheet_source = fake_smartsheet
        try:
            results = [
                self._payload(self.tools.sync_source("local_sales")),
                self._payload(self.tools.sync_source("manual_sales")),
                self._payload(self.tools.sync_source("wedrive_sales")),
                self._payload(self.tools.sync_source("wecom_sheet")),
            ]
        finally:
            self.tools._fetch_wecom_wedrive_source = original_wedrive
            self.tools._fetch_wecom_smartsheet_source = original_smartsheet

        self.assertTrue(all(result["changed"] for result in results))
        self.assertEqual({item["source_type"] for item in self.tools.load_snapshots()}, {"local_file", "manual_upload", "wecom_wedrive_file", "wecom_smartsheet"})
        source_summary = self._payload(self.tools.list_sources())
        self.assertEqual(source_summary["source_count"], 4)
        self.assertEqual(source_summary["freshness"]["failed_count"], 0)
        self.assertEqual(source_summary["freshness"]["recent_success_count"], 4)

    def test_erp_live_snapshot_records_boundary_and_failed_sync_does_not_pollute_old_snapshot(self) -> None:
        self.tools.register_source(
            "erp_inventory",
            "吉客云库存快照",
            "erp_readonly_snapshot",
            owner="ops",
            freshness_sla="6h",
            metadata={"connector_id": "jackyun_erp", "dataset": "inventory_stock", "filters": {"sku": "A001"}},
        )
        self.tools.register_source(
            "wedrive_failure",
            "失败微盘",
            "wecom_wedrive_file",
            owner="ops",
            freshness_sla="4h",
            metadata={"space_id": "space1", "file_id": "file1", "file_name": "bad.csv"},
        )

        def fake_erp(source: dict[str, Any]) -> dict[str, Any]:
            return {
                "file_name": "erp_inventory.json",
                "content": json.dumps({"rows": [{"sku": "A001", "qty": 5}]}, ensure_ascii=False).encode("utf-8"),
                "source_mtime": "2026-05-30T10:10:00",
                "source_size": 40,
                "profile": {"live_read_only_fallback": True, "query_filters": source["metadata"]["filters"], "row_count": 1},
            }

        def failing_wedrive(_source: dict[str, Any]) -> dict[str, Any]:
            raise PermissionError("wedrive permission denied: access_token=secret")

        original_erp = self.tools._fetch_erp_readonly_source
        original_wedrive = self.tools._fetch_wecom_wedrive_source
        self.tools._fetch_erp_readonly_source = fake_erp
        self.tools._fetch_wecom_wedrive_source = failing_wedrive
        try:
            erp = self._payload(self.tools.sync_source("erp_inventory"))
            before_count = len(self.tools.load_snapshots())
            failed = self._payload(self.tools.sync_source("wedrive_failure"))
            after_count = len(self.tools.load_snapshots())
        finally:
            self.tools._fetch_erp_readonly_source = original_erp
            self.tools._fetch_wecom_wedrive_source = original_wedrive

        self.assertEqual(erp["status"], "success")
        self.assertTrue(erp["snapshot"]["profile"]["live_read_only_fallback"])
        self.assertEqual(erp["snapshot"]["profile"]["query_filters"], {"sku": "A001"})
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_code"], "source_sync_failed")
        self.assertEqual(before_count, after_count)
        serialized = (self.audit_dir / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("source_sync_failed", serialized)
        self.assertNotIn("secret", serialized)

    def test_source_sync_intent_and_agent_allowlists_keep_read_only_analysis_safe(self) -> None:
        intent_router = self.modules["intent_router"]
        agent_registry = self.modules["agent_tool_registry"]

        sync_intent = intent_router.classify_user_intent("同步这个销售日报源，只处理这个 source")
        self.assertEqual(sync_intent.intent, "source_sync")
        self.assertTrue(sync_intent.start_background_workflow)

        analysis_intent = intent_router.classify_user_intent("基于已有数据分析 UNOVE 库存风险，不要重新同步")
        self.assertTrue(analysis_intent.read_only)
        self.assertFalse(analysis_intent.start_background_workflow)

        decision_tools = set(agent_registry.AGENT_TOOL_ALLOWLISTS["decision_agent"])
        workflow_tools = set(agent_registry.AGENT_TOOL_ALLOWLISTS["auto_workflow_agent"])
        data_tools = set(agent_registry.AGENT_TOOL_ALLOWLISTS["data_agent"])
        self.assertNotIn("sync_source", decision_tools)
        self.assertNotIn("run_source_sync_workflow", decision_tools)
        self.assertIn("list_sources", data_tools)
        self.assertIn("sync_source", workflow_tools)
        self.assertIn("run_source_sync_workflow", workflow_tools)


if __name__ == "__main__":
    unittest.main()
