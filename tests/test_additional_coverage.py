"""Experimental validation suite for test additional coverage.

This module defines hypothesis-driven checks for deterministic ecosystem behavior, API constraints, and simulation invariants. The tests map computational rules to biological interpretations, including metabolic attrition, trigger-gated signaling, and O(1) spatial locality assumptions, to ensure that implementation details remain aligned with the PHIDS scientific model.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from httpx import ASGITransport, AsyncClient

import phids.api.main as api_main
from phids.api.schemas import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    InitialPlantPlacement,
    InitialSwarmPlacement,
    HerbivoreSpeciesParams,
    SimulationConfig,
)
from phids.engine.components.plant import PlantComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.core.flow_field import apply_camouflage, compute_flow_field
from phids.engine.systems.lifecycle import _attempt_reproduction, run_lifecycle
from phids.io.replay import ReplayBuffer
from phids.io.scenario import load_scenario_from_dict, load_scenario_from_json, scenario_to_json
from phids.shared.logging_config import configure_logging, get_simulation_debug_interval
from phids.telemetry.export import export_bytes_csv, export_bytes_json, export_csv, export_json


@pytest.fixture(autouse=True)
async def _reset_sim_state() -> AsyncGenerator[None, None]:
    task = api_main._sim_task
    if task is not None and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    api_main._sim_task = None
    api_main._sim_loop = None
    yield
    task = api_main._sim_task
    if task is not None and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    api_main._sim_task = None
    api_main._sim_loop = None


@pytest.fixture
def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=api_main.app), base_url="http://test")


def _config(max_ticks: int = 5) -> SimulationConfig:
    return SimulationConfig(
        grid_width=8,
        grid_height=8,
        max_ticks=max_ticks,
        tick_rate_hz=20.0,
        num_signals=2,
        num_toxins=2,
        wind_x=0.0,
        wind_y=0.0,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="grass",
                base_energy=10.0,
                max_energy=20.0,
                growth_rate=5.0,
                survival_threshold=1.0,
                reproduction_interval=2,
                seed_min_dist=1.0,
                seed_max_dist=2.0,
                seed_energy_cost=2.0,
                triggers=[],
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="herbivore",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=2, y=2, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=3.0)],
    )


@pytest.mark.asyncio
async def test_api_control_endpoints_cover_main_branches(_client: AsyncClient) -> None:
    """Validates the api control endpoints cover main branches invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        _client: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    async with _client as client:
        root_resp = await client.get("/")
        assert "⏭ Step" in root_resp.text
        assert "↺ Reset" in root_resp.text

        status_resp = await client.get("/api/simulation/status")
        assert status_resp.status_code == 400

        config = _config()
        load_resp = await client.post("/api/scenario/load", json=config.model_dump(mode="json"))
        assert load_resp.status_code == 200
        assert load_resp.json()["message"] == "Scenario loaded."

        htmx_start_resp = await client.post(
            "/api/simulation/start",
            headers={"HX-Request": "true"},
        )
        assert htmx_start_resp.status_code == 200
        assert "sim-status" in htmx_start_resp.text

        reset_loaded_resp = await client.post("/api/simulation/reset")
        assert reset_loaded_resp.status_code == 200
        assert reset_loaded_resp.json()["tick"] == 0

        start_resp = await client.post("/api/simulation/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["message"] == "Simulation started."

        reload_resp = await client.post("/api/scenario/load", json=config.model_dump(mode="json"))
        assert reload_resp.status_code == 200

        running_resp = await client.post("/api/simulation/start")
        assert running_resp.status_code == 200
        assert running_resp.json()["message"] == "Simulation started."

        api_main._sim_loop.start()
        already_running_resp = await client.post("/api/simulation/start")
        assert already_running_resp.status_code == 200
        assert already_running_resp.json()["message"] == "Simulation already running."

        pause_resp = await client.post("/api/simulation/pause")
        assert pause_resp.status_code == 200
        assert pause_resp.json()["message"] == "Simulation paused."

        status_ok = await client.get("/api/simulation/status")
        assert status_ok.status_code == 200
        assert status_ok.json()["paused"] is True

        step_resp = await client.post("/api/simulation/step")
        assert step_resp.status_code == 200
        assert step_resp.json()["tick"] >= 1

        reset_resp = await client.post("/api/simulation/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json()["tick"] == 0

        post_reset_status = await client.get("/api/simulation/status")
        assert post_reset_status.status_code == 200
        assert post_reset_status.json()["tick"] == 0

        wind_resp = await client.put("/api/simulation/wind", json={"wind_x": 1.5, "wind_y": -0.5})
        assert wind_resp.status_code == 200
        assert wind_resp.json()["wind_x"] == pytest.approx(1.5)

        assert api_main._sim_loop is not None
        api_main._sim_loop.telemetry.record(api_main._sim_loop.world, tick=0)
        csv_resp = await client.get("/api/telemetry/export/csv")
        json_resp = await client.get("/api/telemetry/export/json")
        assert csv_resp.status_code == 200
        assert "tick" in csv_resp.text
        assert json_resp.status_code == 200
        assert '"tick":0' in json_resp.text.replace(" ", "")

        api_main._sim_loop.terminated = True
        api_main._sim_loop.running = False
        api_main._sim_loop.termination_reason = "manual test"
        terminated_resp = await client.post("/api/simulation/start")
        assert terminated_resp.status_code == 400


@pytest.mark.asyncio
async def test_http_middleware_logs_ui_and_api_requests(
    _client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Validates the http middleware logs ui and api requests invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        _client: Input value used to parameterize deterministic behavior for this callable.
        caplog: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    with caplog.at_level(logging.WARNING):
        async with _client as client:
            root_resp = await client.get("/")
            missing_resp = await client.get("/api/simulation/status")

    assert root_resp.status_code == 200
    assert missing_resp.status_code == 400
    assert "Simulation access requested before a scenario was loaded" in caplog.text
    assert "HTTP GET /api/simulation/status -> 400" in caplog.text


@pytest.mark.asyncio
async def test_scenario_import_export_endpoints_roundtrip(_client: AsyncClient) -> None:
    """Validates the scenario import export endpoints roundtrip invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        _client: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    async with _client as client:
        config = _config()
        import_resp = await client.post(
            "/api/scenario/import",
            files={
                "file": (
                    "scenario.json",
                    json.dumps(config.model_dump(mode="json")),
                    "application/json",
                )
            },
        )
        assert import_resp.status_code == 200

        export_resp = await client.get("/api/scenario/export")
        assert export_resp.status_code == 200
        exported = json.loads(export_resp.text)
        assert exported["grid_width"] == config.grid_width
        assert exported["herbivore_species"][0]["name"] == "herbivore"


@pytest.mark.asyncio
async def test_scenario_import_rejects_invalid_json(_client: AsyncClient) -> None:
    """Validates the scenario import rejects invalid json invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        _client: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    async with _client as client:
        resp = await client.post(
            "/api/scenario/import",
            files={"file": ("broken.json", "{not valid json", "application/json")},
        )
    assert resp.status_code == 422


def test_scenario_helpers_roundtrip_json_file(tmp_path: Path) -> None:
    """Validates the scenario helpers roundtrip json file invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        tmp_path: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    config = _config()
    data = config.model_dump(mode="json")

    loaded_from_dict = load_scenario_from_dict(data)
    assert loaded_from_dict.grid_width == config.grid_width

    out_path = tmp_path / "scenario.json"
    text = scenario_to_json(config, out_path)
    assert out_path.read_text(encoding="utf-8") == text

    loaded_from_file = load_scenario_from_json(out_path)
    assert loaded_from_file.model_dump(mode="json") == config.model_dump(mode="json")


def test_replay_buffer_save_load_and_truncated_file_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Validates the replay buffer save load and truncated file warning invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        tmp_path: Input value used to parameterize deterministic behavior for this callable.
        caplog: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    replay = ReplayBuffer()
    replay.append({"tick": 0, "value": 1})
    replay.append({"tick": 1, "value": 2})

    path = tmp_path / "replay.bin"
    replay.save(path)
    loaded = ReplayBuffer.load(path)
    assert len(loaded) == 2
    assert loaded.get_frame(1)["value"] == 2

    broken_path = tmp_path / "broken_replay.bin"
    broken_path.write_bytes((10).to_bytes(4, "little") + b"123")
    with caplog.at_level(logging.WARNING, logger="phids.io.replay"):
        truncated = ReplayBuffer.load(broken_path)
    assert len(truncated) == 0
    assert "ended mid-frame" in caplog.text


def test_telemetry_export_helpers_write_files_and_bytes(tmp_path: Path) -> None:
    """Validates the telemetry export helpers write files and bytes invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        tmp_path: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    frame = pl.DataFrame({"tick": [0, 1], "flora_population": [2, 3]})

    csv_path = tmp_path / "telemetry.csv"
    json_path = tmp_path / "telemetry.ndjson"
    export_csv(frame, csv_path)
    export_json(frame, json_path)

    assert "tick" in csv_path.read_text(encoding="utf-8")
    assert '"tick":0' in json_path.read_text(encoding="utf-8").replace(" ", "")
    assert export_bytes_csv(frame).startswith(b"tick")
    assert b'"tick":0' in export_bytes_json(frame).replace(b" ", b"")


def test_flow_field_generation_and_camouflage() -> None:
    """Validates the flow field generation and camouflage invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    plant_energy = np.array([[0.0, 0.0], [10.0, 0.0]], dtype=np.float64)
    toxin_layers = np.zeros((1, 2, 2), dtype=np.float64)
    toxin_layers[0, 0, 1] = 2.0

    flow = compute_flow_field(plant_energy, toxin_layers, width=2, height=2)
    assert flow.shape == (2, 2)
    assert flow[1, 0] > flow[0, 1]

    before = flow[1, 0]
    apply_camouflage(flow, 1, 0, 0.25)
    assert flow[1, 0] == pytest.approx(before * 0.25)


def test_configure_logging_supports_invalid_env_and_file_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates the configure logging supports invalid env and file output invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        tmp_path: Input value used to parameterize deterministic behavior for this callable.
        monkeypatch: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    log_path = tmp_path / "phids.log"
    monkeypatch.setenv("PHIDS_LOG_LEVEL", "not-a-level")
    monkeypatch.setenv("PHIDS_LOG_FILE_LEVEL", "still-invalid")
    monkeypatch.setenv("PHIDS_LOG_FILE", str(log_path))
    monkeypatch.setenv("PHIDS_LOG_SIM_DEBUG_INTERVAL", "0")

    configure_logging(force=True)
    logger = logging.getLogger("phids.test")
    logger.info("file logging smoke test")

    for handler in logging.getLogger().handlers:
        flush = getattr(handler, "flush", None)
        if callable(flush):
            flush()

    assert logging.getLogger("phids").getEffectiveLevel() == logging.INFO
    assert get_simulation_debug_interval() == 50
    assert log_path.exists()


def test_attempt_reproduction_handles_success_and_blocking_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates the attempt reproduction handles success and blocking cases invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        monkeypatch: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    params = _config().flora_species[0]
    flora_params = {0: params}
    env = GridEnvironment(width=5, height=5, num_signals=1, num_toxins=1)

    success_world = ECSWorld()
    parent_entity = success_world.create_entity()
    parent = PlantComponent(
        entity_id=parent_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    parent.last_reproduction_tick = -10
    success_world.add_component(parent_entity.entity_id, parent)
    success_world.register_position(parent_entity.entity_id, 2, 2)

    values = iter([0.0, 1.0])
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.uniform", lambda a, b: next(values))
    offspring = _attempt_reproduction(parent, 5, success_world, env, flora_params)
    assert len(offspring) == 1
    assert offspring[0].x == 3
    assert offspring[0].y == 2
    assert offspring[0].last_reproduction_tick == 5

    blocked_world = ECSWorld()
    blocked_parent_entity = blocked_world.create_entity()
    blocked_parent = PlantComponent(
        entity_id=blocked_parent_entity.entity_id,
        species_id=0,
        x=2,
        y=2,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    blocked_parent.last_reproduction_tick = -10
    blocked_world.add_component(blocked_parent_entity.entity_id, blocked_parent)
    blocked_world.register_position(blocked_parent_entity.entity_id, 2, 2)

    occupant_entity = blocked_world.create_entity()
    occupant = PlantComponent(
        entity_id=occupant_entity.entity_id,
        species_id=0,
        x=3,
        y=2,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    blocked_world.add_component(occupant_entity.entity_id, occupant)
    blocked_world.register_position(occupant_entity.entity_id, 3, 2)

    values = iter([0.0, 1.0])
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.uniform", lambda a, b: next(values))
    blocked = _attempt_reproduction(blocked_parent, 5, blocked_world, env, flora_params)
    assert blocked == []
    assert blocked_parent.energy == pytest.approx(10.0)

    low_energy_parent = PlantComponent(
        entity_id=99,
        species_id=0,
        x=0,
        y=0,
        energy=1.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    assert _attempt_reproduction(low_energy_parent, 5, blocked_world, env, flora_params) == []

    threshold_parent = PlantComponent(
        entity_id=100,
        species_id=0,
        x=0,
        y=0,
        energy=2.5,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    threshold_parent.last_reproduction_tick = -10
    assert _attempt_reproduction(threshold_parent, 5, blocked_world, env, flora_params) == []
    assert threshold_parent.energy == pytest.approx(2.5)


def test_newborn_reproduction_respects_cooldown_and_energy_constraints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates the newborn reproduction respects cooldown and energy constraints invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Args:
        monkeypatch: Input value used to parameterize deterministic behavior for this callable.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    params = _config().flora_species[0]
    params.reproduction_interval = 3
    params.seed_energy_cost = 4.0
    params.seed_min_dist = 1.0
    params.seed_max_dist = 1.0
    flora_params = {0: params}

    env = GridEnvironment(width=7, height=7, num_signals=1, num_toxins=1)
    world = ECSWorld()

    parent_entity = world.create_entity()
    parent = PlantComponent(
        entity_id=parent_entity.entity_id,
        species_id=0,
        x=2,
        y=3,
        energy=20.0,
        max_energy=40.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=params.reproduction_interval,
        seed_min_dist=params.seed_min_dist,
        seed_max_dist=params.seed_max_dist,
        seed_energy_cost=params.seed_energy_cost,
    )
    parent.last_reproduction_tick = -100
    world.add_component(parent_entity.entity_id, parent)
    world.register_position(parent_entity.entity_id, parent.x, parent.y)

    # First call spawns the newborn; second successful call (later) also needs angle+distance.
    values = iter([0.0, 1.0, 0.0, 1.0])
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.uniform", lambda a, b: next(values))

    birth_tick = 10
    newborn_list = _attempt_reproduction(parent, birth_tick, world, env, flora_params)
    assert len(newborn_list) == 1
    newborn = newborn_list[0]
    assert newborn.last_reproduction_tick == birth_tick

    # Cooldown Constraint: before birth_tick + interval, reproduction is always blocked.
    for attempt_tick in range(birth_tick, birth_tick + newborn.reproduction_interval):
        newborn.energy = 100.0
        assert _attempt_reproduction(newborn, attempt_tick, world, env, flora_params) == []

    boundary_tick = birth_tick + newborn.reproduction_interval

    # Energy Constraint: at boundary tick, insufficient energy still blocks reproduction.
    newborn.energy = newborn.seed_energy_cost - 0.1
    assert _attempt_reproduction(newborn, boundary_tick, world, env, flora_params) == []

    # Success State: at boundary tick, sufficient energy + empty target allows spawning.
    newborn.energy = newborn.seed_energy_cost + 5.0
    before_entities = len(list(world.query(PlantComponent)))
    offspring = _attempt_reproduction(newborn, boundary_tick, world, env, flora_params)
    after_entities = len(list(world.query(PlantComponent)))

    assert len(offspring) == 1
    assert after_entities == before_entities + 1


def test_attempt_reproduction_applies_downwind_bias_when_wind_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that anemochorous seed placement shifts downwind under non-zero local wind."""
    params = _config().flora_species[0]
    params.seed_min_dist = 1.0
    params.seed_max_dist = 1.0
    params.seed_drop_height = 2.0
    params.seed_terminal_velocity = 0.5
    flora_params = {0: params}

    env = GridEnvironment(width=12, height=8, num_signals=1, num_toxins=1)
    env.set_uniform_wind(1.2, 0.0)
    world = ECSWorld()
    parent_entity = world.create_entity()
    parent = PlantComponent(
        entity_id=parent_entity.entity_id,
        species_id=0,
        x=3,
        y=3,
        energy=20.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=1,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
        seed_drop_height=params.seed_drop_height,
        seed_terminal_velocity=params.seed_terminal_velocity,
    )
    parent.last_reproduction_tick = -10
    world.add_component(parent_entity.entity_id, parent)
    world.register_position(parent_entity.entity_id, parent.x, parent.y)

    # Base radial launch: +1 on x-axis. Turbulent terms are deterministic via patched gauss.
    values = iter([0.0, 1.0])
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.uniform", lambda a, b: next(values))
    monkeypatch.setattr("phids.engine.systems.lifecycle.random.gauss", lambda mu, sigma: mu)

    offspring = _attempt_reproduction(parent, 5, world, env, flora_params)
    assert len(offspring) == 1
    assert offspring[0].x >= 8
    assert offspring[0].y == 3


def test_run_lifecycle_culls_dead_plants_and_prunes_missing_links() -> None:
    """Validates the run lifecycle culls dead plants and prunes missing links invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    params = {0: _config().flora_species[0]}

    alive_entity = world.create_entity()
    alive_plant = PlantComponent(
        entity_id=alive_entity.entity_id,
        species_id=0,
        x=1,
        y=1,
        energy=5.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=0.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    alive_plant.mycorrhizal_connections.add(999)
    world.add_component(alive_entity.entity_id, alive_plant)
    world.register_position(alive_entity.entity_id, 1, 1)

    dead_entity = world.create_entity()
    dead_plant = PlantComponent(
        entity_id=dead_entity.entity_id,
        species_id=0,
        x=2,
        y=1,
        energy=0.5,
        max_energy=20.0,
        base_energy=0.5,
        growth_rate=0.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=2.0,
    )
    world.add_component(dead_entity.entity_id, dead_plant)
    world.register_position(dead_entity.entity_id, 2, 1)

    run_lifecycle(
        world,
        env,
        tick=1,
        flora_species_params=params,
        mycorrhizal_connection_cost=10.0,
        mycorrhizal_inter_species=False,
    )

    assert world.has_entity(alive_entity.entity_id) is True
    assert world.has_entity(dead_entity.entity_id) is False
    assert alive_plant.mycorrhizal_connections == set()


def test_run_lifecycle_growth_is_incremental_at_late_ticks() -> None:
    """Validates the run lifecycle growth is incremental at late ticks invariant and confirms the expected biological behavior under controlled simulation conditions.

    The assertions in this test enforce deterministic state transitions so ecological outcomes remain consistent with configured constraints and signal-response dynamics.

    Returns:
        None. The function verifies invariant compliance through assertions rather than data return.

    """
    world = ECSWorld()
    env = GridEnvironment(width=4, height=4, num_signals=1, num_toxins=1)
    params = {0: _config().flora_species[0]}

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=1,
        y=1,
        energy=10.0,
        max_energy=20.0,
        base_energy=10.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=999,
        seed_min_dist=1.0,
        seed_max_dist=1.0,
        seed_energy_cost=999.0,
    )
    world.add_component(plant_entity.entity_id, plant)
    world.register_position(plant_entity.entity_id, 1, 1)

    run_lifecycle(world, env, tick=1000, flora_species_params=params)

    grown = world.get_entity(plant_entity.entity_id).get_component(PlantComponent)
    assert grown.energy == pytest.approx(10.5)
