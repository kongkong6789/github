"""
High-frequency business workflows.

This module keeps existing low-level API wrappers untouched and adds
task-oriented entry points for common ERP operations.
"""
from __future__ import annotations

from datetime import date, timedelta

from jackyun_api import JackyunValidationError

from helpers.experience_store import append_feedback_log, build_workflow_feedback_entry
from helpers.local_store import append_experience, increment_user_preference_counter, set_user_preference
from helpers.runtime_plan import workflow_route_plan
from modules import aftersales, combined, delivery_note, inventory, reports, sales_order, stock_doc, templates, transfer


def _has_batch_selection(item: dict) -> bool:
    return bool(
        item.get("batchNo")
        or item.get("batch_no")
        or item.get("batchNos")
        or item.get("batch_no_list")
        or item.get("batchList")
        or item.get("batch_list")
    )


def _summarize_goods_list(goods_list: list, qty_fields: tuple[str, ...]) -> dict:
    total_quantity = 0
    goods_nos = []
    for item in goods_list or []:
        goods_no = item.get("goodsNo") or item.get("goods_no")
        if goods_no:
            goods_nos.append(str(goods_no))
        for field in qty_fields:
            value = item.get(field)
            if value not in (None, "", 0, "0"):
                try:
                    total_quantity += int(float(value))
                except (TypeError, ValueError):
                    pass
                break
    return {
        "goods_line_count": len(goods_list or []),
        "goods_nos": goods_nos[:10],
        "total_quantity": total_quantity,
    }


def _resolve_report_period(period: str = None, month: str = None, start_time: str = None, end_time: str = None) -> tuple[str, str, str]:
    """
    Resolve common Chinese reporting periods without fetching order details.
    """
    period_text = str(period or "").strip()
    today = date.today()
    if period_text in {"昨天", "yesterday"}:
        yesterday = today - timedelta(days=1)
        return None, yesterday.isoformat(), yesterday.isoformat()
    if period_text in {"今天", "today"}:
        return None, today.isoformat(), today.isoformat()
    if period_text in {"这个月", "本月", "this_month"}:
        return today.strftime("%Y-%m"), None, None
    if period_text in {"上个月", "上月", "last_month"}:
        first_this_month = today.replace(day=1)
        last_month_day = first_this_month - timedelta(days=1)
        return last_month_day.strftime("%Y-%m"), None, None
    return month, start_time, end_time


def _normalize_report_trade_status(value) -> str | int | None:
    """
    Normalize user-facing order status names to the report API status.

    The goods multidimensional report documents tradeStatus as:
    0 未发货, 4040 部分发货, 6000 已发货.
    For the user's UI wording "发货在途/已完成", the report-side equivalent is
    currently treated as 6000 已发货.
    """
    if value in (None, "", []):
        return None
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(_normalize_report_trade_status(item)) for item in value if _normalize_report_trade_status(item))
    text = str(value).strip()
    aliases = {
        "发货在途": "6000",
        "已完成": "6000",
        "已发货": "6000",
        "发货在途或已完成": "6000",
        "发货在途或者已完成": "6000",
        "shipped_or_completed": "6000",
        "shipped": "6000",
        "completed": "6000",
    }
    return aliases.get(text, value)


def _build_sales_order_steps(order_type: str, submit_audit: bool, batch_confirmation: bool) -> list[dict]:
    steps = [
        {"step": "confirm_order_type", "status": "success", "message": f"order_type={order_type}"},
        {"step": "resolve_channel_warehouse_logistics", "status": "success", "message": "resolved channel/warehouse/logistics"},
    ]
    if batch_confirmation:
        steps.append({"step": "confirm_batches", "status": "pending", "message": "waiting for user batch confirmation"})
    else:
        steps.append({"step": "allocate_batches", "status": "success", "message": "used explicit batches or auto allocation"})
        steps.append({"step": "create_trade", "status": "success", "message": "sales order created"})
        steps.append({
            "step": "submit_audit" if submit_audit else "skip_audit",
            "status": "success" if submit_audit else "skipped",
            "message": "audit submitted" if submit_audit else "created only, audit not submitted",
        })
    return steps


def _build_sales_order_pain_points(result: dict, batch_confirmation: bool) -> list[str]:
    pain_points = []
    if batch_confirmation:
        pain_points.append("未确认批次前无法继续创建销售单")
    if result.get("requires_finance_review"):
        pain_points.append("提交审核后仍需财务FBP复核")
    if result.get("requires_approval_flow"):
        pain_points.append("提交审核后进入审批流，需继续关注流转")
    if not result.get("submit_audit"):
        pain_points.append("当前只创建未审核，后续仍需人工提交审核")
    return pain_points


def _build_sales_order_reuse_hints(order_type: str, batch_confirmation: bool) -> list[str]:
    hints = [
        "下次优先走 run_sales_order_workflow()，不要直接拼底层接口参数",
        "先准备：渠道、收件信息、货品数量、创建人",
        "建单前必须先看预检结果；有 errors 时只能补信息或给模板，不能直接创建",
    ]
    if order_type == "manual":
        hints.append("普通手工单要提前准备单价和金额；赠品请显式传 isGift=1")
    if batch_confirmation:
        hints.append("如涉及批次管理，默认按 FIFO 先进先出自动拆分 batchList；有额外要求时先筛选批次再按 FIFO 分配")
    return hints


def _build_sales_preflight_input(order_type: str, batch_strategy: str, kwargs: dict) -> dict:
    return {
        "order_type": order_type,
        "shop_name": kwargs.get("shop_name", ""),
        "receiver_name": kwargs.get("receiver_name", ""),
        "mobile": kwargs.get("mobile", ""),
        "address": kwargs.get("address", ""),
        "goods_list": kwargs.get("goods_list") or [],
        "warehouse_name": kwargs.get("warehouse_name"),
        "logistic_name": kwargs.get("logistic_name"),
        "customer_name": kwargs.get("customer_name") or kwargs.get("customerName"),
        "seller_name": kwargs.get("seller_name"),
        "seller_user_id": kwargs.get("seller_user_id"),
        "seller_depart_code": kwargs.get("seller_depart_code"),
        "check_batches": True,
        "batch_strategy": batch_strategy,
        "allow_stock_shortage": bool(kwargs.get("allow_stock_shortage") or kwargs.get("allow_stock_shortage_create")),
    }


def _run_sales_order_preflight(order_type: str, batch_strategy: str, kwargs: dict) -> dict:
    return sales_order.preflight_sales_order(**_build_sales_preflight_input(order_type, batch_strategy, kwargs))


