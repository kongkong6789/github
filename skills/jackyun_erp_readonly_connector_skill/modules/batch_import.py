"""
批量导入模块

从 Excel / CSV 表格中读取销售单数据，智能识别列映射，批量创建销售单。

★ 核心流程：
1. 读取表格 → 智能列映射 → 数据清洗
2. 逐行校验（必填字段、手机号格式、数量格式）
3. 渠道→仓库→物流 自动解析（支持缓存避免重复查询）
4. 批量创建，收集每行结果（成功/失败/跳过）
5. 输出汇总报告

★ 支持的列名映射（中英文 + 常见别名）：
  渠道/店铺/shopName → shopName
  收件人/姓名/receiverName → receiverName
  手机/电话/mobile/phone → mobile
  省/state → state
  市/city → city
  区/district → district
  地址/address → address
  货品编号/SKU/goodsNo → goodsNo
  数量/sellCount/qty → sellCount
  单价/sellPrice/price → sellPrice
  备注/remark/sellerMemo → sellerMemo
  仓库/warehouseName → warehouseName（可选，不填则自动匹配）
  物流/logisticName → logisticName（可选，不填则自动匹配）
  类型/orderType → orderType（JY=寄样, BF=补发, PT=普通手工, 默认 JY）
"""
import logging
import os
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from jackyun_api import JackyunAPIError, JackyunValidationError
from helpers.matching import normalize_lookup_text
from helpers.validators import validate_phone, validate_quantity
from modules.sales_order import (
    create_sample_order,
    create_manual_order,
    resolve_channel_warehouse_logistics,
    generate_online_trade_no,
    _extract_trade_no,
    preflight_sales_order,
    query_trade_by_no,
)

logger = logging.getLogger(__name__)


# ==================== 列名映射 ====================

