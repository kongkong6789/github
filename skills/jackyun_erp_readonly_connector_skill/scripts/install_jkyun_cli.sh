#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
cd "$PROJECT_ROOT"

python - <<'PY'
from helpers.jkyun_cli import ensure_cli_executable
print(ensure_cli_executable())
PY
