from __future__ import annotations

import unittest

from src.a2a_ecommerce_demo.human_approval_tools import (
    build_human_approval_request,
    parse_human_approval_decision,
)


class HumanApprovalToolsTests(unittest.TestCase):
    def test_build_human_approval_request_matches_agent_inbox_schema(self) -> None:
        request = build_human_approval_request(
            action_name="auto_recover_lightrag_timeouts",
            args={"limit": 10, "delete_original_failed": True},
            description="Recover timeout failed LightRAG docs.",
            destructive_effects=["Delete failed records from LightRAG Server."],
        )

        self.assertEqual("auto_recover_lightrag_timeouts", request["action_requests"][0]["name"])
        self.assertEqual(["approve", "reject"], request["review_configs"][0]["allowed_decisions"])
        self.assertEqual(["Delete failed records from LightRAG Server."], request["metadata"]["destructive_effects"])

    def test_parse_human_approval_decision_accepts_frontend_resume_shape(self) -> None:
        approved = parse_human_approval_decision({"decisions": [{"type": "approve"}]})
        rejected = parse_human_approval_decision({"decisions": [{"type": "reject", "message": "not now"}]})
        edited = parse_human_approval_decision(
            {
                "decisions": [
                    {
                        "type": "edit",
                        "edited_action": {
                            "name": "auto_recover_lightrag_timeouts",
                            "args": {"limit": 3},
                        },
                    }
                ]
            }
        )

        self.assertTrue(approved["approved"])
        self.assertFalse(rejected["approved"])
        self.assertEqual("not now", rejected["message"])
        self.assertTrue(edited["approved"])
        self.assertEqual({"limit": 3}, edited["edited_args"])


if __name__ == "__main__":
    unittest.main()

