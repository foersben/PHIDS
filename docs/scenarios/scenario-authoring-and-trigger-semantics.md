# Scenario Authoring and Trigger Semantics

PHIDS scenarios are not merely startup files. They are formal experimental specifications that must
encode ecological structure, activation logic, bounded state spaces, and reproducible initial
conditions in a schema-valid form.

This chapter documents the current scenario language with particular emphasis on trigger semantics,
substance activation logic, and the transformation from editable draft state to executable runtime
configuration.

## Scenario Language as Experimental Specification

The canonical scenario object is `SimulationConfig` in `src/phids/api/schemas.py`.

It defines the minimum complete specification necessary to instantiate a live `SimulationLoop`:

- biotope dimensions,
- tick and streaming parameters,
- signal and toxin layer counts,
- wind fields,
- flora and herbivore species definitions,
- diet compatibility,
- initial placements,
- mycorrhizal settings,
- termination thresholds.

In PHIDS, this is the reproducibility boundary: once a scenario has been validated into
`SimulationConfig`, it is an executable experiment definition.

## Core Structural Elements

### Flora species

Each `FloraSpeciesParams` entry defines:

- energy parameters,
- growth behavior,
- reproduction spacing and cost,
- camouflage behavior,
- a list of `TriggerConditionSchema` entries.

This means flora species carry both baseline biological parameters and their encoded defensive
response repertoire.

### Herbivore species

Each `HerbivoreSpeciesParams` entry defines:

- `energy_min`,
- `velocity`,
- `consumption_rate`,
- `reproduction_energy_divisor`.

These values shape the swarm behavior later consumed by the interaction phase.

### Diet matrix

The `DietCompatibilityMatrix` is indexed by herbivore species first and flora species second. It is a
bounded boolean edibility relation rather than a continuous preference model.

### Initial placements

`InitialPlantPlacement` and `InitialSwarmPlacement` define where the experimental system begins in
space.

## TriggerConditionSchema

The most expressive part of the current scenario language is `TriggerConditionSchema`.

Each trigger entry specifies not only *when* a response should occur, but also *what kind of
substance behavior* will result from that response.

A trigger currently includes:

- `herbivore_species_id`
- `min_herbivore_population`
- `substance_id`
- `synthesis_duration`
- `is_toxin`
- `lethal`
- `lethality_rate`
- `repellent`
- `repellent_walk_ticks`
- `aftereffect_ticks`
- `irreversible`
- `activation_condition`
- `energy_cost_per_tick`

This makes the trigger structure more like a compact biochemical-defense rule than a simple matrix
lookup.

## Activation Conditions

PHIDS currently supports nested activation-condition trees through the discriminated union
`ConditionNode`.

Supported node kinds are:

- `herbivore_presence`
- `substance_active`
- `all_of`
- `any_of`

This allows scenarios to encode multi-stage defensive logic such as:

- emit a signal only when a threshold herbivore population is present,
- emit a toxin only after another signal is active,
- allow activation through one of several ecological pathways,
- require conjunctions of herbivore presence and precursor substances.

## Legacy Precursors and Normalization

`TriggerConditionSchema` still contains legacy precursor fields:

- `precursor_signal_id`
- `precursor_signal_ids`

The current schema layer normalizes these into the richer `activation_condition` representation.

This is an important current-state behavior: older, signal-only precursor logic is translated into a
condition-tree representation rather than handled as a wholly separate runtime concept.

## DraftState as Authoring Structure

The authoring UI does not edit `SimulationConfig` directly. It edits `DraftState`.

`DraftState` is a richer authoring structure that maintains:

- mutable species lists,
- diet-matrix resizing,
- trigger-rule lists,
- nested condition trees,
- substance definitions,
- placement previews.

This allows the UI to preserve editability and reference compaction while still exporting a clean,
validated scenario schema.

## Draft-to-Schema Transformation

`DraftState.build_sim_config()` is a crucial normalization step.

It currently:

- rejects drafts without at least one flora and one herbivore species,
- reconstructs trigger lists per flora species,
- joins trigger rules with substance definitions,
- trims diet-matrix rows to active dimensions,
- converts placements into schema types,
- produces a validated `SimulationConfig`.

