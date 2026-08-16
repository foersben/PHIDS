# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

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

from fastapi import APIRouter

from phids.api.routers.telemetry.chartjs import router as chartjs_router
from phids.api.routers.telemetry.exports import router as exports_router
from phids.api.routers.telemetry.html import router as html_router

router = APIRouter()
router.include_router(exports_router)
router.include_router(chartjs_router)
router.include_router(html_router)
