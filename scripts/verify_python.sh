#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

PYTHON_BIN="$(find_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "Python runtime not found." >&2
  exit 1
fi

RUFF_BIN="$(find_venv_exec ruff || true)"
PYRIGHT_BIN="$(find_venv_exec pyright || true)"

if [[ -z "${RUFF_BIN}" ]]; then
  echo "Ruff is not installed. Install requirements-dev.txt before running verification." >&2
  exit 1
fi
if [[ -z "${PYRIGHT_BIN}" ]]; then
  echo "Pyright is not installed. Install requirements-dev.txt before running verification." >&2
  exit 1
fi

(
  cd "${PROJECT_ROOT}"
  "${PYTHON_BIN}" -m compileall src tests run_demo.py
  "${PYTHON_BIN}" -m unittest discover -s tests
  "${RUFF_BIN}" check src tests run_demo.py
  "${PYRIGHT_BIN}"
)
