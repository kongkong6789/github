import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.inventory import (
    export_distribution_group_batch_stock_report,
    export_warehouse_keyword_batch_stock_report,
    export_stock_quantity_report,
    format_stock_quantity,
    recommend_batches,
)


class TestInventoryBatchRecommendation(unittest.TestCase):
    @patch("modules.inventory.query_batch_stock_formatted")
    def test_recommend_batches_defaults_to_fifo_and_splits_batches(self, mock_query):
        mock_query.return_value = [
            {
                "batch_no": "NEW",
                "available_quantity": 5,
                "production_date": "2026-02-01",
                "expiration_date": "2026-05-01",
            },
            {
                "batch_no": "OLD",
                "available_quantity": 3,
                "production_date": "2026-01-01",
                "expiration_date": "2026-12-01",
            },
        ]

        result = recommend_batches(
            warehouse_code="WH001",
            goods_no="G001",
            required_quantity=6,
        )

        self.assertEqual(result["strategy"], "fifo")
        self.assertTrue(result["enough_stock"])
        self.assertEqual(result["recommended_allocation"][0]["batch_no"], "OLD")
        self.assertEqual(result["recommended_allocation"][0]["quantity"], 3)
        self.assertEqual(result["recommended_allocation"][1]["batch_no"], "NEW")
        self.assertEqual(result["recommended_allocation"][1]["quantity"], 3)

    @patch("modules.inventory.query_batch_stock_formatted")
    def test_recommend_batches_fefo(self, mock_query):
        mock_query.return_value = [
            {
                "batch_no": "B2",
                "available_quantity": 5,
                "production_date": "2026-01-01",
                "expiration_date": "2026-06-01",
            },
            {
                "batch_no": "B1",
                "available_quantity": 3,
                "production_date": "2025-12-01",
                "expiration_date": "2026-05-01",
            },
        ]
        result = recommend_batches(
            warehouse_code="WH001",
            goods_no="G001",
            required_quantity=6,
            strategy="fefo",
        )
        self.assertTrue(result["enough_stock"])
        self.assertEqual(result["recommended_allocation"][0]["batch_no"], "B1")
        self.assertEqual(result["recommended_allocation"][0]["quantity"], 3)
        self.assertEqual(result["recommended_allocation"][1]["batch_no"], "B2")
        self.assertEqual(result["recommended_allocation"][1]["quantity"], 3)

    @patch("modules.inventory.query_batch_stock_formatted")
    def test_recommend_batches_filters_then_fifo(self, mock_query):
        mock_query.return_value = [
            {
                "batch_no": "A-OLD",
                "available_quantity": 3,
                "production_date": "2026-01-01",
                "expiration_date": "2026-06-01",
            },
            {
                "batch_no": "B-OLD",
                "available_quantity": 3,
                "production_date": "2026-01-05",
                "expiration_date": "2026-06-01",
            },
            {
                "batch_no": "A-NEW",
                "available_quantity": 3,
                "production_date": "2026-02-01",
                "expiration_date": "2026-06-01",
            },
        ]

        result = recommend_batches(
            warehouse_code="WH001",
            goods_no="G001",
            required_quantity=4,
            batch_no_contains="A",
        )

        self.assertTrue(result["enough_stock"])
        self.assertEqual([row["batch_no"] for row in result["recommended_allocation"]], ["A-OLD", "A-NEW"])


