# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Plot rendering routines for PNG telemetry export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.telemetry.export.core import (
    _FLORA_COLOURS,
    _HERBIVORE_COLOURS,
    _get_phasespace_axis,
)

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


def _plot_defense_economy(
    ax: Axes,
    rows: TelemetryRows,
    ticks: list[int],
    *,
    flora_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> None:
    """Render per-species defense-cost to energy ratio trajectories onto ``ax``.

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
        all_flora.update(r.get("plant_energy_by_species", {}).keys())
        all_flora.update(r.get("defense_cost_by_species", {}).keys())

    for i, fid in enumerate(sorted(all_flora)):
        colour = _FLORA_COLOURS[i % len(_FLORA_COLOURS)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        ratio: list[float] = []
        for r in rows:
            defense = float(r.get("defense_cost_by_species", {}).get(fid, 0.0))
            energy = float(r.get("plant_energy_by_species", {}).get(fid, 0.0))
            ratio.append(defense / energy if energy > 0.0 else 0.0)
        ax.plot(ticks, ratio, color=colour, linewidth=1.5, label=name)

    ax.set_xlabel(x_label or "Tick")
    ax.set_ylabel(y_label or "Defense economy ratio")
    ax.set_title(title or "PHIDS - Metabolic Defense Economy")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


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


def _plot_survival_probability(
    ax: Axes,
    rows: TelemetryRows,
    ticks: list[int],
    *,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> None:
    """Render batch survival probability trajectory onto ``ax``.

    Args:
        ax: Matplotlib Axes instance.
        rows: Telemetry records enriched with batch 'survival_probability' metrics.
        ticks: Tick index list aligned with ``rows``.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.
    """
    y = [100.0 * float(r.get("survival_probability", 0.0)) for r in rows]
    ax.plot(ticks, y, color="#0ea5e9", linewidth=2.0, label="Survival probability")
    ax.fill_between(ticks, y, [0.0] * len(y), color="#0ea5e9", alpha=0.15)
    ax.set_xlabel(x_label or "Tick")
    ax.set_ylabel(y_label or "Simulations alive (%)")
    ax.set_title(title or "PHIDS - Batch Survival Probability")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
