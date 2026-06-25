# PHIDS Documentation Information Architecture

This document defines the canonical scientific documentation structure for PHIDS in its
current state. It serves both as a migration plan from the legacy markdown corpus and as
an editorial blueprint for future documentation work.

## 1. Documentation Objectives

PHIDS documentation is now organized around three primary goals:

1. **Scientific exposition first** — describe the simulator as a deterministic ecological
   model with explicit assumptions, state transitions, and invariants.
2. **Codebase traceability** — connect every major concept to concrete implementation
   artifacts under `src/phids/`.
3. **Archival continuity** — preserve the historical design documents that motivated the
   current architecture.

## 2. Intended Audiences

### 2.1 Research and modeling audience

This audience needs:

- the simulator's ecological abstraction,
- mathematical and algorithmic assumptions,
- state variables and invariants,
- reproducibility and determinism guarantees,
- interpretation of outputs and scenario semantics.

### 2.2 System and engine contributors

This audience needs:

- module responsibilities,
- lifecycle ordering,
- data-oriented constraints,
- performance invariants,
- API/UI state ownership.

### 2.3 Operators and evaluators

This audience needs:

- how to inspect, run, configure, and export a simulation,
- how the UI draft state differs from live runtime state,
- what each route and stream provides,
- where curated scenarios fit into analysis workflows.

## 3. Canonical Top-Level Structure

The documentation site should present the following top-level sections in this order:

1. **Home** — scientific overview and navigation entry point.
2. **Documentation Architecture** — this page; defines structure and migration logic.
3. **Foundations** — conceptual model, terminology, assumptions, ecological scope.
4. **Architecture** — system decomposition and runtime data flow.
5. **Engine** — simulation execution internals and subsystem behavior.
6. **Interfaces** — REST, WebSocket, UI draft/live semantics.
7. **Scenarios** — configuration model, curated examples, import/export semantics.
8. **Telemetry** — metrics, replay, export, termination interpretation.
9. **Development** — quality gates, style, docs process, contribution constraints.
10. **Reference** — API reference, README mirror, and symbol index.
11. **Legacy Archive** — immutable pre-restructure source documents.

## 4. Detailed Page Outline

### 4.1 Home

**Purpose:** Provide a concise research-style description of PHIDS as a deterministic
computational ecology instrument.

**Must include:**

- simulator scope,
- key architectural claims,
- core invariants,
- where to start for theory / architecture / API / UI / reference,
- current implementation anchors such as `SimulationLoop`, `GridEnvironment`, `ECSWorld`,
  and `DraftState`.

### 4.2 Foundations

#### `foundations/index.md`

**Purpose:** Establish the scientific framing and glossary.

**Subtopics to include over time:**

- plant–herbivore competition framing,
- deterministic time-stepped interpretation,
- discrete grid assumptions,
- ecological simplifications and non-goals,
- glossary of domain and implementation terms.

#### `foundations/research-scope.md`

**Purpose:** Define model scope and normative invariants.

**Detailed outline:**

1. Biological abstractions represented in PHIDS.
2. Variables represented explicitly vs omitted.
3. Determinism and replayability.
4. Data-oriented constraints as methodological commitments.
5. Current known approximations and implementation caveats.

### 4.3 Architecture

#### `architecture/index.md`

**Purpose:** Explain the macro-architecture of the simulator.

**Detailed outline:**

1. Runtime package boundaries.
2. SimulationLoop as the orchestration center.
3. Environment, ECS, and systems split.
4. Dual interface surface: API and server-rendered UI.
5. Traceability to telemetry and replay.
6. Mermaid diagrams to be migrated from legacy architecture docs.

**Legacy sources:**

- `legacy/2026-03-11/architecture.md`
- `legacy/2026-03-11/comprehensive_description.md`

### 4.4 Engine

#### `engine/index.md`

**Purpose:** Provide a formal overview of the runtime execution model.

**Detailed outline:**

1. Tick ordering in `SimulationLoop.step`.
2. Flow field phase.
3. Lifecycle phase.
4. Interaction phase.
5. Signaling phase.
6. Telemetry and termination phase.
7. Deterministic ordering and side-effect boundaries.

**Future child pages recommended:**

- `engine/ecs-and-spatial-hash.md`
- `engine/biotope-and-double-buffering.md`
- `engine/flow-field.md`
- `engine/lifecycle.md`
- `engine/interaction.md`
- `engine/signaling.md`

