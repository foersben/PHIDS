# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""UI HTML routes for batch runner dashboards."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main

BIO_DB_PATH = Path("src/phids/analytics/bio_database.json")

router = APIRouter()


@router.get("/ui/batch", response_class=HTMLResponse, summary="Batch runner dashboard")
async def ui_batch_dashboard(request: Request) -> Response:
    """Render the Monte Carlo batch runner dashboard shell.

    Args:
        request: FastAPI request object used by Jinja to resolve URL and template context state.

    Returns:
        TemplateResponse: Rendered `batch_dashboard.html` surface for batch orchestration and
        aggregate inspection.
    """
    return api_main.templates.TemplateResponse(request, "batch_dashboard.html")
