"""
吉客云开放平台 API 通用客户端

功能：
- 签名算法：MD5(appsecret + 排序拼接参数 + appsecret).lower()
- 请求格式：POST application/x-www-form-urlencoded
- 自动分页遍历（pageIndex 模式 + contextid 模式）
- 指数退避重试（网络错误/5xx）
- 频率控制（防触发限流）
- 统一错误处理
"""
import time
import logging
import json
from typing import Optional

import requests

import config
from helpers.jackyun_signature import build_signed_openapi_params, generate_openapi_sign
from helpers.jkyun_cli import JackyunCLIUnavailable, call_cli
from helpers.mcp_runtime import JackyunMCPUnavailable, call_mcp_tool, supports_method as mcp_supports_method

logger = logging.getLogger(__name__)


class JackyunAPIError(Exception):
    """吉客云 API 业务错误"""

    # 常见错误码 → 用户友好提示
    ERROR_MESSAGES = {
        "10001": "签名验证失败，请检查 AppKey/AppSecret 配置",
        "10002": "缺少必要参数，请检查请求参数",
        "10003": "应用未授权此接口，请到吉客云开放平台开通权限",
        "10004": "请求频率超限，请稍后再试",
        "10005": "接口不存在，请确认接口方法名",
        "10006": "业务参数错误，请检查传入数据",
    }

    def __init__(self, message: str, code: str = None, method: str = None):
        self.code = code
        self.method = method
        friendly = self.ERROR_MESSAGES.get(str(code), "")
        if friendly:
            message = f"{friendly}（{message}）"
        super().__init__(f"[{method or 'unknown'}] {message} (code={code})")


class JackyunNetworkError(Exception):
    """网络/超时错误"""
    pass


class JackyunValidationError(Exception):
    """参数校验错误"""
    pass


