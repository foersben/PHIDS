# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""UI HTML route partition for the PHIDS control surface.

This module contains the server-rendered HTML endpoints that drive the HTMX and Jinja control
centre. The extraction isolates view assembly from the application bootstrap logic while keeping
`phids.api.main` as the canonical owner of live runtime state, shared helper functions, and
WebSocket orchestration. The resulting boundary is intentionally conservative: the router renders
partials and page shells, but it does not alter the draft-versus-live transition semantics that are
central to deterministic ecological experimentation. By retaining server-side rendering, the module
continues to expose biologically meaningful state such as telemetry summaries, metabolic deficit
watchlists, and mycorrhizal placement previews without moving those calculations into brittle
browser-side replicas.
"""

from __future__ import annotations

from fastapi import APIRouter

from .batch import router as batch_router
from .config import router as config_router
from .core import router as core_router
from .database import router as database_router
from .diagnostics import router as diagnostics_router

router = APIRouter()
router.include_router(batch_router)
router.include_router(config_router)
router.include_router(core_router)
router.include_router(database_router)
router.include_router(diagnostics_router)
