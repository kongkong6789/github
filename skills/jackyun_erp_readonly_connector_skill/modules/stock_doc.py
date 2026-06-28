"""
Stock document helpers.

Provides query, create, and check helpers for inbound/outbound documents.
"""
import logging
from datetime import date
from time import time

from jackyun_api import JackyunValidationError, get_client
from helpers.constants import (
    METHOD_DOC_CHECK,
    METHOD_DOC_IN,
    METHOD_DOC_IN_ADD,
    METHOD_DOC_OUT,
    METHOD_DOC_OUT_ADD,
    METHOD_STOCK_IN_APPLY_CREATE,
    METHOD_STOCK_IN_APPLY_GET,
    METHOD_STOCK_OUT_APPLY_CREATE,
    METHOD_STOCK_OUT_APPLY_GET,
)
from helpers.validators import require_fields_or_raise, validate_quantity

logger = logging.getLogger(__name__)

DOC_DETAIL_BATCH_FIELDS = [
    "batchNo",
    "batchNos",
    "batchList",
    "batch_no",
    "batch_no_list",
    "batch_list",
]

DEFAULT_OUT_SELECT_FIELDS = (
    "recId,goodsdocNo,logisticNo,logisticName,"
    "logisticList.logisticNo,logisticList.logisticName,logisticList.logisticCode,"
    "outBillNo,billNo,checkStatus,inouttype,goodsFlagName,skuFlagName,"
    "goodsDocDetailList.goodsNo,goodsDocDetailList.goodsName,"
    "goodsDocDetailList.quantity,goodsDocDetailList.unitPrice,"
    "warehouseName,channelName,"
    "gmtCreate,gmtModified"
)

DOC_REQUIRED_FIELDS = [
    ("inouttype", "出入库类型"),
]

DOC_DETAIL_REQUIRED_FIELDS = [
    ("goodsNo", "货品编号"),
    ("quantity", "数量"),
]

STOCK_APPLY_UNIT_NAME = "Pcs"

STOCK_IN_APPLY_REQUIRED_FIELDS = [
    ("inWarehouseCode", "入库仓库编号"),
    ("inType", "入库类型"),
    ("relDataId", "关联单据ID"),
    ("applyUserName", "申请人姓名"),
    ("applyDate", "申请日期"),
    ("operator", "制单人姓名"),
    ("source", "来源"),
    ("currencyRate", "汇率"),
]

STOCK_OUT_APPLY_REQUIRED_FIELDS = [
    ("outWarehouseCode", "出库仓库编号"),
    ("outType", "出库类型"),
    ("relDataId", "关联单据ID"),
    ("applyUserName", "申请人姓名"),
    ("applyDate", "申请日期"),
    ("source", "来源"),
    ("currencyRate", "汇率"),
]

STOCK_APPLY_DETAIL_REQUIRED_FIELDS = [
    ("skuCount", "数量"),
    ("unitName", "单位名称"),
]


def _validate_doc_data(doc_data: dict, detail_key: str = "goodsDocDetailList"):
    """Validate create_doc_in/create_doc_out payload before calling ERP."""
    require_fields_or_raise(doc_data, DOC_REQUIRED_FIELDS)

    details = doc_data.get(detail_key)
    if not isinstance(details, list) or not details:
        raise JackyunValidationError(f"缺少货品明细({detail_key})，请至少添加一个货品")

    for index, item in enumerate(details, start=1):
        require_fields_or_raise(item, DOC_DETAIL_REQUIRED_FIELDS)
        if not validate_quantity(item.get("quantity")):
            raise JackyunValidationError(f"第 {index} 个货品明细数量必须为正整数")


def _build_batch_list(allocation: list[dict]) -> list[dict]:
    return [
        {
            "batchNo": row.get("batch_no"),
            "quantity": row.get("quantity"),
            "productionDate": row.get("production_date"),
            "expirationDate": row.get("expiration_date"),
        }
        for row in (allocation or [])
        if row.get("batch_no")
    ]


def _normalize_batch_aliases(item: dict) -> dict:
    if "batch_no" in item and "batchNo" not in item:
        item["batchNo"] = item.pop("batch_no")
    if "batch_no_list" in item and "batchNos" not in item:
        item["batchNos"] = item.pop("batch_no_list")
    if "batch_list" in item and "batchList" not in item:
        item["batchList"] = item.pop("batch_list")
    if item.get("batchNo") and not item.get("batchList"):
        item["batchList"] = [{"batchNo": item["batchNo"], "quantity": item.get("skuCount") or item.get("quantity")}]
    return item


