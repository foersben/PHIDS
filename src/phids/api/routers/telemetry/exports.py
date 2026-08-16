# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Telemetry export endpoints for CSV, JSON, TikZ, PNG formats."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

import phids.api.main as api_main
from phids.telemetry.export.core import (
    decimate_dataframe,
    filter_dataframe_columns,
    filter_telemetry_rows,
    telemetry_to_dataframe,
)
from phids.telemetry.export.latex import export_bytes_tex_table
from phids.telemetry.export.png import generate_png_bytes
from phids.telemetry.export.structured import (
    export_bytes_csv,
    export_bytes_json,
)
from phids.telemetry.export.tikz import generate_tikz_str

router = APIRouter()


@router.get("/api/telemetry/export/csv", summary="Export telemetry as CSV")
async def export_telemetry_csv() -> Response:
    """Stream the live telemetry table as CSV.

    Returns:
        Response: Download-oriented response containing the current telemetry dataframe encoded as
        CSV.

    Raises:
        HTTPException: Propagated when no live simulation is loaded.
    """
    loop = api_main._get_loop()

    def _build_csv_payload() -> tuple[bytes, int]:
        df = loop.telemetry.dataframe
        return export_bytes_csv(df), int(df.height)

    data, rows = await run_in_threadpool(_build_csv_payload)
    api_main.logger.info("Telemetry exported as CSV (%d rows)", rows)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=telemetry.csv"},
    )


@router.get("/api/telemetry/export/json", summary="Export telemetry as JSON")
async def export_telemetry_json() -> Response:
    """Stream the live telemetry table as NDJSON.

    Returns:
        Response: Download-oriented response containing newline-delimited telemetry rows.

    Raises:
        HTTPException: Propagated when no live simulation is loaded.
    """
    loop = api_main._get_loop()

    def _build_json_payload() -> tuple[bytes, int]:
        df = loop.telemetry.dataframe
        return export_bytes_json(df), int(df.height)

    data, rows = await run_in_threadpool(_build_json_payload)
    api_main.logger.info("Telemetry exported as NDJSON (%d rows)", rows)
    return Response(
        content=data,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=telemetry.ndjson"},
    )


async def _export_csv(
    filtered_rows: list[dict[str, object]],
    columns: str | None,
    tick_interval: int,
    normalized_data_type: str,
) -> tuple[bytes, str, str]:
    def _build_export_csv() -> bytes:
        df = telemetry_to_dataframe(filtered_rows)
        df = filter_dataframe_columns(df, columns)
        df = decimate_dataframe(df, tick_interval)
        return str(df.to_csv(index=False)).encode("utf-8")

    data = await run_in_threadpool(_build_export_csv)
    filename = f"phids_{normalized_data_type}.csv"
    media_type = "text/csv"
    return data, filename, media_type


async def _export_tex_table(
    rows: list[dict[str, object]],
    columns: str | None,
    flora_ids: str | None,
    herbivore_ids: str | None,
    tick_interval: int,
    normalized_data_type: str,
) -> tuple[bytes, str, str]:
    def _build_export_tex_table() -> bytes:
        return export_bytes_tex_table(
            rows,
            columns=columns,
            include_flora_ids=flora_ids,
            include_herbivore_ids=herbivore_ids,
            tick_interval=tick_interval,
        )

    data = await run_in_threadpool(_build_export_tex_table)
    filename = f"phids_{normalized_data_type}_table.tex"
    media_type = "text/plain"
    return data, filename, media_type


async def _export_tex_tikz(
    filtered_rows: list[dict[str, object]],
    normalized_data_type: str,
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    plant_species_id: int,
    herbivore_species_id: int,
    flora_ids: str | None,
    herbivore_ids: str | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
    x_max: float | None,
    y_max: float | None,
) -> tuple[bytes, str, str]:
    try:

        def _build_export_tikz() -> str:
            return generate_tikz_str(
                filtered_rows,
                normalized_data_type,
                flora_names=flora_names,
                herbivore_names=herbivore_names,
                plant_species_id=plant_species_id,
                herbivore_species_id=herbivore_species_id,
                include_flora_ids=flora_ids,
                include_herbivore_ids=herbivore_ids,
                title=title,
                x_label=x_label,
                y_label=y_label,
                x_max=x_max,
                y_max=y_max,
            )

        tikz = await run_in_threadpool(_build_export_tikz)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = tikz.encode("utf-8")
    filename = f"phids_{normalized_data_type}.tex"
    media_type = "text/plain"
    return data, filename, media_type


