"""
销售单模块单元测试

测试销售单的创建验证、全流程编排逻辑。
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.sales_order import (
    create_trade, create_and_approve_trade, query_trades, check_trade,
    create_manual_order, create_manual_order_and_audit, create_sample_order, batch_audit_trades,
    summarize_pending_trades, list_pending_trade_candidates,
    summarize_pending_shop_orders, batch_audit_pending_trades_by_filter,
    batch_update_pending_trades_logistics_by_filter, prepare_sales_order_batches,
    query_trade_logistics, preflight_sales_order, diagnose_pending_trade_candidates,
    DEFAULT_GOODS_DETAIL_FIELDS, DEFAULT_TRADE_FIELDS,
)
from jackyun_api import JackyunValidationError


class TestCreateTradeValidation(unittest.TestCase):
    """创建销售单参数校验"""

    def test_missing_required_field_raises(self):
        """缺少必填字段抛出校验异常"""
        incomplete_data = {
            "outBillNo": "TEST001",
            "channelCode": "CH001",
            # 缺少 warehouseNo, receiverName 等
        }
        with self.assertRaises(JackyunValidationError):
            create_trade(incomplete_data)

    def test_missing_goods_list_raises(self):
        """缺少货品明细抛出校验异常"""
        data = {
            "outBillNo": "TEST001",
            "channelCode": "CH001",
            "warehouseNo": "WH001",
            "receiverName": "张三",
            "receiverPhone": "13800138000",
            "receiverAddress": "上海市浦东新区XX路XX号",
            # 缺少 goodsList
        }
        with self.assertRaises(JackyunValidationError):
            create_trade(data)


class TestCreateAndApproveFlow(unittest.TestCase):
    """全流程编排测试"""

    @patch("modules.sales_order.finance_check_trade")
    @patch("modules.sales_order.check_trade")
    @patch("modules.sales_order.create_trade")
    def test_full_success_flow(self, mock_create, mock_check, mock_finance):
        """全部成功"""
        mock_create.return_value = {
            "result": {"billNo": "XS20240101001"},
        }
        mock_check.return_value = {"code": "200"}
        mock_finance.return_value = {"code": "200"}

        order_data = {
            "outBillNo": "TEST001",
            "channelCode": "CH001",
            "warehouseNo": "WH001",
            "receiverName": "张三",
            "receiverPhone": "13800138000",
            "receiverAddress": "上海市浦东新区XX路XX号",
            "goodsList": [{"goodsNo": "G001", "qty": 1, "price": 100}],
        }
        result = create_and_approve_trade(order_data)

        self.assertTrue(result["success"])
        self.assertEqual(result["trade_no"], "XS20240101001")
        self.assertEqual(len(result["steps"]), 3)
        for step in result["steps"]:
            self.assertEqual(step["status"], "success")

    @patch("modules.sales_order.create_trade")
    def test_create_failure_stops(self, mock_create):
        """创建失败不继续后续步骤"""
        from jackyun_api import JackyunAPIError
        mock_create.side_effect = JackyunAPIError("渠道编号不存在")

        order_data = {
            "outBillNo": "TEST002",
            "channelCode": "INVALID",
            "warehouseNo": "WH001",
            "receiverName": "李四",
            "receiverPhone": "13900139000",
            "receiverAddress": "北京市朝阳区XX路XX号",
            "goodsList": [{"goodsNo": "G002", "qty": 2, "price": 50}],
        }
        result = create_and_approve_trade(order_data)

        self.assertFalse(result["success"])
        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["steps"][0]["status"], "failed")

    @patch("modules.sales_order.check_trade")
    @patch("modules.sales_order.create_trade")
    def test_check_failure_stops_at_step2(self, mock_create, mock_check):
        """审核失败停在第二步"""
        mock_create.return_value = {
            "result": {"billNo": "XS20240101003"},
        }
        from jackyun_api import JackyunAPIError
        mock_check.side_effect = JackyunAPIError("库存不足")

        order_data = {
            "outBillNo": "TEST003",
            "channelCode": "CH001",
            "warehouseNo": "WH001",
            "receiverName": "王五",
            "receiverPhone": "13700137000",
            "receiverAddress": "广州市天河区XX路XX号",
            "goodsList": [{"goodsNo": "G003", "qty": 1000, "price": 10}],
        }
        result = create_and_approve_trade(order_data)

        self.assertFalse(result["success"])
        self.assertEqual(len(result["steps"]), 2)
        self.assertEqual(result["steps"][0]["status"], "success")
        self.assertEqual(result["steps"][1]["status"], "failed")


class TestQueryTrades(unittest.TestCase):
    """销售单查询测试"""

    def test_default_trade_fields_include_full_goods_detail_fields(self):
        required_fields = [
            "goodsDetail.goodsNo",
            "goodsDetail.goodsName",
            "goodsDetail.specName",
            "goodsDetail.barcode",
            "goodsDetail.sellCount",
            "goodsDetail.unit",
            "goodsDetail.sellPrice",
            "goodsDetail.sellTotal",
            "goodsDetail.cost",
            "goodsDetail.discountTotal",
            "goodsDetail.discountPoint",
            "goodsDetail.taxFee",
            "goodsDetail.shareFavourableFee",
            "goodsDetail.estimateWeight",
            "goodsDetail.goodsMemo",
            "goodsDetail.cateName",
            "goodsDetail.brandName",
            "goodsDetail.goodsTags",
            "goodsDetail.isFit",
            "goodsDetail.isGift",
            "goodsDetail.discountFee",
            "goodsDetail.taxRate",
            "goodsDetail.estimateGoodsVolume",
            "goodsDetail.isPresell",
            "goodsDetail.customerPrice",
            "goodsDetail.customerTotal",
            "goodsDetail.tradeGoodsNo",
            "goodsDetail.tradeGoodsName",
            "goodsDetail.tradeGoodsSpec",
            "goodsDetail.tradeGoodsUnit",
            "goodsDetail.sourceSubtradeNo",
            "goodsDetail.platCode",
            "goodsDetail.platGoodsId",
            "goodsDetail.subTradeId",
        ]
        for field in required_fields:
            self.assertIn(field, DEFAULT_GOODS_DETAIL_FIELDS)
            self.assertIn(field, DEFAULT_TRADE_FIELDS)

    @patch("modules.sales_order.get_client")
    def test_query_by_bill_no(self, mock_get_client):
        """按单号查询"""
        mock_client = MagicMock()
        mock_client.call.return_value = {
            "result": {
                "data": [{"billNo": "XS001", "tradeStatus": 1}],
                "totalCount": 1,
            }
        }
        mock_get_client.return_value = mock_client

        results = query_trades(bill_no="XS001")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["billNo"], "XS001")


class TestAuditAndWarehouseValidation(unittest.TestCase):
    @patch("modules.sales_order.get_client")
    def test_check_trade_calls_audit_pass(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {"code": "200"}
        mock_get_client.return_value = mock_client

        check_trade("YR260413000001")
        self.assertEqual(mock_client.call.call_args.args[0], "oms.trade.audit.pass")
        self.assertEqual(
            mock_client.call.call_args.args[1],
            {"tradeNos": "[\"YR260413000001\"]"},
        )

    @patch("modules.inventory.recommend_batches")
    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_preflight_sales_order_returns_resolved_fields_and_batch_plan(
        self,
        mock_resolve,
        mock_resolve_seller,
        mock_recommend_batches,
    ):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "channelCode": "CH001",
            "companyId": "C1",
            "companyName": "依然电商",
            "warehouseName": "依然-分销组-麦歌仓",
            "warehouseCode": "YRMG04",
            "warehouseId": "W1",
            "logisticName": "麦歌中通",
            "warnings": [],
        }
        mock_resolve_seller.return_value = {"realName": "李雷", "userId": "U1"}
        mock_recommend_batches.return_value = {
            "enough_stock": True,
            "remaining_quantity": 0,
            "recommended_allocation": [{"batch_no": "B001", "quantity": 1}],
            "candidates": [{"batch_no": "B001"}],
        }

        result = preflight_sales_order(
            order_type="JY",
            shop_name="测试渠道",
            receiver_name="张三",
            mobile="13800138000",
            address="上海",
            seller_name="李雷",
            customer_name="样品客户",
            goods_list=[{"goodsNo": "G1", "sellCount": 1}],
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["resolved"]["warehouseCode"], "YRMG04")
        self.assertEqual(result["resolved"]["logisticName"], "麦歌中通")
        self.assertEqual(result["resolved"]["sellerName"], "李雷")
        self.assertTrue(result["batch_summary"]["needs_confirmation"])
        self.assertEqual(result["goods"][0]["batch_recommendation"]["allocation"][0]["batch_no"], "B001")

    @patch("modules.inventory.recommend_batches")
    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_preflight_sales_order_can_allow_stock_shortage_create(
        self,
        mock_resolve,
        mock_resolve_seller,
        mock_recommend_batches,
    ):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "channelCode": "CH001",
            "companyId": "C1",
            "companyName": "依然电商",
            "warehouseName": "测试仓",
            "warehouseCode": "WH001",
            "warehouseId": "W1",
            "logisticName": "测试物流",
            "warnings": [],
        }
        mock_resolve_seller.return_value = {"realName": "李雷", "userId": "U1"}
        mock_recommend_batches.return_value = {
            "enough_stock": False,
            "remaining_quantity": 3,
            "recommended_allocation": [],
            "candidates": [],
        }

        result = preflight_sales_order(
            order_type="manual",
            shop_name="测试渠道",
            receiver_name="张三",
            mobile="13800138000",
            address="上海",
            seller_name="李雷",
            goods_list=[{"goodsNo": "G1", "sellCount": 3, "sellPrice": "10"}],
            allow_stock_shortage=True,
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["batch_summary"]["all_enough_stock"])
        self.assertTrue(result["batch_summary"]["stock_shortage_allowed"])
        self.assertIn("待配批次", result["next_action"])

    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    @patch("modules.warehouse.get_warehouse_by_name")
    @patch("modules.warehouse.validate_warehouse_company")
    def test_manual_order_rejects_other_company_warehouse(
        self,
        mock_validate_company,
        mock_get_warehouse,
        mock_resolve,
    ):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_get_warehouse.return_value = {
            "warehouseId": "W2",
            "warehouseName": "其他公司仓",
        }
        mock_validate_company.return_value = False

        with self.assertRaises(JackyunValidationError):
            create_manual_order(
                shop_name="测试渠道",
                receiver_name="张三",
                mobile="13800138000",
                address="上海",
                goods_list=[{"goodsNo": "G1", "sellCount": 1, "sellPrice": "10"}],
                warehouse_name="其他公司仓",
            )

    @patch("modules.sales_order.check_trade")
    @patch("modules.sales_order.create_manual_order")
    def test_create_manual_order_and_audit(self, mock_create_manual, mock_check_trade):
        mock_create_manual.return_value = {"result": {"billNo": "YR260413000002"}}
        mock_check_trade.return_value = {"code": "200"}

        result = create_manual_order_and_audit(shop_name="测试渠道", seller_name="创建人")
        self.assertEqual(result["trade_no"], "YR260413000002")
        self.assertEqual(mock_check_trade.call_args.args[0], "YR260413000002")

    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.create_trade")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_create_manual_order_keeps_batch_no(self, mock_resolve, mock_create_trade, mock_resolve_seller):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_resolve_seller.return_value = {"name": "创建人"}
        mock_create_trade.return_value = {"result": {"billNo": "YR1"}}
        create_manual_order(
            shop_name="测试渠道",
            receiver_name="张三",
            mobile="13800138000",
            address="上海",
            seller_name="创建人",
            goods_list=[{
                "goodsNo": "G1",
                "sellCount": 1,
                "sellPrice": "10",
                "batchNo": "B001",
            }],
        )
        payload = mock_create_trade.call_args.args[0]
        self.assertEqual(payload["tradeOrderDetails"][0]["batchNo"], "B001")
        self.assertEqual(payload["tradeOrder"]["sellerName"], "创建人")
        self.assertEqual(payload["tradeOrder"]["registerName"], "创建人")

    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.create_trade")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_create_sample_order_sets_memos_and_trade_flag(self, mock_resolve, mock_create_trade, mock_resolve_seller):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseCode": "WH001",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_resolve_seller.return_value = {"name": "创建账号", "realName": "创建人"}
        mock_create_trade.return_value = {"result": {"billNo": "YR1"}}

        create_sample_order(
            shop_name="测试渠道",
            receiver_name="张三",
            mobile="13800138000",
            address="上海",
            seller_name="创建人",
            customer_name="样品客户",
            buyerMemo="买家备注",
            sellerMemo="内部备注",
            goods_list=[{"goodsNo": "G1", "sellCount": 1, "batchNo": "B001"}],
        )

        payload = mock_create_trade.call_args.args[0]
        trade_order = payload["tradeOrder"]
        self.assertEqual(trade_order["buyerMemo"], "买家备注")
        self.assertEqual(trade_order["sellerMemo"], "内部备注")
        self.assertEqual(trade_order["customerName"], "样品客户")
        self.assertEqual(trade_order["sellerName"], "创建人")
        self.assertEqual(trade_order["registerName"], "创建人")
        self.assertEqual(trade_order["warehouseCode"], "WH001")
        self.assertEqual(trade_order["tradeOrderFlags"][0]["flagName"], "样品")
        self.assertEqual(trade_order["tradeOrderFlags"][0]["flagId"], "1108774772244219136")
        self.assertEqual(trade_order["tradeOrderFlags"][0]["flagType"], 1)

    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_create_sample_order_requires_customer_name(self, mock_resolve, mock_resolve_seller):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseCode": "WH001",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_resolve_seller.return_value = {"name": "创建人"}

        with self.assertRaises(JackyunValidationError):
            create_sample_order(
                shop_name="测试渠道",
                receiver_name="张三",
                mobile="13800138000",
                address="上海",
                seller_name="创建人",
                goods_list=[{"goodsNo": "G1", "sellCount": 1, "batchNo": "B001"}],
            )

    @patch("modules.logistics.get_logistics_for_warehouse")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    @patch("modules.warehouse.get_warehouse_by_name")
    @patch("modules.warehouse.validate_warehouse_company")
    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.create_trade")
    def test_manual_warehouse_auto_selects_matching_logistic(
        self,
        mock_create_trade,
        mock_resolve_seller,
        mock_validate_company,
        mock_get_warehouse,
        mock_resolve,
        mock_get_logistics,
    ):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseCode": "WH001",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_get_warehouse.return_value = {
            "warehouseId": "W2",
            "warehouseName": "宝鼎一仓",
            "warehouseCode": "BD01",
        }
        mock_validate_company.return_value = True
        mock_get_logistics.return_value = [
            {"logisticName": "其他物流", "logisticCode": "L0"},
            {"logisticName": "宝鼎中通", "logisticCode": "ZT"},
        ]
        mock_resolve_seller.return_value = {"name": "创建人"}
        mock_create_trade.return_value = {"result": {"billNo": "YR1"}}

        create_manual_order(
            shop_name="测试渠道",
            receiver_name="张三",
            mobile="13800138000",
            address="上海",
            seller_name="创建人",
            warehouse_name="宝鼎一仓",
            goods_list=[{"goodsNo": "G1", "sellCount": 1, "sellPrice": "10", "batchNo": "B001"}],
        )

        payload = mock_create_trade.call_args.args[0]
        self.assertEqual(payload["tradeOrder"]["warehouseName"], "宝鼎一仓")
        self.assertEqual(payload["tradeOrder"]["warehouseCode"], "BD01")
        self.assertEqual(payload["tradeOrder"]["logisticName"], "宝鼎中通")

    @patch("modules.logistics.get_logistics_for_warehouse")
    def test_baoding_warehouse_defaults_to_baoding_zt(self, mock_get_logistics):
        mock_get_logistics.return_value = [
            {"logisticName": "宝鼎顺丰陆运", "logisticCode": "BD14"},
            {"logisticName": "宝鼎中通", "logisticCode": "BDZT"},
        ]

        from modules.sales_order import _select_logistic_for_warehouse

        logistic_name, logistic_code = _select_logistic_for_warehouse("其他-宝鼎样品仓", "W1")

        self.assertEqual(logistic_name, "宝鼎中通")
        self.assertEqual(logistic_code, "BDZT")

    @patch("modules.inventory.recommend_batches")
    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.create_trade")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_create_manual_order_auto_selects_multiple_batches(
        self,
        mock_resolve,
        mock_create_trade,
        mock_resolve_seller,
        mock_recommend_batches,
    ):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseCode": "WH001",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_resolve_seller.return_value = {"name": "创建人"}
        mock_create_trade.return_value = {"result": {"billNo": "YR1"}}
        mock_recommend_batches.return_value = {
            "recommended_allocation": [
                {"batch_no": "A001", "quantity": 3, "production_date": "2026-04-01", "expiration_date": "2027-04-01"},
                {"batch_no": "B001", "quantity": 3, "production_date": "2026-04-02", "expiration_date": "2027-04-02"},
            ],
            "enough_stock": True,
            "remaining_quantity": 0,
        }

        create_manual_order(
            shop_name="测试渠道",
            receiver_name="张三",
            mobile="13800138000",
            address="上海",
            seller_name="创建人",
            goods_list=[{
                "goodsNo": "G1",
                "sellCount": 6,
                "sellPrice": "10",
                "sellTotal": "60",
            }],
        )

        payload = mock_create_trade.call_args.args[0]
        detail = payload["tradeOrderDetails"][0]
        self.assertEqual(len(detail["batchList"]), 2)
        self.assertEqual(detail["batchList"][0]["batchNo"], "A001")
        self.assertEqual(detail["batchList"][1]["batchNo"], "B001")

    @patch("modules.inventory.recommend_batches")
    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.create_trade")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_create_manual_order_accepts_zero_price_for_gift(
        self,
        mock_resolve,
        mock_create_trade,
        mock_resolve_seller,
        mock_recommend_batches,
    ):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseCode": "WH001",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_resolve_seller.return_value = {"name": "创建人"}
        mock_create_trade.return_value = {"result": {"billNo": "YR1"}}
        mock_recommend_batches.return_value = {
            "recommended_allocation": [{"batch_no": "GIFT001", "quantity": 2}],
            "enough_stock": True,
            "remaining_quantity": 0,
        }

        create_manual_order(
            shop_name="测试渠道",
            receiver_name="张三",
            mobile="13800138000",
            address="上海",
            seller_name="创建人",
            goods_list=[{
                "goodsNo": "G1",
                "sellCount": 2,
                "sellPrice": "0",
                "sellTotal": "0",
                "isGift": 1,
            }],
        )

        payload = mock_create_trade.call_args.args[0]
        self.assertEqual(payload["tradeOrderDetails"][0]["sellPrice"], "0.0")
        self.assertEqual(payload["tradeOrderDetails"][0]["sellTotal"], "0.0")

    @patch("modules.inventory.recommend_batches")
    @patch("modules.sales_order._resolve_confirmed_seller")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_create_manual_order_rejects_incorrect_amount(self, mock_resolve, mock_resolve_seller, mock_recommend_batches):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseCode": "WH001",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_resolve_seller.return_value = {"name": "创建人"}
        mock_recommend_batches.return_value = {
            "recommended_allocation": [{"batch_no": "B001", "quantity": 2}],
            "enough_stock": True,
            "remaining_quantity": 0,
        }

        with self.assertRaises(JackyunValidationError):
            create_manual_order(
                shop_name="测试渠道",
                receiver_name="张三",
                mobile="13800138000",
                address="上海",
                seller_name="创建人",
                goods_list=[{
                    "goodsNo": "G1",
                    "sellCount": 2,
                    "sellPrice": "10",
                    "sellTotal": "15",
                }],
            )

    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_create_manual_order_requires_confirmed_seller(self, mock_resolve):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseCode": "WH1",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }

        with self.assertRaises(JackyunValidationError):
            create_manual_order(
                shop_name="测试渠道",
                receiver_name="张三",
                mobile="13800138000",
                address="上海",
                goods_list=[{"goodsNo": "G1", "sellCount": 1, "sellPrice": "10"}],
            )

    @patch("modules.sales_order.check_trade")
    def test_batch_audit_trades(self, mock_check_trade):
        mock_check_trade.return_value = {
            "result": {
                "data": {
                    "success": False,
                    "failedResults": [{"tradeNo": "YR2", "msg": "处理失败"}],
                }
            }
        }
        result = batch_audit_trades(["YR1", "YR2"], operator="测试001")
        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["fail_count"], 1)

    @patch("modules.sales_order.query_trades")
    def test_summarize_pending_trades(self, mock_query_trades):
        mock_query_trades.return_value = [
            {"goodsDetail": [{"sellCount": "2"}, {"sellCount": "3"}]},
            {"goodsDetail": [{"sellCount": "1"}]},
        ]
        result = summarize_pending_trades()
        self.assertEqual(result["trade_count"], 2)
        self.assertEqual(result["goods_count"], 6)

    @patch("modules.stock_doc.query_outbound_logistics_by_bill_no")
    @patch("modules.sales_order.query_trade_by_no")
    def test_query_trade_logistics_uses_two_step_flow(self, mock_query_trade, mock_query_outbound):
        mock_query_trade.return_value = {
            "tradeNo": "YR260413002043",
            "billNo": "YR260413002043",
            "tradeStatus": 3010,
            "tradeStatusExplain": "已发货",
            "warehouseName": "韩国申通仓",
            "logisticName": "依然物流",
            "logisticCode": "YR100",
        }
        mock_query_outbound.return_value = {
            "found": True,
            "bill_no": "YR260413002043",
            "logistic_no": "SF123456789CN",
            "logistic_name": "顺丰速运",
            "goodsdoc_no": "CK202604130001",
            "goods_list": [],
            "raw": {"billNo": "YR260413002043"},
        }

        result = query_trade_logistics("YR260413002043")

        self.assertTrue(result["trade_exists"])
        self.assertTrue(result["logistic_found"])
        self.assertEqual(result["bill_no"], "YR260413002043")
        self.assertEqual(result["logistic_no"], "SF123456789CN")
        self.assertEqual(mock_query_outbound.call_args.args[0], "YR260413002043")

    @patch("modules.inventory.recommend_batches")
    @patch("modules.sales_order.resolve_channel_warehouse_logistics")
    def test_prepare_sales_order_batches_uses_resolved_warehouse(
        self,
        mock_resolve,
        mock_recommend_batches,
    ):
        mock_resolve.return_value = {
            "success": True,
            "channelName": "测试渠道",
            "companyId": "C1",
            "companyName": "依然美妆",
            "warehouseName": "默认仓",
            "warehouseCode": "WH001",
            "warehouseId": "W1",
            "logisticName": "默认物流",
        }
        mock_recommend_batches.return_value = {
            "warehouse_code": "WH001",
            "goods_no": "G1",
            "required_quantity": 2,
            "candidates": [{"batch_no": "B001", "available_quantity": 5}],
            "recommended_allocation": [{"batch_no": "B001", "quantity": 2}],
            "enough_stock": True,
            "remaining_quantity": 0,
        }

        result = prepare_sales_order_batches(
            shop_name="测试渠道",
            goods_list=[{"goodsNo": "G1", "sellCount": 2}],
        )

        self.assertEqual(result["warehouse_code"], "WH001")
        self.assertTrue(result["all_enough_stock"])
        self.assertEqual(result["goods_recommendations"][0]["line_index"], 1)
        self.assertEqual(mock_recommend_batches.call_args.kwargs["warehouse_code"], "WH001")

    @patch("modules.sales_order.query_trades")
    def test_list_pending_trade_candidates(self, mock_query_trades):
        mock_query_trades.return_value = [
            {
                "tradeNo": "YR1",
                "onlineTradeNo": "ON1",
                "shopName": "渠道A",
                "goodsDetail": [
                    {"goodsNo": "G1", "goodsName": "货品1", "sellCount": "2"},
                    {"goodsNo": "G2", "goodsName": "货品2", "sellCount": "1"},
                ],
            }
        ]
        result = list_pending_trade_candidates()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["goodsCount"], 3)
        self.assertEqual(result[0]["onlineTradeNo"], "ON1")

    @patch("modules.sales_order.list_pending_trade_candidates")
    def test_summarize_pending_shop_orders(self, mock_list_candidates):
        mock_list_candidates.return_value = [
            {"tradeNo": "YR1", "onlineTradeNo": "ON1", "goodsCount": 2},
            {"tradeNo": "YR2", "onlineTradeNo": "ON2", "goodsCount": 3},
            {"tradeNo": "YR3", "onlineTradeNo": "ON2", "goodsCount": 1},
        ]
        result = summarize_pending_shop_orders()
        self.assertEqual(result["trade_count"], 3)
        self.assertEqual(result["goods_count"], 6)
        self.assertEqual(result["online_trade_count"], 2)

    @patch("modules.inventory.recommend_batches")
    @patch("modules.sales_order.query_trades")
    def test_diagnose_pending_trade_candidates_groups_block_reasons(
        self,
        mock_query_trades,
        mock_recommend_batches,
    ):
        mock_query_trades.return_value = [
            {
                "tradeNo": "YR1",
                "onlineTradeNo": "ON1",
                "shopName": "渠道A",
                "warehouseName": "仓A",
                "warehouseCode": "WH001",
                "logisticName": "物流A",
                "receiverName": "张三",
                "mobile": "13800138000",
                "address": "上海",
                "goodsDetail": [{"goodsNo": "G1", "goodsName": "货品1", "sellCount": "2"}],
            },
            {
                "tradeNo": "YR2",
                "onlineTradeNo": "ON2",
                "shopName": "渠道A",
                "warehouseName": "",
                "logisticName": "",
                "receiverName": "李四",
                "mobile": "13900139000",
                "address": "杭州",
                "goodsDetail": [{"goodsNo": "", "goodsName": "无效货品", "sellCount": "1"}],
            },
        ]
        mock_recommend_batches.return_value = {
            "enough_stock": False,
            "remaining_quantity": 1,
            "recommended_allocation": [],
            "candidates": [],
        }

        result = diagnose_pending_trade_candidates(shop_name="渠道A")

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["blocked_count"], 2)
        self.assertEqual(result["issue_summary"]["stock_shortage"], 1)
        self.assertEqual(result["issue_summary"]["missing_warehouse"], 1)
        self.assertEqual(result["issue_summary"]["invalid_goods"], 1)

    @patch("modules.sales_order.batch_audit_trades")
    @patch("modules.sales_order.list_pending_trade_candidates")
    def test_batch_audit_pending_trades_by_filter(
        self,
        mock_list_candidates,
        mock_batch_audit,
    ):
        mock_list_candidates.return_value = [
            {"tradeNo": "YR1", "onlineTradeNo": "ON1", "goodsCount": 2},
            {"tradeNo": "YR2", "onlineTradeNo": "ON2", "goodsCount": 1},
        ]
        mock_batch_audit.return_value = {"total": 2, "success_count": 2, "fail_count": 0}
        result = batch_audit_pending_trades_by_filter(shop_name="渠道A", operator="测试001")
        self.assertEqual(result["success_count"], 2)
        self.assertEqual(len(result["matched_trades"]), 2)

    @patch("modules.sales_order.update_logistics_warehouse")
    @patch("modules.sales_order.list_pending_trade_candidates")
    def test_batch_update_pending_trades_logistics_by_filter(
        self,
        mock_list_candidates,
        mock_update_logistics,
    ):
        mock_list_candidates.return_value = [
            {"tradeNo": "YR1", "onlineTradeNo": "ON1"},
            {"tradeNo": "YR2", "onlineTradeNo": "ON2"},
        ]
        mock_update_logistics.return_value = {"code": "200"}
        result = batch_update_pending_trades_logistics_by_filter(
            shop_name="渠道A",
            warehouse_name="韩国韵达仓",
            logistic_name="韩国韵达-韵达国际",
        )
        self.assertEqual(result["updated_count"], 2)
        self.assertEqual(len(result["update_list"]), 2)


if __name__ == "__main__":
    unittest.main()
