# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Core UI HTML routes including root and main dashboard surfaces."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.ui_state.state import DraftState, get_draft

BIO_DB_PATH = Path("src/phids/analytics/bio_database.json")

router = APIRouter()


@router.get("/", response_class=HTMLResponse, summary="Main UI")
async def root(request: Request) -> Response:
    """Render the PHIDS control-centre root page.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `index.html` page shell seeded with the current draft scenario
        name.
    """
    draft: DraftState = get_draft()
    max_x: int = api_main._sim_loop.env.width if api_main._sim_loop is not None else draft.grid_width
    max_y: int = api_main._sim_loop.env.height if api_main._sim_loop is not None else draft.grid_height
    return api_main.templates.TemplateResponse(
        request,
        "index.html",
        {
            "scenario_name": draft.scenario_name,
            "default_tick_rate_hz": draft.tick_rate_hz,
            "max_x": max_x,
            "max_y": max_y,
        },
    )


@router.get("/ui/dashboard", response_class=HTMLResponse, summary="Dashboard partial")
async def ui_dashboard(request: Request) -> Response:
    """Render the live dashboard partial.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/dashboard.html` fragment.
    """
    draft: DraftState = get_draft()
    max_x: int = api_main._sim_loop.env.width if api_main._sim_loop is not None else draft.grid_width
    max_y: int = api_main._sim_loop.env.height if api_main._sim_loop is not None else draft.grid_height
    return api_main.templates.TemplateResponse(
        request,
        "partials/dashboard.html",
        {
            "max_x": max_x,
            "max_y": max_y,
        },
    )
