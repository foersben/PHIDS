"""UI routes integration test package for PHIDS FastAPI dashboard endpoints.

This package contains integration tests for all HTMX, Jinja2, and FastAPI UI endpoints,
split across cohesive functional modules:
- ``test_dashboard_and_views``: Dashboard rendering, live SSE/canvas payloads, and cell details.
- ``test_config_form_routes``: Configuration forms for flora, herbivores, biotope, and placements.
- ``test_batch_ui_routes``: Batch execution, status, and export endpoints.
- ``test_substance_and_diagnostics_routes``: Trigger rule matrices, substance definitions, and diagnostics.
"""
