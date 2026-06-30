from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.a2a_ecommerce_demo.state_io import atomic_write_json, load_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR") or PROJECT_ROOT / "data").resolve()
WAREHOUSE_DIR = Path(os.getenv("A2A_WAREHOUSE_DIR") or DATA_DIR / "warehouse").resolve()
CONNECTOR_REGISTRY_PATH = Path(
    os.getenv("A2A_CONNECTOR_REGISTRY") or WAREHOUSE_DIR / "connector_registry.json"
).resolve()
CONNECTOR_STAGING_DIR = Path(
    os.getenv("A2A_CONNECTOR_STAGING_DIR") or DATA_DIR / "staging" / "connectors"
).resolve()

DOMESTIC_PLATFORMS = ["天猫", "淘宝", "抖音", "拼多多", "唯品会", "京东", "快手", "小红书", "得物"]
READ_ONLY_CONNECTOR_ACTIONS = ["health", "capability_preview", "live_readonly_query", "sync_readonly_snapshot"]
PROJECT_JACKYUN_SKILL_DIR = PROJECT_ROOT / "skills" / "jackyun_erp_readonly_connector_skill"
PROJECT_KINGDEE_SKILL_DIR = PROJECT_ROOT / "skills" / "kingdee_erp_readonly_connector_skill"
CONNECTOR_ID_ALIASES = {
    "jackyun": "jackyun_erp",
    "jackyunerp": "jackyun_erp",
    "jackyun_erp": "jackyun_erp",
    "jikeyun": "jackyun_erp",
    "jikeyunerp": "jackyun_erp",
    "吉客云": "jackyun_erp",
    "吉客云erp": "jackyun_erp",
    "kingdee": "kingdee_erp",
    "kingdeeerp": "kingdee_erp",
    "kingdee_erp": "kingdee_erp",
    "金蝶": "kingdee_erp",
    "金蝶erp": "kingdee_erp",
    "wecom": "wecom_smartsheet",
    "wecomsmartsheet": "wecom_smartsheet",
    "wecom_smartsheet": "wecom_smartsheet",
    "wework": "wecom_smartsheet",
    "weworksmartsheet": "wecom_smartsheet",
    "企业微信智能表": "wecom_smartsheet",
    "企微智能表": "wecom_smartsheet",
}
WECOM_CHANNEL_DAILY_SALES_COLUMNS = [
    "record_id",
    "年月",
    "范围",
    "月目标（万）",
    "渠道编码",
    *[f"{day}日" for day in range(1, 32)],
    "月最后一天",
    "_source_docid",
    "_source_sheet_id",
]


def _read_only_permission_policy(system: str) -> dict[str, Any]:
    return {
        "schema": "a2a_erp_connector_permission_v1",
        "scope": "read_only",
        "system": system,
        "can_call_external_read_api": True,
        "can_call_external_write_api": False,
        "can_create_or_update_business_doc": False,
        "can_delete_or_cancel_business_doc": False,
        "can_register_local_snapshot": True,
        "local_snapshot_requires_confirmation": True,
        "notes": [
            "外部系统账号建议在源系统后台也配置为只读角色。",
            "应用层只暴露只读查询白名单；外部写入方法不允许直接调用。",
            "sync_readonly_snapshot 只写本地 staging/DuckDB，不写回源系统。",
        ],
    }

P3_NOT_DIRECT_API_SOURCES = [
    {
        "source_id": "domestic_marketplace_api",
        "label": "国内平台销售/商品/退款/评价官方 API",
        "status": "not_direct_api",
        "reason": "平台权限、店铺授权和接口开放限制较多，当前不承诺直接 API 接入。",
        "fallback": "平台后台导出 Excel/CSV 后进入 raw -> cleaning -> DuckDB/wiki/LightRAG。",
    },
    {
        "source_id": "domestic_ads_api",
        "label": "国内广告报表官方 API",
        "status": "not_direct_api",
        "reason": "阿里妈妈、巨量千川、京准通、多多推广等接口权限和稳定授权暂不可控。",
        "fallback": "广告后台导出报表后进入 fact_ads_daily / wiki 复盘；只做本地分析，不直接改预算。",
    },
    {
        "source_id": "customer_service_review_api",
        "label": "客服会话、售后工单、评价、问大家和退款原因官方 API",
        "status": "not_direct_api",
        "reason": "客服/评价/售后数据通常受平台权限、隐私和接口开放限制影响，当前不做直连 API。",
        "fallback": "客服/售后/评价导出文件或人工整理 Markdown 入库，用于商品内容和产品改进分析。",
    },
]

