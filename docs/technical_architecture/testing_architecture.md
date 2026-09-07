---
type: Concept
title: Testing Architecture & Scientific Invariant Rigor
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.2
description: Comprehensive testing architecture, taxonomy, two-pass Numba testing,
  Causal Data-Flow Matrix verification, scientific invariants, property testing,
  and performance benchmarking for PHIDS.
tags: [phids, testing, numba, hypothesis, conservation-laws, zarr, data-flow-matrix, rule-05, two-pass-testing, complexity]
generated: {by: process:okf-updater, at: "2026-08-10T19:23:45Z"}
verified: {by: process:okf-updater, at: "2026-09-07T10:45:00Z"}
sources:
- id: source
  resource: tests/integration/scientific_invariants/pde_conservation/test_advection_mass_conservation.py
- id: source_2
  resource: tests/integration/scientific_invariants/pde_conservation/test_chemical_positivity_and_clamping.py
- id: source_3
  resource: tests/integration/scientific_invariants/pde_conservation/test_convolution_exponential_decay.py
- id: source_4
  resource: tests/integration/scientific_invariants/thermodynamics/test_feeding_first_law.py
- id: source_5
  resource: tests/integration/scientific_invariants/thermodynamics/test_holling_type_ii_bounds.py
- id: source_6
  resource: tests/integration/scientific_invariants/thermodynamics/test_hill_kinetics_monotonicity.py
- id: test_causal_data_flow_matrices
  resource: tests/integration/scientific_invariants/test_causal_data_flow_matrices.py
- id: test_double_buffering_isolation
  resource: tests/integration/scientific_invariants/test_double_buffering_isolation.py
- id: test_phloem_translocation_stability
  resource: tests/integration/scientific_invariants/test_phloem_translocation_stability.py
- id: test_zarr_replay_live_parity
  resource: tests/integration/scientific_invariants/test_zarr_replay_live_parity.py
- id: test_read_layer_immutability
  resource: tests/unit/engine/invariants/test_read_layer_immutability.py
- id: test_toroidal_topological_invariants
  resource: tests/unit/engine/invariants/test_toroidal_topological_invariants.py
- id: test_jit_neighbour_gathering_parity
  resource: tests/unit/engine/invariants/test_jit_neighbour_gathering_parity.py
- id: test_jit_capacity_masking_parity
  resource: tests/unit/engine/invariants/test_jit_capacity_masking_parity.py
- id: test_movement_softmax
  resource: tests/unit/engine/systems/test_movement_softmax.py
- id: test_seed_dispersal_isotropy
  resource: tests/unit/engine/systems/test_seed_dispersal_isotropy.py
- id: test_phase_staggered_cohorts
  resource: tests/unit/engine/systems/test_phase_staggered_cohorts.py
- id: test_zarr_replay_bit_exactness
  resource: tests/e2e/replay_and_io/test_zarr_replay_bit_exactness.py
- id: run_sim_benchmark
  resource: scripts/run_sim_benchmark.py
- id: verify_matrix_trace_parity
  resource: scripts/verify_matrix_trace_parity.py
- id: audit_matrix_coverage
  resource: scripts/audit_matrix_coverage.py
---

This document aggregates PHIDS test suite topography, taxonomy, two-pass Numba execution methodology, Causal Data-Flow Matrix verification (Rule 05), scientific invariant proofs, double-buffering isolation, and performance latency governance.

## 1. Test Suite Taxonomy & Execution Topography

The PHIDS testing architecture is engineered around mathematical rigor, physical conservation laws, strict branch coverage, and deterministic execution. Rather than treating tests merely as regression shields, PHIDS treats test specifications as executable mathematical proofs of biological and physical invariants.

The testing framework is partitioned into distinct domain-focused packages so that fast unit contracts, scientific invariants, property-based exploration, and latency benchmarks evolve independently without coupling simulation physics to transport or presentation layers:

```text
tests/
├── unit/                                  # Isolated component contracts & algorithm helpers
│   ├── analytics/                         # Design Space Exploration (DSE) & EEDSE optimizer
│   ├── api/                               # Pydantic schemas, DraftState transitions, presenter logic
│   ├── cli/                               # Command-line interface entrypoints & argument parsers
│   ├── engine/
│   │   ├── core/                          # ECSWorld, GridEnvironment, SpatialHashGrid, placement
│   │   ├── invariants/                    # Double-buffering immutability, JIT parity, coordinate masks
│   │   └── systems/                       # Movement, feeding, metabolism, mitosis, signaling, triggers
│   ├── io/                                # Scenario JSON validation, draft state serialization
│   ├── pipeline/                          # Empirical trait data extraction, schemas & parquet writers
│   ├── shared/                            # Logging, constants, concurrency guards
│   └── telemetry/                         # Per-species accumulation, Polars metrics, exporters
├── integration/                           # Multi-system loop interaction & physical invariants
│   ├── api/                               # FastAPI endpoints, WebSocket streams, batch workers
│   ├── pipeline/                          # Empirical DuckDB ETL integration tests
│   ├── scientific_invariants/             # PDE conservation, thermodynamics, Data-Flow Matrices
│   │   ├── pde_conservation/             # Advection mass conservation, non-negativity, tail clamping
│   │   └── thermodynamics/                # First Law of Thermodynamics, Holling Type II, Hill kinetics
│   ├── systems/                           # Five-phase loop ordering, batch orchestration, mechanics
│   └── ui/                                # HTMX templates, partials, and presenter integration
├── e2e/                                   # Full simulation runs & data persistence
│   ├── replay_and_io/                     # Zarr telemetry buffers & bit-exact replay playback
│   └── scenarios/                         # Curated ecosystem scenarios (baseline, collapse, defense)
└── benchmarks/                            # Latency budgets & micro-benchmarks (pytest-benchmark)
```

### Partitioning & Domain Ownership

The sections below detail the responsibilities, test boundaries, and design invariants for each primary test tier:

#### A. Unit Tests (`tests/unit/`)

Isolated component contracts, data structures, and mathematical helper logic that execute without spinning up the full simulation loop:

* **`analytics/`**: Validates the Design Space Exploration (DSE) and Evolutionary Encapsulated DSE (EEDSE) subsystem:
  * `test_dse_pruning.py`: Analytical pre-pruner (`AnalyticalPruner`) asserting mathematical bounds (caloric deficits, seed costs, disconnected diet bipartite graphs) prior to expensive simulation runs.
  * `test_dse_optimizer.py`: NSGA-II multi-objective genetic algorithm optimizer (`DSEOptimizer`) sorting, Pareto front calculation, and JIT cache pre-warming on miniature grids.
  * `test_tuning.py`: Parameter sensitivity and empirical trait-mapping logic.
  * *(Note: Extensive DSE testing is deferred until core engine & database features are finalized prior to v1.0)*.