# 表格列名 → API 字段名 的映射关系（支持中英文 + 常见别名）
COLUMN_ALIASES = {
    # 渠道
    "shopName": "shopName",
    "渠道": "shopName",
    "渠道名称": "shopName",
    "店铺": "shopName",
    "店铺名称": "shopName",
    "销售渠道": "shopName",
    "销售渠道名称": "shopName",
    "channel": "shopName",

    # 收件人
    "receiverName": "receiverName",
    "收件人": "receiverName",
    "收件人姓名": "receiverName",
    "收货人": "receiverName",
    "收货人姓名": "receiverName",
    "姓名": "receiverName",
    "客户": "receiverName",
    "客户姓名": "receiverName",
    "receiver": "receiverName",

    # 手机号
    "mobile": "mobile",
    "phone": "mobile",
    "手机": "mobile",
    "手机号": "mobile",
    "手机号码": "mobile",
    "电话": "mobile",
    "联系电话": "mobile",
    "联系方式": "mobile",

    # 省
    "state": "state",
    "省": "state",
    "省份": "state",
    "province": "state",

    # 市
    "city": "city",
    "市": "city",
    "城市": "city",
    "市（区）": "city",
    "市(区)": "city",

    # 区
    "district": "district",
    "区": "district",
    "区县": "district",
    "县": "district",
    "区（县）": "district",
    "区(县)": "district",

    # 镇
    "town": "town",
    "镇": "town",
    "街道": "town",
    "乡镇": "town",

    # 地址
    "address": "address",
    "地址": "address",
    "详细地址": "address",
    "收件地址": "address",
    "收货地址": "address",

    # 货品编号
    "goodsNo": "goodsNo",
    "货品编号": "goodsNo",
    "商品编号": "goodsNo",
    "SKU": "goodsNo",
    "sku": "goodsNo",
    "编号": "goodsNo",
    "条码": "goodsNo",
    "barcode": "goodsNo",

    # 货品名称
    "goodsName": "goodsName",
    "货品名称": "goodsName",
    "商品名称": "goodsName",
    "品名": "goodsName",
    "产品名称": "goodsName",

    # 规格
    "specName": "specName",
    "规格": "specName",
    "规格名称": "specName",
    "spec": "specName",

    # 批次
    "batchNo": "batchNo",
    "批次号": "batchNo",
    "批号": "batchNo",
    "生产批号": "batchNo",

    # 数量
    "sellCount": "sellCount",
    "数量": "sellCount",
    "qty": "sellCount",
    "quantity": "sellCount",
    "寄样数量": "sellCount",
    "发货数量": "sellCount",

    # 单价
    "sellPrice": "sellPrice",
    "单价": "sellPrice",
    "price": "sellPrice",
    "售价": "sellPrice",

    # 金额
    "sellTotal": "sellTotal",
    "金额": "sellTotal",
    "总价": "sellTotal",
    "total": "sellTotal",
    "amount": "sellTotal",

    # 备注
    "sellerMemo": "sellerMemo",
    "备注": "sellerMemo",
    "remark": "sellerMemo",
    "留言": "sellerMemo",
    "客服备注": "sellerMemo",
    "内部备注": "sellerMemo",
    "客户备注": "buyerMemo",
    "买家备注": "buyerMemo",
    "buyerMemo": "buyerMemo",

    # 客户/网店订单
    "customerName": "customerName",
    "客户名称": "customerName",
    "客户账号": "customerName",
    "网店订单号": "onlineTradeNo",
    "平台订单号": "onlineTradeNo",
    "onlineTradeNo": "onlineTradeNo",

    # 业务员 / 创建人
    "sellerName": "sellerName",
    "业务员": "sellerName",
    "创建人": "sellerName",
    "申请人": "sellerName",
    "销售员": "sellerName",

    # 仓库（可选）
    "warehouseName": "warehouseName",
    "仓库": "warehouseName",
    "仓库名称": "warehouseName",
    "发货仓库": "warehouseName",
    "warehouse": "warehouseName",

    # 物流（可选）
    "logisticName": "logisticName",
    "物流": "logisticName",
    "物流公司": "logisticName",
    "快递": "logisticName",
    "logistics": "logisticName",

    # 订单类型
    "orderType": "orderType",
    "类型": "orderType",
    "订单类型": "orderType",
    "单据类型": "orderType",
    "标记": "orderType",
    "订单标记": "orderType",

    # 单位
    "unit": "unit",
    "单位": "unit",
}

# 订单类型别名
ORDER_TYPE_ALIASES = {
    "寄样": "JY",
    "样品": "JY",
    "样品单": "JY",
    "寄样单": "JY",
    "JY": "JY",
    "jy": "JY",
    "补发": "BF",
    "补发单": "BF",
    "BF": "BF",
    "bf": "BF",
    "补寄": "BF",
    "普通": "PT",
    "手工": "PT",
    "PT": "PT",
    "pt": "PT",
    "manual": "PT",
    "普通手工": "PT",
}
NORMALIZED_COLUMN_ALIASES = {
    normalize_lookup_text(alias): field
    for alias, field in COLUMN_ALIASES.items()
}
NORMALIZED_ORDER_TYPE_ALIASES = {
    normalize_lookup_text(alias): value
    for alias, value in ORDER_TYPE_ALIASES.items()
}

# 必须在表格中存在的字段
REQUIRED_MAPPED_FIELDS = ["shopName", "receiverName", "mobile", "address", "goodsNo", "sellCount"]


# ==================== 读取表格 ====================

