---
type: Reference
title: PHIDS Routing & Capabilities
status: stable
stale_after: "2027-01-01"
version: 1.0
description: Primary routing table for AI IDEs defining roles and core
  constraints.
tags: [agents, guidelines]
generated: {by: process:okf-updater, at: "2026-07-25T17:06:00Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
---

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
| --- | --- | --- |
| `@orchestrator` | PM. Delegates tasks; enforces OKF structure. | Planning, refactoring, workflows. |
| `@scientific-architect` | Translates reaction-diffusion PDEs/chemotaxis. | Mathematical/biological models. |
| `@engine-developer` | ECS & Numba developer. Handles double-buffering. | Core performance, ECS arrays, loops. |
| `@qa-automator` | Testing. Isolates failures; runs benchmarks. | Coverage, tests, mutation/hypothesis. |
| `@docs-librarian` | Maintains docs, Zensical. | Documentation, diagrams, LaTeX. |
| `@git-operator` | Manages branches, commits, releases. | Git actions, commits, release tags. |
| `@api-and-ui-developer` | HTMX, Jinja2, and FastAPI developer. | Dashboard UI, endpoints, websockets. |
| `@telemetry-and-data-engineer` | Polars & Zarr schemas. | Teleplay buffers, exports, metrics. |
| `@matrix-auditor` | Audits Data-Flow Matrix coverage & trace parity. | Matrix audits, doc trace validation. |
| `@causal-verifier` | Verifies branchless SIMD masks & causal invariants. | State leaks, unmasked JIT loops. |

## Documentation Formatting Rules

- **Dashes:** Always use the standard hyphen (`-`) instead of the en-dash or em-dash in all Markdown documentation and UI text.

## OKF (Open Knowledge Format) Metadata Rule

- **Mandatory Parsing:** All AI agents (Jules, Antigravity, etc.) MUST actively parse the YAML frontmatter (OKF headers) in `docs/` and `.agents/` files before answering architectural or design questions.
- **Utilization:** Use OKF `tags`, `generated.at`, and `resources` fields to gauge the relevance and contextual scope of the document. If an OKF `status` is `deprecated`, actively warn the user.
- **Enrichment:** When creating or modifying documentation, always populate or update the OKF frontmatter exhaustively (including `type`, `title`, `status`, `version`, `description`, `tags`, `generated`, `resources`).

## MCP Server Usage

- **Introspection Tools:** All agents MUST prefer using the native `PHIDS-Orchestrator` MCP tools (e.g. `runtime_snapshot`, `query_batch_jobs`, `query_diagnostic_logs`, `inspect_telemetry_schema`) and resources (e.g. `phids://config/draft.json`) instead of manually parsing or grepping the codebase and data files when evaluating the simulation state, telemetry metrics, or drift anomalies.

## Continuous Agentic Change & Data-Flow Matrix Synchronization Protocol

- **Mandatory Synchronization Gate:** Whenever ANY AI agent modifies simulation equations, schemas, or engine systems in `src/phids/engine/systems/` or `src/phids/api/schemas/`, the agent MUST:
  1. Run `uv run python scripts/audit_matrix_coverage.py` to assert that all behavioral cascades remain fully covered by documented Data-Flow Matrices.
  2. Run `uv run python scripts/verify_matrix_trace_parity.py --all` (and `uv run pytest tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`) to verify 1:1 table-to-trace parity.
  3. If simulation parameters, thresholds, or kinetics drift intentionally, update the documented Markdown table rows under `## Data-Flow Matrix Specifications` in the corresponding `docs/scientific_model/` files and update `tests/integration/scientific_invariants/test_causal_data_flow_matrices.py`.
- **Pre-Commit Enforcement:** Never bypass git hooks or commit code if `audit_matrix_coverage.py` or `validate_okf.py` report coverage or link structure violations.
