from __future__ import annotations

import unittest

from src.a2a_ecommerce_demo.thread_repair_tools import repair_messages


class ThreadRepairToolsTests(unittest.TestCase):
    def test_repair_messages_removes_orphan_tool_and_inserts_missing_response(self) -> None:
        repaired, stats = repair_messages(
            [
                {"id": "h1", "type": "human", "content": "hello"},
                {"id": "orphan", "type": "tool", "tool_call_id": "missing", "content": "bad"},
                {
                    "id": "ai1",
                    "type": "ai",
                    "content": "calling",
                    "tool_calls": [{"id": "call-1", "name": "demo_tool", "args": {}}],
                },
            ]
        )

        self.assertEqual([message["type"] for message in repaired], ["human", "ai", "tool"])
        self.assertEqual(repaired[2]["tool_call_id"], "call-1")
        self.assertEqual(stats.orphan_tool_messages_removed, 1)
        self.assertEqual(stats.missing_tool_responses_inserted, 1)

    def test_repair_messages_handles_openai_role_assistant_tool_calls(self) -> None:
        repaired, stats = repair_messages(
            [
                {"id": "h1", "role": "user", "content": "hello"},
                {
                    "id": "ai1",
                    "role": "assistant",
                    "content": "calling",
                    "tool_calls": [{"id": "call-1", "name": "demo_tool", "args": {}}],
                },
            ]
        )

        self.assertEqual([message.get("role") or message.get("type") for message in repaired], ["user", "assistant", "tool"])
        self.assertEqual(repaired[2]["tool_call_id"], "call-1")
        self.assertEqual(stats.missing_tool_responses_inserted, 1)

    def test_repair_messages_compacts_old_messages_and_truncates_long_text(self) -> None:
        repaired, stats = repair_messages(
            [{"id": str(index), "type": "human", "content": "x" * 20} for index in range(5)],
            max_messages=3,
            max_text_length=8,
        )

        self.assertEqual(len(repaired), 3)
        self.assertEqual(stats.old_messages_compacted, 2)
        self.assertGreaterEqual(stats.overlong_messages_truncated, 5)
        self.assertTrue(str(repaired[-1]["content"]).startswith("xxxxxxxx"))

    def test_repair_messages_redacts_sensitive_urls_and_compacts_tool_rows(self) -> None:
        repaired, stats = repair_messages(
            [
                {
                    "id": "ai1",
                    "type": "ai",
                    "content": "",
                    "tool_calls": [{"id": "call-1", "name": "query_wecom_smartsheet_records", "args": {}}],
                },
                {
                    "id": "tool1",
                    "type": "tool",
                    "tool_call_id": "call-1",
                    "name": "query_wecom_smartsheet_records",
                    "content": (
                        '{"doc_url":"https://doc.weixin.qq.com/smartsheet/s3_doc?scode=secret-code&tab=sheetA",'
                        '"mcp_url":"https://qyapi.weixin.qq.com/mcp/robot-doc?apikey=secret-key",'
                        '"transport":"live_read_only_mcp","source_id":"sales","dataset":"channel_daily_sales",'
                        '"row_count":2,"raw_total_count":2,"schema":["sku","qty"],'
                        '"rows":[{"sku":"A","qty":1},{"sku":"B","qty":2}]}'
                    ),
                },
            ]
        )

        serialized = str(repaired)
        self.assertNotIn("secret-code", serialized)
        self.assertNotIn("secret-key", serialized)
        self.assertNotIn('"rows"', serialized)
        self.assertIn("sample_rows", serialized)
        self.assertGreaterEqual(stats.sensitive_urls_redacted, 2)
        self.assertEqual(stats.large_tool_results_compacted, 1)

    def test_repair_messages_does_not_recount_already_redacted_urls(self) -> None:
        messages = [
            {
                "id": "h1",
                "type": "human",
                "content": "https://doc.weixin.qq.com/smartsheet/s3_doc?scode=%2A%2A%2AREDACTED%2A%2A%2A&tab=sheetA",
            },
            {
                "id": "h2",
                "type": "human",
                "content": "apikey=***REDACTED*** token=***REDACTED***",
            },
        ]

        repaired, stats = repair_messages(messages)

        self.assertEqual(repaired, messages)
        self.assertEqual(stats.sensitive_urls_redacted, 0)


if __name__ == "__main__":
    unittest.main()
