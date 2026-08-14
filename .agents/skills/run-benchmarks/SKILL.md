---
type: Agent Skill
title: Trigger
status: stable
stale_after: "2027-01-01"
version: 0.1
description: Execute and analyze pytest-benchmark performance gates.
tags: [documentation]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
name: Run Benchmarks
---

# Trigger

Before merging engine logic changes or after completing a vertical slice.

# Execution

```bash
uv run pytest tests/benchmarks/ --benchmark-only --benchmark-json artifacts/benchmark_results.json
```
