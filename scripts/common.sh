#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
RUNTIME_DIR="${A2A_RUNTIME_DIR:-${PROJECT_ROOT}/.runtime}"

mkdir -p "${RUNTIME_DIR}"

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

strip_wrapping_quotes() {
  local value="$1"
  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "${value}"
}

expand_env_value() {
  local value="$1"
  local expanded="${value}"
  local name
  local replacement
  while [[ "${expanded}" =~ \$\{([A-Za-z_][A-Za-z0-9_]*)\} ]]; do
    name="${BASH_REMATCH[1]}"
    replacement="${!name-}"
    expanded="${expanded//\$\{${name}\}/${replacement}}"
  done
  printf '%s' "${expanded}"
}

load_dotenv() {
  local env_file="${1:-${PROJECT_ROOT}/.env}"
  [[ -f "${env_file}" ]] || return 0

  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="$(trim "${line}")"
    [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]] && continue
    local name="${line%%=*}"
    local value="${line#*=}"
    name="$(trim "${name}")"
    if [[ ! "${name}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      echo "Ignoring invalid dotenv key: ${name}" >&2
      continue
    fi
    value="$(expand_env_value "$(strip_wrapping_quotes "$(trim "${value}")")")"
    export "${name}=${value}"
  done < "${env_file}"
}

find_venv_exec() {
  local name="$1"
  local unix_path="${PROJECT_ROOT}/.venv/bin/${name}"
  local windows_exe_path="${PROJECT_ROOT}/.venv/Scripts/${name}.exe"
  local windows_path="${PROJECT_ROOT}/.venv/Scripts/${name}"

  if [[ -x "${unix_path}" ]]; then
    printf '%s' "${unix_path}"
  elif [[ -f "${windows_exe_path}" ]]; then
    printf '%s' "${windows_exe_path}"
  elif [[ -f "${windows_path}" ]]; then
    printf '%s' "${windows_path}"
  else
    return 1
  fi
}

find_python() {
  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    printf '%s' "${PROJECT_ROOT}/.venv/bin/python"
  elif [[ -f "${PROJECT_ROOT}/.venv/Scripts/python.exe" ]]; then
    printf '%s' "${PROJECT_ROOT}/.venv/Scripts/python.exe"
  elif command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    return 1
  fi
}

require_command() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "Required command not found: ${name}" >&2
    exit 1
  fi
}

wait_for_http() {
  local url="$1"
  local timeout_seconds="${2:-45}"
  local deadline=$((SECONDS + timeout_seconds))

  while (( SECONDS < deadline )); do
    if curl -fsS --max-time 5 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  return 1
}

port_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:${port}" 2>/dev/null || true
  fi
}

kill_pid_file() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(<"${pid_file}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      sleep 1
      kill -9 "${pid}" 2>/dev/null || true
    fi
    rm -f "${pid_file}"
  fi
}

kill_port_processes() {
  local port="$1"
  local pids
  pids="$(port_pids "${port}")"
  if [[ -n "${pids}" ]]; then
    # shellcheck disable=SC2086
    kill ${pids} 2>/dev/null || true
    sleep 1
    # shellcheck disable=SC2086
    kill -9 ${pids} 2>/dev/null || true
  fi
}

tail_if_exists() {
  local file="$1"
  local lines="${2:-80}"
  if [[ -f "${file}" ]]; then
    tail -n "${lines}" "${file}"
  fi
}
