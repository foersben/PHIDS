# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Telemetry export to PGFPlots TikZ code.

Generates self-contained tikzpicture environments containing PGFPlots chart specifications
for LaTeX papers (time series, phase spaces, defense economy ratio, biomass stack, survival probability).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from phids.telemetry.export.core import _append_species_id, filter_telemetry_rows

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
        str: LaTeX source code for a complete ``tikzpicture`` environment.

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


def _tikz_timeseries(
    rows: TelemetryRows,
    *,
    flora_names: dict[int, str] | None,
    herbivore_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> str:
    """Build PGFPlots code for a multi-species population time series chart.

    Args:
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        flora_names: Optional display names for flora species.
        herbivore_names: Optional display names for herbivore species.
        title: Optional custom chart title.
        x_label: Optional custom x-axis label.
        y_label: Optional custom y-axis label.

    Returns:
        str: LaTeX ``tikzpicture`` source.

    """
    all_flora: set[int] = set()
    all_herbivores: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_pop_by_species", {}).keys())
        all_herbivores.update(r.get("swarm_pop_by_species", {}).keys())

    flora_colours = ["green!60!black", "lime!80!black", "teal", "green!40!black", "olive"]
    herbivore_colours = ["red!70!black", "orange!80!black", "purple", "magenta!70!black", "brown"]

    plots = []
    for i, fid in enumerate(sorted(all_flora)):
        colour = flora_colours[i % len(flora_colours)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        coords = " ".join(f"({r.get('tick', 0)},{r.get('plant_pop_by_species', {}).get(fid, 0)})" for r in rows)
        plots.append(f"    \\addplot[color={colour}, thick] coordinates {{{coords}}};\n    \\addlegendentry{{{name}}}")

    for i, pid in enumerate(sorted(all_herbivores)):
        colour = herbivore_colours[i % len(herbivore_colours)]
        name = (herbivore_names or {}).get(pid, f"Herbivore {pid}")
        coords = " ".join(f"({r.get('tick', 0)},{r.get('swarm_pop_by_species', {}).get(pid, 0)})" for r in rows)
        plots.append(
            f"    \\addplot[color={colour}, thick, dashed] coordinates {{{coords}}};\n    \\addlegendentry{{{name}}}"
        )

    body = "\n".join(plots)
    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or 'Tick'}}},\n"
        f"    ylabel={{{y_label or 'Population'}}},\n"
        f"    title={{{title or 'PHIDS -- Population Time Series'}}},\n"
        "    legend pos=north east,\n"
        "    grid=major,\n"
        "    width=12cm, height=7cm,\n"
        "]\n" + body + "\n\\end{axis}\n\\end{tikzpicture}"
    )


def _tikz_phasespace(
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
) -> str:
    """Build PGFPlots code for a Lotka-Volterra phase-space chart.

    Args:
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        plant_species_id: Flora species id for x-axis.
        herbivore_species_id: Herbivore species id for y-axis.
        flora_names: Optional display names for flora species.
        herbivore_names: Optional display names for herbivore species.
        title: Optional custom chart title.
        x_label: Optional custom x-axis label.
        y_label: Optional custom y-axis label.
        x_max: Optional custom x-axis maximum value.
        y_max: Optional custom y-axis maximum value.

    Returns:
        str: LaTeX ``tikzpicture`` source.

    """
    if plant_species_id == 0:
        plant_name = "Flora (Total)"
    else:
        plant_name = (flora_names or {}).get(plant_species_id, f"Flora {plant_species_id}")

    if herbivore_species_id == 0:
        herbivore_name = "Herbivores (Total)"
    else:
        herbivore_name = (herbivore_names or {}).get(
            herbivore_species_id,
            f"Herbivore {herbivore_species_id}",
        )

    def get_x(r: dict[str, object]) -> float:
        val = (
            r.get("flora_population", 0)
            if plant_species_id == 0
            else getattr(r.get("plant_pop_by_species", {}), "get", lambda *_: 0)(plant_species_id, 0)
        )
        return float(val) if isinstance(val, (int, float, str)) else 0.0

    def get_y(r: dict[str, object]) -> float:
        val = (
            r.get("herbivore_population", 0)
            if herbivore_species_id == 0
            else getattr(r.get("swarm_pop_by_species", {}), "get", lambda *_: 0)(herbivore_species_id, 0)
        )
        return float(val) if isinstance(val, (int, float, str)) else 0.0

    coords = " ".join(f"({get_x(r)},{get_y(r)})" for r in rows)

    x_bound = f"    xmax={float(x_max)},\n" if x_max is not None and x_max > 0 else ""
    y_bound = f"    ymax={float(y_max)},\n" if y_max is not None and y_max > 0 else ""

    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or (plant_name + ' Population')}}},\n"
        f"    ylabel={{{y_label or (herbivore_name + ' Population')}}},\n"
        f"    title={{{title or 'PHIDS -- Lotka-Volterra Phase Space'}}},\n"
        + x_bound
        + y_bound
        + "    grid=major,\n"
        + "    width=10cm, height=10cm,\n"
        + "]\n"
        f"    \\addplot[color=violet!70!black, thick, mark=none] coordinates {{{coords}}};\n"
        "\\end{axis}\n\\end{tikzpicture}"
    )


