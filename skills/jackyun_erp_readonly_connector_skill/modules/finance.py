"""
Finance helpers.

Covers the existing summary APIs and the newer fin / fin-fbs API families
through a generic dispatcher plus common convenience wrappers.
"""
import logging

from jackyun_api import get_client
from helpers.constants import METHOD_FINANCE_GOODS_SUMMARY, METHOD_FINANCE_SALES_SUMMARY

logger = logging.getLogger(__name__)

FINANCE_METHODS = {
    "accounts_listall": "fin.accounts.listall",
    "acdoc_create": "fin.acdoc.create",
    "acdoc_query": "fin.acdoc.query",
    "acdocdetail_query": "fin.acdocdetail.query",
    "bill_update_annex": "fin.bill.updateAnnex",
    "contact_listcontactunits": "fin.contact.listcontactunits",
    "payment_cancel_audit": "fin.payment.cancelAudit",
    "paymentapply_create": "fin.paymentapply.create",
    "paymentapply_listinfo": "fin.paymentapply.listinfo",
    "paymentapply_queryinfobypurchno": "fin.paymentapply.queryinfobypurchno",
    "paymentid_execute": "fin.paymentid.execute",
    "fbs_createbill": "fin-fbs.createbill",
    "fbs_arapdetail_listarap": "fin-fbs.arapdetail.listarap",
    "fbs_bankbalance_get": "fin-fbs.bankbalance.get",
    "fbs_billinfo_allpayablelist": "fin-fbs.billinfo.allpayablelist",
    "fbs_billinfo_allreceivablelist": "fin-fbs.billinfo.allreceivablelist",
    "fbs_billinfo_allreceivepaymentlist": "fin-fbs.billinfo.allreceivepaymentlist",
    "fbs_billinfo_auditbill": "fin-fbs.billinfo.auditbill",
    "fbs_billinfo_countreceivepayment": "fin-fbs.billinfo.countreceivepayment",
    "fbs_billinfo_createcashorcostrecpaybill": "fin-fbs.billinfo.createcashorcostrecpaybill",
    "fbs_billinfo_createcostbill": "fin-fbs.billinfo.createcostbill",
    "fbs_billinfo_createcustrecbill": "fin-fbs.billinfo.createcustrecbill",
    "fbs_billinfo_createcustvendstaffpaybill": "fin-fbs.billinfo.createcustvendstaffpaybill",
    "fbs_billinfo_createvendpaybill": "fin-fbs.billinfo.createvendpaybill",
    "fbs_billinfo_createvendrecbill": "fin-fbs.billinfo.createvendrecbill",
    "fbs_billinfo_getdetailbyid": "fin-fbs.billinfo.getdetailbyid",
    "fbs_billinfo_getwfdetailbybillnum": "fin-fbs.billinfo.getwfdetailbybillnum",
    "fbs_billinfo_listbillfileurl": "fin-fbs.billinfo.listbillfileurl",
    "fbs_billinfo_receivepaymentlist": "fin-fbs.billinfo.receivepaymentlist",
    "fbs_billinfo_recpaybillwithwfnum": "fin-fbs.billinfo.recpaybillwithwfnum",
    "fbs_billinfo_updatestatus": "fin-fbs.billinfo.updatestatus",
    "fbs_billtranssale_listreceivablespay": "fin-fbs.billtranssale.listreceivablespay",
    "fbs_unitbalance_get": "fin-fbs.unitbalance.get",
}


def _extract_list(result: dict) -> list:
    data = result.get("result", {}).get("data", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        return items if isinstance(items, list) else ([items] if items else [])
    if isinstance(data, list):
        return data
    return []


def call_finance_api(method_key_or_name: str, bizcontent: dict) -> dict:
    client = get_client()
    method = FINANCE_METHODS.get(method_key_or_name, method_key_or_name)
    logger.info("Calling finance API: %s", method)
    return client.call(method, bizcontent)


def query_sales_summary(
    gmt_create_start: str = None,
    gmt_create_end: str = None,
    channel_name: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if gmt_create_start:
        bizcontent["gmtCreateStart"] = gmt_create_start
    if gmt_create_end:
        bizcontent["gmtCreateEnd"] = gmt_create_end
    if channel_name:
        bizcontent["channelName"] = channel_name
    return _extract_list(client.call(METHOD_FINANCE_SALES_SUMMARY, bizcontent))


def query_goods_summary(
    gmt_create_start: str = None,
    gmt_create_end: str = None,
    goods_no: str = None,
    page_index: int = 0,
    page_size: int = 50,
) -> list:
    client = get_client()
    bizcontent = {
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    if gmt_create_start:
        bizcontent["gmtCreateStart"] = gmt_create_start
    if gmt_create_end:
        bizcontent["gmtCreateEnd"] = gmt_create_end
    if goods_no:
        bizcontent["goodsNo"] = goods_no
    return _extract_list(client.call(METHOD_FINANCE_GOODS_SUMMARY, bizcontent))


def query_all_goods_summary(**kwargs) -> list:
    client = get_client()
    bizcontent = {}
    if kwargs.get("gmt_create_start"):
        bizcontent["gmtCreateStart"] = kwargs["gmt_create_start"]
    if kwargs.get("gmt_create_end"):
        bizcontent["gmtCreateEnd"] = kwargs["gmt_create_end"]
    if kwargs.get("goods_no"):
        bizcontent["goodsNo"] = kwargs["goods_no"]
    return client.call_paged(METHOD_FINANCE_GOODS_SUMMARY, bizcontent)


def list_accounts(**kwargs):
    return call_finance_api("accounts_listall", kwargs)


def create_acdoc(data: dict):
    return call_finance_api("acdoc_create", data)


def query_acdocs(**kwargs):
    return call_finance_api("acdoc_query", kwargs)


def query_acdoc_details(**kwargs):
    return call_finance_api("acdocdetail_query", kwargs)


def create_payment_apply(data: dict):
    return call_finance_api("paymentapply_create", data)


def list_payment_apply(**kwargs):
    return call_finance_api("paymentapply_listinfo", kwargs)


def create_fbs_bill(data: dict):
    return call_finance_api("fbs_createbill", data)


def list_arap_details(**kwargs):
    return call_finance_api("fbs_arapdetail_listarap", kwargs)
