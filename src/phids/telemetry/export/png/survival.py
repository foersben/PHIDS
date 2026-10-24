# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Survival probability plot rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from phids.telemetry.export.png.types import TelemetryRows


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
