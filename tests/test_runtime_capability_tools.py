from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _reload_runtime_modules():
    import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools
    import src.a2a_ecommerce_demo.mcp_governance_tools as mcp_governance_tools
    import src.a2a_ecommerce_demo.runtime_capability_tools as runtime_capability_tools
    import src.a2a_ecommerce_demo.skill_registry_tools as skill_registry_tools

    enterprise_audit_tools = importlib.reload(enterprise_audit_tools)
    skill_registry_tools = importlib.reload(skill_registry_tools)
    mcp_governance_tools = importlib.reload(mcp_governance_tools)
    runtime_capability_tools = importlib.reload(runtime_capability_tools)
    return runtime_capability_tools, skill_registry_tools, mcp_governance_tools, enterprise_audit_tools


class RuntimeCapabilityToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.data_dir = self.root / "data"
        self.wiki_dir = self.root / "wiki"
        self.skill_page = self.wiki_dir / "strategy" / "generic-skill.md"
        self.skill_page.parent.mkdir(parents=True, exist_ok=True)
        self.skill_page.write_text(
            "# 通用经营 Skill\n\n"
            "先查事实层，再列证据和数据缺口。\n",
            encoding="utf-8",
        )
        os.environ["A2A_DATA_DIR"] = str(self.data_dir)
        os.environ["A2A_WIKI_DIR"] = str(self.wiki_dir)
        os.environ["A2A_SKILL_REGISTRY_DIR"] = str(self.data_dir / "skill_registry")
        os.environ["A2A_AGENT_TEMPLATE_DIR"] = str(self.data_dir / "agent_templates")
        os.environ["A2A_MCP_POLICY_PATH"] = str(self.data_dir / "mcp" / "tool_policy.json")
        os.environ["A2A_AUDIT_DIR"] = str(self.data_dir / "audit")
        self.runtime_tools, self.skill_tools, self.mcp_tools, self.audit_tools = _reload_runtime_modules()

        json.loads(
            self.skill_tools.create_agent_skill_from_wiki(
                "strategy/generic-skill.md",
                skill_id="generic_business_skill",
                name="通用经营 Skill",
                tool_allowlist_json=json.dumps(["query_fact_layer", "query_lightrag"], ensure_ascii=False),
                created_by="tester",
            )
        )
        json.loads(self.skill_tools.approve_agent_skill("generic_business_skill", approved_by="tester", decision="approve"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_runtime_capabilities_list_tools_skills_and_mcp_policy_entries(self) -> None:
        payload = json.loads(self.runtime_tools.list_runtime_capabilities())
        capability_ids = {item["capability_id"] for item in payload["capabilities"]}

        self.assertEqual("a2a_runtime_capability_registry_v1", payload["schema"])
        self.assertIn("tool:list_agent_skills", capability_ids)
        self.assertIn("skill:generic_business_skill", capability_ids)
        self.assertIn("mcp:query_erp_live_snapshot", capability_ids)
        self.assertTrue(payload["summary"]["read_only_count"] > 0)
        skill = next(item for item in payload["capabilities"] if item["capability_id"] == "skill:generic_business_skill")
        self.assertEqual("agent_skill", skill["type"])
        self.assertEqual("active", skill["status"])
        self.assertTrue(skill["read_only"])

    def test_runtime_capability_invokes_active_skill_as_prompt_bundle(self) -> None:
        result = json.loads(
            self.runtime_tools.invoke_runtime_capability(
                "skill:generic_business_skill",
                args_json=json.dumps({"user_task": "分析本月库存和销售"}, ensure_ascii=False),
                caller="data_agent",
            )
        )

        self.assertEqual("success", result["status"])
        self.assertEqual("skill_prompt_bundle", result["mode"])
        self.assertEqual("generic_business_skill", result["skill"]["skill_id"])
        self.assertIn("先查事实层", result["prompt"])
        self.assertIn("query_fact_layer", result["tool_allowlist"])
        self.assertEqual("分析本月库存和销售", result["user_task"])

    def test_runtime_capability_surfaces_folder_skill_paths(self) -> None:
        record_path = self.data_dir / "skill_registry" / "skills" / "folder_skill.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "schema": "a2a_agent_skill_v1",
            "skill": {
                "skill_id": "folder_skill",
                "name": "Folder Skill",
                "status": "active",
                "version": 1,
                "source_wiki_path": "wiki/skills/imported/folder_skill.md",
                "source_type": "skill_directory",
                "source_skill_path": "skills/folder-skill",
                "managed_skill_dir": "data/skill_registry/imports/folder_skill",
                "tool_allowlist": ["query_fact_layer"],
                "output_schema": ["summary"],
                "updated_at": "2026-05-22T00:00:00.000Z",
            },
            "versions": [],
            "wiki_content": "Folder Skill prompt body.",
        }
        record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        registry_path = self.data_dir / "skill_registry" / "registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["skills"]["folder_skill"] = {
            "skill_id": "folder_skill",
            "name": "Folder Skill",
            "status": "active",
            "version": 1,
            "source_wiki_path": "wiki/skills/imported/folder_skill.md",
            "source_type": "skill_directory",
            "source_skill_path": "skills/folder-skill",
            "managed_skill_dir": "data/skill_registry/imports/folder_skill",
            "tool_count": 1,
            "updated_at": "2026-05-22T00:00:00.000Z",
            "path": str(record_path),
        }
        registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

        capabilities = json.loads(self.runtime_tools.list_runtime_capabilities(status="active"))
        capability = next(item for item in capabilities["capabilities"] if item["capability_id"] == "skill:folder_skill")
        invoked = json.loads(self.runtime_tools.invoke_runtime_capability("skill:folder_skill", caller="data_agent"))

        self.assertEqual("skill_directory", capability["source_type"])
        self.assertEqual("skills/folder-skill", capability["source_skill_path"])
        self.assertEqual("data/skill_registry/imports/folder_skill", capability["managed_skill_dir"])
        self.assertEqual("skills/folder-skill", invoked["source_skill_path"])
        self.assertEqual("data/skill_registry/imports/folder_skill", invoked["managed_skill_dir"])

    def test_runtime_capability_invokes_read_only_local_tool_and_audits(self) -> None:
        result = json.loads(
            self.runtime_tools.invoke_runtime_capability(
                "tool:list_agent_skills",
                args_json=json.dumps({"status": "active"}, ensure_ascii=False),
                caller="agent_factory_agent",
            )
        )

        self.assertEqual("success", result["status"])
        self.assertEqual("local_tool", result["mode"])
        self.assertEqual("tool:list_agent_skills", result["capability_id"])
        self.assertEqual(["generic_business_skill"], [item["skill_id"] for item in result["result"]["skills"]])

        events = json.loads(self.audit_tools.list_audit_events())["events"]
        self.assertTrue(any(event["event_type"] == "runtime_capability_invoked" for event in events))

    def test_runtime_capability_blocks_local_tool_for_unknown_caller(self) -> None:
        result = json.loads(
            self.runtime_tools.invoke_runtime_capability(
                "tool:list_agent_skills",
                caller="agent",
            )
        )

        self.assertEqual("not_allowed", result["status"])
        self.assertEqual("local_tool_caller_gate", result["mode"])
        self.assertFalse(result["permission"]["allowed"])

    def test_runtime_capability_blocks_write_mcp_as_confirmation_request(self) -> None:
        result = json.loads(
            self.runtime_tools.invoke_runtime_capability(
                "mcp:create_purchase_order",
                args_json=json.dumps({"sku": "SKU-001", "qty": 10}, ensure_ascii=False),
                caller="agent_factory_agent",
            )
        )

        self.assertEqual("confirmation_required", result["status"])
        self.assertTrue(result["requires_confirmation"])
        self.assertEqual("create_purchase_order", result["capability"]["tool_name"])
        self.assertFalse(result["permission"]["allowed"])

    def test_runtime_capability_invokes_read_only_mcp_policy_via_local_handler(self) -> None:
        result = json.loads(
            self.runtime_tools.invoke_runtime_capability(
                "mcp:list_erp_live_query_capabilities",
                caller="data_agent",
            )
        )

        self.assertEqual("success", result["status"])
        self.assertEqual("mcp_local_tool", result["mode"])
        self.assertEqual("mcp:list_erp_live_query_capabilities", result["capability_id"])
        self.assertTrue(result["permission"]["allowed"])
        self.assertTrue(result["result"]["read_only"])

    def test_runtime_capability_can_register_uploaded_mcp_policy_entry(self) -> None:
        registered = json.loads(
            self.runtime_tools.register_runtime_mcp_tool(
                "uploaded_read_tool",
                policy_json=json.dumps(
                    {
                        "description": "用户上传的只读 MCP 工具",
                        "action": "read",
                        "read_only": True,
                        "execution_mode": "mcp_jsonrpc_tool",
                        "mcp_tool_name": "uploaded.echo",
                        "mcp_url_env": "UPLOADED_MCP_URL",
                        "data_sources": ["uploaded_mcp"],
                        "allowed_callers": ["agent", "data_agent"],
                    },
                    ensure_ascii=False,
                ),
                registered_by="tester",
            )
        )

        self.assertEqual("success", registered["status"])
        self.assertEqual("uploaded_read_tool", registered["tool_name"])
        self.assertTrue(registered["policy"]["read_only"])

        capabilities = json.loads(self.runtime_tools.list_runtime_capabilities())
        uploaded = next(item for item in capabilities["capabilities"] if item["capability_id"] == "mcp:uploaded_read_tool")
        self.assertEqual("mcp_api", uploaded["type"])
        self.assertEqual("mcp_jsonrpc_tool", uploaded["execution_mode"])

    def test_runtime_mcp_policy_rejects_string_booleans_and_empty_callers(self) -> None:
        with self.assertRaises(ValueError):
            self.runtime_tools.register_runtime_mcp_tool(
                "bad_bool_tool",
                policy_json=json.dumps(
                    {
                        "read_only": "false",
                        "allowed_callers": ["data_agent"],
                    }
                ),
                registered_by="tester",
            )

        with self.assertRaises(ValueError):
            self.runtime_tools.register_runtime_mcp_tool(
                "bad_caller_tool",
                policy_json=json.dumps(
                    {
                        "read_only": True,
                        "allowed_callers": ["agent"],
                    }
                ),
                registered_by="tester",
            )

    def test_runtime_mcp_jsonrpc_http_errors_are_not_treated_as_success(self) -> None:
        registered = json.loads(
            self.runtime_tools.register_runtime_mcp_tool(
                "uploaded_http_error_tool",
                policy_json=json.dumps(
                    {
                        "description": "只读但 HTTP 失败的 MCP 工具",
                        "action": "read",
                        "read_only": True,
                        "execution_mode": "mcp_jsonrpc_tool",
                        "mcp_tool_name": "uploaded.fail",
                        "mcp_url": "http://127.0.0.1:9/mcp",
                        "data_sources": ["uploaded_mcp"],
                        "allowed_callers": ["data_agent"],
                    },
                    ensure_ascii=False,
                ),
                registered_by="tester",
            )
        )
        self.assertEqual("uploaded_http_error_tool", registered["tool_name"])

        class FakeResponse:
            status_code = 500
            text = "server exploded with token=secret"

            def raise_for_status(self) -> None:
                raise RuntimeError("500 server exploded token=secret")

            def json(self) -> dict[str, object]:
                return {"error": {"message": "server exploded"}}

        class FakeSession:
            def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
                return FakeResponse()

        with patch.object(self.runtime_tools.requests, "Session", return_value=FakeSession()):
            result = json.loads(
                self.runtime_tools.invoke_runtime_capability(
                    "mcp:uploaded_http_error_tool",
                    caller="data_agent",
                )
            )

        self.assertEqual("error", result["status"])
        self.assertIn("***REDACTED***", result["error"])
        events = json.loads(self.audit_tools.list_audit_events())["events"]
        self.assertTrue(
            any(
                event["event_type"] == "runtime_capability_invoked"
                and event["metadata"]["status"] == "failed"
                for event in events
            )
        )


if __name__ == "__main__":
    unittest.main()
