# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Targeted unit tests for ChartJS telemetry series extraction.

Validates numerical parity between row-based extraction and vectorized Polars
DataFrame extraction pipelines, as well as graceful handling of empty frames.
"""

from __future__ import annotations

import polars as pl
import pytest

from phids.api.routers.telemetry.chartjs import _extract_chart_series, _extract_chart_series_df


def _build_chart_rows(n: int) -> list[dict[str, object]]:
    """Build minimal telemetry row dictionaries for use in extraction tests.

    Args:
        n: Number of sequential frames to generate.

    Returns:
        List of synthetic telemetry frame dictionaries.
    """
    return [
        {
            "tick": i,
            "flora_population": 100 + i,
            "herbivore_population": 50 + i,
            "total_flora_energy": 200.0 + i,
            "plant_pop_by_species": {},
            "plant_energy_by_species": {},
            "defense_cost_by_species": {},
            "swarm_pop_by_species": {},
        }
        for i in range(n)
    ]


def _rows_to_df(rows: list[dict[str, object]]) -> pl.DataFrame:
    """Convert minimal row dicts to the Polars schema expected by _extract_chart_series_df.

    Args:
        rows: Minimal telemetry row dictionaries.

    Returns:
        Polars DataFrame matching telemetry extract schemas.
    """
    return pl.DataFrame(
        {
            "tick": [int(r["tick"]) for r in rows],  # type: ignore[arg-type]
            "flora_population": [int(r["flora_population"]) for r in rows],  # type: ignore[arg-type]
            "herbivore_population": [int(r["herbivore_population"]) for r in rows],  # type: ignore[arg-type]
            "total_flora_energy": [float(r["total_flora_energy"]) for r in rows],  # type: ignore[arg-type]
        }
    )


def test_extract_chart_series_df_matches_row_path() -> None:
    """Verify that the Polars fast path produces numerically identical scalar series to the row path.

    Both ``_extract_chart_series`` (row-based) and ``_extract_chart_series_df`` (Polars-based) are
    called on equivalent data. The resulting ``labels`` and the three scalar series must be
    element-wise identical, confirming that vectorized extraction does not introduce rounding or
    ordering discrepancies compared to the reference implementation.
    """
    rows = _build_chart_rows(20)
    df = _rows_to_df(rows)

    labels_row, series_row = _extract_chart_series(rows, flora_ids=[], herbivore_ids=[])
    labels_df, series_df = _extract_chart_series_df(df, flora_ids=[], herbivore_ids=[])

    assert labels_row == labels_df, "Tick labels must match between row and DataFrame paths."
    assert series_row["flora_population"] == series_df["flora_population"]
    assert series_row["herbivore_population"] == series_df["herbivore_population"]
    assert series_row["total_flora_energy"] == pytest.approx(series_df["total_flora_energy"], rel=1e-9)


def test_extract_chart_series_df_empty_dataframe() -> None:
    """Verify that an empty Polars DataFrame returns empty labels and zero-length series.

    This guards the edge case where the simulation has just started and no telemetry rows have
    been recorded yet. The function must return an empty label list and pre-initialized empty
    series dicts without raising, matching the behavior of the row-based path on an empty list.
    """
    empty_df = pl.DataFrame(
        {
            "tick": pl.Series([], dtype=pl.Int64),
            "flora_population": pl.Series([], dtype=pl.Int64),
            "herbivore_population": pl.Series([], dtype=pl.Int64),
            "total_flora_energy": pl.Series([], dtype=pl.Float64),
        }
    )

    labels, series = _extract_chart_series_df(empty_df, flora_ids=[1, 2], herbivore_ids=[3])

    assert labels == []
    assert series["flora_population"] == []
    assert series["herbivore_population"] == []
    assert series["total_flora_energy"] == []
    assert series["plant_1_pop"] == []
    assert series["swarm_3_pop"] == []
