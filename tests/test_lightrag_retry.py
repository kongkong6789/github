from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch


class LightRAGRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            key: os.environ.get(key)
            for key in [
                "A2A_WIKI_DIR",
                "A2A_DATA_DIR",
                "A2A_LIGHTRAG_DIR",
                "A2A_WAREHOUSE_DIR",
                "A2A_DATASET_REGISTRY",
                "WORKING_DIR",
            ]
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.wiki_dir = self.root / "wiki"
        self.data_dir = self.root / "data"
        self.warehouse_dir = self.data_dir / "warehouse"
        self.working_dir = self.data_dir / "lightrag_official"
        self.wiki_dir.mkdir(parents=True)
        self.warehouse_dir.mkdir(parents=True)
        self.working_dir.mkdir(parents=True)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_LIGHTRAG_DIR"] = str(self.data_dir / "lightrag")
        os.environ["A2A_WAREHOUSE_DIR"] = str(self.warehouse_dir)
        os.environ["A2A_DATASET_REGISTRY"] = str(self.warehouse_dir / "dataset_registry.json")
        os.environ["WORKING_DIR"] = str(self.working_dir)

        import src.a2a_ecommerce_demo.lightrag_tools as lightrag_tools

        self.lightrag_tools = importlib.reload(lightrag_tools)

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_retry_failed_lightrag_docs_submits_compacted_retry_page(self) -> None:
        source = self.wiki_dir / "datasets" / "big-report.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "# Big UNOVE Report\n\n"
            "## 库存风险\n"
            + "\n".join(f"- UNOVE SKU-{i:03d} 库存风险与销售建议。" for i in range(300))
            + "\nTAIL_MARKER_SHOULD_BE_OMITTED\n",
            encoding="utf-8",
        )
        status_path = self.working_dir / "kv_store_doc_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "doc-failed": {
                        "status": "failed",
                        "file_path": "wiki/datasets/big-report.md",
                        "error": "LLM func: Worker execution timeout after 360s",
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        posted: list[dict[str, Any]] = []

        def fake_http(method: str, endpoint: str, payload: dict[str, Any] | None = None, timeout: float = 0) -> dict[str, str]:
            posted.append({"method": method, "endpoint": endpoint, "payload": payload or {}, "timeout": timeout})
            return {"track_id": "retry-track-1"}

        with (
            patch.object(self.lightrag_tools, "lightrag_server_status", return_value=json.dumps({"available": True})),
            patch.object(self.lightrag_tools, "_http_json", side_effect=fake_http),
        ):
            result = json.loads(self.lightrag_tools.retry_failed_lightrag_docs(limit=5, max_chars_per_doc=700))

        self.assertEqual("success", result["status"])
        self.assertEqual(1, len(result["retried"]))
        retry_path = result["retried"][0]["retry_path"]
        self.assertTrue(retry_path.startswith("wiki/lightrag-retry/"))
        self.assertTrue((self.wiki_dir / Path(retry_path).relative_to("wiki")).exists())
        self.assertEqual(1, len(posted))
        payload = cast(dict[str, Any], posted[0]["payload"])
        self.assertEqual("/documents/text", posted[0]["endpoint"])
        self.assertEqual(retry_path, payload["file_source"])
        self.assertIn("retry_of: wiki/datasets/big-report.md", payload["text"])
        self.assertLess(len(str(payload["text"])), 1800)
        self.assertNotIn("TAIL_MARKER_SHOULD_BE_OMITTED", payload["text"])

        sync_state = json.loads((self.data_dir / "lightrag" / "official_sync.json").read_text(encoding="utf-8"))
        self.assertEqual("retry-track-1", sync_state["documents"][retry_path]["track_id"])

    def test_diagnose_lightrag_failures_groups_root_causes(self) -> None:
        status_path = self.working_dir / "kv_store_doc_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "doc-balance": {
                        "status": "failed",
                        "file_path": "wiki/a.md",
                        "error_msg": "APIStatusError: Error code: 402 - Insufficient Balance",
                    },
                    "doc-embedding": {
                        "status": "failed",
                        "file_path": "wiki/b.md",
                        "error_msg": "Embedding func: Task forcefully terminated due to execution timeout (>75s)",
                    },
                    "doc-processed": {"status": "processed", "file_path": "wiki/c.md"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = json.loads(self.lightrag_tools.diagnose_lightrag_failures(limit=10))

        self.assertEqual("warning", result["status"])
        self.assertEqual({"failed": 2, "processed": 1}, result["status_counts"])
        self.assertEqual(1, result["root_cause_counts"]["llm_insufficient_balance"])
        self.assertEqual(1, result["root_cause_counts"]["embedding_timeout"])
        self.assertIn("先处理 LLM 供应商余额", result["primary_recovery_actions"][0])

    def test_summarize_lightrag_processing_status_flags_retry_blockers(self) -> None:
        status_path = self.working_dir / "kv_store_doc_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "doc-processed": {"status": "processed", "file_path": "wiki/processed.md"},
                    "doc-pending": {"status": "pending", "file_path": "wiki/pending.md"},
                    "doc-processing": {"status": "processing", "file_path": "wiki/processing.md"},
                    "doc-balance": {
                        "status": "failed",
                        "file_path": "wiki/balance.md",
                        "error_msg": "APIStatusError: Error code: 402 - Insufficient Balance",
                    },
                    "doc-model": {
                        "status": "failed",
                        "file_path": "wiki/model.md",
                        "error_msg": "ModelNotFound: model `deepseek-v4` is unavailable",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = json.loads(self.lightrag_tools.summarize_lightrag_processing_status(limit=10))

        self.assertEqual("warning", result["status"])
        self.assertEqual({"processed": 1, "pending": 1, "processing": 1, "failed": 2}, result["status_counts"])
        self.assertEqual(1, result["processed_count"])
        self.assertEqual(2, result["pending_count"])
        self.assertEqual(2, result["failed_count"])
        self.assertFalse(result["retry_guard"]["retry_allowed"])
        self.assertEqual(["llm_insufficient_balance", "model_unavailable"], result["retry_guard"]["blocking_root_causes"])
        self.assertIn("暂停 retry", result["retry_guard"]["recommendation"])

    def test_retry_failed_lightrag_docs_pauses_when_provider_blocker_exists(self) -> None:
        source = self.wiki_dir / "blocked.md"
        source.write_text("# Blocked\n\nretry should wait\n", encoding="utf-8")
        status_path = self.working_dir / "kv_store_doc_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "doc-balance": {
                        "status": "failed",
                        "file_path": "wiki/blocked.md",
                        "error_msg": "APIStatusError: Error code: 402 - Insufficient Balance",
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with (
            patch.object(self.lightrag_tools, "lightrag_server_status", return_value=json.dumps({"available": True})),
            patch.object(self.lightrag_tools, "_http_json") as http_json,
        ):
            result = json.loads(self.lightrag_tools.retry_failed_lightrag_docs(limit=5))

        self.assertEqual("retry_paused", result["status"])
        self.assertFalse(result["retry_guard"]["retry_allowed"])
        self.assertIn("余额", result["retry_guard"]["recommendation"])
        http_json.assert_not_called()

    def test_sync_auto_summarizes_high_risk_lightrag_pages(self) -> None:
        source = self.wiki_dir / "datasets" / "ops" / "field-dictionary.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "# Field Dictionary\n\n"
            + "\n".join(f"| UNOVE字段{i} | 库存 | 销售额 | GMV | ROI |" for i in range(400)),
            encoding="utf-8",
        )

        posted: list[dict[str, Any]] = []

        def fake_http(method: str, endpoint: str, payload: dict[str, Any] | None = None, timeout: float = 0) -> dict[str, str]:
            posted.append({"method": method, "endpoint": endpoint, "payload": payload or {}, "timeout": timeout})
            return {"track_id": "auto-summary-track"}

        with (
            patch.object(self.lightrag_tools, "lightrag_server_status", return_value=json.dumps({"available": True})),
            patch.object(self.lightrag_tools, "_http_json", side_effect=fake_http),
            patch.object(self.lightrag_tools, "rebuild_lightrag_index", return_value=json.dumps({"status": "success"})),
        ):
            result = json.loads(self.lightrag_tools.sync_obsidian_to_official_lightrag(max_docs=5, force=True))

        self.assertEqual("success", result["status"])
        self.assertEqual(1, len(result["auto_summarized"]))
        summary_path = result["auto_summarized"][0]["summary_path"]
        self.assertTrue(summary_path.startswith("wiki/lightrag-auto-summary/"))
        self.assertTrue((self.wiki_dir / Path(summary_path).relative_to("wiki")).exists())
        self.assertEqual(summary_path, posted[0]["payload"]["file_source"])
        self.assertIn("summary_of: wiki/datasets/ops/field-dictionary.md", posted[0]["payload"]["text"])
        self.assertLess(len(str(posted[0]["payload"]["text"])), len(source.read_text(encoding="utf-8")))
        self.assertLess(len(str(posted[0]["payload"]["text"])), 2200)

        sync_state = json.loads((self.data_dir / "lightrag" / "official_sync.json").read_text(encoding="utf-8"))
        self.assertEqual("wiki/datasets/ops/field-dictionary.md", sync_state["documents"][summary_path]["summary_of"])

    def test_sync_does_not_auto_summarize_retry_or_auto_summary_pages(self) -> None:
        retry_source = self.wiki_dir / "lightrag-retry" / "wiki_products_2026销售日报表_md.md"
        retry_source.parent.mkdir(parents=True)
        retry_source.write_text("# Retry\n\n" + "销售日报 " * 2000, encoding="utf-8")
        auto_source = self.wiki_dir / "lightrag-auto-summary" / "wiki_products_2026销售日报表_md.md"
        auto_source.parent.mkdir(parents=True)
        auto_source.write_text("# Auto Summary\n\n" + "销售日报 " * 2000, encoding="utf-8")

        posted: list[dict[str, Any]] = []

        def fake_http(method: str, endpoint: str, payload: dict[str, Any] | None = None, timeout: float = 0) -> dict[str, str]:
            posted.append({"method": method, "endpoint": endpoint, "payload": payload or {}, "timeout": timeout})
            return {"track_id": f"track-{len(posted)}"}

        with (
            patch.object(self.lightrag_tools, "lightrag_server_status", return_value=json.dumps({"available": True})),
            patch.object(self.lightrag_tools, "_http_json", side_effect=fake_http),
            patch.object(self.lightrag_tools, "rebuild_lightrag_index", return_value=json.dumps({"status": "success"})),
        ):
            result = json.loads(self.lightrag_tools.sync_obsidian_to_official_lightrag(max_docs=5, force=True))

        self.assertEqual([], result["auto_summarized"])
        self.assertEqual(
            ["wiki/lightrag-auto-summary/wiki_products_2026销售日报表_md.md", "wiki/lightrag-retry/wiki_products_2026销售日报表_md.md"],
            [call["payload"]["file_source"] for call in posted],
        )

    def test_auto_recover_lightrag_timeouts_requires_confirmation_before_mutation(self) -> None:
        source = self.wiki_dir / "products" / "2026销售日报表.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "# 2026销售日报表\n\n"
            + "\n".join(f"- UNOVE day {i}: GMV、销售额、库存、ROI 证据。" for i in range(300)),
            encoding="utf-8",
        )
        status_path = self.working_dir / "kv_store_doc_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "doc-timeout": {
                        "status": "failed",
                        "file_path": "wiki/products/2026销售日报表.md",
                        "error_msg": "C[4/4]: LLM func: Worker execution timeout after 360s",
                    },
                    "doc-balance": {
                        "status": "failed",
                        "file_path": "wiki/balance.md",
                        "error_msg": "Error code: 402 - Insufficient Balance",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        calls: list[dict[str, Any]] = []

        def fake_http(method: str, endpoint: str, payload: dict[str, Any] | None = None, timeout: float = 0) -> dict[str, Any]:
            calls.append({"method": method, "endpoint": endpoint, "payload": payload or {}, "timeout": timeout})
            if endpoint == "/documents/text":
                return {"status": "success", "track_id": "retry-summary-track"}
            if endpoint == "/documents/delete_document":
                delete_payload = payload or {}
                return {"status": "deletion_started", "doc_id": ",".join(delete_payload.get("doc_ids", []))}
            if endpoint == "/documents/status_counts":
                return {"status_counts": {"failed": 1, "processed": 1}}
            return {}

        with (
            patch.object(self.lightrag_tools, "lightrag_server_status", return_value=json.dumps({"available": True})),
            patch.object(self.lightrag_tools, "_http_json", side_effect=fake_http),
        ):
            result = json.loads(self.lightrag_tools.auto_recover_lightrag_timeouts(limit=10, max_chars_per_doc=900))

        self.assertEqual("confirmation_required", result["status"])
        self.assertTrue(result["requires_confirmation"])
        self.assertEqual("CONFIRM_LIGHTRAG_TIMEOUT_RECOVERY", result["confirmation_token"])
        self.assertEqual("auto_recover_lightrag_timeouts", result["interrupt"]["value"]["action_requests"][0]["name"])
        self.assertEqual(["approve", "reject"], result["interrupt"]["value"]["review_configs"][0]["allowed_decisions"])
        self.assertEqual(["doc-timeout"], [item["doc_id"] for item in result["preview"]["recoverable"]])
        self.assertEqual([], calls)

    def test_auto_recover_lightrag_timeouts_respects_interrupt_rejection(self) -> None:
        source = self.wiki_dir / "products" / "2026销售日报表.md"
        source.parent.mkdir(parents=True)
        source.write_text("# 2026销售日报表\n\n- timeout source", encoding="utf-8")
        status_path = self.working_dir / "kv_store_doc_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "doc-timeout": {
                        "status": "failed",
                        "file_path": "wiki/products/2026销售日报表.md",
                        "error_msg": "LLM func: Worker execution timeout after 360s",
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        calls: list[dict[str, Any]] = []

        def fake_http(method: str, endpoint: str, payload: dict[str, Any] | None = None, timeout: float = 0) -> dict[str, Any]:
            calls.append({"method": method, "endpoint": endpoint, "payload": payload or {}, "timeout": timeout})
            return {}

        with (
            patch.object(self.lightrag_tools, "lightrag_server_status", return_value=json.dumps({"available": True})),
            patch.object(self.lightrag_tools, "_http_json", side_effect=fake_http),
            patch.object(
                self.lightrag_tools,
                "request_human_approval",
                return_value={"status": "rejected", "approved": False, "message": "wait for finance"},
            ),
        ):
            result = json.loads(self.lightrag_tools.auto_recover_lightrag_timeouts(limit=10, max_chars_per_doc=900))

        self.assertEqual("cancelled", result["status"])
        self.assertEqual("wait for finance", result["rejection_reason"])
        self.assertEqual([], calls)

    def test_auto_recover_lightrag_timeouts_submits_summaries_and_deletes_original_failed_docs_after_confirmation(self) -> None:
        source = self.wiki_dir / "products" / "2026销售日报表.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "# 2026销售日报表\n\n"
            + "\n".join(f"- UNOVE day {i}: GMV、销售额、库存、ROI 证据。" for i in range(300)),
            encoding="utf-8",
        )
        status_path = self.working_dir / "kv_store_doc_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "doc-timeout": {
                        "status": "failed",
                        "file_path": "wiki/products/2026销售日报表.md",
                        "error_msg": "C[4/4]: LLM func: Worker execution timeout after 360s",
                    },
                    "doc-balance": {
                        "status": "failed",
                        "file_path": "wiki/balance.md",
                        "error_msg": "Error code: 402 - Insufficient Balance",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        calls: list[dict[str, Any]] = []

        def fake_http(method: str, endpoint: str, payload: dict[str, Any] | None = None, timeout: float = 0) -> dict[str, Any]:
            calls.append({"method": method, "endpoint": endpoint, "payload": payload or {}, "timeout": timeout})
            if endpoint == "/documents/text":
                return {"status": "success", "track_id": "retry-summary-track"}
            if endpoint == "/documents/delete_document":
                delete_payload = payload or {}
                return {"status": "deletion_started", "doc_id": ",".join(delete_payload.get("doc_ids", []))}
            if endpoint == "/documents/status_counts":
                return {"status_counts": {"failed": 1, "processed": 1}}
            return {}

        with (
            patch.object(self.lightrag_tools, "lightrag_server_status", return_value=json.dumps({"available": True})),
            patch.object(self.lightrag_tools, "_http_json", side_effect=fake_http),
        ):
            result = json.loads(
                self.lightrag_tools.auto_recover_lightrag_timeouts(
                    limit=10,
                    max_chars_per_doc=900,
                    confirmation_token="CONFIRM_LIGHTRAG_TIMEOUT_RECOVERY",
                )
            )

        self.assertEqual("success", result["status"])
        self.assertEqual(["doc-timeout"], [item["doc_id"] for item in result["deleted_original_failed_docs"]])
        self.assertEqual(1, len(result["retried"]))
        delete_calls = [call for call in calls if call["endpoint"] == "/documents/delete_document"]
        self.assertEqual([["doc-timeout"]], [call["payload"]["doc_ids"] for call in delete_calls])
        text_calls = [call for call in calls if call["endpoint"] == "/documents/text"]
        self.assertEqual(1, len(text_calls))
        self.assertIn("retry_of: wiki/products/2026销售日报表.md", text_calls[0]["payload"]["text"])

    def test_cleanup_confirmed_lightrag_failed_history_requires_confirmation_and_processed_retry(self) -> None:
        status_path = self.working_dir / "kv_store_doc_status.json"
        status_path.write_text(
            json.dumps(
                {
                    "doc-original": {
                        "status": "failed",
                        "file_path": "wiki/datasets/source.md",
                        "error_msg": "LLM timeout",
                    },
                    "doc-retry": {
                        "status": "processed",
                        "file_path": "wiki/lightrag-retry/source-timeout.md",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        sync_dir = self.data_dir / "lightrag"
        sync_dir.mkdir(parents=True)
        (sync_dir / "official_sync.json").write_text(
            json.dumps(
                {
                    "schema": "a2a_lightrag_official_sync_v1",
                    "documents": {
                        "wiki/lightrag-retry/source-timeout.md": {
                            "retry_of": "wiki/datasets/source.md",
                            "track_id": "retry-track",
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        blocked = json.loads(self.lightrag_tools.cleanup_confirmed_lightrag_failed_history())
        self.assertEqual("confirmation_required", blocked["status"])
        self.assertTrue(blocked["requires_confirmation"])
        self.assertEqual("DELETE_FAILED_HISTORY", blocked["confirmation_token"])
        self.assertIn("doc-original", json.loads(status_path.read_text(encoding="utf-8")))

        result = json.loads(
            self.lightrag_tools.cleanup_confirmed_lightrag_failed_history(
                confirmation_token="DELETE_FAILED_HISTORY",
            )
        )

        self.assertEqual("success", result["status"])
        self.assertEqual(["doc-original"], [item["doc_id"] for item in result["removed"]])
        remaining = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertNotIn("doc-original", remaining)
        self.assertIn("doc-retry", remaining)
        self.assertTrue(Path(result["archive_path"]).exists())

    def test_resolve_lightrag_reference_paths_links_dataset_page_to_source_chunks(self) -> None:
        warehouse_dir = self.data_dir / "warehouse"
        manifest_dir = warehouse_dir / "large_excel" / "ops"
        manifest_dir.mkdir(parents=True)
        manifest_path = manifest_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "source": str(self.root / "raw" / "ops.xlsx"),
                    "relative_source": "raw/ops.xlsx",
                    "sheets": [
                        {
                            "sheet": "Inventory",
                            "detected_header_row": 3,
                            "rows": 120,
                            "columns": 4,
                            "headers": ["SKU", "日期", "期末库存", "销量"],
                        }
                    ],
                    "chunks": [
                        {"sheet": "Inventory", "path": "warehouse/large_excel/ops/inventory_part_0001.csv", "rows": 50},
                        {"sheet": "Inventory", "path": "warehouse/large_excel/ops/inventory_part_0002.csv", "rows": 70},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (warehouse_dir / "dataset_registry.json").write_text(
            json.dumps(
                {
                    "datasets": {
                        "ops": {
                            "dataset_slug": "ops",
                            "source": "raw/ops.xlsx",
                            "manifest_path": str(manifest_path),
                            "wiki_pages": {"sheet_inventory": "wiki/datasets/ops/sheet-Inventory.md"},
                            "sheet_views": [
                                {
                                    "sheet_name": "Inventory",
                                    "raw_view_name": "ops__Inventory",
                                    "headers": ["SKU", "日期", "期末库存", "销量"],
                                }
                            ],
                            "mart_views": [{"category": "fact_inventory_daily", "view_name": "ops_inventory"}],
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = json.loads(
            self.lightrag_tools.resolve_lightrag_reference_paths(
                reference_path="wiki/datasets/ops/sheet-Inventory.md",
            )
        )

        self.assertEqual("success", result["status"])
        ref = result["references"][0]
        self.assertEqual("ops", ref["dataset_slug"])
        self.assertEqual("raw/ops.xlsx", ref["source_excel"])
        self.assertEqual("Inventory", ref["source_sheet"])
        self.assertEqual("ops__Inventory", ref["duckdb_dataset_view"])
        self.assertEqual("fact_inventory_daily", ref["duckdb_marts"][0]["category"])
        self.assertEqual("warehouse/large_excel/ops/inventory_part_0001.csv", ref["chunks"][0]["path"])
        self.assertEqual({"start": 4, "end": 53}, ref["chunks"][0]["estimated_source_excel_rows"])


if __name__ == "__main__":
    unittest.main()
