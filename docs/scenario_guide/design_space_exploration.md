---
type: concept
title: "Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE): Master Architectural Specification"
status: active
version: 3.0
description: The Plant-Herbivore Interaction & Defense Simulator (PHIDS) utilizes an **Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE)** architecture.
tags:
- phids
- ecs
- numba
- chemotaxis
- eedse
- optimization
timestamp: "2026-08-03T12:00:00Z"
resources: []
---

!!! warning "Module Status: Work In Progress (WIP/CIP) / Construction Site"
    The Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE) subsystem and its underlying optimization pipelines are strictly a Work-In-Progress (WIP) and Context-In-Process (CIP) construction site. Furthermore, **AI is not used as a massive black box anywhere in this architecture**. Any AI-in-the-loop features serve strictly to assist and evaluate configurations alongside Human-in-the-loop (HITL) processes, ensuring full biological interpretability. The APIs, algorithms, and UI panels described in this document are subject to continuous refinement.

## Abstract

The Evolutionary Encapsulated Multi-Stage Design Space Exploration (EEDSE) framework is the primary optimization and scenario discovery engine of the Plant-Herbivore Interaction & Defense Simulator (PHIDS). High-dimensional ecosystem spaces ($100+$ continuous traits and discrete choice matrices across multiple species) suffer from exponential sample complexity ($O(2^N)$). Directly evaluating thousands of candidate scenarios in high-fidelity spatiotemporal physics engines is computationally intractable ($T_{sim} \approx 0.85\text{ ms/tick}$).

EEDSE solves this bottleneck through structural encapsulation:

* **Macro Delimitation (Pre-Phase / One-Time Ingress)**: Executes once prior to the optimization loop to restrict the infinite search volume to an empirically anchored, requirement-bounded initial hyper-cube ($\mathcal{X}_{init}$).
* **Encapsulated Evolutionary Loop (Phases 2–4)**:
    * **Genotype Sub-DSE (Fast Heuristic Optimization)**: Evaluates sub-components using fast algebraic/combinatorial solvers (MILP/MINLP) to output candidate Pareto-fronts in $O(\text{ms})$.
    * **Phenotype High-Fidelity Validation**: Instantiates candidate genotypes into concrete spatiotemporal simulations, applying multi-criteria pruning and relativizing metrics into a Unified Normalized Fitness Vector ($\mathbf{J}_{sys}$).
    * **Database & Epistemic Learning (Closed-Loop Feedback)**: Stores (phenotype, generation) pairs in Zarr/DuckDB, calculates error deltas ($\mathbf{\Delta}_{epistemic}$) to recalibrate surrogate solvers, and feeds updated parameters directly back into the next generation of **Genotypes**.

## 1. Complete Workflow & Data Artifact Topology

```mermaid
flowchart TD
    %% Styling matched to the architectural conceptual model
    classDef initial fill:#f39c12,stroke:#d35400,stroke-width:2px,color:#fff;
    classDef genotype fill:#2ecc71,stroke:#27ae60,stroke-width:2px,color:#fff;
    classDef phenotype fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff;
    classDef database fill:#34495e,stroke:#2c3e50,stroke-width:2px,color:#fff;

    %% One-Time Initial Ingress
    Init(["Initial Pre-Phase<br/>Design Space Delimitation"]):::initial

    %% Encapsulated Evolutionary Loop Nodes
    G{{"Genotypes<br/>(Heuristic Sub-DSE Solvers)"}}:::genotype
    P{{"Phenotypes<br/>(High-Fidelity Validation)"}}:::phenotype
    DB[("Database & Epistemic<br/>Learning Feedback")]:::database

    %% Workflow Edges
    Init -- "Initial Design Spaces<br/>& DSE Models" --> G
    G -- "Pareto-Efficient Solutions<br/>(Configuration Candidates)" --> P
    P -- "Transfer Selected:<br/>Phenotype Evaluation Results" --> DB
    DB -- "Evolutionary Tools Update:<br/>Bounds, Weights, Parameters" --> G
```

## 2. Deep-Dive Subsystem Specifications & Mathematical Invariants

### 2.1 Macro-Phase 1: Design Space Delimitation (Pre-Phase)