def _build_sales_order_needs_input_response(
    order_type: str,
    execution_plan: dict,
    preflight: dict,
    should_submit_audit: bool,
    goods_summary: dict,
    kwargs: dict,
) -> dict:
    missing_input = templates.build_missing_input_response(
        "sales_order",
        missing_fields=preflight.get("errors", []),
        message="销售单预检未通过，已阻止创建，避免在吉客云产生脏数据。",
    )
    feedback_entry = append_feedback_log(
        build_workflow_feedback_entry(
            "sales_order",
            "needs_input",
            "sales order creation blocked by preflight",
            order_type=order_type,
            next_action=missing_input["next_action"],
            input_summary={
                "shop_name": kwargs.get("shop_name"),
                "warehouse_name": kwargs.get("warehouse_name"),
                "submit_audit": should_submit_audit,
                **goods_summary,
            },
            steps=[
                {"step": "preflight_before_create", "status": "blocked", "message": preflight.get("next_action", "")},
                {"step": "create_trade", "status": "skipped", "message": "预检失败，未调用创建接口"},
            ],
            pain_points=preflight.get("errors", []),
            reuse_hints=[
                "补齐 template 中的必填字段后再创建",
                "如果用户纠正了字段或规则，调用 record_workflow_correction() 写入经验，避免下次重复踩坑",
            ],
        )
    )
    return {
        **feedback_entry,
        **missing_input,
        "workflow": "sales_order",
        "order_type": order_type,
        "execution_plan": execution_plan,
        "preflight": preflight,
        "submit_audit": should_submit_audit,
        "created": False,
    }


def _build_transfer_steps(quick_create: bool) -> list[dict]:
    return [
        {"step": "normalize_transfer_payload", "status": "success", "message": "normalized transfer payload"},
        {"step": "auto_fill_contacts_goods_batches", "status": "success", "message": "auto-filled contacts, goods and batches"},
        {
            "step": "submit_transfer",
            "status": "success",
            "message": "quick create submitted" if quick_create else "standard create submitted",
        },
    ]


def _build_transfer_pain_points(auto_fill_summary: dict) -> list[str]:
    pain_points = []
    if auto_fill_summary.get("batches"):
        pain_points.append("调拨批次依赖调出仓实时库存，库存变化会影响分配结果")
    if auto_fill_summary.get("goods"):
        pain_points.append("货品字段依赖自动补全结果，异常时需优先核对货品档案和条码")
    return pain_points


def _attach_created_transfer_snapshot(result: dict) -> None:
    """
    Query the newly created transfer document back and attach the display payload.
    """
    create_result = result.get("data") or result.get("create_result") or {}
    allocate_no = transfer.extract_allocate_no(create_result)
    if allocate_no:
        result["allocate_no"] = allocate_no
    else:
        result["created_transfer_query_error"] = "创建接口未返回调拨单号，无法反查单据"
        return
    try:
        result["created_transfer"] = transfer.query_transfer_by_no(allocate_no)
    except Exception as exc:  # pragma: no cover - keep workflow result usable on query failure
        result["created_transfer_query_error"] = str(exc)


def _build_stock_doc_steps(doc_type: str, auto_check: bool) -> list[dict]:
    steps = [
        {"step": "prepare_stock_doc", "status": "success", "message": f"doc_type={doc_type}"},
        {"step": "create_stock_doc", "status": "success", "message": "stock document created"},
    ]
    steps.append({
        "step": "check_stock_doc",
        "status": "success" if auto_check else "skipped",
        "message": "auto check completed" if auto_check else "created only, not checked",
    })
    return steps


def _build_stock_apply_steps(doc_type: str, batch_count: int) -> list[dict]:
    return [
        {"step": "normalize_stock_apply", "status": "success", "message": f"doc_type={doc_type}"},
        {"step": "resolve_applicant_warehouse_goods", "status": "success", "message": "resolved applicant, warehouse and goods"},
        {
            "step": "auto_allocate_batches",
            "status": "success" if batch_count else "skipped",
            "message": f"{batch_count} batch allocations" if batch_count else "no auto batch allocation needed",
        },
        {"step": "create_stock_apply", "status": "success", "message": "stock application created"},
        {"step": "query_created_stock_apply", "status": "success", "message": "created application queried back when number is available"},
    ]


def _build_inventory_export_steps(include_batch_details: bool) -> list[dict]:
    return [
        {"step": "query_inventory", "status": "success", "message": "inventory data queried"},
        {
            "step": "export_batch_details" if include_batch_details else "skip_batch_details",
            "status": "success" if include_batch_details else "skipped",
            "message": "batch details exported" if include_batch_details else "main export only",
        },
    ]


def _get_sales_order_submit_flow(order_type: str, is_online_order: bool) -> dict:
    if is_online_order:
        return {
            "post_submit_flow": "提交审核后直接递交仓库，无需复核",
            "requires_finance_review": False,
            "requires_approval_flow": False,
            "submit_target": "warehouse",
        }
    if order_type == "sample":
        return {
            "post_submit_flow": "提交审核后进入审批流，流转后自动递交仓库",
            "requires_finance_review": False,
            "requires_approval_flow": True,
            "submit_target": "approval_flow",
        }
    return {
        "post_submit_flow": "提交审核后进入复核，请联系财务FBP复核，复核后递交仓库",
        "requires_finance_review": True,
        "requires_approval_flow": False,
        "submit_target": "finance_review",
    }


def _attach_created_trade_snapshot(result: dict) -> None:
    """
    Query the newly created sales order back and attach the full display payload.
    """
    trade_no = result.get("trade_no")
    if not trade_no:
        result["created_trade_query_error"] = "创建接口未返回销售单号，无法反查单据"
        return
    try:
        result["created_trade"] = sales_order.query_trade_by_no(trade_no)
    except Exception as exc:  # pragma: no cover - keep workflow result usable on query failure
        result["created_trade_query_error"] = str(exc)


