# Scenario Authoring & Schema

Scenarios in PHIDS form the strict boundaries of the ecological experiment. A scenario dictates the grid dimensions, initial biomass distributions, trophic links (who eats what), and the specific biochemical triggers deployed by flora when attacked. At the engine level, all scenarios are structurally validated against the `SimulationConfig` Pydantic schema before execution.

## The Rule of 16 Configuration Bounds

A fundamental engineering constraint within the simulation loop is the avoidance of dynamic memory allocations during high-frequency execution. If a new species was dynamically introduced, matrices tracking interaction rules would need to be rebuilt, stalling the CPU.

To circumvent this, configurations are structurally bounded. Every scenario is permitted a maximum of:

-   **16 Flora Species**
-   **16 Herbivore Species**
-   **16 Substance Profiles**

These indices translate directly into fixed $(16 \times 16)$ boolean matrices for diet compatibility and integer matrices for defense behavior. Exceeding these bounds at the API or file ingress stage will result in a validation rejection, ensuring the simulation runs predictably.

## Interaction Matrices

Scenarios orchestrate behavior through explicit matrices, which are fully editable via the HTMX UI Draft State:

1.  **Diet Compatibility Matrix**: A $16 \times 16$ boolean matrix determining whether herbivore $E_i$ can metabolize flora $P_j$. If incompatible, an attempted feeding event resolves into rejection, prompting a randomized displacement of the swarm away from the plant.
2.  **Trigger Matrix**: A $16 \times 16$ mapping detailing which specific substance $S_x$ a given flora species $P_j$ synthesizes upon localized attack by herbivore $E_i$. A single plant can synthesize lethal toxins against one grazer while emitting volatile signals when grazed by another.

## Import/Export Pathways

Scenario parameters are serialized directly to and from normalized JSON payloads (`load_scenario_from_json`, `scenario_to_json`). The control center UI facilitates the injection of exported JSONs directly into the mutable `DraftState` for manual iteration.

Once the operator finalizes the scenario, the draft is pushed into the live `SimulationConfig`. This process ensures absolute separation between experimental setup and experimental execution.

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
