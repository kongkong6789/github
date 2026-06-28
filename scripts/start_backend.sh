#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

PORT="${A2A_BACKEND_PORT:-2024}"
HOST_NAME="${A2A_BACKEND_HOST:-127.0.0.1}"
STARTUP_TIMEOUT_SECONDS="${A2A_BACKEND_STARTUP_TIMEOUT_SECONDS:-45}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --host|--hostname) HOST_NAME="$2"; shift 2 ;;
    --timeout) STARTUP_TIMEOUT_SECONDS="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

LANGGRAPH_BIN="$(find_venv_exec langgraph || true)"
if [[ -z "${LANGGRAPH_BIN}" ]]; then
  echo "LangGraph executable not found under ${PROJECT_ROOT}/.venv" >&2
  exit 1
fi
PYTHON_BIN="$(find_python)"
SCREEN_SESSION="${A2A_BACKEND_SCREEN_SESSION:-a2a-backend}"

"${SCRIPT_DIR}/stop_backend.sh" --port "${PORT}" >/dev/null
rm -f "${PROJECT_ROOT}/langgraph-server.log" "${PROJECT_ROOT}/langgraph-server.err.log"

if command -v screen >/dev/null 2>&1; then
  BACKEND_COMMAND=$(
    printf "cd %q && source %q && load_dotenv && exec %q %q --langgraph-bin %q --host %q --port %q > %q 2> %q" \
      "${PROJECT_ROOT}" \
      "${SCRIPT_DIR}/common.sh" \
      "${PYTHON_BIN}" \
      "${SCRIPT_DIR}/run_langgraph_backend.py" \
      "${LANGGRAPH_BIN}" \
      "${HOST_NAME}" \
      "${PORT}" \
      "${PROJECT_ROOT}/langgraph-server.log" \
      "${PROJECT_ROOT}/langgraph-server.err.log"
  )
  screen -dmS "${SCREEN_SESSION}" /bin/bash -lc "${BACKEND_COMMAND}"
else
  nohup "${PYTHON_BIN}" "${SCRIPT_DIR}/run_langgraph_backend.py" \
    --langgraph-bin "${LANGGRAPH_BIN}" --host "${HOST_NAME}" --port "${PORT}" \
    >"${PROJECT_ROOT}/langgraph-server.log" 2>"${PROJECT_ROOT}/langgraph-server.err.log" &
  echo $! > "${RUNTIME_DIR}/backend.pid"
fi

if ! wait_for_http "http://${HOST_NAME}:${PORT}/ok" "${STARTUP_TIMEOUT_SECONDS}"; then
  echo "Backend did not become healthy within ${STARTUP_TIMEOUT_SECONDS} seconds." >&2
  tail_if_exists "${PROJECT_ROOT}/langgraph-server.err.log" 80 >&2
  exit 1
fi

BACKEND_PID="$(port_pids "${PORT}" | head -n 1 || true)"
if [[ -n "${BACKEND_PID}" ]]; then
  echo "${BACKEND_PID}" > "${RUNTIME_DIR}/backend.pid"
fi

echo "Backend is healthy on http://${HOST_NAME}:${PORT}"
