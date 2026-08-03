---
type: technical_architecture
title: Engine Execution
status: active
version: 0.1
description: Documentation for Engine Execution in the PHIDS framework.
tags:
- phids
- ecs
- numba
timestamp: "2026-07-25T20:25:00Z"
resources:
- src/phids/engine/loop.py
- src/phids/engine/core/flow_field.py
- src/phids/engine/core/ecs.py
- src/phids/engine/core/biotope.py
- src/phids/engine/systems/interaction/feeding.py
- src/phids/engine/systems/interaction/movement.py
- src/phids/engine/systems/lifecycle.py
- src/phids/engine/systems/signaling/lifecycle.py
- src/phids/engine/systems/signaling/triggers.py
---

The core execution loop of PHIDS updates ecological state deterministically. The progression of phases occurs in a fixed sequence, guaranteeing that later phases observe the finalized, double-buffered side effects of earlier computations.

## The Simulation Tick Order

The `SimulationLoop.step()` method executes the following components consecutively, adhering to **Multi-Scale Temporal Decoupling (Modulo-Gating)** to prevent IEEE 754 subnormal floating-point truncation traps and ensure extreme cache locality:

1. **Flow-Field Generation (Fast Loop - Every Tick)**: Utilizes Numba `@njit` compilation to compute the singular global guidance gradient based on plant energy, apparent nutrition, and toxic zones.
2. **Camouflage Attenuation (Fast Loop - Every Tick)**: Post-processes the flow-field matrix by masking local guidance gradients for flora utilizing camouflage traits.
3. **Lifecycle (`run_lifecycle`) (Slow Loop - Weekly / 168-Tick Stride)**:
   - **Photosynthetic Growth**: Applies accumulated weekly photosynthetic biomass growth scaled by `SLOW_TICK_STRIDE` (168x). This prevents FPU microcode traps caused by microscopic per-tick increments ($<10^{-4}$).
   - **$O(1)$ Stochastic Raycasting Dispersal**: Replaces legacy $O(N \times r^2)$ grid spatial convolution with constant-time vector projection along wind unit vector $\mathbf{u} = \mathbf{w} / \|\mathbf{w}\|$ combined with single-axis turbulent Gaussian scatter $\delta_\perp \sim \mathcal{N}(0, \sigma_\perp^2)$.
   - **Mycorrhizal Symbiosis**: Establishes bidirectional root connections between adjacent plants on slow-loop gates, applying continuous carbon maintenance taxes (`mycorrhizal_tax_per_link`).
   - **Threshold Culling & Garbage Collection**: Removes plants whose energy drops below `survival_threshold`.
4. **Interaction (`run_interaction`) (Fast / Medium / Slow Gated)**:
   - **Movement & Chemotaxis (Fast Loop - Every Tick)**: Micro-swarm kinetic movement and spatial repulsion.
   - **Metabolism & Foraging (Medium Loop - Daily / 24-Tick Stride)**: Swarm feeding and daily metabolic cost drain scaled by 24x stride ($\text{cost} = \text{pop} \times E_{\text{min}} \times \text{upkeep} \times 24$).
   - **Colony Fission / Mitosis (Slow Loop - Weekly / 168-Tick Stride)**: Swarms with substantial caloric surpluses split into new entities.
5. **Signaling (`run_signaling`) (Fast Loop - Every Tick)**: Evaluates trigger rules via continuous dose-dependent Hill kinetics ($S(c) = \frac{c^n}{K^n + c^n}$) or threshold predicates. Manages airborne advection-diffusion, mycorrhizal signal propagation, and lethal toxin casualties.
6. **Energy Layer Rebuild & Telemetry Logging**: Rebuilds the double-buffered energy layer (`rebuild_energy_layer()`), records a metrics snapshot of the current tick, and appends raw arrays to the Zarr replay buffer and Polars telemetry exporter.
7. **Termination Check**: Evaluates configured extinction ($Z_2, Z_4$), max energy ($Z_6$), max tick, and population ($Z_7$) threshold limits.

## Entity Component System (ECS) & Spatial Hashing

Entities in PHIDS are lightweight, data-only records lacking encapsulated logic. System functions iterate over specific intersections of component types, separating memory allocation from logic execution. This ensures maximum cache coherence and rapid loop traversal.

### Query Optimization & Structural Versioning

To avoid $O(N)$ list allocations on every tick when systems iterate over component types, `ECSWorld` implements a `_structural_version` cache. The registry caches materialized query lists, only incrementing the version and invalidating the cache when entities or components are structurally added or removed. This provides near-instant lookup speeds for all hot-path systems on steady-state ticks.

### $O(1)$ Locality Resolution & Toroidal Geometry

To avoid catastrophic $O(N^2)$ distance polling, `ECSWorld` maintains a Spatial Hash—a dictionary mapping $(x,y)$ coordinates to the sets of residing `entity_id`s. When an herbivore feeds, or a plant checks for grazing pressure, it queries the spatial hash at its immediate coordinate to retrieve co-located entities.

To eliminate boundary edge-effect distortions and enforce strict physical mass conservation across arbitrary grid dimensions, PHIDS implements a **Toroidal (periodic wrap-around) Topology** across both discrete entity space and continuous biotope fields:

