# Analytics and Export Formats

PHIDS telemetry analytics convert a live ecological run into a compact, tabular record suitable for
comparison, inspection, and export. This chapter documents the current `TelemetryRecorder` model,
the meanings of the collected fields, and the formats exposed by the export layer.

## Role of `TelemetryRecorder`

The telemetry analytics layer is implemented in `src/phids/telemetry/analytics.py` through
`TelemetryRecorder`.

Its job is deliberately narrow and stable:

- sample the ECS world after a completed tick,
- aggregate a small set of canonical ecological metrics,
- cache those rows in memory,
- expose the result as a Polars `DataFrame` for export and rendering.

This makes telemetry the principal summary-scale artifact of a PHIDS run.

## Current Runtime Position

Within `SimulationLoop.step()`, telemetry recording happens only after:

- flow-field generation,
- lifecycle,
- interaction,
- signaling.

Therefore each telemetry row describes the **post-phase state** of that tick rather than an
intermediate state.

## Recorded Fields

The current implementation records the core population/resource metrics together with per-tick plant
death diagnostics.

### `tick`

The tick index associated with the recorded row.

### `total_flora_energy`

The sum of `plant.energy` across all live `PlantComponent` entities.

### `flora_population`

The count of live plant entities.

### `predator_clusters`

The count of live swarm entities.

### `predator_population`

The sum of `swarm.population` across all live `SwarmComponent` entities.

### Plant death diagnostics

The telemetry row also records the immediate plant death causes detected during that tick:

- `death_reproduction`
- `death_mycorrhiza`
- `death_defense_maintenance`
- `death_herbivore_feeding`
- `death_background_deficit`

These fields intentionally span both abundance and resource-state perspectives.

## Analytical Interpretation

The current telemetry fields support several classes of interpretation.

### Resource trajectory

`total_flora_energy` approximates the aggregate energetic capacity of the plant layer.

### Occupancy / persistence

`flora_population` and `predator_clusters` indicate how many discrete entities remain in play.

### Pressure / biomass proxy

`predator_population` provides a coarse measure of herbivore pressure on the system.

Together, these metrics form a compact Lotka–Volterra-style observability surface for comparing runs.
The death-diagnostic columns add an immediate mechanistic layer, making it possible to distinguish
whether plant loss was driven by herbivory, self-funded lifecycle actions, active chemical defense,
or a generic background deficit state.

## In-Memory Representation

`TelemetryRecorder` stores rows first in a Python list of dictionaries and materializes a Polars
`DataFrame` lazily.

Current behavior:

- each `record()` call appends one metrics row,
- the recorder enforces a bounded FIFO retention cap (`MAX_TELEMETRY_TICKS = 10000`),
- the cached dataframe is invalidated,
- `dataframe` rebuilds the Polars structure on demand,
- `get_latest_metrics()` exposes the most recent row for live UI or diagnostics use.

The death-cause counters are injected at `SimulationLoop.step()` scope. Lifecycle, interaction, and
signaling each contribute immediate plant-loss events into the same per-tick accumulator before the
telemetry row is materialized.

This design keeps per-tick recording simple while preserving a convenient tabular export interface.

The retention cap is a memory-safety invariant. Long-running sessions therefore expose a rolling
window of the most recent telemetry rather than unbounded historical growth in backend memory.

## Empty DataFrame Semantics

When no telemetry has yet been recorded, `TelemetryRecorder.dataframe` still returns a DataFrame with
a stable aggregate schema:

- `tick: Int64`
- `total_flora_energy: Float64`
- `flora_population: Int64`
- `predator_clusters: Int64`
- `predator_population: Int64`
- `death_reproduction: Int64`
- `death_mycorrhiza: Int64`
- `death_defense_maintenance: Int64`
- `death_herbivore_feeding: Int64`
- `death_background_deficit: Int64`

This guarantees a consistent typed structure for the export and UI layers before any ticks have
executed.

Once at least one tick has been recorded, the materialised DataFrame additionally contains
per-species flat columns for every species identifier observed across the current retention window:

- `plant_{id}_pop: Int64`
- `plant_{id}_energy: Float64`
- `defense_cost_{id}: Float64`
- `swarm_{id}_pop: Int64`

Missing species for any individual tick are zero-filled, ensuring the DataFrame is fully
rectangular with no null entries regardless of species cardinality or extinction events.

## Export Layer

The export helpers in `src/phids/telemetry/export.py` expose four current functions:

- `export_csv(df, path)`
- `export_json(df, path)`
- `export_bytes_csv(df)`
- `export_bytes_json(df)`

These helpers treat telemetry as tabular data rather than as a custom PHIDS-specific binary format.

## File Formats

### CSV

CSV is the simplest tabular interchange format exposed by PHIDS. It is well-suited for spreadsheet
inspection and downstream plotting pipelines.

### NDJSON

PHIDS’s JSON export currently uses newline-delimited JSON (NDJSON), not a single top-level JSON
array. This matters for consumers that expect streaming-friendly or row-oriented processing.

