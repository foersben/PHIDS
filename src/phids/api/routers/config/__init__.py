# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unified configuration router for PHIDS draft-state mutation routes."""

from __future__ import annotations

from fastapi import APIRouter

from phids.api.routers.config.biotope import router as biotope_router
from phids.api.routers.config.flora import router as flora_router
from phids.api.routers.config.herbivores import router as herbivores_router
from phids.api.routers.config.matrices import router as matrices_router
from phids.api.routers.config.placements import router as placements_router
from phids.api.routers.config.substances import router as substances_router
from phids.api.routers.config.trigger_rules import router as trigger_rules_router

router = APIRouter()

router.include_router(biotope_router)
router.include_router(flora_router)
router.include_router(herbivores_router)
router.include_router(substances_router)
router.include_router(matrices_router)
router.include_router(trigger_rules_router)
router.include_router(placements_router)
