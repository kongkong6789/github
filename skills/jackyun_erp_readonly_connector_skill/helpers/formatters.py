"""
结果格式化工具

将 API 返回的原始数据转换为用户友好的展示格式。
"""
from datetime import datetime
from typing import Optional

from helpers.constants import (
    INOUT_TYPES, CHECK_STATUS, CHARGE_TYPES,
    TRADE_STATUS, LOGISTICS_CODES,
)


def format_amount(amount, currency: str = "¥") -> str:
    """格式化金额：千分位 + 2位小数"""
    try:
        val = float(amount)
        return f"{currency}{val:,.2f}"
    except (TypeError, ValueError):
        return str(amount)


def format_quantity(qty) -> str:
    """格式化数量"""
    try:
        val = int(qty)
        return f"{val:,}"
    except (TypeError, ValueError):
        return str(qty)


def format_datetime(dt_str: str) -> str:
    """格式化日期时间显示"""
    if not dt_str:
        return "-"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return dt_str


def format_check_status(status_code) -> str:
    """格式化审核状态"""
    try:
        code = int(status_code)
        return CHECK_STATUS.get(code, f"未知({code})")
    except (TypeError, ValueError):
        return str(status_code)


def format_inout_type(type_code) -> str:
    """格式化出入库类型"""
    try:
        code = int(type_code)
        return INOUT_TYPES.get(code, f"未知({code})")
    except (TypeError, ValueError):
        return str(type_code)


def format_charge_type(type_code) -> str:
    """格式化结算方式"""
    try:
        code = int(type_code)
        return CHARGE_TYPES.get(code, f"未知({code})")
    except (TypeError, ValueError):
        return str(type_code)


def format_trade_status(status_code) -> str:
    """格式化销售单状态"""
    try:
        code = int(status_code)
        return TRADE_STATUS.get(code, f"未知({code})")
    except (TypeError, ValueError):
        return str(status_code)


def format_logistics_name(code: str) -> str:
    """物流公司编码 → 名称"""
    return LOGISTICS_CODES.get(code.upper(), code)


def format_goods_table(goods_list: list) -> str:
    """
    格式化货品列表为表格

    :param goods_list: [{"goodsNo": "...", "goodsName": "...", "qty": N, "price": N}, ...]
    :return: Markdown 表格字符串
    """
    if not goods_list:
        return "（无货品明细）"

    lines = [
        "| 序号 | 货品编号 | 货品名称 | 数量 | 单价 | 金额 |",
        "|------|----------|----------|------|------|------|",
    ]
    total_amount = 0
    for i, g in enumerate(goods_list, 1):
        no = g.get("goodsNo", "-")
        name = g.get("goodsName", "-")
        qty = g.get("qty", g.get("quantity", 0))
        price = g.get("price", g.get("unitPrice", 0))
        try:
            amount = float(qty) * float(price)
            total_amount += amount
        except (TypeError, ValueError):
            amount = 0
        lines.append(
            f"| {i} | {no} | {name} | "
            f"{format_quantity(qty)} | {format_amount(price)} | "
            f"{format_amount(amount)} |"
        )
    lines.append(f"| | | **合计** | | | **{format_amount(total_amount)}** |")
    return "\n".join(lines)


def format_inventory_table(inventory_list: list) -> str:
    """
    格式化库存列表为表格

    :param inventory_list: [{"warehouseName": "...", "goodsNo": "...", "qty": N, ...}, ...]
    :return: Markdown 表格字符串
    """
    if not inventory_list:
        return "（无库存数据）"

    lines = [
        "| 仓库 | 货品编号 | 货品名称 | 实际库存 | 可用库存 | 占用库存 |",
        "|------|----------|----------|----------|----------|----------|",
    ]
    for item in inventory_list:
        wh = item.get("warehouseName", "-")
        no = item.get("goodsNo", "-")
        name = item.get("goodsName", "-")
        actual = item.get("actualQty", item.get("qty", 0))
        available = item.get("availableQty", actual)
        locked = item.get("lockedQty", 0)
        lines.append(
            f"| {wh} | {no} | {name} | "
            f"{format_quantity(actual)} | {format_quantity(available)} | "
            f"{format_quantity(locked)} |"
        )
    return "\n".join(lines)


