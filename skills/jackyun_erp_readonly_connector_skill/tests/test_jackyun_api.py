"""
API 客户端单元测试

测试签名生成、请求构建、错误处理等核心逻辑。
"""
import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.jackyun_signature import build_signed_openapi_params, generate_openapi_sign
from jackyun_api import JackyunAPI, JackyunAPIError, JackyunNetworkError
import config

TEST_APP_KEY = "TEST_APP_KEY_DO_NOT_USE"
TEST_APP_SECRET = "TEST_APP_SECRET_DO_NOT_USE"


class TestSignature(unittest.TestCase):
    """测试签名生成算法"""

    def setUp(self):
        self.client = JackyunAPI(
            app_key=TEST_APP_KEY,
            app_secret=TEST_APP_SECRET,
            api_url="https://open.jackyun.com/open/openapi/do",
        )

    def test_sign_basic(self):
        """基本签名生成"""
        params = {
            "appkey": TEST_APP_KEY,
            "method": "erp.storage.goodslist",
            "timestamp": "2024-01-01 00:00:00",
            "version": "v1.0",
            "bizcontent": "{}",
        }
        sign = self.client._generate_sign(params)
        public_sign = generate_openapi_sign(params, app_secret=TEST_APP_SECRET)
        self.assertIsInstance(sign, str)
        self.assertEqual(len(sign), 32)  # MD5 hex digest length
        self.assertEqual(sign, public_sign)

    def test_sign_excludes_reserved_keys(self):
        """签名排除 sign/contextid/token 字段"""
        params_base = {
            "appkey": TEST_APP_KEY,
            "method": "erp.storage.goodslist",
            "timestamp": "2024-01-01 00:00:00",
            "version": "v1.0",
            "bizcontent": "{}",
        }
        sign1 = self.client._generate_sign(params_base)

        params_with_extra = {**params_base, "sign": "xxx", "contextid": "yyy", "token": "zzz"}
        sign2 = self.client._generate_sign(params_with_extra)

        self.assertEqual(sign1, sign2)

    def test_sign_deterministic(self):
        """同一参数多次签名结果一致"""
        params = {
            "appkey": TEST_APP_KEY,
            "method": "erp.storage.goodslist",
            "timestamp": "2024-01-01 00:00:00",
            "version": "v1.0",
            "bizcontent": json.dumps({"goodsNo": "TEST001"}),
        }
        sign1 = self.client._generate_sign(params)
        sign2 = self.client._generate_sign(params)
        self.assertEqual(sign1, sign2)

    def test_sign_order_independent(self):
        """参数顺序不影响签名"""
        params1 = {"appkey": TEST_APP_KEY, "method": "erp.storage.goodslist", "version": "v1.0"}
        params2 = {"version": "v1.0", "appkey": TEST_APP_KEY, "method": "erp.storage.goodslist"}
        self.assertEqual(
            self.client._generate_sign(params1),
            self.client._generate_sign(params2),
        )

    def test_build_signed_openapi_params_includes_required_public_fields(self):
        params = build_signed_openapi_params(
            method="erp.warehouse.get",
            bizcontent={"pageIndex": 0, "pageSize": 1},
            app_key=TEST_APP_KEY,
            app_secret=TEST_APP_SECRET,
            timestamp="2026-05-06 12:00:00",
            context_id="CTX1",
        )

        self.assertEqual(params["method"], "erp.warehouse.get")
        self.assertEqual(params["appkey"], TEST_APP_KEY)
        self.assertEqual(params["version"], "v1.0")
        self.assertEqual(params["contenttype"], "json")
        self.assertEqual(params["timestamp"], "2026-05-06 12:00:00")
        self.assertEqual(params["bizcontent"], '{"pageIndex": 0, "pageSize": 1}')
        self.assertEqual(params["contextid"], "CTX1")
        self.assertEqual(len(params["sign"]), 32)
        params_without_context = {k: v for k, v in params.items() if k != "contextid"}
        self.assertEqual(
            params["sign"],
            generate_openapi_sign(params_without_context, app_secret=TEST_APP_SECRET),
        )


class TestResponseParsing(unittest.TestCase):
    """测试响应解析"""

    def setUp(self):
        self.client = JackyunAPI(
            app_key=TEST_APP_KEY,
            app_secret=TEST_APP_SECRET,
            api_url="https://open.jackyun.com/open/openapi/do",
        )

    @patch("jackyun_api.requests.Session.post")
    def test_success_response(self, mock_post):
        """正常响应解析"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "200",
            "result": {"data": [{"goodsNo": "A001"}], "totalCount": 1},
        }
        mock_post.return_value = mock_resp

        result = self.client.call("erp.storage.goodslist", {})
        self.assertIn("result", result)
        self.assertEqual(result["result"]["data"][0]["goodsNo"], "A001")
        posted_data = mock_post.call_args.kwargs["data"]
        self.assertEqual(posted_data["appkey"], TEST_APP_KEY)
        self.assertEqual(posted_data["version"], "v1.0")
        self.assertEqual(posted_data["contenttype"], "json")
        self.assertEqual(len(posted_data["sign"]), 32)

    @patch("jackyun_api.config.JACKYUN_CALL_STRATEGY", "auto")
    @patch("jackyun_api.config.JACKYUN_MCP_TOKEN", "")
    @patch("jackyun_api.config.JACKYUN_CLI_ENABLED", False)
    @patch("jackyun_api.requests.Session.post")
    def test_auto_strategy_falls_back_to_signed_http_without_mcp_token(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"code": "200", "result": {"data": []}}
        mock_post.return_value = mock_resp

        result = self.client.call("erp.stockquantity.get", {"pageIndex": 0, "pageSize": 1})

        self.assertEqual(result["code"], "200")
        self.assertTrue(mock_post.called)

    def test_authorized_appkey_is_recorded(self):
        self.assertEqual(config.JACKYUN_AUTHORIZED_APP_KEY, config.JACKYUN_APP_KEY)

    @patch("jackyun_api.requests.Session.post")
    def test_error_response_raises(self, mock_post):
        """错误响应抛出异常"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "500",
            "msg": "系统错误",
        }
        mock_post.return_value = mock_resp

        with self.assertRaises(JackyunAPIError):
            self.client.call("erp.storage.goodslist", {})

    @patch("jackyun_api.requests.Session.post")
    @patch("jackyun_api.config.MAX_RETRIES", 1)
    def test_network_error_raises(self, mock_post):
        """网络异常抛出 JackyunNetworkError"""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("timeout")

        with self.assertRaises(JackyunNetworkError):
            self.client.call("erp.storage.goodslist", {})


if __name__ == "__main__":
    unittest.main()
