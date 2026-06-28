#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)"

"${SCRIPT_DIR}/verify_python.sh"
"${SCRIPT_DIR}/verify_frontend.sh"
