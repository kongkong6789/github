import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.local_store import get_master_data
from modules.warehouse import get_warehouse_by_code, get_warehouse_by_name, search_warehouses_by_keywords


class TestMasterCacheSafety(unittest.TestCase):
    def test_partial_lookup_does_not_overwrite_master_cache_when_disabled(self):
        with patch("helpers.local_store.get_cached_master_data", return_value=[]), \
             patch("helpers.local_store.save_cached_master_data") as mock_save:
            result = get_master_data(
                "warehouses",
                lambda: [{"warehouseName": "局部结果"}],
                lambda item: item["warehouseName"] == "局部结果",
                save_fresh=False,
            )

        self.assertEqual(result, [{"warehouseName": "局部结果"}])
        mock_save.assert_not_called()

    @patch("modules.warehouse.query_all_warehouses")
    def test_warehouse_keyword_search_refreshes_partial_cache_and_excludes_keywords(self, mock_query_all):
        mock_query_all.return_value = [
            {"warehouseName": "依然电商-分销组仓", "warehouseCompanyName": "依然电商"},
            {"warehouseName": "依然电商-除分销组仓", "warehouseCompanyName": "依然电商"},
            {"warehouseName": "依然电商-虚拟仓（除外贸组和分销组）", "warehouseCompanyName": "依然电商"},
            {"warehouseName": "ACT-分销组仓", "warehouseCompanyName": "ACT"},
            {"warehouseName": "普通仓", "warehouseCompanyName": "依然电商"},
        ]

        with patch("modules.warehouse.get_cached_master_data", return_value=[
            {"warehouseName": "旧局部仓"}
        ]), patch("helpers.local_store.save_cached_master_data") as mock_save:
            result = search_warehouses_by_keywords(
                "分销组",
                exclude_keywords=["除分销组"],
            )

        self.assertEqual(result["cache_count"], 5)
        self.assertEqual(result["total"], 2)
        self.assertEqual([item["warehouseName"] for item in result["items"]], [
            "ACT-分销组仓",
            "依然电商-分销组仓",
        ])
        mock_save.assert_called_once()

    @patch("modules.warehouse.query_warehouses")
    @patch("modules.warehouse.query_all_warehouses")
    def test_get_warehouse_by_name_refreshes_partial_cache_before_missing(self, mock_query_all, mock_query_warehouses):
        mock_query_all.return_value = [
            {"warehouseName": f"普通仓{i}", "warehouseCode": f"WH{i:03d}"}
            for i in range(200)
        ] + [{"warehouseName": "韩国麦歌仓", "warehouseCode": "YRMG04"}]
        mock_query_warehouses.return_value = []

        with patch("modules.warehouse.get_cached_master_data", return_value=[
            {"warehouseName": "第一页仓库", "warehouseCode": "WH001"},
        ]), patch("helpers.local_store.save_cached_master_data"):
            result = get_warehouse_by_name("YRMG04")

        self.assertEqual(result["warehouseCode"], "YRMG04")
        mock_query_warehouses.assert_not_called()

    @patch("modules.warehouse.query_warehouses")
    @patch("modules.warehouse.query_all_warehouses")
    def test_get_warehouse_by_code_refreshes_partial_cache(self, mock_query_all, mock_query_warehouses):
        mock_query_all.return_value = [
            {"warehouseName": f"普通仓{i}", "warehouseCode": f"WH{i:03d}"}
            for i in range(200)
        ] + [{"warehouseName": "韩国麦歌仓", "warehouseCode": "YRMG04"}]
        mock_query_warehouses.return_value = []

        with patch("modules.warehouse.get_cached_master_data", return_value=[
            {"warehouseName": "第一页仓库", "warehouseCode": "WH001"},
        ]), patch("helpers.local_store.save_cached_master_data"):
            result = get_warehouse_by_code("YRMG04")

        self.assertEqual(result["warehouseName"], "韩国麦歌仓")
        mock_query_warehouses.assert_not_called()


if __name__ == "__main__":
    unittest.main()
