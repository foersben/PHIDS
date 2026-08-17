---
type: Agent Skill
title: Trigger
status: stable
stale_after: "2027-01-01"
version: 1.0
description: Scans docs/scientific_model/ files and reports any concept document
  that describes temporal state shifts without a Data-Flow Matrix Table.
tags: [docs, okf, audit, data-flow-matrix]
generated: {by: process:okf-updater, at: "2026-08-14T00:30:00Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
name: Audit OKF Matrix Coverage
sources:
- id: okf_data_flow_matrices
  resource: docs/development_guide/okf_data_flow_matrices.md
---

# Trigger

Dispatched periodically by `@matrix-auditor` or during documentation completeness audits.

# Execution

```bash
uv run python scripts/audit_matrix_coverage.py --dir docs/scientific_model/
```
