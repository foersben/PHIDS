# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Telemetry export to PNG images.

Renders publication-quality charts (time series, phase space, defense economy, biomass stacks,
and survival probability) using Matplotlib headless Agg backend to raw PNG bytes.
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from phids.telemetry.export.core import _FLORA_COLOURS, _HERBIVORE_COLOURS, filter_telemetry_rows

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from phids.telemetry.analytics import TelemetryRow

logger = logging.getLogger(__name__)

TelemetryRows = list["TelemetryRow"]


def generate_png_bytes(
    rows: TelemetryRows,
    plot_type: str = "timeseries",
    *,
    flora_names: dict[int, str] | None = None,
    herbivore_names: dict[int, str] | None = None,
    plant_species_id: int = 0,
    herbivore_species_id: int = 0,
    include_flora_ids: str | None = None,
    include_herbivore_ids: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    x_max: float | None = None,
    y_max: float | None = None,
    dpi: int = 150,
) -> bytes:
    """Render a matplotlib chart to PNG bytes using the headless Agg backend.

    Supports five ``plot_type`` modes:

    * ``"timeseries"`` — Overlaid line chart with one series per flora and herbivore
      species, sharing a common tick x-axis and a left y-axis for population counts.
    * ``"phasespace"`` — Lotka-Volterra phase-space scatter with ``showLine=True``
      semantics.
    * ``"defense_economy"`` — Line chart plotting defense cost divided by total energy
      capacity per flora species.
    * ``"biomass_stack"`` — Stacked area chart approximating carrying capacity share.
    * ``"survival_probability"`` — Aggregate batch survival probability (requires ensemble rows).

    Args:
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        plot_type: Output chart type (``"timeseries"``, ``"phasespace"``,
            ``"defense_economy"``, ``"biomass_stack"``, or ``"survival_probability"``).
        flora_names: Optional dictionary mapping flora species ids to display names.
        herbivore_names: Optional dictionary mapping herbivore ids to display names.
        plant_species_id: Flora species id to use for the x-axis in phasespace mode.
        herbivore_species_id: Herbivore species id to use for the y-axis in phasespace.
        include_flora_ids: Optional CSV list of flora ids to keep (filters out others).
        include_herbivore_ids: Optional CSV list of herbivore ids to keep.
        title: Optional override for the matplotlib title.
        x_label: Optional override for the matplotlib x-axis label.
        y_label: Optional override for the matplotlib y-axis label.
        x_max: Optional upper bound for the x-axis (ignored if zero or None).
        y_max: Optional upper bound for the y-axis (ignored if zero or None).
        dpi: Dots-per-inch scaling factor for rasterization.

    Returns:
        bytes: Raw PNG-encoded bytes of the rendered figure.

    """
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.use("Agg")

    rows = filter_telemetry_rows(
        rows,
        flora_ids=include_flora_ids,
        herbivore_ids=include_herbivore_ids,
    )

    if not rows:
        fig, ax = plt.subplots(figsize=(6, 4), dpi=dpi)
        ax.text(
            0.5,
            0.5,
            "No data to display\n(Filter resulted in empty series)",
            horizontalalignment="center",
            verticalalignment="center",
            transform=ax.transAxes,
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()

    ticks = [int(r.get("tick", i)) for i, r in enumerate(rows)]
    fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)

    try:
        if plot_type == "phasespace":
            _plot_phasespace(
                ax,
                rows,
                plant_species_id=plant_species_id,
                herbivore_species_id=herbivore_species_id,
                flora_names=flora_names,
                herbivore_names=herbivore_names,
                title=title,
                x_label=x_label,
                y_label=y_label,
                x_max=x_max,
                y_max=y_max,
            )
        elif plot_type == "defense_economy":
            _plot_defense_economy(
                ax,
                rows,
                ticks,
                flora_names=flora_names,
                title=title,
                x_label=x_label,
                y_label=y_label,
            )
        elif plot_type == "biomass_stack":
            _plot_biomass_stack(
                ax,
                rows,
                ticks,
                flora_names=flora_names,
                title=title,
                x_label=x_label,
                y_label=y_label,
            )
        elif plot_type == "survival_probability":
            _plot_survival_probability(
                ax,
                rows,
                ticks,
                title=title,
                x_label=x_label,
                y_label=y_label,
            )
        elif plot_type == "timeseries":
            _plot_timeseries(
                ax,
                rows,
                ticks,
                flora_names=flora_names,
                herbivore_names=herbivore_names,
                title=title,
                x_label=x_label,
                y_label=y_label,
            )
        else:
            raise ValueError(f"Unknown plot_type: {plot_type}")
    except ValueError:
        plt.close(fig)
        raise
    except Exception as exc:
        logger.exception("matplotlib render failed")
        ax.clear()
        ax.text(
            0.5,
            0.5,
            f"Render Error: {exc}",
            horizontalalignment="center",
            verticalalignment="center",
            transform=ax.transAxes,
            color="red",
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


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
    if plant_species_id == 0:
        x = [r.get("flora_population", 0) for r in rows]
        plant_name = "Flora (Total)"
    else:
        x = [r.get("plant_pop_by_species", {}).get(plant_species_id, 0) for r in rows]
        plant_name = (flora_names or {}).get(plant_species_id, f"Flora {plant_species_id}")

    if herbivore_species_id == 0:
        y = [r.get("herbivore_population", 0) for r in rows]
        herbivore_name = "Herbivores (Total)"
    else:
        y = [r.get("swarm_pop_by_species", {}).get(herbivore_species_id, 0) for r in rows]
        herbivore_name = (herbivore_names or {}).get(
            herbivore_species_id,
            f"Herbivore {herbivore_species_id}",
        )

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
        ys = [[float(r.get("plant_pop_by_species", {}).get(fid, 0.0)) for r in rows] for fid in ordered]
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
