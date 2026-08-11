# PHIDS Test Suite & Verification Architecture

The PHIDS testing rig is architected around mathematical rigor, physical conservation laws, strict branch coverage, and deterministic execution. The test suite is organized into distinct, domain-focused packages so that fast unit checks, scientific invariants, property-based tests, and performance benchmarks can evolve independently.

## Test Topography & Package Directory Map

* `tests/unit/` — Isolated component contracts and low-level system helper logic.
  * `api/`: Schema validation, UI state transitions (`DraftState`), and route helper presenter logic.
  * `analytics/`: Differential Stability Explorer (DSE) candidate pruning and optimizer unit checks. *(Note: Extensive DSE testing is deferred until core engine & database features are finalized prior to v1.0)*.
  * `engine/core/`: ECS registry (`ECSWorld`), biotope grid allocations, spatial hash indexing, and parameter fallbacks.
  * `engine/systems/`: Modulo gating, stochastic polar seed raycasting, and interaction helper contracts (bypassing Numba JIT overhead).
  * `engine/invariants/`: Cryptographic read-layer immutability (SHA-256 byte hashing), Numba JIT vs. pure Python reference parity, bitwise AND coordinate wrapping `& (W-1)`, inlined Jacobi flow-field relaxation (`_propagate_iteration_jit_pow2`), branchless capacity masking, and zero-weight Softmax fallbacks.
  * `io/`: Scenario I/O serialization and schema validation.
  * `telemetry/`: Per-species telemetry accumulation and Polars metric-shape checks.
  * `shared/`: Logging, constants, and utility-layer invariants.
  * `cli/`: Command-line entrypoint and namespace compatibility tests.
* `tests/integration/` — Multi-system loop interaction, FastAPI boundaries, and physical invariants.
  * `api/`: Route, WebSocket, and export pipeline behavior across FastAPI boundaries and UI builder flows.
  * `systems/`: Multi-system simulation interactions, loop execution phases, and batch orchestration.
  * `scientific_invariants/`:
    * `pde_conservation/`: Reaction-diffusion-advection PDE conservation laws. Validates Semi-Lagrangian mass conservation ($\nabla \cdot \vec{v} = 0$), divergent wind mass drift upper bounds ($\le 2.0\%$), chemical non-negativity ($c \ge 0.0$), and subnormal float tail clamping below `SIGNAL_EPSILON` ($1\times 10^{-4}$).
    * `thermodynamics/`: First Law of Thermodynamics energy balance ($\Delta E_{\text{herbivore}} + E_{\text{digestive\_loss}} = \Delta E_{\text{plant\_consumed}}$), Holling Type II functional response asymptotic upper bounds ($I(N) \le 1/T_h$), and monotone Hill kinetics ($c_1 \le c_2 \implies S(c_1) \le S(c_2)$).
* `tests/e2e/` — End-to-end scenario execution and data persistence.
  * `scenarios/`: Curated scenario fixture execution and full-loop integration checks.
  * `replay_and_io/`: Zarr telemetry buffer persistence, float64 matrix round-trips, and bit-exact playback verification.
* `tests/benchmarks/` — Deterministic latency benchmarks and performance budgets (`pytest-benchmark`).

## Core Invariant & Scientific Verification Strategy

### 1. Scientific & Physical Invariant Rigor
Computational simulation logic must mirror physical laws and biological models to exact floating-point precision:
- **Mass & Energy Conservation**: Advection under non-divergent wind fields conserves mass to $\text{rtol} \le 1\times 10^{-5}$. Herbivory feeding events conserve energy per the First Law of Thermodynamics to $\text{rel\_tol} \le 1\times 10^{-6}$.
- **Non-Linear Kinetics**: Holling Type II consumption rates are strictly bounded by handling time saturation ($1/T_h$). Hill equation responses are proven monotonic.
- **Stochastic Spatial Isotropy**: Polar seed raycasting ($\theta \sim U(-\pi, \pi)$) is verified via Kolmogorov-Smirnov statistical testing ($p > 0.01$) to eliminate spatial directional bias.
- **Phase-Staggered Cohort Completeness**: Modulo cohort gating (`(entity_id % 168) == (tick % 168)`) guarantees every active plant entity is updated exactly once per 168-tick simulation window.

### 2. Hypothesis Property-Based Testing
Bounded stochastic exploration using Hypothesis (`@pytest.mark.hypothesis_pilot`) validates that mathematical equations hold unconditionally across generated input domains (e.g. exponential decay law $M(t) = M_0 (1-\lambda)^t$, Hill kinetics monotonicity, and Holling Type II intake bounds).

### 3. Double-Buffering & Memory Immutability
All ECS systems and `GridEnvironment` layers enforce double-buffering. The `_read` layer is cryptographically hashed (SHA-256) before simulation steps to prove zero in-tick read mutations occur prior to explicit promotion via `rebuild_energy_layer()`.

### 4. Mutation Testing (`mutmut`)
Mutation testing is used to verify that test suites detect semantic mutations in hot-path algorithms (`flow_field.py`, `ecs.py`, `biotope.py`). Run mutmut locally:
```zsh
uv run mutmut run
uv run mutmut results
```

## Code Quality & Coverage Governance

### Atomic Test Decomposition & God Test Policy
Multi-branch "God Tests" that chain unrelated operations are strictly banned. All tests must be decomposed into narrowly-scoped, atomic test functions that target a single invariant or state transition.

### Google-Style Documentation Mandate
Every test module, class, and function must include detailed Google-style docstrings documenting:
- The biological or mathematical invariant under test.
- Mathematical formulas or physical laws.
- `Args` (for Hypothesis strategies or fixtures).
- `Raises: AssertionError` for invariant violations.

### Pytest Custom Markers
The following registered markers categorize test runs:
- `unit`: Isolated component and helper unit tests.
- `scientific_invariant`: High-level scientific, thermodynamic, and PDE conservation tests.
- `hypothesis_pilot`: Property-based invariants using Hypothesis.
- `jit_parity`: Equivalence checks comparing Numba `@njit` kernels with pure Python references.
- `benchmark`: Performance-regression latency benchmarks.
- `mutation_pilot`: Deterministic mutation-resistance test pilots.

### Strict Branch Coverage Floor
Branch coverage is enabled project-wide (`branch = true` under `[tool.coverage.run]`). All pull requests and test runs must satisfy `--cov-fail-under=80` (minimum 80.0% branch coverage). Target specific coverage slices using:
```zsh
scripts/target_cov.zsh tests/unit/engine/core/test_ecs_world.py phids.engine.core.ecs
```
