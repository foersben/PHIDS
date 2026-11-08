# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Telemetry export to PGFPlots TikZ code.

Generates self-contained tikzpicture environments containing PGFPlots chart specifications
for LaTeX papers (time series, phase spaces, defense economy ratio, biomass stack, survival probability).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from phids.telemetry.export.core import (
    _append_species_id,
    filter_telemetry_rows,
)
from phids.telemetry.export.tikz.biomass import _tikz_biomass_stack
from phids.telemetry.export.tikz.defense import _tikz_defense_economy
from phids.telemetry.export.tikz.phasespace import _tikz_phasespace
from phids.telemetry.export.tikz.survival import _tikz_survival_probability
from phids.telemetry.export.tikz.timeseries import _tikz_timeseries

if TYPE_CHECKING:
    from phids.telemetry.analytics import TelemetryRow

logger = logging.getLogger(__name__)

TelemetryRows = list["TelemetryRow"]


def generate_tikz_str(
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
) -> str:
    r"""Generate a PGFPlots LaTeX source string for publication-quality figures.

    Produces a self-contained ``tikzpicture`` environment using the ``pgfplots``
    package. The output does not require the ``tikzplotlib`` library; instead,
    coordinates are injected directly into ``\\addplot`` commands via a
    ``\\pgfplotstable``-compatible inline coordinate format. This approach ensures
    compatibility with any LaTeX installation providing ``pgfplots >= 1.16``.

    The generated code is intended for compilation with ``pdflatex``, ``xelatex``,
    or ``lualatex`` after pasting into a document preamble that includes
    ``\\usepackage{pgfplots}`` and ``\\pgfplotsset{compat=1.18}``.

    Args:
        rows: Raw telemetry rows from ``TelemetryRecorder._rows``.
        plot_type: Chart mode - ``"timeseries"``, ``"phasespace"``,
            ``"defense_economy"``, ``"biomass_stack"``, or
            ``"survival_probability"``.
        flora_names: Optional display names keyed by flora species id.
        herbivore_names: Optional display names keyed by herbivore species id.
        plant_species_id: Flora species id for phase-space x-axis.
        herbivore_species_id: Herbivore species id for phase-space y-axis.
        include_flora_ids: Optional comma-separated list of flora species IDs to filter.
        include_herbivore_ids: Optional comma-separated list of herbivore species IDs to filter.
        title: Optional custom chart title.
        x_label: Optional custom x-axis label.
        x_max: Optional custom x-axis maximum value.
        y_label: Optional custom y-axis label.
        y_max: Optional custom y-axis maximum value.

    Returns:
        LaTeX source code for a complete ``tikzpicture`` environment.

    Raises:
        ValueError: If ``plot_type`` is not a supported chart mode.
    """
    flora_filter = include_flora_ids
    herbivore_filter = include_herbivore_ids
    if plot_type == "phasespace":
        flora_filter = _append_species_id(flora_filter, plant_species_id)
        herbivore_filter = _append_species_id(herbivore_filter, herbivore_species_id)
    plot_rows = filter_telemetry_rows(rows, flora_ids=flora_filter, herbivore_ids=herbivore_filter)
    if plot_type == "timeseries":
        return _tikz_timeseries(
            plot_rows,
            flora_names=flora_names,
            herbivore_names=herbivore_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    if plot_type == "phasespace":
        return _tikz_phasespace(
            plot_rows,
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
    if plot_type == "defense_economy":
        return _tikz_defense_economy(
            plot_rows,
            flora_names=flora_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    if plot_type == "biomass_stack":
        return _tikz_biomass_stack(
            plot_rows,
            flora_names=flora_names,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    if plot_type == "survival_probability":
        return _tikz_survival_probability(
            plot_rows,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    raise ValueError(f"Unknown tikz plot type: {plot_type}")
