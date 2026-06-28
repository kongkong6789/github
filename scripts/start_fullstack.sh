#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

BACKEND_PORT="${A2A_BACKEND_PORT:-2024}"
FRONTEND_PORT="${A2A_FRONTEND_PORT:-3000}"
HOST_NAME="${A2A_HOSTNAME:-127.0.0.1}"
OPEN_BROWSER="${A2A_OPEN_BROWSER:-true}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-port) BACKEND_PORT="$2"; shift 2 ;;
    --frontend-port) FRONTEND_PORT="$2"; shift 2 ;;
    --host|--hostname) HOST_NAME="$2"; shift 2 ;;
    --no-open) OPEN_BROWSER="false"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

"${SCRIPT_DIR}/start_backend.sh" --port "${BACKEND_PORT}" --host "${HOST_NAME}"
"${SCRIPT_DIR}/start_frontend.sh" --port "${FRONTEND_PORT}" --host "${HOST_NAME}"

if [[ "${OPEN_BROWSER}" == "true" ]] && command -v open >/dev/null 2>&1; then
  open "http://${HOST_NAME}:${FRONTEND_PORT}" >/dev/null 2>&1 || true
fi

echo "A2A stack startup requested. Frontend URL: http://${HOST_NAME}:${FRONTEND_PORT}"
