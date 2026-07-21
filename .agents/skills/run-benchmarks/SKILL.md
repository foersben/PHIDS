---
type: skill
title: Trigger
status: active
version: 0.1
description: Execute and analyze pytest-benchmark performance gates.
tags:
- documentation
timestamp: "2026-07-21T16:01:38Z"
resources: []
name: Run Benchmarks
---

# Trigger
Before merging engine logic changes or after completing a vertical slice.

# Execution
```bash
uv run pytest tests/benchmarks/ --benchmark-only --benchmark-json artifacts/benchmark_results.json
```
