---
type: skill
title: Trigger
status: active
version: 1.0
description: Runs a trace session, captures exact numerical output, and automatically updates the Markdown table rows when parameters drift.
tags:
- automation
- reconciliation
- data-flow-matrix
timestamp: "2026-08-14T00:30:00Z"
resources:
- docs/development_guide/okf_data_flow_matrix_architecture.md
name: Auto Reconcile Matrix Drift
---

# Trigger

Dispatched by `@matrix-auditor` or `@causal-verifier` when runtime traces diverge from documented markdown tables after intentional parameter updates.

# Execution

```bash
uv run python scripts/reconcile_matrix_drift.py --doc docs/scientific_model/morphological_defenses.md
```
