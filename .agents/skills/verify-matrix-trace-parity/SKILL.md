---
type: skill
title: Trigger
status: active
version: 1.0
description: Parses Markdown Data-Flow Matrix tables into dataframes and asserts point-by-point numerical parity against Pytest traces.
tags:
- ecs
- testing
- data-flow-matrix
timestamp: "2026-08-14T00:30:00Z"
resources:
- docs/development_guide/okf_data_flow_matrix_architecture.md
name: Verify Matrix Trace Parity
---

# Trigger

Pre-push gate, after modifying simulation behavior equations, or dispatched by `@matrix-auditor`.

# Execution

```bash
uv run python scripts/verify_matrix_trace_parity.py --doc docs/scientific_model/morphological_defenses.md
```
