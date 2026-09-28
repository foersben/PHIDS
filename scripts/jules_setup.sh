#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
#
# Automated setup and environment snapshot script for Jules cloud sandboxes.
# Pre-installs uv, just, Python 3.13, project dependencies, and pre-commit hooks.
set -euo pipefail

# 0. Switch to develop branch if cloned on main
if [ -d .git ] && [ "$(git rev-parse --abbrev-ref HEAD)" != "develop" ]; then
  echo "Switching workspace to develop branch..."
  git remote set-branches --add origin develop || true
  git fetch --depth 1 origin develop || true
  git checkout develop || true
  git submodule update --init --recursive || true
fi

mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:$PATH"

# Persist PATH in shell init files
for rc in "$HOME/.bashrc" "$HOME/.profile"; do
  if [ -f "$rc" ] && ! grep -q 'HOME/.local/bin' "$rc"; then
    echo 'export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"' >> "$rc"
  fi
done

# 1. Install uv if missing
if ! command -v uv &> /dev/null; then
  echo "Installing Astral uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
[ -w /usr/local/bin ] && ln -sf "$(command -v uv)" /usr/local/bin/uv || true

# 2. Install just via uv tool (bypasses Cloudflare 403 blocks)
if ! command -v just &> /dev/null; then
  echo "Installing just via uv tool..."
  uv tool install rust-just
fi
[ -w /usr/local/bin ] && ln -sf "$(command -v just)" /usr/local/bin/just || true

# 3. Pin Python 3.13 and sync all dependencies
uv python install 3.13
uv sync --all-groups

# 4. Pre-cache pre-commit hooks and run verification gates
git config --global --unset-all core.hooksPath || true
uv run pre-commit install-hooks || true

if [ -f scripts/audit_matrix_coverage.py ]; then
  uv run python scripts/audit_matrix_coverage.py
fi

if [ -f scripts/verify_matrix_trace_parity.py ]; then
  uv run python scripts/verify_matrix_trace_parity.py --all
fi

uv run ruff check src/
uv run mypy src/phids