def _resolve_warehouse_code(doc_data: dict) -> str:
    warehouse_code = doc_data.get("warehouseCode") or ""
    if warehouse_code:
        return warehouse_code

    warehouse_name = doc_data.get("warehouseName") or ""
    if not warehouse_name:
        return ""

    from modules.warehouse import get_warehouse_by_name

    warehouse = get_warehouse_by_name(warehouse_name)
    return warehouse.get("warehouseCode", "") if warehouse else ""


def _extract_batch_requirements(item: dict) -> dict:
    requirements = item.get("batch_requirements") or item.get("batchRequirements") or {}
    if not isinstance(requirements, dict):
        requirements = {}
    for source, target in {
        "batch_no": "batch_no",
        "batchNoRequired": "batch_no",
        "batch_no_contains": "batch_no_contains",
        "batchContains": "batch_no_contains",
        "include_batch_nos": "include_batch_nos",
        "includeBatchNos": "include_batch_nos",
        "exclude_batch_nos": "exclude_batch_nos",
        "excludeBatchNos": "exclude_batch_nos",
        "productionDateFrom": "production_date_from",
        "productionDateTo": "production_date_to",
        "expirationDateFrom": "expiration_date_from",
        "expirationDateTo": "expiration_date_to",
        "minRemainingValidDays": "min_remaining_valid_days",
    }.items():
        if source in item and target not in requirements:
            requirements[target] = item[source]
    return requirements


def _resolve_goods_for_apply_detail(item: dict, outbound: bool) -> dict:
    from modules.goods import resolve_goods_for_transfer

    detail = dict(item)
    if "skuCount" not in detail and "quantity" in detail:
        detail["skuCount"] = detail["quantity"]
    if "skuBarcode" not in detail and "barcode" in detail:
        detail["skuBarcode"] = detail["barcode"]
    if "skuBarcode" not in detail and "skuBarCode" in detail:
        detail["skuBarcode"] = detail["skuBarCode"]
    if "outSkuCode" not in detail and "outerSkuCode" in detail:
        detail["outSkuCode"] = detail["outerSkuCode"]
    if "rowRemark" not in detail and "remark" in detail:
        detail["rowRemark"] = detail["remark"]

    goods_no = str(detail.get("goodsNo") or "").strip()
    goods_name = str(detail.get("goodsName") or detail.get("goods_name") or "").strip()
    if goods_no or goods_name:
        resolved = resolve_goods_for_transfer(goods_no=goods_no, goods_name=goods_name)
        goods = resolved.get("record") or {}
        if goods:
            detail.setdefault("goodsNo", goods.get("goodsNo") or goods_no)
            detail.setdefault("goodsName", goods.get("goodsName") or goods_name)
            detail.setdefault("skuBarcode", goods.get("skuBarcode") or goods.get("barcode") or goods.get("goodsNo"))
            detail.setdefault("outSkuCode", goods.get("outSkuCode") or goods.get("outerSkuCode") or goods.get("skuCode"))
            detail.setdefault("skuId", goods.get("skuId"))

    detail["unitName"] = STOCK_APPLY_UNIT_NAME
    detail.setdefault("isCertified", 1)
    detail.setdefault("isSerial", 0)
    _normalize_batch_aliases(detail)

    if outbound:
        if "skuBarCode" not in detail and "skuBarcode" in detail:
            detail["skuBarCode"] = detail["skuBarcode"]
    return detail


def _resolve_apply_operator(payload: dict):
    from modules.user import resolve_default_operator

    applicant_name = (
        payload.get("applyUserName")
        or payload.get("applicant_name")
        or payload.get("applicantName")
    )
    if not str(applicant_name or "").strip():
        raise JackyunValidationError("入库/出库申请单必须由用户提供申请人姓名 applyUserName")
    applicant = resolve_default_operator(
        user_name=str(applicant_name or "").strip(),
        user_id=payload.get("applyUserId") or payload.get("applicant_user_id"),
        depart_code=payload.get("applyDepartCode") or payload.get("departCode"),
    )
    real_name = applicant.get("realName") or applicant.get("name") or applicant.get("userName") or applicant_name
    payload["applyUserName"] = real_name
    payload.setdefault("operator", real_name)
    if applicant.get("departCode") and not payload.get("applyDepartCode"):
        payload["applyDepartCode"] = applicant.get("departCode")
    if applicant.get("mainDepartName") and not payload.get("applyDepartName"):
        payload["applyDepartName"] = applicant.get("mainDepartName")


