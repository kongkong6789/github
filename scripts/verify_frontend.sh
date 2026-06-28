#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)/common.sh"
load_dotenv

FRONTEND_DIR="${PROJECT_ROOT}/agent-chat-ui"
UNIT_ONLY="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --unit-only) UNIT_ONLY="true"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "Frontend directory not found: ${FRONTEND_DIR}" >&2
  exit 1
fi

(
  cd "${FRONTEND_DIR}"

  WITH_ENV="./scripts/with-env-node.sh"
  ESBUILD="./node_modules/.bin/esbuild"
  ESLINT="./node_modules/.bin/eslint"
  TSC="./node_modules/.bin/tsc"

  if [[ ! -x "${WITH_ENV}" || ! -x "${ESBUILD}" || ! -x "${ESLINT}" || ! -x "${TSC}" ]]; then
    echo "Frontend dependencies are missing. Run npm install or pnpm install in agent-chat-ui first." >&2
    exit 1
  fi

  TEST_SOURCE_LIST="$(mktemp /tmp/a2a-ui-test-sources.XXXXXX)"
  TMP_DIR=""
  TEST_BUNDLE_LIST=""
  cleanup() {
    rm -f "${TEST_SOURCE_LIST}"
    if [[ -n "${TEST_BUNDLE_LIST}" ]]; then
      rm -f "${TEST_BUNDLE_LIST}"
    fi
    if [[ -n "${TMP_DIR}" ]]; then
      rm -rf "${TMP_DIR}"
    fi
  }
  trap cleanup EXIT

  find src -type f \( -name "*.test.ts" -o -name "*.test.tsx" \) | sort > "${TEST_SOURCE_LIST}"
  TEST_SOURCES=()
  while IFS= read -r test_source; do
    [[ -n "${test_source}" ]] || continue
    TEST_SOURCES+=("${test_source}")
  done < "${TEST_SOURCE_LIST}"

  if [[ "${#TEST_SOURCES[@]}" -gt 0 ]]; then
    TMP_DIR="$(mktemp -d /tmp/a2a-ui-tests.XXXXXX)"
    "${WITH_ENV}" "${ESBUILD}" "${TEST_SOURCES[@]}" \
      --bundle --platform=node --format=esm --outdir="${TMP_DIR}" "--external:node:*"

    TEST_BUNDLE_LIST="$(mktemp /tmp/a2a-ui-test-bundles.XXXXXX)"
    find "${TMP_DIR}" -type f -name "*.test.js" | sort > "${TEST_BUNDLE_LIST}"
    TEST_BUNDLES=()
    while IFS= read -r test_bundle; do
      [[ -n "${test_bundle}" ]] || continue
      TEST_BUNDLES+=("${test_bundle}")
    done < "${TEST_BUNDLE_LIST}"
    if [[ "${#TEST_BUNDLES[@]}" -gt 0 ]]; then
      "${WITH_ENV}" node --test "${TEST_BUNDLES[@]}"
    else
      echo "No compiled frontend test bundles found under ${TMP_DIR}." >&2
      exit 1
    fi
  else
    echo "No frontend test files found under agent-chat-ui/src."
  fi

  if [[ "${UNIT_ONLY}" != "true" ]]; then
    "${WITH_ENV}" ./node_modules/.bin/tsc --noEmit --pretty false
    "${WITH_ENV}" "${ESLINT}" . --max-warnings=0
    npm run build
  fi
)
