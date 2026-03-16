# HTMX Partials and Builder Routes

The PHIDS control center is a server-rendered hypermedia interface. It is not a thin shell around a
client-side application. Instead, the browser requests HTML fragments from the backend, and those
fragments are rendered from canonical server-side state.

This chapter documents the current builder surface as implemented by Jinja templates, HTMX swaps,
and draft-mutating route handlers.

## Architectural Principle

The UI is organized around three layers:

1. **Jinja templates** define the canonical HTML structure,
2. **HTMX interactions** request updates and replace DOM regions,
3. **FastAPI route handlers** call `DraftService` to mutate `DraftState` and then re-render the relevant partial.

This means that the control center remains fully server-authored even while behaving like a highly
interactive workbench.

## Primary View Partials

The current UI exposes the following view-level partials:

- `partials/dashboard.html`
- `partials/biotope_config.html`
- `partials/flora_config.html`
- `partials/predator_config.html`
- `partials/substance_config.html`
- `partials/diet_matrix.html`
- `partials/trigger_rules.html`
- `partials/placement_editor.html`
- `partials/placement_list.html`
- diagnostics partials under `partials/diagnostics_*.html`
- `partials/telemetry_chart.html`

These are served by routes such as:

- `/ui/dashboard`
- `/ui/biotope`
- `/ui/flora`
- `/ui/predators`
- `/ui/substances`
- `/ui/diet-matrix`
- `/ui/trigger-rules`
- `/ui/placements`
- `/ui/diagnostics/model`
- `/ui/diagnostics/frontend`
- `/ui/diagnostics/backend`

## Builder Route Pattern

Most builder routes follow a common pattern:

1. retrieve the active `DraftState`,
2. apply a mutation or normalization step through `DraftService`,
3. render a fresh partial from the updated state,
4. return HTML for an HTMX swap.

This pattern appears across biotope configuration, species CRUD, trigger editing, and placement
editing.

## Biotope Configuration Workflow

The route `POST /api/config/biotope` updates global draft parameters such as:

- grid width and height,
- max ticks,
- tick rate,
- wind vector,
- signal and toxin counts,
- mycorrhizal settings.

Its current implementation delegates scalar normalization to `DraftService`, which clamps submitted
values to valid ranges before re-rendering the `partials/biotope_config.html` fragment.

This is a good example of PHIDS’s backend-first validation philosophy: even interactive UI edits
pass through explicit normalization logic.

## Entity Builder Workflows

### Flora and predator editors

The flora and predator sections use CRUD-style routes to add, update, and remove species while
keeping species IDs, matrix dimensions, and dependent references consistent.

### Substance editor

The substance builder manages a registry of named substance definitions. These definitions do not
by themselves encode when synthesis occurs; trigger rules provide that coupling.

The mutation boundary is important here. Substance add, update, and delete routes now delegate to
`DraftService`, which not only edits the registry row but also preserves dependent invariants such
as sequential substance identifiers, precursor remapping, trigger-rule removal for deleted products,
and activation-condition rewrites for surviving rules.

This separation gives the UI a more scientifically meaningful structure:

- a substance describes *what a chemical is*,
- a trigger rule describes *when a plant synthesizes it*.

## Matrix and Trigger Editing

PHIDS currently distinguishes two related but different interaction editors:

### Diet matrix

The diet matrix declares which predator species can consume which flora species. The route layer now
delegates cell toggles to `DraftService`, so out-of-range indices are ignored centrally rather than
mutated ad hoc in the HTTP handler.

### Trigger rules editor

The trigger-rules UI replaces the older notion of a single trigger matrix cell choosing only one
substance. The current builder can express multiple explicit rules per `(flora, predator)` pair and
supports nested activation-condition trees.

This is one of the biggest current-state differences between the project’s legacy design documents
and the implemented UI behavior.

## Placement Editor

The placement subsystem combines:

- an HTML partial for the editor shell,
- a JSON endpoint for canvas rendering data,
- CRUD routes for plant placement,
- CRUD routes for swarm placement,
- a clear-all route,
- a list partial showing the current staged placements.

An important current behavior is that draft mycorrhizal links can be previewed directly from
placements via `/api/config/placements/data`.

## Diagnostics Rail

The diagnostics surface is also rendered server-side. It currently includes separate tabs for:

- model diagnostics,
- frontend diagnostics,
- backend diagnostics.

This makes PHIDS unusual among simulation builders: the same control interface that edits the
scenario also exposes structured introspection of runtime state, telemetry, and recent logs.

## Canvas Rendering Boundary

The interface is server-driven almost everywhere, but PHIDS deliberately carves out one narrow
JavaScript-heavy boundary: canvas rendering for live or previewed spatial state.

That rendering is fed by:

- `/ws/ui/stream` for live lightweight JSON updates,
- `/api/config/placements/data` for draft placement preview data,
- `/api/ui/cell-details` for localized inspection.

This separation keeps high-frequency visual updates lightweight without turning the entire control
center into a client-managed application.

## Current-State Design Consequences

The HTMX/Jinja builder architecture has several important consequences:

- server-side state remains authoritative,
- validation logic is shared between UI and API workflows,
- DOM updates are declarative and localized,
- the builder can preview draft state before any live run exists,
- migration from legacy builder concepts can be performed without abandoning server-driven control.

## Verified Current-State Evidence

This chapter is grounded in:

- `src/phids/api/routers/config.py`
- `src/phids/api/main.py`
- `src/phids/api/ui_state.py`
- `src/phids/api/templates/partials/`
- `tests/test_ui_routes.py`
- `tests/test_api_builder_and_helpers.py`

## Legacy Provenance

Historical design intent for this surface is preserved in:

- `legacy/2026-03-11/PHIDS_htmx_ui_design_specification.md`

That archived document remains valuable, but the canonical documentation should follow the current
route structure and template behavior when implementation and legacy design diverge.