def _resolve_apply_warehouse(payload: dict, outbound: bool):
    from modules.warehouse import get_warehouse_by_name

    code_field = "outWarehouseCode" if outbound else "inWarehouseCode"
    name_field = "outWarehouseName" if outbound else "inWarehouseName"
    if payload.get("warehouseCode") and not payload.get(code_field):
        payload[code_field] = payload["warehouseCode"]
    if payload.get("warehouseName") and not payload.get(name_field):
        payload[name_field] = payload["warehouseName"]
    if payload.get(code_field):
        return
    warehouse_name = payload.get(name_field) or payload.get("warehouseName")
    if not warehouse_name:
        return
    warehouse = get_warehouse_by_name(warehouse_name)
    if warehouse and warehouse.get("warehouseCode"):
        payload[code_field] = warehouse.get("warehouseCode")
        payload.setdefault("applyCompanyCode", warehouse.get("warehouseCompanyCode") or "")


def _auto_rel_data_id(prefix: str) -> str:
    return f"{prefix}{date.today().strftime('%Y%m%d')}{int(time() * 1000) % 100000000:08d}"


def _normalize_stock_apply_payload(doc_type: str, apply_data: dict, batch_strategy: str = "fifo") -> tuple[dict, dict]:
    outbound = doc_type == "out"
    payload = dict(apply_data or {})
    if "remark" in payload and "memo" not in payload:
        payload["memo"] = payload["remark"]
    if "reason" in payload:
        payload["outReason" if outbound else "inReason"] = payload["reason"]
    if "type" in payload and ("outType" if outbound else "inType") not in payload:
        payload["outType" if outbound else "inType"] = payload["type"]
    if "goodsList" in payload:
        payload["stockOutDetailViews" if outbound else "stockInDetailViews"] = payload["goodsList"]

    _resolve_apply_warehouse(payload, outbound=outbound)
    _resolve_apply_operator(payload)
    payload.setdefault("applyDate", date.today().isoformat())
    payload.setdefault("source", "OPEN")
    payload.setdefault("currencyCode", "CNY")
    payload.setdefault("currencyRate", 1)
    payload.setdefault("relDataId", payload.get("outNo") or payload.get("inNo") or _auto_rel_data_id("OUT" if outbound else "IN"))

    detail_key = "stockOutDetailViews" if outbound else "stockInDetailViews"
    details = [
        _resolve_goods_for_apply_detail(item, outbound=outbound)
        for item in (payload.get(detail_key) or [])
    ]
    payload[detail_key] = details

    batch_plans = []
    if outbound:
        payload = _auto_select_stock_apply_out_batches(payload, strategy=batch_strategy)
        for index, item in enumerate(payload.get(detail_key) or [], start=1):
            if item.get("batchList"):
                batch_plans.append({
                    "line_index": index,
                    "goods_no": item.get("goodsNo"),
                    "goods_name": item.get("goodsName"),
                    "allocation": item.get("batchList"),
                })
    else:
        for item in details:
            if item.get("batchList"):
                item["isBatch"] = 1

    required_fields = STOCK_OUT_APPLY_REQUIRED_FIELDS if outbound else STOCK_IN_APPLY_REQUIRED_FIELDS
    require_fields_or_raise(payload, required_fields)
    if not details:
        raise JackyunValidationError("申请单缺少货品明细，请至少添加一个货品")
    for index, item in enumerate(details, start=1):
        require_fields_or_raise(item, STOCK_APPLY_DETAIL_REQUIRED_FIELDS)
        if not validate_quantity(item.get("skuCount")):
            raise JackyunValidationError(f"第 {index} 个货品明细数量必须为正整数")
        if not (item.get("skuId") or item.get("outSkuCode") or item.get("skuBarcode") or item.get("skuBarCode")):
            raise JackyunValidationError(f"第 {index} 个货品明细必须至少提供 skuId、outSkuCode 或条码")
    summary = {
        "applicant": payload.get("applyUserName"),
        "depart_code": payload.get("applyDepartCode"),
        "warehouse_code": payload.get("outWarehouseCode") if outbound else payload.get("inWarehouseCode"),
        "batch_strategy": batch_strategy,
        "batches": batch_plans,
    }
    return payload, summary


