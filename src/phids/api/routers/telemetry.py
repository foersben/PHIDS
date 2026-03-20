"""Telemetry route partition for PHIDS analytical transport.

This module isolates the observation and export endpoints that expose telemetry beyond the core
simulation loop. The routes preserve the distinction between lightweight operator-facing telemetry
surfaces and heavier archival export surfaces. HTML fragments remain suitable for HTMX polling,
whereas CSV, NDJSON, TikZ, and PNG exports support downstream statistical and graphical analysis.
The extraction is intentionally conservative: `phids.api.main` continues to own the live
`SimulationLoop`, shared summary helpers, and template environment so that the refactor does not
perturb deterministic engine advancement or the biological semantics encoded in the telemetry rows.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

import phids.api.main as api_main
from phids.telemetry.export import (
    decimate_dataframe,
    export_bytes_csv,
    export_bytes_json,
    export_bytes_tex_table,
    filter_dataframe_columns,
    filter_telemetry_rows,
    generate_png_bytes,
    generate_tikz_str,
    telemetry_to_dataframe,
)

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


@router.get("/api/telemetry/chartjs-data", summary="Per-species time-series data for Chart.js")
async def telemetry_chartjs_data(since_tick: int | None = None) -> JSONResponse:
    """Return per-species population and energy time series for browser charts.

    Returns:
        JSONResponse: Chart.js-compatible labels, per-species identifiers, display names, and
        numeric series extracted from the live telemetry buffer.
    """
    if api_main._sim_loop is None:
        return JSONResponse({"labels": [], "flora_ids": [], "herbivore_ids": [], "series": {}})

    rows = api_main._sim_loop.telemetry._rows
    if since_tick is not None and rows:
        latest_tick = int(rows[-1].get("tick", -1))
        # When the simulation was reset, client-side since_tick can be ahead of
        # the current run; return full rows so chart state can re-synchronize.
        if latest_tick > since_tick:
            rows = [row for row in rows if int(row.get("tick", -1)) > since_tick]
    species = api_main._sim_loop.telemetry.get_species_ids()
    flora_ids = species["flora_ids"]
    herbivore_ids = species["herbivore_ids"]

    flora_names = {sp.species_id: sp.name for sp in api_main._sim_loop.config.flora_species}
    herbivore_names = {sp.species_id: sp.name for sp in api_main._sim_loop.config.herbivore_species}

    labels = [r["tick"] for r in rows]
    series: dict[str, list[float]] = {
        "flora_population": [_safe_float(r.get("flora_population", 0)) for r in rows],
        "herbivore_population": [_safe_float(r.get("herbivore_population", 0)) for r in rows],
        "total_flora_energy": [_safe_float(r.get("total_flora_energy", 0.0)) for r in rows],
    }
    for fid in flora_ids:
        series[f"plant_{fid}_pop"] = [
            _safe_float(r.get("plant_pop_by_species", {}).get(fid, 0)) for r in rows
        ]
        series[f"plant_{fid}_energy"] = [
            _safe_float(r.get("plant_energy_by_species", {}).get(fid, 0.0)) for r in rows
        ]
        series[f"defense_cost_{fid}"] = [
            _safe_float(r.get("defense_cost_by_species", {}).get(fid, 0.0)) for r in rows
        ]
    for hid in herbivore_ids:
        series[f"swarm_{hid}_pop"] = [
            _safe_float(r.get("swarm_pop_by_species", {}).get(hid, 0)) for r in rows
        ]

    return JSONResponse(
        {
            "labels": labels,
            "flora_ids": flora_ids,
            "herbivore_ids": herbivore_ids,
            "flora_names": {str(k): v for k, v in flora_names.items()},
            "herbivore_names": {str(k): v for k, v in herbivore_names.items()},
            "series": series,
        }
    )


@router.get(
    "/api/telemetry/table_preview", response_class=HTMLResponse, summary="Telemetry table preview"
)
async def telemetry_table_preview(
    request: Request,
    columns: str | None = None,
    flora_ids: str | None = None,
    herbivore_ids: str | None = None,
    tick_interval: int = 1,
    limit: int = 200,
) -> Response:
    """Render a bounded HTML preview of filtered telemetry rows.

    Args:
        request: FastAPI request object used by the template renderer.
        columns: Optional comma-delimited dataframe columns to retain.
        flora_ids: Optional comma-delimited flora species identifiers used for row filtering.
        herbivore_ids: Optional comma-delimited herbivore species identifiers used for row filtering.
        tick_interval: Positive decimation factor applied before preview rendering.
        limit: Maximum number of recent rows retained to prevent DOM overload.

    Returns:
        TemplateResponse: Rendered `partials/telemetry_table_preview.html` fragment.
    """
    if api_main._sim_loop is None:
        return api_main.templates.TemplateResponse(
            request,
            "partials/telemetry_table_preview.html",
            {"table_html": "", "empty_message": "No telemetry data available."},
        )

    rows = filter_telemetry_rows(
        api_main._sim_loop.telemetry._rows,
        flora_ids=flora_ids,
        herbivore_ids=herbivore_ids,
    )
    df = telemetry_to_dataframe(rows)
    df = filter_dataframe_columns(df, columns)
    df = decimate_dataframe(df, tick_interval)

    limit = max(1, min(limit, 1000))
    df = df.tail(limit)

    if df.empty:
        context = {"table_html": "", "empty_message": "No rows match current table filters."}
    else:
        table_html = df.to_html(
            index=False,
            classes="min-w-full text-[11px]",
            border=0,
            justify="left",
            float_format=lambda value: f"{value:.2f}",
        )
        context = {"table_html": table_html, "empty_message": ""}
    return api_main.templates.TemplateResponse(
        request,
        "partials/telemetry_table_preview.html",
        context,
    )


@router.get("/api/export/{data_type}", summary="Export telemetry data in academic formats")
async def export_telemetry_format(
    data_type: str,
    format: str = "csv",  # noqa: A002
    prey_species_id: int = 0,
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
        prey_species_id: Flora species identifier used on the phase-space x-axis.
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
                f"Unknown data_type '{data_type}'. Use timeseries, phasespace, defense_economy, biomass_stack, or metabolic."
            ),
        )

    if tick_interval < 1:
        raise HTTPException(status_code=400, detail="tick_interval must be >= 1")

    rows = api_main._sim_loop.telemetry._rows
    flora_names: dict[int, str] = {
        sp.species_id: sp.name for sp in api_main._sim_loop.config.flora_species
    }
    herbivore_names: dict[int, str] = {
        sp.species_id: sp.name for sp in api_main._sim_loop.config.herbivore_species
    }
    filtered_rows = filter_telemetry_rows(rows, flora_ids=flora_ids, herbivore_ids=herbivore_ids)

    if format == "csv":

        def _build_export_csv() -> bytes:
            df = telemetry_to_dataframe(filtered_rows)
            df = filter_dataframe_columns(df, columns)
            df = decimate_dataframe(df, tick_interval)
            return str(df.to_csv(index=False)).encode("utf-8")

        data = await run_in_threadpool(_build_export_csv)
        filename = f"phids_{normalized_data_type}.csv"
        media_type = "text/csv"
    elif format == "tex_table":

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
    elif format == "tex_tikz":
        try:

            def _build_export_tikz() -> str:
                return generate_tikz_str(
                    filtered_rows,
                    normalized_data_type,
                    flora_names=flora_names,
                    herbivore_names=herbivore_names,
                    prey_species_id=prey_species_id,
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
    elif format == "png":
        try:

            def _build_export_png() -> bytes:
                return generate_png_bytes(
                    filtered_rows,
                    normalized_data_type,
                    flora_names=flora_names,
                    herbivore_names=herbivore_names,
                    prey_species_id=prey_species_id,
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


@router.get("/api/telemetry", summary="Telemetry SVG chart partial")
async def telemetry_chart(request: Request) -> Response:
    """Render the HTMX-polled telemetry chart fragment.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/telemetry_chart.html` fragment together with current
        legend and summary context.
    """
    if api_main._sim_loop is None:
        svg = api_main._build_telemetry_svg(None)
        legend = False
        latest_metrics = None
        live_summary = None
    else:
        svg = api_main._build_telemetry_svg(api_main._sim_loop.telemetry.dataframe)
        legend = True
        latest_metrics = api_main._sim_loop.telemetry.get_latest_metrics()
        live_summary = api_main._build_live_summary()

    return api_main.templates.TemplateResponse(
        request,
        "partials/telemetry_chart.html",
        {
            "svg_content": svg,
            "legend": legend,
            "latest_metrics": latest_metrics,
            "live_summary": live_summary,
        },
    )
