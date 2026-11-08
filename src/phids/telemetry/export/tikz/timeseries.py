"""TikZ timeseries chart generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.telemetry.analytics import TelemetryRow
TelemetryRows = list["TelemetryRow"]


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
        LaTeX ``tikzpicture`` source.
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
