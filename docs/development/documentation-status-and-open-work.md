# Documentation Status and Open Work

This page is the canonical handoff note for the current documentation phase. Its purpose is to make
it obvious where the documentation corpus stopped, what is already considered stable, and which
high-value chapters remain intentionally deferred.

## Current Stopping State

The MkDocs corpus is currently strong enough to treat as the canonical project documentation for the
active `phids.*` runtime under `src/phids/`.

The site already covers:

- scientific framing and modeling scope,
- architecture and runtime ownership,
- engine subsystem behavior,
- REST, WebSocket, and HTMX/Jinja surfaces,
- scenario schema and curated examples,
- telemetry, replay, and termination semantics,
- contributor workflow, testing policy, and documentation standards,
- module/reference navigation plus the generated Python API reference,
- preserved legacy documents for provenance.

In short, PHIDS is documented well enough to navigate, operate, and extend without relying on the
legacy standalone documents as the primary source.

## What “Finalized for Now” Means

The current phase should be considered **complete enough to pause safely**, not complete in an
absolute sense.

That means:

- the docs are usable as the canonical current-state corpus,
- the major architectural and operator surfaces are covered,
- `mkdocs build --strict` is expected to remain green,
- the remaining work is mainly high-value polish and usability improvement rather than major
  foundational migration.

## Explicit Open TODOs

These are the deferred items that should be picked up first when the next documentation pass starts.
They are ordered by value.

### 1. Add a canonical UI diagnostics and live-observation chapter

**Why this is still open**

The UI and interfaces chapters already mention diagnostics, telemetry polling, and the live canvas
stream, but there is not yet one canonical chapter that explains the full observation workflow in one
place.

**Recommended target file**

- `docs/ui/diagnostics-and-live-observation.md`

**Implementation anchors to read first**

- `src/phids/api/main.py`
  - `_build_live_dashboard_payload`
  - `_build_live_summary`
  - `_build_starving_swarms`
  - `GET /api/ui/cell-details`
  - `GET /api/telemetry`
  - `WS /ws/ui/stream`
  - `GET /ui/diagnostics/model`
  - `GET /ui/diagnostics/frontend`
  - `GET /ui/diagnostics/backend`
- `src/phids/api/templates/partials/diagnostics_model.html`
- `src/phids/api/templates/partials/diagnostics_frontend.html`
- `src/phids/api/templates/partials/diagnostics_backend.html`
- `tests/test_ui_routes.py`

**What the page should explain**

- dashboard observation modes,
- draft versus live cell inspection,
- the role of `/ws/ui/stream`,
- telemetry chart polling and summary context,
- frontend/backend/model diagnostics tabs,
- stale-tooltip protection via `expected_tick`,
- why these surfaces matter for scientific interpretability.

### 2. Add a canonical glossary and concept index

**Why this is still open**

The current docs are content-rich, but whole-site navigation still depends too much on knowing the
project vocabulary in advance.

**Recommended target file**

- `docs/reference/glossary-and-concept-index.md`

**Terms that should be included first**

- `SimulationLoop`
- `ECSWorld`
- `GridEnvironment`
- flow field
- draft state
- live simulation
- control center
- mycorrhiza / mycorrhizal links
- trigger rule
- signal versus toxin
- telemetry row
- replay snapshot
- termination condition
- Rule of 16
- spatial hash
- double buffering

**What the page should do**

- define terms in current-state language,
- link each term to its owning narrative chapter,
- improve discoverability for new contributors and operators.

### 3. Polish navigation and cross-links after the two pages above exist

**Why this is still open**

Navigation is already workable, but the final usability gains depend on adding the diagnostics chapter
and glossary first.

**Follow-up tasks once those pages exist**

- add both pages to `mkdocs.yml`,
- link them from `docs/index.md`,
- link the diagnostics chapter from `docs/ui/index.md` and `docs/interfaces/rest-and-websocket-surfaces.md`,
- link the glossary from `docs/reference/index.md` and selected subsystem pages.

### 4. Optional polish after the high-value pages land

These are useful, but lower priority than the three items above:

- a release and maintenance checklist,
- richer diagrams for the loop and UI observation surfaces,
- more reference cross-links into generated API docs,
- selective docstring polish where mkdocstrings output remains thin.

## Recommended Re-entry Order

When resuming documentation work later, the safest sequence is:

1. read the diagnostics/live-observation implementation anchors,
2. write `docs/ui/diagnostics-and-live-observation.md`,
3. write `docs/reference/glossary-and-concept-index.md`,
4. update navigation and cross-links,
5. run focused route tests and a strict docs build.

## Validation Checklist for the Next Pass

Use these commands when picking the work back up:

```bash
uv sync --all-extras --dev
uv run pytest -o addopts='' tests/test_ui_routes.py -q
uv run mkdocs build --strict
```

If the diagnostics chapter ends up describing route semantics in more detail than the current UI
chapter, also re-check:

```bash
uv run pytest -o addopts='' tests/test_api_routes.py tests/test_ui_routes.py -q
```

## Closest Current-State Evidence

This handoff page is grounded in the current canonical docs plus the current implementation/test
anchors that define the missing work.

- `mkdocs.yml`
- `docs/index.md`
- `docs/ui/index.md`
- `docs/reference/index.md`
- `docs/development/index.md`
- `src/phids/api/main.py`
- `src/phids/api/templates/partials/diagnostics_model.html`
- `src/phids/api/templates/partials/diagnostics_frontend.html`
- `src/phids/api/templates/partials/diagnostics_backend.html`
- `tests/test_ui_routes.py`

## Where to Read Next

- For contributor workflow around quality gates: [`contribution-workflow-and-quality-gates.md`](contribution-workflow-and-quality-gates.md)
- For CI and local rehearsal details: [`github-actions-and-local-ci.md`](./github-actions-and-local-ci.md)
- For the current UI architecture entry point: [`../ui/index.md`](../ui/index.md)
