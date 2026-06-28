from __future__ import annotations

import csv
import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.a2a_ecommerce_demo.state_io import atomic_write_json, load_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("A2A_DATA_DIR", PROJECT_ROOT / "data")).resolve()
CLEANED_DIR = Path(os.getenv("A2A_CLEANED_DIR", DATA_DIR / "cleaned")).resolve()
DERIVED_DIR = Path(os.getenv("A2A_DERIVED_DIR", DATA_DIR / "derived")).resolve()
WAREHOUSE_DIR = Path(os.getenv("A2A_WAREHOUSE_DIR", DATA_DIR / "warehouse")).resolve()
WIKI_DIR = Path(os.getenv("A2A_WIKI_DIR", PROJECT_ROOT / "wiki")).resolve()
DATASET_ROOT = Path(os.getenv("A2A_DATASET_ROOT", WAREHOUSE_DIR / "datasets")).resolve()
DUCKDB_PATH = Path(os.getenv("A2A_DUCKDB_PATH", WAREHOUSE_DIR / "a2a.duckdb")).resolve()
REGISTRY_PATH = Path(os.getenv("A2A_DATASET_REGISTRY", WAREHOUSE_DIR / "dataset_registry.json")).resolve()
SUPPORTED_STRUCTURED_SUFFIXES = {".csv", ".tsv"}
_SKIPPED_DATA_DIRS = {"audit", "backups", "derived", "lightrag", "lightrag_inputs", "lightrag_official", "staging", "tasks", "warehouse", "reports"}

FIELD_GROUP_ALIASES = {
    "sku": ["sku", "msku", "asin", "货品编码", "货品编号", "商品编码", "货品id", "货号", "条码", "seller_sku"],
    "product_name": ["product_name", "商品名称", "产品名称", "货品名称", "name", "title"],
    "date": ["date", "日期", "日期范围", "月份", "账期", "order_date", "发货时间", "建单时间", "货品级发货时间"],
    "warehouse": ["warehouse", "warehouse_code", "仓库", "仓库名称", "仓库code", "发货仓库"],
    "channel": ["channel", "销售渠道", "渠道", "渠道分类", "平台", "店铺", "shop"],
    "brand": ["brand", "品牌", "品牌名称"],
    "opening_inventory": ["期初总量", "期初库存", "opening_inventory", "begin_stock"],
    "inbound": ["入库总量", "入库", "采购入库", "inbound", "入库申请"],
    "outbound": ["出库总量", "出库", "销售发货", "良品销售发货", "outbound", "sales_qty", "出库申请"],
    "ending_inventory": ["期末总量", "期末库存", "库存", "ending_inventory", "stock", "available", "可用库存", "库存数量", "求和项_库存数量", "求和项_可用库存"],
    "in_transit": ["在途", "采购在途", "调拨在途", "in_transit", "on_the_way"],
    "sales_qty": ["sales_qty", "units_sold", "销量", "销售数量", "出库总量", "良品销售发货", "出库", "数量", "近30天销量"],
    "revenue": ["revenue", "sales_amount", "gmv", "销售额", "收入", "营业收入", "销售收入", "分摊后金额"],
    "cost": ["cost", "cogs", "成本", "采购成本", "采购单价", "货品成本", "主营业务成本", "单件成本"],
    "gross_profit": ["gross_profit", "profit", "毛利", "利润", "gross_margin_profit"],
    "cash": ["cash", "cash_balance", "现金", "现金余额", "可用资金", "账户余额"],
    "ad_spend": ["ad_spend", "spend", "广告花费", "广告支出", "推广费"],
    "acos": ["acos", "acos_7d", "广告销售成本比"],
    "roas": ["roas", "roas_7d", "广告投入产出比"],
    "supplier": ["supplier", "供应商", "工厂", "vendor"],
}

QUERY_RECIPE_TEMPLATES = {
    "fact_inventory_daily": [
        {
            "title": "当前库存快照",
            "sql": "SELECT sku, product_name, warehouse, ending_inventory, in_transit, effective_date_value FROM marts.current_inventory_snapshot ORDER BY CASE WHEN COALESCE(ending_inventory, 0) <> 0 THEN 0 ELSE 1 END, ABS(COALESCE(ending_inventory, 0)) DESC, sku LIMIT 50;",
        },
        {
            "title": "最近 30 天某 SKU 库存变化",
            "sql": "SELECT effective_date_value, warehouse, opening_inventory, inbound, outbound, ending_inventory FROM marts.fact_inventory_daily WHERE sku = '<SKU>' AND effective_date_value >= current_date - INTERVAL 30 DAY ORDER BY effective_date_value, warehouse;",
        },
        {
            "title": "断货候选",
            "sql": "SELECT sku, product_name, warehouse, ending_inventory, outbound, effective_date_value FROM marts.current_inventory_snapshot WHERE COALESCE(ending_inventory, 0) <= 0 ORDER BY effective_date_value DESC NULLS LAST, sku LIMIT 100;",
        },
    ],
    "fact_sales_daily": [
        {
            "title": "最近 30 天销量趋势",
            "sql": "SELECT effective_date_value, sku, SUM(sales_qty) AS sales_qty, SUM(revenue) AS revenue FROM marts.fact_sales_daily WHERE effective_date_value >= current_date - INTERVAL 30 DAY GROUP BY 1, 2 ORDER BY 1, 2 LIMIT 200;",
        },
        {
            "title": "渠道或仓库销量汇总",
            "sql": "SELECT warehouse, sku, SUM(sales_qty) AS sales_qty, SUM(revenue) AS revenue FROM marts.fact_sales_daily GROUP BY 1, 2 ORDER BY sales_qty DESC NULLS LAST LIMIT 100;",
        },
    ],
    "fact_inbound_outbound": [
        {
            "title": "入出库平衡检查",
            "sql": "SELECT effective_date_value, sku, warehouse, inbound, outbound, ending_inventory FROM marts.fact_inbound_outbound ORDER BY effective_date_value DESC NULLS LAST LIMIT 100;",
        }
    ],
    "fact_finance_daily": [
        {
            "title": "财务日汇总",
            "sql": "SELECT effective_date_value, sku, SUM(revenue) AS revenue, SUM(cost) AS cost, SUM(gross_profit) AS gross_profit, SUM(cash) AS cash FROM marts.fact_finance_daily GROUP BY 1, 2 ORDER BY 1 DESC NULLS LAST, 2 LIMIT 200;",
        },
        {
            "title": "近 30 天利润走势",
            "sql": "SELECT effective_date_value, SUM(revenue) AS revenue, SUM(cost) AS cost, SUM(gross_profit) AS gross_profit FROM marts.fact_finance_daily WHERE effective_date_value >= current_date - INTERVAL 30 DAY GROUP BY 1 ORDER BY 1;",
        },
    ],
    "fact_ads_daily": [
        {
            "title": "广告日汇总",
            "sql": "SELECT effective_date_value, sku, channel, SUM(ad_spend) AS ad_spend, AVG(acos) AS acos, AVG(roas) AS roas FROM marts.fact_ads_daily GROUP BY 1, 2, 3 ORDER BY 1 DESC NULLS LAST, ad_spend DESC NULLS LAST LIMIT 200;",
        }
    ],
    "dim_product_master": [
        {
            "title": "产品主数据",
            "sql": "SELECT dataset_slug, sku, brand, product_name, category, product_type, purchase_unit_cost FROM marts.dim_product_master ORDER BY sku LIMIT 100;",
        }
    ],
    "dim_channel": [
        {
            "title": "渠道主数据",
            "sql": "SELECT dataset_slug, sales_channel, warehouse, channel_category, department_category, order_category, region FROM marts.dim_channel ORDER BY sales_channel LIMIT 100;",
        }
    ],
    "inventory_current": [
        {
            "title": "当前库存语义快照",
            "sql": "SELECT dataset_slug, snapshot_date, sku, product_name, warehouse, current_inventory, inventory_value_estimate FROM marts.inventory_current ORDER BY current_inventory DESC NULLS LAST LIMIT 100;",
        }
    ],
}


def _ensure_dirs() -> None:
    DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    (WIKI_DIR / "datasets").mkdir(parents=True, exist_ok=True)


def _safe_under(path: Path, roots: list[Path]) -> Path:
    resolved = path.resolve()
    if not any(root in [resolved, *resolved.parents] for root in roots):
        raise ValueError(f"Refusing to access outside allowed directories: {resolved}")
    return resolved


def _relative(path: Path) -> str:
    for root_name, root in [("wiki", WIKI_DIR), ("warehouse", WAREHOUSE_DIR), ("data", DATA_DIR)]:
        try:
            return f"{root_name}/{path.relative_to(root).as_posix()}"
        except ValueError:
            continue
    return path.as_posix()


def _slugify(value: str, fallback: str = "dataset") -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "_", value).strip("_")
    return slug[:90] or fallback


def _load_json(path: Path) -> dict[str, Any]:
    return load_json(path)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_json(path, data)


def _validate_safe_fact_sql(sql: str) -> None:
    normalized = sql.lstrip().lower()
    if not normalized.startswith("select") and not normalized.startswith("with"):
        raise ValueError("Only SELECT/CTE queries are allowed in query_fact_layer.")
    if ";" in normalized or "--" in normalized or "/*" in normalized or "*/" in normalized:
        raise ValueError("SQL contains a statement separator or comment that is not allowed in query_fact_layer.")
    forbidden_patterns = [
        "read_csv",
        "read_csv_auto",
        "read_parquet",
        "read_json",
        "read_text",
        "httpfs",
        "copy ",
        "attach ",
        "install ",
        "load ",
        "pragma ",
        "from_file",
        "glob(",
    ]
    if any(pattern in normalized for pattern in forbidden_patterns):
        raise ValueError("SQL contains a function or statement that is not allowed in query_fact_layer.")
    if re.search(r"\b(from|join)\s+(['\"])[^'\"]*[/\\][^'\"]*\2", sql, re.IGNORECASE):
        raise ValueError("SQL file path reads are not allowed in query_fact_layer.")
    cte_names = {
        match.group(1).strip('"').lower()
        for match in re.finditer(r"(?:\bwith|,)\s+(\"[^\"]+\"|[A-Za-z_][\w]*)\s+as\s*\(", sql, re.IGNORECASE)
    }
    table_refs = re.finditer(
        r"\b(?:from|join)\s+((?:(?:\"[^\"]+\"|[A-Za-z_][\w]*)\s*\.\s*)?(?:\"[^\"]+\"|[A-Za-z_][\w]*))",
        sql,
        re.IGNORECASE,
    )
    for match in table_refs:
        reference = match.group(1)
        if reference.lstrip().startswith("("):
            continue
        parts = [part.strip().strip('"').lower() for part in reference.split(".")]
        if len(parts) == 1 and parts[0] in cte_names:
            continue
        if len(parts) < 2 or parts[0] not in {"datasets", "marts"}:
            raise ValueError("Only datasets.* and marts.* fact-layer objects are allowed in query_fact_layer.")


