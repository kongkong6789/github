from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _reload_platform_tools():
    import src.a2a_ecommerce_demo.platform_integration_tools as platform_integration_tools

    return importlib.reload(platform_integration_tools)


class P18PlatformIntegrationTests(unittest.TestCase):
    def test_registry_lists_six_platforms(self) -> None:
        tools = _reload_platform_tools()
        payload = json.loads(tools.list_reference_platforms())
        self.assertEqual("a2a_reference_platform_registry_v1", payload["schema"])
        self.assertEqual(6, payload["platform_count"])
        platform_ids = {item["platform_id"] for item in payload["platforms"]}
        self.assertEqual(
            {"duckdb", "lightrag", "karpathy_llm_wiki", "mirofish", "ruoyi_ai", "maxkb"},
            platform_ids,
        )

    def test_route_knowledge_stack_prefers_duckdb_for_numeric_questions(self) -> None:
        tools = _reload_platform_tools()
        payload = json.loads(
            tools.route_knowledge_stack(
                query_intent="inventory turnover",
                question="最近30天 UNOVE 库存周转和覆盖天数",
            )
        )
        layers = [item["layer"] for item in payload["routes"]]
        self.assertEqual("duckdb", layers[0])

    def test_route_knowledge_stack_adds_scenario_tools_for_simulation_questions(self) -> None:
        tools = _reload_platform_tools()
        payload = json.loads(
            tools.route_knowledge_stack(
                question="给出保守/平衡/激进三种补货推演方案对比",
            )
        )
        layers = [item["layer"] for item in payload["routes"]]
        self.assertIn("scenario_local", layers)

    def test_query_external_platform_readonly_returns_not_configured_without_env(self) -> None:
        tools = _reload_platform_tools()
        with patch.dict(os.environ, {}, clear=True):
            payload = json.loads(tools.query_external_platform_readonly("mirofish", query="hello"))
        self.assertEqual("not_configured", payload["status"])
        self.assertIn("simulate_decision_scenarios", payload.get("local_fallback_tools", []))

    def test_query_external_platform_readonly_blocks_embedded_platforms(self) -> None:
        tools = _reload_platform_tools()
        payload = json.loads(tools.query_external_platform_readonly("duckdb", query="select 1"))
        self.assertEqual("blocked", payload["status"])

    def test_seeded_p18_agent_templates_exist(self) -> None:
        expected = {
            "mirofish_scenario_report",
            "ruoyi_workflow_operator",
            "maxkb_knowledge_operator",
        }
        template_dir = PROJECT_ROOT / "config" / "agent_templates"
        loaded = {}
        for template_id in expected:
            path = template_dir / f"{template_id}.json"
            self.assertTrue(path.exists(), template_id)
            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded[template_id] = payload
            self.assertEqual("a2a_agent_template_v1", payload["schema"])
            self.assertEqual("draft", payload["status"])
            self.assertTrue(payload["evidence_required"])
            self.assertIn("DuckDB", payload["prompt"])
        self.assertEqual(expected, set(loaded))

    def test_check_reference_platform_health_marks_sidecars_not_configured(self) -> None:
        tools = _reload_platform_tools()
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(tools, "_embedded_health", return_value={"platform_id": "duckdb", "status": "ready", "reachable": True, "warnings": []}):
                payload = json.loads(tools.check_reference_platform_health("mirofish"))
        self.assertEqual("not_configured", payload["status"])
        self.assertEqual("not_configured", payload["platforms"][0]["status"])


if __name__ == "__main__":
    unittest.main()
