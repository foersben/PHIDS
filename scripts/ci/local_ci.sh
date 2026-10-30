#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
#
# Runs PHIDS continuous integration passes locally on the native host interpreter
# without container overhead (Docker/act). Replicates CI quality, test, and doc builds.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/ci/local_ci.sh [quality|tests|docs|all]

Runs the main PHIDS CI commands on the current local interpreter.

Examples:
  ./scripts/ci/local_ci.sh quality
  ./scripts/ci/local_ci.sh tests
  ./scripts/ci/local_ci.sh docs
  ./scripts/ci/local_ci.sh all

Environment variables:
  PHIDS_SKIP_SYNC=1  Skip 'uv sync --all-groups' before running checks.
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
  echo ">>> 1. Running Ruff lint"
  uv run ruff check .
  echo ">>> 2. Running Ruff format check"
  uv run ruff format --check .
  echo ">>> 3. Running strict Mypy across src/phids and scripts"
  uv run mypy src/phids scripts
  echo ">>> 4. Checking Rule 04 Markdown formatting"
  uv run python scripts/governance/verify_markdown_rules.py
  echo ">>> 5. Validating OKF v0.2 graph and metadata"
  uv run python scripts/governance/validate_okf.py
  echo ">>> 6. Verifying code invariants and bypass ratchet"
  uv run python scripts/governance/verify_code_invariants.py
  echo ">>> 7. Auditing Data-Flow Matrix coverage"
  uv run python scripts/governance/audit_matrix_coverage.py
  echo ">>> 8. Verifying Data-Flow Matrix trace parity"
  uv run python scripts/governance/verify_matrix_trace_parity.py --all
}

run_tests() {
  echo ">>> Pass 1: Logic & Coverage (NUMBA_DISABLE_JIT=1)"
  NUMBA_DISABLE_JIT=1 uv run pytest --cov=src/phids --cov-fail-under=80

  echo ">>> Pass 2: Numba Compilation Verification"
  uv run pytest tests/integration/systems/test_full_numba_jit_compilation.py tests/integration/systems/test_interaction_invariants/ \
    -x -q -o "addopts="
}

run_docs() {
  echo ">>> Building static docs in strict mode"
  uv run zensical build --strict
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