The delimitation pre-phase executes once prior to starting the evolutionary loop. It establishes the bounded search hyper-cube $\mathcal{X}_{init} \subset \mathbb{R}^n \times \mathbb{Z}^m$.

$$
\mathcal{X}_{init} = \left\{ \mathbf{x} \in \mathbb{R}^n \times \mathbb{Z}^m \; \middle\vert{} \; \mathbf{g}_{req}(\mathbf{x}) \le \mathbf{0}, \; \mathbf{h}_{thermo}(\mathbf{x}) \le \mathbf{0}, \; \mathbf{x}_{L} \le \mathbf{x} \le \mathbf{x}_{U} \right\}
$$

* **Requirements-Based Pre-Pruning**: Hard scenario requirements act as preliminary logical masks $\mathbf{g}_{req}(\mathbf{x})$. Non-negotiable survival bounds (e.g., minimum target flora survival threshold $E_{target} \ge E_{min}$, carrying capacity ceiling $E_{max}$, or maximum allowable metabolic penalty) eliminate non-compliant parameter sets immediately.
* **Sub-Space Partitioning**: The global parameter space is partitioned into $k$ discrete initial genotype sub-spaces ($\mathbf{G}_1, \mathbf{G}_2, \dots, \mathbf{G}_k$). Each initial genotype explores a specialized evolutionary sub-strategy:
    * $\mathbf{G}_1$: Airborne Volatile Organic Compound (VOC) alarm networks.
    * $\mathbf{G}_2$: Local tissue toxin synthesis and mechanical armor.
    * $\mathbf{G}_3$: Subterranean mycorrhizal relay chains and nutrient withdrawal.
* **Dimensional Anchoring (Buckingham $\Pi$-Theorem)**: Raw biological traits ingested from empirical databases (TRY, PanTHERIA, Pherobase) via DuckDB are non-dimensionalized relative to grid cell size ($L_0 = \Delta L$), tick duration ($T_0 = \Delta \tau$), and energy quantum ($E_0 = \Delta E$). Continuous traits are bounded within statistical intervals $[\mu_k - 2\sigma_k, \mu_k + 2\sigma_k]$.

### 2.2 Macro-Phase 2: Genotype Sub-DSE (Fast Heuristic Optimization)

The Genotype phase functions as an encapsulated Sub-DSE component within the overarching cycle. It breaks down the massive ecosystem model into sub-components evaluated by fast algebraic and combinatorial solvers in milliseconds ($T_{algebraic} \approx 1\text{ ms}$).

#### Mathematical Formulations per Sub-Stage

```mermaid
flowchart TD
    classDef milp fill:#9B59B6,stroke:#8E44AD,stroke-width:2px,color:#fff;
    classDef graphstyle fill:#F39C12,stroke:#D68910,stroke-width:2px,color:#fff;
    classDef minlp fill:#1ABC9C,stroke:#16A085,stroke-width:2px,color:#fff;


    G["Candidate Sub-Space (G_k)"]
    S21["Stage 2.1: Structural Carbon (MILP)"]
    S22["Stage 2.2: Trophic Interaction Matrix (Graph)"]
    S23["Stage 2.3: Chemical Defense Kinetics (MINLP)"]
    
    G --> S21
    G --> S22
    G --> S23
    
    P1["Sub-Pareto Front"]
    P2["Sub-Pareto Front"]
    P3["Sub-Pareto Front"]
    
    S21 --> P1
    S22 --> P2
    S23 --> P3
    
    Prop["Pareto-Front Propagation"]
    
    P1 --> Prop
    P2 --> Prop
    P3 --> Prop
    
    class S21 milp
    class S22 graphstyle
    class S23 minlp

```

#### Sub-Stage 2.1: Structural Carbon Allocation & Metabolic Balances (MILP)

* **Solver**: Pyomo + HiGHS / SCIP.
* **Mathematical Model**:

$$
\max_{\mathbf{x}} \; \sum_{j=1}^{16} \left( g_j \cdot y_j - m_j \cdot y_j - c_{mechanical, j} \cdot x_{mech, j} \right)
$$

