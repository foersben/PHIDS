# Research Scope and Modeling Assumptions

PHIDS models plant–herbivore interactions on a discrete spatial grid with deterministic,
tick-based state transitions. It is designed as a computational ecology instrument that
privileges reproducibility, inspectability, and architectural rigor over biological maximalism.

## Represented Phenomena

The current simulator explicitly represents:

- flora energy accumulation and bounded growth,
- predator swarm feeding, movement, reproduction, and starvation,
- signal and toxin mediated defensive behavior,
- mycorrhizal connectivity and root-network relay,
- airflow-influenced diffusion in environmental layers,
- telemetry suitable for comparative scenario analysis.

## Deliberate Simplifications

The current implementation deliberately abstracts away:

- individual organism physiology,
- continuous-space body mechanics,
- stochastic weather fields beyond configured wind vectors,
- unrestricted species cardinality,
- unconstrained biochemical networks.

## Methodological Commitments

PHIDS treats the following engineering rules as scientific commitments because they shape the
space of possible simulations:

- double-buffered environment updates,
- fixed-size matrix design under the Rule of 16,
- global flow-field navigation instead of per-agent pathfinding,
- O(1) spatial-locality queries,
- strict schema validation at the API boundary.

## Interpretation Guidance

Readers should interpret PHIDS as:

- a deterministic ecological simulator,
- a controlled environment for comparative scenario studies,
- an executable architectural model of data-oriented simulation design.

Readers should not interpret PHIDS as:

- a full biophysical ecosystem model,
- a continuous-time differential-equation solver,
- a free-form agent sandbox unconstrained by memory and performance invariants.

## Implementation Anchors

- `src/phids/api/schemas.py`
- `src/phids/engine/loop.py`
- `src/phids/engine/core/biotope.py`
- `src/phids/engine/core/ecs.py`
- `src/phids/shared/constants.py`
