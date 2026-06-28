"""
Runtime routing visibility for high-frequency workflows.

Business workflows call module functions, and those modules eventually call
jackyun_api.get_client().call(). This helper exposes which transport will be
preferred for the methods a workflow normally uses.
"""
from __future__ import annotations

from typing import Any

import config
from helpers.mcp_runtime import get_tool_for_method


WORKFLOW_METHODS = {
    "sales_order": [
        "oms.trade.ordercreate",
        "oms.trade.audit.pass",
        "erp.sales.get",
        "erp.warehouse.get",
        "erp.logistic.get",
        "erp.batchstockquantity.get",
        "erp.user.search",
    ],
    "pending_sales_order": [
        "oms.trade.fullinfoget",
        "oms.trade.audit.pass",
        "oms.trade.order.batchUpdateLogisticWarehouse",
    ],
    "transfer": [
        "erp.allocate.create",
        "erp.allocate.quick.create",
        "erp.warehouse.get",
        "erp.company.query",
        "erp.user.search",
        "erp.depart.query",
        "erp.storage.goodslist",
        "erp.batchstockquantity.get",
        "erp.dictionary.page",
        "erp.dictionary.save",
    ],
    "stock_doc": [
        "erp.storage.goodsdocout.add",
        "erp.storage.goodsdocin.add",
        "erp.storage.goodsdoc.check",
        "erp.batchstockquantity.get",
    ],
    "stock_apply": [
        "erp.storage.stockincreate",
        "erp.storage.stockoutcreate",
        "erp.stockin.get.v2",
        "erp.stockout.get.v2",
        "erp.warehouse.get",
        "erp.storage.goodslist",
        "erp.batchstockquantity.get",
        "erp.user.search",
    ],
    "inventory_export": [
        "erp.stockquantity.get",
        "erp.batchstockquantity.get",
    ],
    "goods_sales_analysis": [
        "birc.report.needauth.goodsMultiDimensionalAnalysis",
        "udr.openapi.userdefinedreport",
        "erp.sales.get",
    ],
    "channel_sales_summary": [
        "birc.report.needauth.goodsMultiDimensionalAnalysis",
        "udr.openapi.userdefinedreport",
        "erp.sales.get",
    ],
    "delivery_note_export": [
        "oms.trade.fullinfoget",
    ],
    "warehouse_keyword_batch_stock_export": [
        "erp.warehouse.get",
        "erp.batchstockquantity.get",
        "erp-stock.stock.skulist",
    ],
    "distribution_group_batch_stock_export": [
        "erp.warehouse.get",
        "erp.batchstockquantity.get",
        "erp-stock.stock.skulist",
    ],
    "combined_create": [
        "erp.combind.create.v2",
        "erp.combind.create",
    ],
    "refund_create": [
        "ass-business.refund.create",
    ],
    "returnchange_create": [
        "ass-business.returnchange.create",
    ],
}


def method_route_plan(method: str) -> dict[str, Any]:
    strategy = (config.JACKYUN_CALL_STRATEGY or "auto").lower()
    tool = get_tool_for_method(method)
    mcp_supported = tool is not None
    mcp_ready = bool(config.JACKYUN_MCP_TOKEN and mcp_supported)
    cli_enabled = bool(config.JACKYUN_CLI_ENABLED)

    if strategy == "mcp":
        primary = "mcp"
        fallback = []
    elif strategy == "cli":
        primary = "cli"
        fallback = []
    elif strategy == "http":
        primary = "http"
        fallback = []
    elif mcp_ready:
        primary = "mcp"
        fallback = ["cli", "http"] if cli_enabled else ["http"]
    elif cli_enabled:
        primary = "cli"
        fallback = ["http"]
    else:
        primary = "http"
        fallback = []

    return {
        "method": method,
        "strategy": strategy,
        "primary": primary,
        "fallback": fallback,
        "mcp_supported": mcp_supported,
        "mcp_ready": mcp_ready,
        "mcp_tool_name": tool.get("toolName") if tool else "",
        "cli_enabled": cli_enabled,
    }


def workflow_route_plan(workflow_name: str) -> dict[str, Any]:
    methods = WORKFLOW_METHODS.get(workflow_name, [])
    routes = [method_route_plan(method) for method in methods]
    return {
        "workflow": workflow_name,
        "strategy": (config.JACKYUN_CALL_STRATEGY or "auto").lower(),
        "mcp_token_configured": bool(config.JACKYUN_MCP_TOKEN),
        "cli_enabled": bool(config.JACKYUN_CLI_ENABLED),
        "methods": routes,
    }
