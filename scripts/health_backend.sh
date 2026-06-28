#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

PORT="${A2A_BACKEND_PORT:-2024}"
HOST_NAME="${A2A_BACKEND_HOST:-127.0.0.1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --host|--hostname) HOST_NAME="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

URL="http://${HOST_NAME}:${PORT}/ok"

if ! curl -fsS --max-time 10 "${URL}"; then
  echo
  echo "Backend health check failed for ${URL}" >&2
  tail_if_exists "${PROJECT_ROOT}/langgraph-server.err.log" 80 >&2
  exit 1
fi

