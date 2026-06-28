from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FrontendStartScriptTests(unittest.TestCase):
    def test_macos_frontend_start_script_uses_detached_session_and_health_gate(self) -> None:
        start_script = (PROJECT_ROOT / "scripts" / "start_frontend.sh").read_text(encoding="utf-8")
        stop_script = (PROJECT_ROOT / "scripts" / "stop_frontend.sh").read_text(encoding="utf-8")

        self.assertIn("SCREEN_SESSION", start_script)
        self.assertIn("screen -dmS", start_script)
        self.assertIn("wait_for_http", start_script)
        self.assertIn('rm -rf "${FRONTEND_ROOT}/.next"', start_script)
        self.assertIn("--no-clean-next-cache", start_script)
        self.assertIn("screen -S", stop_script)

    def test_langgraph_backend_wrapper_adds_project_root_to_python_path(self) -> None:
        wrapper = (PROJECT_ROOT / "scripts" / "run_langgraph_backend.py").read_text(encoding="utf-8")

        self.assertIn("PROJECT_ROOT = Path(__file__).resolve().parents[1]", wrapper)
        self.assertIn("sys.path.insert(0, str(PROJECT_ROOT))", wrapper)


if __name__ == "__main__":
    unittest.main()