def run_sales_order_workflow(
    order_type: str,
    auto_audit: bool = False,
    submit_audit: bool = None,
    is_online_order: bool = False,
    batch_strategy: str = "fifo",
    require_batch_confirmation: bool = False,
    preflight_only: bool = False,
    allow_stock_shortage_create: bool = False,
    **kwargs,
) -> dict:
    """
    High-frequency workflow for manual/sample/resend sales orders.
    """
    execution_plan = workflow_route_plan("sales_order")
    goods_list = kwargs.get("goods_list") or []
    goods_summary = _summarize_goods_list(goods_list, ("sellCount", "qty", "quantity", "count"))
    should_submit_audit = auto_audit if submit_audit is None else submit_audit
    if allow_stock_shortage_create:
        kwargs["allow_stock_shortage"] = True
        kwargs["allow_stock_shortage_create"] = True
    if preflight_only:
        preflight = _run_sales_order_preflight(order_type, batch_strategy, kwargs)
        append_feedback_log(
            build_workflow_feedback_entry(
                "sales_order",
                "preflight_ok" if preflight.get("ok") else "preflight_blocked",
                "sales order preflight completed",
                order_type=order_type,
                next_action=preflight.get("next_action"),
                input_summary={
                    "shop_name": kwargs.get("shop_name"),
                    "warehouse_name": kwargs.get("warehouse_name"),
                    "submit_audit": should_submit_audit,
                    **goods_summary,
                },
                steps=[
                    {"step": "resolve_channel_warehouse_logistics", "status": "success" if preflight.get("resolved") else "blocked", "message": "preflight resolution completed"},
                    {"step": "validate_seller_goods_batches", "status": "success" if preflight.get("ok") else "blocked", "message": preflight.get("next_action", "")},
                ],
                pain_points=preflight.get("errors", []),
                reuse_hints=["实际创建前优先跑 preflight_only=True，批量导入先 dry_run=True"],
            )
        )
        return {
            "status": "preflight_ok" if preflight.get("ok") else "preflight_blocked",
            "workflow": "sales_order",
            "order_type": order_type,
            "execution_plan": execution_plan,
            "preflight": preflight,
            "next_action": preflight.get("next_action"),
        }

    preflight = _run_sales_order_preflight(order_type, batch_strategy, kwargs)
    if not preflight.get("ok"):
        return _build_sales_order_needs_input_response(
            order_type=order_type,
            execution_plan=execution_plan,
            preflight=preflight,
            should_submit_audit=should_submit_audit,
            goods_summary=goods_summary,
            kwargs=kwargs,
        )

    stock_shortage_pending = (
        preflight.get("batch_summary", {}).get("all_enough_stock") is False
        and preflight.get("batch_summary", {}).get("stock_shortage_allowed")
    )
    if stock_shortage_pending and should_submit_audit:
        should_submit_audit = False
        kwargs["seller_memo"] = (
            (kwargs.get("seller_memo") or kwargs.get("sellerMemo") or kwargs.get("remark") or "").strip()
            + " | 库存不足先建单，待库存到货后匹配批次再审核发货"
        ).strip(" |")

    if require_batch_confirmation and goods_list and any(not _has_batch_selection(item) for item in goods_list):
        batch_plan = sales_order.prepare_sales_order_batches(
            shop_name=kwargs.get("shop_name", ""),
            goods_list=goods_list,
            warehouse_name=kwargs.get("warehouse_name"),
            strategy=batch_strategy,
        )
        return {
            **append_feedback_log(
                build_workflow_feedback_entry(
                    "sales_order",
                    "needs_batch_confirmation",
                    "sales order requires batch confirmation before create",
                    order_type=order_type,
                    next_action="请确认批次后，再继续创建销售单",
                    input_summary={
                        "shop_name": kwargs.get("shop_name"),
                        "warehouse_name": kwargs.get("warehouse_name"),
                        "submit_audit": should_submit_audit,
                        **goods_summary,
                    },
                    steps=_build_sales_order_steps(order_type, should_submit_audit, True),
                    pain_points=["未确认批次前无法继续创建销售单"],
                    reuse_hints=_build_sales_order_reuse_hints(order_type, True),
                )
            ),
            "status": "needs_batch_confirmation",
            "workflow": "sales_order",
            "order_type": order_type,
            "execution_plan": execution_plan,
            "batch_plan": batch_plan,
            "next_action": "请确认批次后，再继续创建销售单",
            "submit_audit": should_submit_audit,
        }

    if order_type == "manual":
        if should_submit_audit:
            result = sales_order.create_manual_order_and_audit(**kwargs)
        else:
            create_result = sales_order.create_manual_order(**kwargs)
            result = {
                "create_result": create_result,
                "trade_no": sales_order._extract_trade_no(create_result),
                "audit_result": None,
            }
    elif order_type == "sample":
        kwargs.setdefault("order_type", "JY")
        if should_submit_audit:
            result = sales_order.create_sample_order_and_audit(**kwargs)
        else:
            create_result = sales_order.create_sample_order(**kwargs)
            result = {
                "create_result": create_result,
                "trade_no": sales_order._extract_trade_no(create_result),
                "audit_result": None,
            }
    elif order_type == "resend":
        kwargs.setdefault("order_type", "BF")
        if should_submit_audit:
            result = sales_order.create_sample_order_and_audit(**kwargs)
        else:
            create_result = sales_order.create_sample_order(**kwargs)
            result = {
                "create_result": create_result,
                "trade_no": sales_order._extract_trade_no(create_result),
                "audit_result": None,
            }
    else:
        raise JackyunValidationError(f"不支持的销售单工作流类型: {order_type}")

    _attach_created_trade_snapshot(result)
    result.update(_get_sales_order_submit_flow(order_type, is_online_order))
    result["submit_audit"] = should_submit_audit
    result["stock_shortage_pending"] = bool(stock_shortage_pending)
    result["status"] = "completed"
    result["workflow"] = "sales_order"
    result["execution_plan"] = execution_plan
    if not should_submit_audit:
        result["next_action"] = "当前仅创建单据，未提交审核"
    if stock_shortage_pending:
        result["next_action"] = "库存不足已先建单；待库存到货后匹配批次，再审核并递交仓库发货"
        result.setdefault("warnings", []).append("本单为库存不足先建单，不应立即审核发货")
    append_feedback_log(
        build_workflow_feedback_entry(
            "sales_order",
            "completed",
            "sales order workflow completed",
            order_type=order_type,
            trade_no=result.get("trade_no"),
            next_action=result.get("next_action") or result.get("post_submit_flow"),
            requires_finance_review=result.get("requires_finance_review"),
            requires_approval_flow=result.get("requires_approval_flow"),
            submit_target=result.get("submit_target"),
            input_summary={
                "shop_name": kwargs.get("shop_name"),
                "warehouse_name": kwargs.get("warehouse_name"),
                "submit_audit": should_submit_audit,
                **goods_summary,
            },
            steps=_build_sales_order_steps(order_type, should_submit_audit, False),
            pain_points=_build_sales_order_pain_points(result, False),
            reuse_hints=_build_sales_order_reuse_hints(order_type, False),
        )
    )
    return result


