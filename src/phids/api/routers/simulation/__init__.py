# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scenario and simulation control router for PHIDS.

This module groups the routes that transition validated configuration data into a live
`SimulationLoop` and then control that runtime through deterministic lifecycle operations. The
endpoints preserve the draft-versus-live boundary: draft editing occurs in separate builder routes,
while this surface performs scenario loading, single-loop execution control, wind mutation, and
serialization import/export. The computational objective is strict reproducibility of ecological
state trajectories, and the biological objective is controlled experimentation over trophic,
signaling, and metabolic dynamics without introducing ad hoc client-side state transitions.
"""

from __future__ import annotations

from fastapi import APIRouter

from phids.api.routers.simulation.execution import router as execution_router
from phids.api.routers.simulation.scenario import router as scenario_router

router = APIRouter()
router.include_router(scenario_router)
router.include_router(execution_router)
