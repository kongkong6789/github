from __future__ import annotations

import importlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, cast


def _reload_source_modules() -> Any:
    import src.a2a_ecommerce_demo.source_registry_tools as source_registry_tools

    return importlib.reload(source_registry_tools)


class SourceSnapshotTests(unittest.TestCase):
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
        self.source_file = self.export_dir / "sales.csv"
        self.source_file.write_text("date,sku,qty\n2026-05-30,A001,3\n", encoding="utf-8")
        self.tools = _reload_source_modules()
        self.tools.register_source(
            source_id="sales_daily",
            display_name="销售日报",
            source_type="local_file",
            uri=str(self.source_file),
            allowed_root=str(self.export_dir),
            owner="ops",
            freshness_sla="24h",
            format_hint="csv",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _payload(self, text: str) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(text))

    def test_local_file_snapshot_is_immutable_and_idempotent_by_sha256(self) -> None:
        first = self._payload(self.tools.sync_source("sales_daily"))
        self.assertEqual(first["status"], "success")
        self.assertTrue(first["changed"])
        self.assertEqual(first["snapshot"]["source_id"], "sales_daily")
        self.assertEqual(first["snapshot"]["status"], "success")
        self.assertIn("raw/snapshots/sales_daily/", first["snapshot"]["raw_snapshot_path"])
        first_path = Path(first["snapshot"]["raw_snapshot_path"])
        self.assertTrue(first_path.exists())

        time.sleep(0.01)
        os.utime(self.source_file, None)
        second = self._payload(self.tools.sync_source("sales_daily"))
        self.assertEqual(second["status"], "skipped_unchanged")
        self.assertFalse(second["changed"])
        self.assertEqual(second["snapshot_id"], first["snapshot_id"])

        self.source_file.write_text("date,sku,qty\n2026-05-30,A001,9\n", encoding="utf-8")
        changed = self._payload(self.tools.sync_source("sales_daily"))
        self.assertEqual(changed["status"], "success")
        self.assertTrue(changed["changed"])
        self.assertNotEqual(changed["snapshot_id"], first["snapshot_id"])
        self.assertTrue(first_path.exists(), "old snapshot must not be overwritten or deleted")
        self.assertEqual(len(self.tools.load_snapshots()), 2)

    def test_schema_hash_and_dataset_registry_track_source_snapshot_ids(self) -> None:
        first = self._payload(self.tools.sync_source("sales_daily"))
        self.assertEqual(first["snapshot"]["row_count"], 1)
        self.assertEqual(first["snapshot"]["sheet_names"], ["sales"])
        self.assertTrue(first["snapshot"]["schema_hash"])

        self.source_file.write_text("date,sku,qty,new_field\n2026-05-31,A001,4,changed\n", encoding="utf-8")
        drift = self._payload(self.tools.sync_source("sales_daily"))

        self.assertEqual(drift["status"], "success")
        self.assertTrue(any("schema" in warning for warning in drift["quality_warnings"]))
        self.assertNotEqual(first["snapshot"]["schema_hash"], drift["snapshot"]["schema_hash"])
        registry = json.loads(Path(os.environ["A2A_DATASET_REGISTRY"]).read_text(encoding="utf-8"))
        dataset = registry["datasets"][drift["snapshot"]["duckdb_dataset_slug"]]
        self.assertEqual(dataset["source_id"], "sales_daily")
        self.assertEqual(dataset["snapshot_id"], drift["snapshot_id"])
        self.assertEqual(dataset["source_snapshot_path"], drift["snapshot"]["raw_snapshot_path"])


if __name__ == "__main__":
    unittest.main()
