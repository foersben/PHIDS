# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""HTMX & Web API Contract Integrity Unit Suite.

Validates that HTMX partial response endpoints emit required HTTP headers
(e.g., HX-Refresh, HX-Trigger) and include mandatory target DOM element IDs
required for live UI swaps (`#sim-status`, `#main-workspace`, `#status-badge`).
"""

from __future__ import annotations

# ruff: noqa: TC002
import pytest
from conftest import assert_valid_htmx_target
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ui_status_badge_htmx_contract(api_client: AsyncClient) -> None:
    """Verify UI status badge partial includes valid HTMX target element or badge markup."""
    response = await api_client.get("/api/ui/status-badge", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "sim-status" in response.text or "badge" in response.text or "status" in response.text


@pytest.mark.asyncio
async def test_scenario_load_draft_htmx_contract(api_client: AsyncClient) -> None:
    """Verify loading draft returns sim-status target element for HTMX swap."""
    response = await api_client.post("/api/scenario/load-draft", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert_valid_htmx_target(response.text, "sim-status")


@pytest.mark.asyncio
async def test_simulation_pause_htmx_contract(api_client: AsyncClient) -> None:
    """Verify pause simulation returns sim-status target after loading a draft scenario."""
    # 1. Load draft scenario first
    load_resp = await api_client.post("/api/scenario/load-draft", headers={"HX-Request": "true"})
    assert load_resp.status_code == 200

    # 2. Pause simulation
    pause_resp = await api_client.post("/api/simulation/pause", headers={"HX-Request": "true"})
    assert pause_resp.status_code == 200
    assert_valid_htmx_target(pause_resp.text, "sim-status")


@pytest.mark.asyncio
async def test_database_rebuild_htmx_refresh_header(api_client: AsyncClient, mocker) -> None:
    """Verify database rebuild endpoint returns HX-Refresh header on completion."""

    class MockProcess:
        returncode = 0

        async def communicate(self):
            return b"stdout", b"stderr"

    mocker.patch("asyncio.create_subprocess_exec", return_value=MockProcess())

    response = await api_client.post("/api/database/rebuild", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.headers.get("HX-Refresh") == "true"
