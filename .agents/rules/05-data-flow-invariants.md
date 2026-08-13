---
type: rule
title: Mandates
status: active
version: 1.0
description: "- **Table-to-Trace Parity:** Every Markdown Data-Flow Matrix table MUST have a corresponding Pytest trace test."
tags:
- ecs
- numba
- testing
- data-flow-matrix
timestamp: "2026-08-14T00:30:00Z"
resources:
- docs/development_guide/okf_data_flow_matrix_architecture.md
- tests/integration/scientific_invariants/
trigger: always_on
rule_id: data-flow-invariants
severity: critical
---

# Mandates

- **Table-to-Trace Parity (Rule 05-A):** Every Markdown Data-Flow Matrix table MUST have a corresponding Pytest trace test in `tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`. Discrepancies between documented table values and runtime test trace arrays are treated as build-blocking failures.
- **Branchless SIMD Mask Mandate (Rule 05-B):** JIT kernels implementing Data-Flow Matrix rules must execute array transfers via scalar/vector float multiplication (`delta * alive_mask`). `if/else` conditionals on entity states in inner JIT loops are strictly prohibited in the hot path.
- **Bilateral Resource Mapping (Rule 05-C):** OKF frontmatter `resources: []` for any scientific model doc containing a Data-Flow Matrix MUST explicitly declare both the underlying system file (e.g., `src/phids/engine/systems/signaling/emission.py`) AND the corresponding trace test file.
