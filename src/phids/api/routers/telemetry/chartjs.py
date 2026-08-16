# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Chart.js data extraction logic and endpoints for telemetry."""

from __future__ import annotations

import math

import polars as pl
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import phids.api.main as api_main

router = APIRouter()


def _safe_float(value: object) -> float:
    """Return a finite float representation for telemetry serialization."""
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return 0.0
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isfinite(candidate):
        return candidate
    return 0.0


def _filter_telemetry_rows_for_chart(
    rows: list[dict[str, object]],
    run_id: str | None,
    current_run_id: str,
    since_tick: int | None,
) -> list[dict[str, object]]:
    """Filter telemetry rows based on client synchronization state."""
    if run_id == current_run_id and since_tick is not None and rows:
        latest_tick = int(rows[-1].get("tick", -1))  # type: ignore
        if latest_tick >= since_tick:
            return [row for row in rows if int(row.get("tick", -1)) > since_tick]  # type: ignore
    return rows


def _extract_chart_series(
    rows: list[dict[str, object]],
    flora_ids: list[int],
    herbivore_ids: list[int],
) -> tuple[list[int], dict[str, list[float]]]:
    """Extract numerical time series and labels from raw telemetry rows."""
    labels: list[int] = []
    series: dict[str, list[float]] = {
        "flora_population": [],
        "herbivore_population": [],
        "total_flora_energy": [],
    }
    for fid in flora_ids:
        series[f"plant_{fid}_pop"] = []
        series[f"plant_{fid}_energy"] = []
        series[f"defense_cost_{fid}"] = []
    for hid in herbivore_ids:
        series[f"swarm_{hid}_pop"] = []

    for r in rows:
        # Note: We must retain original exact values where possible; some tests assert strict arrays.
        tick_val = int(r.get("tick", 0))  # type: ignore
        labels.append(tick_val)
        series["flora_population"].append(_safe_float(r.get("flora_population", 0)))
        series["herbivore_population"].append(_safe_float(r.get("herbivore_population", 0)))
        series["total_flora_energy"].append(_safe_float(r.get("total_flora_energy", 0.0)))

        plant_pop = r.get("plant_pop_by_species", {})
        plant_energy = r.get("plant_energy_by_species", {})
        defense_cost = r.get("defense_cost_by_species", {})
        if isinstance(plant_pop, dict) and isinstance(plant_energy, dict) and isinstance(defense_cost, dict):
            for fid in flora_ids:
                series[f"plant_{fid}_pop"].append(_safe_float(plant_pop.get(fid, 0)))
                series[f"plant_{fid}_energy"].append(_safe_float(plant_energy.get(fid, 0.0)))
                series[f"defense_cost_{fid}"].append(_safe_float(defense_cost.get(fid, 0.0)))

        swarm_pop = r.get("swarm_pop_by_species", {})
        if isinstance(swarm_pop, dict):
            for hid in herbivore_ids:
                series[f"swarm_{hid}_pop"].append(_safe_float(swarm_pop.get(hid, 0)))

    return labels, series


def _extract_chart_series_df(
    df: pl.DataFrame,
    flora_ids: list[int],
    herbivore_ids: list[int],
) -> tuple[list[int], dict[str, list[float]]]:
    """Extract numerical time series from a Polars DataFrame using vectorized columnar extraction.

    This is the fast path for :func:`_extract_chart_series` when a live Polars DataFrame is
    available. The four scalar columns (``tick``, ``flora_population``, ``herbivore_population``,
    ``total_flora_energy``) are extracted in a single vectorized C operation via ``.to_list()``.
    Per-species nested-dict columns cannot be stored directly in a flat Polars frame without a
    prior ``telemetry_to_dataframe`` unnest pass, so they are handled via a single compact row
    iteration over the raw ``_rows`` list passed as ``raw_rows``.

    Args:
        df: Polars DataFrame with at minimum the four scalar telemetry columns.
        flora_ids: Ordered list of flora species IDs whose per-species series to extract.
        herbivore_ids: Ordered list of herbivore species IDs whose per-species series to extract.

    Returns:
        A ``(labels, series)`` pair identical in structure to :func:`_extract_chart_series`.
    """
    if df.is_empty():
        series: dict[str, list[float]] = {
            "flora_population": [],
            "herbivore_population": [],
            "total_flora_energy": [],
        }
        for fid in flora_ids:
            series[f"plant_{fid}_pop"] = []
            series[f"plant_{fid}_energy"] = []
            series[f"defense_cost_{fid}"] = []
        for hid in herbivore_ids:
            series[f"swarm_{hid}_pop"] = []
        return [], series

    # --- Vectorized scalar extraction (fast path) ---
    labels: list[int] = df["tick"].cast(pl.Int64).to_list()
    series = {
        "flora_population": df["flora_population"].cast(pl.Float64).to_list(),
        "herbivore_population": df["herbivore_population"].cast(pl.Float64).to_list(),
        "total_flora_energy": df["total_flora_energy"].cast(pl.Float64).to_list(),
    }

    # --- Per-species series: initialize to zero-filled lists ---
    n = df.height
    for fid in flora_ids:
        series[f"plant_{fid}_pop"] = [0.0] * n
        series[f"plant_{fid}_energy"] = [0.0] * n
        series[f"defense_cost_{fid}"] = [0.0] * n
    for hid in herbivore_ids:
        series[f"swarm_{hid}_pop"] = [0.0] * n

    return labels, series


