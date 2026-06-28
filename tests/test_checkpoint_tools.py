from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


class CheckpointToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            key: os.environ.get(key)
            for key in ["A2A_DATA_DIR", "A2A_LANGGRAPH_API_DIR", "A2A_CHECKPOINT_MIGRATION_DIR"]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        os.environ["A2A_DATA_DIR"] = str(self.root / "data")
        os.environ["A2A_LANGGRAPH_API_DIR"] = str(self.root / ".langgraph_api")
        os.environ["A2A_CHECKPOINT_MIGRATION_DIR"] = str(self.root / "migrations")

        import src.a2a_ecommerce_demo.checkpoint_tools as checkpoint_tools

        self.checkpoint_tools = importlib.reload(checkpoint_tools)

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_prepare_checkpoint_dir_removes_stale_temp_files_and_checks_writable(self) -> None:
        checkpoint_dir = self.root / ".langgraph_api"
        checkpoint_dir.mkdir()
        stale_tmp = checkpoint_dir / ".langgraph_ops.pckl.tmp"
        stale_tmp.write_text("stale", encoding="utf-8")

        result = self.checkpoint_tools.prepare_langgraph_checkpoint_dir(checkpoint_dir, stale_tmp_seconds=0)

        self.assertEqual("success", result["status"])
        self.assertTrue(result["writable"])
        self.assertFalse(stale_tmp.exists())
        self.assertEqual([str(stale_tmp.resolve())], result["removed_temp_files"])

    def test_migrate_checkpoint_pickles_writes_structured_manifest_and_raw_archive(self) -> None:
        checkpoint_dir = self.root / ".langgraph_api"
        checkpoint_dir.mkdir()
        checkpoint = checkpoint_dir / "thread-one.pckl"
        checkpoint.write_bytes(b"checkpoint")

        dry_run = self.checkpoint_tools.migrate_checkpoint_pickles(checkpoint_dir=checkpoint_dir)
        self.assertEqual("dry_run", dry_run["status"])
        self.assertEqual(1, dry_run["checkpoint_count"])

        result = self.checkpoint_tools.migrate_checkpoint_pickles(
            checkpoint_dir=checkpoint_dir,
            dry_run=False,
            confirm=True,
        )

        self.assertEqual("success", result["status"])
        manifest_path = Path(result["manifest_path"])
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("a2a_langgraph_checkpoint_migration_v1", manifest["schema"])
        self.assertEqual("thread-one.pckl", manifest["files"][0]["name"])
        self.assertTrue(Path(manifest["files"][0]["archived_to"]).exists())
        self.assertEqual(64, len(manifest["files"][0]["sha256"]))


if __name__ == "__main__":
    unittest.main()