def _auto_select_stock_apply_out_batches(payload: dict, strategy: str = "fifo") -> dict:
    from modules.inventory import recommend_batches

    warehouse_code = payload.get("outWarehouseCode", "")
    if not warehouse_code:
        return payload
    for index, item in enumerate(payload.get("stockOutDetailViews", []) or [], start=1):
        if any(item.get(field) for field in DOC_DETAIL_BATCH_FIELDS):
            _normalize_batch_aliases(item)
            if item.get("batchList"):
                item["isBatch"] = 1
            continue
        requested_quantity = item.get("skuCount") or item.get("quantity")
        if requested_quantity in (None, "", 0, "0"):
            continue
        batch_result = recommend_batches(
            warehouse_code=warehouse_code,
            goods_no=item.get("goodsNo"),
            goods_name=item.get("goodsName"),
            required_quantity=int(float(requested_quantity)),
            strategy=strategy,
            is_batch_management=1,
            **_extract_batch_requirements(item),
        )
        if batch_result.get("enough_stock") is False:
            raise JackyunValidationError(
                f"货品 {item.get('goodsNo') or item.get('goodsName') or index} 批次可用库存不足，"
                f"当前还缺少 {batch_result.get('remaining_quantity') or 0}"
            )
        batch_list = _build_batch_list(batch_result.get("recommended_allocation") or [])
        if batch_list:
            item["isBatch"] = 1
            item["batchList"] = batch_list
    return payload


def _auto_select_doc_batches(doc_data: dict, strategy: str = "fifo") -> dict:
    from modules.inventory import recommend_batches

    warehouse_code = _resolve_warehouse_code(doc_data)
    if not warehouse_code:
        return doc_data

    for index, item in enumerate(doc_data.get("goodsDocDetailList", []) or [], start=1):
        if any(item.get(field) for field in DOC_DETAIL_BATCH_FIELDS):
            if "batch_no" in item and "batchNo" not in item:
                item["batchNo"] = item.pop("batch_no")
            if "batch_no_list" in item and "batchNos" not in item:
                item["batchNos"] = item.pop("batch_no_list")
            if "batch_list" in item and "batchList" not in item:
                item["batchList"] = item.pop("batch_list")
            continue

        requested_quantity = item.get("quantity")
        if requested_quantity in (None, "", 0, "0"):
            continue

        batch_result = recommend_batches(
            warehouse_code=warehouse_code,
            goods_no=item.get("goodsNo"),
            goods_name=item.get("goodsName"),
            required_quantity=int(requested_quantity),
            strategy=strategy,
            is_batch_management=1,
            **_extract_batch_requirements(item),
        )
        if batch_result.get("enough_stock") is False:
            raise JackyunValidationError(
                f"货品 {item.get('goodsNo') or item.get('goodsName') or index} 批次可用库存不足，"
                f"当前还缺少 {batch_result.get('remaining_quantity') or 0}"
            )

        batch_list = _build_batch_list(batch_result.get("recommended_allocation") or [])
        if not batch_list:
            continue

        item["isBatch"] = 1
        item["batchList"] = batch_list
        if len(batch_list) == 1:
            item["batchNo"] = batch_list[0]["batchNo"]

    return doc_data


