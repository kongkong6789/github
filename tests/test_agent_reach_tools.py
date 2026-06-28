from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import patch


class AgentReachToolsTests(unittest.TestCase):
    def test_status_uses_doctor_json_without_shell(self) -> None:
        from src.a2a_ecommerce_demo import agent_reach_tools

        completed = subprocess.CompletedProcess(
            ["agent-reach", "doctor", "--json"],
            0,
            stdout=json.dumps({"jina": {"status": "ok"}, "youtube": {"status": "warn"}}),
            stderr="",
        )

        with patch.object(agent_reach_tools.subprocess, "run", return_value=completed) as run:
            result = json.loads(agent_reach_tools.agent_reach_get_status())

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["read_only"])
        self.assertEqual(result["summary"]["channel_count"], 2)
        run.assert_called_once()
        args = run.call_args.args[0]
        self.assertEqual(args, ["agent-reach", "doctor", "--json"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_status_reports_unavailable_when_cli_is_missing(self) -> None:
        from src.a2a_ecommerce_demo import agent_reach_tools

        with patch.object(agent_reach_tools.subprocess, "run", side_effect=FileNotFoundError()):
            result = json.loads(agent_reach_tools.agent_reach_get_status())

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["available"])
        self.assertIn("agent-reach", result["next_actions"][0])

    def test_status_masks_sensitive_cli_errors(self) -> None:
        from src.a2a_ecommerce_demo import agent_reach_tools

        completed = subprocess.CompletedProcess(
            ["agent-reach", "doctor", "--json"],
            1,
            stdout="",
            stderr="token=secret-value cookie=session-id Authorization: Bearer abc.def.ghi",
        )

        with patch.object(agent_reach_tools.subprocess, "run", return_value=completed):
            result = json.loads(agent_reach_tools.agent_reach_get_status())

        self.assertEqual(result["status"], "error")
        self.assertIn("token=<redacted>", result["error"])
        self.assertIn("cookie=<redacted>", result["error"])
        self.assertIn("Authorization: Bearer <redacted>", result["error"])
        self.assertNotIn("secret-value", result["error"])
        self.assertNotIn("session-id", result["error"])
        self.assertNotIn("abc.def.ghi", result["error"])

    def test_public_web_reader_rejects_non_public_urls(self) -> None:
        from src.a2a_ecommerce_demo.agent_reach_tools import agent_reach_read_public_web

        for url in [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "https://user:pass@example.com/a",
            "http://localhost:3000/private",
            "http://127.0.0.1:8000/private",
            "http://10.0.0.2/private",
        ]:
            with self.subTest(url=url):
                result = json.loads(agent_reach_read_public_web(url))
                self.assertEqual(result["status"], "error")
                self.assertIn("http", result["message"].lower())

    def test_public_web_reader_fetches_jina_reader_url_and_truncates(self) -> None:
        from src.a2a_ecommerce_demo import agent_reach_tools

        captured: dict[str, str] = {}

        def fake_fetch(url: str, *, timeout_seconds: int, max_bytes: int) -> str:
            captured["url"] = url
            captured["timeout"] = str(timeout_seconds)
            captured["max_bytes"] = str(max_bytes)
            return "标题\n" + ("内容" * 20)

        with (
            patch.object(agent_reach_tools, "_dns_public_error", return_value=None),
            patch.object(agent_reach_tools, "_fetch_text", side_effect=fake_fetch),
        ):
            result = json.loads(agent_reach_tools.agent_reach_read_public_web("https://example.com/post", max_chars=12))

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["read_only"])
        self.assertEqual(captured["url"], "https://r.jina.ai/https://example.com/post")
        self.assertGreater(int(captured["max_bytes"]), 12)
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["content"]), 12)

    def test_public_search_uses_fixed_mcporter_call_without_shell(self) -> None:
        from src.a2a_ecommerce_demo import agent_reach_tools

        completed = subprocess.CompletedProcess(
            ["mcporter"],
            0,
            stdout='{"results":[{"title":"A","url":"https://example.com"}]}',
            stderr="",
        )

        with patch.object(agent_reach_tools.subprocess, "run", return_value=completed) as run:
            result = json.loads(agent_reach_tools.agent_reach_search_public_sources('新品 "趋势"', limit=3))

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["limit"], 3)
        self.assertIn("results", result)
        args = run.call_args.args[0]
        self.assertEqual(args[:2], ["mcporter", "call"])
        self.assertIn('新品 "趋势"', args[2])
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_video_transcript_rejects_non_video_hosts_and_private_dns(self) -> None:
        from src.a2a_ecommerce_demo import agent_reach_tools

        non_video = json.loads(agent_reach_tools.agent_reach_read_video_transcript("https://example.com/watch/1"))
        self.assertEqual(non_video["status"], "error")
        self.assertIn("视频", non_video["message"])

        with patch.object(
            agent_reach_tools.socket,
            "getaddrinfo",
            return_value=[(0, 0, 0, "", ("127.0.0.1", 0))],
        ):
            with patch.object(agent_reach_tools.subprocess, "run") as run:
                private_dns = json.loads(
                    agent_reach_tools.agent_reach_read_video_transcript("https://youtube.com/watch?v=1")
                )

        self.assertEqual(private_dns["status"], "error")
        self.assertIn("公开互联网地址", private_dns["message"])
        run.assert_not_called()

    def test_logged_in_social_never_reads_local_browser_cookies(self) -> None:
        from src.a2a_ecommerce_demo import agent_reach_tools

        with patch.object(agent_reach_tools.subprocess, "run") as run:
            result = json.loads(
                agent_reach_tools.agent_reach_read_logged_in_social(
                    platform="x",
                    query_or_url="https://x.com/example/status/1",
                    requested_by="knowledge_agent",
                )
            )

        self.assertEqual(result["status"], "confirmation_required")
        self.assertTrue(result["read_only"])
        self.assertIn("专用账号", result["message"])
        run.assert_not_called()
