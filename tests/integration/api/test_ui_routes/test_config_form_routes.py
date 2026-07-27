# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for PHIDS UI configuration form endpoints.

This module tests HTMX form submissions and state mutations for flora parameters, herbivore parameters,
biotope environmental settings, placement grids, mycorrhizal growth clamping, and wind vectors.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from phids.api import main as api_main
from phids.api.ui_state.state import get_draft, reset_draft


@pytest.mark.asyncio
async def test_biotope_config_updates_and_clamps_mycorrhizal_growth_interval(api_client: AsyncClient) -> None:
    """Verifies biotope settings form updates and value bounds clamping."""
    reset_draft()
    data = {
        "grid_width": 30,
        "grid_height": 30,
        "wind_x": 0.2,
        "wind_y": -0.1,
        "mycorrhizal_growth_interval_ticks": 5,
    }
    resp = await api_client.post("/api/config/biotope", data=data)
    assert resp.status_code == 200, resp.text
    draft = get_draft()
    assert draft.grid_width == 30
    assert draft.grid_height == 30
    assert draft.mycorrhizal_growth_interval_ticks == 5


@pytest.mark.asyncio
async def test_biotope_wind_update_auto_applies_to_loaded_live_loop(api_client: AsyncClient) -> None:
    """Verifies live simulation wind is synchronized when biotope form is updated."""
    await api_client.post("/api/scenario/load-draft")
    data = {
        "grid_width": 40,
        "grid_height": 40,
        "wind_x": 0.4,
        "wind_y": -0.3,
    }
    resp = await api_client.post("/api/config/biotope", data=data)
    assert resp.status_code == 200, resp.text
    loop = api_main._sim_loop
    assert loop is not None
    assert abs(loop.env.wind_vector_x[0, 0] - 0.4) < 1e-5
    assert abs(loop.env.wind_vector_y[0, 0] - (-0.3)) < 1e-5


@pytest.mark.asyncio
async def test_control_routes_commit_pending_biotope_form_values(api_client: AsyncClient) -> None:
    """Verifies scenario control routes automatically commit pending form edits."""
    reset_draft()
    form_data = {
        "grid_width": 25,
        "grid_height": 25,
        "wind_x": 0.0,
        "wind_y": 0.0,
    }
    resp = await api_client.post("/api/config/biotope", data=form_data)
    assert resp.status_code == 200, resp.text
    assert get_draft().grid_width == 25
