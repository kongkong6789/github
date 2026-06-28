from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


class EvidenceGraphToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            key: os.environ.get(key)
            for key in [
                "A2A_DATA_DIR",
                "A2A_WIKI_DIR",
                "A2A_DATASET_REGISTRY",
                "A2A_TASK_DIR",
                "A2A_AUDIT_LOG",
            ]
        }

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _create_fixture(self, tmp: str) -> dict[str, Path]:
        root = Path(tmp)
        data_dir = root / "data"
        wiki_dir = root / "wiki"
        registry_path = data_dir / "warehouse" / "dataset_registry.json"
        task_dir = data_dir / "tasks"
        report_dir = data_dir / "reports"
        audit_path = data_dir / "audit" / "events.jsonl"
        for path in [registry_path.parent, task_dir, report_dir, audit_path.parent, wiki_dir / "datasets" / "UNOVE_sales", wiki_dir / "decisions"]:
            path.mkdir(parents=True, exist_ok=True)

        (wiki_dir / "datasets" / "UNOVE_sales" / "overview.md").write_text("# UNOVE sales dataset\n\n天猫渠道 SKU 证据。", encoding="utf-8")
        (wiki_dir / "decisions" / "UNOVE-growth.md").write_text("# UNOVE 增长决策\n\n需要人工确认采购。", encoding="utf-8")
        report_path = report_dir / "unove-final.md"
        report_path.write_text(
            "\n".join(
                [
                    "# UNOVE 5月销售提升报告",
                    "",
                    "## Evidence Chain",
                    "- `wiki/datasets/UNOVE_sales/overview.md`",
                    "- DuckDB: `data/warehouse/a2a.duckdb`",
                    "- Registry: `data/warehouse/dataset_registry.json`",
                    "- Missing data: cash, supplier",
                ]
            ),
            encoding="utf-8",
        )

        registry_path.write_text(
            json.dumps(
                {
                    "schema": "a2a_dataset_registry_v1",
                    "datasets": {
                        "UNOVE_sales": {
                            "dataset_slug": "UNOVE_sales",
                            "source": str(root / "raw" / "unove-sales.xlsx"),
                            "relative_source": "raw/unove-sales.xlsx",
                            "duckdb_path": str(data_dir / "warehouse" / "a2a.duckdb"),
                            "manifest_path": str(data_dir / "warehouse" / "large_excel" / "UNOVE_sales" / "manifest.json"),
                            "quality_report_path": str(data_dir / "warehouse" / "large_excel" / "UNOVE_sales" / "quality_report.json"),
                            "wiki_pages": {
                                "overview": "wiki/datasets/UNOVE_sales/overview.md",
                                "decision": "wiki/decisions/UNOVE-growth.md",
                            },
                            "mart_views": [
                                {
                                    "category": "fact_sales_daily",
                                    "view_name": "fact_sales_daily__UNOVE_sales",
                                    "source_view": "UNOVE_sales__sheet",
                                }
                            ],
                            "sheet_views": [
                                {
                                    "sheet": "天猫销售",
                                    "raw_view_name": "UNOVE_sales__sheet",
                                    "headers": ["品牌", "销售渠道", "SKU编码", "仓库", "供应商", "客户手机号", "客户地址", "采购价明细"],
                                    "field_profiles": [
                                        {"field": "品牌", "sample_values": ["UNOVE"]},
                                        {"field": "销售渠道", "sample_values": ["天猫"]},
                                        {"field": "SKU编码", "sample_values": ["SKU-001"]},
                                        {"field": "仓库", "sample_values": ["杭州仓"]},
                                        {"field": "供应商", "sample_values": ["供应商A"]},
                                        {"field": "客户手机号", "sample_values": ["13800138000"]},
                                        {"field": "客户地址", "sample_values": ["上海市长宁区某路1号"]},
                                        {"field": "采购价明细", "sample_values": ["采购价=19.90"]},
                                    ],
                                }
                            ],
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        task_id = "task-unove-growth"
        (task_dir / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "goal": "分析 UNOVE 天猫 SKU 增长，输出采购确认项",
                    "status": "warning",
                    "final_report": {
                        "saved_to": str(report_path),
                        "evidence_chain": {
                            "wiki_pages": ["wiki/datasets/UNOVE_sales/overview.md"],
                            "report_paths": [str(report_path)],
                            "duckdb_marts": [{"mart": "fact_sales_daily__UNOVE_sales", "fields": ["SKU编码", "销售渠道"]}],
                            "data_gaps": ["cash", "supplier"],
                        },
                    },
                    "steps": [
                        {
                            "task": "company_strategy",
                            "status": "warning",
                            "summary": "UNOVE 天猫 SKU 增长需要人工确认采购。",
                            "evidence": ["wiki/datasets/UNOVE_sales/overview.md", str(report_path)],
                            "risks": ["大额采购需要人工确认"],
                            "missing_data": ["cash", "supplier"],
                            "next_actions": ["确认供应商交期"],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        audit_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-05-20T10:00:00",
                    "event_type": "sensitive_field_access",
                    "task_id": task_id,
                    "tool_name": "record_sensitive_field_access",
                    "risk_level": "medium",
                    "data_sources": ["DuckDB", "audit"],
                    "paths": [str(report_path)],
                    "summary": "使用敏感字段生成聚合证据。",
                    "risks": ["必须脱敏客户手机号和地址，不展示采购价明细。"],
                    "metadata": {
                        "category": "customer_pii",
                        "fields": ["客户手机号", "客户地址", "采购价=19.90"],
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        os.environ["A2A_DATA_DIR"] = str(data_dir)
        os.environ["A2A_WIKI_DIR"] = str(wiki_dir)
        os.environ["A2A_DATASET_REGISTRY"] = str(registry_path)
        os.environ["A2A_TASK_DIR"] = str(task_dir)
        os.environ["A2A_AUDIT_LOG"] = str(audit_path)
        return {"report_path": report_path, "task_dir": task_dir, "registry_path": registry_path}

    def test_builds_graph_from_registry_wiki_task_report_and_audit_without_sensitive_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._create_fixture(tmp)
            import src.a2a_ecommerce_demo.evidence_graph_tools as graph_tools

            graph_tools = importlib.reload(graph_tools)
            graph = json.loads(graph_tools.build_evidence_graph(scope="global", limit=200))

            self.assertEqual("a2a_evidence_graph_v1", graph["schema"])
            node_types = {node["type"] for node in graph["nodes"]}
            edge_types = {edge["type"] for edge in graph["edges"]}
            self.assertTrue(
                {
                    "brand",
                    "channel",
                    "sku",
                    "warehouse",
                    "supplier",
                    "dataset",
                    "mart",
                    "wiki_page",
                    "report",
                    "decision",
                    "risk",
                    "field",
                }.issubset(node_types)
            )
            self.assertTrue(
                {
                    "derived_from",
                    "summarizes",
                    "references",
                    "affects",
                    "belongs_to",
                    "has_risk",
                    "needs_confirmation",
                    "uses_sensitive_field",
                }.issubset(edge_types)
            )
            for node in graph["nodes"]:
                self.assertEqual({"id", "type", "label", "source_path", "summary", "risk_level", "metadata"}, set(node))
                self.assertNotIn("13800138000", node["label"])
                self.assertNotIn("上海市长宁区", node["label"])
                self.assertNotIn("19.90", node["label"])
            for edge in graph["edges"]:
                self.assertEqual({"id", "type", "source", "target", "label", "source_path", "summary", "risk_level", "metadata"}, set(edge))
            self.assertEqual(len({node["id"] for node in graph["nodes"]}), len(graph["nodes"]))
            self.assertEqual(len({edge["id"] for edge in graph["edges"]}), len(graph["edges"]))
            self.assertTrue(any(node["source_path"] == str(paths["registry_path"].resolve()) for node in graph["nodes"]))

    def test_task_report_scope_type_filters_and_limits_are_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._create_fixture(tmp)
            import src.a2a_ecommerce_demo.evidence_graph_tools as graph_tools

            graph_tools = importlib.reload(graph_tools)
            task_graph = json.loads(graph_tools.build_evidence_graph(scope="task", task_id="task-unove-growth", limit=50))
            report_graph = json.loads(
                graph_tools.build_evidence_graph(
                    scope="report",
                    report_path=str(paths["report_path"]),
                    node_types=["report", "wiki_page", "risk"],
                    limit=5,
                )
            )

            self.assertTrue(any(node["type"] == "decision" and node["metadata"].get("task_id") == "task-unove-growth" for node in task_graph["nodes"]))
            self.assertLessEqual(len(report_graph["nodes"]), 5)
            self.assertTrue({node["type"] for node in report_graph["nodes"]}.issubset({"report", "wiki_page", "risk"}))
            self.assertTrue(report_graph["counts"]["truncated"])

    def test_list_nodes_and_edges_return_filtered_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._create_fixture(tmp)
            import src.a2a_ecommerce_demo.evidence_graph_tools as graph_tools

            graph_tools = importlib.reload(graph_tools)
            nodes = json.loads(graph_tools.list_evidence_graph_nodes(node_types=["dataset", "field"], limit=20))
            edges = json.loads(graph_tools.list_evidence_graph_edges(edge_types=["references", "uses_sensitive_field"], limit=20))

            self.assertTrue(nodes["nodes"])
            self.assertTrue(edges["edges"])
            self.assertTrue({node["type"] for node in nodes["nodes"]}.issubset({"dataset", "field"}))
            self.assertTrue({edge["type"] for edge in edges["edges"]}.issubset({"references", "uses_sensitive_field"}))


if __name__ == "__main__":
    unittest.main()
