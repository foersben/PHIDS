---
type: Attested Computation
title: System Health Attestation Seal
status: stable
runtime: uv run (Python 3.13)
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Attested computation seal verifying full repository static analysis and test gates.
tags: [attestation, verification, pre-commit, seal]
generated: {by: "process:attest-seal", at: "2026-10-30T01:49:33Z"}
verified: {by: "process:attest-seal", at: "2026-10-30T01:49:33Z"}
sources:
  - id: toolchain_spec
    resource: .agents/toolchain.yaml
---

# System Health Attestation Seal

* **Timestamp:** `2026-10-30T01:49:33Z`
* **Overall Status:** `PASSED`
* **Total Runtime:** `23.98s`
* **Runtime Environment:** Astral uv (Python 3.13 on Linux x86_64)

## Verification Gate Results

| Gate | Command | Exit Code | Status |
| :--- | :--- | :--- | :--- |
| **Gate 1: Ruff Code Hygiene** | `uv run ruff check .` | `0` | ✅ PASSED (0.06s) |
| **Gate 2: Strict Mypy Core & Scripts** | `uv run mypy src/phids scripts` | `0` | ✅ PASSED (0.71s) |
| **Gate 3: Cognitive Complexity Ceiling (<=15)** | `just complexity` | `0` | ✅ PASSED (0.47s) |
| **Gate 4: Rule 04 Markdown Formatting** | `uv run python scripts/governance/verify_markdown_rules.py` | `0` | ✅ PASSED (0.11s) |
| **Gate 5: OKF v0.2 Graph & Metadata** | `uv run python scripts/validate_okf.py` | `0` | ✅ PASSED (0.31s) |
| **Gate 6: Data-Flow Matrix Trace Parity** | `uv run python scripts/verify_matrix_trace_parity.py --all` | `0` | ✅ PASSED (0.75s) |
| **Gate 7: Data-Flow Matrix Coverage Audit** | `uv run python scripts/audit_matrix_coverage.py` | `0` | ✅ PASSED (0.14s) |
| **Gate 8: Code Invariants & Bypass Ratchet** | `uv run python scripts/governance/verify_code_invariants.py` | `0` | ✅ PASSED (0.53s) |
| **Gate 9: Engine Unit Test Suite** | `uv run pytest tests/unit/ -q -o "addopts="` | `0` | ✅ PASSED (20.90s) |

## Attestation Assertion

All 9 mandatory pre-commit verification gates executed with zero non-zero exit codes.
Cognitive complexity strictly satisfies <= 15 with zero snapshot overrides.
Rule 04 Markdown formatting and OKF v0.2 knowledge graph consistency are formally verified.
Data-Flow Matrix table-to-trace parity verified at 100%.