def record_workflow_correction(
    workflow: str,
    issue: str,
    user_correction: str = "",
    root_cause: str = "",
    prevention_rule: str = "",
    input_summary: dict = None,
    corrected_fields: dict = None,
) -> dict:
    """
    Record a user correction as reusable local learning.

    Call this after a user corrects a wrong workflow result. The record is kept
    outside SKILL.md so reinstalling packaged skill code does not hard-code a
    one-off case, while future preflight can still surface the lesson.
    """
    normalized_workflow = str(workflow or "").strip() or "general"
    corrected_fields = corrected_fields or {}
    record = append_experience(
        "corrections",
        {
            "workflow": normalized_workflow,
            "issue": str(issue or "").strip(),
            "user_correction": str(user_correction or "").strip(),
            "root_cause": str(root_cause or "").strip(),
            "prevention_rule": str(prevention_rule or "").strip(),
            "input_summary": input_summary or {},
            "corrected_fields": corrected_fields,
        },
    )

    if normalized_workflow == "sales_order":
        field_to_group = {
            "shop_name": "sales_order.all.shopName",
            "shopName": "sales_order.all.shopName",
            "warehouse_name": "sales_order.all.warehouseName",
            "warehouseName": "sales_order.all.warehouseName",
            "logistic_name": "sales_order.all.logisticName",
            "logisticName": "sales_order.all.logisticName",
            "seller_name": "sales_order.all.sellerName",
            "sellerName": "sales_order.all.sellerName",
            "customer_name": "sales_order.all.customerName",
            "customerName": "sales_order.all.customerName",
        }
        for field, value in corrected_fields.items():
            group = field_to_group.get(field)
            if group:
                increment_user_preference_counter(group, field, value)
        if corrected_fields.get("batch_strategy"):
            set_user_preference("default_batch_strategy", corrected_fields["batch_strategy"])

    feedback_entry = append_feedback_log(
        build_workflow_feedback_entry(
            normalized_workflow,
            "learned_correction",
            "workflow correction recorded for future prevention",
            next_action="下次执行同类流程时，先参考本次 root_cause 和 prevention_rule 做预检。",
            input_summary=input_summary or {},
            pain_points=[str(issue or "").strip()] if issue else [],
            reuse_hints=[
                hint for hint in (
                    str(prevention_rule or "").strip(),
                    "纠正后要重新跑预检；预检通过前禁止创建单据",
                ) if hint
            ],
        )
    )
    return {
        "status": "learned",
        "workflow": normalized_workflow,
        "record": record,
        "feedback": feedback_entry,
        "next_action": "已记录纠错经验；后续同类建单会在预检提示中暴露该规则。",
    }


def run_pending_sales_order_workflow(action: str, **kwargs) -> dict:
    """
    High-frequency workflow for operations handling of pending online orders.
    """
    if action == "summarize":
        data = sales_order.summarize_pending_shop_orders(
            shop_name=kwargs.get("shop_name"),
            start_trade_time=kwargs.get("start_trade_time"),
            end_trade_time=kwargs.get("end_trade_time"),
        )
    elif action == "list":
        data = sales_order.list_pending_trade_candidates(
            shop_name=kwargs.get("shop_name"),
            start_trade_time=kwargs.get("start_trade_time"),
            end_trade_time=kwargs.get("end_trade_time"),
            page_size=kwargs.get("limit", 200),
        )
    elif action == "diagnose":
        data = sales_order.diagnose_pending_trade_candidates(
            shop_name=kwargs.get("shop_name"),
            start_trade_time=kwargs.get("start_trade_time"),
            end_trade_time=kwargs.get("end_trade_time"),
            limit=kwargs.get("limit", 200),
            check_stock=kwargs.get("check_stock", True),
        )
    elif action == "audit":
        data = sales_order.batch_audit_pending_trades_by_filter(
            shop_name=kwargs.get("shop_name"),
            start_trade_time=kwargs.get("start_trade_time"),
            end_trade_time=kwargs.get("end_trade_time"),
            operator=kwargs.get("operator"),
            limit=kwargs.get("limit", 200),
        )
    elif action == "update_logistics":
        data = sales_order.batch_update_pending_trades_logistics_by_filter(
            warehouse_name=kwargs["warehouse_name"],
            logistic_name=kwargs["logistic_name"],
            shop_name=kwargs.get("shop_name"),
            start_trade_time=kwargs.get("start_trade_time"),
            end_trade_time=kwargs.get("end_trade_time"),
            limit=kwargs.get("limit", 200),
        )
    else:
        raise JackyunValidationError(f"不支持的待审核工作流动作: {action}")

    result = {
        "status": "completed",
        "workflow": "pending_sales_order",
        "action": action,
        "execution_plan": workflow_route_plan("pending_sales_order"),
        "data": data,
    }
    append_feedback_log(
        build_workflow_feedback_entry(
            "pending_sales_order",
            "completed",
            "pending sales order workflow completed",
            action=action,
            input_summary={
                "shop_name": kwargs.get("shop_name"),
                "limit": kwargs.get("limit", 200),
                "start_trade_time": kwargs.get("start_trade_time"),
                "end_trade_time": kwargs.get("end_trade_time"),
            },
            steps=[{"step": action, "status": "success", "message": "pending workflow action completed"}],
            reuse_hints=["下次可直接复用相同筛选条件执行待审核工作流"],
        )
    )
    return result