P3_MANUAL_EXPORT_SOURCES = [
    {
        "source_id": "domestic_marketplace_exports",
        "label": "国内平台经营后台导出",
        "datasets": ["销售明细", "商品表现", "退款明细", "评价导出"],
        "ingestion_route": "raw 文件夹 -> Excel 清洗 -> DuckDB fact layer -> wiki/LightRAG 摘要",
    },
    {
        "source_id": "ads_report_exports",
        "label": "广告后台导出报表",
        "datasets": ["投产比", "费比", "GMV", "转化率", "UV 价值", "预算", "竞价"],
        "ingestion_route": "raw 文件夹 -> fact_ads_daily -> 广告复盘 wiki",
    },
    {
        "source_id": "customer_service_after_sales_exports",
        "label": "客服/售后/评价人工导出",
        "datasets": ["客服会话", "售后工单", "评价", "问大家", "退款退货原因", "差评跟进"],
        "ingestion_route": "raw 文件夹或 wiki 手工页 -> 产品/售后/舆情知识页",
    },
]


def _p3_ingestion_policy() -> dict[str, Any]:
    return {
        "schema": "a2a_p3_ingestion_policy_v1",
        "principle": "ERP-first；平台、广告、客服售后数据优先走后台导出和本地入库，不承诺直接 API。",
        "not_direct_api_sources": P3_NOT_DIRECT_API_SOURCES,
        "manual_export_sources": P3_MANUAL_EXPORT_SOURCES,
    }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_connector_id(connector_id: str) -> str:
    value = str(connector_id or "").strip()
    if not value:
        return ""
    normalized = value.casefold()
    compact = normalized.replace(" ", "").replace("-", "").replace("_", "")
    return CONNECTOR_ID_ALIASES.get(normalized) or CONNECTOR_ID_ALIASES.get(compact) or value


def _safe_path_slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("._-")
    return slug[:80] or fallback


def _path_is_under(path: Path, root: Path) -> bool:
    relative = os.path.relpath(path, root)
    return relative == "." or (not relative.startswith(f"..{os.sep}") and relative != "..")


def _default_skill_dir(env_name: str, fallback: str) -> str:
    return str(Path(os.getenv(env_name, fallback)).expanduser())


