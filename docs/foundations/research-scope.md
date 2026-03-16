# Research Scope and Modeling Assumptions

PHIDS is a deterministic computational ecology instrument that studies plant-herbivore interaction dynamics under explicit architectural constraints. The simulator is intentionally constructed as a bounded, inspectable system in which biological mechanisms are represented through data-oriented operators over ECS entities and double-buffered grid fields. This scope definition is not a marketing boundary; it is an epistemic boundary that determines which ecological questions can be answered with internal validity.

At runtime, the simulator evolves a coupled state consisting of discrete entities and continuous lattice fields. In compact notation,

$$
\mathcal{X}_{t+1}=\mathcal{T}(\mathcal{X}_t;\Theta),
$$

where $\mathcal{X}_t$ is the complete state at tick $t$, $\Theta$ is the configured species and environment parameterization, and $\mathcal{T}$ is the ordered phase composition executed in `SimulationLoop.step()`. Because the transition is deterministic for fixed initial conditions and parameters, comparative scenario analysis can attribute outcome differences to controlled configuration changes rather than latent runtime stochasticity.

## Represented Ecological Phenomena

The current model explicitly represents bounded flora growth, swarm feeding and dispersal, diet-gated trophic links, induced signaling and toxin defense pathways, mycorrhizal relay structure, and wind-influenced signal transport on environmental layers. It also records telemetry suitable for longitudinal comparison across scenario families, including collapse, persistence, and defensive stabilization regimes.

```mermaid
flowchart LR
    A[Configured initial state] --> B[Deterministic phase updates]
    B --> C[Telemetry and replay capture]
    C --> D[Scenario comparison and inference]
```

## Deliberate Abstraction Boundary

PHIDS does not attempt to model full organism physiology, unconstrained biochemical network complexity, or continuous-space biomechanics. Weather forcing is simplified to configured wind vectors and does not claim atmospheric realism. Species cardinality is bounded by Rule-of-16 constants to preserve fixed-memory behavior and reproducible performance characteristics.

These exclusions are methodological choices that keep the simulator analytically tractable and computationally stable. They should be interpreted as design constraints, not as omissions hidden behind general language.

## Engineering Commitments as Scientific Commitments

Several implementation invariants directly shape the scientific behavior envelope. Double-buffered field updates prevent intra-phase read-after-write contamination. O(1) spatial-hash lookups prevent locality logic from degenerating into global pairwise scans. Global flow-field guidance replaces per-agent path planning, yielding a specific class of movement approximation. Strict schema validation at API ingress constrains admissible experiments to explicitly validated configurations.

Because these constraints alter feasible state trajectories, they are part of the simulator's scientific methodology and must be reported whenever outcomes are interpreted.

## Interpretation Guidance

Results from PHIDS should be interpreted as deterministic outcomes of a bounded ecological operator model. The simulator is well suited for comparative experiments on interaction hypotheses, defensive signaling strategies, and parameter sensitivity under controlled assumptions. It should not be interpreted as a full biophysical ecosystem surrogate, a continuous-time PDE solver for all processes, or a free-form multi-agent sandbox unconstrained by memory and locality invariants.

## Implementation Anchors

Primary implementation anchors for this scope are `src/phids/api/schemas.py`, `src/phids/engine/loop.py`, `src/phids/engine/core/biotope.py`, `src/phids/engine/core/ecs.py`, and `src/phids/shared/constants.py`.