def run_transfer_workflow(
    transfer_data: dict,
    quick_create: bool = False,
    batch_strategy: str = "fifo",
    require_batch_confirmation: bool = False,
    allow_stock_shortage_create: bool = False,
) -> dict:
    """
    High-frequency workflow for transfer creation.
    """
    execution_plan = workflow_route_plan("transfer")
    if allow_stock_shortage_create:
        transfer_data = dict(transfer_data)
        transfer_data["allow_stock_shortage_create"] = True
    goods_list = transfer_data.get("stockAllocateDetailViews") or transfer_data.get("goodsList") or []
    goods_summary = _summarize_goods_list(goods_list, ("skuCount", "qty", "quantity", "count"))
    if require_batch_confirmation and goods_list and any(not _has_batch_selection(item) for item in goods_list):
        batch_plan = transfer.prepare_transfer_batches(
            out_warehouse_code=transfer_data.get("outWarehouseCode", ""),
            goods_list=goods_list,
            strategy=batch_strategy,
        )
        return {
            **append_feedback_log(
                build_workflow_feedback_entry(
                    "transfer",
                    "needs_batch_confirmation",
                    "transfer requires batch confirmation before create",
                    next_action="请确认调拨批次后，再继续创建调拨单",
                    input_summary={
                        "out_warehouse_code": transfer_data.get("outWarehouseCode"),
                        "int_warehouse_code": transfer_data.get("intWarehouseCode"),
                        "quick_create": quick_create,
                        "allow_stock_shortage_create": allow_stock_shortage_create,
                        **goods_summary,
                    },
                    steps=[
                        {"step": "prepare_transfer_batches", "status": "success", "message": "batch recommendations prepared"},
                        {"step": "confirm_batches", "status": "pending", "message": "waiting for user batch confirmation"},
                    ],
                    pain_points=["调拨单缺少批次确认时不能直接创建"],
                    reuse_hints=["下次先准备调出仓、调入仓和货品数量；如需要可直接复用批次推荐结果"],
                )
            ),
            "status": "needs_batch_confirmation",
            "workflow": "transfer",
            "execution_plan": execution_plan,
            "batch_plan": batch_plan,
            "next_action": "请确认调拨批次后，再继续创建调拨单",
        }

    try:
        prepared_payload, auto_fill_summary = transfer.prepare_transfer_payload(
            transfer_data,
            batch_strategy=batch_strategy,
            allow_stock_shortage=allow_stock_shortage_create,
        )
    except JackyunValidationError as exc:
        missing_input = templates.build_missing_input_response(
            "transfer",
            missing_fields=[str(exc)],
            message="调拨单信息不完整或不合法，已阻止创建，避免在吉客云产生脏数据。",
        )
        feedback_entry = append_feedback_log(
            build_workflow_feedback_entry(
                "transfer",
                "needs_input",
                "transfer creation blocked before submit",
                next_action=missing_input["next_action"],
                input_summary={
                    "out_warehouse_code": transfer_data.get("outWarehouseCode"),
                    "int_warehouse_code": transfer_data.get("intWarehouseCode"),
                    "quick_create": quick_create,
                    "allow_stock_shortage_create": allow_stock_shortage_create,
                    **goods_summary,
                },
                steps=[
                    {"step": "prepare_transfer_payload", "status": "blocked", "message": str(exc)},
                    {"step": "submit_transfer", "status": "skipped", "message": "字段未通过校验，未调用创建接口"},
                ],
                pain_points=[str(exc)],
                reuse_hints=["补齐调出仓、调入仓、货品数量和必要自定义字段后再创建"],
            )
        )
        return {
            **feedback_entry,
            **missing_input,
            "workflow": "transfer",
            "execution_plan": execution_plan,
            "created": False,
        }
    data = transfer.submit_transfer_payload(prepared_payload, quick_create=quick_create)
    result = {
        "status": "completed",
        "workflow": "transfer",
        "quick_create": quick_create,
        "execution_plan": execution_plan,
        "auto_fill_summary": auto_fill_summary,
        "data": data,
    }
    if any((item.get("status") == "stock_shortage_pending") for item in auto_fill_summary.get("batches", [])):
        result["stock_shortage_pending"] = True
        result["next_action"] = "调拨单已按缺货先建单模式创建；待库存到货后补匹配批次，再继续后续调拨处理"
        result.setdefault("warnings", []).append("存在货品库存不足，仅标记批次管理，未写入 batchList")
    _attach_created_transfer_snapshot(result)
    append_feedback_log(
        build_workflow_feedback_entry(
            "transfer",
            "completed",
            "transfer workflow completed",
            document_no=result.get("allocate_no"),
            next_action=result.get("next_action") or "请按业务状态继续关注调拨单后续处理",
            input_summary={
                "out_warehouse_code": transfer_data.get("outWarehouseCode"),
                "int_warehouse_code": transfer_data.get("intWarehouseCode"),
                "quick_create": quick_create,
                "allow_stock_shortage_create": allow_stock_shortage_create,
                **goods_summary,
            },
            steps=_build_transfer_steps(quick_create),
            pain_points=_build_transfer_pain_points(auto_fill_summary),
            reuse_hints=[
                "下次优先走 run_transfer_workflow()，让系统自动补全联系人、货品和批次",
                "跨主体调拨前先确认公司编码、币种和税率字段",
            ],
            auto_fill_summary=auto_fill_summary,
        )
    )
    return result


def run_stock_doc_workflow(doc_type: str, doc_data: dict, auto_check: bool = False) -> dict:
    """
    High-frequency workflow for stock in/out document creation.
    """
    try:
        if doc_type == "out":
            create_result = stock_doc.create_doc_out(doc_data)
        elif doc_type == "in":
            create_result = stock_doc.create_doc_in(doc_data)
        else:
            raise JackyunValidationError(f"不支持的出入库工作流类型: {doc_type}")
    except JackyunValidationError as exc:
        missing_input = templates.build_missing_input_response(
            "stock_doc",
            missing_fields=[str(exc)],
            message="出入库单信息不完整或不合法，已阻止创建，避免在吉客云产生脏数据。",
        )
        feedback_entry = append_feedback_log(
            build_workflow_feedback_entry(
                "stock_doc",
                "needs_input",
                "stock document creation blocked before submit",
                next_action=missing_input["next_action"],
                input_summary={
                    "doc_type": doc_type,
                    "warehouse_name": doc_data.get("warehouseName"),
                    "warehouse_code": doc_data.get("warehouseCode"),
                    **_summarize_goods_list(doc_data.get("goodsDocDetailList") or [], ("quantity",)),
                },
                steps=[
                    {"step": "validate_stock_doc", "status": "blocked", "message": str(exc)},
                    {"step": "create_stock_doc", "status": "skipped", "message": "字段未通过校验，未调用创建接口"},
                ],
                pain_points=[str(exc)],
                reuse_hints=["补齐出入库类型、仓库和货品数量后再创建"],
            )
        )
        return {
            **feedback_entry,
            **missing_input,
            "workflow": "stock_doc",
            "doc_type": doc_type,
            "execution_plan": workflow_route_plan("stock_doc"),
            "created": False,
        }

    result = {
        "status": "completed",
        "workflow": "stock_doc",
        "doc_type": doc_type,
        "execution_plan": workflow_route_plan("stock_doc"),
        "create_result": create_result,
    }
    payload = create_result.get("result", {}) if isinstance(create_result, dict) else {}

    if auto_check:
        result["check_result"] = stock_doc.check_doc(
            rec_id=payload.get("recId"),
            goodsdoc_no=payload.get("goodsdocNo") or payload.get("billNo"),
        )
    append_feedback_log(
        build_workflow_feedback_entry(
            "stock_doc",
            "completed",
            "stock document workflow completed",
            document_no=str(payload.get("goodsdocNo") or payload.get("billNo") or ""),
            next_action="如有需要，可继续审核出入库单",
            input_summary={
                "doc_type": doc_type,
                "warehouse_name": doc_data.get("warehouseName"),
                "warehouse_code": doc_data.get("warehouseCode"),
                **_summarize_goods_list(doc_data.get("goodsDocDetailList") or [], ("quantity",)),
            },
            steps=_build_stock_doc_steps(doc_type, auto_check),
            pain_points=(["当前只创建未审核，后续仍需人工审核"] if not auto_check else []),
            reuse_hints=[
                "下次出库单如未手填批次，可直接让系统按仓库库存自动拆分 batchList",
                "先准备 inouttype、仓库和货品数量，再创建出入库单",
            ],
        )
    )
    return result


