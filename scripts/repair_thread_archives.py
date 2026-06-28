from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.a2a_ecommerce_demo.thread_repair_tools import repair_thread_archives


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair local A2A thread archives safely.")
    parser.add_argument("--write", action="store_true", help="Write repaired local thread archives.")
    parser.add_argument("--confirm", action="store_true", help="Required with --write.")
    parser.add_argument("--max-messages", type=int, default=80)
    parser.add_argument("--max-text-length", type=int, default=12_000)
    args = parser.parse_args()

    result = repair_thread_archives(
        dry_run=not args.write,
        confirm=args.confirm,
        max_messages=args.max_messages,
        max_text_length=args.max_text_length,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"dry_run", "success"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