def read_spreadsheet(file_path: str, sheet_name: str = None) -> pd.DataFrame:
    """
    读取 Excel 或 CSV 文件

    :param file_path: 文件路径（.xlsx/.xls/.csv/.tsv）
    :param sheet_name: 工作表名（Excel 可选，默认第一个表）
    :return: DataFrame
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".csv",):
        for encoding in ("utf-8", "gbk", "gb2312", "utf-8-sig"):
            try:
                return pd.read_csv(file_path, encoding=encoding, dtype=str)
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError(f"无法识别文件编码: {file_path}")
    elif ext in (".tsv",):
        return pd.read_csv(file_path, sep="\t", dtype=str)
    elif ext in (".xlsx", ".xls", ".xlsm"):
        kwargs = {"dtype": str}
        if sheet_name:
            kwargs["sheet_name"] = sheet_name
        return pd.read_excel(file_path, **kwargs)
    else:
        raise ValueError(f"不支持的文件格式: {ext}（支持 .xlsx, .xls, .csv, .tsv）")


# ==================== 智能列映射 ====================

def auto_map_columns(df: pd.DataFrame) -> dict:
    """
    智能识别列名，映射到 API 字段名

    :param df: 原始 DataFrame
    :return: {原始列名: API字段名} 映射字典
    """
    mapping = {}
    mapped_fields = set()

    for col in df.columns:
        col_clean = str(col).strip()
        api_field = COLUMN_ALIASES.get(col_clean) or NORMALIZED_COLUMN_ALIASES.get(normalize_lookup_text(col_clean))
        if api_field:
            if api_field not in mapped_fields:
                mapping[col] = api_field
                mapped_fields.add(api_field)

    return mapping


def check_required_columns(column_mapping: dict) -> list:
    """
    检查必填列是否都已映射

    :return: 缺失的必填字段列表
    """
    mapped_fields = set(column_mapping.values())
    missing = []
    field_labels = {
        "shopName": "渠道名称（渠道/店铺/shopName）",
        "receiverName": "收件人（收件人/姓名/receiverName）",
        "mobile": "手机号（手机/电话/mobile）",
        "address": "地址（地址/详细地址/address）",
        "goodsNo": "货品编号（货品编号/SKU/goodsNo）",
        "sellCount": "数量（数量/qty/sellCount）",
    }
    for field in REQUIRED_MAPPED_FIELDS:
        if field not in mapped_fields:
            missing.append(field_labels.get(field, field))
    return missing


# ==================== 数据清洗 ====================

def clean_row(row: dict) -> dict:
    """清洗单行数据：去空格、类型转换"""
    cleaned = {}
    for k, v in row.items():
        if pd.isna(v) or v is None:
            cleaned[k] = ""
        else:
            cleaned[k] = str(v).strip()
    return cleaned


def normalize_order_type(raw: str) -> str:
    """标准化订单类型"""
    raw_text = str(raw or "").strip()
    return ORDER_TYPE_ALIASES.get(raw_text) or NORMALIZED_ORDER_TYPE_ALIASES.get(normalize_lookup_text(raw_text), "JY")


# ==================== 行校验 ====================

def validate_row(row: dict, row_index: int) -> list:
    """
    校验单行数据

    :return: 错误信息列表（空=通过）
    """
    errors = []

    if not row.get("shopName"):
        errors.append("缺少渠道名称")
    if not row.get("receiverName"):
        errors.append("缺少收件人")
    if not row.get("mobile"):
        errors.append("缺少手机号")
    elif not validate_phone(row["mobile"]):
        errors.append(f"手机号格式不正确: {row['mobile']}")
    if not row.get("address"):
        errors.append("缺少地址")
    if not row.get("goodsNo"):
        errors.append("缺少货品编号")
    if not row.get("sellCount"):
        errors.append("缺少数量")
    elif not validate_quantity(row["sellCount"]):
        errors.append(f"数量必须为正整数: {row['sellCount']}")
    if not row.get("sellerName"):
        errors.append("缺少业务员姓名；业务员必须填写员工姓名，登记人会同步写入该姓名")
    if normalize_order_type(row.get("orderType", "JY")) == "JY" and not row.get("customerName"):
        errors.append("寄样单缺少客户名称；请在表格客户名称/客户账号列填写，或传入 default_customer_name")

    return errors


# ==================== 多货品行合并 ====================

def group_orders_from_rows(rows: list) -> list:
    """
    将多行数据合并为订单（同一网店订单号优先，其次同一收件人+手机+渠道 = 同一个订单的多个货品）

    ★ 合并规则：onlineTradeNo 优先；没有网店订单号时 shopName + receiverName + mobile + address 完全相同的行，
      合并为一个订单的多个货品明细。

    :param rows: [{mapped API fields}, ...]
    :return: [{"order": {...}, "goods_list": [{...}, ...]}, ...]
    """
    order_map = {}

    for row in rows:
        # 生成合并 key
        key = (
            row.get("onlineTradeNo", ""),
            row.get("shopName", ""),
            row.get("receiverName", ""),
            row.get("mobile", ""),
            row.get("address", ""),
        )

        goods_item = {
            "goodsNo": row.get("goodsNo", ""),
            "sellCount": row.get("sellCount", "1"),
            "sellPrice": row.get("sellPrice", "0"),
            "sellTotal": row.get("sellTotal", "0"),
            "specName": row.get("specName", "默认"),
            "unit": row.get("unit", "Pcs"),
        }
        if row.get("goodsName"):
            goods_item["goodsName"] = row["goodsName"]
        if row.get("batchNo"):
            goods_item["batchNo"] = row["batchNo"]

        if key not in order_map:
            order_map[key] = {
                "order": {
                    "shopName": row.get("shopName", ""),
                    "receiverName": row.get("receiverName", ""),
                    "mobile": row.get("mobile", ""),
                    "state": row.get("state", ""),
                    "city": row.get("city", ""),
                    "district": row.get("district", ""),
                    "town": row.get("town", ""),
                    "address": row.get("address", ""),
                    "sellerMemo": row.get("sellerMemo", ""),
                    "buyerMemo": row.get("buyerMemo", ""),
                    "sellerName": row.get("sellerName", ""),
                    "customerName": row.get("customerName", ""),
                    "onlineTradeNo": row.get("onlineTradeNo", ""),
                    "warehouseName": row.get("warehouseName", ""),
                    "logisticName": row.get("logisticName", ""),
                    "orderType": normalize_order_type(row.get("orderType", "JY")),
                },
                "goods_list": [],
                "source_rows": [],
            }

        order_map[key]["goods_list"].append(goods_item)
        order_map[key]["source_rows"].append(row.get("_row_index", 0))

    return list(order_map.values())


# ==================== 批量创建 ====================

def batch_create_orders(
    file_path: str,
    sheet_name: str = None,
    dry_run: bool = False,
    preflight: bool = True,
    create_interval: float = 0.0,
    order_type_override: str = None,
    default_shop_name: str = None,
    default_seller_name: str = None,
    default_customer_name: str = None,
) -> dict:
    """
    ★ 核心函数：从 Excel/CSV 批量导入并创建销售单

    :param file_path: 表格文件路径
    :param sheet_name: 工作表名（可选）
    :param dry_run: True=仅校验不创建（预览模式）
    :param preflight: dry_run 时是否执行建单前体检（渠道/仓库/物流/业务员/批次）
    :param create_interval: 实际批量创建时每单之间的额外等待秒数；默认 0，底层 API client 已有节流
    :param order_type_override: 强制指定所有订单类型（"JY"/"BF"），覆盖表格中的类型列
    :param default_shop_name: 默认渠道名（表格中没有渠道列时使用）
    :param default_seller_name: 默认业务员/登记人员工姓名（表格中没有业务员列时使用）
    :param default_customer_name: 默认客户名称（寄样单表格中没有客户名称/客户账号时使用）
    :return: {
        "total_rows": int,          # 总行数
        "total_orders": int,        # 合并后订单数
        "success_count": int,       # 创建成功数
        "fail_count": int,          # 创建失败数
        "skip_count": int,          # 校验跳过数
        "column_mapping": dict,     # 列映射结果
        "missing_columns": list,    # 缺失的必填列
        "results": [                # 每个订单的详细结果
            {
                "order_index": int,
                "source_rows": [int],
                "shopName": str,
                "receiverName": str,
                "goods_count": int,
                "status": "success" | "fail" | "skip",
                "tradeNo": str,     # 成功时
                "error": str,       # 失败时
            }
        ],
        "dry_run": bool,
    }
    """
    report = {
        "total_rows": 0,
        "total_orders": 0,
        "success_count": 0,
        "fail_count": 0,
        "skip_count": 0,
        "column_mapping": {},
        "missing_columns": [],
        "results": [],
        "preflight_enabled": bool(preflight),
        "dry_run": dry_run,
    }

    # Step 1: 读取表格
    logger.info("读取文件: %s", file_path)
    try:
        df = read_spreadsheet(file_path, sheet_name)
    except Exception as e:
        report["error"] = f"读取文件失败: {e}"
        return report

    df = df.dropna(how="all")  # 删除全空行
    report["total_rows"] = len(df)

    if df.empty:
        report["error"] = "表格为空，没有数据行"
        return report

    # Step 2: 智能列映射
    column_mapping = auto_map_columns(df)
    report["column_mapping"] = {str(k): v for k, v in column_mapping.items()}

    # 检查必填列
    missing = check_required_columns(column_mapping)
    # 如果有默认渠道且缺少 shopName，移除 shopName 的缺失
    if default_shop_name and "渠道名称（渠道/店铺/shopName）" in missing:
        missing.remove("渠道名称（渠道/店铺/shopName）")
    report["missing_columns"] = missing

    if missing:
        report["error"] = f"表格缺少必填列: {', '.join(missing)}"
        return report

    # Step 3: 重命名列 + 数据清洗
    df_mapped = df.rename(columns=column_mapping)
    rows = []
    validation_errors = []

    for idx, row in df_mapped.iterrows():
        row_dict = clean_row(row.to_dict())
        row_dict["_row_index"] = idx + 2  # Excel 行号（从 2 开始，1 是表头）

        # 默认渠道
        if default_shop_name and not row_dict.get("shopName"):
            row_dict["shopName"] = default_shop_name
        if default_seller_name and not row_dict.get("sellerName"):
            row_dict["sellerName"] = default_seller_name
        if default_customer_name and not row_dict.get("customerName"):
            row_dict["customerName"] = default_customer_name

        # 强制订单类型
        if order_type_override:
            row_dict["orderType"] = order_type_override

        # 行校验
        errors = validate_row(row_dict, idx)
        if errors:
            validation_errors.append({
                "row": idx + 2,
                "errors": errors,
                "data": {k: v for k, v in row_dict.items() if not k.startswith("_")},
            })
        else:
            rows.append(row_dict)

    # 记录校验跳过的行
    for ve in validation_errors:
        report["results"].append({
            "order_index": -1,
            "source_rows": [ve["row"]],
            "shopName": ve["data"].get("shopName", ""),
            "receiverName": ve["data"].get("receiverName", ""),
            "goods_count": 0,
            "status": "skip",
            "error": "; ".join(ve["errors"]),
        })
        report["skip_count"] += 1

    if not rows:
        report["error"] = "所有行校验失败，无可创建的订单"
        return report

    # Step 4: 合并多货品行
    orders = group_orders_from_rows(rows)
    report["total_orders"] = len(orders)

    logger.info("共 %d 行 → 合并为 %d 个订单（跳过 %d 行）",
                report["total_rows"], len(orders), report["skip_count"])

    preflight_cache = {}

    if dry_run:
        # 预览模式：只校验不创建
        for i, order_data in enumerate(orders):
            order = order_data["order"]
            item = {
                "order_index": i + 1,
                "source_rows": order_data["source_rows"],
                "shopName": order["shopName"],
                "receiverName": order["receiverName"],
                "goods_count": len(order_data["goods_list"]),
                "goods_list": order_data["goods_list"],
                "status": "preview",
                "message": "预览模式，未实际创建",
            }
            if preflight:
                cache_key = (
                    order.get("orderType"),
                    order.get("shopName"),
                    order.get("warehouseName"),
                    order.get("logisticName"),
                    order.get("sellerName"),
                    order.get("customerName"),
                    tuple(
                        (
                            goods.get("goodsNo"),
                            goods.get("goodsName"),
                            goods.get("sellCount"),
                            goods.get("sellPrice"),
                            goods.get("sellTotal"),
                            goods.get("batchNo"),
                        )
                        for goods in order_data["goods_list"]
                    ),
                )
                if cache_key not in preflight_cache:
                    preflight_cache[cache_key] = preflight_sales_order(
                        order_type=order.get("orderType", "JY"),
                        shop_name=order["shopName"],
                        receiver_name=order["receiverName"],
                        mobile=order["mobile"],
                        address=order["address"],
                        goods_list=order_data["goods_list"],
                        warehouse_name=order.get("warehouseName") or None,
                        logistic_name=order.get("logisticName") or None,
                        customer_name=order.get("customerName") or None,
                        seller_name=order.get("sellerName") or None,
                        check_batches=True,
                    )
                item["preflight"] = preflight_cache[cache_key]
                if not item["preflight"].get("ok"):
                    item["status"] = "blocked"
                    item["error"] = "; ".join(item["preflight"].get("errors", []))
                    report["fail_count"] += 1
                else:
                    item["resolved"] = item["preflight"].get("resolved", {})
            report["results"].append(item)
        return report

    # Step 5: 渠道解析缓存（同一渠道只查一次）
    channel_cache = {}

    # Step 6: 逐个创建
    for i, order_data in enumerate(orders):
        order = order_data["order"]
        order_result = {
            "order_index": i + 1,
            "source_rows": order_data["source_rows"],
            "shopName": order["shopName"],
            "receiverName": order["receiverName"],
            "goods_count": len(order_data["goods_list"]),
            "status": "fail",
        }

        try:
            order_type = order.get("orderType", "JY")
            if order_type == "PT":
                # 普通手工销售单：调用 create_manual_order
                result = create_manual_order(
                    shop_name=order["shopName"],
                    receiver_name=order["receiverName"],
                    mobile=order["mobile"],
                    address=order["address"],
                    seller_name=order.get("sellerName"),
                    goods_list=order_data["goods_list"],
                    state=order.get("state", ""),
                    city=order.get("city", ""),
                    district=order.get("district", ""),
                    town=order.get("town", ""),
                    remark=order.get("sellerMemo", ""),
                    buyer_memo=order.get("buyerMemo", ""),
                    customer_name=order.get("customerName") or None,
                    online_trade_no=order.get("onlineTradeNo") or None,
                    warehouse_name=order.get("warehouseName") or None,
                    logistic_name=order.get("logisticName") or None,
                )
            else:
                # 寄样/补发单：调用 create_sample_order
                result = create_sample_order(
                    shop_name=order["shopName"],
                    receiver_name=order["receiverName"],
                    mobile=order["mobile"],
                    address=order["address"],
                    seller_name=order.get("sellerName"),
                    goods_list=order_data["goods_list"],
                    state=order.get("state", ""),
                    city=order.get("city", ""),
                    district=order.get("district", ""),
                    town=order.get("town", ""),
                    remark=order.get("sellerMemo", ""),
                    buyer_memo=order.get("buyerMemo", ""),
                    customer_name=order.get("customerName") or None,
                    online_trade_no=order.get("onlineTradeNo") or None,
                    warehouse_name=order.get("warehouseName") or None,
                    logistic_name=order.get("logisticName") or None,
                    order_type=order_type,
                )

            # 提取单号
            trade_no = _extract_trade_no(result)

            order_result["status"] = "success"
            order_result["tradeNo"] = trade_no
            order_result["created_order"] = result
            if trade_no:
                order_result["created_trade"] = query_trade_by_no(trade_no)
            report["success_count"] += 1

            logger.info("[%d/%d] 创建成功: %s → %s",
                        i + 1, len(orders), order["receiverName"], trade_no)

        except (JackyunAPIError, JackyunValidationError) as e:
            order_result["error"] = str(e)
            report["fail_count"] += 1
            logger.warning("[%d/%d] 创建失败: %s → %s",
                           i + 1, len(orders), order["receiverName"], e)

        except Exception as e:
            order_result["error"] = f"未知错误: {e}"
            report["fail_count"] += 1
            logger.error("[%d/%d] 创建异常: %s → %s",
                         i + 1, len(orders), order["receiverName"], e)

        report["results"].append(order_result)

        # 底层 API client 已有 throttle；如遇限流，可由调用方显式设置额外间隔。
        if create_interval and i < len(orders) - 1:
            time.sleep(float(create_interval))

    return report


# ==================== 报告格式化 ====================

def format_import_report(report: dict) -> str:
    """
    将批量导入结果格式化为用户友好的文本

    :param report: batch_create_orders() 的返回值
    :return: Markdown 格式的报告
    """
    lines = []

    if report.get("dry_run"):
        lines.append("## 📋 批量导入预览（未实际创建）\n")
    else:
        lines.append("## 📋 批量导入结果\n")

    if report.get("error"):
        lines.append(f"❌ **错误**: {report['error']}\n")
        if report.get("missing_columns"):
            lines.append("缺少的必填列:")
            for col in report["missing_columns"]:
                lines.append(f"  - {col}")
        return "\n".join(lines)

    # 汇总
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 表格总行数 | {report['total_rows']} |")
    lines.append(f"| 合并后订单数 | {report['total_orders']} |")
    if report.get("dry_run"):
        lines.append(f"| 预检阻断 | {report['fail_count']} |")
    else:
        lines.append(f"| ✅ 创建成功 | {report['success_count']} |")
        lines.append(f"| ❌ 创建失败 | {report['fail_count']} |")
    lines.append(f"| ⏭️ 校验跳过 | {report['skip_count']} |")
    lines.append("")

    # 列映射
    if report.get("column_mapping"):
        lines.append("### 列映射")
        lines.append("| 表格列名 | → API 字段 |")
        lines.append("|----------|-----------|")
        for orig, mapped in report["column_mapping"].items():
            lines.append(f"| {orig} | {mapped} |")
        lines.append("")

    # 详细结果
    results = report.get("results", [])
    if results:
        lines.append("### 详细结果")
        lines.append("| # | 行号 | 渠道 | 收件人 | 货品数 | 状态 | 单号/错误 |")
        lines.append("|---|------|------|--------|--------|------|-----------|")

        for r in results:
            idx = r.get("order_index", "-")
            rows_str = ",".join(str(x) for x in r.get("source_rows", []))
            shop = r.get("shopName", "-")
            if len(shop) > 15:
                shop = shop[:12] + "..."
            receiver = r.get("receiverName", "-")
            goods_count = r.get("goods_count", 0)
            status = r.get("status", "-")

            status_icon = {"success": "✅", "fail": "❌", "skip": "⏭️", "preview": "👁️", "blocked": "🚫"}.get(status, "❓")
            detail = r.get("tradeNo", r.get("error", r.get("message", "")))
            if len(str(detail)) > 30:
                detail = str(detail)[:27] + "..."

            lines.append(f"| {idx} | {rows_str} | {shop} | {receiver} | {goods_count} | {status_icon} | {detail} |")

    # 创建成功的单号汇总
    success_nos = [r["tradeNo"] for r in results if r.get("status") == "success" and r.get("tradeNo")]
    if success_nos:
        lines.append(f"\n### 成功创建的单号（共 {len(success_nos)} 个）")
        lines.append("```")
        lines.append(", ".join(success_nos))
        lines.append("```")
        lines.append("\n> ⚠️ 复核功能已禁用，创建后请在吉客云网页端手动复核")

    return "\n".join(lines)
