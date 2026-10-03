# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Biomass stack plot rendering for PNG export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.telemetry.export.core import _FLORA_COLOURS

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from phids.telemetry.export.png.types import TelemetryRows


def _extract_biomass_series(rows: TelemetryRows, fid: int) -> list[float]:
    """Extract biomass series for a given species id.

    Args:
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        fid: Species identifier.

    Returns:
        The biomass series.
    """
    return [float(r.get("plant_pop_by_species", {}).get(fid, 0.0)) for r in rows]


def _plot_biomass_stack(
    ax: Axes,
    rows: TelemetryRows,
    ticks: list[int],
    *,
    flora_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> None:
    """Render stacked flora population trajectories as a biomass-proxy area chart.

    Args:
        ax: Matplotlib Axes instance.
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        ticks: Tick index list aligned with ``rows``.
        flora_names: Optional display names for flora species.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.
    """
    all_flora: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_pop_by_species", {}).keys())
    ordered = sorted(all_flora)
    if not ordered:
        ax.plot(ticks, [0.0] * len(ticks), color="#94a3b8", linewidth=1.0, label="No flora")
    else:
        ys = [_extract_biomass_series(rows, fid) for fid in ordered]
        labels = [(flora_names or {}).get(fid, f"Flora {fid}") for fid in ordered]
        colours = [_FLORA_COLOURS[i % len(_FLORA_COLOURS)] for i, _ in enumerate(ordered)]
        ax.stackplot(ticks, ys, labels=labels, colors=colours, alpha=0.35)
        for i, series in enumerate(ys):
            ax.plot(ticks, series, color=colours[i], linewidth=0.9, alpha=0.7)

    ax.set_xlabel(x_label or "Tick")
    ax.set_ylabel(y_label or "Stacked biomass proxy")
    ax.set_title(title or "PHIDS - Systemic Carrying Capacity")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.3)