$$
\text{subject to } \sum_{j=1}^{16} \left( e_{build, j} \cdot y_j + e_{armor, j} \cdot x_{mech, j} \right) \le E_{photosynthate}, \quad x_{mech, j} \in \{0, 1\}, \; y_j \in [0, 1]
$$

* **Objective**: Maximizes growth rate $g_j$ against baseline maintenance metabolism $m_j$ and mechanical armor costs ($c_{mechanical, j}$).

#### Sub-Stage 2.2: Trophic Interaction & Diet Compatibility (Graph Constraints)

* **Solver**: Boolean Graph Matching Solver.
* **Mathematical Model**: Given a $16 \times 16$ boolean diet matrix $D_{ij} \in \{0, 1\}$ (Rule-of-16 bound):

$$
\sum_{j=1}^{16} D_{ij} \ge 1 \quad \forall i \in \text{Active Herbivores} \quad (\text{Prevents isolated starving species})
$$

$$
\sum_{i=1}^{16} D_{ij} \le K_{predation\_limit} \quad \forall j \in \text{Active Flora} \quad (\text{Prevents over-grazing singularity})
$$

#### Sub-Stage 2.3: Chemical Defense & Trigger Rule Kinetics (MINLP)

* **Solver**: SCIP / Bonmin.
* **Mathematical Model**: Solves sigmoidal Hill priming kinetics and timer state machines:

$$
\alpha_{priming}(C) = \frac{C^n}{K_d^n + C^n}, \quad n \ge 1, \; K_d > 0
$$

$$
\text{subject to } \tau_{synthesis} + \tau_{aftereffect} \le \tau_{max\_response}
$$

* **Objective**: Balances active defense synthesis maintenance against expected pest deterrence.

#### Multi-Stage Pareto-Front Propagation

Rather than collapsing to a single heuristic guess, each sub-stage solver extracts a non-dominated sub-Pareto front ($\mathcal{P}_{sub}$). Valid continuous parameter ranges and discrete graph structures are propagated forward to subsequent sub-stages, preserving structural diversity and preventing premature convergence.

### 2.3 Macro-Phase 3: Phenotype High-Fidelity Validation & Pruning

Candidates from the Genotype Pareto-fronts are instantiated as concrete Phenotypes—living plant agents and herbivore swarms populated inside the double-buffered PHIDS GridEnvironment and ECSWorld.

#### 1. High-Fidelity Physics & Biology Evaluation ($T_{sim}$)

* **Numba-JIT Chemotaxis Guidance Fields**:

$$
F_t(x, y) = \alpha \cdot \left( E_t(x, y) \cdot N_t(x, y) \right) - \beta \sum_k T_{k,t}(x, y)
$$

Computed via `@njit` kernels at $O(1)$ spatial hash complexity. Herbivore swarms sample the Moore neighborhood using probabilistic softmax routing and orthokinetic momentum.

* **Reaction-Diffusion PDEs**: 2D parabolic PDEs model volatile plume dispersion, anisotropic semi-Lagrangian wind advection ($\tilde{C}^t(x,y) = C^t(x - u_x, y - u_y)$), and Gaussian convolution diffusion ($\mathcal{K}_{iso} * \tilde{C}^t$).
* **Subnormal Float Truncation**: Values decaying below $\epsilon = 1 \times 10^{-4}$ are explicitly clamped to exact $0.0$ to prevent CPU denormalization slowdowns.

#### 2. The Unified Normalized Fitness Vector ($\mathbf{J}_{sys}$)

Raw simulation outputs operate across heterogeneous scales. EEDSE relativizes these metrics into a single dimensionless vector:

$$
\mathbf{J}_{sys} = w_1 \cdot \tilde{S}_{LV} + w_2 \cdot \tilde{E}_{ratio} - w_3 \cdot D_{bio} + w_4 \cdot H_{chem}
$$

Where:
* **Spectral FFT Lotka-Volterra Stability ($\tilde{S}_{LV}$)**: FFT spectral density analysis measuring limit cycle oscillation endurance over 5,000 ticks:

$$
\tilde{S}_{LV} = 1.0 - \frac{\int \vert{}F(\omega) - F_{ideal}(\omega)\vert{} d\omega}{\int F_{ideal}(\omega) d\omega}
$$

