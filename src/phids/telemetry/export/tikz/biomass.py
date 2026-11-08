"""TikZ biomass chart generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.telemetry.analytics import TelemetryRow
TelemetryRows = list["TelemetryRow"]


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
        LaTeX ``tikzpicture`` source.
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
