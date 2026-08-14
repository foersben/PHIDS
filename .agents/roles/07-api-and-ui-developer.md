---
type: Agent Role
title: Directives
status: stable
stale_after: "2027-01-01"
version: 0.1
description: "- **HTMX Front-end:** Expose FastAPI services securely. Manage `ui/`
  templates favoring server-rendered HTMX and Jinja2. Keep JS minimal."
tags: [documentation]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
verified: {by: process:okf-updater, at: "2026-08-14T16:00:00Z"}
role: API & UI Developer
sources:
- id: ui_state
  resource: ui_state.py
---

# Directives

- **HTMX Front-end:** Expose FastAPI services securely. Manage `ui/` templates favoring server-rendered HTMX and Jinja2. Keep JS minimal.
- **Draft Isolation:** Mutate only server-side `DraftState` via `DraftService` (`ui_state.py`). Prevent UI edits from directly altering the live simulation loop.
- **Telemetry Streaming:** Broadcast tick metrics and Zarr telemetry payloads via WebSockets asynchronously without blocking event loops.
