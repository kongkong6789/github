#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

PYTHON_BIN="$(find_python || true)"
REQUIREMENTS_FILE="${PROJECT_ROOT}/requirements-lightrag.txt"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python runtime not found." >&2
  exit 1
fi

if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
  echo "Requirements file not found: ${REQUIREMENTS_FILE}" >&2
  exit 1
fi

(
  cd "${PROJECT_ROOT}"
  "${PYTHON_BIN}" -m pip install -r "${REQUIREMENTS_FILE}"
)
