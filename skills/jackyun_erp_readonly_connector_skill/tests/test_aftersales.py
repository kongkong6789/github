import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.aftersales import call_aftersales_api, create_refund, query_disorders


class TestAfterSales(unittest.TestCase):
    @patch("modules.aftersales.get_client")
    def test_refund_create_method(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        create_refund({"refundNo": "R1"})
        self.assertEqual(mock_client.call.call_args.args[0], "ass-business.refund.create")

    @patch("modules.aftersales.get_client")
    def test_disorder_list_v2_method(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"result": {"data": []}}
        mock_get_client.return_value = mock_client
        query_disorders(v2=True, pageIndex=0)
        self.assertEqual(mock_client.call.call_args.args[0], "ass-business.disorder.listDisorderInfoV2")

    @patch("modules.aftersales.get_client")
    def test_generic_method_resolution(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        call_aftersales_api("legacy_refund_cancel", {"refundNo": "R1"})
        self.assertEqual(mock_client.call.call_args.args[0], "ass.refund.cancel")


if __name__ == "__main__":
    unittest.main()
