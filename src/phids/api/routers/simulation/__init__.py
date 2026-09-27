# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scenario and simulation control router for PHIDS.

This module groups the routes that transition validated configuration data into a live
`SimulationLoop` and then control that runtime through deterministic lifecycle operations.
"""

from fastapi import APIRouter

from .controls import router as controls_router
from .scenario import router as scenario_router

router = APIRouter()
router.include_router(controls_router)
router.include_router(scenario_router)

__all__ = ["router"]
