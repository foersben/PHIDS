#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Full Verification Seal and Quality Gate Attestation for PHIDS.

Executes all 9 mandatory quality gates:
1. Ruff Linter & Formatter Validation (uv run ruff check .)
2. Strict Mypy Core & Scripts Typing (uv run mypy src/phids scripts)
3. Cognitive Complexity Ceiling <=15 (just complexity)
4. Rule 04 Markdown Formatting (uv run python scripts/governance/verify_markdown_rules.py)
5. OKF v0.2 Graph & Frontmatter Invariants (uv run python scripts/validate_okf.py)
6. Matrix Trace Parity Gate (uv run python scripts/verify_matrix_trace_parity.py --all)
7. Data-Flow Matrix Coverage Audit (uv run python scripts/audit_matrix_coverage.py)
8. Code & Architectural Invariants Ratchet (uv run python scripts/governance/verify_code_invariants.py)
9. Fast Unit Test Suite (uv run pytest tests/unit/ -q -o "addopts=")
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
RECEIPTS_DIR = ROOT_DIR / ".agents" / "receipts"
VERIFIERS_DIR = ROOT_DIR / ".agents" / "verifiers"


@dataclass(frozen=True, slots=True)
class Gate:
    """Represents a discrete verification gate."""

    gate_id: int
    name: str
    command: str


GATES: list[Gate] = [
    Gate(1, "Ruff Code Hygiene", "uv run ruff check ."),
    Gate(2, "Strict Mypy Core & Scripts", "uv run mypy src/phids scripts"),
    Gate(3, "Cognitive Complexity Ceiling (<=15)", "just complexity"),
    Gate(4, "Rule 04 Markdown Formatting", "uv run python scripts/governance/verify_markdown_rules.py"),
    Gate(5, "OKF v0.2 Graph & Metadata", "uv run python scripts/validate_okf.py"),
    Gate(6, "Data-Flow Matrix Trace Parity", "uv run python scripts/verify_matrix_trace_parity.py --all"),
    Gate(7, "Data-Flow Matrix Coverage Audit", "uv run python scripts/audit_matrix_coverage.py"),
    Gate(8, "Code Invariants & Bypass Ratchet", "uv run python scripts/governance/verify_code_invariants.py"),
    Gate(9, "Engine Unit Test Suite", 'uv run pytest tests/unit/ -q -o "addopts="'),
]


def run_gate(gate: Gate) -> tuple[bool, float, str]:
    """Execute a single gate and return (success, duration, output)."""
    start = time.perf_counter()
    res = subprocess.run(
        gate.command,
        shell=True,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start
    output = (res.stdout + "\n" + res.stderr).strip()
    return res.returncode == 0, elapsed, output


def emit_attestation_artifacts(
    results: list[tuple[Gate, bool, float]],
    total_elapsed: float,
    timestamp_utc: str,
) -> None:
    """Write OKF Attested Computation markdown seal and JSON receipt."""
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    VERIFIERS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Machine-readable JSON receipt
    receipt_data = {
        "timestamp_utc": timestamp_utc,
        "overall_status": "PASSED",
        "total_elapsed_seconds": round(total_elapsed, 2),
        "gate_count": len(results),
        "passed_count": sum(1 for _, s, _ in results if s),
        "gates": [
            {
                "gate_id": g.gate_id,
                "name": g.name,
                "command": g.command,
                "passed": s,
                "duration_seconds": round(d, 2),
            }
            for g, s, d in results
        ],
    }
    receipt_path = RECEIPTS_DIR / "phase5_receipt.json"
    receipt_path.write_text(json.dumps(receipt_data, indent=2), encoding="utf-8")

    # 2. Formal OKF Attested Computation concept document (§10.2)
    rows_md = "\n".join(
        f"| **Gate {g.gate_id}: {g.name}** | `{g.command}` | `0` | ✅ PASSED ({d:.2f}s) |" for g, _, d in results
    )

    doc_md = f"""---
type: Attested Computation
title: System Health Attestation Seal
status: stable
runtime: uv run (Python 3.13)
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Attested computation seal verifying full repository static analysis and test gates.
tags: [attestation, verification, pre-commit, seal]
generated: {{by: "process:attest-seal", at: "{timestamp_utc}"}}
verified: {{by: "process:attest-seal", at: "{timestamp_utc}"}}
sources:
  - id: toolchain_spec
    resource: .agents/toolchain.yaml
---

# System Health Attestation Seal

* **Timestamp:** `{timestamp_utc}`
* **Overall Status:** `PASSED`
* **Total Runtime:** `{total_elapsed:.2f}s`
* **Runtime Environment:** Astral uv (Python 3.13 on Linux x86_64)

## Verification Gate Results

| Gate | Command | Exit Code | Status |
| :--- | :--- | :--- | :--- |
{rows_md}

## Attestation Assertion

All {len(results)} mandatory pre-commit verification gates executed with zero non-zero exit codes.
Cognitive complexity strictly satisfies <= 15 with zero snapshot overrides.
Rule 04 Markdown formatting and OKF v0.2 knowledge graph consistency are formally verified.
Data-Flow Matrix table-to-trace parity verified at 100%.
"""
    attestation_path = VERIFIERS_DIR / "system_health_attestation.md"
    attestation_path.write_text(doc_md, encoding="utf-8")
    print(f"\n📜 Attested Computation written to '{attestation_path.relative_to(ROOT_DIR)}'.")
    print(f"📦 JSON receipt written to '{receipt_path.relative_to(ROOT_DIR)}'.")


def main() -> int:
    """Execute the verification seal suite."""
    print("=" * 70)
    print("🛡️  PHIDS FULL VERIFICATION SEAL & ATTESTATION SUITE")
    print("=" * 70)

    total_start = time.perf_counter()
    timestamp_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    failed = False
    results: list[tuple[Gate, bool, float]] = []

    for gate in GATES:
        print(f"\n[Gate {gate.gate_id}/{len(GATES)}] {gate.name}...")
        print(f"  Command: {gate.command}")
        success, elapsed, output = run_gate(gate)
        results.append((gate, success, elapsed))

        if success:
            print(f"  Result:  ✅ PASS ({elapsed:.2f}s)")
        else:
            print(f"  Result:  ❌ FAILED ({elapsed:.2f}s)")
            print("\n" + "-" * 60)
            print("GATE FAILURE LOG:")
            print(output[:2000])
            print("-" * 60)
            failed = True
            break

    total_elapsed = time.perf_counter() - total_start
    print("\n" + "=" * 70)
    print("ATTESTATION SUMMARY")
    print("=" * 70)
    for gate, success, elapsed in results:
        status_sym = "✅ PASS" if success else "❌ FAIL"
        print(f"  Gate {gate.gate_id}: {gate.name:<38} {status_sym} ({elapsed:5.2f}s)")
    print("-" * 70)

    if failed:
        print(f"💥 Attestation FAILED after {total_elapsed:.2f}s.")
        return 1

    emit_attestation_artifacts(results, total_elapsed, timestamp_utc)
    print(f"\n🎉 All {len(GATES)} gates PASSED. Attestation SEAL verified in {total_elapsed:.2f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