This means authoring state is not dumped directly into runtime execution. It is compiled into a
schema-valid experiment specification first.

## Import and Export Semantics

### Import

`POST /api/scenario/import` validates uploaded JSON as `SimulationConfig` and then reconstructs a
fresh `DraftState`.

### Export

`GET /api/scenario/export` first builds a valid `SimulationConfig` and then serializes it.

This makes import/export behavior symmetric around the schema boundary, which is a strong
reproducibility property.

## Scenario Authoring Guidance

In the current PHIDS design, scenario authors should think in layers.

### 1. Define the ecological cast

Choose flora and herbivore species with bounded IDs and explicit interaction roles.

### 2. Define who can eat whom

Use the diet matrix to determine which herbivore–flora pairings are biologically active.

### 3. Define defensive responses

Use trigger rules to specify:

- which herbivore species trigger a response,
- what population threshold matters,
- whether the response is a signal or toxin,
- how long synthesis takes,
- how long aftereffects persist,
- whether activation becomes irreversible after first activation,
- what activation-condition logic must already hold.

### 4. Define spatial starting conditions

Initial placements determine whether interactions begin immediately, whether signaling chains must
propagate over time, and whether the example demonstrates wind-dominated or root-network-dominated
behavior.

## Example Patterns from the Curated Pack

The current curated examples illustrate different authoring styles.

### `dry_shrubland_cycles`

This scenario shows a comparatively compact trigger structure in which:

- one signal acts as an initial warning layer,
- toxins can depend on signal activity plus herbivore context,
- wind exists but mycorrhizal networking is conservative.

### `root_network_alarm_chain`

This scenario is the clearest example of chained activation logic and mycorrhizal relay. It uses:

- multiple flora species,
- nested `any_of` and `all_of` activation conditions,
- inter-species mycorrhizal connectivity,
- faster root growth and signal transfer than most examples.

### `wind_tunnel_orchard`

This scenario emphasizes atmospheric transport and compound gating. It includes:

- stronger wind,
- multiple herbivore species,
- nested logic in which repellent and lethal toxins depend on intermediate signal states and herbivore
  combinations.

## Current Curated-Example Policy on SAR-like Mode

The scenario language now supports `irreversible` trigger semantics (SAR-like permanent induced
defense once active). To keep the curated pack behavior easy to compare across releases, all current
examples under `examples/` explicitly set:

- `"irreversible": false`

for every trigger rule.

## How Trigger Logic Reaches Runtime

At runtime, the signaling system consumes these trigger schemas by:

- evaluating co-located herbivore thresholds,
- spawning `SubstanceComponent` entities when necessary,
- advancing synthesis timers,
- evaluating activation-condition trees,
- activating and emitting signals or toxins.

Thus scenario-side trigger definitions are not abstract annotations; they are directly interpreted by
`run_signaling()`.

## Constraints Authors Must Respect

Scenario authors must remain within the architectural limits enforced by schemas and runtime design.

### Rule of 16

Species and substance counts are bounded.

### Placement validity

Initial placements must reference known species IDs.

### Positive biological and timing parameters

Many fields are constrained by the schema to be positive or non-negative.

### Example-pack competition rule

For curated examples, both plants and swarms should be present so that ecological competition is
actually exhibited.

## Evidence from Tests

The following tests support the current semantics described here:

- `tests/test_ui_state.py`
- `tests/test_api_builder_and_helpers.py`
- `tests/test_ui_routes.py`
- `tests/test_example_scenarios.py`
- `tests/test_systems_behavior.py`
- `tests/test_schemas_and_invariants.py`

## Verified Current-State Evidence

- `src/phids/api/schemas.py`
- `src/phids/api/ui_state.py`
- `src/phids/api/main.py`
- `src/phids/io/scenario.py`
- `src/phids/engine/systems/signaling.py`
- curated scenarios under `examples/`

## Where to Read Next

- For the curated examples as a catalog: [`curated-example-catalog.md`](curated-example-catalog.md)
- For import/export and draft semantics: [`../ui/draft-state-and-load-workflow.md`](../ui/draft-state-and-load-workflow.md)
- For runtime substance activation behavior: [`../engine/signaling.md`](../engine/signaling.md)
