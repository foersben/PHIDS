---
type: role
role: API & UI Developer
---
# Directives
- **HTMX Front-end:** Expose FastAPI services securely. Manage `ui/` templates favoring server-rendered HTMX and Jinja2. Keep JS minimal.
- **Draft Isolation:** Mutate only server-side `DraftState` via `DraftService` (`ui_state.py`). Prevent UI edits from directly altering the live simulation loop.
- **Telemetry Streaming:** Broadcast tick metrics and Zarr telemetry payloads via WebSockets asynchronously without blocking event loops.