def run_stock_apply_workflow(doc_type: str, apply_data: dict, batch_strategy: str = "fifo") -> dict:
    """
    High-frequency workflow for inbound/outbound stock application creation.

    This uses erp.storage.stockincreate / erp.storage.stockoutcreate, not the
    lower-level goodsdoc add APIs. The applicant must be a confirmed user name.
    """
    execution_plan = workflow_route_plan("stock_apply")
    goods_key = "stockOutDetailViews" if doc_type == "out" else "stockInDetailViews"
    raw_goods = apply_data.get(goods_key) or apply_data.get("goodsList") or []
    goods_summary = _summarize_goods_list(raw_goods, ("skuCount", "quantity", "qty", "count"))
    try:
        prepared_payload, auto_fill_summary = stock_doc.prepare_stock_apply_payload(
            doc_type,
            apply_data,
            batch_strategy=batch_strategy,
        )
        if doc_type == "out":
            create_result = stock_doc.submit_stock_out_apply_payload(prepared_payload)
            apply_no = stock_doc.extract_stock_apply_no("out", create_result, prepared_payload)
            created_apply = (
                stock_doc.query_stock_out_apply(out_no=apply_no, rel_data_id=prepared_payload.get("relDataId"))[:1]
                if apply_no or prepared_payload.get("relDataId") else []
            )
        elif doc_type == "in":
            create_result = stock_doc.submit_stock_in_apply_payload(prepared_payload)
            apply_no = stock_doc.extract_stock_apply_no("in", create_result, prepared_payload)
            created_apply = (
                stock_doc.query_stock_in_apply(in_no=apply_no, rel_data_id=prepared_payload.get("relDataId"))[:1]
                if apply_no or prepared_payload.get("relDataId") else []
            )
        else:
            raise JackyunValidationError(f"不支持的申请单类型: {doc_type}")
    except JackyunValidationError as exc:
        missing_input = templates.build_missing_input_response(
            "stock_apply",
            missing_fields=[str(exc)],
            message="出入库申请单信息不完整或不合法，已阻止创建，避免在吉客云产生脏数据。",
        )
        feedback_entry = append_feedback_log(
            build_workflow_feedback_entry(
                "stock_apply",
                "needs_input",
                "stock application creation blocked before submit",
                next_action=missing_input["next_action"],
                input_summary={
                    "doc_type": doc_type,
                    "warehouse_name": apply_data.get("warehouseName"),
                    "applicant": apply_data.get("applyUserName") or apply_data.get("applicant_name"),
                    **goods_summary,
                },
                steps=[
                    {"step": "prepare_stock_apply_payload", "status": "blocked", "message": str(exc)},
                    {"step": "create_stock_apply", "status": "skipped", "message": "字段未通过校验，未调用创建接口"},
                ],
                pain_points=[str(exc)],
                reuse_hints=["补齐申请人、仓库、类型、货品数量后再创建；申请人必须是员工姓名"],
            )
        )
        return {
            **feedback_entry,
            **missing_input,
            "workflow": "stock_apply",
            "doc_type": doc_type,
            "execution_plan": execution_plan,
            "created": False,
        }

    batch_count = len(auto_fill_summary.get("batches") or [])
    result = {
        "status": "completed",
        "workflow": "stock_apply",
        "doc_type": doc_type,
        "execution_plan": execution_plan,
        "apply_no": apply_no,
        "auto_fill_summary": auto_fill_summary,
        "create_result": create_result,
        "created_apply": created_apply[0] if created_apply else None,
    }
    append_feedback_log(
        build_workflow_feedback_entry(
            "stock_apply",
            "completed",
            "stock application workflow completed",
            document_no=apply_no,
            next_action="出入库申请单已创建；如接口未返回完整字段，请以 created_apply 反查结果为准",
            input_summary={
                "doc_type": doc_type,
                "warehouse_code": auto_fill_summary.get("warehouse_code"),
                "applicant": auto_fill_summary.get("applicant"),
                "batch_strategy": batch_strategy,
                **goods_summary,
            },
            steps=_build_stock_apply_steps(doc_type, batch_count),
            pain_points=(["出库申请单批次按出库仓实时库存 FIFO 分配，库存变化会影响结果"] if batch_count else []),
            reuse_hints=[
                "入库/出库申请单优先走 run_stock_apply_workflow()，不要用 goodsdoc.add 替代",
                "申请人必须传员工姓名 applyUserName；出库申请不传批次时默认按 FIFO 自动拆 batchList",
            ],
            auto_fill_summary=auto_fill_summary,
        )
    )
    return result


def run_inventory_export_workflow(
    output_path: str,
    warehouse_code: str = None,
    goods_no: str = None,
    goods_name: str = None,
    sku_name: str = None,
    sku_barcode: str = None,
    unit_name: str = None,
    include_batch_details: bool = False,
    use_chinese_headers: bool = True,
) -> dict:
    """
    Export inventory report with optional batch detail attachment.
    """
    export_result = inventory.export_stock_quantity_report(
        output_path=output_path,
        warehouse_code=warehouse_code,
        goods_no=goods_no,
        goods_name=goods_name,
        sku_name=sku_name,
        sku_barcode=sku_barcode,
        unit_name=unit_name,
        include_batch_details=include_batch_details,
        use_chinese_headers=use_chinese_headers,
    )
    result = {
        "status": "completed",
        "workflow": "inventory_export",
        "execution_plan": workflow_route_plan("inventory_export"),
        "data": export_result,
    }
    append_feedback_log(
        build_workflow_feedback_entry(
            "inventory_export",
            "completed",
            "inventory export workflow completed",
            next_action=(
                f"库存导出已生成: {export_result.get('output_path')}"
                + (
                    f"；批次明细: {export_result.get('batch_output_path')}"
                    if export_result.get("batch_output_path")
                    else ""
                )
            ),
            input_summary={
                "warehouse_code": warehouse_code,
                "goods_no": goods_no,
                "goods_name": goods_name,
                "include_batch_details": include_batch_details,
                "use_chinese_headers": use_chinese_headers,
            },
            steps=_build_inventory_export_steps(include_batch_details),
            pain_points=(["附带批次明细会额外生成第二份文件"] if include_batch_details else []),
            reuse_hints=["下次可直接复用相同仓库和筛选条件导出库存"],
        )
    )
    return result


