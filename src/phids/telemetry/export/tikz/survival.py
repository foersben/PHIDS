"""TikZ survival chart generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phids.telemetry.analytics import TelemetryRow
TelemetryRows = list["TelemetryRow"]


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
        LaTeX ``tikzpicture`` source.
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
