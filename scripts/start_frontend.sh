#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

PORT="${A2A_FRONTEND_PORT:-3000}"
HOST_NAME="${A2A_FRONTEND_HOST:-127.0.0.1}"
STARTUP_TIMEOUT_SECONDS="${A2A_FRONTEND_STARTUP_TIMEOUT_SECONDS:-45}"
FRONTEND_ROOT="${PROJECT_ROOT}/agent-chat-ui"
NEXT_BIN="${FRONTEND_ROOT}/node_modules/next/dist/bin/next"
NODE_BIN="${A2A_NODE_BIN:-}"
SCREEN_SESSION="${A2A_FRONTEND_SCREEN_SESSION:-a2a-frontend}"
CLEAN_NEXT_CACHE="${A2A_FRONTEND_CLEAN_NEXT_CACHE:-1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --host|--hostname) HOST_NAME="$2"; shift 2 ;;
    --timeout) STARTUP_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --no-clean-next-cache) CLEAN_NEXT_CACHE="0"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${NODE_BIN}" ]]; then
  NODE_BIN="$(command -v node || true)"
fi

if [[ ! -d "${FRONTEND_ROOT}" ]]; then
  echo "Frontend directory not found: ${FRONTEND_ROOT}" >&2
  exit 1
fi

if [[ -z "${NODE_BIN}" ]]; then
  echo "Node runtime not found. Set A2A_NODE_BIN or ensure node is on PATH." >&2
  exit 1
fi

if [[ ! -f "${NEXT_BIN}" ]]; then
  echo "Next.js binary not found: ${NEXT_BIN}" >&2
  exit 1
fi

"${SCRIPT_DIR}/stop_frontend.sh" --port "${PORT}" >/dev/null
rm -f "${PROJECT_ROOT}/frontend.out.log" "${PROJECT_ROOT}/frontend.err.log"
if [[ "${CLEAN_NEXT_CACHE}" != "0" ]]; then
  rm -rf "${FRONTEND_ROOT}/.next"
fi

if command -v screen >/dev/null 2>&1; then
  FRONTEND_COMMAND=$(
    printf "cd %q && exec %q %q dev --hostname %q --port %q > %q 2> %q" \
      "${FRONTEND_ROOT}" \
      "${NODE_BIN}" \
      "${NEXT_BIN}" \
      "${HOST_NAME}" \
      "${PORT}" \
      "${PROJECT_ROOT}/frontend.out.log" \
      "${PROJECT_ROOT}/frontend.err.log"
  )
  screen -dmS "${SCREEN_SESSION}" /bin/bash -lc "${FRONTEND_COMMAND}"
else
  (
    cd "${FRONTEND_ROOT}"
    nohup "${NODE_BIN}" "${NEXT_BIN}" dev --hostname "${HOST_NAME}" --port "${PORT}" \
      >"${PROJECT_ROOT}/frontend.out.log" 2>"${PROJECT_ROOT}/frontend.err.log" &
    echo $! > "${RUNTIME_DIR}/frontend.pid"
  )
fi

if ! wait_for_http "http://${HOST_NAME}:${PORT}" "${STARTUP_TIMEOUT_SECONDS}"; then
  echo "Frontend did not start listening on port ${PORT} within ${STARTUP_TIMEOUT_SECONDS} seconds." >&2
  tail_if_exists "${PROJECT_ROOT}/frontend.err.log" 80 >&2
  exit 1
fi

FRONTEND_PID="$(port_pids "${PORT}" | head -n 1 || true)"
if [[ -n "${FRONTEND_PID}" ]]; then
  echo "${FRONTEND_PID}" > "${RUNTIME_DIR}/frontend.pid"
fi

echo "Frontend is listening on http://${HOST_NAME}:${PORT}"
