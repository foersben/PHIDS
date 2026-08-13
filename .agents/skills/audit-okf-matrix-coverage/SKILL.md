---
type: skill
title: Trigger
status: active
version: 1.0
description: Scans docs/scientific_model/ files and reports any concept document that describes temporal state shifts without a Data-Flow Matrix Table.
tags:
- docs
- okf
- audit
- data-flow-matrix
timestamp: "2026-08-14T00:30:00Z"
resources:
- docs/development_guide/okf_data_flow_matrix_architecture.md
name: Audit OKF Matrix Coverage
---

# Trigger

Dispatched periodically by `@matrix-auditor` or during documentation completeness audits.

# Execution

```bash
uv run python scripts/audit_matrix_coverage.py --dir docs/scientific_model/
```
