#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${ROOT}/_references"
mkdir -p "${TARGET}"

clone_or_update() {
  local name="$1"
  local url="$2"
  local dir="${TARGET}/${name}"
  if [[ -d "${dir}/.git" ]]; then
    echo "Updating ${name}..."
    git -C "${dir}" fetch --depth 1 origin
    git -C "${dir}" checkout -q main 2>/dev/null || git -C "${dir}" checkout -q master 2>/dev/null || true
    git -C "${dir}" pull --ff-only --depth 1 || true
  else
    echo "Cloning ${name}..."
    git clone --depth 1 "${url}" "${dir}"
  fi
}

clone_or_update "duckdb" "https://github.com/duckdb/duckdb.git"
clone_or_update "LightRAG" "https://github.com/HKUDS/LightRAG.git"
clone_or_update "MiroFish" "https://github.com/666ghj/MiroFish.git"
clone_or_update "ruoyi-ai" "https://github.com/ageerle/ruoyi-ai.git"
clone_or_update "MaxKB" "https://github.com/1Panel-dev/MaxKB.git"

curl -fsSL "https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw" \
  -o "${TARGET}/karpathy-llm-wiki.md"

echo "Reference snapshots synced under ${TARGET}"
