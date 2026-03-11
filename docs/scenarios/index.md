# Scenarios

Scenarios are the formal experimental inputs of PHIDS. They define the biotope, species,
interaction matrices, trigger rules, placements, and global simulation parameters required to
instantiate a deterministic run.

## Canonical Schema

The authoritative scenario model is `phids.api.schemas.SimulationConfig`.

Supporting runtime and UI workflows are implemented in:

- `src/phids/io/scenario.py`
- `src/phids/api/ui_state.py`
- `src/phids/api/main.py`

## Scenario Thesis

In PHIDS, a scenario is not just a startup file. It is the formal specification of an experiment.
It defines what may be executed, what may be reproduced, and what may be exported or compared.

## Canonical Scenario Chapters

- [`schema-and-curated-examples.md`](schema-and-curated-examples.md)
- [`scenario-authoring-and-trigger-semantics.md`](scenario-authoring-and-trigger-semantics.md)
- [`curated-example-catalog.md`](curated-example-catalog.md)

## What a Scenario Encodes Today

The current documentation and tests establish that scenarios encode:

- grid dimensions and environmental parameters,
- flora and predator species definitions,
- diet compatibility and trigger-rule encoding,
- initial placement semantics,
- mycorrhizal-network parameters,
- termination thresholds,
- curated example scenario intent,
- import/export and draft loading behavior.

## Scenario Lifecycle in Practice

PHIDS currently supports three closely related scenario representations:

1. **Draft authoring state** in `phids.api.ui_state.DraftState`,
2. **Validated schema state** in `phids.api.schemas.SimulationConfig`,
3. **Live runtime state** inside `phids.engine.loop.SimulationLoop`.

The important boundary is that only `SimulationConfig` is an executable experiment description.
Draft state is editable and server-owned; live runtime is operational and time-advancing.

This means scenario work in PHIDS is a compilation flow:

- edit draft data,
- normalize it through `build_sim_config()`,
- import/export through the same schema boundary,
- load it into the engine when ready.

## Substance and Trigger Semantics

Substance behavior is currently expressed across two authoring layers:

- `SubstanceDefinition` in the draft describes the behavior of a signal or toxin,
- trigger rules bind that substance to specific flora/predator interactions,
- `build_sim_config()` compiles the combined result into flora `triggers` entries inside the
  exported `SimulationConfig`.

This is why imported scenarios do not store a separate top-level substance registry: the executable
schema carries trigger payloads attached to flora species, while the builder reconstructs editable
substance definitions when importing JSON.

## Curated Example Pack

The example pack is not an arbitrary folder of JSON files. It is a curated documentation and
compatibility surface validated by tests under `tests/test_example_scenarios.py`.

In the current project state, examples are expected to:

- remain within Rule-of-16 bounds,
- include both plants and swarms,
- validate as `SimulationConfig`,
- survive actual engine stepping rather than only schema validation.

## Where to Read Next

- For field-by-field scenario boundary details:
  [`schema-and-curated-examples.md`](schema-and-curated-examples.md)
- For trigger logic, activation trees, and authoring guidance:
  [`scenario-authoring-and-trigger-semantics.md`](scenario-authoring-and-trigger-semantics.md)
- For the scientific intent of each bundled example:
  [`curated-example-catalog.md`](curated-example-catalog.md)
