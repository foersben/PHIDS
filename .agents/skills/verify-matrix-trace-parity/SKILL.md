---
type: Agent Skill
title: Trigger
status: active
version: 1.0
description: Parses Markdown Data-Flow Matrix tables into dataframes and asserts
  point-by-point numerical parity against Pytest traces.
tags: [ecs, testing, data-flow-matrix]
generated: {by: process:okf-updater, at: "2026-08-14T00:30:00Z"}
name: Verify Matrix Trace Parity
sources:
- resource: docs/development_guide/okf_data_flow_matrices.md
---

# Trigger

Pre-push gate, after modifying simulation behavior equations, or dispatched by `@matrix-auditor`.

# Execution

```bash
uv run python scripts/verify_matrix_trace_parity.py --doc docs/scientific_model/morphological_defenses.md
```
