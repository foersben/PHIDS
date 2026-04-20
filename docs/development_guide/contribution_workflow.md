# Contribution Workflow

Modifying the Plant-Herbivore Interaction & Defense Simulator requires strict adherence to scientific computing constraints. The engine is deliberately deterministic; introducing stochastic or unoptimized logic can violate the reproducibility of the entire ecosystem.

## Local Environment Management

Development is exclusively managed by the `uv` toolchain, ensuring extremely fast dependency resolution and deterministic virtual environments.

```bash
uv sync --all-extras --dev
uv run phids --reload
```

## The Quality Gate Sequence

Before a contribution can be merged into `main` or `develop`, it must successfully traverse a rigorous staging pipeline that asserts performance, syntax, and typing bounds.

1.  **Linting & Formatting**: Enforced identically across developer machines via `ruff`. Any code style deviations or unused imports will halt the gate.
2.  **Static Typing**: The `mypy` static type checker targets `src/phids` with strict mode enabled. `Any` suppression is explicitly rejected at the boundary layers to maintain pure object parsing.
3.  **Testing & Coverage**: Extensive unit and integration tests are required (`pytest`). To ensure broad resilience, `pytest-cov` enforces specific coverage thresholds before passing.
4.  **Performance Verification**: The crucial `pytest-benchmark` suite actively monitors the execution time of numerical kernels (like the Numba JIT gradients and the Spatial Hash). Introducing code that degrades a hot-path loop will result in a rejected CI build.
5.  **Documentation Build**: Changes must not break existing site structures, internal relative links, or LaTeX equations. Every run strictly executes `mkdocs build --strict`.

## The Two-Stage Pre-Commit Model

To improve developer iteration speed without compromising the integrity of the repository, PHIDS enforces a split-hook topology for `pre-commit`:

-   **Commit Stage**: Executes fast hooks. It normalizes trailing whitespaces, end-of-file carriage returns, and structural validations for JSON and YAML files.
-   **Push Stage**: Rather than forcing a 30-second wait on every local commit, the heavy operational commands (`pytest`, `mypy`, `mkdocs build --strict`) are deferred until the developer attempts to push the branch to the remote origin.

```bash
# Install the split hooks
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

## Benchmark-Sensitive Paths

Edits to the following files require extreme caution. They sit on the critical execution path of the simulation tick, and sub-optimal $O(N)$ logic here will catastrophically degrade the continuous rendering capability:

-   `src/phids/engine/core/flow_field.py` (Global guidance gradient logic)
-   `src/phids/engine/core/biotope.py` (Gaussian diffusion arrays)
-   `src/phids/engine/core/ecs.py` (Spatial hashing and collision checks)
