# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""HTML fragment endpoints for telemetry UI."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.presenters.diagnostics import build_live_summary
from phids.api.presenters.telemetry import build_telemetry_svg
from phids.telemetry.export.core import (
    decimate_dataframe,
    filter_dataframe_columns,
    filter_telemetry_rows,
    telemetry_to_dataframe,
)

router = APIRouter()


@router.get("/api/telemetry/table_preview", response_class=HTMLResponse, summary="Telemetry table preview")
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
        svg = build_telemetry_svg(None)
        legend = False
        latest_metrics = None
        live_summary = None
    else:
        svg = build_telemetry_svg(api_main._sim_loop.telemetry.dataframe)
        legend = True
        latest_metrics = api_main._sim_loop.telemetry.get_latest_metrics()
        live_summary = build_live_summary(api_main._sim_loop)

    from phids.api.ui_state.state import DraftState, get_draft

    draft: DraftState = get_draft()
    max_x: int = api_main._sim_loop.env.width if api_main._sim_loop is not None else draft.grid_width
    max_y: int = api_main._sim_loop.env.height if api_main._sim_loop is not None else draft.grid_height

    return api_main.templates.TemplateResponse(
        request,
        "partials/telemetry_chart.html",
        {
            "svg_content": svg,
            "legend": legend,
            "latest_metrics": latest_metrics,
            "live_summary": live_summary,
            "tick_value": api_main._sim_loop.tick if api_main._sim_loop is not None else 0,
            "max_x": max_x,
            "max_y": max_y,
        },
    )
