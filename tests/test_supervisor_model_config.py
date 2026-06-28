from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage


class SupervisorModelConfigTests(unittest.TestCase):
    def test_deepseek_v4_pro_disables_thinking_mode_for_tool_calls(self) -> None:
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["OPENAI_MODEL"] = "deepseek-v4-pro"
        os.environ["OPENAI_BASE_URL"] = "https://api.deepseek.com"

        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        supervisor_app = importlib.reload(supervisor_app)

        kwargs = supervisor_app._chat_openai_kwargs()
        self.assertEqual({"thinking": {"type": "disabled"}}, kwargs["extra_body"])
        self.assertTrue(kwargs["disable_streaming"])
        self.assertGreaterEqual(kwargs["max_retries"], 3)
        self.assertGreaterEqual(kwargs["timeout"], 120)

    def test_non_deepseek_models_keep_default_chat_kwargs(self) -> None:
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["OPENAI_MODEL"] = "gpt-4.1-mini"
        os.environ["OPENAI_BASE_URL"] = "https://api.openai.com/v1"

        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        supervisor_app = importlib.reload(supervisor_app)

        self.assertNotIn("extra_body", supervisor_app._chat_openai_kwargs())

    def test_existing_knowledge_analysis_does_not_start_background_workflow(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        self.assertFalse(
            supervisor_app._is_friendly_background_request(
                "基于当前知识库和 DuckDB 数据，分析 UNOVE 5/6 月销售提升决策，给优先级和执行清单。"
            )
        )

    def test_business_analysis_without_explicit_raw_work_does_not_start_background_workflow(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        self.assertFalse(
            supervisor_app._is_friendly_background_request("基于所有数据分析 5/6 月 UNOVE 销售提升决策。")
        )
        self.assertFalse(
            supervisor_app._is_friendly_background_request(
                "基于所有已有数据，分析 5/6 月 UNOVE 销售提升决策，输出优先级、执行清单、关键依据、风险和数据缺口。"
            )
        )

    def test_background_workflow_tool_rejects_existing_data_analysis_goal(self) -> None:
        import src.a2a_ecommerce_demo.task_delegation_tools as task_delegation_tools

        result = task_delegation_tools.start_company_workflow_task(
            "基于所有已有数据，分析 5/6 月 UNOVE 销售提升决策，输出优先级、执行清单、关键依据、风险和数据缺口。"
        )

        self.assertEqual("rejected", json.loads(result)["status"])

    def test_new_raw_material_request_still_uses_background_workflow(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        self.assertTrue(
            supervisor_app._is_friendly_background_request("我刚放了 raw 资料，帮我整理入库并同步知识库")
        )
        import src.a2a_ecommerce_demo.task_delegation_tools as task_delegation_tools

        self.assertTrue(
            task_delegation_tools._should_start_background_company_workflow("我刚放了 raw 资料，帮我整理入库并同步知识库")
        )

    def test_model_input_sanitizer_drops_orphan_tool_messages(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        sanitized = supervisor_app._sanitize_messages_for_llm(
            [
                HumanMessage(content="先前问题"),
                ToolMessage(content="orphan", tool_call_id="missing-call", name="demo_tool"),
                HumanMessage(content="继续分析"),
            ]
        )

        self.assertEqual(["human", "human"], [message.type for message in sanitized])
        self.assertEqual("继续分析", sanitized[-1].content)

    def test_model_input_sanitizer_drops_persisted_system_injection_messages(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        sanitized = supervisor_app._sanitize_messages_for_llm(
            [
                SystemMessage(content="Active Skill matched for this user request."),
                HumanMessage(content="使用吉客云查询下unove当前全渠道库存信息"),
            ]
        )

        self.assertEqual(["human"], [message.type for message in sanitized])
        self.assertEqual("使用吉客云查询下unove当前全渠道库存信息", sanitized[0].content)

    def test_model_input_sanitizer_repairs_missing_tool_response_after_ai_tool_call(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        sanitized = supervisor_app._sanitize_messages_for_llm(
            [
                HumanMessage(content="查库存"),
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call-1", "name": "query_inventory", "args": {}}],
                ),
                AIMessage(content="后续总结"),
            ]
        )

        self.assertEqual(["human", "ai", "tool", "ai"], [message.type for message in sanitized])
        self.assertEqual("call-1", sanitized[2].tool_call_id)
        self.assertIn("Synthetic", sanitized[2].content)

    def test_model_input_sanitizer_repairs_openai_role_assistant_tool_calls(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        sanitized = supervisor_app._sanitize_messages_for_llm(
            [
                {"role": "user", "content": "查库存"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "call-1", "name": "query_inventory", "args": {}}],
                },
                {"role": "assistant", "content": "后续总结"},
            ]
        )

        self.assertEqual(["user", "assistant", "tool", "assistant"], [supervisor_app._message_type(message) for message in sanitized])
        self.assertEqual("call-1", sanitized[2].tool_call_id)

    def test_explicit_jackyun_current_inventory_request_injects_live_erp_guard(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        hook_result = supervisor_app._sanitize_model_input_hook(
            {"messages": [HumanMessage(content="使用吉客云查询下unove当前全渠道库存信息")]}
        )

        llm_messages = hook_result["llm_input_messages"]
        self.assertEqual("system", llm_messages[0].type)
        self.assertIn("query_erp_live_snapshot", llm_messages[0].content)
        self.assertIn("handoff/transfer 成功消息不是数据证据", llm_messages[0].content)
        self.assertIn("大贸=麦歌仓", llm_messages[0].content)
        self.assertIn("不得编造 UNV-001", llm_messages[0].content)
        self.assertIn("costPrice/采购价缺失或覆盖不全只影响库存金额", llm_messages[0].content)
        self.assertIn("query_erp_live_snapshot 查询 kingdee_erp 的 supplier_procurement_terms", llm_messages[0].content)
        self.assertIn("FTaxPrice 只能作为", llm_messages[0].content)
        self.assertIn("batch_inventory/erp.batchstockquantity.get", llm_messages[0].content)
        self.assertIn("cost_reference.selected_value", llm_messages[0].content)
        self.assertIn("不得当成全品牌统一采购价", llm_messages[0].content)
        self.assertIn("brand_expansion.summary", llm_messages[0].content)
        self.assertIn("yesterdayQuantity/threedayQuantity/weekQuantity/stockOutuantity", llm_messages[0].content)
        self.assertIn("不得写成完整销售订单明细", llm_messages[0].content)
        self.assertIn("query_jackyun_channel_sales_summary", llm_messages[0].content)
        self.assertEqual("human", llm_messages[-1].type)

    def test_wecom_url_request_injects_runtime_doc_url_guidance(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        hook_result = supervisor_app._sanitize_model_input_hook(
            {
                "messages": [
                    HumanMessage(
                        content="读取企业微信智能表日销表 https://doc.weixin.qq.com/smartsheet/s3_doc?tab=sheetB"
                    )
                ]
            }
        )

        llm_messages = hook_result["llm_input_messages"]
        self.assertIn("doc.weixin.qq.com/smartsheet", llm_messages[0].content)
        self.assertIn("doc_url", llm_messages[0].content)
        self.assertIn("不依赖固定 source_id", llm_messages[0].content)
        self.assertIn("渠道编码", llm_messages[0].content)
        self.assertIn("不得把 DuckDB", llm_messages[0].content)

    def test_live_erp_guard_uses_configured_jackyun_warehouse_scope_rules(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        previous = os.environ.get("A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH")
        with tempfile.TemporaryDirectory() as tempdir:
            rules_path = Path(tempdir) / "warehouse-scope.json"
            rules_path.write_text(
                json.dumps(
                    {
                        "schema": "a2a_jackyun_warehouse_scope_rules_v1",
                        "rules": [
                            {
                                "business_scope": "大贸",
                                "canonical_warehouse": "华东大贸仓",
                                "keywords": ["华东大贸"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.environ["A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH"] = str(rules_path)
            try:
                hook_result = supervisor_app._sanitize_model_input_hook(
                    {"messages": [HumanMessage(content="使用吉客云查询下unove当前全渠道库存信息")]}
                )
            finally:
                if previous is None:
                    os.environ.pop("A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH", None)
                else:
                    os.environ["A2A_JACKYUN_WAREHOUSE_SCOPE_RULES_PATH"] = previous

        self.assertIn("大贸=华东大贸仓", hook_result["llm_input_messages"][0].content)
        self.assertIn("华东大贸", hook_result["llm_input_messages"][0].content)

    def test_live_erp_guard_does_not_trigger_for_local_existing_data_analysis(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        hook_result = supervisor_app._sanitize_model_input_hook(
            {"messages": [HumanMessage(content="基于当前知识库和 DuckDB 数据，分析 UNOVE 5/6 月销售提升决策")]}
        )

        self.assertNotIn(
            "handoff/transfer 成功消息不是数据证据",
            "\n".join(str(message.content) for message in hook_result["llm_input_messages"] if message.type == "system"),
        )

    def test_tool_catalog_includes_p4_sensitive_field_guardrail_tools(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        catalog = supervisor_app._tool_catalog()

        for tool_name in [
            "summarize_sensitive_fields_from_registry",
            "classify_sensitive_fields",
            "mask_sensitive_record",
            "record_sensitive_field_access",
        ]:
            self.assertIn(tool_name, catalog)

    def test_tool_catalog_includes_p14_evidence_graph_tools(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        catalog = supervisor_app._tool_catalog()

        for tool_name in [
            "build_evidence_graph",
            "list_evidence_graph_nodes",
            "list_evidence_graph_edges",
        ]:
            self.assertIn(tool_name, catalog)

    def test_tool_catalog_includes_p15_wiki_lifecycle_tools(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        catalog = supervisor_app._tool_catalog()

        for tool_name in [
            "ensure_wiki_knowledge_scaffold",
            "refresh_wiki_index",
            "append_wiki_log_event",
            "normalize_legacy_wiki_pages",
            "lint_wiki_knowledge_base",
            "archive_decision_to_wiki",
            "register_wiki_claim_evidence",
            "generate_wiki_review_questions",
        ]:
            self.assertIn(tool_name, catalog)

    def test_tool_catalog_includes_prompt_referenced_workflow_tools(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        self.assertIn("run_fact_layer_registration_task", supervisor_app._tool_catalog())

    def test_tool_catalog_includes_jackyun_channel_sales_summary(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        self.assertIn("query_jackyun_channel_sales_summary", supervisor_app._tool_catalog())

    def test_tool_catalog_includes_runtime_capability_tools(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        catalog = supervisor_app._tool_catalog()

        self.assertIn("list_runtime_capabilities", catalog)
        self.assertIn("invoke_runtime_capability", catalog)
        self.assertIn("register_runtime_mcp_tool", catalog)

    def test_tool_catalog_includes_agent_reach_tools(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        catalog = supervisor_app._tool_catalog()

        for tool_name in [
            "agent_reach_get_status",
            "agent_reach_read_public_web",
            "agent_reach_search_public_sources",
            "agent_reach_read_video_transcript",
            "agent_reach_read_logged_in_social",
        ]:
            self.assertIn(tool_name, catalog)

    def test_top_supervisor_safe_read_tools_include_live_data_and_exclude_writes(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app

        tool_names = set(supervisor_app.TOP_SUPERVISOR_SAFE_READ_TOOLS)

        for tool_name in [
            "summarize_business_data",
            "query_fact_layer",
            "query_erp_live_snapshot",
            "query_jackyun_channel_sales_summary",
            "query_wecom_smartsheet_records",
            "list_runtime_capabilities",
            "invoke_runtime_capability",
            "search_wiki",
            "read_wiki_page",
            "query_lightrag",
        ]:
            self.assertIn(tool_name, tool_names)

        for tool_name in [
            "sync_connector_dataset",
            "sync_wecom_smartsheet_snapshot",
            "request_mcp_write_approval",
            "save_decision_report",
            "append_decision_note",
        ]:
            self.assertNotIn(tool_name, tool_names)

    def test_top_supervisor_safe_tools_resolve_only_read_only_registry_entries(self) -> None:
        import src.a2a_ecommerce_demo.supervisor_app as supervisor_app
        from src.a2a_ecommerce_demo.agent_tool_registry import TOOL_REGISTRY

        catalog = supervisor_app._tool_catalog()
        tools = supervisor_app._top_supervisor_safe_tools(catalog)
        resolved_names = {tool.__name__ for tool in tools}

        self.assertIn("query_erp_live_snapshot", resolved_names)
        self.assertIn("query_jackyun_channel_sales_summary", resolved_names)
        self.assertIn("query_wecom_smartsheet_records", resolved_names)
        self.assertNotIn("sync_wecom_smartsheet_snapshot", resolved_names)
        self.assertTrue(all(TOOL_REGISTRY[name].read_only for name in resolved_names))


if __name__ == "__main__":
    unittest.main()
