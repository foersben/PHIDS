---
type: Agent Role
title: Directives
status: active
version: 0.1
description: "- **HTMX Front-end:** Expose FastAPI services securely. Manage `ui/`
  templates favoring server-rendered HTMX and Jinja2. Keep JS minimal."
tags: [documentation]
generated: {by: process:okf-updater, at: "2026-07-21T16:01:38Z"}
role: API & UI Developer
sources:
- resource: ui_state.py
---

# Directives

- **HTMX Front-end:** Expose FastAPI services securely. Manage `ui/` templates favoring server-rendered HTMX and Jinja2. Keep JS minimal.
- **Draft Isolation:** Mutate only server-side `DraftState` via `DraftService` (`ui_state.py`). Prevent UI edits from directly altering the live simulation loop.
- **Telemetry Streaming:** Broadcast tick metrics and Zarr telemetry payloads via WebSockets asynchronously without blocking event loops.
