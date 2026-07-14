# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Dashboard presenter package.

Exposes helpers, presenters, and serializers for rendering the biotope
dashboard, cell details, and mycorrhizal root network state in the UI.
"""

from phids.api.presenters.dashboard.cell_details import build_live_cell_details, build_preview_cell_details
from phids.api.presenters.dashboard.mycorrhizal import _links_touching_cell, build_draft_mycorrhizal_links
from phids.api.presenters.dashboard.payloads import build_live_dashboard_payload
from phids.api.presenters.dashboard.shared import (
    _default_substance_name,
    _describe_activation_condition,
    validate_cell_coordinates,
)
from phids.api.presenters.dashboard.substances import (
    _fallback_live_substance_payload,
    _is_live_substance_visible,
    _live_substance_state_payload,
    _serialize_live_substance,
)

__all__ = [
    "_default_substance_name",
    "_describe_activation_condition",
    "_fallback_live_substance_payload",
    "_is_live_substance_visible",
    "_links_touching_cell",
    "_live_substance_state_payload",
    "_serialize_live_substance",
    "build_draft_mycorrhizal_links",
    "build_live_cell_details",
    "build_live_dashboard_payload",
    "build_preview_cell_details",
    "validate_cell_coordinates",
]
