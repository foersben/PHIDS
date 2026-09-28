# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""UI HTML routes for diagnostic logs, deficits, and system metrics."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.presenters.diagnostics import build_energy_deficit_swarms, build_live_summary
from phids.api.ui_state.state import get_draft
from phids.shared.logging_config import get_recent_logs

BIO_DB_PATH = Path("src/phids/analytics/bio_database.json")

router = APIRouter()


@router.get("/ui/diagnostics/model", response_class=HTMLResponse, summary="Diagnostics model tab")
async def ui_diagnostics_model(request: Request) -> Response:
    """Render live ecological counters and deficit diagnostics.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/diagnostics_model.html` fragment populated from live
        telemetry and draft metadata.
    """
    return api_main.templates.TemplateResponse(
        request,
        "partials/diagnostics_model.html",
        {
            "draft": get_draft(),
            "live_summary": build_live_summary(api_main._sim_loop),
            "latest_metrics": api_main._sim_loop.telemetry.get_latest_metrics()
            if api_main._sim_loop is not None
            else None,
            "energy_deficit_swarms": build_energy_deficit_swarms(api_main._sim_loop),
            "wind": {
                "vx": api_main._sim_loop.config.wind_x if api_main._sim_loop else get_draft().wind_x,
                "vy": api_main._sim_loop.config.wind_y if api_main._sim_loop else get_draft().wind_y,
            },
            "initial_population": sum(sp.population for sp in get_draft().initial_swarms),
            "initial_flora_count": len(get_draft().initial_plants),
        },
    )


@router.get("/ui/diagnostics/frontend", response_class=HTMLResponse, summary="Diagnostics frontend tab")
async def ui_diagnostics_frontend(request: Request) -> Response:
    """Render the browser-observation diagnostics shell.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/diagnostics_frontend.html` fragment.
    """
    return api_main.templates.TemplateResponse(request, "partials/diagnostics_frontend.html")


@router.get("/ui/diagnostics/backend", response_class=HTMLResponse, summary="Diagnostics backend tab")
async def ui_diagnostics_backend(request: Request) -> Response:
    """Render recent structured backend logs for operator inspection.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/diagnostics_backend.html` fragment with bounded recent
        log context.
    """
    return api_main.templates.TemplateResponse(
        request,
        "partials/diagnostics_backend.html",
        {"recent_logs": get_recent_logs(limit=120)},
    )
