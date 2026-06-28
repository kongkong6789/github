#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

PORT="${LIGHTRAG_PORT:-9621}"
SCREEN_SESSION="${A2A_LIGHTRAG_SCREEN_SESSION:-a2a-lightrag}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if command -v screen >/dev/null 2>&1; then
  screen -S "${SCREEN_SESSION}" -X quit >/dev/null 2>&1 || true
fi
kill_pid_file "${RUNTIME_DIR}/lightrag.pid"
kill_port_processes "${PORT}"

if command -v pkill >/dev/null 2>&1; then
  pkill -f "lightrag-server" 2>/dev/null || true
fi

echo "Stopped LightRAG server processes when present."
