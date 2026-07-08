from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from phids.telemetry.export.core import (
    decimate_dataframe,
    filter_dataframe_columns,
    filter_telemetry_rows,
    telemetry_to_dataframe,
)

if TYPE_CHECKING:
    from phids.telemetry.analytics import TelemetryRow

logger = logging.getLogger(__name__)

TelemetryRows = list["TelemetryRow"]

def export_bytes_tex_table(
    rows: TelemetryRows,
    *,
    columns: str | None = None,
    include_flora_ids: str | None = None,
    include_herbivore_ids: str | None = None,
    tick_interval: int = 1,
) -> bytes:
    r"""Render the telemetry rows as a booktabs LaTeX tabular environment.

    Flattens per-species dicts into a wide pandas DataFrame via
    :func:`telemetry_to_dataframe`, then serialises to LaTeX using
    ``DataFrame.to_latex(index=False)``, which emits
    ``\\toprule``, ``\\midrule``, and ``\\bottomrule`` rules consistent with
    the ``booktabs`` LaTeX package conventions expected in peer-reviewed journals.

    Args:
        rows: Raw telemetry rows from ``TelemetryRecorder._rows``.
        columns: Optional comma-separated list of columns to include.
        include_flora_ids: Optional comma-separated list of flora species IDs to filter.
        include_herbivore_ids: Optional comma-separated list of herbivore species IDs to filter.
        tick_interval: Integer tick interval to decimate rows.

    Returns:
        bytes: UTF-8 encoded LaTeX ``tabular`` source.
    """
    filtered_rows = filter_telemetry_rows(rows, flora_ids=include_flora_ids, herbivore_ids=include_herbivore_ids)
    df = telemetry_to_dataframe(filtered_rows)
    df = filter_dataframe_columns(df, columns)
    df = decimate_dataframe(df, tick_interval)
    if df.empty:
        return b"% No telemetry data\n"
    latex: str = df.to_latex(index=False, float_format="%.2f")
    return latex.encode("utf-8")
