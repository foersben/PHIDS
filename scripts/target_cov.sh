#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
#
# Runs targeted pytest test-node execution with isolated module coverage gates.
# Fast feedback loop for subsystem development and mutation testing without global test overhead.

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: scripts/target_cov.sh <test-path-or-node> <cov-module> [extra pytest args...]" >&2
  echo "Example: scripts/target_cov.sh tests/integration/api/test_api_simulation_and_scenario_routes.py phids.api.routers.simulation" >&2
  exit 2
fi

target="$1"
cov_module="$2"
shift 2

NUMBA_DISABLE_JIT=1 uv run pytest -o addopts='' "$target" -q \
  --cov="$cov_module" \
  --cov-fail-under=80 \
  --cov-report=term-missing:skip-covered \
  --no-cov-on-fail \
  "$@"
