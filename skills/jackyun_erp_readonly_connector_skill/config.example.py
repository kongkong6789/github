"""
吉客云项目 Skill 运行配置示例。

本文件只从环境变量读取凭据，避免把 AppKey/AppSecret 固化进项目 Skill。
真实实时 ERP 查询需要在项目 .env 或进程环境中配置 JACKYUN_APP_KEY 和 JACKYUN_APP_SECRET。
"""

from __future__ import annotations

import os

JACKYUN_APP_KEY = os.getenv("JACKYUN_APP_KEY", "").strip()
JACKYUN_APP_SECRET = os.getenv("JACKYUN_APP_SECRET", "").strip()
JACKYUN_API_URL = os.getenv("JACKYUN_API_URL", "https://open.jackyun.com/open/openapi/do")
JACKYUN_AUTHORIZED_APP_KEY = os.getenv("JACKYUN_AUTHORIZED_APP_KEY", JACKYUN_APP_KEY)

API_TIMEOUT = int(os.getenv("JACKYUN_API_TIMEOUT", "30"))
DEFAULT_PAGE_SIZE = int(os.getenv("JACKYUN_PAGE_SIZE", "50"))
MAX_PAGE_LIMIT = int(os.getenv("JACKYUN_MAX_PAGE_LIMIT", "100"))

MAX_RETRIES = int(os.getenv("JACKYUN_MAX_RETRIES", "3"))
RETRY_BACKOFF = float(os.getenv("JACKYUN_RETRY_BACKOFF", "1.0"))
RETRY_STATUS_CODES = {500, 502, 503, 504}
API_CALL_INTERVAL = float(os.getenv("JACKYUN_API_CALL_INTERVAL", "0.3"))

DEFAULT_APPLICATION_COMPANY_NAME = os.getenv("JACKYUN_DEFAULT_APPLICATION_COMPANY_NAME", "依然电商")
TRANSFER_REASON_DICT_VALUE = os.getenv("JACKYUN_TRANSFER_REASON_DICT_VALUE", "调拨原因")
SAMPLE_ORDER_FLAG_ID = os.getenv("JACKYUN_SAMPLE_ORDER_FLAG_ID", "")
SAMPLE_ORDER_FLAG_NAME = os.getenv("JACKYUN_SAMPLE_ORDER_FLAG_NAME", "样品")
RESEND_ORDER_FLAG_ID = os.getenv("JACKYUN_RESEND_ORDER_FLAG_ID", "")
RESEND_ORDER_FLAG_NAME = os.getenv("JACKYUN_RESEND_ORDER_FLAG_NAME", "补发")
STOCK_HISTORY_METHOD = os.getenv("JACKYUN_STOCK_HISTORY_METHOD", "")
CHANNEL_SALES_UDR_REPORT_ID = os.getenv("JACKYUN_CHANNEL_SALES_UDR_REPORT_ID", "")

JACKYUN_CALL_STRATEGY = os.getenv("JACKYUN_CALL_STRATEGY", "auto").lower()
JACKYUN_MCP_URL = os.getenv("JACKYUN_MCP_URL", "https://mcp.open.jackyun.com/mcp/messages")
JACKYUN_MCP_TOKEN = os.getenv("JACKYUN_MCP_TOKEN", "")
JACKYUN_MCP_TIMEOUT = int(os.getenv("JACKYUN_MCP_TIMEOUT", "30"))
JACKYUN_CLI_ENABLED = os.getenv("JACKYUN_CLI_ENABLED", "0").lower() in {"1", "true", "yes"}
JACKYUN_CLI_TIMEOUT = int(os.getenv("JACKYUN_CLI_TIMEOUT", "60"))
