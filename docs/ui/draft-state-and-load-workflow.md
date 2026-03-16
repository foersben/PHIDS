# Draft State and Load Workflow

The most important UI-specific invariant in PHIDS is that editable builder state is **not** the live simulation. The server-side `DraftState` functions as a controlled staging area in which an operator can assemble, normalize, inspect, import, and export a scenario before committing it to an executable `SimulationLoop`. This distinction is foundational to the control-center architecture: it prevents exploratory authoring from mutating the active runtime and makes scenario preparation a deliberate, inspectable process rather than an accumulation of hidden side effects.

This chapter documents that workflow as an operational pipeline. It explains why draft state exists, how `DraftService` preserves structural invariants during editing, how `DraftState.build_sim_config()` compiles builder state into the canonical schema boundary, and what exactly happens when a draft is promoted into live runtime state. The objective is to make the draft-to-live transition legible both to operators using the UI and to contributors maintaining the builder internals.

## Why Draft State Exists

PHIDS deliberately does not allow the browser to incrementally mutate the live engine directly.
Instead, the UI invokes `DraftService` (`src/phids/api/services/draft_service.py`) to mutate
a server-side draft object defined in `src/phids/api/ui_state.py`.

This design centralizes:

- validation logic,
- Rule-of-16 enforcement,
- matrix compaction rules after deletions,
- scenario import/export semantics,
- conversion from operator-facing builder state to `SimulationConfig`.

## Core Objects

### `DraftState`

`DraftState` is a dataclass state container that accumulates the full scenario-builder state. It owns:

- scenario metadata,
- biotope dimensions and global parameters,
- mycorrhizal settings,
- flora and predator species lists,
- diet compatibility matrix,
- trigger rules,
- substance definitions,
- initial plant and swarm placements.

### `DraftService`

`DraftService` is the imperative mutation layer for draft editing. It executes species compaction,
diet-matrix resizing, trigger-tree updates, and placement mutations against a supplied
`DraftState` instance.

### `SimulationConfig`

`SimulationConfig` is the validated, canonical experiment schema used by the engine. Draft state
must be transformed into this type before becoming executable.

### `SimulationLoop`

`SimulationLoop` is the live runtime produced when a `SimulationConfig` is loaded.

## The Draft-to-Live Pipeline

The current UI workflow can be summarized as follows:

```mermaid
flowchart TD
	A[Operator edits builder controls] --> B[Route calls DraftService]
	B --> C[Server renders updated HTML partial]
	C --> D[Operator continues editing / previewing]
	D --> E[POST /api/scenario/load-draft]
	E --> F[DraftState.build_sim_config()]
	F --> G[Validated SimulationConfig]
	G --> H[SimulationLoop(config)]
```

The key transition occurs at `POST /api/scenario/load-draft`: prior to that point, the UI is
editing draft-only state.

## `DraftState` as Scenario Accumulator

`DraftState` remains the canonical accumulator of draft data, while `DraftService` owns the
mutation procedures that preserve structural consistency.

### Species, substances, and matrix maintenance

When flora, predator, or substance registries are edited, `DraftService` performs coordinated
maintenance of:

- sequential species IDs,
- sequential substance IDs,
- diet matrix dimensions,
- trigger-rule references,
- nested activation-condition references,
- placement ledgers and precursor references.

This coordination is essential because the builder edits a bounded scientific model with coupled
indices. A deleted substance is not merely removed from a table row; the deletion must also
eliminate orphaned trigger rules and renumber surviving chemical references so subsequent
`SimulationConfig` construction remains valid.

### Trigger rule accumulation

Trigger rules are stored explicitly as `TriggerRule` objects rather than embedded only in table
cells. This supports multiple substance rules per `(flora, predator)` pair and allows nested
activation-condition trees to be edited and preserved.

### Placement accumulation

Draft placements are stored as explicit `PlacedPlant` and `PlacedSwarm` entries that remain
editable until the draft is committed to a live simulation.

## Building a `SimulationConfig`

The method `DraftState.build_sim_config()` is the critical transformation step.

It currently:

- rejects drafts with no flora or no predator species,
- reconstructs trigger information by combining trigger rules with substance definitions,
- injects trigger lists into flora species entries,
- compacts diet-matrix rows to the active species dimensions,
- converts placements into schema types,
- constructs a fully validated `SimulationConfig`.

This means the draft is **not itself** the final schema object. It is a richer editing structure
that must be normalized and validated before execution or export.

Termination controls configured in the biotope editor (`Z2`, `Z4`, `Z6`, `Z7`) are part of this compilation boundary. They remain inert draft values until `build_sim_config()` materializes them into executable schema fields consumed by `check_termination()`.

## Import Workflow

`POST /api/scenario/import` follows the reverse direction:

1. uploaded JSON is parsed,
2. validated as `SimulationConfig`,
3. trigger rules are reconstructed from imported flora triggers,
4. substance definitions are reconstructed from the imported trigger set,
5. a new `DraftState` is created and installed via `set_draft()`.

Notably, import populates the draft but does not by itself start a live simulation.

## Export Workflow

`GET /api/scenario/export` first calls `draft.build_sim_config()` and then serializes the resulting
schema object to JSON.

This has an important methodological consequence: exported scenarios are not ad-hoc UI state
dumps. They are schema-normalized configurations.

## Load-Draft Workflow

`POST /api/scenario/load-draft` performs the draft-to-runtime transition.

Its current behavior includes:

- retrieving the active draft,
- building a validated `SimulationConfig`,
- cancelling any existing background simulation task if necessary,
- creating a new `SimulationLoop(config)`,
- resetting the background task handle,
- synchronizing simulation substance names for UI/runtime display.

The route returns an updated status-badge HTML fragment because it is primarily designed for the
HTMX control surface.

After load, runtime cadence can be adjusted independently through the live speed control in the grid toolbar (`PUT /api/simulation/tick-rate`). This changes live execution pace without mutating the already-compiled draft.

## Preview Without a Live Simulation

One of the most distinctive current PHIDS behaviors is that some UI routes can still expose useful
information even before a live simulation exists.

For example:

- placement preview data can be rendered from the draft,
- cell-detail inspection can operate in a draft-preview mode,
- mycorrhizal links can be previewed from draft placements.

This means the draft is not merely pre-runtime storage; it is also the source of truth for the
builder’s preview experience.

## Single-Operator Assumption

The `ui_state.py` module explicitly notes that `DraftState` is a module-level singleton with no
additional concurrency locking, because the current application is designed as a single-operator
workbench.

This is an important current-state constraint. The builder is not presently modeled as a
multi-user collaborative editing environment.

## Failure Modes and Explicit Errors

The draft/load workflow is designed to fail visibly rather than silently.

Examples include:

- `ValueError` when a draft lacks the minimum required species,
- `400` responses when export or load-draft cannot build a valid config,
- `422` responses when imported JSON does not validate,
- reference cleanup when species or substances are removed from draft structures.

## Verified Current-State Evidence

This chapter is grounded in:

- `src/phids/api/ui_state.py`
- `src/phids/api/services/draft_service.py`
- `src/phids/api/routers/config.py`
- `src/phids/api/main.py`
- `tests/test_ui_state.py`
- `tests/test_ui_routes.py`
- `tests/test_api_builder_and_helpers.py`

## Where to Read Next

- For the broader interface taxonomy: [`../interfaces/rest-and-websocket-surfaces.md`](../interfaces/rest-and-websocket-surfaces.md)
- For the control-center HTML and HTMX structure: [`htmx-partials-and-builder-routes.md`](htmx-partials-and-builder-routes.md)
