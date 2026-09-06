#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Local development environment bootstrapper.

Initializes the required local configuration files and cache directories
prior to running containerized or local continuous integration workflows:
1. Provisions `.github/workflows/secrets.env` from `.github/workflows/secrets.env.example`
   if not already present (required by `act` to run GitHub Actions locally).
2. Restores `.cache/act-artifacts/` and its `.gitkeep` anchor to ensure artifact
   caching succeeds without git tracking local build products.

Usage:
    python scripts/bootstrap.py
    uv run python scripts/bootstrap.py
"""

from __future__ import annotations

import shutil
from pathlib import Path


def bootstrap() -> None:
    """Bootstrap the local development environment.

    Ensures that local environment files and cache directories required by
    developer tooling (e.g. `act` and pre-commit) are present:
    - Copies ``.github/workflows/secrets.env.example`` to ``secrets.env`` if missing.
    - Creates ``.cache/act-artifacts/`` with a ``.gitkeep`` file if missing.

    Raises:
        OSError: If directory creation or file writing fails due to permission errors.
    """
    print("🚀 Initializing local development environment...")

    # Resolve repository root directory (two levels up from scripts/bootstrap.py)
    root = Path(__file__).resolve().parent.parent
    env_example = root / ".github" / "workflows" / "secrets.env.example"
    env_actual = root / ".github" / "workflows" / "secrets.env"

    cache_dir = root / ".cache" / "act-artifacts"
    gitkeep_file = cache_dir / ".gitkeep"

    # 1. Handle secrets.env for local act execution
    if env_actual.exists():
        print("✅ .github/workflows/secrets.env already exists.")
    else:
        if env_example.exists():
            shutil.copy(env_example, env_actual)
            print("🆕 Created .github/workflows/secrets.env from template.")
        else:
            env_actual.parent.mkdir(parents=True, exist_ok=True)
            env_actual.write_text("# GITHUB_TOKEN=your_real_github_token_here\n", encoding="utf-8")
            print("🆕 Created a blank .github/workflows/secrets.env file.")

    print("\n📁 Checking local cache directories...")
    # 2. Handle .cache/act-artifacts/.gitkeep
    if gitkeep_file.exists():
        print("   ✅ .cache/act-artifacts/ is ready.")
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)
        gitkeep_file.write_text("# act artifact store - contents are gitignored\n", encoding="utf-8")
        print("   🆕 Restored .cache/act-artifacts/ and .gitkeep file.")

    print("\n🎉 Local setup complete! You can now run your local 'act' workflows safely.")


if __name__ == "__main__":
    bootstrap()