* **Fractional Carrying Capacity ($\tilde{E}_{ratio}$)**: Ratio of aggregate biomass to maximum carrying capacity ($E / E_{max} \in [0, 1]$).
* **Mahalanobis Empirical Distance ($D_{bio}$)**: Log-space distance measuring deviation from TRY/PanTHERIA empirical trait distributions:

$$
D_{bio} = \sqrt{(\ln \mathbf{x} - \boldsymbol{\mu}_{TRY})^T \boldsymbol{\Sigma}_{TRY}^{-1} (\ln \mathbf{x} - \boldsymbol{\mu}_{TRY})}
$$

* **Chemical Defensive Diversity ($H_{chem}$)**: Shannon entropy across active secondary metabolite concentrations:

$$
H_{chem} = -\sum_{k=1}^{16} p_k \ln p_k, \quad p_k = \frac{C_k}{\sum_m C_m}
$$

#### 3. Drastic Multi-Criteria Pruning

Because evaluating thousands of phenotypes in $T_{sim}$ is computationally expensive, strict pruning filters out candidates early:

* **Termination Code Penalties ($Z_1 - Z_7$)**: Scenarios triggering premature extinction ($Z_2 \dots Z_5$) or runaway trophic growth ($Z_6, Z_7$) receive instant fitness zeroing.
* **Entropy & Variance Pruning**: Candidates that perform well but exhibit near-zero variance compared to existing population cohorts are pruned to prevent monoculture collapse.

### 2.4 Macro-Phase 4: Closed-Loop Epistemic Learning & Co-Evolution

Phase 4 completes the evolutionary closed loop, processing evaluated Genotype-Phenotype-Fitness triads $(\mathbf{G}, \mathbf{P}, \mathbf{J}_{sys})$ stored in append-only Zarr binary buffers and indexed via DuckDB / Polars.

#### 1. Epistemic Error Delta Calculation ($\mathbf{\Delta}_{epistemic}$)

```mermaid
flowchart LR
    classDef model fill:#E67E22,stroke:#D35400,stroke-width:2px,color:#fff;
    classDef sim fill:#3498DB,stroke:#2980B9,stroke-width:2px,color:#fff;
    classDef error fill:#E74C3C,stroke:#C0392B,stroke-width:2px,color:#fff;

    Heuristic["Fast Algebraic Guess<br/>(F_heuristic)"]:::model --> Diff(("Difference"))
    Sim["Physical Simulation Reality<br/>(F_actual)"]:::sim --> Diff
    Diff --> Delta["Epistemic Error Delta<br/>(Δ_epistemic)"]:::error
```

The engine calculates discrepancies between fast algebraic guesses ($\mathbf{\hat{F}}_{heuristic}$) and physical simulation realities ($\mathbf{F}_{actual}$):

$$
\mathbf{\Delta}_{epistemic} = \mathbf{F}_{actual} - \mathbf{\hat{F}}_{heuristic}
$$

#### 2. Surrogate Model Recalibration (GPyTorch)

A Gaussian Process Regression (GPR) surrogate model is trained on historical error deltas $\mathcal{D} = \{(\mathbf{x}_k, \mathbf{\Delta}_{epistemic, k})\}$. Minimizing the negative marginal log-likelihood loss $\mathcal{L}_{surrogate}$:

$$
\mathcal{L}_{surrogate}(\boldsymbol{\theta}) = \frac{1}{2} \mathbf{\Delta}^T \mathbf{K}_{\boldsymbol{\theta}}^{-1} \mathbf{\Delta} + \frac{1}{2} \ln \vert{}\mathbf{K}_{\boldsymbol{\theta}}\vert{} + \frac{n}{2} \ln(2\pi)
$$

The surrogate gradient recalibrates the weight matrix $\mathbf{\hat{W}}_{t+1}$ used by the MILP/MINLP sub-solvers in the next generation:

$$
\mathbf{\hat{W}}_{t+1} = \mathbf{\hat{W}}_t + \eta \cdot \nabla_{\mathbf{W}} \mathcal{L}_{surrogate}(\mathbf{\Delta}_{epistemic})
$$

This re-educates the fast algebraic solvers, forcing them to mathematically account for spatiotemporal realities (wind advection, spatial chemotaxis bypasses) during subsequent scenario generation passes.

