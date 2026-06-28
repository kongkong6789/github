#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"

PORT="${A2A_FRONTEND_PORT:-3000}"
SCREEN_SESSION="${A2A_FRONTEND_SCREEN_SESSION:-a2a-frontend}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if command -v screen >/dev/null 2>&1; then
  screen -S "${SCREEN_SESSION}" -X quit >/dev/null 2>&1 || true
fi
kill_pid_file "${RUNTIME_DIR}/frontend.pid"
kill_port_processes "${PORT}"

echo "Stopped frontend processes on port ${PORT} when present."
