#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

WORKING_DIR="${WORKING_DIR:-${PROJECT_ROOT}/data/lightrag_official}"
INPUT_DIR="${INPUT_DIR:-${PROJECT_ROOT}/data/lightrag_inputs}"
LOG_PATH="${PROJECT_ROOT}/lightrag-server.log"
ERR_PATH="${PROJECT_ROOT}/lightrag-server.err.log"
SERVER_BIN="$(find_venv_exec lightrag-server || true)"
SCREEN_SESSION="${A2A_LIGHTRAG_SCREEN_SESSION:-a2a-lightrag}"
STARTUP_TIMEOUT_SECONDS="${A2A_LIGHTRAG_STARTUP_TIMEOUT_SECONDS:-45}"

if [[ -z "${SERVER_BIN}" ]]; then
  echo "lightrag-server executable not found under ${PROJECT_ROOT}/.venv" >&2
  exit 1
fi

mkdir -p "${WORKING_DIR}" "${INPUT_DIR}"

export LIGHTRAG_HOST="${LIGHTRAG_HOST:-127.0.0.1}"
export LIGHTRAG_PORT="${LIGHTRAG_PORT:-9621}"
export TIMEOUT="${LIGHTRAG_TIMEOUT:-900}"
export WORKING_DIR
export INPUT_DIR
export LLM_BINDING="${LLM_BINDING:-openai}"
export LLM_MODEL="${LLM_MODEL:-${OPENAI_MODEL:-gpt-4.1-mini}}"
export LLM_BINDING_HOST="${LLM_BINDING_HOST:-${OPENAI_BASE_URL:-https://api.openai.com/v1}}"
export LLM_BINDING_API_KEY="${LLM_BINDING_API_KEY:-${OPENAI_API_KEY:-}}"
export EMBEDDING_BINDING="${EMBEDDING_BINDING:-openai}"
export EMBEDDING_BINDING_HOST="${EMBEDDING_BINDING_HOST:-${OPENAI_BASE_URL:-https://api.openai.com/v1}}"
export EMBEDDING_BINDING_API_KEY="${EMBEDDING_BINDING_API_KEY:-${OPENAI_API_KEY:-}}"
export EMBEDDING_MODEL="${EMBEDDING_MODEL:-text-embedding-3-small}"
export EMBEDDING_DIM="${EMBEDDING_DIM:-2048}"
export EMBEDDING_MAX_TOKEN_SIZE="${EMBEDDING_MAX_TOKEN_SIZE:-8192}"
export EMBEDDING_SEND_DIM="${EMBEDDING_SEND_DIM:-false}"
export EMBEDDING_USE_BASE64="${EMBEDDING_USE_BASE64:-false}"
export A2A_LIGHTRAG_MODE="${A2A_LIGHTRAG_MODE:-official}"
export LIGHTRAG_API_URL="${LIGHTRAG_API_URL:-http://127.0.0.1:9621}"

"${SCRIPT_DIR}/stop_lightrag_server.sh" --port "${LIGHTRAG_PORT}" >/dev/null
rm -f "${LOG_PATH}" "${ERR_PATH}"

if command -v screen >/dev/null 2>&1; then
  LIGHTRAG_COMMAND=$(
    printf "cd %q && source %q && load_dotenv && exec %q > %q 2> %q" \
      "${PROJECT_ROOT}" \
      "${SCRIPT_DIR}/common.sh" \
      "${SERVER_BIN}" \
      "${LOG_PATH}" \
      "${ERR_PATH}"
  )
  screen -dmS "${SCREEN_SESSION}" /bin/bash -lc "${LIGHTRAG_COMMAND}"
else
  (
    cd "${PROJECT_ROOT}"
    nohup "${SERVER_BIN}" >"${LOG_PATH}" 2>"${ERR_PATH}" &
    echo $! > "${RUNTIME_DIR}/lightrag.pid"
  )
fi

if ! wait_for_http "${LIGHTRAG_API_URL}/documents/status_counts" "${STARTUP_TIMEOUT_SECONDS}"; then
  echo "LightRAG server did not become healthy within ${STARTUP_TIMEOUT_SECONDS} seconds." >&2
  tail_if_exists "${ERR_PATH}" 80 >&2
  exit 1
fi

LIGHTRAG_PID="$(port_pids "${LIGHTRAG_PORT}" | head -n 1 || true)"
if [[ -n "${LIGHTRAG_PID}" ]]; then
  echo "${LIGHTRAG_PID}" > "${RUNTIME_DIR}/lightrag.pid"
fi

echo "LightRAG server is healthy at ${LIGHTRAG_API_URL}"
echo "Logs: ${LOG_PATH}"
echo "Errors: ${ERR_PATH}"