def _default_connector_specs() -> dict[str, dict[str, Any]]:
    return {
        "jackyun_erp": {
            "connector_id": "jackyun_erp",
            "display_name": "吉客云 ERP",
            "system": "jackyun",
            "kind": "erp",
            "source": "desktop_skill_api",
            "skill_dir_env": "A2A_JACKYUN_SKILL_DIR",
            "skill_dir": _default_skill_dir(
                "A2A_JACKYUN_SKILL_DIR",
                str(PROJECT_JACKYUN_SKILL_DIR),
            ),
            "required_files": ["SKILL.md", "jackyun_api.py", "ARCHITECTURE.md"],
            "credential_env_names": ["JACKYUN_APP_KEY", "JACKYUN_APP_SECRET"],
            "read_only_default": True,
            "write_requires_confirmation": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "permission_policy": _read_only_permission_policy("jackyun"),
            "risk_level": "medium",
            "status": "registered",
            "domestic_platforms": DOMESTIC_PLATFORMS,
            "allowed_actions": READ_ONLY_CONNECTOR_ACTIONS,
            "denied_write_actions": ["创建销售单", "审核销售单", "驳回销售单", "修改仓配", "库存调整", "财务单据写入"],
            "datasets": {
                "inventory_stock": {
                    "label": "库存快照",
                    "description": "吉客云分仓库存、批次库存或 SKU 库存快照。",
                    "columns": ["日期", "SKU", "商品名称", "仓库", "销售渠道", "期初总量", "入库总量", "出库总量", "期末总量", "在途"],
                    "mart_candidates": ["fact_inventory_daily", "fact_inbound_outbound", "inventory_current"],
                },
                "batch_inventory": {
                    "label": "批次库存",
                    "description": "吉客云批次库存、生产日期、效期和分仓可用数量。",
                    "columns": ["日期", "SKU", "商品名称", "仓库", "批次号", "生产日期", "有效期", "库存数量", "可用数量"],
                    "mart_candidates": ["fact_inventory_daily", "fact_inbound_outbound", "inventory_current"],
                },
                "sales_orders": {
                    "label": "销售订单",
                    "description": "销售订单明细或按日汇总后的 SKU 销售数据。",
                    "columns": ["日期", "订单号", "SKU", "商品名称", "仓库", "销售渠道", "销量", "销售额"],
                    "mart_candidates": ["fact_sales_daily", "agg_sku_daily_sales", "agg_channel_sales"],
                },
                "sales_report": {
                    "label": "货品销售分析",
                    "description": "吉客云货品销售多维分析或渠道销售汇总。",
                    "columns": ["日期", "SKU", "商品名称", "销售渠道", "销量", "销售额"],
                    "mart_candidates": ["fact_sales_daily", "agg_channel_sales"],
                },
                "purchase_orders": {
                    "label": "采购订单",
                    "description": "吉客云采购订单只读明细，用于供应商、采购价、到货状态和入库进度分析。",
                    "columns": ["日期", "采购单号", "供应商", "SKU", "商品名称", "数量", "采购单价", "到货状态", "申请入库数量", "实际入库数量"],
                    "mart_candidates": ["fact_finance_daily", "fact_inbound_outbound", "dim_product_master"],
                    "coverage": {
                        "purchase_price": "available_from_purchase_or_inbound_docs",
                        "lead_time": "available_when_arrive_period_or_plan_in_date_exists",
                        "historical_delay": "requires_purchase_vs_receipt_join",
                    },
                },
                "stock_inbound": {
                    "label": "入库明细",
                    "description": "吉客云入库单/入库申请只读明细。",
                    "columns": ["日期", "入库单号", "SKU", "商品名称", "仓库", "入库类型", "数量", "批次号"],
                    "mart_candidates": ["fact_inbound_outbound"],
                },
                "stock_outbound": {
                    "label": "出库明细",
                    "description": "吉客云出库单/出库申请只读明细。",
                    "columns": ["日期", "出库单号", "SKU", "商品名称", "仓库", "出库类型", "数量", "批次号"],
                    "mart_candidates": ["fact_inbound_outbound"],
                },
                "suppliers": {
                    "label": "供应商基础资料",
                    "description": "吉客云供应商基础资料。交期、延误需要看是否有自定义字段或与采购/入库数据关联。",
                    "columns": ["供应商编码", "供应商名称", "状态", "联系人", "更新时间"],
                    "mart_candidates": ["dim_product_master"],
                    "coverage": {
                        "purchase_price": "not_in_vendor_master",
                        "lead_time": "custom_field_or_manual_export_required",
                        "historical_delay": "requires_purchase_vs_receipt_join",
                    },
                },
                "master_data": {
                    "label": "基础资料",
                    "description": "渠道、仓库、货品、供应商等基础资料快照。",
                    "columns": ["编码", "名称", "类型", "状态", "更新时间"],
                    "mart_candidates": ["dim_product_master", "dim_channel"],
                },
            },
        },
        "kingdee_erp": {
            "connector_id": "kingdee_erp",
            "display_name": "金蝶云星空",
            "system": "kingdee",
            "kind": "erp",
            "source": "desktop_skill_api",
            "skill_dir_env": "A2A_KINGDEE_SKILL_DIR",
            "skill_dir": _default_skill_dir(
                "A2A_KINGDEE_SKILL_DIR",
                str(PROJECT_KINGDEE_SKILL_DIR),
            ),
            "required_files": ["SKILL.md", "auth.py", "api.py"],
            "credential_env_names": ["KINGDEE_BASE_URL", "KINGDEE_USERNAME", "KINGDEE_PASSWORD"],
            "read_only_default": True,
            "write_requires_confirmation": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "permission_policy": _read_only_permission_policy("kingdee"),
            "risk_level": "high",
            "status": "registered",
            "domestic_platforms": DOMESTIC_PLATFORMS,
            "allowed_actions": READ_ONLY_CONNECTOR_ACTIONS,
            "denied_write_actions": ["Save 保存单据", "Submit 提交单据", "Push 下推单据", "批量提交", "修改应收/付款/备注"],
            "datasets": {
                "finance_snapshot": {
                    "label": "财务快照",
                    "description": "应收、应付、收款、费用、毛利或现金相关快照。",
                    "columns": ["日期", "SKU", "商品名称", "销售渠道", "收入", "成本", "毛利", "现金"],
                    "mart_candidates": ["fact_finance_daily"],
                },
                "purchase_orders": {
                    "label": "采购订单",
                    "description": "采购订单列表和供应商物料明细。",
                    "columns": ["日期", "单据编号", "供应商", "SKU", "商品名称", "数量", "采购单价", "金额", "交货日期"],
                    "mart_candidates": ["fact_finance_daily", "dim_product_master"],
                },
                "supplier_procurement_terms": {
                    "label": "供应商采购条款观察",
                    "description": "从金蝶采购订单分录只读提取供应商、物料、数量、采购单价和交货日期；历史延误需要入库匹配。",
                    "columns": ["日期", "单据编号", "供应商", "SKU", "商品名称", "数量", "采购单价", "交货日期", "延误状态"],
                    "mart_candidates": ["fact_finance_daily", "dim_product_master"],
                    "coverage": {
                        "purchase_price": "available_from_PUR_PurchaseOrder_entry",
                        "lead_time": "available_when_delivery_date_field_exists",
                        "historical_delay": "requires_purchase_vs_receipt_join",
                    },
                },
                "sales_outstock": {
                    "label": "销售出库",
                    "description": "销售出库单列表和明细。",
                    "columns": ["日期", "单据编号", "SKU", "商品名称", "仓库", "销售渠道", "销量", "销售额"],
                    "mart_candidates": ["fact_sales_daily", "fact_inbound_outbound"],
                },
                "sales_returns": {
                    "label": "销售退货",
                    "description": "金蝶销售退货单列表和明细，只读用于退货/应收/成本链路核对。",
                    "columns": ["日期", "单据编号", "客户", "SKU", "商品名称", "数量", "金额", "状态"],
                    "mart_candidates": ["fact_sales_daily", "fact_inbound_outbound"],
                },
                "other_payables": {
                    "label": "其他应付",
                    "description": "金蝶其他应付单只读列表。",
                    "columns": ["日期", "单据编号", "往来单位", "金额", "状态"],
                    "mart_candidates": ["fact_finance_daily"],
                },
                "organizations": {
                    "label": "组织",
                    "description": "金蝶组织基础资料，用于组织/客户映射。",
                    "columns": ["组织编码", "组织名称", "状态"],
                    "mart_candidates": ["dim_product_master"],
                },
                "customers": {
                    "label": "客户",
                    "description": "金蝶客户基础资料，用于组织/客户/店铺映射。",
                    "columns": ["客户编码", "客户名称", "状态"],
                    "mart_candidates": ["dim_channel"],
                },
                "suppliers": {
                    "label": "供应商",
                    "description": "供应商基础资料。",
                    "columns": ["供应商编码", "供应商名称", "状态", "更新时间"],
                    "mart_candidates": ["dim_product_master"],
                },
            },
        },
        "wecom_smartsheet": {
            "connector_id": "wecom_smartsheet",
            "display_name": "企业微信智能表",
            "system": "wecom_smartsheet",
            "kind": "collaboration_table",
            "source": "wecom_wedoc_mcp",
            "skill_dir_env": "",
            "skill_dir": "",
            "required_files": [],
            "credential_env_names": [
                "WECOM_SMARTSHEET_MCP_URL",
                "WEWORK_SMARTSHEET_MCP_URL",
                "WEDOC_MCP_URL",
                "WEWORK_WEDOC_MCP_URL",
                "WECOM_SMARTSHEET_URL",
                "WECOM_SMARTSHEET_DOCID",
                "WECOM_SMARTSHEET_SHEET_ID",
                "WECOM_SMARTSHEET_SHEET_IDS",
            ],
            "credential_alternative_sets": [
                ["WECOM_SMARTSHEET_MCP_URL"],
                ["WEWORK_SMARTSHEET_MCP_URL"],
                ["WEDOC_MCP_URL"],
                ["WEWORK_WEDOC_MCP_URL"],
                ["WECOM_SMARTSHEET_MCP_URL", "WECOM_SMARTSHEET_URL", "WECOM_SMARTSHEET_SHEET_ID"],
                ["WECOM_SMARTSHEET_MCP_URL", "WECOM_SMARTSHEET_URL", "WECOM_SMARTSHEET_SHEET_IDS"],
                ["WECOM_SMARTSHEET_MCP_URL", "WECOM_SMARTSHEET_DOCID", "WECOM_SMARTSHEET_SHEET_ID"],
                ["WECOM_SMARTSHEET_MCP_URL", "WECOM_SMARTSHEET_DOCID", "WECOM_SMARTSHEET_SHEET_IDS"],
            ],
            "read_only_default": True,
            "write_requires_confirmation": True,
            "external_write_enabled": False,
            "permission_scope": "read_only",
            "permission_policy": _read_only_permission_policy("wecom_smartsheet"),
            "risk_level": "medium",
            "status": "registered",
            "domestic_platforms": DOMESTIC_PLATFORMS,
            "allowed_actions": READ_ONLY_CONNECTOR_ACTIONS,
            "denied_write_actions": [
                "智能表新增记录",
                "智能表修改记录",
                "智能表删除记录",
                "webhook 新增/修改",
                "外部链接增删改查写入",
            ],
            "datasets": {
                "smart_records": {
                    "label": "智能表通用记录",
                    "description": "企业微信智能表只读记录，字段按返回值扁平化；适合先作为原始数据源进入 DuckDB/raw view。",
                    "columns": ["record_id", "_source_docid", "_source_sheet_id"],
                    "mart_candidates": [],
                },
                "channel_daily_sales": {
                    "label": "渠道每日销售智能表",
                    "description": "参考桌面脚本里的渠道编码、年月、1-31 日金额宽表；读取后可作为经营日报源表入库。",
                    "columns": WECOM_CHANNEL_DAILY_SALES_COLUMNS,
                    "mart_candidates": ["dim_channel", "fact_sales_daily"],
                },
            },
        },
    }


