# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""UI HTML routes for Bio-Database management and persistence."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.analytics.bio_database import BioDatabaseModel  # noqa: TC001

BIO_DB_PATH = Path("src/phids/analytics/bio_database.json")

router = APIRouter()


@router.get("/ui/database", response_class=HTMLResponse, summary="Bio-Database Catalog partial")
async def ui_database(request: Request) -> Response:
    """Render the Bio-Database Catalog for browsing and managing species.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `database_dashboard.html` fragment containing database items.
    """
    import json

    db_path = BIO_DB_PATH
    try:
        with open(db_path, encoding="utf-8") as f:
            db_data = json.load(f)
    except FileNotFoundError:
        db_data = {"flora": {}, "herbivores": {}, "substances": {}}

    return api_main.templates.TemplateResponse(
        request,
        "database_dashboard.html",
        {
            "flora": db_data.get("flora", {}),
            "herbivores": db_data.get("herbivores", {}),
            "substances": db_data.get("substances", {}),
        },
    )


@router.post("/api/database/save", summary="Save Bio-Database")
async def api_database_save(payload: BioDatabaseModel) -> Response:
    """Save the current bio-database payload."""
    import json

    db_path = BIO_DB_PATH

    try:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(payload.model_dump(), f, indent=2)

        return Response(status_code=200)
    except Exception as e:
        return Response(content=str(e), status_code=400)


@router.post("/api/database/rebuild", summary="Rebuild Bio-Database via ETL pipeline")
async def api_database_rebuild() -> Response:
    """Run the ETL pipeline.

    Returns:
        Response: Success or failure message.
    """
    import asyncio

    try:
        process = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "python",
            "src/data_pipeline/run_all.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await process.communicate()
        if process.returncode != 0:
            return Response(content=f"ETL Failed:\\n{stderr.decode('utf-8')}", status_code=500)

        # We trigger an HTMX refresh of the panel by returning a client-side redirect header
        # or we can just return a success message
        return Response(content="ETL Pipeline completed successfully.", status_code=200, headers={"HX-Refresh": "true"})
    except Exception as e:
        return Response(content=str(e), status_code=500)
