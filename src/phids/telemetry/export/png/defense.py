# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Defense economy plot rendering for PNG export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.telemetry.export.core import (
    _FLORA_COLOURS,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from phids.telemetry.export.png.types import TelemetryRows


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
