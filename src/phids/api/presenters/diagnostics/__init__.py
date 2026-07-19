"""Diagnostics presenter package."""

from phids.api.presenters.diagnostics.badge import render_status_badge_html
from phids.api.presenters.diagnostics.model import (
    EnergyDeficitSwarmRow,
    LiveSummary,
    build_energy_deficit_swarms,
    build_live_summary,
)

__all__ = [
    "EnergyDeficitSwarmRow",
    "LiveSummary",
    "build_energy_deficit_swarms",
    "build_live_summary",
    "render_status_badge_html",
]
