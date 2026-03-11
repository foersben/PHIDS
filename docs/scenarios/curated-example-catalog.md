# Curated Example Catalog

The example scenarios under `examples/` are a curated part of the PHIDS project surface. They are
not disposable samples. Each scenario is schema-validated, stepped through the runtime in tests,
and intended to demonstrate a distinct ecological or architectural pattern.

This chapter catalogs the current example pack in scientific terms.

## Why the Example Pack Matters

The curated examples serve several roles simultaneously:

- regression fixtures for scenario validation,
- runtime smoke tests,
- operator-facing demonstrations of supported interactions,
- canonical references for scenario-authoring patterns.

The test suite also enforces that curated examples include both plants and swarms, ensuring that the
pack exhibits actual competitive or antagonistic dynamics rather than one-sided static scenes.

## Current Curated Example Set

The currently enforced example stems are:

- `dry_shrubland_cycles`
- `meadow_defense`
- `mixed_forest_understory`
- `rectangular_crossfire`
- `root_network_alarm_chain`
- `wind_tunnel_orchard`

## 1. `dry_shrubland_cycles`

### Scientific emphasis

A dry, open system with moderate wind and a compact defensive logic stack.

### Architectural emphasis

- mycorrhizal networking is conservative,
- one signal functions as an early warning layer,
- both repellent and lethal toxin logic appear in chained form,
- camouflage is present on one flora species.

### Good for studying

- threshold-triggered signals,
- signal-to-toxin escalation,
- how modest wind and sparse vegetation shape local competition.

## 2. `meadow_defense`

### Scientific emphasis

A more classic meadow-style defense scenario with layered plant strategies.

### Architectural emphasis

- one flora species carries no triggers and acts as a baseline resource,
- one clover-like species provides signal behavior,
- yarrow-like defense combines camouflage and multi-predator toxin logic,
- both repellent and lethal toxins are represented.

### Good for studying

- heterogeneous flora roles in one biotope,
- how signal precursors mediate toxin deployment,
- coexistence of multiple herbivore guilds attacking different flora subsets.

## 3. `mixed_forest_understory`

### Scientific emphasis

A denser, more networked understory in which multiple flora species participate in signal and toxin
chains.

### Architectural emphasis

- inter-species mycorrhizal networking is enabled,
- root growth is faster than in many other examples,
- multiple flora species contribute different pieces of the defensive chain,
- camouflage and chained toxins coexist.

### Good for studying

- multi-species defensive specialization,
- denser local interaction structure,
- the interplay between root-network connectivity and compound activation logic.

## 4. `rectangular_crossfire`

### Scientific emphasis

A more corridor-like or lane-like spatial setup with multiple confrontation zones.

### Architectural emphasis

- moderate wind but strong structured placements,
- parallel defensive behaviors across different flora clusters,
- both signal-first and toxin-escalation patterns,
- repeated confrontation fronts rather than a single dense cluster.

### Good for studying

- spatially separated local battles,
- repeated predator–flora engagement patterns,
- how localized geometry affects conflict propagation.

## 5. `root_network_alarm_chain`

### Scientific emphasis

The canonical mycorrhizal-relay example in the pack.

### Architectural emphasis

- inter-species mycorrhizal connectivity is enabled,
- root growth cadence is faster than the default,
- signal velocity is elevated,
- nested `any_of` and `all_of` activation trees form a chain of progressively conditioned responses.

### Good for studying

- below-ground signal transfer,
- multi-step activation logic,
- how root-network connectivity changes defensive timing and reach.

## 6. `wind_tunnel_orchard`

### Scientific emphasis

The canonical wind-dominated orchard example.

### Architectural emphasis

- stronger wind than the other curated scenarios,
- multiple predator species interacting with different flora,
- compound activation logic that depends on signals and alternative enemy pathways,
- both repellent and lethal toxin strategies in an orchard-style layout.

### Good for studying

- the importance of atmospheric transport,
- how wind can shape signaling reach and timing,
- multi-species pressure on structured plantings.

## Comparative Reading Guide

The examples can be read as a progression of increasing structural complexity.

### Simpler trigger layering

- `dry_shrubland_cycles`
- `meadow_defense`

### Stronger spatial structuring

- `rectangular_crossfire`
- `wind_tunnel_orchard`

### Stronger mycorrhizal and chain activation logic

- `mixed_forest_understory`
- `root_network_alarm_chain`

## Authoring Lessons from the Pack

Taken together, the curated examples teach several scenario-authoring lessons.

### Use species roles deliberately

The strongest examples assign distinct ecological and defensive roles to different flora species
rather than making all plants interchangeable.

### Treat triggers as staged logic

The examples frequently use signals as precursor states and toxins as escalated responses.

### Use placements as part of the experiment

Initial placement geometry matters. The examples are spatial experiments, not merely species lists.

### Tune mycorrhiza and wind to express the intended mechanism

Scenarios that emphasize airborne propagation and scenarios that emphasize root relay use different
parameter regimes.

## Test and Documentation Status

The current test suite validates that every example:

- can be loaded as a valid scenario,
- contains plants and swarms,
- remains within species bounds,
- can step through the runtime without immediate errors.

This makes the curated pack both a documentation layer and a tested compatibility contract.

## Verified Current-State Evidence

- `examples/*.json`
- `tests/test_example_scenarios.py`
- `src/phids/io/scenario.py`
- `src/phids/engine/loop.py`

## Where to Read Next

- For the scenario language itself: [`scenario-authoring-and-trigger-semantics.md`](scenario-authoring-and-trigger-semantics.md)
- For the schema boundary and import/export role: [`schema-and-curated-examples.md`](schema-and-curated-examples.md)
- For runtime defensive behavior: [`../engine/signaling.md`](../engine/signaling.md)