#### 3. Adaptive Search Space Bounds Refinement

Search bounds for generation $i+1$ contract around high-performing, validated regions while expanding along dimensions of high uncertainty ($\boldsymbol{\sigma}_j$):

$$
\mathcal{X}_{i+1} = \bigcup_{j \in \text{Surviving}} \left[ \mathbf{x}_j - \mathbf{k}_{adapt} \odot \boldsymbol{\sigma}_j, \; \mathbf{x}_j + \mathbf{k}_{adapt} \odot \boldsymbol{\sigma}_j \right] \cap \mathcal{X}_{init}
$$

#### 4. Co-Evolutionary Counter-Adaptation

The historical database triggers adaptive mutations in opposing agents:
* When flora evolve high mechanical resistance, the database mutates herbivore trait structs (`morphological_adaptation`, `digestive_efficiency`, `chemical_neutralization`) to model ongoing co-evolutionary arms races.
* This prevents the DSE from settling into fragile, non-resilient local minima.

#### 5. Distributed Recombination (Ray/Tune & NSGA-III)

* High-throughput NSGA-III non-dominated sorting (DEAP library integration) extracts balanced scenario blueprints.
* Chromosomal trait structs undergo SIMD bit-mask mutations across Ray/Tune distributed worker tasks.
* Population size is strictly bounded ($N_{genotypes} \le 32$) to guarantee high-throughput completion within cluster memory budgets.

## 3. Inter-Phase Data Schema & Interface Contracts

| Phase Transition | Payload Schema Name | Data Format / Type | Core Fields Passed |
| :--- | :--- | :--- | :--- |
| Phase 1 $\to$ Phase 2 | `DelimitedSpaceSchema` | DuckDB View / Pydantic V2 | $\mathcal{X}_{init}$ bounds, requirements mask $\mathbf{g}_{req}$, Buckingham $\Pi$ scalars |
| Phase 2 $\to$ Phase 3 | `GenotypeBlueprintSet` | JSON / YAML Scenario Draft | Propagated sub-Pareto sets $\mathcal{P}_{sub}$, Rule-of-16 $16\times16$ matrices, MINLP parameters |
| Phase 3 $\to$ Phase 4 | `PhenotypeEvaluationRecord` | Zarr Array + Polars DataFrame | Raw tick telemetry, $Z_1-Z_7$ termination code, relativized vector $\mathbf{J}_{sys}$ |
| Phase 4 $\to$ Phase 1/2 | `EpistemicWeightUpdate` | Binary MsgPack Payload | Gradient updates $\mathbf{\hat{W}}_{t+1}$, GPR kernel params $\boldsymbol{\theta}$, adaptive bounds $\mathcal{X}_{i+1}$ |

## 4. Runtime Software Boundary & Codebase Mapping

| Subsystem Component | Technical Task | Primary Software Framework / Library | Codebase Location (`src/phids/`) |
| :--- | :--- | :--- | :--- |
| **Ingress & Delimitation** | Bounds Validation, Buckingham $\Pi$ Anchoring | Pydantic V2, DuckDB, NumPy | `src/phids/api/schemas/`, `src/phids/analytics/bio_database.py` |
| **Genotype Sub-DSE** | Algebraic MILP / MINLP Solvers | Pyomo, HiGHS, SCIP, PuLP | `src/phids/analytics/dse_genotype.py`, `dse_optimizer.py` |
| **Sub-DSE Pareto Extraction** | Fast Non-Dominated Sorting | DEAP (NSGA-III), NumPy | `src/phids/analytics/dse_pruning.py` |
| **Phenotype Validation** | High-Fidelity Spatial ECS & PDEs | Numba JIT (`@njit`), PyTorch CUDA | `src/phids/engine/core/biotope.py`, `flow_field.py`, `ecs.py` |
| **Relativization & Scoring** | Unified Normalized Fitness Vector | Polars, PHIDS Presenter Layer | `src/phids/telemetry/analytics.py`, `src/phids/api/presenters/` |
| **Telemetry Storage** | Append-Only High-Density Replays | Zarr, msgpack, zlib | `src/phids/telemetry/zarr_replay.py` |
| **Epistemic Delta Learning** | Gaussian Process Surrogate Weights | GPyTorch, scikit-learn | `src/phids/analytics/tuning.py` |
| **Cluster Orchestration** | Distributed Parallel Evaluation | Ray/Tune, Typer CLI | `src/phids/analytics/dse_distributed.py` |

