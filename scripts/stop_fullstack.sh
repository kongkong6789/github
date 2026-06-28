#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"

BACKEND_PORT="${A2A_BACKEND_PORT:-2024}"
FRONTEND_PORT="${A2A_FRONTEND_PORT:-3000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-port) BACKEND_PORT="$2"; shift 2 ;;
    --frontend-port) FRONTEND_PORT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

"${SCRIPT_DIR}/stop_frontend.sh" --port "${FRONTEND_PORT}"
"${SCRIPT_DIR}/stop_backend.sh" --port "${BACKEND_PORT}"

echo "A2A frontend and backend stop requested."