def query_doc_out(
    out_bill_no: str = None,
    bill_no: str = None,
    goodsdoc_no: str = None,
    inouttype: int = None,
    check_status: int = None,
    gmt_create_start: str = None,
    gmt_create_end: str = None,
    page_index: int = 0,
    page_size: int = 50,
    select_fields: str = None,
) -> list:
    """Query outbound stock documents."""
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
        "selelctFields": select_fields or DEFAULT_OUT_SELECT_FIELDS,
    }
    if out_bill_no:
        bizcontent["outBillNo"] = out_bill_no
    if bill_no:
        bizcontent["billNo"] = bill_no
    if goodsdoc_no:
        bizcontent["goodsdocNo"] = goodsdoc_no
    if inouttype is not None:
        bizcontent["inouttype"] = inouttype
    if check_status is not None:
        bizcontent["checkStatus"] = check_status
    if gmt_create_start:
        bizcontent["gmtCreateStart"] = gmt_create_start
    if gmt_create_end:
        bizcontent["gmtCreateEnd"] = gmt_create_end

    result = client.call(METHOD_DOC_OUT, bizcontent)
    data = result.get("result", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def query_all_doc_out(**kwargs) -> list:
    """Query all outbound stock documents with auto pagination."""
    client = get_client()
    bizcontent = {"selelctFields": DEFAULT_OUT_SELECT_FIELDS}
    if kwargs.get("inouttype"):
        bizcontent["inouttype"] = kwargs["inouttype"]
    if kwargs.get("gmt_create_start"):
        bizcontent["gmtCreateStart"] = kwargs["gmt_create_start"]
    if kwargs.get("gmt_create_end"):
        bizcontent["gmtCreateEnd"] = kwargs["gmt_create_end"]
    if kwargs.get("check_status") is not None:
        bizcontent["checkStatus"] = kwargs["check_status"]
    return client.call_paged(METHOD_DOC_OUT, bizcontent)


def query_doc_in(
    bill_no: str = None,
    goodsdoc_no: str = None,
    inouttype: int = None,
    check_status: int = None,
    gmt_create_start: str = None,
    gmt_create_end: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    """Query inbound stock documents."""
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if bill_no:
        bizcontent["billNo"] = bill_no
    if goodsdoc_no:
        bizcontent["goodsdocNo"] = goodsdoc_no
    if inouttype is not None:
        bizcontent["inouttype"] = inouttype
    if check_status is not None:
        bizcontent["checkStatus"] = check_status
    if gmt_create_start:
        bizcontent["gmtCreateStart"] = gmt_create_start
    if gmt_create_end:
        bizcontent["gmtCreateEnd"] = gmt_create_end

    result = client.call(METHOD_DOC_IN, bizcontent)
    data = result.get("result", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        return items if isinstance(items, list) else ([items] if items else [])
    return []


def create_doc_out(doc_data: dict) -> dict:
    """Create an outbound stock document."""
    doc_data = _auto_select_doc_batches(doc_data)
    _validate_doc_data(doc_data)
    client = get_client()
    logger.info("Creating outbound stock doc: %s", doc_data.get("outBillNo", ""))
    return client.call(METHOD_DOC_OUT_ADD, doc_data)


def create_doc_in(doc_data: dict) -> dict:
    """Create an inbound stock document."""
    _validate_doc_data(doc_data)
    client = get_client()
    logger.info("Creating inbound stock doc: %s", doc_data.get("outBillNo", ""))
    return client.call(METHOD_DOC_IN_ADD, doc_data)


def prepare_stock_apply_payload(doc_type: str, apply_data: dict, batch_strategy: str = "fifo") -> tuple[dict, dict]:
    """Prepare and validate an inbound/outbound stock application payload."""
    if doc_type not in ("in", "out"):
        raise JackyunValidationError(f"不支持的申请单类型: {doc_type}")
    return _normalize_stock_apply_payload(doc_type, apply_data, batch_strategy=batch_strategy)


def create_stock_in_apply(apply_data: dict, batch_strategy: str = "fifo") -> dict:
    """Create inbound stock application using erp.storage.stockincreate."""
    payload, _ = prepare_stock_apply_payload("in", apply_data, batch_strategy=batch_strategy)
    return submit_stock_in_apply_payload(payload)


def submit_stock_in_apply_payload(payload: dict) -> dict:
    """Submit a prepared inbound stock application payload."""
    client = get_client()
    logger.info("Creating inbound stock application: %s", payload.get("inNo", ""))
    return client.call(METHOD_STOCK_IN_APPLY_CREATE, payload)


def create_stock_out_apply(apply_data: dict, batch_strategy: str = "fifo") -> dict:
    """Create outbound stock application using erp.storage.stockoutcreate."""
    payload, _ = prepare_stock_apply_payload("out", apply_data, batch_strategy=batch_strategy)
    return submit_stock_out_apply_payload(payload)


def submit_stock_out_apply_payload(payload: dict) -> dict:
    """Submit a prepared outbound stock application payload."""
    client = get_client()
    logger.info("Creating outbound stock application: %s", payload.get("outNo", ""))
    return client.call(METHOD_STOCK_OUT_APPLY_CREATE, {"bizdata": payload})


def extract_stock_apply_no(doc_type: str, create_result: dict, payload: dict = None) -> str:
    """Extract inbound/outbound application number from common response shapes."""
    payload = payload or {}
    result = create_result.get("result", {}) if isinstance(create_result, dict) else {}
    data = result.get("data", {}) if isinstance(result, dict) else {}
    fields = ("outNo", "out_no", "stockOutNo", "billNo", "goodsdocNo") if doc_type == "out" else (
        "inNo", "in_no", "stockInNo", "billNo", "goodsdocNo"
    )
    for container in (data, result, create_result if isinstance(create_result, dict) else {}, payload):
        if not isinstance(container, dict):
            continue
        for field in fields:
            value = container.get(field)
            if value:
                return str(value)
    return ""


def query_stock_in_apply(in_no: str = None, rel_data_id: str = None, page_index: int = 0, page_size: int = 20) -> list:
    """Query inbound stock applications."""
    client = get_client()
    bizcontent = {"pageIndex": page_index, "pageSize": page_size}
    if in_no:
        bizcontent["inNo"] = in_no
    if rel_data_id:
        bizcontent["relDataId"] = rel_data_id
    result = client.call(METHOD_STOCK_IN_APPLY_GET, bizcontent)
    data = result.get("result", {}).get("data", {}) if isinstance(result, dict) else {}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("stockInList", "stockin", "rows", "records", "list", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [value]
        return [data] if data else []
    return []


def query_stock_out_apply(out_no: str = None, rel_data_id: str = None, page_index: int = 0, page_size: int = 20) -> list:
    """Query outbound stock applications."""
    client = get_client()
    bizcontent = {"pageIndex": page_index, "pageSize": page_size}
    if out_no:
        bizcontent["outNo"] = out_no
    if rel_data_id:
        bizcontent["relDataId"] = rel_data_id
    result = client.call(METHOD_STOCK_OUT_APPLY_GET, bizcontent)
    data = result.get("result", {}).get("data", {}) if isinstance(result, dict) else {}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("stockOutList", "stockout", "rows", "records", "list", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [value]
        return [data] if data else []
    return []


def check_doc(rec_id: str = None, goodsdoc_no: str = None) -> dict:
    """Check an inbound or outbound stock document."""
    client = get_client()
    bizcontent = {}
    if rec_id:
        bizcontent["recId"] = rec_id
    if goodsdoc_no:
        bizcontent["goodsdocNo"] = goodsdoc_no
    logger.info("Checking stock doc: recId=%s, goodsdocNo=%s", rec_id, goodsdoc_no)
    return client.call(METHOD_DOC_CHECK, bizcontent)


def query_outbound_logistics_by_bill_no(bill_no: str) -> dict:
    """Query logistics info from outbound documents by source bill number."""
    if not bill_no:
        raise JackyunValidationError("缺少销售单号/业务单号，必须提供 bill_no")

    records = query_doc_out(bill_no=bill_no, page_size=20)
    if not records:
        return {
            "bill_no": bill_no,
            "found": False,
            "logistic_no": "",
            "logistic_name": "",
            "goodsdoc_no": "",
            "goods_list": [],
            "raw": None,
        }

    record = records[0]
    info = extract_logistics_info(record)
    info.update({
        "bill_no": bill_no,
        "found": True,
        "raw": record,
    })
    return info


def extract_logistics_info(record: dict) -> dict:
    """Extract logistics and goods info from an outbound stock record."""
    logistic_list = record.get("logisticList", []) or []
    if logistic_list:
        nos = [item.get("logisticNo", "") for item in logistic_list if item.get("logisticNo")]
        names = list(dict.fromkeys(
            item.get("logisticName", "") for item in logistic_list if item.get("logisticName")
        ))
        logistic_no = ",".join(nos)
        logistic_name = ",".join(names)
    else:
        logistic_no = record.get("logisticNo", "") or ""
        logistic_name = record.get("logisticName", "") or ""

    detail_list = record.get("goodsDocDetailList", []) or []
    goods_list = []
    for detail in detail_list:
        goods_list.append({
            "goodsNo": detail.get("goodsNo", ""),
            "goodsName": detail.get("goodsName", ""),
            "quantity": detail.get("quantity", 0),
            "unitPrice": detail.get("unitPrice", 0),
        })

    return {
        "logistic_no": logistic_no,
        "logistic_name": logistic_name,
        "goodsdoc_no": record.get("goodsdocNo", ""),
        "goods_list": goods_list,
    }
