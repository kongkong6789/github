#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

PYTHON_BIN="$(find_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python runtime not found." >&2
  exit 1
fi

(
  cd "${PROJECT_ROOT}"
  "${PYTHON_BIN}" -c "from src.a2a_ecommerce_demo.fact_layer_tools import register_all_fact_datasets; print(register_all_fact_datasets())"
)
