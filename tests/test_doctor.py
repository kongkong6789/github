from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCTOR_PATH = PROJECT_ROOT / "scripts" / "doctor.py"


def load_doctor() -> ModuleType:
    spec = importlib.util.spec_from_file_location("a2a_doctor", DOCTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scripts/doctor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class DoctorTests(unittest.TestCase):
    def test_run_doctor_returns_statuses_suggestions_and_redacted_json(self) -> None:
        doctor = load_doctor()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            (data_dir / "tasks").mkdir(parents=True)
            (root / "agent-chat-ui").mkdir()
            (root / "scripts").mkdir()
            (root / "scripts" / "only_unix.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (root / ".env").write_text(
                "\n".join(
                    [
                        "OPENAI_API_KEY=sk-test-secret-value",
                        "OPENAI_MODEL=gpt-4.1-mini",
                        "OPENAI_BASE_URL=https://api.openai.com/v1",
                        "EMBEDDING_BINDING_API_KEY=token_that_must_not_leak",
                        "LIGHTRAG_API_KEY=password_that_must_not_leak",
                    ],
                ),
                encoding="utf-8",
            )
            write_json(
                data_dir / "warehouse" / "dataset_registry.json",
                {"schema": "a2a_dataset_registry_v1", "datasets": {}},
            )
            write_json(
                data_dir / "warehouse" / "connector_registry.json",
                {
                    "schema": "a2a_connector_registry_v1",
                    "connectors": {
                        "jackyun_erp": {
                            "connector_id": "jackyun_erp",
                            "external_write_enabled": False,
                            "read_only_default": True,
                        },
                    },
                },
            )
            write_json(
                data_dir / "mcp" / "tool_policy.json",
                {
                    "schema": "a2a_mcp_tool_policy_v1",
                    "tools": {
                        "create_purchase_order": {
                            "read_only": False,
                            "requires_human_confirmation": True,
                            "external_write_enabled": False,
                        },
                    },
                },
            )
            write_json(
                data_dir / "skill_registry" / "registry.json",
                {
                    "schema": "a2a_agent_skill_registry_v1",
                    "skills": {
                        "active_without_template": {
                            "skill_id": "active_without_template",
                            "status": "active",
                        },
                    },
                },
            )
            write_json(data_dir / "tasks" / "ok.json", {"task_id": "ok"})
            (data_dir / "tasks" / "bad.json").write_text("{not json", encoding="utf-8")
            (data_dir / "audit").mkdir()
            (data_dir / "audit" / "events.jsonl").write_text(
                '{"event_type":"ok"}\n{not json\n',
                encoding="utf-8",
            )

            result = doctor.run_doctor(
                project_root=root,
                env={
                    "A2A_DATA_DIR": str(data_dir),
                    "A2A_DOCTOR_SKIP_PORT_CHECKS": "1",
                },
            )
            serialized = json.dumps(result, ensure_ascii=False)

            statuses = {check["status"] for check in result["checks"]}
            self.assertTrue({"ok", "warn", "fail", "skipped"}.issubset(statuses))
            self.assertNotIn("sk-test-secret-value", serialized)
            self.assertNotIn("token_that_must_not_leak", serialized)
            self.assertNotIn("password_that_must_not_leak", serialized)

            failures = [check for check in result["checks"] if check["status"] == "fail"]
            self.assertTrue(failures)
            for failure in failures:
                self.assertTrue(failure["suggestion"], failure)
                self.assertTrue(failure["files"] or failure["commands"], failure)

            human_output = doctor.format_human(result)
            self.assertIn("fail", human_output.lower())
            self.assertIn("***REDACTED***", human_output)
            self.assertNotIn("sk-test-secret-value", human_output)

    def test_config_validators_cover_external_writes_and_active_skill_templates(self) -> None:
        doctor = load_doctor()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            write_json(
                data_dir / "warehouse" / "connector_registry.json",
                {
                    "connectors": {
                        "unsafe": {
                            "connector_id": "unsafe",
                            "external_write_enabled": True,
                        },
                    },
                },
            )
            write_json(
                data_dir / "mcp" / "tool_policy.json",
                {
                    "tools": {
                        "send_external_message": {
                            "read_only": False,
                            "requires_human_confirmation": False,
                            "external_write_enabled": True,
                        },
                    },
                },
            )
            write_json(
                data_dir / "skill_registry" / "registry.json",
                {
                    "skills": {
                        "safe": {"skill_id": "safe", "status": "active"},
                    },
                },
            )

            connector = doctor.validate_connector_registry(
                data_dir / "warehouse" / "connector_registry.json",
            )
            policy = doctor.validate_mcp_policy(data_dir / "mcp" / "tool_policy.json")
            skills = doctor.validate_skill_registry(
                data_dir / "skill_registry" / "registry.json",
                data_dir / "agent_templates",
            )

            self.assertEqual(connector["status"], "fail")
            self.assertEqual(policy["status"], "fail")
            self.assertEqual(skills["status"], "fail")
            self.assertIn("external_write_enabled", connector["summary"])
            self.assertIn("confirmation", policy["summary"])
            self.assertIn("template", skills["summary"])

    def test_optional_python_deps_do_not_make_doctor_warn(self) -> None:
        doctor = load_doctor()
        required = {"duckdb", "langgraph", "openpyxl"}

        def fake_find_spec(name: str) -> object | None:
            return object() if name in required else None

        with patch.object(doctor.importlib.util, "find_spec", side_effect=fake_find_spec):
            result = doctor.check_python_deps()

        self.assertEqual(result["status"], "ok")
        self.assertIn("pyarrow", result["metadata"]["optional_missing"])

    def test_frontend_check_accepts_npm_when_pnpm_is_not_on_path(self) -> None:
        doctor = load_doctor()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "agent-chat-ui" / "node_modules").mkdir(parents=True)
            (root / "agent-chat-ui" / "package.json").write_text("{}", encoding="utf-8")

            def fake_which(name: str) -> str | None:
                return f"/usr/bin/{name}" if name in {"node", "npm"} else None

            with patch.object(doctor.shutil, "which", side_effect=fake_which):
                result = doctor.check_node_frontend(root)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metadata"]["pnpm_available"], False)

    def test_desktop_harness_check_marks_windows_only_tools_unavailable_on_macos(self) -> None:
        doctor = load_doctor()

        result = doctor.check_desktop_harness_availability(platform_name="darwin")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metadata"]["platform"], "darwin")
        self.assertEqual(result["metadata"]["harnesses"]["wps_office"], "unavailable")
        self.assertEqual(result["metadata"]["harnesses"]["photoshop"], "unavailable")
        self.assertEqual(result["metadata"]["harnesses"]["illustrator"], "unavailable")
        self.assertIn("Windows worker", result["summary"])

    def test_lightrag_port_check_uses_health_endpoint(self) -> None:
        doctor = load_doctor()

        self.assertEqual(
            doctor.lightrag_health_url({"LIGHTRAG_API_URL": "http://127.0.0.1:9621"}),
            "http://127.0.0.1:9621/health",
        )

    def test_thread_archive_check_reads_values_messages_and_exact_tool_ids(self) -> None:
        doctor = load_doctor()
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            write_json(
                data_dir / "thread_archive" / "bad.json",
                {
                    "values": {
                        "messages": [
                            {
                                "id": "ai1",
                                "type": "ai",
                                "tool_calls": [{"id": "call-1", "name": "demo"}],
                            },
                            {
                                "id": "tool-wrong",
                                "type": "tool",
                                "tool_call_id": "call-other",
                                "content": "wrong response",
                            },
                        ],
                    },
                },
            )

            result = doctor.check_thread_archive(data_dir, {})

        self.assertEqual(result["status"], "warn")
        self.assertIn("missing", result["summary"])
        self.assertIn("mismatched", result["summary"])


if __name__ == "__main__":
    unittest.main()
