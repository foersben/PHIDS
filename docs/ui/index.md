# UI Control Center

The PHIDS UI is a server-rendered control center rather than a client-side single-page
application. This is a deliberate architectural choice.

## Core Principle

The browser is not the primary state owner. Instead:

- `DraftState` stores editable scenario state on the server,
- Jinja templates render canonical HTML fragments,
- HTMX transmits incremental mutations,
- a small isolated JavaScript surface is reserved for high-frequency rendering tasks such as
  canvas visualization.

In other words, the UI is best understood as a **server-authored scientific workbench** rather
than as a browser-owned application model.

## Why This Matters

This architecture keeps:

- validation on the backend,
- Rule-of-16 enforcement centralized,
- scenario import/export deterministic,
- UI logic aligned with the same trusted schemas used by the API.

It also allows draft configuration to remain a meaningful preview object before any live run has
been instantiated.

## Current-State UI Model

The current PHIDS control center combines several distinct interaction modes:

- HTMX partial swaps for structural navigation,
- form-driven draft mutation routes,
- JSON endpoints for preview and tooltip data,
- WebSocket-driven canvas rendering for live updates,
- diagnostics tabs for frontend, backend, and model-state inspection.

In live mode, the inspection surface is richer than a simple hover label: cell-detail payloads are
expected to expose local plants, swarms, signal/toxin concentrations, visible substances, and
touching mycorrhizal links in a way that stays aligned with the dashboard canvas overlays.

This makes the UI more than a configuration form: it is an operational surface for building,
running, and interpreting simulations.

## Canonical UI Chapters

- Draft state and the load boundary:
  [`draft-state-and-load-workflow.md`](draft-state-and-load-workflow.md)
- HTMX partial composition and builder route structure:
  [`htmx-partials-and-builder-routes.md`](htmx-partials-and-builder-routes.md)

## Current UI Invariants

### The browser is not the source of truth

All authoritative scenario editing happens on the server through `DraftState`.

### The builder is not the live runtime

The UI can preview, import, export, and edit scenarios without mutating the live engine until the
operator explicitly loads the draft.

### HTML is a first-class response format

Because the application is HTMX-driven, HTML fragments are part of the formal interface contract,
not just a legacy convenience.

### JavaScript is deliberately narrow in scope

High-frequency spatial rendering is handled in the browser, but configuration logic, validation,
and canonical state transformations remain server-side.

## Verified Current-State Evidence

This section is grounded in:

- `src/phids/api/ui_state.py`
- `src/phids/api/main.py`
- `src/phids/api/templates/`
- `tests/test_ui_routes.py`
- `tests/test_ui_state.py`
- `tests/test_api_builder_and_helpers.py`

## Legacy Provenance

This section is seeded from:

- `legacy/2026-03-11/PHIDS_htmx_ui_design_specification.md`
- current template partials under `src/phids/api/templates/`
