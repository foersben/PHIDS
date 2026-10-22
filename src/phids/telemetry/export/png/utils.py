# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Utility functions for telemetry export PNG generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.telemetry.analytics import TelemetryRow

TelemetryRows = list["TelemetryRow"]


def _extract_biomass_series(rows: TelemetryRows, fid: int) -> list[float]:
    """Extract biomass series for a given species id.

    Args:
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        fid: Species identifier.

    Returns:
        The biomass series.
    """
    return [float(r.get("plant_pop_by_species", {}).get(fid, 0.0)) for r in rows]