class TestInventoryExport(unittest.TestCase):
    def test_format_stock_quantity(self):
        row = format_stock_quantity({
            "warehouseCode": "WH001",
            "warehouseName": "Main Warehouse",
            "goodsNo": "G001",
            "goodsName": "Test Goods",
            "skuName": "Default",
            "skuBarcode": "BAR001",
            "unitName": "pcs",
            "currentQuantity": 20,
            "useQuantity": 18,
            "lockedQuantity": 2,
            "reserveQuantity": 1,
            "stockOutuantity": 4,
        })
        self.assertEqual(row["warehouse_code"], "WH001")
        self.assertEqual(row["current_quantity"], 20)
        self.assertEqual(row["available_quantity"], 18)
        self.assertEqual(row["locked_quantity"], 2)
        self.assertEqual(row["stock_out_quantity"], 4)

    @patch("modules.inventory.get_client")
    def test_export_stock_quantity_report_to_csv(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.call.return_value = {
            "result": {
                "data": {
                    "goodsStockQuantity": [
                        {
                            "warehouseCode": "WH001",
                            "warehouseName": "Main Warehouse",
                            "goodsNo": "G001",
                            "goodsName": "Test Goods",
                            "skuName": "Default",
                            "skuBarcode": "BAR001",
                            "unitName": "pcs",
                            "currentQuantity": 20,
                            "useQuantity": 18,
                            "lockedQuantity": 2,
                            "reserveQuantity": 1,
                            "allocateQuantity": 3,
                            "purchasingQuantity": 4,
                            "orderingQuantity": 5,
                            "stockInQuantity": 6,
                            "stockOutQuantity": 7,
                            "defectiveQuanity": 0,
                            "defectiveUseQuantity": 0,
                            "costPrice": 9.9,
                        }
                    ]
                }
            }
        }
        mock_get_client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "inventory.csv")
            result = export_stock_quantity_report(output_path=output_path, warehouse_code="WH001")
            self.assertEqual(result["row_count"], 1)
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, encoding="utf-8-sig") as handle:
                content = handle.read()
            self.assertIn("仓库编码,仓库名称,货品编号", content)
            self.assertIn("WH001,Main Warehouse,G001", content)
            self.assertEqual(result["header_mode"], "zh-CN")

    @patch("modules.inventory.query_all_sku_stock_list")
    @patch("modules.inventory.query_all_batch_stock_quantity")
    @patch("modules.warehouse.search_warehouses_by_keywords")
    def test_warehouse_keyword_batch_stock_export(self, mock_search_wh, mock_batch_stock, mock_sku_stock):
        mock_search_wh.return_value = {
            "items": [
                {"warehouseCode": "WH001", "warehouseName": "依然-分销组-虚拟仓"},
                {"warehouseCode": "WH002", "warehouseName": "ACT-分销组-韩国申通仓"},
            ],
            "cache_count": 247,
            "source": "data/cache/warehouses",
        }
        mock_batch_stock.side_effect = [
            [
                {
                    "warehouseCode": "WH001",
                    "warehouseName": "依然-分销组-虚拟仓",
                    "batchNo": "B001",
                    "goodsNo": "G001",
                    "goodsName": "测试货品",
                    "currentQuantity": 10,
                    "availableQuantity": 8,
                    "productionDate": 1767225600000,
                    "expirationDate": 1798761600000,
                }
            ],
            [],
        ]
        mock_sku_stock.return_value = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "distribution.csv")
            result = export_warehouse_keyword_batch_stock_report(
                output_path,
                include_keyword="分销组",
                exclude_keywords=["除分销组"],
            )

            self.assertEqual(result["warehouse_count"], 2)
            self.assertEqual(result["warehouse_cache_count"], 247)
            self.assertEqual(result["row_count"], 1)
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, encoding="utf-8-sig") as handle:
                content = handle.read()

        self.assertIn("仓库,批次,货品编号,货品名称,库存数量,可用库存", content)
        self.assertIn("依然-分销组-虚拟仓,B001,G001,测试货品,10,8", content)
        self.assertTrue(content.rstrip().endswith(",0"))
        mock_search_wh.assert_called_once()
        self.assertEqual(mock_batch_stock.call_count, 2)

    @patch("modules.inventory.export_warehouse_keyword_batch_stock_report")
    def test_distribution_group_wrapper_uses_generic_export(self, mock_export):
        mock_export.return_value = {"output_path": "x.csv", "row_count": 0}

        result = export_distribution_group_batch_stock_report("x.csv")

        self.assertEqual(result["row_count"], 0)
        mock_export.assert_called_once_with(
            output_path="x.csv",
            include_keyword="分销组",
            exclude_keywords=None,
            fill_missing_sales_zero=True,
            include_sales=True,
            active_only=False,
            use_chinese_headers=True,
        )


if __name__ == "__main__":
    unittest.main()
