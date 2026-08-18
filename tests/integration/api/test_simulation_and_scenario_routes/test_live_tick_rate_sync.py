# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for live tick rate updates and biotope configuration synchronization."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from phids.api.main import app
from phids.api.ui_state.state import get_draft


@pytest.mark.asyncio
async def test_live_tick_rate_update_endpoint() -> None:
    """Verify PUT /api/simulation/tick-rate updates draft and live loop tick speed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Load draft into simulation
        load_resp = await client.post("/api/scenario/load-draft")
        assert load_resp.status_code == 204

        # Update tick rate to 1.0 Hz
        resp = await client.put("/api/simulation/tick-rate", data={"tick_rate_hz": 1.0})
        assert resp.status_code == 200
        assert get_draft().tick_rate_hz == 1.0

        # Update tick rate via biotope config form
        biotope_resp = await client.post(
            "/api/config/biotope",
            data={
                "grid_width": 40,
                "grid_height": 40,
                "max_ticks": 1000,
                "tick_rate_hz": 2.5,
                "wind_x": 0.0,
                "wind_y": 0.0,
                "num_signals": 4,
                "num_toxins": 4,
            },
        )
        assert biotope_resp.status_code == 200
        assert get_draft().tick_rate_hz == 2.5
