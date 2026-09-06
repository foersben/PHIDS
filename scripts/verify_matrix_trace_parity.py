#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Automated parity verifier between Markdown Data-Flow Matrix tables and live Pytest traces.

Extracts table rows from Markdown documents and asserts 1:1 numerical parity against
canonical simulation trace outputs from `tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path for test imports
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tests.integration.scientific_invariants.test_causal_data_flow_matrices import (  # noqa: E402
    generate_clonal_mitosis_trace,
    generate_defense_cascade_trace,
    generate_herbivore_starvation_trace,
    generate_mycorrhizal_hop_trace,
    generate_phloem_translocation_trace,
)


def _extract_markdown_table(doc_path: Path) -> list[dict[str, str]]:
    """Extract Markdown table rows into a list of column-keyed dictionaries.

    Args:
        doc_path: Path to the markdown file.

    Returns:
        List of dicts representing parsed rows.
    """
    text = doc_path.read_text(encoding="utf-8")
    table_lines: list[str] = []
    in_table = False

    for line in text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("|") and ("Tick" in trimmed or in_table):
            in_table = True
            table_lines.append(trimmed)
        elif in_table and not trimmed.startswith("|"):
            break

    if len(table_lines) < 3:
        return []

    # Parse headers
    headers = [h.strip().replace("`", "").replace("$", "") for h in table_lines[0].split("|")[1:-1]]
    rows: list[dict[str, str]] = []

    # Skip header and separator row
    for line in table_lines[2:]:
        cols = [c.strip().replace("`", "").replace("$", "") for c in line.split("|")[1:-1]]
        if len(cols) == len(headers):
            rows.append(dict(zip(headers, cols, strict=False)))

    return rows


def verify_phloem_matrix_parity(doc_path: Path) -> list[str]:
    """Verify phloem translocation table against live engine trace."""
    errors: list[str] = []
    table = _extract_markdown_table(doc_path)
    if not table:
        return ["Could not find or parse Data-Flow Matrix table in document."]

    trace = generate_phloem_translocation_trace(0.5, 0.2, 0.5, 2, 6)
    if len(table) != len(trace):
        errors.append(f"Row count mismatch: Document has {len(table)} rows; runtime trace has {len(trace)} rows.")
        return errors

    for _i, (doc_row, trace_row) in enumerate(zip(table, trace, strict=False)):
        for key in doc_row:
            low_k = key.lower()
            try:
                if "apparent" in low_k:
                    val = float(doc_row[key].split()[0])
                    expected = float(trace_row.n_apparent)
                    if abs(val - expected) > 1e-4:
                        errors.append(f"Tick {trace_row.tick} apparent drift: Doc={val}, Runtime={expected}")
                elif "target" in low_k:
                    val = float(doc_row[key].split()[0])
                    expected = float(trace_row.n_target)
                    if abs(val - expected) > 1e-4:
                        errors.append(f"Tick {trace_row.tick} target drift: Doc={val}, Runtime={expected}")
                elif "withdrawal" in low_k:
                    val_int = int(doc_row[key].split()[0])
                    if val_int != trace_row.withdrawal_ticks:
                        errors.append(
                            f"Tick {trace_row.tick} withdrawal ticks drift: "
                            f"Doc={val_int}, Runtime={trace_row.withdrawal_ticks}"
                        )
            except (ValueError, IndexError):
                pass

    return errors


def verify_defense_matrix_parity(doc_path: Path) -> list[str]:
    """Verify defense signaling cascade table against canonical trace."""
    errors: list[str] = []
    table = _extract_markdown_table(doc_path)
    if not table:
        return ["Could not find or parse Data-Flow Matrix table in document."]

    trace = generate_defense_cascade_trace()
    if len(table) != len(trace):
        errors.append(f"Row count mismatch: Document has {len(table)} rows; runtime trace has {len(trace)} rows.")
        return errors

    for doc_row, trace_row in zip(table, trace, strict=False):
        for key in doc_row:
            low_k = key.lower()
            try:
                if ("e_current" in low_k) or (low_k.startswith("e") and "current" in low_k):
                    val = float(doc_row[key].split()[0])
                    if abs(val - trace_row.e_current) > 1e-4:
                        errors.append(f"Tick {trace_row.tick} E drift: Doc={val}, Expected={trace_row.e_current}")
                elif "internal" in low_k:
                    val = float(doc_row[key].split()[0])
                    if abs(val - trace_row.m_internal) > 1e-4:
                        errors.append(
                            f"Tick {trace_row.tick} M_internal drift: Doc={val}, Expected={trace_row.m_internal}"
                        )
                elif "external" in low_k:
                    val = float(doc_row[key].split()[0])
                    if abs(val - trace_row.l_external) > 1e-4:
                        errors.append(
                            f"Tick {trace_row.tick} L_external drift: Doc={val}, Expected={trace_row.l_external}"
                        )
            except ValueError:
                pass

    return errors


