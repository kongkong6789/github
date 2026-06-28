"""
参数校验器

提供通用的参数校验函数，在调用 API 前检查必填字段和数据格式。
"""
import re
from typing import Any

from jackyun_api import JackyunValidationError


def require_fields(data: dict, fields: list[tuple[str, str]]) -> list[str]:
    """
    检查必填字段，返回缺失字段的中文名列表

    :param data: 待检查的数据字典
    :param fields: [(field_key, field_label), ...] 字段列表
    :return: 缺失字段标签列表（空列表表示全部通过）
    """
    missing = []
    for key, label in fields:
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(label)
    return missing


def require_fields_or_raise(data: dict, fields: list[tuple[str, str]]):
    """检查必填字段，缺失时抛出 JackyunValidationError"""
    missing = require_fields(data, fields)
    if missing:
        raise JackyunValidationError(
            f"缺少必填字段：{'、'.join(missing)}"
        )


def validate_phone(phone: str) -> bool:
    """校验手机号格式（大陆）"""
    return bool(re.match(r"^1[3-9]\d{9}$", phone.strip()))


def validate_goods_no(goods_no: str) -> bool:
    """校验货品编号格式（非空，无特殊字符）"""
    if not goods_no or not goods_no.strip():
        return False
    return bool(re.match(r"^[\w\-\.]+$", goods_no.strip()))


def validate_amount(amount: Any) -> bool:
    """校验金额（非负数）"""
    try:
        val = float(amount)
        return val >= 0
    except (TypeError, ValueError):
        return False


def validate_quantity(qty: Any) -> bool:
    """校验数量（正整数）"""
    try:
        val = int(qty)
        return val > 0
    except (TypeError, ValueError):
        return False


def validate_date_str(date_str: str) -> bool:
    """校验日期字符串格式 YYYY-MM-DD"""
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date_str.strip()))


def validate_datetime_str(dt_str: str) -> bool:
    """校验日期时间字符串格式 YYYY-MM-DD HH:MM:SS"""
    return bool(re.match(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        dt_str.strip(),
    ))


def format_missing_fields_prompt(missing: list[str]) -> str:
    """生成缺失字段的用户提示"""
    lines = ["创建该单据还需要以下信息："]
    for i, field in enumerate(missing, 1):
        lines.append(f"  {i}. {field}")
    lines.append("\n请补充以上信息后重试。")
    return "\n".join(lines)
