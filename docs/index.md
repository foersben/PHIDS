# PHIDS

PHIDS (Plant-Herbivore Interaction & Defense Simulator) is a deterministic computational ecology system for studying plant–herbivore competition, chemical defense, and spatially localized interaction on a discrete grid. The project couples a data-oriented ECS engine with vectorized environmental layers, a scientific telemetry pipeline, and two operator surfaces: a programmatic JSON/WebSocket API and a server-rendered HTMX/Jinja control center.

Current release line: `v0.4.0`.

## Live Documentation

- **Published GitHub Pages site**: <https://foersben.github.io/PHIDS/>
- **Deployment workflow**: <https://github.com/foersben/PHIDS/actions/workflows/docs-pages.yml>
- **Source repository**: <https://github.com/foersben/PHIDS>

## Core Simulation Principles

PHIDS is engineered as a research-grade simulation instrument. To ensure that ecological outputs are mathematically traceable and experimentally reproducible, the system adheres to strict architectural constraints:

- **Deterministic tick ordering** through `SimulationLoop.step()`.
- **Data-oriented state storage** in `ECSWorld` and NumPy layer buffers.
- **Global flow-field navigation** (chemotaxis) instead of per-agent pathfinding.
- **Double-buffered environmental updates** for diffusion-style layers.
- **Rule-of-16 bounded configuration spaces** for species and substances.
- **O(1) spatial locality queries** through the spatial hash.

These are not incidental implementation details; they define the simulator's methodological scope and the kinds of ecological questions PHIDS can answer accurately.

### Legacy Simulation Invariants

During the migration from legacy Object-Oriented implementations to the current data-oriented framework, several core operational invariants were formalized to ensure computational efficiency and mathematical rigor.

1.  **$O(1)$ Spatial Lookups:**
    *Legacy limitation:* Calculating Euclidean distance between every swarm and every plant created catastrophic $O(N^2)$ CPU bottlenecks.
    *Current invariant:* All locational biology (feeding, reproduction boundaries, toxin triggering) is resolved through an `ECSWorld` Spatial Hash mapping $(x, y)$ coordinates directly to Entity IDs.
2.  **No Dynamic Array Allocation (The Rule of 16):**
    *Legacy limitation:* Growing interaction matrices dynamically caused severe memory latency.
    *Current invariant:* The ecosystem is strictly bounded. At initialization, 16 flora, 16 herbivores, and 16 substance profiles are allocated.
3.  **Subnormal Float Clamping:**
    *Legacy limitation:* Diffusing signal clouds created infinitely long decimal tails (e.g., `1e-300`), which crash processor FPUs.
    *Current invariant:* Any continuous signal concentration dropping below $\varepsilon$ (`1e-4`) is explicitly truncated to `0.0`.
4.  **No Homogeneous Continuous Fractions:**
    *Legacy limitation:* Simple ODE solvers allow for 0.43 of a swarm to exist, failing to map to spatial grids.
    *Current invariant:* Swarms suffer fractional deficit attrition, but split boundaries and final spatial placement are resolved through discrete, physical Entity components.

## Current Runtime Anchors

- `phids.engine.loop.SimulationLoop` — orchestrates the ordered simulation phases.
- `phids.engine.core.biotope.GridEnvironment` — owns vectorized environmental layers.
- `phids.engine.core.ecs.ECSWorld` — stores entities and spatial-locality data.
- `phids.api.ui_state.DraftState` — holds editable UI state before live loading.
- `phids.telemetry.analytics.TelemetryRecorder` — records tick-level output metrics.

## Documentation Map

- **Scientific Model** — research scope, detailed breakdown of mathematical models (Chemotaxis, PDEs), biological reasoning, and equations:
  [`scientific_model/`](scientific_model/index.md)
- **Technical Architecture** — system constraints, package boundaries, loop ownership, interfaces, and telemetry:
  [`technical_architecture/`](technical_architecture/system_architecture.md)
- **Scenarios** — schema semantics, import/export, and curated examples:
  [`scenario_guide/`](scenario_guide/scenario_authoring.md)
- **Development & Reference** — API Reference, contribution workflows, agent orchestration (MCP), and historical archives:
  [`development_guide/`](development_guide/contribution_workflow.md)

## How to Read This Site

The canonical current-state documentation lives in the structured MkDocs sections above. If you are new to the project, a practical reading order is:

1. start with [`scientific_model/mathematical_framework.md`](scientific_model/mathematical_framework.md),
2. continue to the deep dives within the scientific model like [`scientific_model/chemotaxis.md`](scientific_model/chemotaxis.md),
3. inspect the architecture overview under [`technical_architecture/system_architecture.md`](technical_architecture/system_architecture.md),
4. then use [`technical_architecture/interfaces_and_ui.md`](technical_architecture/interfaces_and_ui.md) or [`scenario_guide/scenario_authoring.md`](scenario_guide/scenario_authoring.md) depending on the surface you are working on.

## Build the Documentation Locally

```bash
uv sync --all-extras --dev
uv run mkdocs serve
```
