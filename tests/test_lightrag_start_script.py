from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LightRAGStartScriptTests(unittest.TestCase):
    def test_macos_lightrag_start_script_uses_detached_session_and_health_gate(self) -> None:
        start_script = (PROJECT_ROOT / "scripts" / "start_lightrag_server.sh").read_text(encoding="utf-8")
        stop_script = (PROJECT_ROOT / "scripts" / "stop_lightrag_server.sh").read_text(encoding="utf-8")

        self.assertIn("SCREEN_SESSION", start_script)
        self.assertIn("screen -dmS", start_script)
        self.assertIn("wait_for_http", start_script)
        self.assertIn("/documents/status_counts", start_script)
        self.assertNotIn('/health" "${STARTUP_TIMEOUT_SECONDS}"', start_script)
        self.assertIn("screen -S", stop_script)


if __name__ == "__main__":
    unittest.main()
