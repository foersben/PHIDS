---
type: scenario
title: Scenario Authoring & Schema
status: active
version: 0.1
description: Documentation for Scenario Authoring & Schema in the PHIDS framework.
tags:
- phids
timestamp: '2026-07-21T16:01:38Z'
resources: []
---

Scenarios in PHIDS form the strict boundaries of the ecological experiment. A scenario dictates the grid dimensions, initial biomass distributions, trophic links (who eats what), and the specific substance triggers deployed by flora when attacked. At the engine level, all scenarios are structurally validated against the `SimulationConfig` Pydantic schema before execution.

## The Rule of 16 Configuration Bounds

A fundamental engineering constraint within the simulation loop is the avoidance of dynamic memory allocations during high-frequency execution. If a new species was dynamically introduced, matrices tracking interaction rules would need to be rebuilt, stalling the CPU.

To circumvent this, configurations are structurally bounded. Every scenario is permitted a maximum of:

* **16 Flora Species**
* **16 Herbivore Species**
* **16 Substance Profiles**

These indices translate directly into fixed $(16 \times 16)$ boolean matrices for diet compatibility and integer matrices for defense behavior. Exceeding these bounds at the API or file ingress stage will result in a validation rejection, ensuring the simulation runs predictably.

```mermaid
flowchart TD
    %% Title Matrix Header
    subgraph Configuration_Limit ["Pre-Allocated Static Memory Allocation Array Substrates"]
        direction LR
        F_Array["Flora Array Slots<br><b>[0..15 Sub-Blocks]</b>"]
        H_Array["Herbivore Array Slots<br><b>[0..15 Sub-Blocks]</b>"]
        S_Array["Substance Profile Slots<br><b>[0..15 Sub-Blocks]</b>"]
    end

    %% Core Matrices Mapping
    subgraph PreAllocated_Matrices ["Fixed Cache-Resident Invariant Rule Matrices"]
        direction TB
        Diet_Matrix["Diet Compatibility Block Matrix<br><i>(Fixed 16x16 Contiguous Boolean Matrix)</i>"]
        Trigger_Matrix["Substance Trigger Interaction Matrix<br><i>(Fixed 16x16 Contiguous Integer Lookup Matrix)</i>"]
    end

    %% Structural Boundaries Check
    Ingress_Payload{"Scenario File Ingress Processing<br><i>Pydantic SimulationConfig Validation Phase</i>"}
    Ingress_Payload -->|Valid: Entities <= 16| Boot["Bootstrap Static Arrays<br><i>Safe JIT Compilation Space</i>"]
    Ingress_Payload -->|Invalid: Count > 16| Rejection[["API Validation Error Raised<br>(Reject Dynamic Allocation Overhead)"]]

    %% Connections
    Boot --> Configuration_Limit
    Configuration_Limit --> Diet_Matrix & Trigger_Matrix

    %% Class Allocations
    classDef dataLayer fill:#111b24,stroke:#00b8d4,stroke-width:2px,rx:6px,ry:6px;
    classDef boundary fill:#1c1212,stroke:#ff5252,stroke-width:2px,rx:6px,ry:6px;
    classDef peripheral fill:#181818,stroke:#9e9e9e,stroke-width:2px,rx:6px,ry:6px;

    class Configuration_Limit,Diet_Matrix,Trigger_Matrix dataLayer
    class Rejection boundary
    class Ingress_Payload,Boot peripheral
```

## Interaction Matrices

Scenarios orchestrate behavior through explicit matrices, which are fully editable via the HTMX UI Draft State:

1. **Diet Compatibility Matrix**: A $16 \times 16$ boolean matrix determining whether herbivore $E_i$ can metabolize flora $P_j$. If incompatible, an attempted feeding event resolves into rejection, prompting a randomized displacement of the swarm away from the plant.
2. **Trigger Matrix**: A $16 \times 16$ mapping detailing which specific substance $S_x$ a given flora species $P_j$ synthesizes upon localized attack by herbivore $E_i$. A single plant can synthesize lethal toxins against one grazer while emitting volatile signals when grazed by another.

## Import/Export Pathways

Scenario parameters are serialized directly to and from normalized JSON payloads (`load_scenario_from_json`, `scenario_to_json`). The control center UI facilitates the injection of exported JSONs directly into the mutable `DraftState` for manual iteration.

Once the operator finalizes the scenario, the draft is pushed into the live `SimulationConfig`. This process ensures absolute separation between experimental setup and experimental execution.

```mermaid
flowchart TD
    %% Phase 1: Detection & Extraction
    subgraph Detection ["Phase I: Detection & Spatial Hash Ingress"]
        A([Tick Commences]) --> B{"Co-located Entities Found?<br><i>Spatial Hash O(1) Check</i>"}
        B -- Yes --> C{"Local Population Density<br><b>N_i >= n_i,min</b>?"}
        B -- No --> End_Passive([No Trigger Activated])
        C -- No --> End_Passive
    end

    %% Phase 2: Synthesis Core
    subgraph Synthesis ["Phase II: Gated Synthesis Engine"]
        C -- Yes --> D{"Precursor Signal Array<br>Requirement Active?"}
        D -- No/Met --> E["Initialize Substance Clock<br><b>T_s_x Countdowns</b>"]
        D -- Unmet --> End_Passive

        E --> F{"Counter Complete?<br><b>synthesis_remaining == 0</b>"}
        F -- No --> G["Decrement Counter Layer<br><i>Inline Write Array Mutation</i>"]
        F -- Yes --> H[["Substance Component State: ACTIVE"]]
    end

    %% Phase 3: Action Bifurcation
    subgraph Evaluation ["Phase III: Action Allocation & Outcomes"]
        H --> I{"Substance Type Classification"}

        %% Airborne Path
        I -->|Atmospheric Signal| J["Emit Volatile Plume<br><i>SciPy convolve2d Diffusion</i>"]
        J --> K["Propagate via Mycorrhizal Graph<br><i>Fixed Network Velocity Bypass</i>"]

        %% Local Tissue Toxin Path
        I -->|Localized Tissue Toxin| L{"Lethality Evaluation"}
        L -- Lethal Toxin --> M["Apply Cascade Casualties<br><i>Ceiling Attrition Function</i>"]
        L -- Repellent Compound --> N["Set Swarm State: REPELLED<br><i>Force k-Tick Random Walk</i>"]
    end

    %% Loop Closure Paths
    K & M & N --> P{"Herbivore Pressure Persists?"}
    P -- Yes --> H
    P -- No --> Q["Process Substance Aftereffect Countdowns"]
    Q --> R([Deactivate / Garbage Collect Substance Entity])

    %% Styling Classes
    classDef coreSys fill:#141224,stroke:#b388ff,stroke-width:2px,rx:6px,ry:6px;
    classDef stateData fill:#111b24,stroke:#00b8d4,stroke-width:2px,rx:6px,ry:6px;
    classDef hazard fill:#1c1212,stroke:#ff5252,stroke-width:2px,rx:6px,ry:6px;
    classDef shortcut fill:#112214,stroke:#00e676,stroke-width:2px,rx:6px,ry:6px;

    class B,C shortcut
    class E,F,G,Q coreSys
    class J,K stateData
    class I,L,M,N,R hazard
```
