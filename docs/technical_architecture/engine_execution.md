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
stateDiagram-v2
    [*] --> Idle : Application starts

    Idle --> Loaded : POST /api/scenario/load
    Loaded --> Running : POST /api/simulation/start
    Running --> Paused : POST /api/simulation/pause
    Paused --> Running : POST /api/simulation/pause
    Running --> Terminated : Z1–Z7 condition met
    Terminated --> Loaded : POST /api/scenario/load (reload)

    state Running {
        [*] --> FlowField
        FlowField --> Lifecycle : compute_flow_field (numba)
        Lifecycle --> Interaction : grow / reproduce / cull
        Interaction --> Signaling : feed / upkeep / mitosis
        Signaling --> Telemetry : synthesise / relay / local toxins
        Telemetry --> CheckTermination : record Polars row
        CheckTermination --> FlowField : not terminated
        CheckTermination --> [*] : terminated
    }
```
