"""
After-sales helpers covering refund / return-change / dispute / disorder APIs.
"""
import logging

from jackyun_api import get_client

logger = logging.getLogger(__name__)

AFTERSALES_METHODS = {
    "refund_create": "ass-business.refund.create",
    "refund_list": "ass-business.refund.listRefundInfo",
    "refund_cancel": "ass-business.refund.cancel",
    "refund_update": "ass-business.refund.update",
    "refund_pay": "ass-business.refund.pay",
    "returnchange_create": "ass-business.returnchange.create",
    "returnchange_get": "ass-business.returnchange.fullinfoget",
    "returnchange_cancel": "ass-business.returnchange.cancel",
    "returnchange_pay": "ass-business.returnchange.pay",
    "returnchange_recover": "ass-business.returnchange.recoverToAuditStatus",
    "returnchange_update": "ass-business.returnchange.update.plat",
    "returnchange_update_custom_fields": "ass-business.returnchange.update.customFields.plat",
    "returnchange_oppo_list": "ass-business.returnchange.oppolist",
    "dispute_create": "ass-business.dispute.createdispute",
    "dispute_list": "ass-business.dispute.listDisputeInfo",
    "dispute_complete": "ass-business.dispute.complete",
    "disorder_create": "ass-business.disorder.createDisorder",
    "disorder_list": "ass-business.disorder.listDisorderInfo",
    "disorder_list_v2": "ass-business.disorder.listDisorderInfoV2",
    "disorder_cancel": "ass-business.disorder.cancel",
    "exchange_delivery": "ass-business.exchange.delivery",
    "exchange_delivery_complete": "ass-business.exchange.deliverycomplete",
    "exchange_return_confirm": "ass-business.exchange.returnorder.confirm",
    "flag_batch_edit": "ass-business.flag.batchedit",
    "custom_column_config": "ass-business.others.getcustomcolumnconfiginfo",
    "return_address_info": "ass-business.others.getreturnaddressinfo",
    "legacy_refund_create": "ass.refund.create",
    "legacy_refund_cancel": "ass.refund.cancel",
    "legacy_returnchange_create": "ass.returnchange.create",
    "legacy_returnchange_cancel": "ass.returnchange.cancel",
    "legacy_returnchange_get": "ass.returnchange.fullinfoget",
}


def _extract_data(result: dict):
    data = result.get("result", {}).get("data")
    return data if data is not None else result.get("result", {})


def call_aftersales_api(method_key_or_name: str, bizcontent: dict) -> dict:
    client = get_client()
    method = AFTERSALES_METHODS.get(method_key_or_name, method_key_or_name)
    logger.info("Calling aftersales API: %s", method)
    return client.call(method, bizcontent)


def query_refunds(**kwargs):
    return _extract_data(call_aftersales_api("refund_list", kwargs))


def create_refund(refund_data: dict) -> dict:
    return call_aftersales_api("refund_create", refund_data)


def cancel_refund(refund_data: dict) -> dict:
    return call_aftersales_api("refund_cancel", refund_data)


def update_refund(refund_data: dict) -> dict:
    return call_aftersales_api("refund_update", refund_data)


def pay_refund(refund_data: dict) -> dict:
    return call_aftersales_api("refund_pay", refund_data)


def query_returnchanges(**kwargs):
    return _extract_data(call_aftersales_api("returnchange_get", kwargs))


def create_returnchange(data: dict) -> dict:
    return call_aftersales_api("returnchange_create", data)


def cancel_returnchange(data: dict) -> dict:
    return call_aftersales_api("returnchange_cancel", data)


def pay_returnchange(data: dict) -> dict:
    return call_aftersales_api("returnchange_pay", data)


def recover_returnchange_to_audit_status(data: dict) -> dict:
    return call_aftersales_api("returnchange_recover", data)


def update_returnchange(data: dict) -> dict:
    return call_aftersales_api("returnchange_update", data)


def update_returnchange_custom_fields(data: dict) -> dict:
    return call_aftersales_api("returnchange_update_custom_fields", data)


def query_disputes(**kwargs):
    return _extract_data(call_aftersales_api("dispute_list", kwargs))


def create_dispute(data: dict) -> dict:
    return call_aftersales_api("dispute_create", data)


def complete_dispute(data: dict) -> dict:
    return call_aftersales_api("dispute_complete", data)


def query_disorders(v2: bool = False, **kwargs):
    key = "disorder_list_v2" if v2 else "disorder_list"
    return _extract_data(call_aftersales_api(key, kwargs))


def create_disorder(data: dict) -> dict:
    return call_aftersales_api("disorder_create", data)


def cancel_disorder(data: dict) -> dict:
    return call_aftersales_api("disorder_cancel", data)
