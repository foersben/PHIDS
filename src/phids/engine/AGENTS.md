# PHIDS Engine Domain - Quick-Reference Constraints

Full constraints are in `.agents/rules/02-numba-constraints.md` and
`.agents/rules/01-stochastic-engine-and-replay.md`. Load those for detail.

## Critical Summary

* OOP inside engine core is BANNED. Entities = ints. Components = NumPy arrays.
* No `dict`/`list` inside `@njit`. Float masks only (0.0/1.0). No if/else branching.
* Double-buffer: read current layer; write ONLY to `_write` layer.
* Zero-allocation gating: `.max() >= EPSILON`, NOT `np.any(arr >= EPSILON)`.
* Never extract helpers inside `@njit` (Numba cannot JIT-compile closures).
* No dynamic imports inside per-tick entity loops.

## Pre-Commit Gate (REQUIRED for all engine commits)

```bash
uv run python scripts/audit_matrix_coverage.py
uv run python scripts/verify_matrix_trace_parity.py --all
uv run pytest tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
uv run ruff check src/ && uv run mypy src/
```

Role: `03-engine-developer`.
