---
type: technical_architecture
title: "Engine Execution"
status: active
version: 0.1
description: "Documentation for Engine Execution in the PHIDS framework."
---

# Engine Execution

The core execution loop of PHIDS updates ecological state deterministically. The progression of phases occurs in a fixed sequence, guaranteeing that later phases observe the finalized, double-buffered side effects of earlier computations.

## The Simulation Tick Order

The `SimulationLoop.step()` method executes the following components consecutively, forming a single discrete timeframe ($\Delta t$):

1.  **Flow-Field Generation**: Utilizes Numba JIT compilation to compute the singular global guidance gradient based on plant energy and toxic zones.
2.  **Camouflage Attenuation**: Post-processes the flow-field by masking the gradient for flora utilizing camouflage traits.
3.  **Lifecycle (`run_lifecycle`)**: Updates flora-centric state. Handles resource growth, deterministic mycorrhizal propagation, threshold culling, and interval-gated reproduction logic.
4.  **Interaction (`run_interaction`)**: Determines swarm behavior. Checks the spatial hash for crowding (inducing repelled dispersal), executes flow-field gradient sampling, performs localized feeding, and manages the continuous deficit attrition and mitosis algorithms.
5.  **Signaling (`run_signaling`)**: Converts herbivore presence into substance triggers. Manages the synthesis countdowns, aftereffects, emits substances into the double-buffered grid, and processes local toxic casualties.
6.  **Observation**: Records telemetry output and checks global termination conditions against the newly finalized tick state.

## Entity Component System (ECS) & Spatial Hashing

Entities in PHIDS are lightweight, data-only records lacking encapsulated logic. System functions iterate over specific intersections of component types, separating memory allocation from logic execution. This ensures maximum cache coherence and rapid loop traversal.

### $O(1)$ Locality Resolution

To avoid catastrophic $O(N^2)$ distance polling, `ECSWorld` maintains a Spatial Hash—a dictionary mapping $(x,y)$ coordinates to the sets of residing `entity_id`s. When an herbivore feeds, or a plant checks for grazing pressure, it queries the spatial hash at its immediate coordinate to retrieve co-located entities. This completely negates the need for global proximity iterations across the map.

### Active Garbage Collection

Entities whose population or energy levels degrade past viable thresholds are unregistered from the Spatial Hash immediately, removing them from subsequent spatial lookups within the same tick. At the conclusion of system iterations, `ECSWorld.collect_garbage()` permanently deletes these entities, recovering resources and ensuring clean state space for subsequent ticks. This prevents the memory overhead typical in naive ECS implementations where dead entities remain stored indefinitely.

```mermaid
flowchart LR
    %% External Application States
    subgraph App_Control ["Application Master State Controller"]
        Idle(["Idle Space"]) -->|POST /load| Loaded(["Scenario Loaded"])
        Loaded -->|POST /start| Running[["RUNNING HOT LOOP"]]
        Running -->|POST /pause| Paused(["Simulation Paused"])
        Paused -->|POST /resume| Running
        Running -->|Termination Condition Met| Terminated(["Terminated State"])
        Terminated -->|POST /reload| Loaded
    end

    %% Internal Hot Loop Pass Execution
    subgraph Loop_Step ["Granular In-Tick Operational Ordering (SimulationLoop.step)"]
        direction TB
        S1["1. Compute Vector Guidance Field<br><i>flow_field.py @njit Pass</i>"]
        S2["2. Attenuate Camouflage Profiles<br><i>Mask Flora Guidance Gradients</i>"]
        S3["3. Execute Flora Lifecycle Pass<br><i>Resource Growth & Reproduction</i>"]
        S4["4. Run Interaction Dynamics<br><i>Spatial Hash Grazing & Mitosis</i>"]
        S5["5. Evaluate Inductions & Signaling<br><i>Reaction-Diffusion Convolutions</i>"]
        S6["6. Telemetry Logging Output<br><i>Appends Record to Polars Data Block</i>"]
    end

    %% Causal Link to Engine Core
    Running ==>|Spins Continuous Tick Core| S1
    S6 -->|Loop Back if Invariants Hold| S1

    %% Class Allocations
    classDef peripheral fill:#181818,stroke:#9e9e9e,stroke-width:2px,rx:6px,ry:6px;
    classDef coreSys fill:#141224,stroke:#b388ff,stroke-width:2px,rx:6px,ry:6px;
    classDef stateData fill:#111b24,stroke:#00b8d4,stroke-width:2px,rx:6px,ry:6px;

    class Idle,Loaded,Paused,Terminated peripheral
    class Running coreSys
    class S1,S2,S3,S4,S5,S6 stateData
```
