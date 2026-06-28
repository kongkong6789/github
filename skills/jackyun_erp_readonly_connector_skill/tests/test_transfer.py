"""
Tests for transfer helpers.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jackyun_api import JackyunValidationError
from modules.goods import resolve_goods_for_transfer
from modules.transfer import (
    SAME_COMPANY_CHANNEL,
    create_transfer,
    prepare_transfer_batches,
    prepare_transfer_payload,
    quick_create_transfer,
)


BASE_FIELD4 = "target-channel"
OUT_WAREHOUSE_NAME = "OUT-WH"
IN_WAREHOUSE_NAME = "IN-WH"
OUT_CONTACT_NAME = "out contact"
IN_CONTACT_NAME = "in contact"
OUT_ADDRESS = "Shanghai Pudong Road 1"
IN_ADDRESS = "Shanghai Minhang Road 2"
UNIT_NAME = "Pcs"


def make_base_payload():
    return {
        "allocateType": 0,
        "applyUserId": 1,
        "applyUserName": "Tester",
        "departCode": "D01",
        "companyCode": "P01",
        "outWarehouseCode": "WH001",
        "intWarehouseCode": "WH002",
        "field4": BASE_FIELD4,
        "stockAllocateDetailViews": [
            {
                "unitName": UNIT_NAME,
                "skuCount": 3,
                "isCertified": 1,
                "skuBarcode": "BAR001",
            }
        ],
    }


def make_user():
    return {
        "userId": 1,
        "realName": "Tester",
        "departCode": "D01",
        "mainDepartId": "DP01",
        "mainDepartName": "Test Department",
    }


def make_out_warehouse():
    return {
        "warehouseCode": "WH001",
        "warehouseName": OUT_WAREHOUSE_NAME,
        "warehouseCompanyCode": "P01",
        "linkMan": OUT_CONTACT_NAME,
        "tel": "13800000001",
        "address": OUT_ADDRESS,
    }


def make_in_warehouse():
    return {
        "warehouseCode": "WH002",
        "warehouseName": IN_WAREHOUSE_NAME,
        "warehouseCompanyCode": "P02",
        "linkMan": IN_CONTACT_NAME,
        "tel": "13800000002",
        "address": IN_ADDRESS,
    }


def make_out_company():
    return {
        "companyCode": "P01",
        "currencyCode": "CNY",
    }


def make_in_company():
    return {
        "companyCode": "P02",
        "currencyCode": "KRW",
    }


class TestCreateTransferValidation(unittest.TestCase):

    def test_requires_header_fields(self):
        with self.assertRaises(JackyunValidationError):
            create_transfer({
                "field4": BASE_FIELD4,
                "stockAllocateDetailViews": [
                    {"unitName": UNIT_NAME, "skuCount": 1, "isCertified": 1, "skuBarcode": "B"}
                ],
            })

    def test_requires_details(self):
        payload = make_base_payload()
        payload.pop("stockAllocateDetailViews")
        with self.assertRaises(JackyunValidationError):
            create_transfer(payload)

    def test_requires_positive_qty(self):
        payload = make_base_payload()
        payload["stockAllocateDetailViews"][0]["skuCount"] = 0
        with self.assertRaises(JackyunValidationError):
            create_transfer(payload)

    def test_requires_barcode_or_outer_sku(self):
        payload = make_base_payload()
        payload["stockAllocateDetailViews"][0].pop("skuBarcode")
        with self.assertRaises(JackyunValidationError):
            create_transfer(payload)

    def test_cross_company_requires_price(self):
        payload = make_base_payload()
        payload["allocateType"] = 1
        with self.assertRaises(JackyunValidationError):
            create_transfer(payload)

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_same_company_calls_allocate_create(self, mock_get_warehouse, mock_resolve_user, mock_get_client, mock_get_company):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]

        result = create_transfer(make_base_payload())

        self.assertEqual(result["code"], "200")
        self.assertEqual(mock_client.call.call_args.args[0], "erp.allocate.create")

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_quick_create_sets_default_open_allocate_type(self, mock_get_warehouse, mock_resolve_user, mock_get_client, mock_get_company):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company(), make_in_company()]

        payload = make_base_payload()
        payload["allocateType"] = 1
        payload["companyCode"] = "P02"
        payload["stockAllocateDetailViews"][0]["skuPrice"] = 12

        result = quick_create_transfer(payload)

        self.assertEqual(result["code"], "200")
        self.assertEqual(mock_client.call.call_args.args[0], "erp.allocate.quick.create")
        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["openAllocateType"], 1)
        self.assertEqual(sent_payload["stockAllocateDetailViews"][0]["totalAmount"], 36.0)

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_custom_fields_are_passed_through(self, mock_get_warehouse, mock_resolve_user, mock_get_client, mock_get_company):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]

        payload = make_base_payload()
        payload["field1"] = "CNY"
        payload["field3"] = SAME_COMPANY_CHANNEL
        payload["stockAllocateDetailViews"][0]["detailField1"] = "D1"

        create_transfer(payload)

        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["field1"], "CNY")
        self.assertEqual(sent_payload["field3"], SAME_COMPANY_CHANNEL)
        self.assertEqual(sent_payload["stockAllocateDetailViews"][0]["detailField1"], "D1")

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_in_channel_prefix_is_removed(self, mock_get_warehouse, mock_resolve_user, mock_get_client, mock_get_company):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]

        payload = make_base_payload()
        payload["field4"] = "ACT-target-channel"

        create_transfer(payload)

        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["field4"], BASE_FIELD4)

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_batch_no_alias_is_preserved(self, mock_get_warehouse, mock_resolve_user, mock_get_client, mock_get_company):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]

        payload = make_base_payload()
        payload["stockAllocateDetailViews"][0]["batch_no"] = "B001"

        create_transfer(payload)

        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["stockAllocateDetailViews"][0]["batchNo"], "B001")

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_contacts_are_filled_from_warehouses(self, mock_get_warehouse, mock_resolve_user, mock_get_client, mock_get_company):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]

        create_transfer(make_base_payload())

        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["senderName"], OUT_CONTACT_NAME)
        self.assertEqual(sent_payload["receiverName"], IN_CONTACT_NAME)
        self.assertEqual(sent_payload["senderMobile"], "13800000001")
        self.assertEqual(sent_payload["receiverMobile"], "13800000002")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["send"], OUT_CONTACT_NAME)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["senderName"], OUT_CONTACT_NAME)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["outContactName"], OUT_CONTACT_NAME)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["receive"], IN_CONTACT_NAME)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["receiverName"], IN_CONTACT_NAME)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["intContactName"], IN_CONTACT_NAME)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["sendTel"], "13800000001")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["sendPhone"], "13800000001")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["senderMobile"], "13800000001")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["receiveTel"], "13800000002")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["receivePhone"], "13800000002")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["receiverMobile"], "13800000002")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["sendAddress"], OUT_ADDRESS)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["senderAddress"], OUT_ADDRESS)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["receiveAddress"], IN_ADDRESS)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["receiverAddress"], IN_ADDRESS)

    @patch("modules.dictionary.ensure_dictionary_item")
    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_reason_is_checked_and_memo_is_sent(
        self,
        mock_get_warehouse,
        mock_resolve_user,
        mock_get_client,
        mock_get_company,
        mock_ensure_dictionary_item,
    ):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]
        mock_ensure_dictionary_item.return_value = {"status": "exists", "item": {"text": "门店调货"}}

        payload = make_base_payload()
        payload["reason"] = "门店调货"
        payload["remark"] = "客户提供的备注"

        create_transfer(payload)

        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["reason"], "门店调货")
        self.assertEqual(sent_payload["memo"], "客户提供的备注")
        mock_ensure_dictionary_item.assert_called_once()

    @patch("modules.dictionary.ensure_dictionary_item")
    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_reason_and_memo_aliases_are_sent(
        self,
        mock_get_warehouse,
        mock_resolve_user,
        mock_get_client,
        mock_get_company,
        mock_ensure_dictionary_item,
    ):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]
        mock_ensure_dictionary_item.return_value = {"status": "exists", "item": {"text": "运营调拨"}}

        payload = make_base_payload()
        payload.pop("reason", None)
        payload["transfer_reason"] = "运营调拨"
        payload["transfer_memo"] = "用户填写的调拨备注"

        create_transfer(payload)

        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["reason"], "运营调拨")
        self.assertEqual(sent_payload["memo"], "用户填写的调拨备注")
        mock_ensure_dictionary_item.assert_called_once()

    @patch("modules.goods.resolve_goods_for_transfer")
    def test_resolved_goods_unit_is_forced_to_pcs(self, mock_resolve_goods):
        from modules.transfer import _resolve_goods_detail

        mock_resolve_goods.return_value = {
            "record": {
                "goodsNo": "G1",
                "goodsName": "货品1",
                "skuBarcode": "B1",
                "unitName": "件",
            },
            "source": "erp.storage.goodslist",
            "match": "goodsNo_exact",
        }

        detail = _resolve_goods_detail({"goodsNo": "G1", "skuCount": 2, "unitName": "箱"})

        self.assertEqual(detail["unitName"], "Pcs")

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_stock_allocate_express_info_preserves_explicit_values(self, mock_get_warehouse, mock_resolve_user, mock_get_client, mock_get_company):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]

        payload = make_base_payload()
        payload["senderName"] = "manual sender"
        payload["stockAllocateExpressInfo"] = {
            "senderMobile": "13900000000",
        }

        create_transfer(payload)

        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["senderName"], "manual sender")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["send"], "manual sender")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["senderName"], "manual sender")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["sendTel"], "13900000000")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["sendPhone"], "13900000000")
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["sendAddress"], OUT_ADDRESS)
        self.assertEqual(sent_payload["stockAllocateExpressInfo"]["receive"], IN_CONTACT_NAME)

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_contacts_require_names_and_addresses_from_payload_or_warehouse(self, mock_get_warehouse, mock_resolve_user, mock_get_company):
        mock_resolve_user.return_value = make_user()
        out_warehouse = make_out_warehouse()
        in_warehouse = make_in_warehouse()
        out_warehouse["linkMan"] = ""
        out_warehouse["address"] = ""
        in_warehouse["linkMan"] = ""
        in_warehouse["address"] = ""
        mock_get_warehouse.side_effect = [out_warehouse, in_warehouse]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]

        with self.assertRaises(JackyunValidationError):
            create_transfer(make_base_payload())

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_company_code_must_match_in_or_out_company(self, mock_get_warehouse, mock_resolve_user, mock_get_company):
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company(), {"companyCode": "P99", "currencyCode": "USD"}]

        payload = make_base_payload()
        payload["companyCode"] = "P99"

        with self.assertRaises(JackyunValidationError):
            create_transfer(payload)

    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_currency_is_filled_from_company(self, mock_get_warehouse, mock_resolve_user, mock_get_client, mock_get_company):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]

        payload = make_base_payload()
        payload.pop("field1", None)

        create_transfer(payload)

        sent_payload = mock_client.call.call_args.args[1]
        self.assertEqual(sent_payload["outCurrencyCode"], "CNY")
        self.assertEqual(sent_payload["inCurrencyCode"], "KRW")
        self.assertEqual(sent_payload["field1"], "CNY")

    @patch("modules.inventory.recommend_batches")
    @patch("modules.transfer._resolve_goods_detail")
    @patch("modules.transfer._get_company_by_code")
    @patch("modules.transfer.get_client")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_auto_batch_selection_builds_batch_list(
        self,
        mock_get_warehouse,
        mock_resolve_user,
        mock_get_client,
        mock_get_company,
        mock_resolve_goods_detail,
        mock_recommend_batches,
    ):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]
        mock_resolve_goods_detail.side_effect = (
            lambda item: {**item, "goodsNo": item.get("goodsNo"), "unitName": UNIT_NAME, "isCertified": 1}
        )
        mock_recommend_batches.return_value = {
            "recommended_allocation": [
                {"batch_no": "B001", "quantity": 2, "production_date": "2026-04-01", "expiration_date": "2027-04-01"},
                {"batch_no": "B002", "quantity": 1, "production_date": "2026-04-02", "expiration_date": "2027-04-02"},
            ],
            "enough_stock": True,
        }

        payload = make_base_payload()
        payload["stockAllocateDetailViews"][0]["goodsNo"] = "G1"

        create_transfer(payload)

        sent_payload = mock_client.call.call_args.args[1]
        detail = sent_payload["stockAllocateDetailViews"][0]
        self.assertEqual(detail["unitName"], "Pcs")
        self.assertEqual(detail["isBatch"], 1)
        self.assertEqual(len(detail["batchList"]), 2)
        self.assertEqual(detail["batchList"][0]["batchNo"], "B001")
        self.assertEqual(sent_payload["batchControlByWarehouse"], 1)

    @patch("modules.inventory.recommend_batches")
    @patch("modules.transfer._resolve_goods_detail")
    @patch("modules.transfer._get_company_by_code")
    @patch("modules.user.resolve_user_identity")
    @patch("modules.warehouse.get_warehouse_by_code")
    def test_prepare_transfer_payload_allows_stock_shortage_without_batch_list(
        self,
        mock_get_warehouse,
        mock_resolve_user,
        mock_get_company,
        mock_resolve_goods_detail,
        mock_recommend_batches,
    ):
        mock_resolve_user.return_value = make_user()
        mock_get_warehouse.side_effect = [make_out_warehouse(), make_in_warehouse()]
        mock_get_company.side_effect = [make_out_company(), make_in_company()]
        mock_resolve_goods_detail.side_effect = (
            lambda item: {**item, "goodsNo": item.get("goodsNo"), "unitName": UNIT_NAME, "isCertified": 1}
        )
        mock_recommend_batches.return_value = {
            "recommended_allocation": [],
            "enough_stock": False,
            "remaining_quantity": 3,
        }

        payload = make_base_payload()
        payload["stockAllocateDetailViews"][0]["goodsNo"] = "G1"

        normalized, summary = prepare_transfer_payload(payload, allow_stock_shortage=True)

        detail = normalized["stockAllocateDetailViews"][0]
        self.assertEqual(detail["isBatch"], 1)
        self.assertNotIn("batchList", detail)
        self.assertNotIn("batch_allocation_status", detail)
        self.assertEqual(summary["batches"][0]["status"], "stock_shortage_pending")
        self.assertEqual(summary["batches"][0]["shortage_quantity"], 3)


class TestGoodsFallback(unittest.TestCase):
    @patch("modules.goods.query_goods_sku_search")
    @patch("modules.goods.query_goods")
    def test_resolve_goods_for_transfer_falls_back_to_sku_search(self, mock_query_goods, mock_query_sku_search):
        mock_query_goods.return_value = []
        mock_query_sku_search.return_value = [
            {"goodsNo": "G1", "goodsName": "goods-1", "skuBarcode": "B1", "unitName": UNIT_NAME}
        ]

        result = resolve_goods_for_transfer(goods_no="G1")

        self.assertEqual(result["source"], "erp-goods.goods.sku.search")
        self.assertEqual(result["record"]["goodsNo"], "G1")

    @patch("modules.inventory.recommend_batches")
    def test_prepare_transfer_batches(self, mock_recommend_batches):
        mock_recommend_batches.return_value = {
            "warehouse_code": "WH001",
            "goods_no": "G1",
            "required_quantity": 3,
            "candidates": [{"batch_no": "B001", "available_quantity": 10}],
            "recommended_allocation": [{"batch_no": "B001", "quantity": 3}],
            "enough_stock": True,
            "remaining_quantity": 0,
        }

        result = prepare_transfer_batches(
            out_warehouse_code="WH001",
            goods_list=[{"goodsNo": "G1", "skuCount": 3}],
        )

        self.assertEqual(result["out_warehouse_code"], "WH001")
        self.assertTrue(result["all_enough_stock"])
        self.assertEqual(result["goods_recommendations"][0]["line_index"], 1)
        self.assertEqual(mock_recommend_batches.call_args.kwargs["warehouse_code"], "WH001")


if __name__ == "__main__":
    unittest.main()
