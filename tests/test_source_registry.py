from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast


def _reload_source_modules() -> Any:
    import src.a2a_ecommerce_demo.source_registry_tools as source_registry_tools

    return importlib.reload(source_registry_tools)


class SourceRegistryTests(unittest.TestCase):
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
        self.tools = _reload_source_modules()

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _payload(self, text: str) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(text))

    def test_register_source_persists_required_model_and_supported_types(self) -> None:
        result = self._payload(
            self.tools.register_source(
                source_id="tmall_sales_daily",
                display_name="天猫销售日报导出目录",
                source_type="local_folder",
                uri=str(self.export_dir),
                allowed_root=str(self.export_dir),
                sync_mode="on_demand",
                owner="ops",
                sensitivity_level="internal",
                credential_env_keys=[],
                freshness_sla="24h",
                format_hint="csv",
            )
        )

        self.assertEqual(result["status"], "registered")
        source = result["source"]
        self.assertEqual(source["source_id"], "tmall_sales_daily")
        self.assertEqual(source["source_type"], "local_folder")
        self.assertEqual(source["sync_mode"], "on_demand")
        self.assertEqual(source["status"], "active")
        for field in [
            "source_id",
            "display_name",
            "source_type",
            "uri",
            "allowed_root",
            "sync_mode",
            "owner",
            "sensitivity_level",
            "credential_env_keys",
            "format_hint",
            "expected_schema",
            "freshness_sla",
            "created_at",
            "updated_at",
        ]:
            self.assertIn(field, source)
        registry = self._payload(self.tools.list_sources())
        self.assertEqual(registry["schema"], "a2a_source_registry_v1")
        self.assertIn("wecom_wedrive_file", registry["supported_source_types"])
        self.assertIn("mcp_readonly_tool", registry["supported_source_types"])
        self.assertIn("agent_reach_public_web", registry["supported_source_types"])
        self.assertIn("agent_reach_public_search", registry["supported_source_types"])
        self.assertIn("agent_reach_public_video", registry["supported_source_types"])
        self.assertIn("agent_reach_social", registry["supported_source_types"])
        self.assertEqual(registry["source_count"], 1)

    def test_registry_rejects_duplicate_ids_plaintext_credentials_and_path_escape(self) -> None:
        self.tools.register_source(
            source_id="local_exports",
            display_name="平台导出",
            source_type="local_folder",
            uri=str(self.export_dir),
            allowed_root=str(self.export_dir),
            owner="ops",
            freshness_sla="24h",
        )

        duplicate = self._payload(
            self.tools.register_source(
                source_id="local_exports",
                display_name="重复",
                source_type="local_folder",
                uri=str(self.export_dir),
                allowed_root=str(self.export_dir),
                owner="ops",
                freshness_sla="24h",
            )
        )
        self.assertEqual(duplicate["status"], "error")
        self.assertEqual(duplicate["error_code"], "duplicate_source_id")

        escaped = self._payload(
            self.tools.register_source(
                source_id="escape",
                display_name="越界文件",
                source_type="local_file",
                uri=str(self.root / "outside.csv"),
                allowed_root=str(self.export_dir),
                owner="ops",
                freshness_sla="24h",
            )
        )
        self.assertEqual(escaped["status"], "error")
        self.assertEqual(escaped["error_code"], "path_outside_allowed_root")

        broad_root = self._payload(
            self.tools.register_source(
                source_id="broad_root",
                display_name="过宽根目录",
                source_type="local_file",
                uri=str(self.export_dir / "daily.csv"),
                allowed_root="/",
                owner="ops",
                freshness_sla="24h",
            )
        )
        self.assertEqual(broad_root["status"], "error")
        self.assertEqual(broad_root["error_code"], "path_outside_allowed_root")

        secret = self._payload(
            self.tools.register_source(
                source_id="secret_source",
                display_name="明文密钥",
                source_type="api_pull",
                uri="https://example.com/export.csv?access_token=plain-token",
                credential_env_keys=["plain-secret-value"],
                owner="ops",
                freshness_sla="24h",
            )
        )
        self.assertEqual(secret["status"], "error")
        self.assertIn(secret["error_code"], {"unsafe_source_uri", "credential_plaintext"})

    def test_wecom_sources_store_only_safe_identifiers_and_env_key_placeholders(self) -> None:
        smartsheet = self._payload(
            self.tools.register_source(
                source_id="daily_sales_sheet",
                display_name="企业微信日销智能表",
                source_type="wecom_smartsheet",
                uri="https://doc.weixin.qq.com/smartsheet/s3_doc?scode=secret-code&tab=sheetA",
                owner="ops",
                freshness_sla="4h",
                credential_env_keys=["WECOM_SMARTSHEET_MCP_URL"],
                metadata={
                    "docid": "s3_doc",
                    "sheet_ids": ["sheetA"],
                    "doc_url": "https://doc.weixin.qq.com/smartsheet/s3_doc?scode=secret-code&tab=sheetA",
                },
            )
        )
        wedrive = self._payload(
            self.tools.register_source(
                source_id="wedrive_sales_file",
                display_name="微盘销售日报",
                source_type="wecom_wedrive_file",
                owner="ops",
                freshness_sla="4h",
                credential_env_keys=[],
                metadata={
                    "space_id": "space_001",
                    "file_id": "file_001",
                    "file_name": "sales.xlsx",
                    "path_summary": "/经营/销售日报.xlsx",
                    "download_url": "https://qyapi.weixin.qq.com/download?access_token=secret-token",
                    "member_name": "张三",
                },
            )
        )

        serialized = json.dumps(self._payload(self.tools.list_sources()), ensure_ascii=False)
        self.assertEqual(smartsheet["status"], "registered")
        self.assertEqual(wedrive["status"], "registered")
        self.assertIn("s3_doc", serialized)
        self.assertIn("sheetA", serialized)
        self.assertIn("space_001", serialized)
        self.assertIn("file_001", serialized)
        self.assertNotIn("secret-code", serialized)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("download_url", serialized)
        self.assertNotIn("张三", serialized)

    def test_set_source_status_and_doctor_surface_bad_sources(self) -> None:
        next_dir = self.root / "exports_next"
        next_dir.mkdir(parents=True, exist_ok=True)
        (next_dir / "next.csv").write_text("date,sku\n2026-05-30,A001\n", encoding="utf-8")
        self.tools.register_source(
            source_id="exports",
            display_name="平台导出",
            source_type="local_folder",
            uri=str(self.export_dir),
            allowed_root=str(self.export_dir),
            owner="ops",
            freshness_sla="24h",
        )
        paused = self._payload(self.tools.set_source_status("exports", "paused"))
        self.assertEqual(paused["source"]["status"], "paused")
        rebound = self._payload(
            self.tools.rebind_source_path(
                "exports",
                uri=str(next_dir),
                allowed_root=str(next_dir),
            )
        )
        self.assertEqual(rebound["status"], "updated")
        self.assertEqual(rebound["source"]["uri"], str(next_dir.resolve(strict=False)))
        escaped_rebind = self._payload(
            self.tools.rebind_source_path(
                "exports",
                uri=str(self.root / "outside.csv"),
                allowed_root=str(self.export_dir),
            )
        )
        self.assertEqual(escaped_rebind["error_code"], "path_outside_allowed_root")

        registry_path = Path(os.environ["A2A_SOURCE_REGISTRY_PATH"])
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        payload["sources"]["bad"] = {
            "source_id": "bad",
            "display_name": "bad",
            "source_type": "local_file",
            "uri": str(self.root / "outside.csv"),
            "allowed_root": str(self.export_dir),
            "credential_env_keys": ["sk-live-secret"],
            "owner": "",
            "freshness_sla": "",
            "status": "active",
        }
        registry_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        doctor = self._payload(self.tools.check_source_registry_health())

        self.assertEqual(doctor["status"], "fail")
        self.assertGreaterEqual(doctor["problem_count"], 1)
        self.assertTrue(any("credential" in item["code"] or "owner" in item["code"] for item in doctor["problems"]))


if __name__ == "__main__":
    unittest.main()