class JackyunAPI:
    """吉客云开放平台 API 通用客户端"""

    def __init__(
        self,
        app_key: str = None,
        app_secret: str = None,
        api_url: str = None,
    ):
        self.app_key = app_key or config.JACKYUN_APP_KEY
        self.app_secret = app_secret or config.JACKYUN_APP_SECRET
        self.api_url = api_url or config.JACKYUN_API_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        })
        self._last_call_time = 0.0

    def _generate_sign(self, params: dict) -> str:
        """
        生成吉客云 API 签名。

        Deprecated internal compatibility wrapper. New code should import
        helpers.jackyun_signature.generate_openapi_sign directly.
        """
        return generate_openapi_sign(params, app_secret=self.app_secret)

    def _throttle(self):
        """频率控制：确保连续调用间隔不低于 API_CALL_INTERVAL"""
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < config.API_CALL_INTERVAL:
            time.sleep(config.API_CALL_INTERVAL - elapsed)
        self._last_call_time = time.time()

    def call(
        self,
        method: str,
        bizcontent: dict,
        context_id: str = "",
    ) -> dict:
        """
        调用吉客云 API（带重试）

        :param method: API 方法名，如 erp.storage.goodslist
        :param bizcontent: 业务参数字典
        :param context_id: 分页上下文 ID
        :return: 完整响应字典
        :raises JackyunAPIError: 业务错误
        :raises JackyunNetworkError: 网络错误（重试耗尽后）
        """
        strategy = (config.JACKYUN_CALL_STRATEGY or "auto").lower()
        if strategy == "mcp":
            return call_mcp_tool(method, bizcontent)
        if strategy == "cli":
            return call_cli(method, bizcontent)
        if strategy == "auto" and not context_id:
            if mcp_supports_method(method):
                try:
                    return call_mcp_tool(method, bizcontent)
                except (JackyunMCPUnavailable, requests.exceptions.RequestException, ValueError) as exc:
                    logger.info("[%s] MCP unavailable, falling back: %s", method, exc)
            if config.JACKYUN_CLI_ENABLED:
                try:
                    return call_cli(method, bizcontent)
                except JackyunCLIUnavailable as exc:
                    logger.debug("[%s] CLI unavailable, falling back: %s", method, exc)
        return self._call_signed_http(method, bizcontent, context_id=context_id)

    def _call_signed_http(
        self,
        method: str,
        bizcontent: dict,
        context_id: str = "",
    ) -> dict:
        """Call JackYun OpenAPI directly with the existing MD5 signature flow."""
        self._throttle()

        params = build_signed_openapi_params(
            method=method,
            bizcontent=bizcontent,
            app_key=self.app_key,
            app_secret=self.app_secret,
            context_id=context_id,
        )

        last_error = None
        for attempt in range(config.MAX_RETRIES):
            try:
                start = time.time()
                resp = self.session.post(
                    self.api_url,
                    data=params,
                    timeout=config.API_TIMEOUT,
                )
                elapsed_ms = int((time.time() - start) * 1000)

                if resp.status_code in config.RETRY_STATUS_CODES:
                    logger.warning(
                        f"[{method}] HTTP {resp.status_code}，"
                        f"第 {attempt + 1}/{config.MAX_RETRIES} 次重试"
                    )
                    last_error = JackyunNetworkError(
                        f"HTTP {resp.status_code}"
                    )
                    time.sleep(config.RETRY_BACKOFF * (2 ** attempt))
                    continue

                resp.raise_for_status()
                result = resp.json()

                logger.debug(
                    f"[{method}] {elapsed_ms}ms | "
                    f"code={result.get('code')} | "
                    f"响应片段: {json.dumps(result, ensure_ascii=False)[:200]}"
                )

                resp_code = str(result.get("code", ""))
                if resp_code not in ("10000", "200"):
                    error_msg = result.get("msg", "未知错误")
                    raise JackyunAPIError(error_msg, code=resp_code, method=method)

                return result

            except requests.exceptions.Timeout:
                logger.warning(
                    f"[{method}] 请求超时，"
                    f"第 {attempt + 1}/{config.MAX_RETRIES} 次重试"
                )
                last_error = JackyunNetworkError(f"[{method}] 请求超时")
                time.sleep(config.RETRY_BACKOFF * (2 ** attempt))

            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    f"[{method}] 连接错误: {e}，"
                    f"第 {attempt + 1}/{config.MAX_RETRIES} 次重试"
                )
                last_error = JackyunNetworkError(f"[{method}] 连接错误: {e}")
                time.sleep(config.RETRY_BACKOFF * (2 ** attempt))

            except JackyunAPIError:
                raise  # 业务错误不重试

            except requests.exceptions.RequestException as e:
                raise JackyunNetworkError(f"[{method}] 请求失败: {e}")

        raise last_error or JackyunNetworkError(f"[{method}] 重试耗尽")

    def call_paged(
        self,
        method: str,
        bizcontent: dict,
        page_size: int = None,
        max_pages: int = None,
        data_key: str = "data",
    ) -> list:
        """
        自动分页遍历，返回所有结果

        :param method: API 方法名
        :param bizcontent: 业务参数（不含 pageIndex/pageSize）
        :param page_size: 每页大小
        :param max_pages: 最大页数限制
        :param data_key: 响应中数据列表的 key
        :return: 所有页数据合并后的列表
        """
        page_size = page_size or config.DEFAULT_PAGE_SIZE
        max_pages = max_pages or config.MAX_PAGE_LIMIT
        all_data = []
        page_index = 0
        context_id = ""

        while page_index < max_pages:
            paged_content = {**bizcontent, "pageIndex": page_index, "pageSize": page_size}
            result = self.call(method, paged_content, context_id=context_id)

            data = result.get("result", {})
            if isinstance(data, dict):
                items = data.get(data_key, [])
                if isinstance(items, dict):
                    items = [items] if items else []
            elif isinstance(data, list):
                items = data
            else:
                items = []

            if not items:
                break

            all_data.extend(items)

            total = 0
            if isinstance(data, dict):
                total = data.get("totalCount", 0) or data.get("total", 0)

            if total and len(all_data) >= total:
                break

            if len(items) < page_size:
                break

            # 获取下一页的 contextid
            context_id = result.get("contextid", "") or ""
            page_index += 1

            logger.debug(
                f"[{method}] 分页遍历中... page={page_index}, "
                f"已获取 {len(all_data)} 条"
            )

        logger.info(
            f"[{method}] 分页遍历完成，共 {len(all_data)} 条"
        )
        return all_data


# 全局单例（供各模块使用）
_client: Optional[JackyunAPI] = None


def get_client() -> JackyunAPI:
    """获取全局 API 客户端单例"""
    global _client
    if _client is None:
        _client = JackyunAPI()
    return _client
