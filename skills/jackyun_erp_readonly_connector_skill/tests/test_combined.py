import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.combined import close_combined, create_combined, query_combined


class TestCombined(unittest.TestCase):
    @patch("modules.combined.get_client")
    def test_query_combined_uses_v2(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"result": {"data": [{"goodsNo": "A1"}]}}
        mock_get_client.return_value = mock_client
        result = query_combined(goods_no="A1")
        self.assertEqual(result[0]["goodsNo"], "A1")
        self.assertEqual(mock_client.call.call_args.args[0], "erp.combined.get.v2")

    @patch("modules.combined.get_client")
    def test_create_combined_v2(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        create_combined({"billNo": "CB1"})
        self.assertEqual(mock_client.call.call_args.args[0], "erp.combind.create.v2")

    @patch("modules.combined.get_client")
    def test_close_combined(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        close_combined(bill_no="CB1", reason="test")
        self.assertEqual(mock_client.call.call_args.args[0], "erp.combined.close")


if __name__ == "__main__":
    unittest.main()
