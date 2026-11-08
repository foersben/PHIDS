"""TikZ phasespace chart generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.telemetry.export.core import (
    _get_phasespace_axis,
)

if TYPE_CHECKING:
    from phids.telemetry.analytics import TelemetryRow
TelemetryRows = list["TelemetryRow"]


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
        LaTeX ``tikzpicture`` source.
    """
    x, plant_name = _get_phasespace_axis(rows, plant_species_id, True, flora_names)
    y, herbivore_name = _get_phasespace_axis(rows, herbivore_species_id, False, herbivore_names)

    coords = " ".join(f"({x[i]},{y[i]})" for i in range(len(rows)))

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