async def _export_png(
    filtered_rows: list[dict[str, object]],
    normalized_data_type: str,
    flora_names: dict[int, str],
    herbivore_names: dict[int, str],
    plant_species_id: int,
    herbivore_species_id: int,
    flora_ids: str | None,
    herbivore_ids: str | None,
    title: str | None,
    x_label: str | None,
    y_label: str | None,
    x_max: float | None,
    y_max: float | None,
) -> tuple[bytes, str, str]:
    try:

        def _build_export_png() -> bytes:
            return generate_png_bytes(
                filtered_rows,
                normalized_data_type,
                flora_names=flora_names,
                herbivore_names=herbivore_names,
                plant_species_id=plant_species_id,
                herbivore_species_id=herbivore_species_id,
                include_flora_ids=flora_ids,
                include_herbivore_ids=herbivore_ids,
                title=title,
                x_label=x_label,
                y_label=y_label,
                x_max=x_max,
                y_max=y_max,
            )

        data = await run_in_threadpool(_build_export_png)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = f"phids_{normalized_data_type}.png"
    media_type = "image/png"
    return data, filename, media_type


@router.get("/api/export/{data_type}", summary="Export telemetry data in academic formats")
async def export_telemetry_format(
    data_type: str,
    format: str = "csv",
    plant_species_id: int = 0,
    herbivore_species_id: int = 0,
    columns: str | None = None,
    flora_ids: str | None = None,
    herbivore_ids: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    x_max: float | None = None,
    y_max: float | None = None,
    tick_interval: int = 1,
) -> Response:
    """Export telemetry data as CSV, LaTeX, TikZ, or PNG artifacts.

    Args:
        data_type: Analytical projection to export, including time series and phase-space views.
        format: Output artifact encoding.
        plant_species_id: Flora species identifier used on the phase-space x-axis.
        herbivore_species_id: Herbivore species identifier used on the phase-space y-axis.
        columns: Optional comma-delimited dataframe column subset.
        flora_ids: Optional comma-delimited flora species subset.
        herbivore_ids: Optional comma-delimited herbivore species subset.
        title: Optional plot title override.
        x_label: Optional x-axis label override.
        y_label: Optional y-axis label override.
        x_max: Optional x-axis upper bound.
        y_max: Optional y-axis upper bound.
        tick_interval: Positive decimation factor applied before export.

    Returns:
        Response: File download response with a media type and filename aligned to the requested
        analytical view.

    Raises:
        HTTPException: If no live simulation is loaded, the analytical view is unknown, the
        decimation factor is invalid, or a plot generator rejects the requested parameters.
    """
    if api_main._sim_loop is None:
        raise HTTPException(status_code=404, detail="No simulation loaded.")

    normalized_data_type = "defense_economy" if data_type == "metabolic" else data_type
    if normalized_data_type not in {"timeseries", "phasespace", "defense_economy", "biomass_stack"}:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown data_type '{data_type}'. Use timeseries, phasespace, "
                "defense_economy, biomass_stack, or metabolic."
            ),
        )

    if tick_interval < 1:
        raise HTTPException(status_code=400, detail="tick_interval must be >= 1")

    rows = api_main._sim_loop.telemetry._rows
    flora_names: dict[int, str] = {sp.species_id: sp.name for sp in api_main._sim_loop.config.flora_species}
    herbivore_names: dict[int, str] = {sp.species_id: sp.name for sp in api_main._sim_loop.config.herbivore_species}
    filtered_rows = filter_telemetry_rows(rows, flora_ids=flora_ids, herbivore_ids=herbivore_ids)

    if format == "csv":
        data, filename, media_type = await _export_csv(filtered_rows, columns, tick_interval, normalized_data_type)
    elif format == "tex_table":
        data, filename, media_type = await _export_tex_table(
            rows, columns, flora_ids, herbivore_ids, tick_interval, normalized_data_type
        )
    elif format == "tex_tikz":
        data, filename, media_type = await _export_tex_tikz(
            filtered_rows,
            normalized_data_type,
            flora_names,
            herbivore_names,
            plant_species_id,
            herbivore_species_id,
            flora_ids,
            herbivore_ids,
            title,
            x_label,
            y_label,
            x_max,
            y_max,
        )
    elif format == "png":
        data, filename, media_type = await _export_png(
            filtered_rows,
            normalized_data_type,
            flora_names,
            herbivore_names,
            plant_species_id,
            herbivore_species_id,
            flora_ids,
            herbivore_ids,
            title,
            x_label,
            y_label,
            x_max,
            y_max,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format '{format}'. Use csv, tex_table, tex_tikz, or png.",
        )

    api_main.logger.info("Export (%s/%s): %d bytes", normalized_data_type, format, len(data))
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
