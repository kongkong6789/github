import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.workflows import (
    record_workflow_correction,
    run_delivery_note_export_workflow,
    run_distribution_group_batch_stock_export_workflow,
    get_workflow_catalog,
    run_inventory_export_workflow,
    run_fast_workflow,
    run_misc_workflow,
    run_pending_sales_order_workflow,
    run_sales_order_workflow,
    run_stock_doc_workflow,
    run_stock_apply_workflow,
    run_transfer_workflow,
    run_channel_sales_summary_workflow,
    run_warehouse_keyword_batch_stock_export_workflow,
)


class TestWorkflowHelpers(unittest.TestCase):
    @patch("modules.workflows.append_feedback_log")
    @patch("modules.sales_order.prepare_sales_order_batches")
    @patch("modules.sales_order.preflight_sales_order")
    def test_sales_order_workflow_requests_batch_confirmation(self, mock_preflight, mock_prepare, mock_append_feedback):
        mock_preflight.return_value = {"ok": True, "errors": [], "next_action": "预检通过"}
        mock_prepare.return_value = {"goods_recommendations": []}
        mock_append_feedback.side_effect = lambda entry: entry

        result = run_sales_order_workflow(
            order_type="manual",
            require_batch_confirmation=True,
            shop_name="测试渠道",
            seller_name="创建人",
            goods_list=[{"goodsNo": "G1", "sellCount": 1, "sellPrice": "10"}],
        )

        self.assertEqual(result["status"], "needs_batch_confirmation")
        self.assertEqual(result["workflow"], "sales_order")
        self.assertIn("execution_plan", result)
        self.assertIn("steps", result)
        self.assertIn("pain_points", result)
        self.assertIn("reuse_hints", result)

    @patch("modules.workflows.append_feedback_log")
    @patch("modules.sales_order.create_manual_order_and_audit")
    @patch("modules.sales_order.query_trade_by_no")
    @patch("modules.sales_order.preflight_sales_order")
    def test_sales_order_workflow_auto_audit(self, mock_preflight, mock_query_trade, mock_create, mock_append_feedback):
        mock_preflight.return_value = {"ok": True, "errors": [], "next_action": "预检通过"}
        mock_create.return_value = {"trade_no": "YR001", "audit_result": {"code": "200"}}
        mock_query_trade.return_value = {"tradeNo": "YR001", "warehouseName": "默认仓"}
        mock_append_feedback.side_effect = lambda entry: entry

        result = run_sales_order_workflow(
            order_type="manual",
            submit_audit=True,
            require_batch_confirmation=False,
            shop_name="测试渠道",
            seller_name="创建人",
            goods_list=[{"goodsNo": "G1", "sellCount": 1, "sellPrice": "10", "batchNo": "B001"}],
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["trade_no"], "YR001")
        self.assertTrue(result["submit_audit"])
        self.assertTrue(result["requires_finance_review"])
        self.assertEqual(result["execution_plan"]["workflow"], "sales_order")
        self.assertEqual(result["created_trade"]["tradeNo"], "YR001")
        self.assertEqual(mock_query_trade.call_args.args[0], "YR001")
        logged = mock_append_feedback.call_args.args[0]
        self.assertIn("steps", logged)
        self.assertIn("pain_points", logged)
        self.assertIn("reuse_hints", logged)
        self.assertEqual(logged["input_summary"]["goods_line_count"], 1)

    @patch("modules.sales_order.create_manual_order_and_audit")
    @patch("modules.sales_order.query_trade_by_no")
    @patch("modules.sales_order.preflight_sales_order")
    def test_online_order_submit_does_not_require_finance_review(self, mock_preflight, mock_query_trade, mock_create):
        mock_preflight.return_value = {"ok": True, "errors": [], "next_action": "预检通过"}
        mock_create.return_value = {"trade_no": "YR002", "audit_result": {"code": "200"}}
        mock_query_trade.return_value = {"tradeNo": "YR002"}

        result = run_sales_order_workflow(
            order_type="manual",
            submit_audit=True,
            is_online_order=True,
            require_batch_confirmation=False,
            shop_name="测试渠道",
            seller_name="创建人",
            goods_list=[{"goodsNo": "G1", "sellCount": 1, "sellPrice": "10", "batchNo": "B001"}],
        )

        self.assertFalse(result["requires_finance_review"])
        self.assertEqual(result["submit_target"], "warehouse")

    @patch("modules.sales_order.create_manual_order")
    @patch("modules.sales_order.query_trade_by_no")
    @patch("modules.sales_order.preflight_sales_order")
    def test_sales_order_workflow_accepts_confirmed_batch_list(self, mock_preflight, mock_query_trade, mock_create):
        mock_preflight.return_value = {"ok": True, "errors": [], "next_action": "预检通过"}
        mock_create.return_value = {"result": {"billNo": "YR003"}}
        mock_query_trade.return_value = {"tradeNo": "YR003"}

        result = run_sales_order_workflow(
            order_type="manual",
            require_batch_confirmation=True,
            shop_name="测试渠道",
            seller_name="创建人",
            goods_list=[
                {
                    "goodsNo": "G1",
                    "sellCount": 2,
                    "sellPrice": "10",
                    "batchList": [{"batchNo": "B001", "quantity": 2}],
                }
            ],
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["trade_no"], "YR003")

    @patch("modules.workflows.append_feedback_log")
    @patch("modules.sales_order.create_manual_order")
    @patch("modules.sales_order.preflight_sales_order")
    def test_sales_order_workflow_blocks_incomplete_create(self, mock_preflight, mock_create, mock_append_feedback):
        mock_preflight.return_value = {
            "ok": False,
            "errors": ["缺少 receiver_name", "缺少手机号"],
            "next_action": "请先修正 errors 中的问题，再创建单据",
        }
        mock_append_feedback.side_effect = lambda entry: entry

        result = run_sales_order_workflow(
            order_type="manual",
            shop_name="测试渠道",
            seller_name="创建人",
            goods_list=[{"goodsNo": "G1", "sellCount": 1, "sellPrice": "10"}],
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertFalse(result["created"])
        self.assertEqual(result["workflow"], "sales_order")
        self.assertIn("template", result)
        mock_create.assert_not_called()

    @patch("modules.workflows.append_feedback_log")
    @patch("modules.sales_order.create_manual_order")
    @patch("modules.sales_order.query_trade_by_no")
    @patch("modules.sales_order.preflight_sales_order")
    def test_sales_order_workflow_allows_stock_shortage_create_without_audit(
        self,
        mock_preflight,
        mock_query_trade,
        mock_create,
        mock_append_feedback,
    ):
        mock_preflight.return_value = {
            "ok": True,
            "errors": [],
            "warnings": ["库存不足；用户已允许先建待配批次单"],
            "next_action": "库存不足但已允许先建单",
            "batch_summary": {"all_enough_stock": False, "stock_shortage_allowed": True},
        }
        mock_create.return_value = {"result": {"billNo": "YR004"}}
        mock_query_trade.return_value = {"tradeNo": "YR004"}
        mock_append_feedback.side_effect = lambda entry: entry

        result = run_sales_order_workflow(
            order_type="manual",
            submit_audit=True,
            allow_stock_shortage_create=True,
            shop_name="测试渠道",
            seller_name="创建人",
            receiver_name="张三",
            mobile="13800138000",
            address="上海",
            goods_list=[{"goodsNo": "G1", "sellCount": 3, "sellPrice": "10"}],
        )

        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["submit_audit"])
        self.assertTrue(result["stock_shortage_pending"])
        self.assertIn("待库存到货", result["next_action"])
        self.assertTrue(mock_create.call_args.kwargs["allow_stock_shortage"])

    @patch("modules.workflows.append_feedback_log")
    @patch("modules.workflows.set_user_preference")
    @patch("modules.workflows.increment_user_preference_counter")
    @patch("modules.workflows.append_experience")
    def test_record_workflow_correction_learns_sales_order_fields(
        self,
        mock_append_experience,
        mock_increment_counter,
        mock_set_preference,
        mock_append_feedback,
    ):
        mock_append_experience.side_effect = lambda kind, payload: {"kind": kind, **payload}
        mock_append_feedback.side_effect = lambda entry: entry

        result = record_workflow_correction(
            workflow="sales_order",
            issue="仓库匹配错",
            user_correction="仓库应为 YRMG04",
            root_cause="缓存没有全量分页",
            prevention_rule="仓库未命中时必须全量分页刷新后再匹配",
            corrected_fields={"warehouse_name": "依然-分销组-麦歌仓", "batch_strategy": "fifo"},
        )

        self.assertEqual(result["status"], "learned")
        mock_increment_counter.assert_called_with(
            "sales_order.all.warehouseName",
            "warehouse_name",
            "依然-分销组-麦歌仓",
        )
        mock_set_preference.assert_called_with("default_batch_strategy", "fifo")

    @patch("modules.sales_order.summarize_pending_shop_orders")
    def test_pending_workflow_summary(self, mock_summary):
        mock_summary.return_value = {"trade_count": 5, "goods_count": 8}

        result = run_pending_sales_order_workflow(action="summarize", shop_name="测试渠道")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["data"]["trade_count"], 5)
        self.assertEqual(result["execution_plan"]["workflow"], "pending_sales_order")

    @patch("modules.sales_order.diagnose_pending_trade_candidates")
    def test_pending_workflow_diagnose(self, mock_diagnose):
        mock_diagnose.return_value = {"total": 2, "blocked_count": 1, "audit_ready_trade_nos": ["YR1"]}

        result = run_pending_sales_order_workflow(action="diagnose", shop_name="测试渠道", check_stock=False)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["data"]["blocked_count"], 1)
        mock_diagnose.assert_called_once()

    @patch("modules.transfer.submit_transfer_payload")
    @patch("modules.transfer.prepare_transfer_payload")
    @patch("modules.transfer.query_transfer_by_no")
    def test_transfer_workflow_does_not_auto_request_batch_confirmation(self, mock_query_transfer, mock_prepare, mock_submit):
        mock_prepare.return_value = (
            {"outWarehouseCode": "WH001", "stockAllocateDetailViews": [{"goodsNo": "G1", "skuCount": 2}]},
            {"goods": [{"line_index": 1, "source": "erp.storage.goodslist"}], "batches": []},
        )
        mock_submit.return_value = {"result": {"allocateNo": "DB001"}}
        mock_query_transfer.return_value = {"allocateNo": "DB001", "memo": "调拨备注"}

        result = run_transfer_workflow(
            {
                "outWarehouseCode": "WH001",
                "goodsList": [{"goodsNo": "G1", "skuCount": 2}],
            }
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["workflow"], "transfer")
        self.assertEqual(result["execution_plan"]["workflow"], "transfer")
        self.assertEqual(result["auto_fill_summary"]["goods"][0]["source"], "erp.storage.goodslist")
        self.assertEqual(result["allocate_no"], "DB001")
        self.assertEqual(result["created_transfer"]["allocateNo"], "DB001")
        self.assertEqual(mock_query_transfer.call_args.args[0], "DB001")
        self.assertEqual(mock_prepare.call_args.kwargs["batch_strategy"], "fifo")

    @patch("modules.transfer.submit_transfer_payload")
    @patch("modules.transfer.prepare_transfer_payload")
    @patch("modules.transfer.query_transfer_by_no")
    def test_transfer_workflow_allows_stock_shortage_create(self, mock_query_transfer, mock_prepare, mock_submit):
        mock_prepare.return_value = (
            {"outWarehouseCode": "WH001", "stockAllocateDetailViews": [{"goodsNo": "G1", "skuCount": 2, "isBatch": 1}]},
            {
                "goods": [{"line_index": 1, "source": "erp.storage.goodslist"}],
                "batches": [{"line_index": 1, "status": "stock_shortage_pending", "shortage_quantity": 2}],
            },
        )
        mock_submit.return_value = {"result": {"allocateNo": "DB002"}}
        mock_query_transfer.return_value = {"allocateNo": "DB002"}

        result = run_transfer_workflow(
            {"outWarehouseCode": "WH001", "goodsList": [{"goodsNo": "G1", "skuCount": 2}]},
            allow_stock_shortage_create=True,
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["stock_shortage_pending"])
        self.assertIn("缺货先建单", result["next_action"])
        self.assertTrue(mock_prepare.call_args.kwargs["allow_stock_shortage"])

    @patch("modules.stock_doc.check_doc")
    @patch("modules.stock_doc.create_doc_out")
    def test_stock_doc_workflow_can_auto_check(self, mock_create, mock_check):
        mock_create.return_value = {"result": {"goodsdocNo": "GD001"}}
        mock_check.return_value = {"code": "200"}

        result = run_stock_doc_workflow(
            doc_type="out",
            doc_data={"inouttype": 201, "goodsDocDetailList": [{"goodsNo": "G1", "quantity": 1}]},
            auto_check=True,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["check_result"]["code"], "200")
        self.assertEqual(result["execution_plan"]["workflow"], "stock_doc")

    @patch("modules.stock_doc.query_stock_out_apply")
    @patch("modules.stock_doc.submit_stock_out_apply_payload")
    @patch("modules.stock_doc.prepare_stock_apply_payload")
    def test_stock_apply_workflow_creates_and_queries(self, mock_prepare, mock_submit, mock_query):
        mock_prepare.return_value = (
            {
                "outWarehouseCode": "WH001",
                "applyUserName": "张三",
                "relDataId": "REL001",
                "stockOutDetailViews": [{"goodsNo": "G1", "skuCount": 2}],
            },
            {
                "applicant": "张三",
                "warehouse_code": "WH001",
                "batches": [{"line_index": 1, "allocation": [{"batchNo": "B1", "quantity": 2}]}],
            },
        )
        mock_submit.return_value = {"result": {"data": {"outNo": "OUT001"}}}
        mock_query.return_value = [{"outNo": "OUT001", "applyUserName": "张三"}]

        result = run_stock_apply_workflow("out", {"applyUserName": "张三", "goodsList": [{"goodsNo": "G1", "skuCount": 2}]})

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["workflow"], "stock_apply")
        self.assertEqual(result["apply_no"], "OUT001")
        self.assertEqual(result["created_apply"]["outNo"], "OUT001")
        self.assertEqual(result["execution_plan"]["workflow"], "stock_apply")

    @patch("modules.reports.query_channel_sales_summary")
    def test_channel_sales_summary_workflow(self, mock_query):
        mock_query.return_value = {
            "row_count": 1,
            "resolved_shops": [{"shopName": "渠道A"}],
            "total_goods_qty": 3,
            "total_goods_amount": 99,
        }

        result = run_channel_sales_summary_workflow(month="2026-05", shop_names=["渠道A"], dimension="channel")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["workflow"], "channel_sales_summary")
        self.assertEqual(result["data"]["total_goods_qty"], 3)
        self.assertEqual(mock_query.call_args.kwargs["dimension"], "channel")

    @patch("modules.reports.query_channel_sales_summary")
    def test_channel_sales_summary_workflow_supports_period_keyword_and_status_alias(self, mock_query):
        mock_query.return_value = {
            "row_count": 0,
            "resolved_shops": [],
            "total_goods_qty": 0,
            "total_goods_amount": 0,
        }

        run_channel_sales_summary_workflow(
            period="昨天",
            channel_include_keyword="分销组",
            dimension="channel_daily",
            trade_status="发货在途或者已完成",
        )

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        kwargs = mock_query.call_args.kwargs
        self.assertEqual(kwargs["start_time"], yesterday)
        self.assertEqual(kwargs["end_time"], yesterday)
        self.assertEqual(kwargs["channel_include_keyword"], "分销组")
        self.assertEqual(kwargs["trade_status"], "6000")
        self.assertEqual(kwargs["dimension"], "channel_daily")

    def test_workflow_catalog_and_fast_dispatch(self):
        catalog = get_workflow_catalog()
        self.assertIn("stock_apply_create", catalog)
        with patch("modules.workflows.run_channel_sales_summary_workflow") as mock_summary:
            mock_summary.return_value = {"status": "completed"}
            result = run_fast_workflow("channel_sales_summary", month="2026-05")
        self.assertEqual(result["status"], "completed")

    @patch("modules.aftersales.create_refund")
    def test_misc_workflow_refund(self, mock_create):
        mock_create.return_value = {"code": "200"}

        result = run_misc_workflow("refund_create", refund_data={"refundNo": "R1"})

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["data"]["code"], "200")
        self.assertEqual(result["execution_plan"]["workflow"], "refund_create")

    @patch("modules.inventory.export_stock_quantity_report")
    def test_inventory_export_workflow(self, mock_export):
        mock_export.return_value = {
            "output_path": "C:/tmp/inventory.xlsx",
            "row_count": 10,
            "header_mode": "zh-CN",
            "batch_output_path": "C:/tmp/inventory.batches.csv",
        }

        result = run_inventory_export_workflow(
            output_path="C:/tmp/inventory.xlsx",
            warehouse_code="WH001",
            include_batch_details=True,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["workflow"], "inventory_export")
        self.assertEqual(result["execution_plan"]["workflow"], "inventory_export")
        self.assertEqual(result["data"]["row_count"], 10)
        self.assertEqual(result["data"]["batch_output_path"], "C:/tmp/inventory.batches.csv")

    @patch("modules.delivery_note.generate_delivery_note_from_trade")
    def test_delivery_note_export_workflow(self, mock_generate):
        mock_generate.return_value = {
            "output_path": "C:/tmp/260429订单出库单（YR260429001022）.xlsx",
            "trade_no": "YR260429001022",
            "goods_count": 30,
        }

        result = run_delivery_note_export_workflow("YR260429001022")

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["workflow"], "delivery_note_export")
        self.assertEqual(result["execution_plan"]["workflow"], "delivery_note_export")
        self.assertEqual(result["data"]["goods_count"], 30)

    @patch("modules.inventory.export_warehouse_keyword_batch_stock_report")
    def test_warehouse_keyword_batch_stock_export_workflow(self, mock_export):
        mock_export.return_value = {
            "output_path": "C:/tmp/关键词仓库批次库存.xlsx",
            "row_count": 662,
            "warehouse_count": 25,
            "warehouse_cache_count": 247,
            "pain_points": ["匹配到的仓库可能包含虚拟/调拨仓"],
        }

        result = run_warehouse_keyword_batch_stock_export_workflow(
            output_path="C:/tmp/关键词仓库批次库存.xlsx",
            include_keyword="分销组",
            exclude_keywords=["除分销组"],
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["workflow"], "warehouse_keyword_batch_stock_export")
        self.assertEqual(result["execution_plan"]["workflow"], "warehouse_keyword_batch_stock_export")
        self.assertEqual(result["data"]["row_count"], 662)

    @patch("modules.workflows.run_warehouse_keyword_batch_stock_export_workflow")
    def test_distribution_group_batch_stock_export_workflow_alias(self, mock_generic):
        mock_generic.return_value = {
            "status": "completed",
            "workflow": "warehouse_keyword_batch_stock_export",
            "data": {"row_count": 662},
        }

        result = run_distribution_group_batch_stock_export_workflow("C:/tmp/分销组.xlsx")

        self.assertEqual(result["workflow_alias"], "distribution_group_batch_stock_export")
        mock_generic.assert_called_once()


if __name__ == "__main__":
    unittest.main()
