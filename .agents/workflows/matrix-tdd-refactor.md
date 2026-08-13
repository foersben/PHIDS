---
type: workflow
title: Matrix-Driven TDD Refactoring
status: active
version: 1.0
description: Coordinated pipeline for translating conceptual behavior to Data-Flow Matrix specifications, failing Pytest trace tests, branchless Numba kernels, and verified audits.
tags:
- workflow
- data-flow-matrix
- tdd
- refactoring
timestamp: "2026-08-14T00:30:00Z"
resources:
- docs/development_guide/okf_data_flow_matrices.md
---

# Sequence

1. **Specification (`@scientific-architect` & `@docs-librarian`):** Read target theory and source code. Construct the Data-Flow Matrix Table (Ticks $t_0 \dots t_n$, NumPy array columns, branchless float masks). Save under `## Data-Flow Matrix Specifications` in the target doc. *Pause for human review and approval.*
2. **Pytest Trace Gate (`@qa-automator` & `@matrix-auditor`):** Translate the Data-Flow Matrix Table into a time-series trace test in `tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`. Run Pytest and confirm the tests fail (TDD gate).
3. **Branchless Numba Implementation (`@engine-developer` & `@causal-verifier`):** Implement or refactor Numba `@njit` kernels in `src/phids/engine/systems/` using contiguous double-buffered arrays and float mask math (`alive_mask`, `capacity_mask`). Iterate until all trace tests pass.
4. **Verification & Audit (`@docs-librarian`, `@matrix-auditor`, & `@git-operator`):** Run `verify-matrix-trace-parity` to ensure 100% parity. Validate OKF frontmatter `resources` links with `scripts/validate_okf.py`. Execute signed git commit.
