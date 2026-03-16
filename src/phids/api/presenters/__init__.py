"""Presenter sub-package for PHIDS API payload assembly.

This package encapsulates the transformation of live ECS world state and draft configuration data
into the structured JSON payloads consumed by the browser canvas and HTMX tooltip system.  By
isolating these heavy serialisation routines from the FastAPI composition root, the package enforces
a disciplined separation between HTTP dispatch concerns and the biological interpretation of
simulation state.

The canonical entry point is :mod:`phids.api.presenters.dashboard`, which exposes
:func:`~phids.api.presenters.dashboard.build_live_cell_details`,
:func:`~phids.api.presenters.dashboard.build_preview_cell_details`, and
:func:`~phids.api.presenters.dashboard.build_live_dashboard_payload`.  Each function accepts
explicit, dependency-injected arguments — most notably a ``substance_names`` mapping — rather than
reading module-level mutable state, thereby supporting deterministic, side-effect-free unit testing
without requiring a running FastAPI application.
"""

from phids.api.presenters.dashboard import (
    build_draft_mycorrhizal_links,
    build_live_cell_details,
    build_live_dashboard_payload,
    build_preview_cell_details,
    validate_cell_coordinates,
)

__all__ = [
    "build_draft_mycorrhizal_links",
    "build_live_cell_details",
    "build_live_dashboard_payload",
    "build_preview_cell_details",
    "validate_cell_coordinates",
]
