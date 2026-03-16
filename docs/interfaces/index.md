# Interfaces

PHIDS exposes the simulator through two intentionally different surfaces:

- a programmatic FastAPI + WebSocket interface, and
- a server-driven UI built with Jinja templates and HTMX.

These surfaces share schema definitions and runtime state, but they do not serve identical
purposes.

## Interface Thesis

The interface layer in PHIDS should be understood as a **controlled execution boundary**, not just
as a convenience wrapper around internal Python objects.

Its responsibilities are to:

- validate external inputs,
- expose explicit runtime control,
- preserve the distinction between draft and live state,
- provide streams appropriate to both machines and browsers,
- support interactive scientific inspection without surrendering state ownership to the client.

## Surface Classification

The current interface layer contains four major surface types:

1. **scenario and lifecycle REST endpoints**,
2. **HTML partial routes for HTMX-driven UI composition**,
3. **JSON polling and inspection helpers for the control center**,
4. **two distinct WebSocket protocols**.

## API Surface

The API provides:

- scenario loading,
- simulation lifecycle control,
- status reporting,
- wind updates,
- telemetry export,
- binary simulation streaming,
- lightweight UI streaming.

## State Ownership

The most important interface-level distinction in PHIDS is this:

- the **live runtime** is the active `SimulationLoop`, and
- the **editable UI state** is `DraftState` in `phids.api.ui_state`.

The UI mutates draft configuration first. Only an explicit load action turns that draft into a
live simulation.

This distinction is not incidental. It is the architectural rule that prevents the browser from
becoming an unsupervised runtime mutation layer.

## Current Interface Documents

- Detailed route families and stream semantics:
  [`rest-and-websocket-surfaces.md`](rest-and-websocket-surfaces.md)
- Draft-to-live builder workflow:
  [`../ui/draft-state-and-load-workflow.md`](../ui/draft-state-and-load-workflow.md)
- HTMX partial composition and builder routes:
  [`../ui/htmx-partials-and-builder-routes.md`](../ui/htmx-partials-and-builder-routes.md)

## Key Current-State Distinctions

### Machine-oriented vs browser-oriented streams

PHIDS intentionally exposes both:

- a compact binary simulation stream for full-state transport, and
- a lightweight JSON UI stream optimized for canvas rendering.

### Draft preview vs live inspection

Some UI-facing endpoints, such as cell-detail inspection, can operate either against the draft
preview or a loaded live simulation depending on runtime state.

### HTML fragments as first-class API products

Many builder routes return HTML rather than JSON because the server-rendered UI is a primary
product surface of the application.

## Evidence Base

This section is grounded in the current implementation and tests, especially:

- `src/phids/api/main.py`
- `src/phids/api/routers/`
- `src/phids/api/ui_state.py`
- `tests/test_api_routes.py`
- `tests/test_ui_routes.py`
- `tests/test_api_builder_and_helpers.py`

## Key Source Modules

- `src/phids/api/main.py`
- `src/phids/api/routers/`
- `src/phids/api/schemas.py`
- `src/phids/api/ui_state.py`
