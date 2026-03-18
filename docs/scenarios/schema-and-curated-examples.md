# Scenario Schema and Curated Example Pack

Scenarios are the formal experimental units of PHIDS. Every reproducible run begins as a validated `SimulationConfig`, whether authored as JSON, assembled through the builder UI, or exported from prior draft state. In methodological terms, the scenario boundary is the point at which editable configuration intent becomes an executable ecological specification.

This chapter documents that boundary and the role of the curated example pack as a compatibility and reproducibility surface. It explains how schema validation, import/export pathways, and runtime smoke execution together establish that a scenario is not only syntactically valid, but scientifically and computationally admissible under current PHIDS invariants.

## Canonical Scenario Boundary

The authoritative scenario type is `phids.api.schemas.SimulationConfig`.

It defines, in a single validated object:

- grid dimensions,
- tick budget and stream rate,
- wind parameters,
- signal and toxin layer counts,
- flora species definitions,
- herbivore species definitions,
- diet compatibility,
- initial placements,
- mycorrhizal configuration,
- trigger information embedded into flora species.

This means that PHIDS scenarios are not loose configuration fragments; they are executable,
validated experiment descriptions.

## Scenario I/O Pathways

Current scenario I/O is concentrated in `src/phids/io/scenario.py` and the API routes in
`src/phids/api/main.py`.

### File-based loading

`load_scenario_from_json(path)` reads JSON and validates it into `SimulationConfig`.

### Programmatic loading

`load_scenario_from_dict(data)` validates already-decoded mappings.

### Serialization

`scenario_to_json(config, path=None)` emits a normalized JSON representation of a validated config.

### UI-mediated import/export

The control center routes:

- `GET /api/scenario/export`
- `POST /api/scenario/import`
- `POST /api/scenario/load-draft`

bridge between `DraftState` and the canonical scenario schema.

## Scenario Normalization Principle

A key current-state property of PHIDS is that exported scenarios are normalized through the schema
boundary rather than dumped from arbitrary builder internals. Conversely, imported scenarios are
validated first and only then reconstructed into draft state.

This gives scenarios a strong role as reproducible scientific artifacts.

## Structural Expectations

The current test suite verifies several important expectations for scenarios.

### Trigger persistence mode is explicit

`TriggerConditionSchema` now supports an `irreversible` flag to model SAR-like permanent induced
defense once activated. Curated examples currently keep this mode disabled for comparability and
therefore declare `"irreversible": false` across trigger entries.

### Plants and swarms are both required in curated examples

The curated example pack is expected to include both:

- initial plant placements, and
- initial swarm placements.

This rule is important because the examples are intended to exhibit actual plant–herbivore
competition rather than degenerate one-sided dynamics.

### Rule-of-16 compatibility

The example tests also verify that scenario species counts remain within the bounded architecture:

- at most 16 flora species,
- at most 16 herbivore species.

## Curated Example Pack

The current example pack is treated as a compatibility and documentation surface, not merely as an
assortment of convenience files.

The curated stems currently enforced by tests are:

- `dry_shrubland_cycles`
- `meadow_defense`
- `mixed_forest_understory`
- `rectangular_crossfire`
- `root_network_alarm_chain`
- `wind_tunnel_orchard`

These files live under `examples/` and are validated by dedicated tests.

## Why the Examples Matter

The example pack serves several roles simultaneously:

- regression coverage for scenario validation,
- smoke tests for runtime stepping,
- user-facing demonstrations of supported dynamics,
- documentation anchors for common scenario patterns.

Because of this, example scenarios should be maintained with the same care as public API surfaces.

## Runtime Verification of Examples

The current tests do more than schema validation. They also instantiate `SimulationLoop` for each
example and step the runtime for a bounded number of ticks, confirming that:

- snapshots are produced,
- plant-energy layers are present in state output,
- the configuration can survive actual engine execution.

This is an important scientific-documentation point: curated scenarios are not just syntactically
valid; they are executed against the current runtime.

## Scenario Authoring Implications

Authors of future scenarios should treat the following as current best practice:

- include both plants and swarms in any curated demonstration scenario,
- remain within Rule-of-16 bounds,
- think of the scenario as an experimental specification rather than a UI preset,
- ensure that the scenario still steps meaningfully under the current engine.

## Verified Current-State Evidence

This chapter is grounded in:

- `src/phids/io/scenario.py`
- `src/phids/api/schemas.py`
- `src/phids/api/ui_state.py`
- `src/phids/api/main.py`
- `tests/e2e/scenarios/test_example_scenarios.py`

## Where to Read Next

- For trigger logic and authoring guidance: [`scenario-authoring-and-trigger-semantics.md`](scenario-authoring-and-trigger-semantics.md)
- For a scientific overview of each curated example: [`curated-example-catalog.md`](curated-example-catalog.md)
- For interface-level import/export semantics: [`../interfaces/rest-and-websocket-surfaces.md`](../interfaces/rest-and-websocket-surfaces.md)
- For draft conversion into live runtime: [`../ui/draft-state-and-load-workflow.md`](../ui/draft-state-and-load-workflow.md)
