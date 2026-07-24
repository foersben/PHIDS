---
type: skill
name: Run Benchmarks
description: Execute and analyze pytest-benchmark performance gates.
---
# Trigger
Before merging engine logic changes or after completing a vertical slice.

# Execution
```bash
uv run pytest tests/benchmarks/ --benchmark-only --benchmark-json artifacts/benchmark_results.json
```
