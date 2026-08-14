---
type: Agent Skill
title: Trigger
status: active
version: 1.0
description: Runs a trace session, captures exact numerical output, and
  automatically updates the Markdown table rows when parameters drift.
tags: [automation, reconciliation, data-flow-matrix]
generated: {by: process:okf-updater, at: "2026-08-14T00:30:00Z"}
name: Auto Reconcile Matrix Drift
sources:
- resource: docs/development_guide/okf_data_flow_matrices.md
---

# Trigger

Dispatched by `@matrix-auditor` or `@causal-verifier` when runtime traces diverge from documented markdown tables after intentional parameter updates.

# Execution

```bash
uv run python scripts/reconcile_matrix_drift.py --doc docs/scientific_model/morphological_defenses.md
```