* **`api/`**: Verifies HTTP/WebSocket interface schemas, presenter functions, and state machines:
  * Validates Pydantic schema coercion, biological parameter bounds, and JSON schema compatibility.
  * Asserts atomic draft state transitions (`DraftState` $\to$ `DraftService` $\to$ Live commit).
  * Validates UI presenter components (cell inspection tooltips, badge renderers, Chart.js payload structures).
* **`cli/`**: Asserts CLI entrypoints, command-line arguments, headless execution switches, and environment variable overrides.
* **`engine/core/`**: Tests the core ECS foundation, biotope layers, and spatial indexing:
  * `test_ecs_world.py`: Verifies zero-allocation entity creation, archetypal component registration, single-writer invariants, and garbage collection (`collect_garbage`).
  * `test_placement.py`: Asserts density guarantees, boundary padding, and non-overlapping invariants for uniform, patchy, and Poisson-disc placement algorithms.
  * `test_herbivore_params_fallbacks.py`: Validates fallback parameter resolution and configuration defaults.
  * Spatial Hash Grid: Validates $O(1)$ spatial cell lookups, wrapping boundary queries, and entity relocation updates.
* **`engine/invariants/`**: Low-level computational and hardware invariant verification:
  * `test_read_layer_immutability.py`: Verifies that the `_read` layer of all biotope grids is cryptographically immutable (SHA-256 byte hashing) throughout an entire simulation step.
  * `test_numba_jit_parity.py`: Verifies numerical identity between Numba `@njit` kernels and pure-Python reference implementations.
  * `test_toroidal_topological_invariants.py`: Asserts bitwise coordinate masking (`x & (W - 1)`) parity against modular arithmetic (`x % W`) on power-of-two grids.
  * `test_jit_neighbour_gathering_parity.py`: Verifies Von-Neumann 4-neighbourhood gathering and coordinate wrapping.
  * `test_jit_capacity_masking_parity.py`: Asserts branchless float SIMD masking for carrying capacity thresholds.
  * `test_jit_zero_weight_fallback.py`: Validates numerical stability and uniform random fallback under chemically flat flow-field gradients.
* **`engine/systems/`**: Micro-contracts for individual simulation systems:
  * `test_movement_softmax.py`: Validates temperature-scaled Softmax probability distribution calculations, klinokinetic persistence vectors, and stochastic MVT departure curves.
  * `test_phase_staggered_cohorts.py`: Verifies modulo cohort gating completeness across 168-tick simulation windows.
  * `test_seed_dispersal_isotropy.py`: Validates polar seed raycasting spatial isotropy using Kolmogorov-Smirnov statistical tests.
  * Feeding & Metabolism: Asserts per-individual maintenance upkeep deductions, caloric deficit conversions into population casualties, and net-assimilation reproduction thresholds.
  * Signaling & Synthesis: Verifies plant defense volatile organic compound (VOC) synthesis, airborne emission rates, and spatial signal decay.
* **`io/`**: Verifies scenario serialization, JSON schema validation, migration edge cases, and Zarr metadata encoding.
* **`pipeline/`**: Tests empirical trait data extraction (LEDA, BIEN, GIFT, TRY, PanTHERIA), trait schemas, taxonomy mapping, and DuckDB parquet writers.
* **`shared/`**: Tests structured logging formats, shared constants, thread-safety primitives, and exception hierarchies.
* **`telemetry/`**: Validates telemetry accumulation, Polars DataFrame conversion, metric decimation, condition alarms, and multi-format exporters (CSV, PNG, LaTeX tabular, and TikZ vector code).

#### B. Integration Tests (`tests/integration/`)

Multi-system loop interactions, boundary crossings, and overarching physical conservation laws:

* **`api/`**: Verifies FastAPI routes, WebSocket telemetry streaming, SSE connection lifecycles, and batch processing worker thread governance (`test_batch_processing_thread_governance`).
* **`pipeline/`**: Tests empirical DuckDB trait extraction and archetype compilation workflows.
* **`systems/`**: Asserts deterministic phase ordering across the complete 5-phase loop execution cycle:
  1. **Flow Field Phase**: Dynamic gradient derivation, Jacobi relaxation, and chemical advection.
  2. **Lifecycle Phase**: Plant growth, seed dispersal, root mycorrhizal signal propagation, and culling.
  3. **Interaction Phase**: Swarm chemotaxis, incidental grazing, feeding, metabolic taxation, and clonal fission.
  4. **Signaling Phase**: Trigger evaluation, defense synthesis, volatile organic compound (VOC) emission, and airborne diffusion.
  5. **Telemetry & Termination Phase**: Replay buffer commits, WebSocket dispatch, and condition threshold evaluation.
* **`scientific_invariants/`**:
  * **`pde_conservation/`**: Reaction-diffusion-advection conservation laws:
    * `test_advection_mass_conservation.py`: Semi-Lagrangian mass conservation ($\nabla \cdot \vec{v} = 0$, $\text{rtol} \le 1\times 10^{-5}$) and divergent wind mass drift upper bounds ($\le 2.0\%$).
    * `test_chemical_positivity_and_clamping.py`: Chemical concentration non-negativity ($c \ge 0.0$) and subnormal float tail zeroing below `SIGNAL_EPSILON` ($1\times 10^{-4}$).
    * `test_convolution_exponential_decay.py`: Exponential spatial and temporal decay rates for diffused signals.
  * **`thermodynamics/`**: First Law of Thermodynamics and non-linear ingestion kinetics:
    * `test_feeding_first_law.py`: Energy conservation balance ($\Delta E_{\text{herbivore}} + E_{\text{digestive\_loss}} = \Delta E_{\text{plant\_consumed}}$).
    * `test_holling_type_ii_bounds.py`: Asymptotic saturation upper bounds ($I(N) \le 1/T_h$) under high resource densities.
    * `test_hill_kinetics_monotonicity.py`: Monotone increasing response curves for chemical defense induction.
  * **`test_causal_data_flow_matrices.py`**: Automated Table-to-Trace Parity tests enforcing exact 1:1 correspondence between documented OKF Data-Flow Matrices and runtime simulation traces.
  * **`test_double_buffering_isolation.py`**: Enforces strict read/write layer isolation across multi-tick loop transitions.
  * **`test_phloem_translocation_stability.py`**: Verifies rate-limited nutrient translocation stability and post-grazing apparent nutrition recovery kinetics.
  * **`test_zarr_replay_live_parity.py`**: Verifies that live simulation outputs and telemetry buffers strictly match recorded Zarr matrices.
* **`ui/`**: Verifies HTMX partial template rendering, Chart.js payload structures, and presenter integration.

#### C. End-to-End Tests (`tests/e2e/`)

Full-system scenario execution from initial state load to final termination:

* **`scenarios/`**: Executes complete ecosystem scenarios across varying temporal horizons (100 to 1,000+ ticks), asserting non-degeneracy, trophic stability, and population persistence.
* **`replay_and_io/`**:
  * `test_zarr_replay_bit_exactness.py`: Serializes multi-tick simulation runs into compressed Zarr replay buffers and verifies bit-exact numerical round-trip playback completely bypassing the engine loop.

