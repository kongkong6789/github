import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.matching import best_match, normalize_lookup_text


class TestMasterDataMatching(unittest.TestCase):
    def test_normalizes_chinese_and_english_parentheses(self):
        self.assertEqual(
            normalize_lookup_text("ACT-骅韵（UNOVE) "),
            normalize_lookup_text("act-骅韵(UNOVE）"),
        )

    def test_best_match_handles_parentheses_variants(self):
        candidates = [
            {"channelName": "ACT-骅韵（UNOVE)"},
            {"channelName": "依然电商-其他渠道"},
        ]

        result = best_match("ACT-骅韵(UNOVE）", candidates, ("channelName",))

        self.assertEqual(result["channelName"], "ACT-骅韵（UNOVE)")


if __name__ == "__main__":
    unittest.main()