def _overlay_flora_data(
    series: dict[str, list[float]],
    r: dict[str, object],
    i: int,
    flora_ids: list[int],
) -> None:
    """Extract flora metrics from raw dictionaries and overlay into columnar series.

    Args:
        series: Output dictionary mapping series names to float lists.
        r: Raw unstructured dictionary row for the current tick.
        i: Current time-index within the extracted output lists.
        flora_ids: Bounded array of flora IDs requiring metric overlay.
    """
    plant_pop = r.get("plant_pop_by_species", {})
    plant_energy = r.get("plant_energy_by_species", {})
    defense_cost = r.get("defense_cost_by_species", {})

    if not (isinstance(plant_pop, dict) and isinstance(plant_energy, dict) and isinstance(defense_cost, dict)):
        return

    for fid in flora_ids:
        if i < len(series.get(f"plant_{fid}_pop", [])):
            series[f"plant_{fid}_pop"][i] = _safe_float(plant_pop.get(fid, 0))
            series[f"plant_{fid}_energy"][i] = _safe_float(plant_energy.get(fid, 0.0))
            series[f"defense_cost_{fid}"][i] = _safe_float(defense_cost.get(fid, 0.0))


def _overlay_herbivore_data(
    series: dict[str, list[float]],
    r: dict[str, object],
    i: int,
    herbivore_ids: list[int],
) -> None:
    """Extract herbivore metrics from raw dictionaries and overlay into columnar series.

    Args:
        series: Output dictionary mapping series names to float lists.
        r: Raw unstructured dictionary row for the current tick.
        i: Current time-index within the extracted output lists.
        herbivore_ids: Bounded array of herbivore IDs requiring metric overlay.
    """
    swarm_pop = r.get("swarm_pop_by_species", {})
    if not isinstance(swarm_pop, dict):
        return

    for hid in herbivore_ids:
        if i < len(series.get(f"swarm_{hid}_pop", [])):
            series[f"swarm_{hid}_pop"][i] = _safe_float(swarm_pop.get(hid, 0))


def _overlay_raw_species_data(
    series: dict[str, list[float]],
    raw_rows_for_species: list[dict[str, object]],
    flora_ids: list[int],
    herbivore_ids: list[int],
) -> None:
    """Overlay per-species nested-dict data from raw rows."""
    if not flora_ids and not herbivore_ids:
        return

    for i, r in enumerate(raw_rows_for_species):
        if flora_ids:
            _overlay_flora_data(series, r, i, flora_ids)
        if herbivore_ids:
            _overlay_herbivore_data(series, r, i, herbivore_ids)


@router.get("/api/telemetry/chartjs-data", summary="Per-species time-series data for Chart.js")
async def telemetry_chartjs_data(
    since_tick: int | None = None,
    run_id: str | None = None,
) -> JSONResponse:
    """Return per-species population and energy time series for browser charts.

    Returns:
        JSONResponse: Chart.js-compatible labels, per-species identifiers, display names, and
        numeric series extracted from the live telemetry buffer.
    """
    if api_main._sim_loop is None:
        return JSONResponse({"labels": [], "flora_ids": [], "herbivore_ids": [], "series": {}, "run_id": ""})

    current_run_id = api_main._sim_loop.run_id
    raw_rows = api_main._sim_loop.telemetry._rows

    species = api_main._sim_loop.telemetry.get_species_ids()
    flora_ids = species["flora_ids"]
    herbivore_ids = species["herbivore_ids"]

    flora_names = {sp.species_id: sp.name for sp in api_main._sim_loop.config.flora_species}
    herbivore_names = {sp.species_id: sp.name for sp in api_main._sim_loop.config.herbivore_species}

    labels, series = _extract_chart_series_df(
        api_main._sim_loop.telemetry.dataframe.filter(pl.col("tick") > (since_tick or -1))
        if run_id == current_run_id and since_tick is not None
        else api_main._sim_loop.telemetry.dataframe,
        flora_ids,
        herbivore_ids,
    )
    # Overlay per-species nested-dict data from raw rows (not available in flat dataframe)
    raw_rows_for_species = _filter_telemetry_rows_for_chart(raw_rows, run_id, current_run_id, since_tick)
    _overlay_raw_species_data(series, raw_rows_for_species, flora_ids, herbivore_ids)

    return JSONResponse(
        {
            "labels": labels,
            "flora_ids": flora_ids,
            "herbivore_ids": herbivore_ids,
            "flora_names": {str(k): v for k, v in flora_names.items()},
            "herbivore_names": {str(k): v for k, v in herbivore_names.items()},
            "series": series,
            "run_id": current_run_id,
        }
    )
