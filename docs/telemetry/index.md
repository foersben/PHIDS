# Telemetry and Replay

PHIDS is designed not only to execute ecological simulations but also to preserve them as inspectable analytical artifacts. The telemetry layer converts each completed tick into three complementary records: a compact summary row for comparative analysis, a serializable environment snapshot for deterministic reinspection, and a termination interpretation that explains why the run continued or stopped. Together, these records transform a simulation from an ephemeral runtime process into a structured experimental trace.

This section introduces telemetry and replay as the analytical memory of PHIDS. It explains why summary metrics and state snapshots are both necessary, how their ordering inside `SimulationLoop.step()` affects interpretation, and why termination metadata belongs to the scientific outcome rather than merely to runtime control. The result is a documentation entry point for readers who need to understand not only what PHIDS computes, but also how those computations are preserved, exported, and compared across runs.

## Telemetry as a Scientific Interface

In PHIDS, telemetry is not an afterthought added for debugging convenience. It is the mechanism
that makes a run comparable, exportable, and reproducible across scenarios.

The telemetry and replay stack provides:

- **per-tick ecological summaries** for analysis,
- **serialized state snapshots** for deterministic reinspection,
- **machine-exportable outputs** for downstream processing,
- **formal stop conditions** that explain why a run ended.

## Current Runtime Position

Within `SimulationLoop.step()`, telemetry is recorded only after the ecological phases
(flow-field, lifecycle, interaction, signaling) have completed for the tick.

The ordering is currently:

1. record telemetry,
2. append replay snapshot,
3. evaluate termination.

This means the telemetry row and replay frame describe the post-update state of the tick, while
termination explains whether that state should halt the run.

## Core Modules

- `src/phids/telemetry/analytics.py`
- `src/phids/telemetry/conditions.py`
- `src/phids/telemetry/export.py`
- `src/phids/io/replay.py`

## Canonical Telemetry Chapters

- [`analytics-and-export-formats.md`](analytics-and-export-formats.md)
- [`replay-and-termination-semantics.md`](replay-and-termination-semantics.md)

## Two Complementary Output Families

PHIDS currently exposes two complementary output families.

### Summary analytics

Telemetry rows are compact tabular descriptions of a completed tick. They are the primary artifact
for cross-run comparison and export.

### Replay frames

Replay snapshots preserve a richer environment-centered state trace suitable for deterministic
reinspection.

The key distinction is:

- analytics describe the run in summary form,
- replay preserves the run in state-sequence form.

## Termination Conditions `Z1`–`Z7`

Termination logic is implemented in `phids.telemetry.conditions.check_termination()` and returns a
`TerminationResult` containing both a boolean outcome and a human-readable reason.

The currently implemented conditions are:

### `Z1` — Maximum duration reached

The simulation halts when `tick >= max_ticks`.

### `Z2` — Target flora species extinct

The simulation halts when a configured flora species ID is no longer present.

### `Z3` — All flora extinct

The simulation halts when no living flora remain.

### `Z4` — Target predator species extinct

The simulation halts when a configured predator species ID is no longer present.

### `Z5` — All predators extinct

The simulation halts when no living predator swarms remain.

### `Z6` — Flora energy overshoot

The simulation halts when aggregate flora energy exceeds a configured upper threshold.

### `Z7` — Predator population overshoot

The simulation halts when aggregate predator population exceeds a configured upper threshold.

## Interpreting Termination Scientifically

The termination reason should be understood as part of the experiment outcome, not merely a
runtime control signal.

For example:

- `Z3` may represent ecological collapse of the flora layer,
- `Z5` may represent complete predator extinction,
- `Z6` and `Z7` may represent runaway regimes in which a configured quantity exceeds acceptable
  analysis bounds,
- `Z1` marks a censored but intentionally time-bounded run.

This makes termination metadata analytically meaningful when comparing scenarios.

## Recommended Interpretation Workflow

For serious scenario analysis, a reader should interpret PHIDS outputs at three levels:

1. **Telemetry rows** for trends and aggregates,
2. **Replay snapshots** for reconstructing spatial state evolution,
3. **Termination reason** for understanding why the experimental run ended.

Each of these captures a different scale of information, and none alone is a complete account of
the simulation.

## Where to Read Next

- For tabular fields and export semantics: [`analytics-and-export-formats.md`](analytics-and-export-formats.md)
- For replay framing and `Z1`–`Z7`: [`replay-and-termination-semantics.md`](replay-and-termination-semantics.md)
- For interface-level download routes: [`../interfaces/rest-and-websocket-surfaces.md`](../interfaces/rest-and-websocket-surfaces.md)
