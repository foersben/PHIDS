# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Timeseries plot rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.telemetry.export.core import _FLORA_COLOURS, _HERBIVORE_COLOURS

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from phids.telemetry.analytics import TelemetryRow

TelemetryRows = list["TelemetryRow"]


def _plot_timeseries(
    ax: Axes,
    rows: TelemetryRows,
    ticks: list[int],
    *,
    flora_names: dict[int, str] | None,
    herbivore_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> None:
    """Render per-species population time series onto ``ax``.

    Args:
        ax: Matplotlib Axes instance.
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        ticks: Tick index list aligned with ``rows``.
        flora_names: Optional display names for flora species.
        herbivore_names: Optional display names for herbivore species.
        title: Optional custom chart title.
        x_label: Optional custom x-axis label.
        y_label: Optional custom y-axis label.
    """
    all_flora: set[int] = set()
    all_herbivores: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_pop_by_species", {}).keys())
        all_herbivores.update(r.get("swarm_pop_by_species", {}).keys())

    for i, fid in enumerate(sorted(all_flora)):
        colour = _FLORA_COLOURS[i % len(_FLORA_COLOURS)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        y = [r.get("plant_pop_by_species", {}).get(fid, 0) for r in rows]
        ax.plot(ticks, y, color=colour, linewidth=1.5, label=name)

    for i, pid in enumerate(sorted(all_herbivores)):
        colour = _HERBIVORE_COLOURS[i % len(_HERBIVORE_COLOURS)]
        name = (herbivore_names or {}).get(pid, f"Herbivore {pid}")
        y = [r.get("swarm_pop_by_species", {}).get(pid, 0) for r in rows]
        ax.plot(ticks, y, color=colour, linewidth=1.5, linestyle="--", label=name)

    ax.set_xlabel(x_label or "Tick")
    ax.set_ylabel(y_label or "Population")
    ax.set_title(title or "PHIDS - Population Time Series")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