#### D. Performance Benchmarks (`tests/benchmarks/`)

Deterministic latency benchmarks asserted via `pytest-benchmark` against pre-defined performance budgets:

* Spatial hash grid query throughput ($O(1)$ neighbour discovery).
* Sparse vs. dense Gaussian diffusion kernel execution latency.
* OpenMP multi-threaded vs. serial Jacobi flow-field relaxation.
* Power-of-two bitwise AND coordinate wrapping vs. modulo operations.
* WebSocket binary frame and JSON payload encoding throughput.
* Zarr chunk write and telemetry export serialization speeds.

## System Mapping & Test Relations

```mermaid
graph TD
    subgraph Engine["Core Simulation Engine"]
        Advection["Semi-Lagrangian Advection"]
        Diffusion["Gaussian Diffusion Kernel"]
        Feeding["Holling Type II Feeding"]
        Lifecycle["Phase-Staggered Lifecycle"]
        DoubleBuffer["Double-Buffered GridEnvironment"]
        FlowField["Jacobi Flow Field & Softmax"]
    end

    subgraph Scientific_Invariants["Scientific Invariants (tests/integration/scientific_invariants/)"]
        PDE["PDE Mass Conservation (pde_conservation/)"]
        Thermo["First Law & Hill Kinetics (thermodynamics/)"]
        Matrices["Causal Data-Flow Matrices (Rule 05)"]
    end

    subgraph JIT_Invariants["JIT & Buffer Invariants (tests/unit/engine/invariants/)"]
        ReadImmutability["SHA-256 Read-Layer Immutability"]
        JITParity["Power-of-Two Masking Parity"]
        CapacityMask["Branchless SIMD Capacity Masks"]
    end

    subgraph Loop_Integration["Loop & Transport (tests/integration/systems/ & api/)"]
        FivePhase["5-Phase Loop Ordering & Cohorts"]
        APIRoutes["FastAPI Endpoints & WebSockets"]
    end

    subgraph Replay_IO["E2E Bit-Exact Replay (tests/e2e/replay_and_io/)"]
        ZarrReplay["Zarr Float64 Matrix Roundtrip"]
    end

    Advection -.-> PDE
    Diffusion -.-> PDE
    Feeding -.-> Thermo
    DoubleBuffer -.-> ReadImmutability
    Engine -.-> JITParity
    Engine -.-> CapacityMask
    Lifecycle -.-> FivePhase
    Engine -.-> Matrices
    Engine -.-> ZarrReplay
    Engine -.-> APIRoutes
```

## 2. Two-Pass Testing Methodology

PHIDS employs a two-pass testing strategy to resolve the fundamental conflict between Numba JIT acceleration and Python test coverage instrumentation:

```mermaid
graph TD
    A["Test Invocation"] --> B{"Test Pass Selection"}
    B -->|"Pass 1: Logic & Coverage"| C["NUMBA_DISABLE_JIT=1"]
    C --> D["Python Coverage Engine (coverage.py)"]
    D --> E["Exercises all branch combinations"]
    D --> F["Asserts --cov-fail-under=80 (Actual: 84.65%)"]

    B -->|"Pass 2: JIT Parity & Latency"| G["Numba JIT Enabled (LLVM)"]
    G --> H["Parallel OpenMP & Bitwise Coordinate Kernels"]
    G --> I["Asserts bit-exact numerical parity with pure Python"]
    G --> J["Enforces pytest-benchmark latency budgets"]
```

### Pass 1: Logic & Branch Coverage (`NUMBA_DISABLE_JIT=1`)

* **Rationale**: Numba compiles decorated `@njit` kernels into optimized LLVM machine instructions. During execution, the CPU jumps directly into native machine code, completely bypassing the Python virtual machine's tracing hooks. As a result, standard Python coverage tools (`coverage.py`, `pytest-cov`) report 0% execution across compiled kernels, blinding CI quality gates to unexercised branches.
* **Mechanism**: By launching the test suite with `NUMBA_DISABLE_JIT=1`, Numba decorators execute as standard Python functions. This exposes every branch, boundary clamp, and fallback branch to `coverage.py`, ensuring strict branch coverage measurement across all algorithmic permutations.
* **Execution**:

  ```bash
  NUMBA_DISABLE_JIT=1 uv run pytest --cov=src/phids --cov-fail-under=80
  ```

### Pass 2: High-Performance Parity & Latency (JIT Enabled)

* **Rationale**: Disabling JIT proves logic correctness, but cannot verify compiler semantics, memory layout compatibility (e.g. C-contiguous NumPy arrays, explicit `int32`/`float64` types), or parallel OpenMP race conditions.
* **Mechanism**: Tests tagged with `@pytest.mark.jit_parity` and `@pytest.mark.benchmark` run with full Numba JIT compilation active (`NUMBA_DISABLE_JIT=0`). These tests execute both the pure-Python reference implementation and the compiled JIT kernel, asserting point-by-point numerical identity within floating-point tolerance ($\text{atol} \le 1\times 10^{-12}$).
* **Execution**:

  ```bash
  just test-parity
  just benchmark
  ```

## 3. Data-Flow Matrix Synchronization Protocol (Rule 05)

Every multi-tick behavioral cascade, resource translocation, and temporal state transition in PHIDS must adhere to the **Data-Flow Invariant Architecture (Rule 05)**:

1. **Table-to-Trace Parity (Rule 05-A)**:
   Every documented Data-Flow Matrix in `docs/scientific_model/` must have a corresponding, dedicated Pytest trace test in `tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`. Discrepancies between documented Markdown table rows and live simulation traces fail the build.
2. **Branchless SIMD Mask Mandate (Rule 05-B)**:
   JIT kernels implementing Data-Flow Matrix rules must execute state transfers via scalar/vector float multiplication (`delta * alive_mask`). `if/else` conditionals on entity states in inner JIT loops are strictly prohibited in the hot path.
3. **Bilateral Resource Mapping (Rule 05-C)**:
   OKF frontmatter `sources:` for any scientific model doc containing a Data-Flow Matrix must explicitly declare both the underlying system file (e.g. `src/phids/engine/systems/signaling/emission.py`) and the corresponding trace test file (`tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`).
4. **Continuous Agentic Synchronization Gate (Rule 05-D)**:
   Automated verification scripts enforce compliance in local development and CI:
   * `scripts/audit_matrix_coverage.py`: Verifies that all dynamic concept documents contain valid matrix specifications and bilateral OKF links.
   * `scripts/verify_matrix_trace_parity.py --all`: Extracts Markdown tables, runs canonical simulation traces, and asserts 1:1 point-by-point numerical parity.

### Verified Behavioral Cascades (11 Total)