def run_goods_sales_analysis_workflow(
    output_path: str = None,
    query_time_begin: str = None,
    query_time_end: str = None,
    start_time: str = None,
    end_time: str = None,
    month: str = None,
    shop_names: list[str] | str = None,
    shop_ids: list[str] | str = None,
    channel_include_keyword: str = None,
    channel_exclude_keywords: list[str] | str = None,
    channel_active_only: bool = False,
    summary_types: str = "channel,goods",
    filter_time_type: int = 2,
    use_chinese_headers: bool = True,
    **filters,
) -> dict:
    """
    Query or export goods sales multidimensional analysis.
    """
    query_kwargs = {
        "query_time_begin": query_time_begin,
        "query_time_end": query_time_end,
        "start_time": start_time,
        "end_time": end_time,
        "month": month,
        "shop_names": shop_names,
        "shop_ids": shop_ids,
        "channel_include_keyword": channel_include_keyword,
        "channel_exclude_keywords": channel_exclude_keywords,
        "channel_active_only": channel_active_only,
        "summary_types": summary_types,
        "filter_time_type": filter_time_type,
        **filters,
    }
    if output_path:
        data = reports.export_goods_sales_analysis_report(
            output_path=output_path,
            use_chinese_headers=use_chinese_headers,
            **query_kwargs,
        )
    else:
        data = reports.query_goods_sales_analysis(**query_kwargs)

    result = {
        "status": "completed",
        "workflow": "goods_sales_analysis",
        "execution_plan": workflow_route_plan("goods_sales_analysis"),
        "data": data,
    }
    append_feedback_log(
        build_workflow_feedback_entry(
            "goods_sales_analysis",
            "completed",
            "goods sales multidimensional analysis queried",
            next_action=(
                f"货品销售多维分析报表已生成: {data.get('output_path')}"
                if output_path else
                f"已查询货品销售多维分析报表，共 {data.get('row_count')} 行"
            ),
            input_summary={
                "month": month,
                "query_time_begin": query_time_begin,
                "query_time_end": query_time_end,
                "shop_names": shop_names,
                "shop_ids": shop_ids,
                "channel_include_keyword": channel_include_keyword,
                "channel_exclude_keywords": channel_exclude_keywords,
                "summary_types": summary_types,
                "filter_time_type": filter_time_type,
                "row_count": data.get("row_count"),
            },
            steps=[
                {"step": "resolve_channels", "status": "success", "message": f"{len(data.get('resolved_shops') or [])} channels"},
                {"step": "query_report", "status": "success", "message": f"{data.get('row_count')} rows"},
                {"step": "export_file", "status": "success" if output_path else "skipped", "message": data.get("output_path", "")},
            ],
            reuse_hints=[
                "按月份和渠道查销售额/销量时优先走 run_goods_sales_analysis_workflow()",
                "默认汇总维度为 channel,goods；如需按规格、时间、仓库等维度，用户需明确 summary_types",
            ],
        )
    )
    return result


def run_channel_sales_summary_workflow(
    output_path: str = None,
    dimension: str = "channel_goods",
    period: str = None,
    month: str = None,
    start_time: str = None,
    end_time: str = None,
    shop_names: list[str] | str = None,
    shop_ids: list[str] | str = None,
    channel_include_keyword: str = None,
    channel_exclude_keywords: list[str] | str = None,
    channel_active_only: bool = False,
    filter_time_type: int = 2,
    trade_status: str | int = None,
    prefer_udr: bool = False,
    use_udr_fallback: bool = True,
    udr_report_id: str | int = None,
    udr_filters: dict | list[dict] | str = None,
    use_chinese_headers: bool = True,
    **filters,
) -> dict:
    """
    Frequent workflow: summarize sales quantity and amount by channel or by channel+goods.
    """
    month, start_time, end_time = _resolve_report_period(period=period, month=month, start_time=start_time, end_time=end_time)
    trade_status = _normalize_report_trade_status(trade_status)
    query_kwargs = {
        "month": month,
        "start_time": start_time,
        "end_time": end_time,
        "shop_names": shop_names,
        "shop_ids": shop_ids,
        "channel_include_keyword": channel_include_keyword,
        "channel_exclude_keywords": channel_exclude_keywords,
        "channel_active_only": channel_active_only,
        "filter_time_type": filter_time_type,
        **filters,
    }
    if trade_status not in (None, "", []):
        query_kwargs["trade_status"] = trade_status
    if output_path:
        data = reports.export_channel_sales_summary_report(
            output_path=output_path,
            dimension=dimension,
            use_chinese_headers=use_chinese_headers,
            prefer_udr=prefer_udr,
            use_udr_fallback=use_udr_fallback,
            udr_report_id=udr_report_id,
            udr_filters=udr_filters,
            **query_kwargs,
        )
    else:
        data = reports.query_channel_sales_summary(
            dimension=dimension,
            prefer_udr=prefer_udr,
            use_udr_fallback=use_udr_fallback,
            udr_report_id=udr_report_id,
            udr_filters=udr_filters,
            **query_kwargs,
        )

    result = {
        "status": "completed",
        "workflow": "channel_sales_summary",
        "execution_plan": workflow_route_plan("channel_sales_summary"),
        "data": data,
    }
    append_feedback_log(
        build_workflow_feedback_entry(
            "channel_sales_summary",
            "completed",
            "channel sales summary queried",
            next_action=(
                f"渠道销售汇总已生成: {data.get('output_path')}"
                if output_path else
                f"已查询渠道销售汇总，共 {data.get('row_count')} 行"
            ),
            input_summary={
                "dimension": dimension,
                "period": period,
                "month": month,
                "start_time": start_time,
                "end_time": end_time,
                "shop_names": shop_names,
                "shop_ids": shop_ids,
                "channel_include_keyword": channel_include_keyword,
                "channel_exclude_keywords": channel_exclude_keywords,
                "filter_time_type": filter_time_type,
                "trade_status": trade_status,
                "prefer_udr": prefer_udr,
                "use_udr_fallback": use_udr_fallback,
                "udr_report_id": str(udr_report_id or ""),
                "row_count": data.get("row_count"),
                "total_goods_qty": data.get("total_goods_qty"),
                "total_goods_amount": data.get("total_goods_amount"),
            },
            steps=[
                {"step": "resolve_channels", "status": "success", "message": f"{len(data.get('resolved_shops') or [])} channels"},
                {"step": "query_sales_report", "status": "success", "message": f"{data.get('row_count')} rows"},
                {"step": "summarize_quantity_amount", "status": "success", "message": f"dimension={dimension}"},
                {"step": "export_file", "status": "success" if output_path else "skipped", "message": data.get("output_path", "")},
            ],
            reuse_hints=[
                "用户要按渠道或渠道+货品看销售数量/金额时，优先走 run_channel_sales_summary_workflow()",
                "底层使用货品销售多维分析报表，避免逐页拉销售单再本地汇总导致慢和不准",
            ],
        )
    )
    return result


def run_delivery_note_export_workflow(
    trade_no: str,
    template_path: str = None,
    output_path: str = None,
    output_dir: str = None,
    config: dict = None,
) -> dict:
    """
    Generate an Excel template delivery note from a sales order.
    """
    export_result = delivery_note.generate_delivery_note_from_trade(
        trade_no=trade_no,
        template_path=template_path,
        output_path=output_path,
        output_dir=output_dir,
        config=config,
    )
    result = {
        "status": "completed",
        "workflow": "delivery_note_export",
        "execution_plan": workflow_route_plan("delivery_note_export"),
        "data": export_result,
    }
    append_feedback_log(
        build_workflow_feedback_entry(
            "delivery_note_export",
            "completed",
            "delivery note generated from sales order template",
            next_action=f"模板出库单已生成: {export_result.get('output_path')}",
            input_summary={
                "trade_no": trade_no,
                "template_path": template_path,
                "output_path": output_path,
                "output_dir": output_dir,
            },
            steps=[
                {"step": "query_sales_order", "status": "success", "message": "queried oms.trade.fullinfoget with goodsDetail fields"},
                {"step": "fill_template", "status": "success", "message": f"{export_result.get('goods_count')} goods lines"},
                {"step": "save_file", "status": "success", "message": export_result.get("output_path", "")},
            ],
            pain_points=[
                "销售单查询必须包含 goodsDetail.* 字段，否则模板没有货品明细",
                "Excel 合并单元格只能写入合并区域左上角",
                "展示单元格和文件名数据必须分离，避免文件名被模板文字污染",
            ],
            reuse_hints=[
                "同类仓库模板单据生成优先复用 run_delivery_note_export_workflow()",
                "不同仓库模板用 config 调整单号单元格、明细起止行、列映射和留空列",
            ],
        )
    )
    return result


