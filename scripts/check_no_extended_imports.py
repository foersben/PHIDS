#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Pre-commit guard: fail if extended NC-licensed imports appear in core pipeline.

This script is registered as a pre-commit hook and is run automatically by
``git commit``. It scans the core pipeline files for any import of the
``data_pipeline.ingest.extended`` subpackage.

If such an import is found, the commit is BLOCKED with a clear error message
explaining the license violation risk.

PROTECTED FILES
---------------
- src/data_pipeline/run_all.py
- src/data_pipeline/db/export.py  (the core publish function)

These files form the "trusted zone" of the pipeline. They MUST NEVER import
from the ``ingest.extended`` subpackage.

Usage
-----
    python scripts/check_no_extended_imports.py

Returns 0 if clean, 1 if violations found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Files that must NEVER import from the extended subpackage
PROTECTED_FILES: list[Path] = [
    Path("src/data_pipeline/run_all.py"),
    Path("src/data_pipeline/db/export.py"),
    Path("src/data_pipeline/db/writer.py"),
    Path("src/data_pipeline/db/query.py"),
    Path("src/data_pipeline/transform.py"),
    Path("src/data_pipeline/archetype_extractor.py"),
]

# Patterns that indicate an import from the extended subpackage
FORBIDDEN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"from\s+data_pipeline\.ingest\.extended"),
    re.compile(r"import\s+data_pipeline\.ingest\.extended"),
    re.compile(r"from\s+\.extended"),
    re.compile(r"from\s+ingest\.extended"),
    # Also catch direct module names
    re.compile(r"bien_client"),
    re.compile(r"leda_client"),
    re.compile(r"gift_client"),
]


def check_file(path: Path) -> list[tuple[int, str]]:
    """Check a single file for forbidden extended import patterns.

    Args:
        path: Absolute or relative path to the Python source file.

    Returns:
        List of (line_number, line_content) tuples for each violation found.

    """
    violations: list[tuple[int, str]] = []
    if not path.exists():
        return violations

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        # Skip comments and docstrings that merely document the protection
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                violations.append((line_no, line.rstrip()))
                break

    return violations


def main() -> int:
    """Run the extended import guard check across all protected files.

    Returns:
        Exit code: 0 = clean, 1 = violations found.

    """
    repo_root = Path(__file__).parent.parent
    found_any = False

    for rel_path in PROTECTED_FILES:
        abs_path = repo_root / rel_path
        violations = check_file(abs_path)
        if violations:
            found_any = True
            print(f"\n{'=' * 70}")
            print(f"LICENSE VIOLATION DETECTED in: {rel_path}")
            print(f"{'=' * 70}")
            print("The following lines import from the extended NC-licensed subpackage:")
            for line_no, content in violations:
                print(f"  Line {line_no:4d}: {content}")
            print()
            print("This import would allow NC-licensed data (BIEN, LEDA, GIFT) to flow")
            print("into the core commercial pipeline, constituting a license violation.")
            print()
            print("RESOLUTION:")
            print("  - Remove the import from this core pipeline file.")
            print("  - If you need extended data, use run_extended.py instead.")
            print("  - NEVER set PHIDS_EXTENDED_MODE=1 in the default pipeline.")
            print(f"{'=' * 70}")

    if found_any:
        print("\nCommit BLOCKED. Fix the license violations above before committing.")
        return 1

    print("License guard OK: no extended NC imports found in core pipeline files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
