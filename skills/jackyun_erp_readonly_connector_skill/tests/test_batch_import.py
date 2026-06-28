import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.batch_import import (
    auto_map_columns,
    batch_create_orders,
    group_orders_from_rows,
    normalize_order_type,
    validate_row,
)


class TestBatchImportOfficialTemplate(unittest.TestCase):
    def test_official_template_columns_map_with_parentheses_and_marker(self):
        df = pd.DataFrame(columns=[
            "网店订单号",
            "收货人",
            "手机",
            "省份",
            "市（区）",
            "区（县）",
            "收货地址",
            "发货仓库",
            "客服备注",
            "客户备注",
            "销售渠道名称",
            "货品名称",
            "条码",
            "规格",
            "批次号",
            "数量",
            "单价",
            "金额",
            "物流公司",
            "业务员",
            "标记",
        ])

        mapping = auto_map_columns(df)

        self.assertEqual(mapping["网店订单号"], "onlineTradeNo")
        self.assertEqual(mapping["收货人"], "receiverName")
        self.assertEqual(mapping["市（区）"], "city")
        self.assertEqual(mapping["区（县）"], "district")
        self.assertEqual(mapping["发货仓库"], "warehouseName")
        self.assertEqual(mapping["销售渠道名称"], "shopName")
        self.assertEqual(mapping["标记"], "orderType")
        self.assertEqual(mapping["批次号"], "batchNo")

    def test_group_orders_preserves_order_and_goods_fields(self):
        rows = [
            {
                "_row_index": 2,
                "onlineTradeNo": "202605061625JY",
                "shopName": "正品-面护部-Arencia",
                "receiverName": "小杨",
                "mobile": "13712147367",
                "address": "广东省深圳市南山区",
                "warehouseName": "正品-宝鼎售后仓",
                "logisticName": "宝鼎中通",
                "sellerName": "李雷",
                "customerName": "样品客户",
                "buyerMemo": "客户备注",
                "sellerMemo": "客服备注",
                "goodsNo": "8809562191889",
                "goodsName": "ARENCIA红思慕雪精华30 50g",
                "specName": "默认规格",
                "batchNo": "B001",
                "sellCount": "1",
                "sellPrice": "0",
                "sellTotal": "0",
                "orderType": "样品",
            }
        ]

        orders = group_orders_from_rows(rows)

        self.assertEqual(len(orders), 1)
        order = orders[0]["order"]
        goods = orders[0]["goods_list"][0]
        self.assertEqual(order["onlineTradeNo"], "202605061625JY")
        self.assertEqual(order["sellerName"], "李雷")
        self.assertEqual(order["customerName"], "样品客户")
        self.assertEqual(order["buyerMemo"], "客户备注")
        self.assertEqual(order["orderType"], "JY")
        self.assertEqual(goods["batchNo"], "B001")
        self.assertEqual(goods["unit"], "Pcs")

    def test_sample_rows_require_employee_and_customer(self):
        errors = validate_row({
            "shopName": "正品-面护部-Arencia",
            "receiverName": "小杨",
            "mobile": "13712147367",
            "address": "广东省深圳市南山区",
            "goodsNo": "8809562191889",
            "sellCount": "1",
            "orderType": "样品",
        }, 0)

        self.assertTrue(any("业务员" in error for error in errors))
        self.assertTrue(any("客户名称" in error for error in errors))
        self.assertEqual(normalize_order_type("样品"), "JY")

    @patch("modules.batch_import.query_trade_by_no")
    @patch("modules.batch_import.create_sample_order")
    def test_batch_create_orders_supports_official_template_with_defaults(self, mock_create_sample, mock_query_trade):
        mock_create_sample.return_value = {"result": {"billNo": "YR260506000001"}}
        mock_query_trade.return_value = {"tradeNo": "YR260506000001", "sellerName": "李雷"}
        df = pd.DataFrame([{
            "网店订单号": "202605061625JY",
            "收货人": "小杨",
            "手机": "13712147367",
            "省份": "广东省",
            "市（区）": "深圳市",
            "区（县）": "南山区",
            "收货地址": "广东省深圳市南山区",
            "发货仓库": "正品-宝鼎售后仓",
            "销售渠道名称": "正品-面护部-Arencia",
            "货品名称": "ARENCIA红思慕雪精华30 50g",
            "条码": "8809562191889",
            "规格": "默认规格",
            "批次号": "B001",
            "数量": "1",
            "单价": "0",
            "金额": "0",
            "物流公司": "宝鼎中通",
            "标记": "样品",
        }])

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as handle:
            file_path = handle.name
        try:
            df.to_excel(file_path, index=False)
            report = batch_create_orders(
                file_path,
                default_seller_name="李雷",
                default_customer_name="样品客户",
            )
        finally:
            os.unlink(file_path)

        self.assertEqual(report["success_count"], 1)
        self.assertEqual(report["results"][0]["tradeNo"], "YR260506000001")
        self.assertEqual(report["results"][0]["created_trade"]["sellerName"], "李雷")
        mock_query_trade.assert_called_once_with("YR260506000001")
        kwargs = mock_create_sample.call_args.kwargs
        self.assertEqual(kwargs["seller_name"], "李雷")
        self.assertEqual(kwargs["customer_name"], "样品客户")
        self.assertEqual(kwargs["online_trade_no"], "202605061625JY")
        self.assertEqual(kwargs["warehouse_name"], "正品-宝鼎售后仓")
        self.assertEqual(kwargs["logistic_name"], "宝鼎中通")
        self.assertEqual(kwargs["goods_list"][0]["batchNo"], "B001")

    @patch("modules.batch_import.preflight_sales_order")
    def test_batch_create_orders_dry_run_runs_preflight(self, mock_preflight):
        mock_preflight.return_value = {
            "ok": True,
            "resolved": {
                "warehouseName": "依然-分销组-麦歌仓",
                "warehouseCode": "YRMG04",
                "logisticName": "麦歌中通",
                "sellerName": "李雷",
            },
            "errors": [],
            "warnings": [],
        }
        df = pd.DataFrame([{
            "网店订单号": "202605061625JY",
            "收货人": "小杨",
            "手机": "13712147367",
            "收货地址": "广东省深圳市南山区",
            "发货仓库": "依然-分销组-麦歌仓",
            "销售渠道名称": "正品-面护部-Arencia",
            "条码": "8809562191889",
            "数量": "1",
            "业务员": "李雷",
            "客户名称": "样品客户",
            "标记": "样品",
        }])

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as handle:
            file_path = handle.name
        try:
            df.to_excel(file_path, index=False)
            report = batch_create_orders(file_path, dry_run=True)
        finally:
            os.unlink(file_path)

        self.assertEqual(report["total_orders"], 1)
        self.assertEqual(report["results"][0]["status"], "preview")
        self.assertEqual(report["results"][0]["resolved"]["warehouseCode"], "YRMG04")
        mock_preflight.assert_called_once()

    @patch("modules.batch_import.preflight_sales_order")
    def test_batch_create_orders_dry_run_blocks_failed_preflight(self, mock_preflight):
        mock_preflight.return_value = {
            "ok": False,
            "resolved": {},
            "errors": ["未找到仓库: YRMG04"],
            "warnings": [],
        }
        df = pd.DataFrame([{
            "收货人": "小杨",
            "手机": "13712147367",
            "收货地址": "广东省深圳市南山区",
            "发货仓库": "YRMG04",
            "销售渠道名称": "正品-面护部-Arencia",
            "条码": "8809562191889",
            "数量": "1",
            "业务员": "李雷",
            "客户名称": "样品客户",
            "标记": "样品",
        }])

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as handle:
            file_path = handle.name
        try:
            df.to_excel(file_path, index=False)
            report = batch_create_orders(file_path, dry_run=True)
        finally:
            os.unlink(file_path)

        self.assertEqual(report["fail_count"], 1)
        self.assertEqual(report["results"][0]["status"], "blocked")
        self.assertIn("未找到仓库", report["results"][0]["error"])


if __name__ == "__main__":
    unittest.main()
