#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)"

if [[ -f "${PROJECT_ROOT}/scripts/common.sh" ]]; then
  # Reuse the project dotenv parser so frontend npm scripts honor A2A_NODE_BIN.
  # shellcheck source=/dev/null
  source "${PROJECT_ROOT}/scripts/common.sh"
  load_dotenv
fi

if [[ -n "${A2A_NODE_BIN:-}" && -x "${A2A_NODE_BIN}" ]]; then
  export PATH="$(dirname "${A2A_NODE_BIN}"):${PATH}"
fi

exec "$@"