- **Branchless Coordinate Wrapping**: All spatial coordinate updates enforce branchless modulo arithmetic: $x_{\text{wrapped}} = (x + \Delta x) \pmod W$ and $y_{\text{wrapped}} = (y + \Delta y) \pmod H$, completely eliminating branch mispredictions in Numba `@njit` loop kernels.
- **Toroidal Spatial Distance**: Spatial distance between points $(x_1, y_1)$ and $(x_2, y_2)$ accounts for wrap-around seam boundaries:

  $$\Delta x_{\text{toroidal}} = \min(|x_1 - x_2|, W - |x_1 - x_2|)$$

  $$\Delta y_{\text{toroidal}} = \min(|y_1 - y_2|, H - |y_1 - y_2|)$$

- **Shortest-Seam Inertia Vector Alignment**: When swarms cross boundary seams (e.g. from $x=W-1$ to $x=0$), inertia deltas are normalized to $\Delta x = -1$ rather than $-(W-1)$, ensuring smooth kinematic trajectory continuation across wrap boundaries.

### Active Garbage Collection

Entities whose population or energy levels degrade past viable thresholds are unregistered from the Spatial Hash immediately, removing them from subsequent spatial lookups within the same tick. To prevent "ghost" entities from being queried by subsequent system phases in the same tick, `ECSWorld.collect_garbage()` is executed immediately at the end of (or inline within) each individual system phase (Lifecycle, Interaction, and Signaling) to permanently delete dead entities and reclaim memory resources. This prevents memory overhead and lookup pollution typical in naive ECS implementations.

```mermaid
flowchart LR
    %% External Application States
    subgraph App_Control ["Application Master State Controller"]
        Idle(["Idle Space"]) -->|POST /api/scenario/load| Loaded(["Scenario Loaded"])
        Loaded -->|POST /api/simulation/start| Running[["RUNNING HOT LOOP"]]
        Running -->|POST /api/simulation/pause| Paused(["Simulation Paused"])
        Paused -->|POST /api/simulation/pause or /start| Running
        Running -->|Termination Condition Met| Terminated(["Terminated State"])
        Terminated -->|POST /api/simulation/reset| Loaded
    end

    %% Internal Hot Loop Pass Execution
    subgraph Loop_Step ["Granular In-Tick Operational Ordering (SimulationLoop.step)"]
        direction TB
        S1["1. Compute Vector Guidance Field<br><i>flow_field.py @njit Pass</i>"] --> S2
        S2["2. Attenuate Camouflage Profiles<br><i>Mask Flora Guidance Gradients</i>"] --> S3
        
        S3["3. Execute Flora Lifecycle Pass<br><i>Resource Growth & Threshold Culling<br><b>ECSWorld.collect_garbage() (Plants)</b></i>"] --> S4
        S4["4. Run Interaction Dynamics<br><i>Spatial Hash Grazing, Attrition & Mitosis<br><b>ECSWorld.collect_garbage() (Plants & Swarms)</b></i>"] --> S5
        S5["5. Evaluate Inductions & Signaling<br><i>Reaction-Diffusion & Toxic Casualties<br><b>ECSWorld.collect_garbage() (Toxin Casualties)</b></i>"] --> S6
        
        S6["6. Telemetry Logging Output<br><i>Appends Record to Polars Data Block & Replay</i>"] --> S7
        S7["7. Termination Check<br><i>Evaluates stop conditions for next tick</i>"]
    end

    %% Immediate Mid-Tick Eviction Substrate
    subgraph Spatial_Hash_Substrate ["Stage 1: Immediate Spatial Invalidation"]
        SH_Evict[["O(1) Instant Hash Eviction<br><i>Unregister Dead Entity IDs from Coordinates</i>"]]
    end

    %% Mid-tick death trigger hooks linking to immediate eviction
    S3 -.->|Biomass Depletion / Decay| SH_Evict
    S4 -.->|Starvation / Grazing| SH_Evict
    S5 -.->|Lethal Toxic Damage| SH_Evict

    %% Eviction loop effects bypassing subsequent system phases
    SH_Evict -.->|Removes entity from lookup pool| S4
    SH_Evict -.->|Removes entity from lookup pool| S5

    %% Causal Link to Engine Core
    Running ==>|Spins Continuous Tick Core| S1
    S7 -->|Loop Back if Invariants Hold| S1

    %% Class Allocations
    classDef peripheral fill:#181818,stroke:#9e9e9e,stroke-width:2px,rx:6px,ry:6px;
    classDef coreSys fill:#141224,stroke:#b388ff,stroke-width:2px,rx:6px,ry:6px;
    classDef stateData fill:#111b24,stroke:#00b8d4,stroke-width:2px,rx:6px,ry:6px;
    classDef hazard fill:#1c1212,stroke:#ff5252,stroke-width:2px,rx:6px,ry:6px;
    classDef shortcut fill:#112214,stroke:#00e676,stroke-width:2px,rx:6px,ry:6px;

    class Idle,Loaded,Paused,Terminated peripheral
    class Running,S1,S2,S3,S4,S5,S6,S7 coreSys
    class SH_Evict shortcut
```