def _write_markdown(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join([f"# {title}", "", *lines]).rstrip() + "\n"
    path.write_text(body, encoding="utf-8")


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def duckdb_installed() -> bool:
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return False
    return True


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB fact layer requires duckdb. Run pip install -r requirements.txt.") from exc
    return duckdb


def _connect(read_only: bool = False):
    duckdb = _require_duckdb()
    _ensure_dirs()
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            connection = duckdb.connect(str(DUCKDB_PATH), read_only=read_only)
            break
        except Exception as exc:
            last_error = exc
            if read_only or attempt == 4:
                raise
            time.sleep(0.5)
    else:
        assert last_error is not None
        raise last_error
    if not read_only:
        connection.execute("CREATE SCHEMA IF NOT EXISTS datasets;")
        connection.execute("CREATE SCHEMA IF NOT EXISTS marts;")
    return connection


def _load_registry() -> dict[str, Any]:
    _ensure_dirs()
    if not REGISTRY_PATH.exists():
        return {"schema": "a2a_dataset_registry_v1", "updated_at": "", "datasets": {}}
    return _load_json(REGISTRY_PATH)


def _save_registry(registry: dict[str, Any]) -> None:
    registry["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_json(REGISTRY_PATH, registry)


def _find_field(headers: list[str], group: str) -> str:
    aliases = [alias.lower() for alias in FIELD_GROUP_ALIASES.get(group, [])]
    lowered_headers = [(header, header.lower()) for header in headers]
    for alias in aliases:
        for header, lowered in lowered_headers:
            if alias == lowered:
                return header
    for alias in sorted(aliases, key=len, reverse=True):
        for header, lowered in lowered_headers:
            if alias in lowered:
                return header
    return ""


def _semantic_type(field: str) -> str:
    lowered = field.lower()
    if any(token in lowered for token in ["sku", "asin", "msku", "code", "id", "编码", "条码", "货号"]):
        return "identifier_text"
    if any(token in lowered for token in ["date", "日期", "月份", "账期", "时间"]):
        return "date"
    if any(token in lowered for token in ["库存", "期末", "期初", "入库", "出库", "销量", "数量", "在途"]):
        return "quantity"
    if any(token in lowered for token in ["金额", "收入", "成本", "利润", "售价", "价格"]):
        return "money"
    return "text"


def _business_meaning(sheet_name: str, headers: list[str]) -> str:
    matched = {group for group in FIELD_GROUP_ALIASES if _find_field(headers, group)}
    if {"opening_inventory", "inbound", "outbound", "ending_inventory"} & matched:
        return "Inventory ledger or stock balance sheet."
    if {"sales_qty", "revenue"} & matched:
        return "Sales fact sheet."
    if {"sku", "product_name"} <= matched:
        return "Product or SKU master sheet."
    if "warehouse" in matched:
        return "Warehouse or fulfillment sheet."
    return f"Needs manual labeling; inferred from sheet name `{sheet_name}`."


def _candidate_keys(headers: list[str]) -> list[str]:
    groups = {
        "sku": _find_field(headers, "sku"),
        "date": _find_field(headers, "date"),
        "warehouse": _find_field(headers, "warehouse"),
        "product_name": _find_field(headers, "product_name"),
    }
    candidates = []
    if groups["sku"] and groups["date"] and groups["warehouse"]:
        candidates.append(f"{groups['sku']} + {groups['date']} + {groups['warehouse']}")
    if groups["sku"] and groups["date"]:
        candidates.append(f"{groups['sku']} + {groups['date']}")
    if groups["sku"]:
        candidates.append(groups["sku"])
    if groups["product_name"] and groups["warehouse"]:
        candidates.append(f"{groups['product_name']} + {groups['warehouse']}")
    return candidates or ["Needs manual confirmation."]


def _text_expr(field_name: str) -> str:
    if not field_name:
        return "NULL::VARCHAR"
    quoted = _quote_ident(field_name)
    return f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '')"


def _double_expr(field_name: str) -> str:
    if not field_name:
        return "NULL::DOUBLE"
    quoted = _quote_ident(field_name)
    text_expr = f"NULLIF(REPLACE(REPLACE(TRIM(CAST({quoted} AS VARCHAR)), ',', ''), '%', ''), '')"
    return f"TRY_CAST({text_expr} AS DOUBLE)"


def _date_text_expr(field_name: str) -> str:
    return _text_expr(field_name) if field_name else "NULL::VARCHAR"


def _date_value_expr(field_name: str) -> str:
    text_expr = _date_text_expr(field_name)
    if text_expr == "NULL::VARCHAR":
        return "NULL::DATE"
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y.%m.%d",
        "%Y.%m.%d %H:%M:%S",
        "%Y%m%d",
        "%Y-%m",
        "%Y/%m",
        "%Y.%m",
        "%Y%m",
        "%Y年%m月%d日",
        "%Y年%m月",
    ]
    attempts = [f"TRY_CAST({text_expr} AS DATE)"]
    attempts.extend(f"CAST(TRY_STRPTIME({text_expr}, '{fmt}') AS DATE)" for fmt in formats)
    return "COALESCE(" + ", ".join(attempts) + ")"


def _infer_snapshot_date(sheet_name: str, source_path: Path) -> str | None:
    haystack = f"{sheet_name} {source_path.stem}"
    explicit = re.search(r"(20\d{2})[._/-](\d{1,2})[._/-](\d{1,2})", haystack)
    if explicit:
        year, month, day = (int(explicit.group(index)) for index in range(1, 4))
        return f"{year:04d}-{month:02d}-{day:02d}"
    compact = re.search(r"(20\d{2})(\d{2})(\d{2})", haystack)
    if compact:
        year, month, day = (int(compact.group(index)) for index in range(1, 4))
        return f"{year:04d}-{month:02d}-{day:02d}"
    month_day = re.search(r"(?<!\d)(\d{1,2})[._/-](\d{1,2})(?!\d)", sheet_name)
    if month_day:
        year = datetime.fromtimestamp(source_path.stat().st_mtime).year if source_path.exists() else datetime.now().year
        month = int(month_day.group(1))
        day = int(month_day.group(2))
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _snapshot_date_expr(snapshot_date: str | None) -> str:
    if not snapshot_date:
        return "NULL::DATE"
    return f"CAST({_sql_literal(snapshot_date)} AS DATE)"


def _effective_month_expr(date_field: str, snapshot_date_sql: str) -> str:
    effective_date = f"COALESCE({_date_value_expr(date_field)}, {snapshot_date_sql})"
    return f"CAST(DATE_TRUNC('month', {effective_date}) AS DATE)"


def _warehouse_partition_expr(warehouse_field: str) -> str:
    return f"COALESCE({_text_expr(warehouse_field)}, 'unknown')"


def _sku_hash_expr(sku_field: str) -> str:
    return f"LOWER(MD5(COALESCE({_text_expr(sku_field)}, 'unknown')))"


def _sku_hash_bucket_expr(sku_field: str) -> str:
    return f"SUBSTR({_sku_hash_expr(sku_field)}, 1, 2)"


def _valid_business_row_condition(sku_field: str, product_name_field: str) -> str:
    sku_expr = _text_expr(sku_field)
    product_expr = _text_expr(product_name_field)
    invalid_tokens = ["(全部)", "(多项)", "全部", "多项"]
    invalid_checks = [f"{sku_expr} <> {_sql_literal(token)}" for token in invalid_tokens]
    invalid_checks.extend(f"{product_expr} <> {_sql_literal(token)}" for token in invalid_tokens)
    return " AND ".join(
        [
            f"COALESCE({sku_expr}, {product_expr}) IS NOT NULL",
            *invalid_checks,
        ]
    )


def _headers_from_structured_file(path: Path) -> list[str]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter=delimiter)
        try:
            first_row = next(reader)
        except StopIteration:
            return []
    return [str(item).strip() for item in first_row if str(item).strip()]


