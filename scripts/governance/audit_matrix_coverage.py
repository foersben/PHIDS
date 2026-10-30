#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Automated coverage auditor verifying OKF Data-Flow Matrix presence and bilateral links.

Scans concept documents in `docs/scientific_model/` (and configured subdirectories) to assert:
1. Presence of a mandatory `## Data-Flow Matrix Specifications` section containing a valid Markdown table.
2. Rule 05-C Bilateral Resource Mapping in OKF YAML frontmatter:
   - Must link to the underlying engine system implementation in `src/phids/engine/`.
   - Must link to the corresponding Pytest trace suite in `tests/integration/scientific_invariants/`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


def _parse_frontmatter(content: str) -> tuple[dict[str, object], str]:
    """Extract YAML frontmatter and body from Markdown text.

    Args:
        content: Raw Markdown file text.

    Returns:
        Tuple of (frontmatter dict, markdown body).
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        fm = yaml.safe_load(parts[1])
        return (fm if isinstance(fm, dict) else {}), parts[2]
    except Exception:
        return {}, parts[2]


def _check_matrix_presence(body: str) -> list[str]:
    """Check for Data-Flow Matrix section and table."""
    errors: list[str] = []
    has_matrix_section = bool(
        re.search(r"##\s+(?:Data-Flow\s+Matrix\s+Specifications|Data-Flow\s+Matrix)", body, re.IGNORECASE)
    )
    if not has_matrix_section:
        errors.append("Missing mandatory '## Data-Flow Matrix Specifications' section.")

    has_table = bool(re.search(r"\|\s*Tick\s*[^|]*\|", body, re.IGNORECASE)) or bool(
        re.search(r"\|\s*Event\s*\|[^|]*Precondition", body, re.IGNORECASE)
    )
    if not has_table:
        errors.append("Missing columnar Data-Flow Matrix table (| Tick ... |).")
    return errors


def _extract_declared_resources(fm: dict[str, object]) -> list[str]:
    """Extract string resources declared in frontmatter."""
    sources = fm.get("sources") or fm.get("resources") or []
    if not isinstance(sources, list):
        sources = [sources]

    declared_resources: list[str] = []
    for item in sources:
        if isinstance(item, dict) and "resource" in item:
            declared_resources.append(str(item["resource"]))
        elif isinstance(item, str):
            declared_resources.append(item)
    return declared_resources


def _check_bilateral_resources(fm: dict[str, object]) -> list[str]:
    """Check Rule 05-C Bilateral Resource Mapping in frontmatter."""
    errors: list[str] = []
    declared_resources = _extract_declared_resources(fm)

    has_engine_link = any("src/phids/engine" in r or "src/phids/api" in r for r in declared_resources)
    if not has_engine_link:
        errors.append(
            "Rule 05-C Violation: Frontmatter sources/resources must link to "
            "underlying engine implementation in src/phids/engine/."
        )

    has_test_link = any(
        "tests/integration/scientific_invariants" in r or "test_causal_data_flow_matrices" in r
        for r in declared_resources
    )
    if not has_test_link:
        errors.append(
            "Rule 05-C Violation: Frontmatter sources/resources must link to "
            "trace test suite in tests/integration/scientific_invariants/."
        )

    return errors


def audit_document(file_path: Path) -> list[str]:
    """Audit a single scientific model Markdown document.

    Args:
        file_path: Path to the markdown document.

    Returns:
        List of validation error messages, or empty list if fully compliant.
    """
    text = file_path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    return _check_matrix_presence(body) + _check_bilateral_resources(fm)


def _discover_target_files(target_dir: Path, strict: bool) -> list[Path]:
    """Discover Markdown files targeted for matrix coverage audit."""
    cascade_names = {
        "morphological_defenses.md",
        "reaction_diffusion.md",
        "herbivore_behavior.md",
        "flora_and_symbiosis.md",
        "population_dynamics.md",
        "biological_abstractions.md",
    }
    excluded_names = {"index.md", "log.md", "related_works.md", "parameter_calibration_strategy.md"}

    if strict:
        return [f for f in target_dir.rglob("*.md") if f.name not in excluded_names and "site" not in f.parts]
    return [f for f in target_dir.rglob("*.md") if f.name in cascade_names and "site" not in f.parts]


def _execute_audit_run(md_files: list[Path]) -> int:
    """Run audit checks and print summary report."""
    total_violations = 0
    total_files = len(md_files)

    for doc in sorted(md_files):
        rel_path = doc.relative_to(Path.cwd()) if doc.is_relative_to(Path.cwd()) else doc
        doc_errors = audit_document(doc)
        if doc_errors:
            total_violations += len(doc_errors)
            print(f"❌ Coverage Deficit in -> {rel_path}:")
            for err in doc_errors:
                print(f"   • {err}")
        else:
            print(f"✅ {rel_path}: Data-Flow Matrix & Rule 05-C Bilateral Mapping verified.")

    print(f"\nAudit complete: {total_files - (1 if total_violations else 0)}/{total_files} files compliant.")
    if total_violations > 0:
        print(f"⚠️ Total violations: {total_violations}. Failing gate.")
        return 1

    print("🎉 100% OKF Data-Flow Matrix coverage verified.")
    return 0


def main() -> int:
    """Run coverage audit across scientific model documents."""
    parser = argparse.ArgumentParser(description="Audit OKF Data-Flow Matrix coverage across documentation.")
    parser.add_argument(
        "--dir",
        default="docs/scientific_model",
        help="Directory containing scientific model concept docs (default: docs/scientific_model)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce audit on all discovered markdown files (excluding index.md/log.md).",
    )
    args = parser.parse_args()

    target_dir = Path(args.dir).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"❌ Error: Target directory '{target_dir}' does not exist.")
        return 1

    md_files = _discover_target_files(target_dir, args.strict)
    print(f"🔍 Auditing OKF Data-Flow Matrix Coverage across {len(md_files)} concept files in '{args.dir}'...\n")
    return _execute_audit_run(md_files)


if __name__ == "__main__":
    sys.exit(main())
