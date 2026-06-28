import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.reports import (
    build_goods_sales_analysis_payload,
    build_channel_sales_udr_filters,
    query_channel_sales_summary,
    export_goods_sales_analysis_report,
    goods_sales_analysis_columns,
    query_goods_sales_analysis,
    query_user_defined_report,
)
from modules.workflows import run_goods_sales_analysis_workflow


class TestGoodsSalesAnalysisReport(unittest.TestCase):
    @patch("modules.channel.get_channel_by_name")
    @patch("modules.reports.get_client")
    def test_query_goods_sales_analysis_resolves_channel_and_paginates(self, mock_get_client, mock_get_channel):
        mock_get_channel.return_value = {
            "channelId": "SHOP001",
            "channelName": "渠道A",
            "companyName": "依然电商",
        }
        mock_client = MagicMock()
        mock_client.call.side_effect = [
            {
                "result": {
                    "data": [
                        {"shopName": "渠道A", "goodsNo": "G1", "goodsQty": 2, "goodsAmtCompanyCurrency": 100},
                    ]
                }
            },
            {"result": {"data": []}},
        ]
        mock_get_client.return_value = mock_client

        result = query_goods_sales_analysis(month="2026-05", shop_names=["渠道A"], page_size=1)

        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["request"]["startTime"], "2026-05")
        self.assertEqual(result["request"]["endTime"], "2026-05")
        self.assertEqual(result["request"]["timeType"], 2)
        self.assertEqual(result["request"]["shopIds"], "SHOP001")
        self.assertEqual(result["request"]["summaryType"], "channel,goods")
        self.assertEqual(mock_client.call.call_args_list[0].args[0], "birc.report.needauth.goodsMultiDimensionalAnalysis")

    def test_goods_sales_analysis_columns_include_all_official_fields(self):
        columns = goods_sales_analysis_columns()
        for field in (
            "goodsQty",
            "goodsAmtCompanyCurrency",
            "sellAmtCompanyCurrency",
            "deliveryGoodsQty",
            "refundGoodsAmtCompanyCurrency",
            "grossProfitRateCompanyCurrencyShow",
        ):
            self.assertIn(field, columns)

    @patch("modules.channel.get_channel_by_name")
    @patch("modules.reports.get_client")
    def test_export_goods_sales_analysis_report_csv(self, mock_get_client, mock_get_channel):
        mock_get_channel.return_value = {"channelId": "SHOP001", "channelName": "渠道A"}
        mock_client = MagicMock()
        mock_client.call.side_effect = [
            {
                "result": {
                    "data": {
                        "rows": [
                            {"shopName": "渠道A", "goodsNo": "G1", "goodsName": "货品1", "goodsQty": 2},
                        ]
                    }
                }
            },
            {"result": {"data": {"rows": []}}},
        ]
        mock_get_client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "goods_sales.csv")
            result = export_goods_sales_analysis_report(
                output_path=output_path,
                month="2026-05",
                shop_names="渠道A",
            )
            self.assertEqual(result["row_count"], 1)
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, encoding="utf-8-sig") as handle:
                content = handle.read()
            self.assertIn("销售渠道", content)
            self.assertIn("货品编号", content)
            self.assertIn("渠道A", content)

    @patch("modules.channel.get_channel_by_name")
    @patch("modules.reports.get_client")
    def test_query_channel_sales_summary_simplifies_quantity_amount(self, mock_get_client, mock_get_channel):
        mock_get_channel.return_value = {"channelId": "SHOP001", "channelName": "渠道A"}
        mock_client = MagicMock()
        mock_client.call.side_effect = [
            {
                "result": {
                    "data": [
                        {
                            "shopName": "渠道A",
                            "goodsNo": "G1",
                            "goodsName": "货品1",
                            "goodsQty": 2,
                            "goodsAmtCompanyCurrency": 100,
                        }
                    ]
                }
            },
            {"result": {"data": []}},
        ]
        mock_get_client.return_value = mock_client

        result = query_channel_sales_summary(month="2026-05", shop_names="渠道A", dimension="channel_goods")

        self.assertEqual(result["summaryType"], "channel,goods")
        self.assertEqual(result["total_goods_qty"], 2)
        self.assertEqual(result["total_goods_amount"], 100)
        self.assertEqual(result["summary_rows"][0]["goodsNo"], "G1")

    def test_build_channel_sales_udr_filters(self):
        filter_text = build_channel_sales_udr_filters(
            start_time="2026-05-12",
            end_time="2026-05-12",
            shop_ids="SHOP001,SHOP002",
            trade_status="6000",
        )

        self.assertIn('"key": "timeType"', filter_text)
        self.assertIn('"value": "consign_time"', filter_text)
        self.assertIn('"key": "date_key"', filter_text)
        self.assertIn("2026-05-12,2026-05-12", filter_text)
        self.assertIn("SHOP001,SHOP002", filter_text)

    @patch("modules.reports.get_client")
    def test_query_user_defined_report_parses_json_string_rows(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.side_effect = [
            {"result": {"data": {"data": '[{"渠道名称":"渠道A","销售数量":"2","销售额":"100"}]'}}},
            {"result": {"data": {"data": "[]"}}},
        ]
        mock_get_client.return_value = mock_client

        result = query_user_defined_report(
            report_id="159",
            filters={"date_key": "2026-05-12,2026-05-12"},
            page_size=1,
        )

        self.assertEqual(result["method"], "udr.openapi.userdefinedreport")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["items"][0]["渠道名称"], "渠道A")
        self.assertEqual(mock_client.call.call_args_list[0].args[1]["pageSize"], "1")

    @patch("modules.channel.search_channels_by_keywords")
    @patch("modules.reports.get_client")
    def test_channel_sales_summary_falls_back_to_udr(self, mock_get_client, mock_search_channels):
        mock_search_channels.return_value = [
            {"channelId": "SHOP001", "channelName": "分销组A", "companyName": "依然电商"}
        ]
        mock_client = MagicMock()
        mock_client.call.side_effect = [
            {"result": {"data": []}},
            {"result": {"data": {"data": '[{"渠道名称":"分销组A","销售数量":"3","销售额":"99"}]'}}},
            {"result": {"data": {"data": "[]"}}},
        ]
        mock_get_client.return_value = mock_client

        result = query_channel_sales_summary(
            start_time="2026-05-12",
            end_time="2026-05-12",
            channel_include_keyword="分销组",
            dimension="channel",
            udr_report_id="159",
        )

        self.assertEqual(result["source_method"], "udr.openapi.userdefinedreport")
        self.assertEqual(result["total_goods_qty"], 3)
        self.assertEqual(result["total_goods_amount"], 99)
        self.assertIn("已自动改用吉智BI自定义报表查询", "\n".join(result["warnings"]))

    @patch("modules.channel.search_channels_by_keywords")
    def test_build_goods_sales_analysis_payload_resolves_channel_keyword(self, mock_search_channels):
        mock_search_channels.return_value = [
            {
                "channelId": "SHOP001",
                "channelName": "分销组渠道A",
                "channelCode": "C001",
                "companyName": "依然电商",
                "channelDepartName": "分销组",
            }
        ]

        payload, resolved = build_goods_sales_analysis_payload(
            start_time="2026-05-12",
            end_time="2026-05-12",
            channel_include_keyword="分销组",
            summary_types="channel",
            trade_status="6000",
        )

        self.assertEqual(payload["shopIds"], "SHOP001")
        self.assertEqual(payload["summaryType"], "channel")
        self.assertEqual(payload["tradeStatus"], "6000")
        self.assertEqual(resolved[0]["shopName"], "分销组渠道A")

    @patch("modules.reports.export_goods_sales_analysis_report")
    def test_goods_sales_analysis_workflow_export(self, mock_export):
        mock_export.return_value = {
            "output_path": "x.csv",
            "row_count": 2,
            "resolved_shops": [{"shopName": "渠道A"}],
        }

        result = run_goods_sales_analysis_workflow(output_path="x.csv", month="2026-05", shop_names=["渠道A"])

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["workflow"], "goods_sales_analysis")
        self.assertEqual(result["data"]["row_count"], 2)
        mock_export.assert_called_once()


if __name__ == "__main__":
    unittest.main()