Each should document:

- owned state,
- read/write invariants,
- asymptotic expectations,
- relevant tests,
- performance constraints,
- failure modes and edge cases.

### 4.5 Interfaces

#### `interfaces/index.md`

**Purpose:** Describe PHIDS as an executable interface surface.

**Detailed outline:**

1. FastAPI application role.
2. Schema validation boundary.
3. Simulation lifecycle endpoints.
4. Binary simulation stream.
5. Lightweight UI stream.
6. Error handling and state transitions.

#### `ui/index.md`

**Purpose:** Explain the server-driven HTMX/Jinja control center.

**Detailed outline:**

1. `DraftState` as the UI source of truth.
2. Difference between draft configuration and live `SimulationLoop`.
3. Partial-template rendering model.
4. Scenario import/export and load-draft workflow.
5. Why the UI is intentionally not a SPA.

**Legacy sources:**

- `legacy/2026-03-11/PHIDS_htmx_ui_design_specification.md`

### 4.6 Scenarios

#### `scenarios/index.md`

**Purpose:** Document the scenario language and curated example pack.

**Detailed outline:**

1. `SimulationConfig` as canonical scenario schema.
2. Rule-of-16 matrix bounds.
3. Trigger rule semantics.
4. Import/export/replay relationship.
5. Curated example scenarios and what each demonstrates.
6. Scenario design conventions, including the plants-plus-swarms competition rule.

### 4.7 Telemetry

#### `telemetry/index.md`

**Purpose:** Explain how simulation outputs are recorded, exported, and interpreted.

**Detailed outline:**

1. Tick-level telemetry collection.
2. Replay frames and deterministic reinspection.
3. CSV/JSON export pathways.
4. Termination conditions and scientific interpretation.
5. Suggested future figures and example plots.

### 4.8 Development

#### `development/index.md`

**Purpose:** Document engineering governance for future contributors.

**Detailed outline:**

1. Toolchain and quality gates.
2. Documentation contribution workflow.
3. Google-style docstrings and mkdocstrings integration.
4. Testing strategy, including benchmark-sensitive modules.
5. Architectural non-negotiables from `AGENTS.md` and Copilot instructions.

### 4.9 Reference

#### `reference/index.md`

**Purpose:** Tell readers how to use the API reference and where human-oriented prose ends.

#### `reference/api.md`

**Purpose:** Expose mkdocstrings-backed Python reference material.

#### `appendices/readme.md`

**Purpose:** Mirror the root `README.md` within the docs site for continuity between GitHub
and MkDocs audiences.

## 5. Migration Matrix from Legacy Documents

| Legacy source | Canonical destination | Migration strategy |
| --- | --- | --- |
| `index.md` | `index.md` | Replace with scientific landing page; preserve original in archive. |
| `architecture.md` | `architecture/index.md` | Expand diagrams into explanatory prose and updated diagrams. |
| `comprehensive_description.md` | `foundations/` + `engine/` + `telemetry/` | Split into conceptually coherent scientific chapters. |
| `technical_requirements.md` | `development/` + future normative constraints page | Preserve as normative source; later convert into a specification chapter. |
| `requirements_coverage.md` | future traceability appendix | Maintain a live code-to-requirements mapping. |
| `PHIDS_htmx_ui_design_specification.md` | `ui/index.md` | Convert from prescriptive design memo into current-state UI architecture. |
| `reference.md` | `reference/api.md` | Preserve as generated-reference entry point. |
| `docstring_guidelines.md` | `development/index.md` + future docs standards page | Keep as style source for contributor guidance. |

## 6. Editorial Standards

All new canonical pages should follow these conventions:

- Tone: formal, precise, and research-oriented.
- Provenance: cite the legacy source document when material is migrated.
- Traceability: name the concrete source modules and symbols being described.
- Separation of concerns: distinguish current implementation from aspirations.
- Figures and diagrams: prefer Mermaid for architecture and state sequencing.
- Mathematical notation: use it where clarifying, not decoratively.
- Testing links: important claims about behavior should cite tests or verified runtime modules.

## 7. Immediate Implementation Status

The current overhaul establishes:

- a scientific landing page,
- section landing pages for the future documentation tree,
- a README mirror inside the docs site,
- an archive of the previous documentation corpus,
- an updated MkDocs navigation structure.

Subsequent work should expand each section into full subsystem documentation without losing
traceability to the preserved legacy material.