def run_warehouse_keyword_batch_stock_export_workflow(
    output_path: str,
    include_keyword: str,
    exclude_keywords: list[str] = None,
    fill_missing_sales_zero: bool = True,
    include_sales: bool = True,
    active_only: bool = False,
    use_chinese_headers: bool = True,
) -> dict:
    """
    Export a batch-stock report for warehouses matched by user-provided keyword rules.
    """
    export_result = inventory.export_warehouse_keyword_batch_stock_report(
        output_path=output_path,
        include_keyword=include_keyword,
        exclude_keywords=exclude_keywords,
        fill_missing_sales_zero=fill_missing_sales_zero,
        include_sales=include_sales,
        active_only=active_only,
        use_chinese_headers=use_chinese_headers,
    )
    result = {
        "status": "completed",
        "workflow": "warehouse_keyword_batch_stock_export",
        "execution_plan": workflow_route_plan("warehouse_keyword_batch_stock_export"),
        "data": export_result,
    }
    append_feedback_log(
        build_workflow_feedback_entry(
            "warehouse_keyword_batch_stock_export",
            "completed",
            "warehouse keyword batch stock report exported",
            next_action=f"仓库关键词批次库存报表已生成: {export_result.get('output_path')}",
            input_summary={
                "include_keyword": include_keyword,
                "exclude_keywords": exclude_keywords or [f"除{include_keyword}"],
                "fill_missing_sales_zero": fill_missing_sales_zero,
                "include_sales": include_sales,
            },
            steps=[
                {"step": "search_warehouses_by_keyword", "status": "success", "message": f"{export_result.get('warehouse_count')} warehouses"},
                {"step": "query_batch_stock_by_warehouse", "status": "success", "message": f"{export_result.get('row_count')} rows"},
                {"step": "fill_sales", "status": "success" if include_sales else "skipped", "message": "threedayQuantity or configured blank/zero fallback"},
                {"step": "export_file", "status": "success", "message": export_result.get("output_path", "")},
            ],
            pain_points=export_result.get("pain_points", []),
            reuse_hints=[
                "下次导出同类仓库批次库存直接走 run_warehouse_keyword_batch_stock_export_workflow()",
                "销量字段为空时，必须按用户确认的业务口径填 0 或留空",
            ],
        )
    )
    return result


def run_distribution_group_batch_stock_export_workflow(
    output_path: str,
    include_keyword: str = "分销组",
    exclude_keywords: list[str] = None,
    fill_missing_sales_zero: bool = True,
    include_sales: bool = True,
    active_only: bool = False,
    use_chinese_headers: bool = True,
) -> dict:
    """
    Compatibility wrapper for the learned distribution-group example.
    Prefer run_warehouse_keyword_batch_stock_export_workflow() for new needs.
    """
    result = run_warehouse_keyword_batch_stock_export_workflow(
        output_path=output_path,
        include_keyword=include_keyword,
        exclude_keywords=exclude_keywords,
        fill_missing_sales_zero=fill_missing_sales_zero,
        include_sales=include_sales,
        active_only=active_only,
        use_chinese_headers=use_chinese_headers,
    )
    result["workflow_alias"] = "distribution_group_batch_stock_export"
    return result


WORKFLOW_CATALOG = {
    "sales_order_create": {
        "function": "run_sales_order_workflow",
        "description": "新建普通/寄样/补发销售单，含预检、批次、反查展示",
    },
    "transfer_create": {
        "function": "run_transfer_workflow",
        "description": "新建调拨单，自动补申请人、货品、仓库、联系人和批次",
    },
    "stock_apply_create": {
        "function": "run_stock_apply_workflow",
        "description": "新建入库/出库申请单，申请人必填，出库批次可自动 FIFO",
    },
    "channel_sales_summary": {
        "function": "run_channel_sales_summary_workflow",
        "description": "按渠道或渠道+货品汇总销售数量和金额",
    },
    "goods_sales_analysis": {
        "function": "run_goods_sales_analysis_workflow",
        "description": "货品销售多维分析报表，全字段导出",
    },
    "inventory_export": {
        "function": "run_inventory_export_workflow",
        "description": "导出库存，可附带批次明细",
    },
}


def get_workflow_catalog() -> dict:
    """
    Return stable workflow entry points for other agents.

    OpenClaw / Work Buddy 类产品应优先选择这里的 action，再调用
    run_fast_workflow()，避免每次重新编写临时脚本和接口签名逻辑。
    """
    return dict(WORKFLOW_CATALOG)


def run_fast_workflow(action: str, **kwargs) -> dict:
    """
    Thin dispatcher for high-frequency workflows.
    """
    if action == "sales_order_create":
        return run_sales_order_workflow(**kwargs)
    if action == "transfer_create":
        return run_transfer_workflow(**kwargs)
    if action == "stock_apply_create":
        return run_stock_apply_workflow(**kwargs)
    if action == "channel_sales_summary":
        return run_channel_sales_summary_workflow(**kwargs)
    if action == "goods_sales_analysis":
        return run_goods_sales_analysis_workflow(**kwargs)
    if action == "inventory_export":
        return run_inventory_export_workflow(**kwargs)
    raise JackyunValidationError(f"不支持的快速工作流 action: {action}")


def run_misc_workflow(workflow_type: str, **kwargs) -> dict:
    """
    Lightweight high-frequency workflow router for other common modules.
    """
    if workflow_type == "combined_create":
        data = combined.create_combined(kwargs["combined_data"], use_v2=kwargs.get("use_v2", True))
    elif workflow_type == "refund_create":
        data = aftersales.create_refund(kwargs["refund_data"])
    elif workflow_type == "returnchange_create":
        data = aftersales.create_returnchange(kwargs["returnchange_data"])
    else:
        raise JackyunValidationError(f"不支持的高频工作流类型: {workflow_type}")

    result = {
        "status": "completed",
        "workflow": workflow_type,
        "execution_plan": workflow_route_plan(workflow_type),
        "data": data,
    }
    append_feedback_log(
        build_workflow_feedback_entry(
            workflow_type,
            "completed",
            "misc workflow completed",
            input_summary={"workflow_type": workflow_type},
            steps=[{"step": workflow_type, "status": "success", "message": "misc workflow completed"}],
            reuse_hints=["下次可直接复用相同高频工作流入口"],
        )
    )
    return result