def format_order_summary(order: dict) -> str:
    """
    格式化单据摘要（通用）

    :param order: 单据数据字典
    :return: 格式化字符串
    """
    lines = []
    field_map = [
        ("billNo", "单据编号"),
        ("outBillNo", "外部单号"),
        ("channelName", "销售渠道"),
        ("warehouseName", "仓库"),
        ("checkStatus", "审核状态"),
        ("gmtCreate", "创建时间"),
        ("gmtModified", "修改时间"),
    ]
    for key, label in field_map:
        value = order.get(key)
        if value is not None:
            if key == "checkStatus":
                value = format_check_status(value)
            elif key in ("gmtCreate", "gmtModified"):
                value = format_datetime(str(value))
            lines.append(f"  {label}：{value}")
    return "\n".join(lines) if lines else "（无数据）"


def _format_timestamp(ts) -> str:
    """将时间戳（毫秒）转换为日期字符串"""
    if not ts:
        return "-"
    try:
        val = int(ts) / 1000  # 毫秒→秒
        return datetime.fromtimestamp(val).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return str(ts)


def format_batch_stock_table(batch_list: list) -> str:
    """
    格式化批次库存表格（含效期）

    :param batch_list: erp.batchstockquantity.get 返回的 goodsStockQuantity 列表
    :return: Markdown 表格字符串
    """
    if not batch_list:
        return "（无批次库存数据）"

    lines = [
        "| 仓库 | 货品编号 | 货品名称 | 规格 | 批次编号 | 生产批号 | "
        "当前库存 | 可用 | 锁定 | 生产日期 | 到期日期 | 质保期 |",
        "|------|----------|----------|------|----------|----------|"
        "----------|------|------|----------|----------|--------|",
    ]
    for item in batch_list:
        wh = item.get("warehouseName", "-")
        gno = item.get("goodsNo", "-")
        gname = item.get("goodsName", "-")
        sname = item.get("skuName", "-")
        bno = item.get("batchNo", "-")
        bnum = item.get("batchNumber", "-")
        cur = item.get("currentQuantity", 0)
        use = item.get("useQuantity", 0)
        locked = item.get("lockedQuantity", 0)
        prod_date = _format_timestamp(item.get("productionDate"))
        exp_date = item.get("expirationDate", "-")
        shelf_life = item.get("shelfLife", "")
        shelf_unit = item.get("shelfLiftUnit", "")
        shelf_str = f"{shelf_life}{shelf_unit}" if shelf_life else "-"

        lines.append(
            f"| {wh} | {gno} | {gname} | {sname} | {bno} | {bnum} | "
            f"{format_quantity(cur)} | {format_quantity(use)} | {format_quantity(locked)} | "
            f"{prod_date} | {exp_date} | {shelf_str} |"
        )
    return "\n".join(lines)


def format_sku_stock_table(sku_list: list) -> str:
    """
    格式化分仓库存表格（规格模式）

    :param sku_list: erp-stock.stock.skulist 返回的库存列表
    :return: Markdown 表格字符串
    """
    if not sku_list:
        return "（无分仓库存数据）"

    lines = [
        "| 仓库 | 当前库存 | 可用库存 | 锁定待发 | 采购在途 | 可用量 | 成本价 |",
        "|------|----------|----------|----------|----------|--------|--------|",
    ]
    for item in sku_list:
        wh = item.get("warehouseName", "-")
        cur = item.get("currentQuantity", 0)
        can_use = item.get("canUseQuantity", 0)
        locked = item.get("lockingQuantity", 0)
        purch = item.get("purchasingQuantity", 0)
        avail = item.get("availableQuantity", 0)
        cost = item.get("costPrice", "-")

        lines.append(
            f"| {wh} | {format_quantity(cur)} | {format_quantity(can_use)} | "
            f"{format_quantity(locked)} | {format_quantity(purch)} | "
            f"{format_quantity(avail)} | {format_amount(cost) if cost != '-' else '-'} |"
        )
    return "\n".join(lines)
