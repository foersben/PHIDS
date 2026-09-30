# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Dashboard payload construction package."""

from __future__ import annotations

from phids.api.presenters.dashboard.payloads.collections import (
    _collect_flora_species,
    _collect_live_plants,
    _collect_live_swarms,
)
from phids.api.presenters.dashboard.payloads.core import build_live_dashboard_payload
from phids.api.presenters.dashboard.payloads.metrics import PlantMetrics, _compute_plant_metrics
from phids.api.presenters.dashboard.payloads.snapshot import (
    _extract_plants,
    _extract_substances,
    _extract_swarms,
    extract_ui_snapshot,
)

__all__ = [
    "PlantMetrics",
    "_collect_flora_species",
    "_collect_live_plants",
    "_collect_live_swarms",
    "_compute_plant_metrics",
    "_extract_plants",
    "_extract_substances",
    "_extract_swarms",
    "build_live_dashboard_payload",
    "extract_ui_snapshot",
]