## 5. Governance & Interventions: Agentic AI-in-the-Loop (AITL) vs. Human-in-the-Loop (HITL)

This section specifies the exact architectural touchpoints across the Evolutionary Encapsulated Design Space Exploration (EEDSE) pipeline where Human-in-the-Loop (HITL) and Agentic AI-in-the-Loop (AITL) toggles, intervention gates, and steering overrides are positioned in PHIDS.

The core objective is to prevent the optimization engine from becoming an opaque black box while maintaining high-throughput compute efficiency ($T_{algebraic} \approx 1\text{ ms}$).

### 5.1 High-Level Intervention Topology

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: MACRO DELIMITATION & PRE-PRUNING                                                        │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Ingest Bounds ──► [ GATE 1: Requirement & Constraint Invariant Gate ] ──► Initial Hyper-Cube X_init│
│                   │ Toggle: Fully Autonomous AI vs. Human Rule Override / Hard Locking           │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: GENOTYPE SUB-DSE (FAST HEURISTIC SOLVERS)                                                │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Algebraic MILP/MINLP ──► [ GATE 2: Sub-Pareto Structural Inspection & Slicing ] ──► P_genotype   │
│                          │ Toggle: AI Multi-Objective Slicing vs. Human Pareto Steering          │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: PHENOTYPE HIGH-FIDELITY VALIDATION                                                       │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Numba/CUDA Simulation ──► [ GATE 3: Unified Fitness Vector Weight & Penalty Tuning ] ──► J_sys    │
│                            │ Toggle: AI Automated Relativization vs. Human Weight Adjustments    │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: CLOSED-LOOP EPISTEMIC LEARNING & RECOMBINATION                                          │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Epistemic Delta Δ ──► [ GATE 4: Surrogate Model (GPR) Recalibration Audit ]                      │
│                       │ Toggle: AI Auto-Grad Weight Update vs. Human Epistemic Validation        │
│                                                │                                                 │
│ Co-Evolution     ──► [ GATE 5: Adversarial Arms Race Steering ]                                  │
│                       │ Toggle: AI MARL Mutation Pass vs. Human Herbivore Trait Force-Inject     │
│                                                │                                                 │
│ Recombination    ──► [ GATE 6: Generational Gate & Exploration Entropy Safeguard ]              │
│                       │ Toggle: Continuous Autonomous Loop vs. Step-by-Step Approval (Breakpoints) │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Detailed Intervention Points & Toggle Specifications

#### Touchpoint 1: Delimitation Requirements & Constraint Gate (Phase 1 Ingress)

