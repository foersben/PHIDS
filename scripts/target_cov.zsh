#!/usr/bin/env zsh
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: scripts/target_cov.zsh <test-path-or-node> <cov-module> [extra pytest args...]" >&2
  echo "Example: scripts/target_cov.zsh tests/integration/api/test_api_simulation_and_scenario_routes.py phids.api.routers.simulation" >&2
  exit 2
fi

target="$1"
cov_module="$2"
shift 2

uv run pytest -o addopts='' "$target" -q \
  --cov="$cov_module" \
  --cov-fail-under=80 \
  --cov-report=term-missing:skip-covered \
  --no-cov-on-fail \
  "$@"
