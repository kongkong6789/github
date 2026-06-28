from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path


class EnterpriseAuditToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_env = {
            "A2A_DATA_DIR": os.environ.get("A2A_DATA_DIR"),
            "A2A_AUDIT_DIR": os.environ.get("A2A_AUDIT_DIR"),
        }
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        os.environ["A2A_DATA_DIR"] = str(self.root / "data")
        os.environ["A2A_AUDIT_DIR"] = str(self.root / "data" / "audit")

        import src.a2a_ecommerce_demo.enterprise_audit_tools as enterprise_audit_tools

        self.audit_tools = importlib.reload(enterprise_audit_tools)

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_record_audit_event_redacts_sensitive_keys_even_plain_values(self) -> None:
        payload = json.loads(
            self.audit_tools.record_audit_event(
                "secret_test",
                metadata={
                    "password": "plain",
                    "nested": {
                        "authorization": "Bearer raw",
                        "safe": "value",
                    },
                },
            )
        )

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("plain", serialized)
        self.assertNotIn("Bearer raw", serialized)
        self.assertIn("***REDACTED***", serialized)
        self.assertEqual(payload["event"]["metadata"]["nested"]["safe"], "value")


if __name__ == "__main__":
    unittest.main()
