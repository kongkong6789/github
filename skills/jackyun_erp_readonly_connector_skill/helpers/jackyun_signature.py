"""
Reusable JackYun OpenAPI signing helpers.

Use this module whenever a direct signed HTTP request is needed. Do not
reimplement signing in ad hoc scripts; the request params and sign must be
constructed from the exact same serialized values.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

import config


SIGN_EXCLUDED_KEYS = {"sign", "contextid", "token"}


def generate_openapi_sign(params: dict[str, Any], app_secret: str | None = None) -> str:
    """
    Generate JackYun OpenAPI MD5 signature.

    Algorithm:
    1. Exclude sign/contextid/token.
    2. Sort remaining keys alphabetically.
    3. Concatenate key + value.
    4. Wrap with appSecret on both sides.
    5. Lowercase the whole string, then MD5 hex digest.
    """
    secret = app_secret if app_secret is not None else config.JACKYUN_APP_SECRET
    filtered = {
        k: v for k, v in (params or {}).items()
        if k not in SIGN_EXCLUDED_KEYS
    }
    sign_body = "".join(f"{key}{filtered[key]}" for key in sorted(filtered))
    sign_text = f"{secret}{sign_body}{secret}".lower()
    return hashlib.md5(sign_text.encode("utf-8")).hexdigest()


def build_signed_openapi_params(
    method: str,
    bizcontent: dict[str, Any] | None,
    app_key: str | None = None,
    app_secret: str | None = None,
    timestamp: str | datetime | None = None,
    context_id: str = "",
) -> dict[str, Any]:
    """
    Build the complete form payload for direct JackYun OpenAPI HTTP calls.

    The returned dict is ready to send as form data to
    https://open.jackyun.com/open/openapi/do.
    """
    if isinstance(timestamp, datetime):
        timestamp_text = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    else:
        timestamp_text = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "method": method,
        "appkey": app_key or config.JACKYUN_APP_KEY,
        "version": "v1.0",
        "contenttype": "json",
        "timestamp": timestamp_text,
        "bizcontent": json.dumps(bizcontent or {}, ensure_ascii=False),
    }
    params["sign"] = generate_openapi_sign(params, app_secret=app_secret)
    if context_id:
        params["contextid"] = context_id
    return params
