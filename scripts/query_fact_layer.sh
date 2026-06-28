#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

SQL=""
LIMIT=50

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sql) SQL="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${SQL}" ]]; then
  echo "Missing required argument: --sql" >&2
  exit 1
fi

PYTHON_BIN="$(find_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python runtime not found." >&2
  exit 1
fi

(
  cd "${PROJECT_ROOT}"
  A2A_QUERY_SQL="${SQL}" A2A_QUERY_LIMIT="${LIMIT}" "${PYTHON_BIN}" - <<'PY'
import os
import sys

from src.a2a_ecommerce_demo.fact_layer_tools import query_fact_layer

try:
    limit = int(os.environ.get("A2A_QUERY_LIMIT", "50"))
except ValueError:
    print("A2A_QUERY_LIMIT must be an integer.", file=sys.stderr)
    raise SystemExit(2)

print(query_fact_layer(os.environ["A2A_QUERY_SQL"], limit=limit))
PY
)