* **Location in Codebase**: [`src/phids/analytics/bio_database.py`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/analytics/bio_database.py), [`src/phids/api/schemas/`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/api/schemas/)
* **Purpose**: Defines the initial hyper-cube ($\mathcal{X}_{init}$) and pre-pruning masks ($\mathbf{g}_{req}$).
* **Modes**:
    * **Autonomous AI (AITL)**: Ingests database traits (TRY/PanTHERIA via DuckDB) and automatically non-dimensionalizes parameters using Buckingham $\Pi$-groups based on standard confidence intervals $[\mu \pm 2\sigma]$.
    * **Human Control (HITL)**: A researcher toggles strict overrides:
        * **Hard Trait Locking**: Pinning specific species traits (e.g., forcing a specific plant's max growth rate $g_j = 0.05$ or locking a $16 \times 16$ diet matrix topology).
        * **Requirement Injections**: Specifying non-negotiable scenario goals (e.g., $E_{target\_flora} \ge 80\%$) that act as hard pre-pruning masks.
* **UI Control Surface**: Contextual modal toggle in the Control Center Dashboard (`DraftState`) titled `Pre-Pruning Governance: [ Auto-Impute (AI) | Custom Constraint Overrides (Human) ]`.

#### Touchpoint 2: Sub-Pareto Structural Inspection & Slicing (Phase 2 Output)

* **Location in Codebase**: [`src/phids/analytics/dse_genotype.py`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/analytics/dse_genotype.py), [`src/phids/analytics/dse_pruning.py`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/analytics/dse_pruning.py)
* **Purpose**: Manages the propagation of sub-Pareto fronts ($\mathcal{P}_{sub}$) generated by the fast MILP/MINLP solvers (Pyomo/HiGHS).
* **Modes**:
    * **Autonomous AI (AITL)**: Automatically computes crowding distances and non-dominated ranks, passing the top $K$ mathematical trade-off blueprints forward to Phase 3.
    * **Human Control (HITL)**: The researcher inspects the trade-off curve (e.g., Morphological Lignin Cost vs. Growth Rate) in a live 2D/3D scatter plot and visually draws a regional bounding box (slice) to eliminate mathematically valid but scientifically uninteresting regions.
* **UI Control Surface**: Interactive HTMX/Chart.js Pareto Front inspector with a `Propagate Front: [ AI Automated Rank | Manual Region Slice ]` switch.

#### Touchpoint 3: Unified Fitness Vector Weighting & Relativization (Phase 3 Scoring)

* **Location in Codebase**: [`src/phids/telemetry/analytics.py`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/telemetry/analytics.py), [`src/phids/api/presenters/`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/api/presenters/)
* **Purpose**: Weights the components of the Unified Normalized Fitness Vector:

$$
\mathbf{J}_{sys} = w_1 \cdot \tilde{S}_{LV} + w_2 \cdot \tilde{E}_{ratio} - w_3 \cdot D_{bio} + w_4 \cdot H_{chem}
$$

* **Modes**:
    * **Autonomous AI (AITL)**: Uses dynamic variance-scaling (e.g., Inverse Variance Weighting) to rebalance weights $w_1 \dots w_4$ across generations based on population entropy.
    * **Human Control (HITL)**: The user manually adjusts sliders for $w_1$ (Lotka-Volterra Stability), $w_2$ (Biomass Energy), $w_3$ (Empirical Distance Penalty), and $w_4$ (Defensive Diversity), prioritizing what "success" means for their specific experiment.
* **UI Control Surface**: Live slider control panel in the DSE dashboard with a toggle: `Objective Vector Calibration: [ Adaptive Entropic Weighting (AI) | User-Defined Sliders (Human) ]`.

#### Touchpoint 4: Epistemic Error Delta Audit & Surrogate Recalibration (Phase 4 Ingress)

* **Location in Codebase**: [`src/phids/analytics/tuning.py`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/analytics/tuning.py)
* **Purpose**: Learns the error delta between fast algebraic models and high-fidelity physics ($\mathbf{\Delta}_{epistemic} = \mathbf{F}_{actual} - \mathbf{\hat{F}}_{heuristic}$) using Gaussian Process Regression (GPyTorch).
* **Modes**:
    * **Autonomous AI (AITL)**: Auto-evaluates loss $\mathcal{L}_{surrogate}$, calculates gradients $\nabla_{\mathbf{W}} \mathcal{L}_{surrogate}$, and immediately updates the solver weight matrix $\mathbf{\hat{W}}_{t+1}$ for the next cycle.
    * **Human Control (HITL - Diagnostic Audit)**: Pauses the loop when $\mathbf{\Delta}_{epistemic}$ exceeds a user-defined threshold (e.g., $>30\%$ discrepancy between heuristic guess and physical simulation). The human inspects the physical cause (e.g., wind advection causing VOC plume bypass) before approving the weight recalibration.
* **UI Control Surface**: Diagnostic alert banner: `Epistemic Drift Threshold Crossed (|Δ| > 30%). [ Auto-Apply Gradient Update | Audit Discrepancy & Override ]`.

#### Touchpoint 5: Co-Evolutionary Arms Race & Counter-Strategy Steering (Phase 4 Evolution)

* **Location in Codebase**: [`src/phids/analytics/dse_optimizer.py`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/analytics/dse_optimizer.py), [`src/phids/analytics/dse_distributed.py`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/analytics/dse_distributed.py)
* **Purpose**: Drives the counter-adaptation of opposing agents (e.g., herbivore resistances) to prevent plants from settling into fragile local minima.
* **Modes**:
    * **Autonomous AI (AITL)**: Reinforcement Learning / MARL policies or SIMD bit-mask mutations automatically evolve herbivore traits (`chemical_neutralization`, `digestive_efficiency`) to attack the dominant plant defense strategies.
    * **Human Control (HITL - Scenario Authoring)**: The researcher acts as an "adversarial designer," manually injecting specific counter-adaptations (e.g., force-mutating a specific herbivore pest to become $90\%$ resistant to a synthesized alkaloid) to test the robustness of candidate plant genotypes.
* **UI Control Surface**: AITL/HITL switch under the Co-Evolution Panel: `Adversarial Dynamics: [ AI Agent Policy Adaptation | Manual Pest Resistance Injection ]`.

#### Touchpoint 6: Generational Execution & Loop Breakpoints (Phase 4 Recombination)

* **Location in Codebase**: [`src/phids/analytics/dse_distributed.py`](file:///home/benni/Documents/antigravity_workspace/PHIDS/src/phids/analytics/dse_distributed.py), `src/phids/api/services/dse/task_manager.py`
* **Purpose**: Controls overall generation-to-generation execution flow and search space entropy management ($\mathcal{X}_{i+1}$).
* **Modes**:
    * **Autonomous Execution (Continuous AITL)**: Runs $G$ generations headless across Ray/Tune clusters until convergence criteria or maximum generations are met.
    * **Human Step-by-Step Execution (Interactive HITL)**: Acts as a simulation "breakpoint engine." At the end of each generation, the DSE engine pauses, displays the newly derived candidate pool ($N \le 32$), and waits for explicit human confirmation to launch the next generational cycle.
* **UI Control Surface**: Top-bar execution toolbar: `DSE Execution Mode: [ Continuous Autonomous Sweep | Step-by-Step Generational Breakpoints ]`.

### 5.3 Summary of Value Proposition for HITL / AITL Toggles

| Pipeline Gate / Touchpoint | Autonomous AI Mode (AITL) Value | Human-in-the-Loop Mode (HITL) Value |
| :--- | :--- | :--- |
| **Gate 1: Macro Delimitation** | Rapid auto-bounding via empirical DuckDB statistical confidence intervals. | Hard-locks specific species parameters and enforces non-negotiable scenario requirements. |
| **Gate 2: Sub-Pareto Slicing** | Mathematical rank/distance extraction across multi-component MILP solvers. | Visual slicing of trade-off curves to focus compute power on scientifically relevant regions. |
| **Gate 3: Fitness Vector Weighting** | Dynamic entropic weight balancing preventing search space collapse. | Custom multi-objective prioritization (e.g., valuing Lotka-Volterra stability over empirical distance). |
| **Gate 4: Epistemic Audit** | Real-time gradient updates ($\mathbf{\hat{W}}_{t+1}$) via GPyTorch surrogate models. | Diagnostic safety barrier preventing the AI from learning unphysical edge-case exploits. |
| **Gate 5: Co-Evolution Steering** | Automated MARL pest counter-adaptation preventing fragile local minima. | Targeted adversarial stress-testing against specific biological mutations. |
| **Gate 6: Generational Breakpoints** | Unattended, high-throughput HPC execution across Ray/Tune clusters. | Full step-by-step oversight, scenario inspection, and steering control for researchers. |

## 6. Architectural Summary & System Guarantees

The Evolutionary Encapsulated Design Space Exploration (EEDSE) framework transforms ecological scenario discovery into a mathematically rigorous, self-correcting optimization pipeline:

* **$10^2\times$ Compute Reduction**: Eliminates $>99\%$ of unviable parameter combinations in $O(1\text{ ms})$ algebraic sub-solvers before running $T_{sim}$.
* **Empirical Authenticity**: Bounds searches via DuckDB TRY/PanTHERIA distributions and Mahalanobis distances ($D_{bio}$).
* **Self-Correcting Intelligence**: Recalibrates heuristic generator weights ($\mathbf{\hat{W}}_{t+1}$) using physical simulation error deltas ($\mathbf{\Delta}_{epistemic}$).
* **Resilient Optimization**: Avoids local minima trap-in through co-evolutionary agent mutations and adaptive search space variance expansion.
