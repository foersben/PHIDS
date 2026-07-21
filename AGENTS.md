# PHIDS Routing & Capabilities

Primary routing table for AI IDEs defining roles in `.agents/roles/` and core constraints.

## Core Architecture Constraints

- **ECS (Entity-Component-System):** Engine is data-oriented. Entities are ints. Components are raw NumPy arrays. Systems hold logic. OOP (classes with behavior/state) inside engine core is banned.
- **Loop Phases:** SimulationLoop execution: flow field → lifecycle → interaction → signaling → telemetry/termination.
- **Double Buffering:** ECS systems and `GridEnvironment` read from current layer; write ONLY to `_write` layer.
- **Performance:** JIT-compile hot-path math (`flow_field.py`, interactions) with Numba `@njit`. Ban Python collections (`dict`, `list`) in JIT loops.
- **Stochastic Replay:** Serialize all evaluation outcomes tick-by-tick into Zarr replay buffers. Playback reads Zarr directly, bypassing engine logic.
- **State:** HTMX UI mutates server-side `DraftState` via `DraftService`. `POST /api/scenario/load-draft` commits to live loop.

## AI Role Registry

| Role | Description | Trigger |
|---|---|---|
| `@orchestrator` | PM. Delegates tasks; enforces OKF structure. | Planning, refactoring, workflows. |
| `@scientific-architect` | Translates reaction-diffusion PDEs/chemotaxis. | Mathematical/biological models. |
| `@engine-developer` | ECS & Numba developer. Handles double-buffering. | Core performance, ECS arrays, loops. |
| `@qa-automator` | Testing. Isolates failures; runs benchmarks. | Coverage, tests, mutation/hypothesis. |
| `@docs-librarian` | Maintains docs, Zensical, mkdocstrings. | Documentation, diagrams, LaTeX. |
| `@git-operator` | Manages branches, commits, releases. | Git actions, commits, release tags. |
| `@api-and-ui-developer` | HTMX, Jinja2, and FastAPI developer. | Dashboard UI, endpoints, websockets. |
| `@telemetry-and-data-engineer`| Polars & Zarr schemas. | Teleplay buffers, exports, metrics. |

## Documentation Formatting Rules

- **Dashes:** Always use the standard hyphen (`-`) instead of the en-dash or em-dash in all Markdown documentation and UI text.

## OKF (Open Knowledge Format) Metadata Rule

- **Mandatory Parsing:** All AI agents (Jules, Antigravity, etc.) MUST actively parse the YAML frontmatter (OKF headers) in `docs/` and `.agents/` files before answering architectural or design questions.
- **Utilization:** Use OKF `tags`, `timestamps`, and `resources` fields to gauge the relevance and contextual scope of the document. If an OKF `status` is `deprecated`, actively warn the user.
- **Enrichment:** When creating or modifying documentation, always populate or update the OKF frontmatter exhaustively (including `type`, `title`, `status`, `version`, `description`, `tags`, `timestamp`, `resources`).
