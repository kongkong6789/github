"""
Refresh bundled master-data caches for faster skill operation.

This script intentionally stores only shared master data under data/cache/.
It does not touch data/profile.json or data/experiences/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helpers.local_store import save_cached_master_data
from modules.channel import query_all_channels
from modules.goods import query_all_goods
from modules.user import query_all_users
from modules.warehouse import query_all_warehouses


SUMMARY_PATH = PROJECT_ROOT / "data/cache/_refresh_summary.json"
MIN_EXPECTED_COUNTS = {
    "warehouses": 200,
    "channels": 200,
    "goods": 10000,
    "users": 100,
}


def _refresh(name: str, fetcher):
    print(f"Refreshing {name} ...", flush=True)
    items = fetcher()
    minimum = MIN_EXPECTED_COUNTS.get(name, 0)
    if minimum and len(items) < minimum:
        raise RuntimeError(
            f"{name} refresh returned only {len(items)} records; expected at least {minimum}. "
            "Refusing to overwrite the bundled full cache with a partial result."
        )
    save_cached_master_data(name, items)
    print(f"  {name}: {len(items)} records", flush=True)
    return {"name": name, "count": len(items)}


def main():
    summary = [
        _refresh("warehouses", query_all_warehouses),
        _refresh("channels", query_all_channels),
        _refresh("goods", query_all_goods),
        _refresh("users", query_all_users),
    ]
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {SUMMARY_PATH}", flush=True)


if __name__ == "__main__":
    main()
