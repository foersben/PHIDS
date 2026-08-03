# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests verifying background task retention and pause/resume execution stability."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient

import phids.api.main as api_main
from phids.api.schemas.simulation import SimulationConfig


@pytest.mark.asyncio
async def test_api_simulation_pause_resume_task_deduplication(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify that pausing and resuming reuses the active background task instead of spawning duplicates."""
    config = config_builder(max_ticks=1000)
    load_resp = await api_client.post("/api/scenario/load", json=config.model_dump(mode="json"))
    assert load_resp.status_code == 200

    # Start simulation
    start_resp = await api_client.post("/api/simulation/start")
    assert start_resp.status_code == 200
    assert api_main._sim_task is not None
    initial_task = api_main._sim_task

    # Pause simulation
    pause_resp = await api_client.post("/api/simulation/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["message"] == "Simulation paused."

    # Resume simulation by calling start again
    resume_resp = await api_client.post("/api/simulation/start")
    assert resume_resp.status_code == 200

    # Task instance MUST be identical (no duplicate task created)
    assert api_main._sim_task is initial_task
    assert not initial_task.done()

    # Clean up simulation task
    reset_resp = await api_client.post("/api/simulation/reset")
    assert reset_resp.status_code == 200


@pytest.mark.asyncio
async def test_api_simulation_pause_terminated_simulation_returns_200(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify attempting to pause a terminated simulation returns HTTP 200 with status."""
    config = config_builder(max_ticks=1)
    load_resp = await api_client.post("/api/scenario/load", json=config.model_dump(mode="json"))
    assert load_resp.status_code == 200

    assert api_main._sim_loop is not None
    api_main._sim_loop.terminated = True
    api_main._sim_loop.termination_reason = "Test termination"

    pause_resp = await api_client.post("/api/simulation/pause")
    assert pause_resp.status_code == 200
    assert "paused" in pause_resp.text.lower() or "sim-status" in pause_resp.text