def verify_starvation_matrix_parity(doc_path: Path) -> list[str]:
    """Verify herbivore starvation table against canonical trace."""
    errors: list[str] = []
    table = _extract_markdown_table(doc_path)
    if not table:
        return ["Could not find or parse Data-Flow Matrix table in document."]

    trace = generate_herbivore_starvation_trace()
    if len(table) != len(trace):
        errors.append(f"Row count mismatch: Document has {len(table)} rows; runtime trace has {len(trace)} rows.")
        return errors

    for doc_row, trace_row in zip(table, trace, strict=False):
        for key in doc_row:
            low_k = key.lower()
            try:
                if "population" in low_k:
                    val_pop = int(doc_row[key].split()[0])
                    if val_pop != trace_row.population:
                        errors.append(
                            f"Tick {trace_row.tick} Pop drift: Doc={val_pop}, Expected={trace_row.population}"
                        )
                elif "energy" in low_k and "min" not in low_k:
                    val_e = float(doc_row[key].split()[0])
                    if abs(val_e - trace_row.energy) > 1e-4:
                        errors.append(f"Tick {trace_row.tick} E drift: Doc={val_e}, Expected={trace_row.energy}")
                elif "alive" in low_k:
                    val_alive = float(doc_row[key].split()[0])
                    if abs(val_alive - trace_row.alive_mask) > 1e-4:
                        errors.append(
                            f"Tick {trace_row.tick} alive_mask drift: Doc={val_alive}, Expected={trace_row.alive_mask}"
                        )
            except (ValueError, IndexError):
                pass

    return errors


def verify_mycorrhizal_matrix_parity(doc_path: Path) -> list[str]:
    """Verify mycorrhizal root hop propagation table against canonical trace."""
    errors: list[str] = []
    table = _extract_markdown_table(doc_path)
    if not table:
        return ["Could not find or parse Data-Flow Matrix table in document."]

    trace = generate_mycorrhizal_hop_trace()
    if len(table) != len(trace):
        errors.append(f"Row count mismatch: Document has {len(table)} rows; runtime trace has {len(trace)} rows.")
        return errors

    for doc_row, trace_row in zip(table, trace, strict=False):
        for key in doc_row:
            low_k = key.lower()
            try:
                if "hop1" in low_k and "energy" not in low_k:
                    val = float(doc_row[key].split()[0])
                    if abs(val - trace_row.hop1_signal) > 1e-4:
                        errors.append(
                            f"Tick {trace_row.tick} Hop 1 signal drift: Doc={val}, Expected={trace_row.hop1_signal}"
                        )
                elif "hop2" in low_k:
                    val = float(doc_row[key].split()[0])
                    if abs(val - trace_row.hop2_signal) > 1e-4:
                        errors.append(
                            f"Tick {trace_row.tick} Hop 2 signal drift: Doc={val}, Expected={trace_row.hop2_signal}"
                        )
            except (ValueError, IndexError):
                pass

    return errors


def verify_mitosis_matrix_parity(doc_path: Path) -> list[str]:
    """Verify clonal mitosis bifurcation table against canonical trace."""
    errors: list[str] = []
    table = _extract_markdown_table(doc_path)
    if not table:
        return ["Could not find or parse Data-Flow Matrix table in document."]

    trace = generate_clonal_mitosis_trace()
    if len(table) != len(trace):
        errors.append(f"Row count mismatch: Document has {len(table)} rows; runtime trace has {len(trace)} rows.")
        return errors

    for doc_row, trace_row in zip(table, trace, strict=False):
        for key in doc_row:
            low_k = key.lower()
            try:
                if ("parent_pop" in low_k) or (("parent" in low_k) and ("pop" in low_k)):
                    val = int(doc_row[key].split()[0])
                    if val != trace_row.parent_pop:
                        errors.append(
                            f"Tick {trace_row.tick} Parent Pop drift: Doc={val}, Expected={trace_row.parent_pop}"
                        )
                elif ("daughter_pop" in low_k) or (("daughter" in low_k) and ("pop" in low_k)):
                    val = int(doc_row[key].split()[0])
                    if val != trace_row.daughter_pop:
                        errors.append(
                            f"Tick {trace_row.tick} Daughter Pop drift: Doc={val}, Expected={trace_row.daughter_pop}"
                        )
            except (ValueError, IndexError):
                pass

    return errors


def main() -> int:
    """Run trace parity verifier."""
    parser = argparse.ArgumentParser(description="Verify table-to-trace parity for OKF Data-Flow Matrices.")
    parser.add_argument("--doc", help="Specific markdown document to verify.")
    parser.add_argument("--all", action="store_true", help="Verify all documented Data-Flow Matrices.")
    args = parser.parse_args()

    doc_registry: dict[str, Any] = {
        "docs/scientific_model/morphological_defenses.md": verify_phloem_matrix_parity,
        "docs/scientific_model/reaction_diffusion.md": verify_defense_matrix_parity,
        "docs/scientific_model/herbivore_behavior.md": verify_starvation_matrix_parity,
        "docs/scientific_model/flora_and_symbiosis.md": verify_mycorrhizal_matrix_parity,
        "docs/scientific_model/population_dynamics.md": verify_mitosis_matrix_parity,
        "docs/development_guide/okf_data_flow_matrices.md": verify_defense_matrix_parity,
    }

    targets = []
    if args.doc:
        targets.append(Path(args.doc))
    elif args.all:
        targets = [Path(p) for p in doc_registry]
    else:
        print("Please specify --doc <path> or --all.")
        return 1

    total_errors = 0
    for doc in targets:
        rel_str = str(doc.relative_to(Path.cwd())) if doc.is_relative_to(Path.cwd()) else str(doc)
        print(f"🔬 Verifying Data-Flow Matrix Parity for '{rel_str}'...")

        verifier = doc_registry.get(rel_str, verify_phloem_matrix_parity)
        errors = verifier(doc)
        if errors:
            total_errors += len(errors)
            print(f"❌ Parity Violations in '{rel_str}':")
            for err in errors:
                print(f"   • {err}")
        else:
            print("✅ 100% Numerical Parity verified against runtime Pytest trace.")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
