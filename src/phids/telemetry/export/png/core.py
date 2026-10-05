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

from phids.telemetry.export.core import (
    filter_telemetry_rows,
)
from phids.telemetry.export.png.plots import (
    _plot_biomass_stack,
    _plot_defense_economy,
    _plot_phasespace,
    _plot_survival_probability,
    _plot_timeseries,
)

if TYPE_CHECKING:

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

    * ``"timeseries"`` - Overlaid line chart with one series per flora and herbivore
      species, sharing a common tick x-axis and a left y-axis for population counts.
    * ``"phasespace"`` - Lotka-Volterra phase-space scatter with ``showLine=True``
      semantics.
    * ``"defense_economy"`` - Line chart plotting defense cost divided by total energy
      capacity per flora species.
    * ``"biomass_stack"`` - Stacked area chart approximating carrying capacity share.
    * ``"survival_probability"`` - Aggregate batch survival probability (requires ensemble rows).

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
        Raw PNG-encoded bytes of the rendered figure.
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
