# PHIDS

PHIDS (Plant-Herbivore Interaction & Defense Simulator) is a deterministic computational
ecology system for studying plant–herbivore competition, chemical defense, and spatially
localized interaction on a discrete grid. The project couples a data-oriented ECS engine with
vectorized environmental layers, a scientific telemetry pipeline, and two operator surfaces:
a programmatic JSON/WebSocket API and a server-rendered HTMX/Jinja control center.

Current release line: `v0.4.0`.

## Live Documentation

- **Published GitHub Pages site**: <https://foersben.github.io/PHIDS/>
- **Deployment workflow**:
  <https://github.com/foersben/PHIDS/actions/workflows/docs-pages.yml>
- **Source repository**: <https://github.com/foersben/PHIDS>

## Scientific Framing

PHIDS should be read as a research-grade simulation instrument with explicit architectural
commitments:

- **Deterministic tick ordering** through `SimulationLoop.step()`.
- **Data-oriented state storage** in `ECSWorld` and NumPy layer buffers.
- **Global flow-field navigation** instead of per-agent pathfinding.
- **Double-buffered environmental updates** for diffusion-style layers.
- **Rule-of-16 bounded configuration spaces** for species and substances.
- **O(1) spatial locality queries** through the spatial hash.

These are not incidental implementation details; they define the simulator's methodological
scope and the kinds of ecological questions PHIDS can answer reproducibly.

## Current Runtime Anchors

- `phids.engine.loop.SimulationLoop` — orchestrates the ordered simulation phases.
- `phids.engine.core.biotope.GridEnvironment` — owns vectorized environmental layers.
- `phids.engine.core.ecs.ECSWorld` — stores entities and spatial-locality data.
- `phids.api.ui_state.DraftState` — holds editable UI state before live loading.
- `phids.telemetry.analytics.TelemetryRecorder` — records tick-level output metrics.

## Documentation Map

- **Foundations** — research scope, terminology, and modeling commitments:
  [`foundations/`](scientific_model/mathematical_framework.md)
- **Architecture** — package boundaries, loop ownership, and runtime decomposition:
  [`architecture/`](technical_architecture/system_architecture.md)
- **Engine** — subsystem behavior and performance-sensitive invariants:
  [`engine/`](technical_architecture/engine_execution.md)
- **Interfaces** — REST, WebSocket, and control-center surfaces:
  [`interfaces/`](technical_architecture/interfaces_and_ui.md) and [`ui/`](technical_architecture/interfaces_and_ui.md)
- **Live Observation and Diagnostics** — cell inspection, canvas streaming, diagnostics rail:
  [`technical_architecture/interfaces_and_ui.md`](technical_architecture/interfaces_and_ui.md)
- **Scenarios** — schema semantics, import/export, and curated examples:
  [`scenarios/`](scenario_guide/scenario_authoring.md)
- **Telemetry** — analytics, replay framing, and termination interpretation:
  [`telemetry/`](technical_architecture/telemetry.md)
- **Development handoff and CI guidance** — deferred documentation work and workflow validation:
  [`development_guide/agent_ecosystem.md`](development_guide/agent_ecosystem.md)
  and [`development_guide/contribution_workflow.md`](development_guide/contribution_workflow.md)
- **Release governance** — version bump, promotion, tag publication, and artifact checks:
  [`development_guide/contribution_workflow.md`](development_guide/contribution_workflow.md)
- **Reference** — module map, glossary and concept index, and generated Python API docs:
  [`reference/`](reference/index.md)
- **Glossary** — current-state definitions for all major PHIDS terms:
  [`reference/glossary-and-concept-index.md`](reference/glossary-and-concept-index.md)
- **Legacy Archive** — preserved historical source documents:
  [`legacy/`](legacy/index.md)

## How to Read This Site

The canonical current-state documentation lives in the structured MkDocs sections above. Narrative
chapters describe the behavior of the active `phids.*` runtime under `src/phids/`, while the
`legacy/` section preserves earlier standalone design documents for provenance and comparison.

If you are new to the project, a practical reading order is:

1. start with [`scientific_model/mathematical_framework.md`](scientific_model/mathematical_framework.md),
2. continue to [`technical_architecture/system_architecture.md`](technical_architecture/system_architecture.md),
3. inspect the relevant subsystem chapter under [`engine/`](technical_architecture/engine_execution.md),
4. then use [`interfaces/`](technical_architecture/interfaces_and_ui.md), [`scenarios/`](scenario_guide/scenario_authoring.md), or
   [`telemetry/`](technical_architecture/telemetry.md) depending on the surface you are working on,
5. use [`development_guide/agent_ecosystem.md`](development_guide/agent_ecosystem.md)
   if you are resuming the documentation migration or polish pass.

## Current Documentation Anchors

This documentation set is organized around the current implementation and test surfaces, especially:

- `src/phids/api/main.py`
- `src/phids/api/routers/`
- `src/phids/api/ui_state.py`
- `src/phids/engine/loop.py`
- `src/phids/engine/core/`
- `tests/`
- `README.md`

## Build the Documentation Locally

```bash
uv sync --all-extras --dev
uv run mkdocs serve
```
