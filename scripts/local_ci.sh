#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/local_ci.sh [quality|tests|docs|all]

Runs the main PHIDS CI commands on the current local interpreter.

Examples:
  ./scripts/local_ci.sh quality
  ./scripts/local_ci.sh tests
  ./scripts/local_ci.sh docs
  ./scripts/local_ci.sh all

Environment variables:
  PHIDS_SKIP_SYNC=1  Skip 'uv sync --all-extras --dev' before running checks.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

job="${1:-all}"

run_sync() {
  if [[ "${PHIDS_SKIP_SYNC:-0}" == "1" ]]; then
    echo ">>> Skipping dependency sync because PHIDS_SKIP_SYNC=1"
    return
  fi

  echo ">>> Syncing dependencies"
  uv sync --all-groups
}

run_quality() {
  echo ">>> Running Ruff lint"
  uv run ruff check .
  echo ">>> Running Ruff format check"
  uv run ruff format --check .
}

run_tests() {
  echo ">>> Pass 1: Logic & Coverage (NUMBA_DISABLE_JIT=1)"
  NUMBA_DISABLE_JIT=1 uv run pytest --cov=src/phids --cov-fail-under=80

  echo ">>> Pass 2: Numba Compilation Verification"
  uv run pytest tests/integration/systems/test_interaction_property_invariants.py \
    -x -q -o "addopts="
}

run_docs() {
  echo ">>> Building docs in strict mode"
  uv run zensical build
}

case "$job" in
  quality)
    run_sync
    run_quality
    ;;
  tests)
    run_sync
    run_tests
    ;;
  docs)
    run_sync
    run_docs
    ;;
  all)
    run_sync
    run_quality
    run_tests
    run_docs
    ;;
  *)
    echo "Unknown job: $job" >&2
    usage >&2
    exit 1
    ;;
esac