| Cascade # | Behavioral Transition | Document Location | Verified Invariant |
| :--- | :--- | :--- | :--- |
| **1** | Morphological Vascular Defense | `docs/scientific_model/part_2_autotrophic_dynamics/morphological_defenses.md` | 2-tick vascular withdrawal countdown ($\tau=2$), exponential relaxation ($k=0.50$), post-grazing recovery. |
| **2** | Airborne VOC Reaction-Diffusion | `docs/scientific_model/part_3_signaling_and_transport/reaction_diffusion.md` | Metabolic investment delay, atmospheric volatilization, mortality interruption, SIMD ghost guard. |
| **3** | Herbivore Movement & Starvation | `docs/scientific_model/part_4_heterotrophic_kinematics/herbivore_behavior.md` | Circadian upkeep deduction ($\Delta E=-12.0$), starvation collapse to 0 individuals without heap deallocation. |
| **4** | Flora & Mycorrhizal Conduit | `docs/scientific_model/part_2_autotrophic_dynamics/flora_and_symbiosis.md` | Fungal conduit arrival, carbon maintenance tax ($\Delta E=-1.5$), quadratic distance decay ($0.81$). |
| **5** | Clonal Mitosis Reproduction | `docs/scientific_model/part_4_heterotrophic_kinematics/population_dynamics.md` | Modulo 168 cohort reproduction, equal population split ($20 \to 10 + 10$), energy equipartition ($50.0 \to 25.0 + 25.0$). |
| **6** | Dual-Proxy Metabolic Partition | `docs/scientific_model/future_prospects/biological_abstractions.md` | Partition between caloric energy ($E_{\text{current}}$) and physical structural biomass ($M_{\text{structural}}$). |
| **7** | Specification Master Architecture | `docs/development_guide/okf_data_flow_matrices.md` | Formal SIMD array transfer schemas, column definitions, and trace verification protocols. |
| **8** | Defense Signaling Cascade | `docs/scientific_model/computations/defense_signaling_cascade.md` | Empirical computation trace: trigger sensitivity and airborne plume dispersal. |
| **9** | Phloem Translocation Stability | `docs/scientific_model/computations/phloem_translocation.md` | Empirical computation trace: rate-limited vascular recovery kinetics. |
| **10** | Herbivore Starvation Mortality | `docs/scientific_model/computations/herbivore_starvation.md` | Empirical computation trace: caloric deficit individual cull balance. |
| **11** | Mycorrhizal Signal Propagation | `docs/scientific_model/computations/mycorrhizal_propagation.md` | Empirical computation trace: subterranean common mycelial network propagation. |

## Deep-Dive: Scientific Invariant & Physical Conservation Testing

### 1. Mathematical & Physical Foundations

Computational ecological simulations are fundamentally vulnerable to numerical artifacts. When discretized reaction-diffusion-advection PDEs, continuous Holling functional responses, and discrete multi-agent interactions run across millions of ticks, small numerical errors can compound into unphysical mass creation, artificial species extinction, or runaway energetic instabilities. The PHIDS scientific invariant testing suite enforces physical conservation laws and mathematical limits as hard system assertions.

#### Reaction-Diffusion-Advection PDE Conservation

The continuous spatio-temporal dynamics of plant defensive toxins and volatile organic compounds (VOCs) are governed by the partial differential equation:

$$\frac{\partial c(x,y,t)}{\partial t} + \vec{v}(x,y) \cdot \nabla c(x,y,t) = D \nabla^2 c(x,y,t) - \lambda c(x,y,t)$$

where $\vec{v}(x,y)$ is the wind velocity field, $D$ is the isotropic diffusion coefficient, and $\lambda$ is the chemical decay rate.

