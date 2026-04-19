# Contribution Workflow

Modifying PHIDS requires adherence to stringent scientific computing constraints. Changes must not introduce unpredictable performance variations or violate the strict data-oriented ECS boundaries.

## Local Environment

Development is exclusively managed by `uv`.

```bash
uv sync --all-extras --dev
uv run phids --reload
```

## The Quality Gate Sequence

Before contributions are accepted into the `main` or `develop` branches, they must pass rigorous staging:
- **Linting & Formatting**: Enforced via `ruff`.
- **Static Typing**: Strict `mypy` evaluations targeting `src/phids`.
- **Testing**: Requires `pytest` and specific coverage thresholds (`pytest-cov`). Crucially, benchmark tests (`pytest-benchmark`) monitor the execution time of Numba routines and Spatial Hashing structures. Regressions in hot-path loops will fail the build.
- **Documentation Build**: Changes must build successfully via `mkdocs build --strict`.

## The Two-Stage Pre-Commit Model

PHIDS enforces split hooks to distinguish fast syntax fixes from heavy compilations:
1. **Commit Stage**: Executes fast linters, trailing-whitespace checks, and basic structural validations (JSON/YAML).
2. **Push Stage**: Runs the heavy operational commands (`pytest`, `mypy`, `mkdocs build --strict`) before the repository accepts the commit sequence.

## Benchmark-Sensitive Paths

Edits to the following files require extreme caution and mandatory performance verification:
- `src/phids/engine/core/flow_field.py` (JIT global gradient)
- `src/phids/engine/core/biotope.py` (Diffusion routines)
- `src/phids/engine/core/ecs.py` (O(1) Spatial hashing operations)
