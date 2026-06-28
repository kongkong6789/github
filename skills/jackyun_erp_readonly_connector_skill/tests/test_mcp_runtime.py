import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.mcp_runtime import _normalize_tool_payload


class TestMcpRuntime(unittest.TestCase):
    def test_normalizes_nested_text_content(self):
        payload = {
            "isError": False,
            "content": [
                {
                    "type": "text",
                    "text": '[{"goodsStockQuantity":[{"goodsNo":"G1","currentQuantity":3}]}]',
                }
            ],
        }

        result = _normalize_tool_payload(payload)

        self.assertEqual(result["code"], "200")
        items = result["result"]["data"]["goodsStockQuantity"]
        self.assertEqual(items[0]["goodsNo"], "G1")


if __name__ == "__main__":
    unittest.main()
