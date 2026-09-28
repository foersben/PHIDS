#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
#
# Automated setup and environment snapshot script for Jules cloud sandboxes.
# Pre-installs uv, just, Python 3.13, project dependencies, and pre-commit hooks.

set -euo pipefail

echo "=========================================="
echo "PHIDS Jules Cloud Environment Setup"
echo "=========================================="

# 1. Create local binary directory
mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:$PATH"

# Persist PATH in shell init files
for rc in "$HOME/.bashrc" "$HOME/.profile"; do
  if [ -f "$rc" ]; then
    if ! grep -q 'HOME/.local/bin' "$rc"; then
      echo 'export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"' >> "$rc"
    fi
  fi
done

# 2. Install uv (Astral) if missing
if ! command -v uv &> /dev/null; then
  echo ">>> Installing Astral uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

# Symlink to /usr/local/bin if writable
if [ -w /usr/local/bin ] && command -v uv &> /dev/null; then
  ln -sf "$(command -v uv)" /usr/local/bin/uv || true
fi

echo ">>> uv version: $(uv --version)"

# 3. Install just (Task runner) if missing
if ! command -v just &> /dev/null; then
  echo ">>> Installing just..."
  curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to "$HOME/.local/bin"
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ -w /usr/local/bin ] && command -v just &> /dev/null; then
  ln -sf "$(command -v just)" /usr/local/bin/just || true
fi

echo ">>> just version: $(just --version)"

# 4. Ensure Python 3.13 is installed via uv
echo ">>> Installing and pinning Python 3.13..."
uv python install 3.13

# 5. Synchronize all dependency groups into .venv
echo ">>> Synchronizing PHIDS dependencies (--all-groups)..."
uv sync --all-groups

# 6. Pre-cache pre-commit hooks and environments
echo ">>> Pre-caching pre-commit environments..."
uv run pre-commit install --install-hooks || true

# 7. Run initial matrix coverage & trace parity verification
echo ">>> Verifying causal matrix and type integrity..."
uv run python scripts/audit_matrix_coverage.py
uv run python scripts/verify_matrix_trace_parity.py --all
uv run ruff check src/ && uv run mypy src/phids

echo "=========================================="
echo "PHIDS Jules Snapshot Environment Ready!"
echo "=========================================="