def _empty_registry() -> dict[str, Any]:
    return {
        "schema": "a2a_connector_registry_v1",
        "updated_at": "",
        "registry_path": str(CONNECTOR_REGISTRY_PATH),
        "connectors": {},
    }


def _remove_unsupported_supplier_terms(datasets: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    unsupported_code = "m" + "oq"
    unsupported_chinese = "起" + "订"
    for dataset, spec in datasets.items():
        if not isinstance(spec, dict):
            cleaned[dataset] = spec
            continue
        item = dict(spec)
        coverage = item.get("coverage")
        if isinstance(coverage, dict):
            item["coverage"] = {key: value for key, value in coverage.items() if str(key).lower() != "moq"}
        columns = item.get("columns")
        if isinstance(columns, list):
            item["columns"] = [
                column
                for column in columns
                if unsupported_code not in str(column).lower() and unsupported_chinese not in str(column)
            ]
        description = item.get("description")
        if isinstance(description, str) and (
            unsupported_code in description.lower() or unsupported_chinese in description
        ):
            uppercase_code = unsupported_code.upper()
            item["description"] = (
                description.replace(f"、{uppercase_code}", "")
                .replace(f"{uppercase_code} 和", "")
                .replace(f"{uppercase_code}、", "")
                .replace(f"最小{unsupported_chinese}量", "")
                .strip()
            )
        cleaned[dataset] = item
    return cleaned


def _project_skill_dir(connector_id: str) -> Path | None:
    if connector_id == "jackyun_erp":
        return PROJECT_JACKYUN_SKILL_DIR
    if connector_id == "kingdee_erp":
        return PROJECT_KINGDEE_SKILL_DIR
    return None


def _normalize_connector_skill_dir(connector_id: str, spec: dict[str, Any]) -> None:
    env_name = str(spec.get("skill_dir_env", "")).strip()
    env_value = os.getenv(env_name, "").strip() if env_name else ""
    if env_value:
        spec["skill_dir"] = str(Path(env_value).expanduser())
        return

    project_dir = _project_skill_dir(connector_id)
    if project_dir is None or not project_dir.exists():
        return

    configured = str(spec.get("skill_dir", "")).strip()
    configured_path = Path(configured).expanduser() if configured else Path()
    stale_markers = (
        "/vendor/desktop-skills/",
        "/Desktop/jackyun-skill-project",
        "/Desktop/Finance",
    )
    should_rebind = not configured or not configured_path.exists() or any(marker in configured for marker in stale_markers)
    if should_rebind:
        spec["skill_dir"] = str(project_dir)


def _normalize_connector_required_files(connector_id: str, spec: dict[str, Any]) -> None:
    files = [str(item) for item in spec.get("required_files", []) if str(item)]
    if connector_id == "jackyun_erp":
        files = [file_name for file_name in files if file_name != "config.py"]
    spec["required_files"] = list(dict.fromkeys(files))


def load_connector_registry() -> dict[str, Any]:
    CONNECTOR_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    registry = load_json(CONNECTOR_REGISTRY_PATH, default=_empty_registry())
    registry.setdefault("schema", "a2a_connector_registry_v1")
    registry.setdefault("registry_path", str(CONNECTOR_REGISTRY_PATH))
    registry.setdefault("connectors", {})
    return registry


def save_connector_registry(registry: dict[str, Any]) -> dict[str, Any]:
    CONNECTOR_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    registry["schema"] = "a2a_connector_registry_v1"
    registry["registry_path"] = str(CONNECTOR_REGISTRY_PATH)
    registry["updated_at"] = _now()
    atomic_write_json(CONNECTOR_REGISTRY_PATH, registry)
    return registry


def ensure_connector_registry() -> dict[str, Any]:
    registry = load_connector_registry()
    connectors = registry.setdefault("connectors", {})
    changed = False
    policy = _p3_ingestion_policy()
    if registry.get("p3_ingestion_policy") != policy:
        registry["p3_ingestion_policy"] = policy
        changed = True
    for connector_id, default_spec in _default_connector_specs().items():
        existing = connectors.get(connector_id, {})
        merged = {**default_spec, **existing}
        merged["datasets"] = _remove_unsupported_supplier_terms(
            {**default_spec.get("datasets", {}), **existing.get("datasets", {})}
        )
        merged["domestic_platforms"] = DOMESTIC_PLATFORMS
        merged["read_only_default"] = True
        merged["write_requires_confirmation"] = True
        merged["external_write_enabled"] = False
        merged["permission_scope"] = "read_only"
        merged["permission_policy"] = _read_only_permission_policy(str(default_spec.get("system", connector_id)))
        merged["allowed_actions"] = list(READ_ONLY_CONNECTOR_ACTIONS)
        denied_actions = [
            *[str(item) for item in default_spec.get("denied_write_actions", [])],
            *[str(item) for item in existing.get("denied_write_actions", [])],
        ]
        merged["denied_write_actions"] = list(dict.fromkeys(denied_actions))
        if connector_id == "kingdee_erp":
            merged["credential_env_names"] = [
                name for name in merged.get("credential_env_names", []) if name != "KINGDEE_ACCT_ID"
            ]
        _normalize_connector_skill_dir(connector_id, merged)
        _normalize_connector_required_files(connector_id, merged)
        if merged != existing:
            connectors[connector_id] = merged
            changed = True
    return save_connector_registry(registry) if changed or not CONNECTOR_REGISTRY_PATH.exists() else registry


def get_connector_spec(connector_id: str) -> dict[str, Any]:
    connector_id = normalize_connector_id(connector_id)
    registry = ensure_connector_registry()
    connector = registry.get("connectors", {}).get(connector_id)
    if not connector:
        raise KeyError(f"Unknown connector_id: {connector_id}")
    return connector


def get_connector_dataset(connector_id: str, dataset: str) -> dict[str, Any]:
    connector_id = normalize_connector_id(connector_id)
    connector = get_connector_spec(connector_id)
    dataset_spec = connector.get("datasets", {}).get(dataset)
    if not dataset_spec:
        raise KeyError(f"Unknown dataset for {connector_id}: {dataset}")
    return dataset_spec


def connector_snapshot_path(connector_id: str, dataset: str, *, timestamp: str = "") -> Path:
    connector_id = normalize_connector_id(connector_id)
    connector_slug = _safe_path_slug(connector_id, "connector")
    dataset_slug = _safe_path_slug(dataset, "dataset")
    safe_timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    root = CONNECTOR_STAGING_DIR.resolve(strict=False)
    path = (root / connector_slug / f"{dataset_slug}_{safe_timestamp}.csv").resolve(strict=False)
    if not _path_is_under(path, root):
        raise PermissionError("connector_snapshot_path_outside_staging")
    return path


def record_connector_sync(
    connector_id: str,
    run: dict[str, Any],
    *,
    status: str = "ready",
) -> dict[str, Any]:
    connector_id = normalize_connector_id(connector_id)
    registry = ensure_connector_registry()
    connector = registry["connectors"][connector_id]
    run = {**run, "completed_at": run.get("completed_at") or _now()}
    connector["status"] = status
    connector["last_sync"] = run
    connector.setdefault("sync_runs", []).append(run)
    connector["sync_runs"] = connector["sync_runs"][-50:]
    return save_connector_registry(registry)