The API route docstrings and helper names make this explicit.

## API Export Surface

The telemetry export routes in `src/phids/api/main.py` are:

- `GET /api/telemetry/export/csv`
- `GET /api/telemetry/export/json`

Current behavior:

- both operate on the live loop’s telemetry dataframe,
- CSV is returned with `text/csv`,
- JSON export is returned as `application/x-ndjson`,
- both use download-oriented `Content-Disposition` headers.

## UI Telemetry Surface

PHIDS also exposes telemetry in a separate UI-oriented form through:

- `GET /api/telemetry`

This route does not return raw tabular data. Instead, it builds an SVG chart fragment and associated
summary context for the HTMX-polled dashboard.

This is an important current distinction:

- `/api/telemetry/export/*` is for external analysis artifacts,
- `/api/telemetry` is for live operator-facing visualization.

For browser table previews, PHIDS intentionally renders a bounded recent-tail projection (after
optional decimation) to prevent DOM overload from multi-thousand-row HTML payloads.

## Artifact Lifecycle

The current telemetry artifact flow can be summarized as follows:

```mermaid
flowchart TD
    A[SimulationLoop.step completes ecological phases] --> B[TelemetryRecorder.record(world, tick)]
    B --> C[Row appended to in-memory telemetry buffer]
    C --> D[Polars DataFrame materialized on demand]
    D --> E1[CSV / NDJSON export helpers]
    D --> E2[HTMX telemetry SVG builder]
```

This diagram emphasizes that one telemetry source feeds both external export and live visualization.

## Evidence from Tests

The current test suite verifies key telemetry/export behaviors.

### Loop integration

`tests/test_termination_and_loop.py` verifies that stepping a simulation updates telemetry,
produces at least one telemetry row, and exposes the plant-death diagnostic columns.

### Per-species accumulation and flat column layout

`tests/test_telemetry_per_species.py` verifies that `TelemetryRecorder.record()` correctly
accumulates per-species population, energy, and defense-cost accumulators from a multi-species ECS
world, and that `TelemetryRecorder.dataframe` flattens those accumulators into typed Polars scalar
columns (`plant_{id}_pop`, `plant_{id}_energy`, `defense_cost_{id}`, `swarm_{id}_pop`) with
zero-filling for absent species and deterministic column ordering.

### API export behavior

`tests/test_additional_coverage.py` verifies that CSV and NDJSON export routes return usable data.

### File and bytes export helpers

`tests/test_additional_coverage.py` also exercises the file-writing and bytes-returning helper
functions directly.

### UI telemetry chart context

`tests/test_ui_routes.py` verifies the UI telemetry refresh path, empty-state behavior, and the
presence of plant-death diagnostics in the model diagnostics rail.

## Per-Species Breakdown in the Export Artifact

`TelemetryRecorder.dataframe` now flattens the per-species nested-dict accumulators
(`plant_pop_by_species`, `plant_energy_by_species`, `swarm_pop_by_species`,
`defense_cost_by_species`) into typed Polars scalar columns following the naming
convention `plant_{id}_pop`, `plant_{id}_energy`, `swarm_{id}_pop`, and
`defense_cost_{id}`.

This means the primary export routes (`GET /api/telemetry/export/csv` and
`GET /api/telemetry/export/json`) automatically include per-species breakdowns in their
output without requiring any additional API parameters or client-side post-processing.

Species identifiers are unioned across all retained rows and sorted numerically before
the columns are written, so the column order is deterministic even when different
simulation sessions involve different species cardinalities. Ticks in which a species was
absent (due to extinction or delayed colonisation) receive a zero value in the
corresponding column, preserving full rectangular structure.

The auxiliary `telemetry_to_dataframe` function in `src/phids/telemetry/export.py`
remains available for callers that require a pandas DataFrame representation (e.g., for
the matplotlib and LaTeX export pipelines). Both functions produce equivalent per-species
breakdown columns from the same source data.

## Methodological Limits of the Current Analytics Layer

The current telemetry layer should be described precisely.

- it captures a compact summary, not every derived ecological statistic,
- it focuses on run comparison and diagnostics rather than full state reconstruction,
- plant-death attribution is immediate-cause oriented rather than a full causal graph,
- its JSON export is NDJSON rather than a custom nested schema.


## Verified Current-State Evidence

- `src/phids/telemetry/analytics.py`
- `src/phids/telemetry/export.py`
- `src/phids/api/main.py`
- `tests/test_telemetry_per_species.py`
- `tests/test_termination_and_loop.py`
- `tests/test_additional_coverage.py`
- `tests/test_ui_routes.py`

## Where to Read Next

- For replay files and tick snapshots: [`replay-and-termination-semantics.md`](replay-and-termination-semantics.md)
- For the high-level telemetry overview: [`index.md`](index.md)
- For engine-side snapshot production: [`../engine/index.md`](../engine/index.md)
