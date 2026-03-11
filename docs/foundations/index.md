# Foundations

This section frames PHIDS as a deterministic scientific model rather than only a software
artifact. Its purpose is to define the ecological abstractions, state variables, and
methodological constraints that shape every implementation decision.

## Current Focus

The current implementation should be read through the following lenses:

- **Deterministic ecological simulation**: every tick is explicitly ordered and reproducible.
- **Data-oriented execution**: state is stored in ECS components and NumPy layers rather than
  ad-hoc object graphs.
- **Fixed configuration bounds**: the Rule of 16 is not merely UI validation; it is a runtime
  architectural invariant.
- **Spatial locality over pairwise search**: local interactions are resolved through the spatial
  hash and grid layers, never through quadratic scans.

## Core Terms

The following terms are used consistently across the current PHIDS documentation set.

- **Scenario** — a validated `SimulationConfig` describing one executable experiment.
- **Draft state** — the mutable `DraftState` edited through the HTMX/Jinja UI before live loading.
- **Live runtime** — the active `SimulationLoop` currently stepping or paused in memory.
- **Trigger rule** — a `(flora, predator) -> substance` defense rule, optionally gated by a nested
  activation-condition tree.
- **Substance definition** — the physical/biological behavior of one signal or toxin layer as edited
  in `DraftState` and compiled into flora trigger payloads.
- **Spatial hash** — the O(1) locality index used by the ECS for occupancy and nearby-entity queries.
- **Double buffering** — the rule that environmental logic reads current layers and writes only to
  dedicated write buffers before swapping.

## Normative Invariants

The foundations of PHIDS are expressed not just in theory but in architectural rules that remain
visible throughout the codebase and test suite.

### Determinism

The simulation advances in an explicit phase order through `SimulationLoop.step()`. This makes tick
ordering inspectable and reproducible.

### Bounded configuration space

Species and substance counts are bounded by the Rule of 16. These caps are part of the runtime
design, not merely UI convenience checks.

### Server-owned state transitions

The UI edits `DraftState`; only an explicit load action creates or replaces a live `SimulationLoop`.
This keeps authoring state separate from execution state.

### Locality-sensitive interaction

PHIDS resolves neighborhood behavior through the ECS spatial hash and grid layers. The model should
be understood as locality-aware and deliberately non-quadratic.

### Vectorized environmental representation

Environmental layers are NumPy-backed matrices owned by `GridEnvironment`, not Python object graphs.
This is both a performance choice and a modeling commitment.

## Current Implementation Anchors

- `phids.api.schemas.SimulationConfig`
- `phids.engine.loop.SimulationLoop`
- `phids.engine.core.ecs.ECSWorld`
- `phids.engine.core.biotope.GridEnvironment`
- `phids.shared.constants`

## Interpretation Boundary

This section defines the conceptual framing for the simulator as it exists now. Historical design
material remains available for provenance in:

- `legacy/2026-03-11/comprehensive_description.md`
- `legacy/2026-03-11/technical_requirements.md`

Those archived documents are useful background, but the current `foundations/` pages should be read
as the canonical explanation of present-day PHIDS behavior.
