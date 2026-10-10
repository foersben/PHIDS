# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Phase-space plot rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.telemetry.export.core import _get_phasespace_axis

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from phids.telemetry.analytics import TelemetryRow

TelemetryRows = list["TelemetryRow"]


def _plot_phasespace(
    ax: Axes,
    rows: TelemetryRows,
    *,
    plant_species_id: int,
    herbivore_species_id: int,
    flora_names: dict[int, str] | None,
    herbivore_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
    x_max: float | None,
    y_max: float | None,
) -> None:
    """Render a Lotka-Volterra phase-space trajectory onto ``ax``.

    Args:
        ax: Matplotlib Axes instance.
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        plant_species_id: Flora species id to use as x-axis.
        herbivore_species_id: Herbivore species id to use as y-axis.
        flora_names: Optional display names for flora species.
        herbivore_names: Optional display names for herbivore species.
        title: Optional custom chart title.
        x_label: Optional custom x-axis label.
        y_label: Optional custom y-axis label.
        x_max: Optional custom x-axis maximum value.
        y_max: Optional custom y-axis maximum value.
    """
    x, plant_name = _get_phasespace_axis(rows, plant_species_id, True, flora_names)
    y, herbivore_name = _get_phasespace_axis(rows, herbivore_species_id, False, herbivore_names)

    n = len(x)
    if n > 0:
        colours = [float(i) / max(n - 1, 1) for i in range(n)]
        ax.scatter(x, y, c=colours, cmap="viridis", s=10, zorder=3, alpha=0.8)
        ax.plot(x, y, color="#64748b", linewidth=0.8, alpha=0.5, zorder=2)
        ax.plot(x[0], y[0], "go", markersize=8, label="Start", zorder=4)
        ax.plot(x[-1], y[-1], "rs", markersize=8, label="End", zorder=4)

    ax.set_xlabel(x_label or f"Population - {plant_name}")
    ax.set_ylabel(y_label or f"Population - {herbivore_name}")
    ax.set_title(title or "PHIDS - Lotka-Volterra Phase Space")
    if x_max is not None and x_max > 0:
        ax.set_xlim(0, float(x_max))
    if y_max is not None and y_max > 0:
        ax.set_ylim(0, float(y_max))
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
