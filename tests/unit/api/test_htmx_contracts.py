# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""HTMX & Web API Contract Integrity Unit Suite.

Validates that HTMX partial response endpoints emit required HTTP headers
(e.g., HX-Refresh, HX-Trigger) and include mandatory target DOM element IDs
required for live UI swaps (`#sim-status`, `#main-workspace`, `#status-badge`).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ui_status_badge_htmx_contract(api_client: AsyncClient) -> None:
    """Verify UI status badge partial includes valid HTMX target element or badge markup."""
    response = await api_client.get("/api/ui/status-badge", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "sim-status" in response.text or "badge" in response.text or "status" in response.text


@pytest.mark.asyncio
async def test_scenario_load_draft_htmx_contract(api_client: AsyncClient) -> None:
    """Verify loading draft returns 204 and HX-Trigger header for event-driven UI updates."""
    response = await api_client.post("/api/scenario/load-draft", headers={"HX-Request": "true"})
    assert response.status_code == 204
    assert "updateStatusBadge" in response.headers.get("HX-Trigger", "")
    assert "updateMainActionBtn" in response.headers.get("HX-Trigger", "")


@pytest.mark.asyncio
async def test_simulation_pause_htmx_contract(api_client: AsyncClient) -> None:
    """Verify pause simulation returns 204 and HX-Trigger header after loading a draft scenario."""
    # 1. Load draft scenario first
    load_resp = await api_client.post("/api/scenario/load-draft", headers={"HX-Request": "true"})
    assert load_resp.status_code == 204

    # 2. Pause simulation
    pause_resp = await api_client.post("/api/simulation/pause", headers={"HX-Request": "true"})
    assert pause_resp.status_code == 204
    assert "updateStatusBadge" in pause_resp.headers.get("HX-Trigger", "")
    assert "updateMainActionBtn" in pause_resp.headers.get("HX-Trigger", "")


@pytest.mark.asyncio
async def test_database_rebuild_htmx_refresh_header(api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify database rebuild endpoint returns HX-Refresh header on completion."""
    import asyncio

    class MockProcess:
        returncode = 0

        async def communicate(self):
            return b"stdout", b"stderr"

    async def mock_exec(*_args, **_kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_exec)

    response = await api_client.post("/api/database/rebuild", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert response.headers.get("HX-Refresh") == "true"