1. **Non-Divergent Wind Mass Conservation ($\nabla \cdot \vec{v} = 0$):**
   * **Mechanism:** Under a uniform wind field $\vec{v}(x,y) = (v_x, v_y)$, spatial velocity divergence is identically zero ($\nabla \cdot \vec{v} = 0$). In a continuous, closed toroidal domain, the total integrated chemical mass $M(t) = \iint_{\Omega} c(x,y,t) \,dx\,dy$ must be strictly conserved across advection steps.
   * **Implementation & Tolerance:** Tested in [test_advection_mass_conservation.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/pde_conservation/test_advection_mass_conservation.py#L18-L46) using `_numba_advect_signal_layer`. Total floating-point mass before and after backward Semi-Lagrangian advection must match to machine precision ($\text{rtol} \le 1\times 10^{-5}$).
   * **Divergent Wind Upper Bounds:** When wind vectors vary spatially ($\nabla \cdot \vec{v} \neq 0$), discrete backward interpolation introduces local numerical volume compression or expansion. We enforce a hard upper bound of $\le 2.0\%$ mass drift per step.

2. **Positivity Invariant ($c(x,y,t) \ge 0.0$):**
   * **Mechanism:** Chemical concentrations represent non-negative physical quantities (moles/$m^2$). Combined advection, Gaussian convolution, and decay must never produce negative concentrations anywhere on the grid ($c(x,y,t) \ge 0.0, \forall x,y,t$).
   * **Implementation:** Tested in [test_chemical_positivity_and_clamping.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/pde_conservation/test_chemical_positivity_and_clamping.py#L17-L49).

3. **Subnormal Float Clamping (`SIGNAL_EPSILON`):**
   * **Mechanism:** As chemical signals decay exponentially, concentration values drop into IEEE 754 subnormal (denormalized) floating-point ranges ($< 10^{-308}$). On x86_64 CPUs, processing subnormal floats in Numba FPU pipelines triggers microcode fallbacks, causing a 10x-100x performance penalty.
   * **Implementation:** `_numba_diffuse_signal_layer` explicitly zeroes out any concentration falling below `SIGNAL_EPSILON` ($1\times 10^{-4}$). Tested in [test_chemical_positivity_and_clamping.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/pde_conservation/test_chemical_positivity_and_clamping.py#L52-L80) to prove zero tail leakage.

#### Thermodynamic First Law & Non-Linear Kinetics

1. **First Law of Thermodynamics Energy Balance:**
   * **Mechanism:** In herbivory feeding interactions, energy extracted from a target plant ($\Delta E_{\text{plant\_consumed}}$) must equal the sum of net metabolized energy gained by the herbivore swarm ($\Delta E_{\text{herbivore}}$) and unassimilated digestive loss ($E_{\text{digestive\_loss}}$):

     $$\Delta E_{\text{herbivore}} + E_{\text{digestive\_loss}} = \Delta E_{\text{plant\_consumed}}$$

   * **Implementation:** Tested in [test_feeding_first_law.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/thermodynamics/test_feeding_first_law.py#L18-L98) with digestibility modifiers ($0.8$) and digestive efficiency ($0.9$). Energy conservation is verified to $\text{rel\_tol} \le 1\times 10^{-6}$.

2. **Holling Type II Functional Response Saturation:**
   * **Mechanism:** The per-individual intake rate $I(N)$ as a function of plant energy density $N$ is governed by Holling Type II kinetics:

     $$I(N) = \frac{a N}{1 + a T_h N}$$

     where $a$ is the search rate and $T_h$ is the handling time per unit biomass. As $N \to \infty$, intake rate asymptotically approaches the handling time saturation ceiling $\lim_{N \to \infty} I(N) = \frac{1}{T_h}$.
   * **Implementation:** Tested in [test_holling_type_ii_bounds.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/thermodynamics/test_holling_type_ii_bounds.py#L14-L40) using Hypothesis property testing to verify $I(N) \le \frac{1}{T_h} + 10^{-9}$ unconditionally.

3. **Monotone Hill Equation Responses:**
   * **Mechanism:** Plant defensive signaling sensitivity is modeled via the Hill equation $S(c) = \frac{c^n}{K^n + c^n}$. Physical realism requires strict monotonicity: increasing concentration $c_1 \le c_2$ must never reduce response $S(c_1) \le S(c_2)$.
   * **Implementation:** Tested in [test_hill_kinetics_monotonicity.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/thermodynamics/test_hill_kinetics_monotonicity.py#L14-L40).

#### Stochastic Spatial Isotropy & Cohort Gating

1. **Kolmogorov-Smirnov Spatial Isotropy:**
   * **Mechanism:** O(1) polar seed raycasting projects seed dispersal vectors at angles $\theta \sim U(-\pi, \pi)$. To prevent directional grid alignment bias, Cartesian reconstructed angles $\theta = \arctan2(\Delta y, \Delta x)$ over $10,000$ draws are evaluated using a two-sample Kolmogorov-Smirnov test against a continuous uniform distribution.
   * **Implementation:** Tested in [test_seed_dispersal_isotropy.py](https://github.com/foersben/PHIDS/blob/develop/tests/unit/engine/systems/test_seed_dispersal_isotropy.py#L18-L40) to enforce $p > 0.01$.

2. **Phase-Staggered Cohort Completeness:**
   * **Mechanism:** To eliminate per-tick CPU load spikes, flora lifecycle updates are phase-staggered across a 168-tick simulation window using modulo gating `(entity_id % 168) == (tick % 168)`.
   * **Implementation:** Tested in [test_phase_staggered_cohorts.py](https://github.com/foersben/PHIDS/blob/develop/tests/unit/engine/systems/test_phase_staggered_cohorts.py#L14-L38) to prove 100% of active entities are processed exactly once per 168 ticks.

#### Toroidal Topological Invariants & Softmax Temperature Scaling

1. **Toroidal Coordinate Wrapping Mathematical Proof:**
   * **Mechanism:** For power-of-two grid dimensions ($W = 2^k$), bitwise AND coordinate masking is mathematically identical to modular arithmetic:

     $$x \ \& \ (W - 1) \equiv x \pmod{W} \quad \forall x \in [-2W, 3W]$$

   * **Implementation:** Tested in [test_toroidal_topological_invariants.py](https://github.com/foersben/PHIDS/blob/develop/tests/unit/engine/invariants/test_toroidal_topological_invariants.py) across all integer coordinates including negative crossings.

2. **Softmax Temperature-Scaled Movement:**
   * **Mechanism:** Klinokinetic departure probabilities from nutrient tiles follow a temperature-scaled Softmax distribution over adjacent chemical gradients:

     $$P_i = \frac{\exp(w_i / T)}{\sum_j \exp(w_j / T)}$$

   * **Implementation:** Tested in [test_movement_softmax.py](https://github.com/foersben/PHIDS/blob/develop/tests/unit/engine/systems/test_movement_softmax.py), asserting temperature scaling, persistence vectors, and stochastic departure curves.

### 2. Rationale: Why and How We Implemented Scientific Invariant Tests

* **Why We Chose This Approach:** Standard software unit tests only check if a function returns an expected scalar given static inputs. In complex multi-agent reaction-diffusion ecosystems, functional correctness is insufficient - the engine must satisfy fundamental physical conservation laws and asymptotic mathematical bounds. Without these invariants, hidden numerical drift can invalidate scientific simulation findings.
* **How We Implemented It:** We isolated all conservation checks into dedicated subpackages ([pde_conservation/](https://github.com/foersben/PHIDS/tree/develop/tests/integration/scientific_invariants/pde_conservation) and [thermodynamics/](https://github.com/foersben/PHIDS/tree/develop/tests/integration/scientific_invariants/thermodynamics)), tagged them with `@pytest.mark.scientific_invariant`, and coupled them with exact floating-point tolerance assertions (`np.testing.assert_allclose`, `math.isclose`).

## Deep-Dive: Property-Based Testing with Hypothesis

### 1. Mechanics of Property-Based Falsification

Property-based testing radically shifts testing methodology from checking specific, hand-crafted example inputs to defining mathematical properties that must hold true across an entire generative input domain. We leverage the [Hypothesis](https://hypothesis.readthedocs.io/) framework for Python to execute bounded property-based falsification runs.

#### Generative Parameter Strategies & Falsification Engine

Rather than supplying static values (e.g. `energy = 50.0`), Hypothesis strategies generate random, boundary-focused parameter vectors across execution runs:

```python
@given(
    plant_energy=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    handling_time=st.floats(min_value=1e-4, max_value=1e2, allow_nan=False, allow_infinity=False),
)
```

1. **Targeted Domain Exploration:** Hypothesis actively samples edge-case floating-point boundaries, including subnormals, values near zero ($10^{-12}$), maximum thresholds, and numerical inflection points.
2. **Automated Counterexample Shrinking:** When Hypothesis discovers an input vector that violates a mathematical assertion, it enters a deterministic **shrinking phase**. It systematically simplifies the complex failing input down to the absolute minimal reproducible counterexample (e.g. reducing an input vector of 1,000 float elements to a single 2-element array triggering floating-point overflow).

#### Invariants Verified via Hypothesis

1. **Holling Type II Intake Upper Bounds:** Verified in [test_holling_type_ii_bounds.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/thermodynamics/test_holling_type_ii_bounds.py#L14-L40). Generates arbitrary plant energy densities and handling times $T_h$ to verify that per-individual intake $I(N)$ never exceeds the theoretical handling saturation limit $1/T_h$.
2. **Monotone Hill Equation Sensitivity:** Verified in [test_hill_kinetics_monotonicity.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/thermodynamics/test_hill_kinetics_monotonicity.py#L14-L40). Generates arbitrary concentrations $c_1 \le c_2$ to prove $S(c_1) \le S(c_2)$ across all valid Hill coefficients $n \ge 1$ and half-saturation constants $K > 0$.
3. **Convolution Exponential Decay Law:** Verified in [test_convolution_exponential_decay.py](https://github.com/foersben/PHIDS/blob/develop/tests/integration/scientific_invariants/pde_conservation/test_convolution_exponential_decay.py#L14-L42). Generates arbitrary initial mass $M_0$, decay rates $\lambda \in (0, 1)$, and tick horizons $t \in [1, 100]$ to verify $M(t) = M_0 (1 - \lambda)^t$ to relative tolerance $\text{rtol} \le 1\times 10^{-4}$.

### 2. Rationale: Why and How We Implemented Hypothesis Testing

* **Why We Chose Hypothesis:** In non-linear biological differential equations, hand-written unit tests can easily miss edge cases occurring at floating-point boundaries (e.g., handling times approaching zero or zero-division when plant density is $10^{-15}$). Hypothesis generates thousands of stochastic parameter combinations per test run, guaranteeing that mathematical bounds hold unconditionally across the continuous parameter domain.
* **How We Implemented It:** Tests are organized under `@pytest.mark.hypothesis_pilot`, configured with bounded parameter strategies (`allow_nan=False`, `allow_infinity=False`), and configured to run deterministically with Hypothesis database caching for fast CI execution.

## Deep-Dive: Mutation Testing with mutmut

### 1. Mechanics of AST Mutation & Mutant Falsification

Standard code coverage measures which lines of source code are executed during a test run, but it cannot evaluate whether the test suite's **assertions** are sensitive enough to detect subtle logic errors. A test suite can achieve 100% line coverage while failing to detect bugs if assertions are missing or weak. Mutation testing resolves this by evaluating test suite quality directly.

We use [`mutmut`](https://mutmut.readthedocs.io/) to perform deterministic AST-level mutation analysis on core simulation modules.

#### AST Transformation & Mutation Operators

`mutmut` parses Python source code into Abstract Syntax Trees (AST) and systematically introduces single artificial defects ("mutants") into the codebase:

1. **Relational Operator Mutations:** Replaces `>` with `>=`, `<` with `<=`, `==` with `!=`.
2. **Arithmetic Operator Mutations:** Replaces `+` with `-`, `*` with `/`, `&` with `|`.
3. **Logical Operator Mutations:** Replaces `and` with `or`, `True` with `False`, `is` with `is not`.
4. **Boundary & Index Modifications:** Mutates array offsets, loop boundaries, and zero-check conditionals.

#### Mutant Lifecycle

```mermaid
graph TD
    Src["Original Source Code"] --> Mutator["AST Mutation Operator"]
    Mutator --> Binary["Mutated Source Binary"]
    Binary --> Suite["Execute Pytest Suite"]
    Suite -->|Test Suite FAILS| Killed["Killed Mutant (Desired Outcome)<br/>Assertion caught the defect"]
    Suite -->|Test Suite PASSES| Surviving["Surviving Mutant (Defect Indicator)<br/>Testing gap: Assertion failed to detect mutated logic"]
```

* **Killed Mutant (Desired Outcome):** The test suite fails when executed against the mutated code, proving that test assertions actively enforce the modified logic contract.
* **Surviving Mutant (Defect Indicator):** The test suite passes despite the source code mutation, revealing a coverage gap, missing assertion, or loose tolerance.

### 2. Rationale: Why and How We Implemented Mutation Testing

* **Why We Chose Mutation Testing:** In PHIDS, hot-path array operations (`flow_field.py`, `ecs.py`, `biotope.py`) execute high-performance Numba loops. A subtle off-by-one error or misplaced comparison operator (e.g. `>` vs. `>=`) in biotope capacity checks could corrupt simulation dynamics without raising a runtime exception. Mutation testing guarantees that our test assertions actively detect and fail on any semantic deviation in engine core logic.
* **How We Implemented It:** Configured strictly for core execution paths in `pyproject.toml` (`pytest_add_cli_args_test_selection`). Executed locally via:

  ```bash
  # Run mutation testing across movement and interaction kernels
  just mutate

  # Inspect mutation results
  uv run mutmut results

  # View specific mutation diff
  uv run mutmut show <id>
  ```

## Deep-Dive: Unit Testing, Double-Buffering & JIT Parity

### 1. Mechanics of Unit Testing & Component Contracts

Unit tests in PHIDS form the foundation of the testing hierarchy under `tests/unit/`. Because the engine follows a data-oriented Entity-Component-System (ECS) pattern, entities are simple integer identifiers (`int`) and components are light data containers wrapping raw NumPy arrays or scalar primitive attributes.

#### Python Stubs & Numba JIT Bypass

To achieve sub-second unit test execution times, low-level interaction helper contracts (such as scalar coercion `_coerce_float`, trigger re-arming, and defense upkeep decay) are implemented as pure Python functions. In unit testing (`tests/unit/engine/systems/`), these functions run using standard Python stubs that bypass the `@njit` compilation boundary. This allows fast, deterministic validation of branch logic without waiting for LLVM JIT compilation overhead.

#### Cryptographic SHA-256 Double-Buffering Immutability

The simulation loop relies on strict double-buffering. Engine systems read exclusively from the immutable `_read` layer and write outcomes strictly to the `_write` layer. In-tick read state mutation violates thread safety and destroys stochastic reproducibility.

```mermaid
graph TD
    Input["System Input Phase"] --> HashInit["Compute SHA-256 Hash of _read Buffer"]
    HashInit --> Exec["Execute Simulation Loop Phase"]
    Exec --> HashFinal["Re-Compute SHA-256 Hash of _read Buffer"]
    HashFinal --> Assert["Assert Hash_Initial == Hash_Final<br/>(100% Byte-Identical Immutability)"]
```

* **Implementation:** Tested in [test_read_layer_immutability.py](https://github.com/foersben/PHIDS/blob/develop/tests/unit/engine/invariants/test_read_layer_immutability.py#L14-L45). The test extracts the underlying C-contiguous byte buffer of `_read` via `memoryview(grid.energy_layer.get_read_layer().data).tobytes()`, computes its SHA-256 digest before tick execution, runs interaction systems, and asserts that the SHA-256 digest remains 100% byte-identical prior to explicit promotion via `rebuild_energy_layer()`.

#### Numba JIT vs. Pure Python Parity

High-performance Numba kernels (`@njit(fastmath=True)`) use C-level SIMD vectorization, fast-math floating-point reassociation, and bitwise pointer manipulation. To ensure LLVM compiler optimizations introduce zero numerical drift or edge-case divergence:

1. **Power-of-Two Coordinate Wrapping & Jacobi Relaxation Parity:** Verified in [test_jit_neighbour_gathering_parity.py](https://github.com/foersben/PHIDS/blob/develop/tests/unit/engine/invariants/test_jit_neighbour_gathering_parity.py#L14-L65) and [test_flow_field.py](https://github.com/foersben/PHIDS/blob/develop/tests/unit/engine/core/test_flow_field.py). Validates that optimized bitwise AND coordinate wrapping `x & (W - 1)` and inlined Jacobi relaxation (`_propagate_iteration_jit_pow2`) produce bit-exact identical output to standard modulo reference `% W` across all toroidal grid dimensions ($W \in \{16, 32, 64, 128, 256\}$).
2. **Branchless Carrying Capacity Masking:** Verified in [test_jit_capacity_masking_parity.py](https://github.com/foersben/PHIDS/blob/develop/tests/unit/engine/invariants/test_jit_capacity_masking_parity.py#L14-L40). Validates that branchless multiplication masks (`weight * (capacity > 0.0)`) produce exact array equivalence with standard Python conditionals.

### 2. Rationale: Why and How We Implemented Unit & Parity Tests

* **Why We Chose This Approach:** Data-oriented ECS engine architectures rely on raw contiguous array memory layout. If a Numba JIT compiler optimization reorders floating-point operations or mishandles bitwise masking on wrapped grid boundaries, the simulation state will silently diverge. Unit tests isolate component array indexing and prove that JIT optimizations introduce zero numerical divergence from standard Python math.
* **How We Implemented It:** Isolated under `tests/unit/engine/invariants/`, tagged with `@pytest.mark.unit` and `@pytest.mark.jit_parity`, and executed automatically on every test run.

## Deep-Dive: Integration, E2E & Bit-Exact Zarr Replay Testing

### 1. Mechanics of Integration & Transport Boundary Testing

Integration tests operate across system boundaries, enforcing security perimeters, API data contracts, state persistence, and WebSocket real-time transport streams.

#### API Perimeter Defense & Rule of 16 Validation

FastAPI route handlers (`src/phids/api/routers/`) sit at the perimeter of the application. Integration tests in `tests/integration/api/`:

1. **HTTP Status Code Enforcement:** Verify that invalid or malformed JSON payloads return explicit HTTP error codes (`400 Bad Request`, `422 Unprocessable Entity`, `404 Not Found`) before reaching server-side state (`DraftState`).
2. **Rule of 16 Capacity Enforcements:** Verify that requests attempting to register more than 16 active substance or defense parameters are rejected, protecting static memory bounds across array allocations.
3. **WebSocket Transport Durability:** Stream resilience tests (`test_websocket_manager.py`) verify client connection handshakes, graceful teardown on `WebSocketDisconnect`, frame serialization performance, and snapshot cache reuse for ticks where the simulation loop has not advanced.

#### E2E Scenario Execution

End-to-End (E2E) tests (`tests/e2e/scenarios/`) execute complete multi-system simulation runs using baseline JSON scenario configurations (e.g. `examples/dry_shrubland_cycles.json`). The test runner initializes the `ECSWorld`, `GridEnvironment`, and `SimulationLoop`, executing the full 5-phase tick lifecycle:

$$\text{Flow Field Phase} \longrightarrow \text{Lifecycle Phase} \longrightarrow \text{Interaction Phase} \longrightarrow \text{Signaling Phase} \longrightarrow \text{Telemetry Phase}$$

E2E tests verify macro-level ecological convergence: ensuring multi-species populations stabilize, energy balances remain positive, and loop execution terminates cleanly upon reaching max ticks or extinction thresholds.

#### Bit-Exact Zarr Replay Verification

To support scientific telemetry analysis and UI timeline playback, simulation outcomes are recorded tick-by-tick into Zarr v3 chunked array stores using `ZarrReplayWriter`.

```mermaid
graph TD
    Loop["Simulation Execution Loop"] --> Write["Write Tick Matrices"]
    Write --> Buffer["Zarr Replay Buffer (.zarr)"]
    Buffer --> Bypass["Bypass Simulation Engine"]
    Bypass --> Reader["Zarr Replay Reader"]
    Reader --> Frame["Read Frame Matrix"]
    Frame --> Assert["Assert Bit-Exact Matrix Equality<br/>(Zero Floating-Point Deviation)"]
```

* **Engine Bypass Mandate:** Playback must read historical spatial matrices directly from Zarr buffers, completely bypassing `SimulationLoop` systems and Numba JIT kernels.
* **Bit-Exactness Assertion:** Verified in [test_zarr_replay_bit_exactness.py](https://github.com/foersben/PHIDS/blob/develop/tests/e2e/replay_and_io/test_zarr_replay_bit_exactness.py#L14-L45). The test records 50 simulation ticks into a Zarr buffer, initializes a `ZarrReplayReader`, reads back historical Float64 matrices for biotope energy, plant biomass, and toxin fields, and compares them against live tick snapshots using `np.testing.assert_array_equal`. This proves zero floating-point loss or matrix corruption across serialization boundaries.

### 2. Rationale: Why and How We Implemented Integration & Replay Tests

* **Why We Chose This Approach:** Scientific analysis requires post-hoc exploration of spatial simulation runs without incurring the computational cost of re-running the simulation engine. Bit-exact Zarr testing guarantees that the telemetry pipeline preserves 100% of spatial precision, while API integration tests protect server state from invalid user requests.
* **How We Implemented It:** Integration tests are grouped under `tests/integration/api/` and `tests/e2e/replay_and_io/`, utilizing Pytest fixtures (`client`, `tmp_path`) to manage temporal Zarr storage directories and API server lifecycles.

## Deep-Dive: Performance Benchmarking & Cross-Commit Comparison

### 1. Mechanics of Latency Budgets & Throughput Comparison

Performance regressions in high-performance simulation software are often difficult to detect through functional testing alone. A refactoring might preserve functional correctness while accidentally degrading throughput from 1,000 ticks/sec down to 100 ticks/sec due to unwanted array re-allocation or FPU microcode traps.

#### `pytest-benchmark` Execution Budgets

Micro-benchmarks (`tests/benchmarks/`) isolate hot-path algorithms:

1. **Diffusion & Flow Field Latency Budgets:** Measures execution duration per tick for Gaussian diffusion (`test_diffusion_sparse_fast_path_benchmark`) and spatial hash queries (`test_spatial_hash_query_benchmark`).
2. **Environment-Overridable Thresholds:** Failing and warning mean latency limits are configurable via environment variables (e.g. `PHIDS_DIFFUSION_SPARSE_WARN_MEAN_MS=2.5`), preventing false positives on heterogeneous CI hardware.
3. **Statistical Outlier Analysis:** Computes Operations Per Second (OPS), Mean, Median, and InterQuartile Range (IQR), enforcing $p_{95}$ latency thresholds.

#### Cross-Commit & JIT Benchmarking Utility (`run_sim_benchmark.py`)

To evaluate macro-level engine throughput across Git commits, refactorings, or JIT compilation states:

```bash
just bench-compare <commit1> <commit2> examples/ 500 3
just bench-compare-jit 17d6980 worktree examples/ 100 5
```

1. **Workspace Isolation:** Uses a temporary local repository clone (`.cache/bench_clone`) to perform checkouts of target commits. Active uncommitted modifications in the primary workspace remain untouched.
2. **`worktree` Reference Mode:** Supports comparing a historical commit against uncommitted working tree changes using the `worktree` pseudo-ref.
3. **JIT Warmup Phase:** Runs 10 initial warmup ticks to allow Numba LLVM compilation to complete before starting statistical timers, measuring execution throughput rather than compilation latency.

### 2. Rationale: Why and How We Implemented Performance Benchmarking

* **Why We Chose This Approach:** Real-time web UI dashboards and interactive simulation loops require strict sub-millisecond per-tick budgets to maintain fluid visual updates. Benchmarking isolates performance regressions immediately at commit time.
* **How We Implemented It:** Configured under `tests/benchmarks/` with `pytest-benchmark`, combined with the [run_sim_benchmark.py](https://github.com/foersben/PHIDS/blob/develop/scripts/run_sim_benchmark.py) CLI utility for multi-commit throughput comparisons.

## Quality Analysis & Governance Rules

### 1. Atomic Test Decomposition & God Test Policy

* **Prohibition:** Multi-branch "God Tests" that chain multiple state transitions or unrelated subsystem checks into a monolithic test function are strictly prohibited.
* **Requirement:** Tests must be decomposed into narrowly-scoped atomic functions targeting a single state transition, error condition, or invariant.

### 2. Cognitive Complexity Budget ($\le 15$)

All test and production functions must respect a cognitive complexity budget $\le 15$ measured via Complexipy (`just complexity`). Deeply nested branching logic must be refactored into atomic, single-responsibility helper functions or branchless SIMD array masks:

```bash
# Run repository-wide cognitive complexity check
just complexity
```

### 3. Google-Style Documentation Mandate

Every test module, class, and test function must include Google-style docstrings declaring:

* The specific biological or mathematical invariant under test.
* Governing physical formulas, mathematical equations, or conservation laws.
* `Args` (for fixtures and Hypothesis strategies).
* `Raises: AssertionError` documenting the failure condition.

### 4. Strict Branch Coverage Floor & Diff Coverage

Branch coverage is evaluated project-wide (`branch = true` in `pyproject.toml`). All pull requests and test runs must satisfy two independent coverage gates:

1. **Global Branch Coverage:** $\ge 80.0\%$ across the entire `src/phids/` codebase (currently **84.65%**).
2. **Diff Coverage:** $\ge 80.0\%$ branch coverage on modified lines compared against `origin/main` (currently **89.0%**).

Target specific test slices during local development:

```bash
scripts/target_cov.sh tests/unit/engine/core/test_ecs_world.py phids.engine.core.ecs
```

### 5. Mutation Testing (`mutmut`)

Deterministic mutation testing is applied to hot-path algorithms (`flow_field.py`, `ecs.py`, `biotope.py`) to verify that test assertions kill mutants altering binary branch conditions or mathematical operators:

```bash
# Run mutation testing
just mutate

# Inspect mutation testing results
uv run mutmut results
```

### 6. Registered Pytest Custom Markers

| Marker | Description | Typical Invocation |
| :--- | :--- | :--- |
| `unit` | Isolated component, presenter, and helper tests | `uv run pytest -m unit` |
| `scientific_invariant` | High-level scientific, thermodynamic, and PDE conservation tests | `just test-scientific` |
| `hypothesis_pilot` | Property-based invariant tests using Hypothesis | `uv run pytest -m hypothesis_pilot` |
| `jit_parity` | Equivalence checks comparing compiled Numba kernels with pure Python | `just test-parity` |
| `benchmark` | Micro-benchmarks measuring latency against predefined budgets | `just benchmark` |
| `mutation_pilot` | Mutation resistance validation tests | `uv run pytest -m mutation_pilot` |

## Test Isolation, Fixtures, and Cleanup Contracts

To ensure deterministic and reproducible test execution, PHIDS enforces strict isolation contracts for test environments, leveraging Pytest fixtures and controlled cleanup procedures.

### 1. Fixture Isolation Contracts

All integration and end-to-end tests must rely exclusively on Pytest fixtures (`tmp_path`, `client`, `db_session`) to manage isolated environments. Direct interaction with the global filesystem, active SQLite databases, or the live FastAPI test client instance is prohibited. Test logic must be expressed solely through fixture interfaces, ensuring that each test executes within its own ephemeral state context without side effects.

### 2. `tmp_path` Temporal Storage Isolation

For scenario execution and telemetry pipeline validation, tests must utilize the `tmp_path` fixture to provision temporary on-disk directories for Zarr telemetry storage. This isolation contract guarantees that all temporal array data is confined to the ephemeral filesystem and automatically cleaned upon test completion, preventing filesystem state leakage between test runs.

### 3. `ZarrReplayReader` Non-Mutation Contract

Temporal playback functionality must utilize `ZarrReplayReader` instances that operate strictly in read-only mode. These instances must bypass all mutable system components and write operations, ensuring that post-hoc scientific analysis cannot modify simulation states or telemetry buffers. The immutability contract guarantees that historical data remains invariant to analytical queries.

### 4. Deterministic Test Cleanup

All Pytest test functions must conclude with explicit cleanup assertions that verify environment state has been restored. This includes:

* Verifying that ephemeral Zarr storage paths have been released or garbage-collected.
* Asserting that no persistent data or file handles remain open after function execution.
* Validating that FastAPI test clients are properly closed and session contexts are released.

### 5. Isolation Rationale

This architecture enforces isolation to:

* **Guarantee Reproducibility:** Ensures that test outcomes depend only on explicit inputs and fixture states, not on filesystem or database states from preceding tests.
* **Prevent Side Effects:** Eliminates cross-test contamination, especially critical for high-concurrency systems involving JIT-compiled code and in-memory state management.
* **Enable Safe Temporal Analysis:** Guarantees that post-hoc replay and validation workflows do not corrupt or overwrite historical telemetry buffers.

## 8. Common Developer Recipes & Command Reference

| Goal | Command / Recipe | Environment & Flags |
| :--- | :--- | :--- |
| **Run Full Test Suite** | `just test` | Standard pytest with benchmarks enabled |
| **Full Coverage Pass** | `NUMBA_DISABLE_JIT=1 uv run pytest --cov=src/phids --cov-fail-under=80` | Disables JIT for 100% Python branch tracing |
| **Diff Coverage Check** | `just test-diff-cover` | Evaluates branch coverage against `origin/main` |
| **Scientific Invariants** | `just test-scientific` | Runs `-m scientific_invariant` with `--no-cov` |
| **JIT Parity Checks** | `just test-parity` | Runs `-m jit_parity` with compiled Numba kernels |
| **Data-Flow Matrix Audit** | `just audit-matrix` | Verifies OKF coverage across scientific concepts |
| **Table-to-Trace Parity** | `just verify-matrix` | Asserts 1:1 numerical parity against doc tables |
| **Zarr Replay Parity** | `just test-replay` | Tests bit-exact Zarr matrix round-trip playback |
| **Performance Benchmarks** | `just benchmark` | Runs latency micro-benchmarks via pytest-benchmark |
| **Cognitive Complexity** | `just complexity` | Evaluates Complexipy cognitive complexity ($\le 15$) |
| **Code Formatting & Lint** | `just lint` | Runs `ruff check --fix`, `ruff format`, and strict `mypy` |
| **Full Pre-Commit Suite** | `uv run pre-commit run --all-files` | Executes all 18 pre-commit quality gates |
