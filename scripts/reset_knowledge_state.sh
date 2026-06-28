#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

clear_directory_contents() {
  local target="$1"
  shift || true
  local excludes=("$@")

  mkdir -p "${target}"
  shopt -s nullglob dotglob
  local item name skip
  for item in "${target}"/*; do
    name="$(basename "${item}")"
    skip=0
    for excluded in "${excludes[@]}"; do
      if [[ "${name}" == "${excluded}" ]]; then
        skip=1
        break
      fi
    done
    if [[ "${skip}" -eq 0 ]]; then
      rm -rf -- "${item}"
    fi
  done
  shopt -u nullglob dotglob
}

"${SCRIPT_DIR}/stop_backend.sh" || true
"${SCRIPT_DIR}/stop_lightrag_server.sh" || true

clear_directory_contents "${PROJECT_ROOT}/.langgraph_api"
clear_directory_contents "${PROJECT_ROOT}/data/tasks"
clear_directory_contents "${PROJECT_ROOT}/data/lightrag"
clear_directory_contents "${PROJECT_ROOT}/data/lightrag_inputs"
clear_directory_contents "${PROJECT_ROOT}/data/lightrag_official"
clear_directory_contents "${PROJECT_ROOT}/wiki" ".obsidian"

rm -f "${PROJECT_ROOT}/wiki/index.md"

echo "Cleared Obsidian wiki content, LightRAG data, and conversation history."
