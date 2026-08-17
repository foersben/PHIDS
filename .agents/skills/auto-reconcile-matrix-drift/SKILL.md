---
type: Agent Skill
title: Trigger
status: stable
stale_after: "2027-01-01"
version: 1.0
description: Runs a trace session, captures exact numerical output, and
  automatically updates the Markdown table rows when parameters drift.
tags: [automation, reconciliation, data-flow-matrix]
generated: {by: process:okf-updater, at: "2026-08-14T00:30:00Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
name: Auto Reconcile Matrix Drift
sources:
- id: okf_data_flow_matrices
  resource: docs/development_guide/okf_data_flow_matrices.md
---

# Trigger

Dispatched by `@matrix-auditor` or `@causal-verifier` when runtime traces diverge from documented markdown tables after intentional parameter updates.

# Execution

```bash
uv run python scripts/reconcile_matrix_drift.py --doc docs/scientific_model/morphological_defenses.md
```
