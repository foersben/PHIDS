# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration checks for scenario import/export and draft loading HTTP routes.

This module validates scenario JSON import, export serialization, trigger materialization,
background task cancellation on draft reload, and malformed payload rejection.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

import phids.api.main as api_main
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.triggers import (
    HerbivoreAttackInitiator,
    SynthesizeSubstanceAction,
    TriggerConditionSchema,
)
from phids.api.ui_state.state import DraftState, reset_draft, set_draft

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_scenario_import_export_endpoints_roundtrip(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify scenario import accepts valid JSON and export returns expected core fields."""
    config = config_builder()
    import_resp = await api_client.post(
        "/api/scenario/import",
        files={
            "file": (
                "scenario.json",
                json.dumps(config.model_dump(mode="json")),
                "application/json",
            )
        },
    )
    assert import_resp.status_code == 200, import_resp.text

    export_resp = await api_client.get("/api/scenario/export")
    assert export_resp.status_code == 200, export_resp.text
    exported = json.loads(export_resp.text)
    assert exported["grid_width"] == config.grid_width
    assert exported["herbivore_species"][0]["name"] == "herbivore"


@pytest.mark.asyncio
async def test_scenario_import_materializes_trigger_rules_and_substances(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify scenario import reconstructs draft trigger rules and substance definitions from schema triggers."""
    config = config_builder()
    config.flora_species[0] = config.flora_species[0].model_copy(
        update={
            "triggers": [
                TriggerConditionSchema(
                    initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=2),
                    action=SynthesizeSubstanceAction(
                        substance_id=1,
                        synthesis_duration=3,
                        is_toxin=False,
                    ),
                )
            ]
        }
    )
    config.num_signals = 2

    import_resp = await api_client.post(
        "/api/scenario/import",
        files={
            "file": (
                "triggered.json",
                json.dumps(config.model_dump(mode="json")),
                "application/json",
            )
        },
    )

    assert import_resp.status_code == 200, import_resp.text

    export_resp = await api_client.get("/api/scenario/export")
    assert export_resp.status_code == 200, export_resp.text
    exported = json.loads(export_resp.text)
    assert len(exported["flora_species"][0]["triggers"]) == 1
    assert exported["flora_species"][0]["triggers"][0]["action"]["substance_id"] == 1


@pytest.mark.asyncio
async def test_scenario_export_and_load_draft_fail_for_invalid_draft(
    api_client: AsyncClient,
) -> None:
    """Verify export/load-draft fail with deterministic 400 responses when draft cannot build config."""
    set_draft(DraftState(flora_species=[], herbivore_species=[]))

    export_resp = await api_client.get("/api/scenario/export")
    assert export_resp.status_code == 400, export_resp.text

    load_resp = await api_client.post("/api/scenario/load-draft")
    assert load_resp.status_code == 400, load_resp.text
    reset_draft()


@pytest.mark.asyncio
async def test_scenario_load_draft_cancels_running_background_task(
    api_client: AsyncClient,
    config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify loading draft while a simulation task is running cancels it and returns fresh status HTML."""
    load_resp = await api_client.post("/api/scenario/load", json=config_builder(max_ticks=200).model_dump(mode="json"))
    assert load_resp.status_code == 200, load_resp.text

    start_resp = await api_client.post("/api/simulation/start")
    assert start_resp.status_code == 200, start_resp.text
    assert api_main._sim_task is not None
    assert not api_main._sim_task.done()

    draft_load_resp = await api_client.post(
        "/api/scenario/load-draft",
        headers={"HX-Request": "true"},
    )

    assert draft_load_resp.status_code == 200, draft_load_resp.text
    assert "sim-status" in draft_load_resp.text
    assert api_main._sim_task is None
    assert api_main._sim_loop is not None


@pytest.mark.asyncio
async def test_scenario_import_rejects_invalid_json(api_client: AsyncClient) -> None:
    """Verify scenario import returns 422 for malformed JSON uploads."""
    resp = await api_client.post(
        "/api/scenario/import",
        files={"file": ("broken.json", "{not valid json", "application/json")},
    )

    assert resp.status_code == 422, resp.text
