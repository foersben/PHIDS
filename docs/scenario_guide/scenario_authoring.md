# Scenario Authoring & Schema

Scenarios in PHIDS form the boundaries of the ecological experiment. A scenario dictates grid bounds, initial biomass distributions, trophic links, and the specific biochemical triggers deployed. At the engine level, all scenarios converge on the `SimulationConfig` Pydantic model.

## The Rule of 16 Configuration Bounds

A fundamental engineering constraint within the simulation loop is the avoidance of dynamic memory allocations. To support this, configurations are structurally bounded. Scenarios are permitted a maximum of:
- **16 Flora Species**
- **16 Herbivore Species**
- **16 Substance Profiles**

These indices translate directly into fixed $(16 \times 16)$ interaction matrices for diet and defense behavior. Exceeding these bounds at the API or file ingress stage will result in rejection.

## Interaction Matrices

Scenarios orchestrate behavior through matrices:

1. **Diet Compatibility Matrix**: A boolean matrix determining whether herbivore $E_i$ can metabolize flora $P_j$. If incompatible, feeding resolves into rejection and randomized displacement.
2. **Trigger Matrix**: A mapping detailing which specific substance $S_x$ a given flora species $P_j$ synthesizes upon localized attack by herbivore $E_i$.

## Import/Export Pathways

Scenario parameters are serialized directly to and from normalized JSON payloads (`load_scenario_from_json`, `scenario_to_json`). The control center UI facilitates the injection of exported JSONs directly into the mutable `DraftState` for iteration, before finalizing the design back into the live `SimulationConfig`.

```mermaid
flowchart TD
    A([Tick Start]) --> B{Herbivore at plant cell?<br/>via Spatial Hash O1}
    B -- No --> END([No synthesis])
    B -- Yes --> C{population ≥ n_i,min?}
    C -- No --> END
    C -- Yes --> D{Precursor signal active?}
    D -- No, required --> END
    D -- Yes / not required --> E[Start synthesis timer<br/>T_s_x ticks]
    E --> F{synthesis_remaining = 0?}
    F -- No --> G[Decrement counter]
    G --> F
    F -- Yes --> H[Substance ACTIVE]
    H --> I{is_toxin?}
    I -- Signal --> J[Emit into signal_layers<br/>Relay via mycorrhizal network<br/>SciPy convolve2d diffusion]
    I -- Toxin --> K{lethal?}
    K -- Yes --> L[Apply β casualties to swarms]
    K -- No --> M{repellent?}
    M -- Yes --> N[Set swarm.repelled = True<br/>k-tick random walk]
    M -- No --> O[Passive toxin presence]
    L --> P{Trigger still active?}
    N --> P
    O --> P
    P -- Yes --> H
    P -- No, aftereffect > 0 --> Q[Decrement T_k aftereffect]
    Q --> H
    P -- No, aftereffect = 0 --> R[Deactivate / GC substance entity]
    R --> END2([Tick End])
    J --> END2
```
