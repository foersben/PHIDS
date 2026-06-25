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
- engine subsystem behavior (including the current surplus-based reproduction model, crowding
  dispersal, stale-entity guard, `environmental_signal` activation condition, and ghost-swarm GC),
- REST, WebSocket, and HTMX/Jinja surfaces,
- scenario schema and curated examples,
- telemetry, replay, and termination semantics,
- contributor workflow, testing policy, and documentation standards,
- module/reference navigation plus the generated Python API reference,
- a comprehensive glossary and concept index,
- a diagnostics and live-observation chapter covering all observation modes,
- preserved legacy documents for provenance.
- scientific Google-style docstrings applied to all public Python symbols across the runtime.

## Completed Since Previous Pass

The following items were identified as open work in the previous documentation status and have now
been addressed:

### Scientific docstrings across the runtime

All public Python symbols in `src/phids/` now carry Google-style scholarly docstrings covering both
the algorithmic mechanics and the biological rationale for each component. The completion was
validated by running `uv run pre-commit run --all-files` and the full test suite.

### Interaction system documentation updated for bug fixes

`docs/engine/interaction.md` was updated to reflect three correctness fixes applied to
`src/phids/engine/systems/interaction.py`:

1. **Surplus-based reproduction model** — the stale description of `new_individuals = int(energy //
   energy_min)` was replaced with the current four-step baseline/surplus/cost formula.
2. **Population-based crowding dispersal** — a new "Crowding-induced dispersal" subsection
   documents `TILE_CARRYING_CAPACITY = 500` and the `_co_located_swarm_population` helper that
   aggregates biological individuals rather than entity count.
3. **Stale-entity guard in feeding loop** — a new "Stale-entity guard" subsection documents the
   `world.has_entity(co_eid)` validity check that prevents `KeyError` on mid-iteration plant GC.

### Signaling documentation corrected for `environmental_signal` and ghost-swarm GC

`docs/engine/signaling.md` received two substantive corrections:

1. The incorrect note claiming that "no activation predicate reads `signal_layers[x, y]` directly"
   was removed and replaced with accurate documentation of the `environmental_signal` condition
   node, which does exactly this.
2. The "Direct Toxin Effects" section was expanded to document the immediate garbage collection of
   toxin-killed swarms introduced in `_apply_toxin_to_swarms`, explaining how ghost-entity
   accumulation in the spatial hash is prevented within the same tick.

### Diagnostics and live-observation chapter

`docs/ui/diagnostics-and-live-observation.md` was created, covering:

- canvas streaming via `/ws/ui/stream` (message fields, transmission policy, disconnection),
- binary simulation stream via `/ws/simulation/stream`,
- cell-detail inspection via `GET /api/ui/cell-details` (live vs draft, stale-tooltip protection),
- diagnostics rail model/backend/frontend tabs with their endpoint semantics,
- telemetry polling endpoints,
- the draft-vs-live observation boundary invariant,
- scientific interpretability notes for each observation surface.

### Glossary and concept index

`docs/reference/glossary-and-concept-index.md` was created with current-state definitions for all
major PHIDS vocabulary terms, each cross-linked to the owning narrative chapter.

## What "Finalized for Now" Means

The current phase should be considered **complete enough to pause safely**, not complete in an
absolute sense.

That means:

- the docs are usable as the canonical current-state corpus,
- the major architectural and operator surfaces are covered,
- `mkdocs build --strict` is expected to remain green,
- the remaining work is optional polish and extension rather than foundational gaps.

## Remaining Optional Enhancements

These items are useful but do not represent foundational gaps in the current documentation state.
They are ordered by approximate value.

### 1. Polish navigation and cross-links

Now that the glossary and diagnostics chapter exist, the following cross-link improvements are
recommended when resuming the next pass:

- add the glossary link from `docs/reference/index.md` and selected subsystem pages,
- link the diagnostics chapter from `docs/ui/index.md` and from
  `docs/interfaces/rest-and-websocket-surfaces.md`,
- verify that all `mkdocs.yml` nav entries are reachable after adding the two new pages.

### 2. Richer engine diagrams

The mermaid flowchart in `docs/engine/index.md` covers the top-level tick ordering well, but
subsystem-level diagrams for signaling substance lifecycle phases (materialized → synthesizing →
active → aftereffect → inactive) and for the mitosis decision tree would improve navigability.

### 3. Release and maintenance checklist

A one-page `docs/development/release-checklist.md` capturing the git tagging, GHCR publish, and
PyInstaller artifact release workflow would complement the existing CI and contribution chapters.

### 4. More reference cross-links into generated API docs

Some narrative chapter sections reference symbols that are not yet cross-linked to their generated
docstring entries in `reference/api.md`. Adding inline `::: phids.module.Symbol` cross-links in
selected prose sections would improve the reference surface.

## Validation Checklist for the Next Pass

Use these commands when picking the work back up:

```bash
uv sync --all-extras --dev
uv run pytest -q
uv run mkdocs build --strict
```

For focused route regression:

```bash
uv run pytest -o addopts='' tests/test_ui_routes.py tests/test_api_routes.py -q
```

## Where to Read Next

- For contributor workflow around quality gates:
  [`contribution-workflow-and-quality-gates.md`](contribution-workflow-and-quality-gates.md)
- For CI and local rehearsal details:
  [`github-actions-and-local-ci.md`](./github-actions-and-local-ci.md)
- For the current UI architecture entry point:
  [`../ui/index.md`](../ui/index.md)
- For the new diagnostics chapter:
  [`../ui/diagnostics-and-live-observation.md`](../ui/diagnostics-and-live-observation.md)
- For the new glossary:
  [`../reference/glossary-and-concept-index.md`](../reference/glossary-and-concept-index.md)
