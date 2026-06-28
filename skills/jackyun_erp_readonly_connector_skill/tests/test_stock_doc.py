import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jackyun_api import JackyunValidationError
from modules.stock_doc import create_doc_out, create_stock_out_apply, query_outbound_logistics_by_bill_no


class TestStockDocLogisticsHelpers(unittest.TestCase):
    @patch("modules.stock_doc.query_doc_out")
    def test_query_outbound_logistics_by_bill_no_returns_first_match(self, mock_query_doc_out):
        mock_query_doc_out.return_value = [{
            "billNo": "YR260413002043",
            "goodsdocNo": "CK202604130001",
            "logisticName": "顺丰速运",
            "logisticNo": "SF123456789CN",
            "goodsDocDetailList": [{"goodsNo": "G1", "goodsName": "商品1", "quantity": 1}],
        }]

        result = query_outbound_logistics_by_bill_no("YR260413002043")

        self.assertTrue(result["found"])
        self.assertEqual(result["bill_no"], "YR260413002043")
        self.assertEqual(result["logistic_no"], "SF123456789CN")
        self.assertEqual(result["goodsdoc_no"], "CK202604130001")

    @patch("modules.stock_doc.query_doc_out")
    def test_query_outbound_logistics_by_bill_no_handles_missing_record(self, mock_query_doc_out):
        mock_query_doc_out.return_value = []

        result = query_outbound_logistics_by_bill_no("YR260413002043")

        self.assertFalse(result["found"])
        self.assertEqual(result["logistic_no"], "")

    def test_query_outbound_logistics_by_bill_no_requires_bill_no(self):
        with self.assertRaises(JackyunValidationError):
            query_outbound_logistics_by_bill_no("")


class TestStockDocCreate(unittest.TestCase):
    @patch("modules.inventory.recommend_batches")
    @patch("modules.warehouse.get_warehouse_by_name")
    @patch("modules.stock_doc.get_client")
    def test_create_doc_out_auto_selects_multiple_batches(self, mock_get_client, mock_get_warehouse, mock_recommend_batches):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_get_warehouse.return_value = {"warehouseCode": "WH001", "warehouseName": "上海成品仓"}
        mock_recommend_batches.return_value = {
            "recommended_allocation": [
                {"batch_no": "A001", "quantity": 2, "production_date": "2026-04-01", "expiration_date": "2027-04-01"},
                {"batch_no": "B001", "quantity": 1, "production_date": "2026-04-02", "expiration_date": "2027-04-02"},
            ],
            "enough_stock": True,
            "remaining_quantity": 0,
        }

        create_doc_out({
            "inouttype": 201,
            "warehouseName": "上海成品仓",
            "goodsDocDetailList": [{"goodsNo": "G1", "goodsName": "商品1", "quantity": 3}],
        })

        payload = mock_client.call.call_args.args[1]
        detail = payload["goodsDocDetailList"][0]
        self.assertEqual(len(detail["batchList"]), 2)
        self.assertEqual(detail["batchList"][0]["batchNo"], "A001")
        self.assertEqual(detail["batchList"][1]["batchNo"], "B001")

    @patch("modules.inventory.recommend_batches")
    @patch("modules.goods.resolve_goods_for_transfer")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_name")
    @patch("modules.stock_doc.get_client")
    def test_create_stock_out_apply_uses_applicant_and_auto_batches(
        self,
        mock_get_client,
        mock_get_warehouse,
        mock_resolve_user,
        mock_resolve_goods,
        mock_recommend_batches,
    ):
        mock_client = MagicMock()
        mock_client.call.return_value = {"result": {"data": {"outNo": "OUT001"}}}
        mock_get_client.return_value = mock_client
        mock_get_warehouse.return_value = {
            "warehouseCode": "WH001",
            "warehouseName": "上海成品仓",
            "warehouseCompanyCode": "C01",
        }
        mock_resolve_user.return_value = {
            "realName": "张三",
            "departCode": "D01",
            "mainDepartName": "运营部",
        }
        mock_resolve_goods.return_value = {
            "record": {"goodsNo": "G1", "goodsName": "商品1", "skuBarcode": "BAR1", "outSkuCode": "OUTSKU1"}
        }
        mock_recommend_batches.return_value = {
            "recommended_allocation": [
                {"batch_no": "B001", "quantity": 2, "production_date": "2026-04-01", "expiration_date": "2027-04-01"},
            ],
            "enough_stock": True,
        }

        create_stock_out_apply({
            "outType": 204,
            "warehouseName": "上海成品仓",
            "applyUserName": "张三",
            "goodsList": [{"goodsNo": "G1", "skuCount": 2}],
        })

        method, payload = mock_client.call.call_args.args
        self.assertEqual(method, "erp.storage.stockoutcreate")
        bizdata = payload["bizdata"]
        self.assertEqual(bizdata["applyUserName"], "张三")
        self.assertEqual(bizdata["operator"], "张三")
        self.assertEqual(bizdata["applyDepartCode"], "D01")
        self.assertEqual(bizdata["outWarehouseCode"], "WH001")
        detail = bizdata["stockOutDetailViews"][0]
        self.assertEqual(detail["unitName"], "Pcs")
        self.assertEqual(detail["skuBarCode"], "BAR1")
        self.assertEqual(detail["batchList"][0]["batchNo"], "B001")

    def test_create_stock_out_apply_requires_explicit_applicant(self):
        with self.assertRaises(JackyunValidationError):
            create_stock_out_apply({
                "outType": 204,
                "warehouseCode": "WH001",
                "goodsList": [{"skuBarcode": "BAR1", "skuCount": 1}],
            })


if __name__ == "__main__":
    unittest.main()