def _iter_standard_structured_files(limit: int = 200) -> list[Path]:
    candidates = []
    for path in sorted(DATA_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_STRUCTURED_SUFFIXES:
            continue
        try:
            relative_parts = path.relative_to(DATA_DIR).parts
        except ValueError:
            continue
        if relative_parts and relative_parts[0].lower() in _SKIPPED_DATA_DIRS:
            continue
        candidates.append(_safe_under(path, [DATA_DIR]))
        if len(candidates) >= limit:
            break
    return candidates


def _mart_candidates_from_headers(headers: list[str]) -> list[str]:
    candidates: list[str] = []
    if _find_field(headers, "sku") and (
        _find_field(headers, "opening_inventory")
        or _find_field(headers, "inbound")
        or _find_field(headers, "outbound")
        or _find_field(headers, "ending_inventory")
    ):
        candidates.append("fact_inventory_daily")
    if _find_field(headers, "sku") and (_find_field(headers, "sales_qty") or _find_field(headers, "revenue")):
        candidates.append("fact_sales_daily")
    if _find_field(headers, "date") and (
        _find_field(headers, "cost") or _find_field(headers, "gross_profit") or _find_field(headers, "cash")
    ):
        candidates.append("fact_finance_daily")
    if _find_field(headers, "date") and (
        _find_field(headers, "ad_spend") or _find_field(headers, "acos") or _find_field(headers, "roas")
    ):
        candidates.append("fact_ads_daily")
    return candidates


def _build_parquet_for_single_file(conn, source_path: Path, parquet_path: Path) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    if parquet_path.exists():
        parquet_path.unlink()
    delimiter = "\\t" if source_path.suffix.lower() == ".tsv" else ","
    conn.execute(
        f"""
        COPY (
            SELECT *
            FROM read_csv_auto(
                {_sql_literal(source_path.as_posix())},
                delim = {_sql_literal(delimiter)},
                header = true,
                all_varchar = true,
                sample_size = -1
            )
        )
        TO {_sql_literal(parquet_path.as_posix())}
        (FORMAT PARQUET, COMPRESSION ZSTD);
        """
    )


def _sheet_chunk_paths(manifest: dict[str, Any], sheet_name: str) -> tuple[list[Path], list[str], int]:
    chunk_paths = []
    missing_paths: list[str] = []
    available_rows = 0
    for chunk in manifest.get("chunks", []):
        if chunk.get("sheet") != sheet_name:
            continue
        chunk_path = Path(str(chunk.get("path", "")))
        if not chunk_path.is_absolute():
            if chunk_path.parts and chunk_path.parts[0].lower() == "warehouse":
                chunk_path = WAREHOUSE_DIR / Path(*chunk_path.parts[1:])
            elif chunk_path.parts and chunk_path.parts[0].lower() == "data":
                chunk_path = DATA_DIR / Path(*chunk_path.parts[1:])
            else:
                chunk_path = DATA_DIR / chunk_path
        chunk_path = _safe_under(chunk_path, [WAREHOUSE_DIR, DATA_DIR])
        if chunk_path.exists():
            chunk_paths.append(chunk_path)
            available_rows += int(chunk.get("rows", 0) or 0)
        else:
            missing_paths.append(_relative(chunk_path))
    return chunk_paths, missing_paths, available_rows


def _build_parquet_for_sheet(conn, chunk_paths: list[Path], parquet_path: Path) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    if parquet_path.exists():
        parquet_path.unlink()
    csv_paths_sql = "[" + ", ".join(_sql_literal(path.as_posix()) for path in chunk_paths) + "]"
    conn.execute(
        f"""
        COPY (
            SELECT *
            FROM read_csv_auto(
                {csv_paths_sql},
                union_by_name = true,
                header = true,
                all_varchar = true,
                sample_size = -1
            )
        )
        TO {_sql_literal(parquet_path.as_posix())}
        (FORMAT PARQUET, COMPRESSION ZSTD);
        """
    )


def _sample_rows(conn, schema: str, view_name: str, limit: int = 5) -> list[dict[str, Any]]:
    cursor = conn.execute(f"SELECT * FROM {_quote_ident(schema)}.{_quote_ident(view_name)} LIMIT {limit};")
    columns = [item[0] for item in cursor.description]
    rows = []
    for raw_row in cursor.fetchall():
        rows.append({column: _json_safe(value) for column, value in zip(columns, raw_row)})
    return rows


def _field_profiles(headers: list[str], sample_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles = []
    for field in headers:
        values = []
        for row in sample_rows:
            value = str(row.get(field, "") or "").strip()
            if value and value not in values:
                values.append(value)
            if len(values) >= 5:
                break
        profiles.append(
            {
                "field": field,
                "semantic_type": _semantic_type(field),
                "sample_values": values,
                "mapped_group": next((group for group in FIELD_GROUP_ALIASES if _find_field([field], group)), ""),
            }
        )
    return profiles


def _find_field_candidates(headers: list[str], candidates: list[str]) -> str:
    lowered_headers = [(header, header.lower()) for header in headers]
    lowered_candidates = [candidate.lower() for candidate in candidates]
    for candidate in lowered_candidates:
        for header, lowered in lowered_headers:
            if candidate == lowered:
                return header
    for candidate in sorted(lowered_candidates, key=len, reverse=True):
        for header, lowered in lowered_headers:
            if candidate in lowered:
                return header
    return ""


def _normalized_cost_expr(field_name: str) -> str:
    value_expr = _double_expr(field_name)
    return (
        f"CASE "
        f"WHEN {value_expr} IS NULL THEN NULL::DOUBLE "
        f"WHEN ABS({value_expr}) >= 500 THEN {value_expr} / 100.0 "
        f"ELSE {value_expr} END"
    )


def _find_sheet_view(dataset_record: dict[str, Any], keywords: list[str]) -> dict[str, Any] | None:
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for sheet in dataset_record.get("sheet_views", []):
        haystack = f"{sheet.get('sheet', '')} {sheet.get('raw_view_name', '')}".lower()
        if any(keyword in haystack for keyword in lowered_keywords):
            return sheet
    if len(dataset_record.get("sheet_views", [])) == 1:
        return dataset_record["sheet_views"][0]
    return None


def _query_to_csv(conn, sql: str, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cursor = conn.execute(sql)
    columns = [item[0] for item in cursor.description]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in cursor.fetchall():
            writer.writerow([_json_safe(value) for value in row])
    return _relative(path)


def _dedupe_view_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        view_name = str(entry.get("view_name", ""))
        if view_name:
            deduped[view_name] = entry
    return list(deduped.values())


def _register_raw_sheet_view(conn, dataset_slug: str, sheet_slug: str, parquet_path: Path) -> str:
    view_name = f"{dataset_slug}__{sheet_slug}"
    conn.execute(
        f"""
        CREATE OR REPLACE VIEW datasets.{_quote_ident(view_name)} AS
        SELECT * FROM read_parquet({_sql_literal(parquet_path.as_posix())});
        """
    )
    return view_name


def _create_mart_view(conn, category: str, view_name: str, source_view: str, sql_body: str) -> dict[str, str]:
    conn.execute(
        f"""
        CREATE OR REPLACE VIEW marts.{_quote_ident(view_name)} AS
        {sql_body}
        """
    )
    return {"category": category, "view_name": view_name, "source_view": source_view}


def _build_sheet_marts(
    conn,
    dataset_slug: str,
    sheet_slug: str,
    headers: list[str],
    raw_view_name: str,
    snapshot_date: str | None = None,
) -> list[dict[str, str]]:
    marts: list[dict[str, str]] = []
    sku_field = _find_field(headers, "sku")
    product_name_field = _find_field(headers, "product_name")
    date_field = _find_field(headers, "date")
    warehouse_field = _find_field(headers, "warehouse")
    channel_field = _find_field(headers, "channel")
    opening_field = _find_field(headers, "opening_inventory")
    inbound_field = _find_field(headers, "inbound")
    outbound_field = _find_field(headers, "outbound")
    ending_field = _find_field(headers, "ending_inventory")
    in_transit_field = _find_field(headers, "in_transit")
    sales_qty_field = _find_field(headers, "sales_qty")
    revenue_field = _find_field(headers, "revenue")
    cost_field = _find_field(headers, "cost")
    gross_profit_field = _find_field(headers, "gross_profit")
    cash_field = _find_field(headers, "cash")
    ad_spend_field = _find_field(headers, "ad_spend")
    acos_field = _find_field(headers, "acos")
    roas_field = _find_field(headers, "roas")
    snapshot_date_sql = _snapshot_date_expr(snapshot_date)
    effective_month_sql = _effective_month_expr(date_field, snapshot_date_sql)
    warehouse_partition_sql = _warehouse_partition_expr(warehouse_field)
    sku_hash_sql = _sku_hash_expr(sku_field)
    sku_hash_bucket_sql = _sku_hash_bucket_expr(sku_field)

    if sku_field and (ending_field or outbound_field or inbound_field or opening_field):
        valid_condition = _valid_business_row_condition(sku_field, product_name_field)
        marts.append(
            _create_mart_view(
                conn,
                "fact_inventory_daily",
                f"fact_inventory_daily__{dataset_slug}__{sheet_slug}",
                raw_view_name,
                f"""
                SELECT
                    {_sql_literal(dataset_slug)} AS dataset_slug,
                    {_sql_literal(sheet_slug)} AS dataset_sheet_slug,
                    _source_file,
                    _source_sheet,
                    _source_row_number,
                    {_date_text_expr(date_field)} AS date_text,
                    {_date_value_expr(date_field)} AS date_value,
                    {snapshot_date_sql} AS snapshot_date,
                    COALESCE({_date_value_expr(date_field)}, {snapshot_date_sql}) AS effective_date_value,
                    {effective_month_sql} AS effective_month,
                    {_text_expr(sku_field)} AS sku,
                    {sku_hash_sql} AS sku_hash,
                    {sku_hash_bucket_sql} AS sku_hash_bucket,
                    {_text_expr(product_name_field)} AS product_name,
                    {_text_expr(warehouse_field)} AS warehouse,
                    {warehouse_partition_sql} AS warehouse_partition,
                    {_double_expr(opening_field)} AS opening_inventory,
                    {_double_expr(inbound_field)} AS inbound,
                    {_double_expr(outbound_field)} AS outbound,
                    {_double_expr(ending_field)} AS ending_inventory,
                    {_double_expr(in_transit_field)} AS in_transit
                FROM datasets.{_quote_ident(raw_view_name)}
                WHERE {valid_condition}
                  AND (
                      {_double_expr(opening_field)} IS NOT NULL
                      OR {_double_expr(inbound_field)} IS NOT NULL
                      OR {_double_expr(outbound_field)} IS NOT NULL
                      OR {_double_expr(ending_field)} IS NOT NULL
                      OR {_double_expr(in_transit_field)} IS NOT NULL
                  )
                """,
            )
        )

    if sku_field and (sales_qty_field or revenue_field):
        valid_condition = _valid_business_row_condition(sku_field, product_name_field)
        marts.append(
            _create_mart_view(
                conn,
                "fact_sales_daily",
                f"fact_sales_daily__{dataset_slug}__{sheet_slug}",
                raw_view_name,
                f"""
                SELECT
                    {_sql_literal(dataset_slug)} AS dataset_slug,
                    {_sql_literal(sheet_slug)} AS dataset_sheet_slug,
                    _source_file,
                    _source_sheet,
                    _source_row_number,
                    {_date_text_expr(date_field)} AS date_text,
                    {_date_value_expr(date_field)} AS date_value,
                    {snapshot_date_sql} AS snapshot_date,
                    COALESCE({_date_value_expr(date_field)}, {snapshot_date_sql}) AS effective_date_value,
                    {effective_month_sql} AS effective_month,
                    {_text_expr(sku_field)} AS sku,
                    {sku_hash_sql} AS sku_hash,
                    {sku_hash_bucket_sql} AS sku_hash_bucket,
                    {_text_expr(product_name_field)} AS product_name,
                    {_text_expr(warehouse_field)} AS warehouse,
                    {warehouse_partition_sql} AS warehouse_partition,
                    {_text_expr(channel_field)} AS channel,
                    {_double_expr(sales_qty_field or outbound_field)} AS sales_qty,
                    {_double_expr(revenue_field)} AS revenue
                FROM datasets.{_quote_ident(raw_view_name)}
                WHERE {valid_condition}
                  AND (
                      {_double_expr(sales_qty_field or outbound_field)} IS NOT NULL
                      OR {_double_expr(revenue_field)} IS NOT NULL
                  )
                """,
            )
        )

    if warehouse_field and (inbound_field or outbound_field):
        valid_condition = _valid_business_row_condition(sku_field, product_name_field)
        marts.append(
            _create_mart_view(
                conn,
                "fact_inbound_outbound",
                f"fact_inbound_outbound__{dataset_slug}__{sheet_slug}",
                raw_view_name,
                f"""
                SELECT
                    {_sql_literal(dataset_slug)} AS dataset_slug,
                    {_sql_literal(sheet_slug)} AS dataset_sheet_slug,
                    _source_file,
                    _source_sheet,
                    _source_row_number,
                    {_date_text_expr(date_field)} AS date_text,
                    {_date_value_expr(date_field)} AS date_value,
                    {snapshot_date_sql} AS snapshot_date,
                    COALESCE({_date_value_expr(date_field)}, {snapshot_date_sql}) AS effective_date_value,
                    {effective_month_sql} AS effective_month,
                    {_text_expr(sku_field)} AS sku,
                    {sku_hash_sql} AS sku_hash,
                    {sku_hash_bucket_sql} AS sku_hash_bucket,
                    {_text_expr(product_name_field)} AS product_name,
                    {_text_expr(warehouse_field)} AS warehouse,
                    {warehouse_partition_sql} AS warehouse_partition,
                    {_text_expr(channel_field)} AS channel,
                    {_double_expr(inbound_field)} AS inbound,
                    {_double_expr(outbound_field)} AS outbound,
                    {_double_expr(ending_field)} AS ending_inventory
                FROM datasets.{_quote_ident(raw_view_name)}
                WHERE {valid_condition}
                  AND {_text_expr(warehouse_field)} IS NOT NULL
                  AND (
                      {_double_expr(inbound_field)} IS NOT NULL
                      OR {_double_expr(outbound_field)} IS NOT NULL
                      OR {_double_expr(ending_field)} IS NOT NULL
                  )
                """,
            )
        )

    if date_field and (cost_field or gross_profit_field or cash_field):
        valid_condition = _valid_business_row_condition(sku_field, product_name_field)
        marts.append(
            _create_mart_view(
                conn,
                "fact_finance_daily",
                f"fact_finance_daily__{dataset_slug}__{sheet_slug}",
                raw_view_name,
                f"""
                SELECT
                    {_sql_literal(dataset_slug)} AS dataset_slug,
                    {_sql_literal(sheet_slug)} AS dataset_sheet_slug,
                    _source_file,
                    _source_sheet,
                    _source_row_number,
                    {_date_text_expr(date_field)} AS date_text,
                    {_date_value_expr(date_field)} AS date_value,
                    {snapshot_date_sql} AS snapshot_date,
                    COALESCE({_date_value_expr(date_field)}, {snapshot_date_sql}) AS effective_date_value,
                    {effective_month_sql} AS effective_month,
                    {_text_expr(sku_field)} AS sku,
                    {sku_hash_sql} AS sku_hash,
                    {sku_hash_bucket_sql} AS sku_hash_bucket,
                    {_text_expr(product_name_field)} AS product_name,
                    {_text_expr(warehouse_field)} AS warehouse,
                    {warehouse_partition_sql} AS warehouse_partition,
                    {_text_expr(channel_field)} AS channel,
                    {_double_expr(revenue_field)} AS revenue,
                    {_double_expr(cost_field)} AS cost,
                    {_double_expr(gross_profit_field)} AS gross_profit,
                    {_double_expr(cash_field)} AS cash
                FROM datasets.{_quote_ident(raw_view_name)}
                WHERE {valid_condition}
                  AND (
                      {_double_expr(revenue_field)} IS NOT NULL
                      OR {_double_expr(cost_field)} IS NOT NULL
                      OR {_double_expr(gross_profit_field)} IS NOT NULL
                      OR {_double_expr(cash_field)} IS NOT NULL
                  )
                """,
            )
        )

    if date_field and (ad_spend_field or acos_field or roas_field):
        valid_condition = _valid_business_row_condition(sku_field, product_name_field)
        marts.append(
            _create_mart_view(
                conn,
                "fact_ads_daily",
                f"fact_ads_daily__{dataset_slug}__{sheet_slug}",
                raw_view_name,
                f"""
                SELECT
                    {_sql_literal(dataset_slug)} AS dataset_slug,
                    {_sql_literal(sheet_slug)} AS dataset_sheet_slug,
                    _source_file,
                    _source_sheet,
                    _source_row_number,
                    {_date_text_expr(date_field)} AS date_text,
                    {_date_value_expr(date_field)} AS date_value,
                    {snapshot_date_sql} AS snapshot_date,
                    COALESCE({_date_value_expr(date_field)}, {snapshot_date_sql}) AS effective_date_value,
                    {effective_month_sql} AS effective_month,
                    {_text_expr(sku_field)} AS sku,
                    {sku_hash_sql} AS sku_hash,
                    {sku_hash_bucket_sql} AS sku_hash_bucket,
                    {_text_expr(product_name_field)} AS product_name,
                    {_text_expr(warehouse_field)} AS warehouse,
                    {warehouse_partition_sql} AS warehouse_partition,
                    {_text_expr(channel_field)} AS channel,
                    {_double_expr(ad_spend_field)} AS ad_spend,
                    {_double_expr(acos_field)} AS acos,
                    {_double_expr(roas_field)} AS roas
                FROM datasets.{_quote_ident(raw_view_name)}
                WHERE {valid_condition}
                  AND (
                      {_double_expr(ad_spend_field)} IS NOT NULL
                      OR {_double_expr(acos_field)} IS NOT NULL
                      OR {_double_expr(roas_field)} IS NOT NULL
                  )
                """,
            )
        )

    if sku_field:
        valid_condition = _valid_business_row_condition(sku_field, product_name_field)
        marts.append(
            _create_mart_view(
                conn,
                "dim_product",
                f"dim_product__{dataset_slug}__{sheet_slug}",
                raw_view_name,
                f"""
                SELECT DISTINCT
                    {_sql_literal(dataset_slug)} AS dataset_slug,
                    {_text_expr(sku_field)} AS sku,
                    {_text_expr(product_name_field)} AS product_name
                FROM datasets.{_quote_ident(raw_view_name)}
                WHERE {valid_condition}
                """,
            )
        )

    if warehouse_field:
        marts.append(
            _create_mart_view(
                conn,
                "dim_warehouse",
                f"dim_warehouse__{dataset_slug}__{sheet_slug}",
                raw_view_name,
                f"""
                SELECT DISTINCT
                    {_sql_literal(dataset_slug)} AS dataset_slug,
                    {_text_expr(warehouse_field)} AS warehouse
                FROM datasets.{_quote_ident(raw_view_name)}
                WHERE {_text_expr(warehouse_field)} IS NOT NULL
                """,
            )
        )

    return marts


def _refresh_global_marts(conn, registry: dict[str, Any]) -> None:
    categories = [
        "fact_inventory_daily",
        "fact_sales_daily",
        "fact_inbound_outbound",
        "fact_finance_daily",
        "fact_ads_daily",
        "dim_product",
        "dim_warehouse",
    ]
    for category in categories:
        sources = []
        for dataset in registry.get("datasets", {}).values():
            for mart in dataset.get("mart_views", []):
                if mart.get("category") == category:
                    sources.append(f"SELECT * FROM marts.{_quote_ident(mart['view_name'])}")
        if sources:
            conn.execute(
                f"""
                CREATE OR REPLACE VIEW marts.{_quote_ident(category)} AS
                {" UNION ALL ".join(sources)};
                """
            )
    fact_inventory_sources = [
        mart
        for dataset in registry.get("datasets", {}).values()
        for mart in dataset.get("mart_views", [])
        if mart.get("category") == "fact_inventory_daily"
    ]
    if fact_inventory_sources:
        conn.execute(
            """
            CREATE OR REPLACE VIEW marts.current_inventory_snapshot AS
            WITH ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY dataset_slug, sku, warehouse
                        ORDER BY effective_date_value DESC NULLS LAST,
                                 ABS(COALESCE(ending_inventory, 0)) DESC,
                                 _source_row_number DESC
                    ) AS inventory_rank
                FROM marts.fact_inventory_daily
                WHERE sku IS NOT NULL
            )
            SELECT *
            FROM ranked
            WHERE inventory_rank = 1;
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE VIEW marts.agg_warehouse_inventory AS
            SELECT
                dataset_slug,
                effective_date_value AS snapshot_date,
                effective_month,
                warehouse,
                warehouse_partition,
                COUNT(DISTINCT sku) AS sku_count,
                SUM(COALESCE(opening_inventory, 0)) AS opening_inventory,
                SUM(COALESCE(inbound, 0)) AS inbound,
                SUM(COALESCE(outbound, 0)) AS outbound,
                SUM(COALESCE(ending_inventory, 0)) AS ending_inventory,
                SUM(COALESCE(in_transit, 0)) AS in_transit
            FROM marts.current_inventory_snapshot
            GROUP BY dataset_slug, effective_date_value, effective_month, warehouse, warehouse_partition;
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE VIEW marts.inventory_partition_index AS
            SELECT
                dataset_slug,
                effective_month,
                warehouse,
                warehouse_partition,
                sku_hash_bucket,
                MIN(effective_date_value) AS first_date_value,
                MAX(effective_date_value) AS last_date_value,
                COUNT(*) AS row_count,
                COUNT(DISTINCT sku) AS sku_count,
                SUM(COALESCE(ending_inventory, 0)) AS ending_inventory
            FROM marts.fact_inventory_daily
            WHERE sku IS NOT NULL
            GROUP BY dataset_slug, effective_month, warehouse, warehouse_partition, sku_hash_bucket;
            """
        )

    if any(
        mart.get("category") == "fact_sales_daily"
        for dataset in registry.get("datasets", {}).values()
        for mart in dataset.get("mart_views", [])
    ):
        conn.execute(
            """
            CREATE OR REPLACE VIEW marts.agg_sku_daily_sales AS
            SELECT
                effective_date_value AS date_value,
                effective_month,
                sku,
                sku_hash,
                sku_hash_bucket,
                ANY_VALUE(product_name) FILTER (WHERE product_name IS NOT NULL) AS product_name,
                SUM(COALESCE(sales_qty, 0)) AS sales_qty,
                SUM(COALESCE(revenue, 0)) AS revenue
            FROM marts.fact_sales_daily
            WHERE sku IS NOT NULL
              AND sales_qty IS NOT NULL
              AND COALESCE(sales_qty, 0) > 0
            GROUP BY effective_date_value, effective_month, sku, sku_hash, sku_hash_bucket;
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE VIEW marts.agg_channel_sales AS
            SELECT
                COALESCE(channel, 'unknown') AS channel,
                sku,
                sku_hash,
                sku_hash_bucket,
                ANY_VALUE(product_name) FILTER (WHERE product_name IS NOT NULL) AS product_name,
                MIN(effective_date_value) AS first_date_value,
                MAX(effective_date_value) AS last_date_value,
                SUM(COALESCE(sales_qty, 0)) AS sales_qty,
                SUM(COALESCE(revenue, 0)) AS revenue
            FROM marts.fact_sales_daily
            WHERE sku IS NOT NULL
              AND sales_qty IS NOT NULL
              AND COALESCE(sales_qty, 0) > 0
            GROUP BY COALESCE(channel, 'unknown'), sku, sku_hash, sku_hash_bucket;
            """
        )

    if any(
        mart.get("category") == "fact_inbound_outbound"
        for dataset in registry.get("datasets", {}).values()
        for mart in dataset.get("mart_views", [])
    ):
        conn.execute(
            """
            CREATE OR REPLACE VIEW marts.agg_inbound_outbound_daily AS
            SELECT
                effective_date_value AS date_value,
                effective_month,
                warehouse,
                warehouse_partition,
                sku,
                sku_hash,
                sku_hash_bucket,
                ANY_VALUE(product_name) FILTER (WHERE product_name IS NOT NULL) AS product_name,
                SUM(COALESCE(inbound, 0)) AS inbound,
                SUM(COALESCE(outbound, 0)) AS outbound,
                SUM(COALESCE(inbound, 0) + COALESCE(outbound, 0)) AS net_movement,
                SUM(COALESCE(ending_inventory, 0)) AS ending_inventory
            FROM marts.fact_inbound_outbound
            WHERE sku IS NOT NULL
            GROUP BY effective_date_value, effective_month, warehouse, warehouse_partition, sku, sku_hash, sku_hash_bucket;
            """
        )

    has_inventory = any(
        mart.get("category") == "fact_inventory_daily"
        for dataset in registry.get("datasets", {}).values()
        for mart in dataset.get("mart_views", [])
    )
    has_movement = any(
        mart.get("category") == "fact_inbound_outbound"
        for dataset in registry.get("datasets", {}).values()
        for mart in dataset.get("mart_views", [])
    )
    has_sales = any(
        mart.get("category") == "fact_sales_daily"
        for dataset in registry.get("datasets", {}).values()
        for mart in dataset.get("mart_views", [])
    )
    if has_inventory:
        reference_date_sql = (
            """
                SELECT MAX(effective_date_value) AS max_effective_date
                FROM (
                    SELECT effective_date_value FROM marts.current_inventory_snapshot
                    UNION ALL
                    SELECT effective_date_value FROM marts.fact_sales_daily
                ) reference_dates
            """
            if has_sales
            else """
                SELECT MAX(effective_date_value) AS max_effective_date
                FROM marts.current_inventory_snapshot
            """
        )
        sales_cte = (
            """
            recent_sales AS (
                SELECT
                    sales.sku,
                    COALESCE(sales.warehouse, 'unknown') AS warehouse_partition,
                    SUM(COALESCE(sales.sales_qty, 0)) AS sales_qty_30d,
                    COUNT(DISTINCT sales.effective_date_value) FILTER (WHERE COALESCE(sales.sales_qty, 0) > 0) AS selling_days_30d
                FROM marts.fact_sales_daily sales
                CROSS JOIN reference_date ref
                WHERE sales.sku IS NOT NULL
                  AND sales.effective_date_value >= ref.max_effective_date - INTERVAL 30 DAY
                  AND sales.effective_date_value <= ref.max_effective_date
                GROUP BY sales.sku, COALESCE(sales.warehouse, 'unknown')
            ),
            """
            if has_sales
            else """
            recent_sales AS (
                SELECT
                    NULL::VARCHAR AS sku,
                    NULL::VARCHAR AS warehouse_partition,
                    0::DOUBLE AS sales_qty_30d,
                    0::BIGINT AS selling_days_30d
                WHERE FALSE
            ),
            """
        )
        movement_cte = (
            """
            movement_balance AS (
                SELECT
                    dataset_slug,
                    effective_date_value,
                    sku,
                    warehouse_partition,
                    ANY_VALUE(product_name) FILTER (WHERE product_name IS NOT NULL) AS product_name,
                    SUM(COALESCE(inbound, 0)) AS inbound,
                    SUM(COALESCE(outbound, 0)) AS outbound,
                    SUM(COALESCE(ending_inventory, 0)) AS ending_inventory
                FROM marts.fact_inbound_outbound
                WHERE sku IS NOT NULL
                GROUP BY dataset_slug, effective_date_value, sku, warehouse_partition
            ),
            """
            if has_movement
            else """
            movement_balance AS (
                SELECT
                    NULL::VARCHAR AS dataset_slug,
                    NULL::DATE AS effective_date_value,
                    NULL::VARCHAR AS sku,
                    NULL::VARCHAR AS warehouse_partition,
                    NULL::VARCHAR AS product_name,
                    0::DOUBLE AS inbound,
                    0::DOUBLE AS outbound,
                    0::DOUBLE AS ending_inventory
                WHERE FALSE
            ),
            """
        )
        conn.execute(
            f"""
            CREATE OR REPLACE VIEW marts.inventory_anomalies AS
            WITH reference_date AS (
                {reference_date_sql}
            ),
            {sales_cte}
            {movement_cte}
            latest_inventory AS (
                SELECT
                    inv.dataset_slug,
                    inv.effective_date_value,
                    inv.effective_month,
                    inv.sku,
                    inv.sku_hash,
                    inv.sku_hash_bucket,
                    inv.product_name,
                    inv.warehouse,
                    inv.warehouse_partition,
                    inv.opening_inventory,
                    inv.inbound,
                    inv.outbound,
                    inv.ending_inventory,
                    inv.in_transit,
                    COALESCE(sales.sales_qty_30d, 0) AS sales_qty_30d,
                    COALESCE(sales.selling_days_30d, 0) AS selling_days_30d
                FROM marts.current_inventory_snapshot inv
                LEFT JOIN recent_sales sales
                  ON sales.sku = inv.sku
                 AND sales.warehouse_partition = inv.warehouse_partition
                WHERE inv.sku IS NOT NULL
            )
            SELECT
                'negative_inventory' AS anomaly_type,
                'high' AS severity,
                dataset_slug,
                effective_date_value,
                effective_month,
                sku,
                sku_hash,
                sku_hash_bucket,
                product_name,
                warehouse,
                warehouse_partition,
                ending_inventory,
                inbound,
                outbound,
                opening_inventory,
                in_transit,
                sales_qty_30d,
                selling_days_30d,
                '库存为负，需要核对期初、出入库或仓库映射。' AS recommendation
            FROM latest_inventory
            WHERE COALESCE(ending_inventory, 0) < 0

            UNION ALL

            SELECT
                'inbound_outbound_imbalance' AS anomaly_type,
                'medium' AS severity,
                inv.dataset_slug,
                inv.effective_date_value,
                inv.effective_month,
                inv.sku,
                inv.sku_hash,
                inv.sku_hash_bucket,
                inv.product_name,
                inv.warehouse,
                inv.warehouse_partition,
                inv.ending_inventory,
                inv.inbound,
                inv.outbound,
                inv.opening_inventory,
                inv.in_transit,
                inv.sales_qty_30d,
                inv.selling_days_30d,
                '期初 + 入库 + 出库 与期末不一致，需要检查出入库符号和漏记单据。' AS recommendation
            FROM latest_inventory inv
            WHERE inv.opening_inventory IS NOT NULL
              AND inv.ending_inventory IS NOT NULL
              AND ABS(
                    COALESCE(inv.opening_inventory, 0)
                    + COALESCE(inv.inbound, 0)
                    + COALESCE(inv.outbound, 0)
                    - COALESCE(inv.ending_inventory, 0)
                  ) > 0.01

            UNION ALL

            SELECT
                'no_sales_30d_high_inventory' AS anomaly_type,
                'medium' AS severity,
                dataset_slug,
                effective_date_value,
                effective_month,
                sku,
                sku_hash,
                sku_hash_bucket,
                product_name,
                warehouse,
                warehouse_partition,
                ending_inventory,
                inbound,
                outbound,
                opening_inventory,
                in_transit,
                sales_qty_30d,
                selling_days_30d,
                '近 30 天无销量但库存较高，建议排查滞销、渠道映射或补货策略。' AS recommendation
            FROM latest_inventory
            WHERE COALESCE(sales_qty_30d, 0) <= 0
              AND COALESCE(ending_inventory, 0) >= 100

            UNION ALL

            SELECT
                'stockout_risk' AS anomaly_type,
                'high' AS severity,
                dataset_slug,
                effective_date_value,
                effective_month,
                sku,
                sku_hash,
                sku_hash_bucket,
                product_name,
                warehouse,
                warehouse_partition,
                ending_inventory,
                inbound,
                outbound,
                opening_inventory,
                in_transit,
                sales_qty_30d,
                selling_days_30d,
                '按近 30 天销量估算库存覆盖不足 7 天或库存已经非正，建议检查补货/调拨。' AS recommendation
            FROM latest_inventory
            WHERE COALESCE(ending_inventory, 0) <= 0
               OR (
                    COALESCE(sales_qty_30d, 0) > 0
                    AND COALESCE(ending_inventory, 0) <= GREATEST(1, COALESCE(sales_qty_30d, 0) / 30.0 * 7.0)
                  );
            """
        )


def _refresh_global_semantic_views(conn, registry: dict[str, Any]) -> None:
    categories = ["dim_channel", "dim_product_master", "inventory_current"]
    for category in categories:
        sources = []
        for dataset in registry.get("datasets", {}).values():
            for semantic_view in dataset.get("semantic_views", []):
                if semantic_view.get("category") == category:
                    sources.append(f"SELECT * FROM marts.{_quote_ident(semantic_view['view_name'])}")
        if sources:
            conn.execute(
                f"""
                CREATE OR REPLACE VIEW marts.{_quote_ident(category)} AS
                {" UNION ALL ".join(sources)};
                """
            )


def _materialize_semantic_assets(conn, dataset_record: dict[str, Any]) -> dict[str, Any]:
    dataset_slug = str(dataset_record.get("dataset_slug", "dataset"))
    source_name = Path(str(dataset_record.get("source", ""))).name or f"{dataset_slug}.source"
    derived_dir = _safe_under(DERIVED_DIR / dataset_slug, [DERIVED_DIR])
    derived_dir.mkdir(parents=True, exist_ok=True)
    semantic_views: list[dict[str, str]] = []
    derived_exports: list[str] = []
    additional_mart_views: list[dict[str, str]] = []
    warnings: list[str] = []

    product_sheet = _find_sheet_view(dataset_record, ["商品对照", "分库存底表", "inventory"])
    erp_sheet = _find_sheet_view(dataset_record, ["erp底表", "sales"])

    product_view_name = f"dim_product_master__{dataset_slug}"
    product_sources_sql: list[str] = []
    if product_sheet is not None:
        raw_view_name = str(product_sheet["raw_view_name"])
        headers = list(product_sheet.get("headers", []))
        sku_field = _find_field(headers, "sku")
        product_name_field = _find_field(headers, "product_name")
        brand_field = _find_field(headers, "brand")
        product_position_field = _find_field_candidates(headers, ["产品定位"])
        category_field = _find_field_candidates(headers, ["分类"])
        short_name_field = _find_field_candidates(headers, ["缩写"])
        content_field = _find_field_candidates(headers, ["含量", "规格"])
        product_type_field = _find_field_candidates(headers, ["产品类型"])
        unit_cost_field = _find_field_candidates(headers, ["采购单价", "成本", "货品成本"])
        product_sources_sql.append(
            f"""
            SELECT
                {_sql_literal(dataset_slug)} AS dataset_slug,
                {_text_expr(sku_field)} AS sku,
                {_text_expr(brand_field)} AS brand,
                {_text_expr(product_name_field)} AS product_name,
                {_text_expr(category_field)} AS category,
                {_text_expr(short_name_field)} AS short_name,
                {_text_expr(content_field)} AS content,
                {_text_expr(product_type_field)} AS product_type,
                {_text_expr(product_position_field)} AS product_position,
                {_normalized_cost_expr(unit_cost_field)} AS purchase_unit_cost
            FROM datasets.{_quote_ident(raw_view_name)}
            WHERE {_valid_business_row_condition(sku_field, product_name_field)}
            """
        )
    if erp_sheet is not None:
        raw_view_name = str(erp_sheet["raw_view_name"])
        headers = list(erp_sheet.get("headers", []))
        sku_field = _find_field(headers, "sku")
        product_name_field = _find_field(headers, "product_name")
        brand_field = _find_field(headers, "brand")
        product_position_field = _find_field_candidates(headers, ["产品定位"])
        category_field = _find_field_candidates(headers, ["分类"])
        short_name_field = _find_field_candidates(headers, ["缩写"])
        product_type_field = _find_field_candidates(headers, ["产品类型"])
        product_sources_sql.append(
            f"""
            SELECT
                {_sql_literal(dataset_slug)} AS dataset_slug,
                {_text_expr(sku_field)} AS sku,
                {_text_expr(brand_field)} AS brand,
                {_text_expr(product_name_field)} AS product_name,
                {_text_expr(category_field)} AS category,
                {_text_expr(short_name_field)} AS short_name,
                NULL::VARCHAR AS content,
                {_text_expr(product_type_field)} AS product_type,
                {_text_expr(product_position_field)} AS product_position,
                NULL::DOUBLE AS purchase_unit_cost
            FROM datasets.{_quote_ident(raw_view_name)}
            WHERE {_valid_business_row_condition(sku_field, product_name_field)}
            """
        )
    if product_sources_sql:
        conn.execute(
            f"""
            CREATE OR REPLACE VIEW marts.{_quote_ident(product_view_name)} AS
            WITH product_sources AS (
                {" UNION ALL ".join(product_sources_sql)}
            )
            SELECT
                dataset_slug,
                sku,
                ANY_VALUE(brand) FILTER (WHERE brand IS NOT NULL) AS brand,
                ANY_VALUE(product_name) FILTER (WHERE product_name IS NOT NULL) AS product_name,
                ANY_VALUE(category) FILTER (WHERE category IS NOT NULL) AS category,
                ANY_VALUE(short_name) FILTER (WHERE short_name IS NOT NULL) AS short_name,
                ANY_VALUE(content) FILTER (WHERE content IS NOT NULL) AS content,
                ANY_VALUE(product_type) FILTER (WHERE product_type IS NOT NULL) AS product_type,
                ANY_VALUE(product_position) FILTER (WHERE product_position IS NOT NULL) AS product_position,
                MAX(purchase_unit_cost) AS purchase_unit_cost
            FROM product_sources
            WHERE sku IS NOT NULL
            GROUP BY dataset_slug, sku;
            """
        )
        semantic_views.append({"category": "dim_product_master", "view_name": product_view_name})
        derived_exports.append(
            _query_to_csv(
                conn,
                f"SELECT * FROM marts.{_quote_ident(product_view_name)} ORDER BY sku",
                derived_dir / "dim_product_master.csv",
            )
        )
    else:
        warnings.append("Could not infer product master sources for this dataset.")

    if erp_sheet is not None:
        raw_view_name = str(erp_sheet["raw_view_name"])
        headers = list(erp_sheet.get("headers", []))
        sales_channel_field = _find_field_candidates(headers, ["销售渠道"])
        warehouse_field = _find_field(headers, "warehouse")
        channel_category_field = _find_field_candidates(headers, ["渠道分类"])
        department_category_field = _find_field_candidates(headers, ["部门分类"])
        order_category_field = _find_field_candidates(headers, ["下单分类", "订单类型"])
        region_field = _find_field_candidates(headers, ["区域"])
        channel_view_name = f"dim_channel__{dataset_slug}"
        conn.execute(
            f"""
            CREATE OR REPLACE VIEW marts.{_quote_ident(channel_view_name)} AS
            SELECT DISTINCT
                {_sql_literal(dataset_slug)} AS dataset_slug,
                {_text_expr(sales_channel_field)} AS sales_channel,
                {_text_expr(warehouse_field)} AS warehouse,
                {_text_expr(channel_category_field)} AS channel_category,
                {_text_expr(department_category_field)} AS department_category,
                {_text_expr(order_category_field)} AS order_category,
                {_text_expr(region_field)} AS region
            FROM datasets.{_quote_ident(raw_view_name)}
            WHERE {_text_expr(sales_channel_field)} IS NOT NULL;
            """
        )
        semantic_views.append({"category": "dim_channel", "view_name": channel_view_name})
        derived_exports.append(
            _query_to_csv(
                conn,
                f"SELECT * FROM marts.{_quote_ident(channel_view_name)} ORDER BY sales_channel, warehouse",
                derived_dir / "dim_channel.csv",
            )
        )
    else:
        warnings.append("Could not infer channel dimension sources for this dataset.")

    if any(mart.get("category") == "fact_inventory_daily" for mart in dataset_record.get("mart_views", [])):
        inventory_view_name = f"inventory_current__{dataset_slug}"
        product_join = (
            f"LEFT JOIN marts.{_quote_ident(product_view_name)} prod "
            f"ON inv.dataset_slug = prod.dataset_slug AND inv.sku = prod.sku"
            if any(view.get("view_name") == product_view_name for view in semantic_views)
            else ""
        )
        conn.execute(
            f"""
            CREATE OR REPLACE VIEW marts.{_quote_ident(inventory_view_name)} AS
            SELECT
                inv.dataset_slug,
                inv.effective_date_value AS snapshot_date,
                inv.sku,
                COALESCE(prod.product_name, inv.product_name) AS product_name,
                inv.warehouse,
                inv.ending_inventory AS current_inventory,
                inv.in_transit,
                inv.inbound,
                inv.outbound,
                prod.category,
                prod.product_type,
                prod.product_position,
                prod.purchase_unit_cost,
                COALESCE(inv.ending_inventory, 0) * COALESCE(prod.purchase_unit_cost, 0) AS inventory_value_estimate
            FROM marts.current_inventory_snapshot inv
            {product_join}
            WHERE inv.dataset_slug = {_sql_literal(dataset_slug)};
            """
        )
        semantic_views.append({"category": "inventory_current", "view_name": inventory_view_name})
        derived_exports.append(
            _query_to_csv(
                conn,
                f"SELECT * FROM marts.{_quote_ident(inventory_view_name)} ORDER BY current_inventory DESC NULLS LAST, sku",
                derived_dir / "inventory_current.csv",
            )
        )

    erp_has_revenue = False
    if erp_sheet is not None:
        erp_has_revenue = bool(_find_field(list(erp_sheet.get("headers", [])), "revenue"))
    has_raw_finance_mart = any(mart.get("category") == "fact_finance_daily" for mart in dataset_record.get("mart_views", []))
    has_sales_mart = any(mart.get("category") == "fact_sales_daily" for mart in dataset_record.get("mart_views", []))
    if erp_has_revenue and has_sales_mart and not has_raw_finance_mart and any(view.get("view_name") == product_view_name for view in semantic_views):
        finance_view_name = f"fact_finance_daily__derived__{dataset_slug}"
        conn.execute(
            f"""
            CREATE OR REPLACE VIEW marts.{_quote_ident(finance_view_name)} AS
            SELECT
                sales.dataset_slug,
                {_sql_literal('derived_finance')} AS dataset_sheet_slug,
                {_sql_literal(source_name)} AS _source_file,
                {_sql_literal('derived_finance')} AS _source_sheet,
                NULL::BIGINT AS _source_row_number,
                sales.date_text,
                sales.date_value,
                sales.snapshot_date,
                sales.effective_date_value,
                sales.effective_month,
                sales.sku,
                sales.sku_hash,
                sales.sku_hash_bucket,
                COALESCE(prod.product_name, sales.product_name) AS product_name,
                sales.warehouse,
                sales.warehouse_partition,
                sales.channel,
                SUM(COALESCE(sales.revenue, 0)) AS revenue,
                SUM(ABS(COALESCE(sales.sales_qty, 0)) * COALESCE(prod.purchase_unit_cost, 0)) AS cost,
                SUM(COALESCE(sales.revenue, 0) - ABS(COALESCE(sales.sales_qty, 0)) * COALESCE(prod.purchase_unit_cost, 0)) AS gross_profit,
                NULL::DOUBLE AS cash
            FROM marts.fact_sales_daily sales
            LEFT JOIN marts.{_quote_ident(product_view_name)} prod
              ON sales.dataset_slug = prod.dataset_slug AND sales.sku = prod.sku
            WHERE sales.dataset_slug = {_sql_literal(dataset_slug)}
            GROUP BY
                sales.dataset_slug,
                sales.date_text,
                sales.date_value,
                sales.snapshot_date,
                sales.effective_date_value,
                sales.effective_month,
                sales.sku,
                sales.sku_hash,
                sales.sku_hash_bucket,
                COALESCE(prod.product_name, sales.product_name),
                sales.warehouse,
                sales.warehouse_partition,
                sales.channel;
            """
        )
        additional_mart_views.append({"category": "fact_finance_daily", "view_name": finance_view_name, "source_view": finance_view_name})
        derived_exports.append(
            _query_to_csv(
                conn,
                f"SELECT * FROM marts.{_quote_ident(finance_view_name)} ORDER BY effective_date_value DESC NULLS LAST, sku, warehouse, channel",
                derived_dir / "fact_finance_daily.csv",
            )
        )
    elif not has_raw_finance_mart:
        warnings.append("Could not derive finance fact table for this dataset.")

    if not any(mart.get("category") == "fact_ads_daily" for mart in dataset_record.get("mart_views", [])):
        warnings.append("No real ads source table is present for this dataset, so fact_ads_daily remains unpopulated.")

    return {
        "semantic_views": semantic_views,
        "derived_exports": derived_exports,
        "additional_mart_views": additional_mart_views,
        "warnings": warnings,
    }


def _dataset_query_recipes(sheet_views: list[dict[str, Any]], mart_views: list[dict[str, str]]) -> list[dict[str, Any]]:
    recipes = []
    for sheet in sheet_views:
        recipes.append(
            {
                "title": f"Preview raw sheet {sheet['sheet']}",
                "sql": f'SELECT * FROM datasets."{sheet["raw_view_name"]}" LIMIT 50;',
            }
        )
    for mart in mart_views:
        recipes.extend(QUERY_RECIPE_TEMPLATES.get(mart["category"], []))
    seen = set()
    deduped = []
    for recipe in recipes:
        key = (recipe["title"], recipe["sql"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(recipe)
    return deduped


def _build_dataset_wiki(
    dataset_slug: str,
    source_path: Path,
    manifest: dict[str, Any],
    quality: dict[str, Any],
    sheet_views: list[dict[str, Any]],
    mart_views: list[dict[str, str]],
    dataset_warnings: list[str],
) -> dict[str, str]:
    dataset_dir = _safe_under(WIKI_DIR / "datasets" / dataset_slug, [WIKI_DIR])
    dataset_dir.mkdir(parents=True, exist_ok=True)
    source_mtime = datetime.fromtimestamp(source_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S") if source_path.exists() else ""
    query_recipes = _dataset_query_recipes(sheet_views, mart_views)

    overview_lines = [
        f"- Source file: `{_relative(source_path)}`",
        f"- Last source update: {source_mtime}",
        f"- Processed at: {manifest.get('processed_at', '')}",
        f"- Manifest: `{manifest.get('manifest_path', '')}`",
        f"- Quality report: `{quality.get('quality_report_path', '')}`",
        f"- DuckDB: `{_relative(DUCKDB_PATH)}`",
        f"- Sheet count: {len(sheet_views)}",
        f"- Mart views: {', '.join(sorted({mart['category'] for mart in mart_views})) or 'None'}",
        "",
        "## What This Dataset Is For",
        "",
        "- Use wiki pages to understand meaning, field definitions, known caveats, and reusable query patterns.",
        "- Use DuckDB marts for full-table metrics, filters, grouping, and time-window analysis.",
        "- Do not rely on warehouse CSV previews for semantic retrieval.",
        "",
        "## Registration Warnings",
        "",
    ]
    if dataset_warnings:
        overview_lines.extend(f"- {warning}" for warning in dataset_warnings)
    else:
        overview_lines.append("- No registration warnings.")
    overview_lines.extend(
        [
            "",
        "## Sheets",
        "",
        ]
    )
    for sheet in sheet_views:
        overview_lines.extend(
            [
                f"- `{sheet['sheet']}`: rows={sheet['rows']} available_rows={sheet['available_rows_from_chunks']} columns={sheet['columns']} raw_view=`datasets.{sheet['raw_view_name']}`",
                f"  Meaning: {sheet['business_meaning']}",
                f"  Snapshot date: {sheet.get('snapshot_date') or 'unresolved'}",
            ]
        )
    _write_markdown(dataset_dir / "overview.md", f"Dataset Overview - {dataset_slug}", overview_lines)

    field_lines = [
        f"- Dataset: `{dataset_slug}`",
        f"- Source: `{_relative(source_path)}`",
        "",
        "## Fields",
        "",
    ]
    for sheet in sheet_views:
        field_lines.append(f"### {sheet['sheet']}")
        field_lines.append("")
        for profile in sheet["field_profiles"]:
            examples = ", ".join(f"`{value}`" for value in profile["sample_values"]) or "No sample values"
            mapped_group = f"`{profile['mapped_group']}`" if profile["mapped_group"] else "Unmapped"
            field_lines.extend(
                [
                    f"- `{profile['field']}`: type=`{profile['semantic_type']}` group={mapped_group} examples={examples}",
                ]
            )
        field_lines.append("")
    _write_markdown(dataset_dir / "field-dictionary.md", f"Field Dictionary - {dataset_slug}", field_lines)

    quality_lines = [
        f"- Dataset: `{dataset_slug}`",
        f"- Quality level: `{quality.get('quality_level', 'unknown')}`",
        "",
        "## Findings",
        "",
    ]
    if quality.get("warnings"):
        quality_lines.extend(f"- {warning}" for warning in quality["warnings"])
    else:
        quality_lines.append("- No major warnings were detected by the automated quality pass.")
    if dataset_warnings:
        quality_lines.extend(f"- Fact-layer registration: {warning}" for warning in dataset_warnings)
    quality_lines.extend(
        [
            "",
            "## Structured Summary",
            "",
            f"- Total rows checked: {quality.get('total_rows', 0)}",
            f"- Duplicate SKU+date+warehouse candidates: {quality.get('duplicate_sku_date_warehouse_rows', 0)}",
            f"- Missing field groups: {', '.join(quality.get('missing_field_groups', [])) or 'None'}",
        ]
    )
    _write_markdown(dataset_dir / "quality-report.md", f"Quality Report - {dataset_slug}", quality_lines)

    recipe_lines = [
        f"- Dataset: `{dataset_slug}`",
        f"- DuckDB path: `{_relative(DUCKDB_PATH)}`",
        "",
        "## Query Recipes",
        "",
    ]
    for recipe in query_recipes:
        recipe_lines.extend(
            [
                f"### {recipe['title']}",
                "",
                "```sql",
                recipe["sql"],
                "```",
                "",
            ]
        )
    _write_markdown(dataset_dir / "query-recipes.md", f"Query Recipes - {dataset_slug}", recipe_lines)

    open_question_lines = [
        f"- Dataset: `{dataset_slug}`",
        "",
        "## Open Questions",
        "",
    ]
    if quality.get("missing_field_groups"):
        open_question_lines.extend(
            f"- Confirm business meaning and source mapping for missing field group `{field_group}`."
            for field_group in quality["missing_field_groups"]
        )
    if quality.get("warnings"):
        open_question_lines.extend(f"- Review: {warning}" for warning in quality["warnings"])
    if dataset_warnings:
        open_question_lines.extend(f"- Repair or regenerate missing chunk references: {warning}" for warning in dataset_warnings)
    if not quality.get("warnings") and not quality.get("missing_field_groups"):
        open_question_lines.append("- No immediate blockers detected. Confirm refresh cadence and ownership manually.")
    _write_markdown(dataset_dir / "open-questions.md", f"Open Questions - {dataset_slug}", open_question_lines)

    for sheet in sheet_views:
        sheet_lines = [
            f"- Source file: `{_relative(source_path)}`",
            f"- Sheet name: `{sheet['sheet']}`",
            f"- Rows: {sheet['rows']}",
            f"- Available rows from current chunk files: {sheet['available_rows_from_chunks']}",
            f"- Columns: {sheet['columns']}",
            f"- Snapshot date: {sheet.get('snapshot_date') or 'unresolved'}",
            f"- Parquet: `{sheet['parquet_path']}`",
            f"- DuckDB raw view: `datasets.{sheet['raw_view_name']}`",
            f"- Business meaning: {sheet['business_meaning']}",
            f"- Candidate keys: {', '.join(sheet['candidate_keys'])}",
            "",
            "## Key Fields",
            "",
        ]
        if sheet["missing_chunk_paths"]:
            sheet_lines.extend(["## Missing Chunks", ""])
            sheet_lines.extend(f"- `{path}`" for path in sheet["missing_chunk_paths"])
            sheet_lines.append("")
        for profile in sheet["field_profiles"]:
            if profile["mapped_group"] or profile["semantic_type"] != "text":
                examples = ", ".join(f"`{value}`" for value in profile["sample_values"]) or "No sample values"
                sheet_lines.append(
                    f"- `{profile['field']}`: type=`{profile['semantic_type']}` group=`{profile['mapped_group'] or 'unmapped'}` examples={examples}"
                )
        if sheet["sample_rows"]:
            sheet_lines.extend(["", "## Sample Rows", ""])
            for row in sheet["sample_rows"]:
                sheet_lines.append(f"- `{json.dumps(row, ensure_ascii=False)}`")
        _write_markdown(dataset_dir / f"sheet-{sheet['sheet_slug']}.md", f"Sheet - {sheet['sheet']}", sheet_lines)

    return {
        "overview": _relative(dataset_dir / "overview.md"),
        "field_dictionary": _relative(dataset_dir / "field-dictionary.md"),
        "quality_report": _relative(dataset_dir / "quality-report.md"),
        "query_recipes": _relative(dataset_dir / "query-recipes.md"),
        "open_questions": _relative(dataset_dir / "open-questions.md"),
    }


def register_large_excel_dataset(manifest_path: str, quality_report_path: str = "") -> dict[str, Any]:
    """Create the fact layer artifacts for one processed large Excel dataset."""
    _ensure_dirs()
    manifest_target = Path(manifest_path)
    if not manifest_target.is_absolute():
        manifest_target = WAREHOUSE_DIR / manifest_path
    manifest_target = _safe_under(manifest_target, [WAREHOUSE_DIR, DATA_DIR])
    manifest = _load_json(manifest_target)

    if quality_report_path:
        quality_target = Path(quality_report_path)
        if not quality_target.is_absolute():
            quality_target = WAREHOUSE_DIR / quality_report_path
        quality_target = _safe_under(quality_target, [WAREHOUSE_DIR, DATA_DIR])
    else:
        quality_target = manifest_target.parent / "quality_report.json"
    quality = _load_json(quality_target) if quality_target.exists() else {}

    source_path = Path(str(manifest.get("source", "")))
    if not source_path.is_absolute():
        source_path = DATA_DIR / source_path
    source_path = source_path.resolve()
    dataset_slug = _slugify(source_path.stem or manifest_target.parent.name)
    dataset_dir = _safe_under(DATASET_ROOT / dataset_slug, [DATASET_ROOT])
    parquet_dir = dataset_dir / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)

    if not duckdb_installed():
        return {
            "status": "skipped",
            "dataset_slug": dataset_slug,
            "reason": "duckdb not installed",
            "next_action": "Install dependencies from requirements.txt to enable the fact layer.",
        }

    registry = _load_registry()
    conn = _connect()
    sheet_views: list[dict[str, Any]] = []
    mart_views: list[dict[str, str]] = []
    dataset_warnings: list[str] = []

    for sheet in manifest.get("sheets", []):
        if sheet.get("status") != "processed":
            continue
        sheet_name = str(sheet.get("sheet", "sheet"))
        sheet_slug = _slugify(sheet_name, "sheet")
        snapshot_date = _infer_snapshot_date(sheet_name, source_path)
        headers = [str(item) for item in sheet.get("headers", [])]
        chunk_paths, missing_paths, available_rows = _sheet_chunk_paths(manifest, sheet_name)
        if missing_paths:
            dataset_warnings.append(
                f"Sheet `{sheet_name}` is missing {len(missing_paths)} chunk file(s): {', '.join(missing_paths[:5])}"
            )
        if not chunk_paths:
            dataset_warnings.append(f"Sheet `{sheet_name}` has no available chunk files and was skipped during fact-layer registration.")
            continue
        parquet_path = _safe_under(parquet_dir / f"{sheet_slug}.parquet", [dataset_dir])
        _build_parquet_for_sheet(conn, chunk_paths, parquet_path)
        raw_view_name = _register_raw_sheet_view(conn, dataset_slug, sheet_slug, parquet_path)
        sample_rows = _sample_rows(conn, "datasets", raw_view_name, limit=5)
        profiles = _field_profiles(headers, sample_rows)
        sheet_record = {
            "sheet": sheet_name,
            "sheet_slug": sheet_slug,
            "rows": int(sheet.get("rows", 0) or 0),
            "available_rows_from_chunks": available_rows,
            "columns": int(sheet.get("columns", 0) or len(headers)),
            "headers": headers,
            "parquet_path": _relative(parquet_path),
            "raw_view_name": raw_view_name,
            "snapshot_date": snapshot_date,
            "candidate_keys": _candidate_keys(headers),
            "business_meaning": _business_meaning(sheet_name, headers),
            "field_profiles": profiles,
            "sample_rows": sample_rows,
            "missing_chunk_paths": missing_paths,
        }
        sheet_views.append(sheet_record)
        mart_views.extend(_build_sheet_marts(conn, dataset_slug, sheet_slug, headers, raw_view_name, snapshot_date=snapshot_date))

    dataset_record = {
        "dataset_slug": dataset_slug,
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(source_path),
        "relative_source": manifest.get("relative_source") or _relative(source_path),
        "manifest_path": str(manifest_target),
        "quality_report_path": str(quality_target),
        "duckdb_path": str(DUCKDB_PATH),
        "sheet_views": sheet_views,
        "mart_views": mart_views,
        "semantic_views": [],
        "derived_exports": [],
        "warnings": dataset_warnings,
    }

    registry.setdefault("datasets", {})[dataset_slug] = dataset_record
    _refresh_global_marts(conn, registry)
    semantic_assets = _materialize_semantic_assets(conn, dataset_record)
    dataset_record["semantic_views"] = _dedupe_view_entries(semantic_assets.get("semantic_views", []))
    dataset_record["derived_exports"] = list(semantic_assets.get("derived_exports", []))
    dataset_record["mart_views"] = _dedupe_view_entries(dataset_record["mart_views"] + semantic_assets.get("additional_mart_views", []))
    dataset_record["warnings"] = dataset_warnings + semantic_assets.get("warnings", [])
    registry["datasets"][dataset_slug] = dataset_record
    _refresh_global_marts(conn, registry)
    _refresh_global_semantic_views(conn, registry)
    wiki_pages = _build_dataset_wiki(
        dataset_slug,
        source_path,
        manifest,
        quality,
        sheet_views,
        dataset_record["mart_views"],
        dataset_record["warnings"],
    )
    dataset_record["wiki_pages"] = wiki_pages
    dataset_record["query_recipes"] = _dataset_query_recipes(sheet_views, dataset_record["mart_views"] + dataset_record["semantic_views"])
    registry["datasets"][dataset_slug] = dataset_record
    _save_registry(registry)
    conn.close()
    return dataset_record


def register_structured_file_dataset(path: str) -> dict[str, Any]:
    """Register a standard CSV/TSV structured file into the DuckDB fact layer."""
    _ensure_dirs()
    source_path = Path(path)
    if not source_path.is_absolute():
        source_path = DATA_DIR / path
    source_path = _safe_under(source_path, [DATA_DIR, CLEANED_DIR])
    if source_path.suffix.lower() not in SUPPORTED_STRUCTURED_SUFFIXES:
        raise ValueError(f"Unsupported structured file for fact-layer registration: {source_path.name}")
    headers = _headers_from_structured_file(source_path)
    if not headers:
        raise ValueError(f"No readable header row found in {source_path}")

    dataset_slug = _slugify(source_path.stem or source_path.name)
    dataset_dir = _safe_under(DATASET_ROOT / dataset_slug, [DATASET_ROOT])
    parquet_dir = dataset_dir / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)

    if not duckdb_installed():
        return {
            "status": "skipped",
            "dataset_slug": dataset_slug,
            "reason": "duckdb not installed",
            "next_action": "Install dependencies from requirements.txt to enable the fact layer.",
        }

    registry = _load_registry()
    conn = _connect()
    sheet_name = source_path.stem
    sheet_slug = _slugify(sheet_name, "sheet")
    parquet_path = _safe_under(parquet_dir / f"{sheet_slug}.parquet", [dataset_dir])
    _build_parquet_for_single_file(conn, source_path, parquet_path)
    raw_view_name = f"{dataset_slug}__{sheet_slug}"
    conn.execute(
        f"""
        CREATE OR REPLACE VIEW datasets.{_quote_ident(raw_view_name)} AS
        SELECT
            {_sql_literal(source_path.name)} AS _source_file,
            {_sql_literal(sheet_name)} AS _source_sheet,
            ROW_NUMBER() OVER () AS _source_row_number,
            *
        FROM read_parquet({_sql_literal(parquet_path.as_posix())});
        """
    )
    sample_rows = _sample_rows(conn, "datasets", raw_view_name, limit=5)
    profiles = _field_profiles(headers, sample_rows)
    row_count_result = conn.execute(f"SELECT COUNT(*) FROM datasets.{_quote_ident(raw_view_name)}").fetchone()
    row_count = int(row_count_result[0]) if row_count_result else 0
    snapshot_date = _infer_snapshot_date(sheet_name, source_path)
    sheet_record = {
        "sheet": sheet_name,
        "sheet_slug": sheet_slug,
        "rows": row_count,
        "available_rows_from_chunks": row_count,
        "columns": len(headers),
        "headers": headers,
        "parquet_path": _relative(parquet_path),
        "raw_view_name": raw_view_name,
        "snapshot_date": snapshot_date,
        "candidate_keys": _candidate_keys(headers),
        "business_meaning": _business_meaning(sheet_name, headers),
        "field_profiles": profiles,
        "sample_rows": sample_rows,
        "missing_chunk_paths": [],
    }
    mart_views = _build_sheet_marts(conn, dataset_slug, sheet_slug, headers, raw_view_name, snapshot_date=snapshot_date)
    dataset_record = {
        "dataset_slug": dataset_slug,
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(source_path),
        "relative_source": _relative(source_path),
        "source_kind": "structured_file",
        "manifest_path": "",
        "quality_report_path": "",
        "duckdb_path": str(DUCKDB_PATH),
        "sheet_views": [sheet_record],
        "mart_views": mart_views,
        "semantic_views": [],
        "derived_exports": [],
        "warnings": [],
    }
    registry.setdefault("datasets", {})[dataset_slug] = dataset_record
    _refresh_global_marts(conn, registry)
    semantic_assets = _materialize_semantic_assets(conn, dataset_record)
    dataset_record["semantic_views"] = _dedupe_view_entries(semantic_assets.get("semantic_views", []))
    dataset_record["derived_exports"] = list(semantic_assets.get("derived_exports", []))
    dataset_record["mart_views"] = _dedupe_view_entries(dataset_record["mart_views"] + semantic_assets.get("additional_mart_views", []))
    dataset_record["warnings"] = list(semantic_assets.get("warnings", []))
    registry["datasets"][dataset_slug] = dataset_record
    _refresh_global_marts(conn, registry)
    _refresh_global_semantic_views(conn, registry)
    wiki_pages = _build_dataset_wiki(
        dataset_slug,
        source_path,
        {"processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "manifest_path": ""},
        {},
        [sheet_record],
        dataset_record["mart_views"],
        dataset_record["warnings"],
    )
    dataset_record["wiki_pages"] = wiki_pages
    dataset_record["query_recipes"] = _dataset_query_recipes([sheet_record], dataset_record["mart_views"] + dataset_record["semantic_views"])
    registry["datasets"][dataset_slug] = dataset_record
    _save_registry(registry)
    conn.close()
    return dataset_record


def register_connector_snapshot_dataset(path: str, connector_id: str, connector_dataset: str) -> dict[str, Any]:
    """Register a connector-produced CSV/TSV snapshot and tag its registry entry."""
    dataset_record = register_structured_file_dataset(path)
    if dataset_record.get("status") == "skipped":
        return dataset_record
    dataset_slug = str(dataset_record.get("dataset_slug", ""))
    registry = _load_registry()
    registry_record = registry.get("datasets", {}).get(dataset_slug, dataset_record)
    registry_record["source_kind"] = "connector_snapshot"
    registry_record["connector_id"] = connector_id
    registry_record["connector_dataset"] = connector_dataset
    registry_record["registry_path"] = str(REGISTRY_PATH)
    registry.setdefault("datasets", {})[dataset_slug] = registry_record
    _save_registry(registry)
    return registry_record


def register_all_large_excel_datasets(limit: int = 20) -> str:
    """Register existing large-excel manifests into the DuckDB fact layer."""
    _ensure_dirs()
    manifests = sorted((WAREHOUSE_DIR / "large_excel").rglob("manifest.json"))[:limit]
    results = []
    for manifest_path in manifests:
        try:
            results.append(
                {
                    "manifest_path": str(manifest_path),
                    "status": "success",
                    "dataset": register_large_excel_dataset(str(manifest_path)),
                }
            )
        except Exception as exc:
            results.append({"manifest_path": str(manifest_path), "status": "failed", "error": str(exc)})
    return json.dumps(
        {
            "status": "success" if not any(item.get("status") == "failed" for item in results) else "warning",
            "duckdb_path": str(DUCKDB_PATH),
            "registry_path": str(REGISTRY_PATH),
            "processed": len(results),
            "results": results,
        },
        ensure_ascii=False,
        indent=2,
    )


def register_all_structured_datasets(limit: int = 200) -> str:
    """Register all standard CSV/TSV data files into the DuckDB fact layer."""
    files = _iter_standard_structured_files(limit=limit)
    results = []
    for source_path in files:
        try:
            results.append({"path": str(source_path), "status": "success", "dataset": register_structured_file_dataset(str(source_path))})
        except Exception as exc:
            results.append({"path": str(source_path), "status": "failed", "error": str(exc)})
    return json.dumps(
        {
            "status": "success" if not any(item.get("status") == "failed" for item in results) else "warning",
            "duckdb_path": str(DUCKDB_PATH),
            "registry_path": str(REGISTRY_PATH),
            "processed": len(results),
            "results": results,
        },
        ensure_ascii=False,
        indent=2,
    )


def audit_fact_source_readiness(limit: int = 200) -> str:
    """Inspect local structured files and report which fact marts they can populate."""
    files = _iter_standard_structured_files(limit=limit)
    reports = []
    ads_ready = False
    finance_ready = False
    for source_path in files:
        headers = _headers_from_structured_file(source_path)
        candidate_marts = _mart_candidates_from_headers(headers)
        report = {
            "path": _relative(source_path),
            "headers": headers,
            "candidate_marts": candidate_marts,
            "matched_groups": sorted(group for group in FIELD_GROUP_ALIASES if _find_field(headers, group)),
        }
        if "fact_ads_daily" in candidate_marts:
            ads_ready = True
        if "fact_finance_daily" in candidate_marts:
            finance_ready = True
        reports.append(report)
    return json.dumps(
        {
            "duckdb_path": str(DUCKDB_PATH),
            "registry_path": str(REGISTRY_PATH),
            "ads_ready": ads_ready,
            "finance_ready": finance_ready,
            "files": reports,
            "guidance": {
                "ads_required_groups": ["date", "sku", "product_name", "channel", "ad_spend"],
                "ads_optional_groups": ["warehouse", "acos", "roas"],
                "finance_required_groups": ["date", "sku", "product_name", "revenue"],
                "finance_optional_groups": ["warehouse", "channel", "cost", "gross_profit", "cash"],
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def register_all_fact_datasets(large_excel_limit: int = 20, structured_limit: int = 200) -> str:
    """Register both historical large-excel manifests and standard structured files."""
    _save_registry({"schema": "a2a_dataset_registry_v1", "updated_at": "", "datasets": {}})
    large_excel = json.loads(register_all_large_excel_datasets(limit=large_excel_limit))
    structured = json.loads(register_all_structured_datasets(limit=structured_limit))
    status = "success"
    if large_excel.get("status") != "success" or structured.get("status") != "success":
        status = "warning"
    return json.dumps(
        {
            "status": status,
            "duckdb_path": str(DUCKDB_PATH),
            "registry_path": str(REGISTRY_PATH),
            "large_excel": large_excel,
            "structured": structured,
        },
        ensure_ascii=False,
        indent=2,
    )


def list_registered_datasets() -> str:
    """List datasets registered in the DuckDB fact layer."""
    registry = _load_registry()
    rows = []
    for dataset in registry.get("datasets", {}).values():
        rows.append(
            {
                "dataset_slug": dataset.get("dataset_slug", ""),
                "source": dataset.get("relative_source", dataset.get("source", "")),
                "registered_at": dataset.get("registered_at", ""),
                "sheets": len(dataset.get("sheet_views", [])),
                "mart_views": sorted({item.get("category", "") for item in dataset.get("mart_views", []) if item.get("category")}),
                "semantic_views": sorted({item.get("category", "") for item in dataset.get("semantic_views", []) if item.get("category")}),
                "derived_exports": dataset.get("derived_exports", []),
                "overview_page": dataset.get("wiki_pages", {}).get("overview", ""),
            }
        )
    return json.dumps({"registry_path": str(REGISTRY_PATH), "duckdb_path": str(DUCKDB_PATH), "datasets": rows}, ensure_ascii=False, indent=2)


def list_fact_tables() -> str:
    """List DuckDB dataset and mart views."""
    if not duckdb_installed():
        return json.dumps(
            {"available": False, "reason": "duckdb not installed", "duckdb_path": str(DUCKDB_PATH)},
            ensure_ascii=False,
            indent=2,
        )
    conn = _connect(read_only=True)
    cursor = conn.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('datasets', 'marts')
        ORDER BY table_schema, table_name;
        """
    )
    tables = [{"schema": row[0], "name": row[1]} for row in cursor.fetchall()]
    conn.close()
    return json.dumps({"available": True, "duckdb_path": str(DUCKDB_PATH), "tables": tables}, ensure_ascii=False, indent=2)


def _quote_qualified_table(schema: str, name: str) -> str:
    return f"{schema}.{_quote_ident(name)}"


def _extract_referenced_table_names(sql: str) -> set[str]:
    names: set[str] = set()
    pattern = re.compile(
        r"\b(?:from|join)\s+((?:[A-Za-z_][\w]*\.)?(?:\"[^\"]+\"|[\w\u4e00-\u9fff][\w\u4e00-\u9fff_-]*))",
        re.IGNORECASE,
    )
    for match in pattern.finditer(sql):
        raw = match.group(1).strip()
        parts = [part.strip().strip('"') for part in raw.split(".") if part.strip()]
        names.update(part for part in parts if part)
        if parts:
            names.add(".".join(parts))
    return names


def _registered_table_suggestions(sql: str, limit: int = 20) -> list[dict[str, Any]]:
    references = _extract_referenced_table_names(sql)
    if not references:
        return []
    registry = _load_registry()
    suggestions: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for dataset in registry.get("datasets", {}).values():
        dataset_slug = str(dataset.get("dataset_slug", "")).strip()
        if not dataset_slug:
            continue
        if dataset_slug not in references and not any(ref and (ref in dataset_slug or dataset_slug in ref) for ref in references):
            continue
        for sheet in dataset.get("sheet_views", []):
            table_name = str(sheet.get("raw_view_name", "")).strip()
            if not table_name:
                continue
            key = ("datasets", table_name)
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(
                {
                    "schema": "datasets",
                    "name": table_name,
                    "qualified_name": _quote_qualified_table("datasets", table_name),
                    "dataset_slug": dataset_slug,
                    "source": "raw_sheet_view",
                    "sheet": sheet.get("sheet", ""),
                }
            )
            if len(suggestions) >= limit:
                return suggestions
        for view_group in ("semantic_views", "mart_views"):
            for view in dataset.get(view_group, []):
                table_name = str(view.get("view_name", "")).strip()
                if not table_name:
                    continue
                key = ("marts", table_name)
                if key in seen:
                    continue
                seen.add(key)
                suggestions.append(
                    {
                        "schema": "marts",
                        "name": table_name,
                        "qualified_name": _quote_qualified_table("marts", table_name),
                        "dataset_slug": dataset_slug,
                        "source": view_group,
                        "category": view.get("category", ""),
                    }
                )
                if len(suggestions) >= limit:
                    return suggestions
    return suggestions


def _list_fact_table_rows(conn: Any) -> list[dict[str, str]]:
    cursor = conn.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('datasets', 'marts')
        ORDER BY table_schema, table_name
        LIMIT 50;
        """
    )
    return [{"schema": row[0], "name": row[1], "qualified_name": _quote_qualified_table(row[0], row[1])} for row in cursor.fetchall()]


def _format_fact_query_error(sql: str, error: Exception, conn: Any | None = None) -> dict[str, Any]:
    available_examples: list[dict[str, str]] = []
    if conn is not None:
        try:
            available_examples = _list_fact_table_rows(conn)
        except Exception:
            available_examples = []
    return {
        "available": False,
        "error_type": "duckdb_query_failed",
        "reason": str(error),
        "duckdb_path": str(DUCKDB_PATH),
        "row_count": 0,
        "rows": [],
        "sql": sql,
        "suggested_tables": _registered_table_suggestions(sql),
        "available_table_examples": available_examples,
        "recovery_hint": "Use tables listed by list_fact_tables. Dataset slugs are registry names, not DuckDB table names; query datasets.<raw_view_name> or marts.<view_name>.",
    }


def query_fact_layer(sql: str, limit: int = 200) -> str:
    """Run a read-only DuckDB query against the fact layer."""
    _validate_safe_fact_sql(sql)
    limit_warning = ""
    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("query_fact_layer limit must be an integer.") from exc
    if limit <= 0:
        limit = 200
    if limit > 1000:
        limit = 1000
        limit_warning = "limit clamped to 1000"
    if not duckdb_installed():
        return json.dumps(
            {"available": False, "reason": "duckdb not installed", "duckdb_path": str(DUCKDB_PATH)},
            ensure_ascii=False,
            indent=2,
        )
    conn = None
    try:
        conn = _connect(read_only=True)
        wrapped = f"SELECT * FROM ({sql}) AS a2a_fact_query LIMIT {int(limit)}"
        cursor = conn.execute(wrapped)
        columns = [item[0] for item in cursor.description]
        rows = [{column: _json_safe(value) for column, value in zip(columns, raw_row)} for raw_row in cursor.fetchall()]
        payload: dict[str, Any] = {"duckdb_path": str(DUCKDB_PATH), "row_count": len(rows), "rows": rows, "limit": limit}
        if limit_warning:
            payload["warning"] = limit_warning
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps(_format_fact_query_error(sql, exc, conn), ensure_ascii=False, indent=2)
    finally:
        if conn is not None:
            conn.close()
