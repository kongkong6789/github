import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.finance import call_finance_api, create_fbs_bill, list_accounts


class TestFinance(unittest.TestCase):
    @patch("modules.finance.get_client")
    def test_list_accounts_method(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        list_accounts(pageIndex=0)
        self.assertEqual(mock_client.call.call_args.args[0], "fin.accounts.listall")

    @patch("modules.finance.get_client")
    def test_create_fbs_bill_method(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        create_fbs_bill({"billNo": "F1"})
        self.assertEqual(mock_client.call.call_args.args[0], "fin-fbs.createbill")

    @patch("modules.finance.get_client")
    def test_generic_finance_method(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        call_finance_api("paymentapply_create", {"no": "P1"})
        self.assertEqual(mock_client.call.call_args.args[0], "fin.paymentapply.create")


if __name__ == "__main__":
    unittest.main()