def _tikz_defense_economy(
    rows: TelemetryRows,
    *,
    flora_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> str:
    """Build PGFPlots code for per-species defense economy trajectories.

    Args:
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        flora_names: Optional display names for flora species.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.

    Returns:
        str: LaTeX ``tikzpicture`` source.

    """
    all_flora: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_energy_by_species", {}).keys())
        all_flora.update(r.get("defense_cost_by_species", {}).keys())

    flora_colours = ["green!60!black", "lime!80!black", "teal", "green!40!black", "olive"]
    plots = []
    for i, fid in enumerate(sorted(all_flora)):
        colour = flora_colours[i % len(flora_colours)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        coords_parts = []
        for r in rows:
            tick = r.get("tick", 0)
            defense = float(r.get("defense_cost_by_species", {}).get(fid, 0.0))
            energy = float(r.get("plant_energy_by_species", {}).get(fid, 0.0))
            ratio = defense / energy if energy > 0.0 else 0.0
            coords_parts.append(f"({tick},{ratio})")
        coords = " ".join(coords_parts)
        plots.append(f"    \\addplot[color={colour}, thick] coordinates {{{coords}}};\n    \\addlegendentry{{{name}}}")

    body = "\n".join(plots)
    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or 'Tick'}}},\n"
        f"    ylabel={{{y_label or 'Defense economy ratio'}}},\n"
        f"    title={{{title or 'PHIDS -- Metabolic Defense Economy'}}},\n"
        "    legend pos=north east,\n"
        "    grid=major,\n"
        "    width=12cm, height=7cm,\n"
        "]\n" + body + "\n\\end{axis}\n\\end{tikzpicture}"
    )


def _tikz_biomass_stack(
    rows: TelemetryRows,
    *,
    flora_names: dict[int, str] | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> str:
    """Build PGFPlots code for stacked-biomass proxy trajectories.

    Args:
        rows: A list of recorded telemetry frame dictionaries sequentially captured during the simulation execution.
        flora_names: Optional display names for flora species.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.

    Returns:
        str: LaTeX ``tikzpicture`` source.

    """
    all_flora: set[int] = set()
    for r in rows:
        all_flora.update(r.get("plant_pop_by_species", {}).keys())

    flora_colours = ["green!60!black", "lime!80!black", "teal", "green!40!black", "olive"]
    plots = []
    for i, fid in enumerate(sorted(all_flora)):
        colour = flora_colours[i % len(flora_colours)]
        name = (flora_names or {}).get(fid, f"Flora {fid}")
        coords = " ".join(f"({r.get('tick', 0)},{r.get('plant_pop_by_species', {}).get(fid, 0)})" for r in rows)
        plots.append(
            f"    \\addplot+[name path={name.replace(' ', '_')}, color={colour}, thick] coordinates {{{coords}}};\n"
            f"    \\addlegendentry{{{name}}}"
        )

    body = "\n".join(plots)
    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or 'Tick'}}},\n"
        f"    ylabel={{{y_label or 'Stacked biomass proxy'}}},\n"
        f"    title={{{title or 'PHIDS -- Systemic Carrying Capacity'}}},\n"
        "    legend pos=north east,\n"
        "    grid=major,\n"
        "    width=12cm, height=7cm,\n"
        "]\n" + body + "\n\\end{axis}\n\\end{tikzpicture}"
    )


def _tikz_survival_probability(
    rows: TelemetryRows,
    *,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
) -> str:
    """Build PGFPlots code for batch survival probability trajectories.

    Args:
        rows: Telemetry records enriched with batch 'survival_probability' metrics.
        title: Optional chart title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.

    Returns:
        str: LaTeX ``tikzpicture`` source.

    """
    coords = " ".join(f"({r.get('tick', 0)},{100.0 * float(r.get('survival_probability', 0.0))})" for r in rows)
    return (
        "\\begin{tikzpicture}\n"
        "\\begin{axis}[\n"
        f"    xlabel={{{x_label or 'Tick'}}},\n"
        f"    ylabel={{{y_label or 'Simulations alive (%)'}}},\n"
        f"    title={{{title or 'PHIDS -- Batch Survival Probability'}}},\n"
        "    ymin=0, ymax=100,\n"
        "    grid=major,\n"
        "    width=12cm, height=7cm,\n"
        "]\n"
        f"    \\addplot[color=cyan!70!black, thick] coordinates {{{coords}}};\n"
        "\\end{axis}\n\\end{tikzpicture}"
    )
