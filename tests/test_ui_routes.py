"""
Integration coverage for PHIDS HTMX/UI routes and dashboard helpers.

This module implements integration tests for the PHIDS HTMX-driven UI routes and dashboard helpers. The test suite verifies the correctness of server-side draft state mutation, scenario loading, placement editing, and dashboard rendering, ensuring compliance with deterministic simulation logic, double-buffered state management, and O(1) spatial hash invariants. Each test function is documented to state the invariant or biological behavior being verified and its scientific rationale, supporting reproducible and rigorous validation of emergent ecological dynamics and UI interactions. The module-level docstring is written in accordance with Google-style documentation standards, providing a comprehensive scholarly abstract of the test suite's scope and scientific rationale.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from httpx import ASGITransport, AsyncClient

from phids import __main__ as phids_cli
from phids.api import main as api_main
from phids.api.presenters.dashboard import build_live_dashboard_payload
from phids.api import ui_state as draft_state_module
from phids.api.main import app
from phids.api.services.draft_service import DraftService
from phids.api.schemas import BatchJobState, FloraSpeciesParams, PredatorSpeciesParams
from phids.api.ui_state import DraftState, SubstanceDefinition, get_draft, reset_draft, set_draft
from phids.engine import batch as batch_engine
from phids.engine.components.plant import PlantComponent
from phids.engine.core import flow_field
from phids.engine.loop import SimulationLoop
from phids.io import replay
from phids.io.scenario import load_scenario_from_json
from phids.shared import logging_config
from phids.telemetry import export as telemetry_export


draft_service = DraftService()


def _default_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _sample_telemetry_rows() -> list[dict[str, object]]:
    """Return compact telemetry rows spanning flora, predator, defense, and batch fields."""
    return [
        {
            "tick": 0,
            "flora_population": 10,
            "predator_population": 4,
            "total_flora_energy": 100.0,
            "plant_pop_by_species": {0: 6, 1: 4},
            "plant_energy_by_species": {0: 60.0, 1: 40.0},
            "swarm_pop_by_species": {0: 4},
            "defense_cost_by_species": {0: 6.0, 1: 2.0},
            "survival_probability": 1.0,
        },
        {
            "tick": 1,
            "flora_population": 8,
            "predator_population": 5,
            "total_flora_energy": 88.0,
            "plant_pop_by_species": {0: 5, 1: 3},
            "plant_energy_by_species": {0: 50.0, 1: 38.0},
            "swarm_pop_by_species": {0: 3, 1: 2},
            "defense_cost_by_species": {0: 5.0, 1: 4.0},
            "survival_probability": 0.75,
        },
    ]


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """
    Resets the draft and live simulation loop state between UI tests to ensure deterministic reproducibility.

    This fixture enforces a clean simulation environment for each test, preventing cross-test contamination of mutable draft state and live simulation loop. By resetting the draft and nullifying the simulation loop and task, the fixture guarantees that each test operates on a pristine state, thereby upholding the scientific rigor required for reproducible validation of emergent ecological dynamics and UI interactions in PHIDS.
    """
    reset_draft()
    api_main._sim_loop = None
    api_main._sim_task = None


@pytest.mark.asyncio
async def test_root_returns_full_html() -> None:
    """
    Validates that the root endpoint returns a complete HTML workspace for the PHIDS UI.

    This test ensures that the main workspace, diagnostics rail, and upload scenario elements are present in the HTML response, confirming the integrity of the HTMX-driven UI. The presence of these elements is critical for user interaction, scenario management, and diagnostics, supporting the scientific workflow of ecosystem simulation and analysis.
    """
    async with _default_client() as client:
        resp = await client.get("/")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert 'id="main-workspace"' in resp.text
    assert 'id="diagnostics-rail"' in resp.text
    assert 'id="diagnostics-content"' in resp.text
    assert "phidsUploadScenario" in resp.text
    assert "/api/scenario/load-draft" in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("/ui/dashboard", "biotope-canvas"),
        ("/ui/placements", "placement-canvas"),
        ("/ui/biotope", "biotope-config-view"),
        ("/ui/flora", "flora-config-view"),
        ("/ui/predators", "predator-config-view"),
        ("/ui/substances", "substance-config-view"),
        ("/ui/diet-matrix", "diet-matrix-view"),
        ("/ui/trigger-rules", "trigger-rules-view"),
        ("/ui/batch", "Monte Carlo Batch Runner"),
    ],
)
async def test_ui_partials_render(path: str, marker: str) -> None:
    """
    Verifies that each UI partial endpoint renders the expected canvas or configuration view.

    This test suite systematically checks the rendering of dashboard and configuration views for biotope, flora, predators, substances, diet matrix, and trigger rules. The presence of specific markers in the HTML response confirms that the UI correctly exposes the configuration and visualization surfaces necessary for deterministic scenario editing and ecological simulation, supporting rigorous scientific experimentation.
    """
    async with _default_client() as client:
        resp = await client.get(path)

    assert resp.status_code == 200
    assert marker in resp.text
    if path == "/ui/batch":
        assert "Load Persisted Batches" in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/ui/diagnostics/model",
        "/ui/diagnostics/frontend",
        "/ui/diagnostics/backend",
    ],
)
async def test_diagnostics_tabs_render(path: str) -> None:
    """
    Ensures that diagnostics tab endpoints render the diagnostics content for model, frontend, and backend.

    This test validates the accessibility and rendering of diagnostics views, which are essential for monitoring simulation health, model correctness, and backend/frontend integration. The presence of diagnostics content in the response supports the scientific requirement for transparent telemetry and error reporting in PHIDS.
    """
    async with _default_client() as client:
        resp = await client.get(path)

    assert resp.status_code == 200
    assert "diagnostics" in resp.text.lower()


@pytest.mark.asyncio
async def test_ui_status_helpers_render_without_loaded_simulation() -> None:
    """
    Confirms that UI status helpers render correctly when no simulation is loaded.

    This test checks the tick, status badge, and telemetry endpoints for correct responses in the absence of a loaded simulation. The test ensures that the UI accurately reflects the idle state, supporting the scientific principle of deterministic state reporting and user feedback in ecosystem simulation workflows.
    """
    async with _default_client() as client:
        tick_resp = await client.get("/api/ui/tick")
        status_resp = await client.get("/api/ui/status-badge")
        telemetry_resp = await client.get("/api/telemetry")

    assert tick_resp.status_code == 200
    assert tick_resp.text == "0"
    assert status_resp.status_code == 200
    assert "Idle" in status_resp.text
    assert telemetry_resp.status_code == 200
    assert "No telemetry data yet" in telemetry_resp.text


@pytest.mark.asyncio
async def test_table_preview_route_renders_empty_state_without_loaded_simulation() -> None:
    """Confirms telemetry table preview fragment reports an informative empty-state message."""
    async with _default_client() as client:
        resp = await client.get("/api/telemetry/table_preview")

    assert resp.status_code == 200
    assert "No telemetry data available" in resp.text


@pytest.mark.asyncio
async def test_dashboard_contains_extended_telemetry_canvases() -> None:
    """Ensures the dashboard partial exposes defense and biomass telemetry canvases."""
    async with _default_client() as client:
        resp = await client.get("/ui/dashboard")

    assert resp.status_code == 200
    assert 'id="ts-chart"' in resp.text
    assert 'id="defense-chart"' in resp.text
    assert 'id="biomass-chart"' in resp.text


def test_live_dashboard_payload_separates_render_layers_from_all_configured_species() -> None:
    """Verifies that the dashboard payload preserves extinct-species metadata without repainting extinct layers.

    This test validates the bifurcated payload contract used by the live dashboard. The canvas
    renderer must receive only extant flora layers so stale or extinct species cannot reappear as
    chromatic ghosts on the grid, whereas the legend and population bars must continue to enumerate
    the full configured flora catalogue with an explicit ``extinct`` flag. The invariant preserves
    ecological interpretability across collapse events while keeping the rendered field faithful to
    the live ECS population state.
    """
    config = load_scenario_from_json(Path("examples/meadow_defense.json"))
    loop = SimulationLoop(config)

    # Advance until only one flora species remains in the ECS world.
    while loop.tick < 140:
        asyncio.run(loop.step())
        live_species = {
            entity.get_component(PlantComponent).species_id
            for entity in loop.world.query(PlantComponent)
        }
        if len(live_species) <= 1:
            break

    payload = build_live_dashboard_payload(loop, substance_names=api_main._sim_substance_names)
    payload_species = {int(spec["species_id"]) for spec in payload["species_energy"]}
    legend_species = {int(spec["species_id"]) for spec in payload["all_flora_species"]}
    configured_species = {species.species_id for species in loop.config.flora_species}
    live_species = {
        entity.get_component(PlantComponent).species_id
        for entity in loop.world.query(PlantComponent)
    }

    assert payload_species == live_species
    assert legend_species == configured_species

    # Extinct entries must remain visible in the legend metadata but absent from the render layers.
    extinct_in_payload = {
        int(spec["species_id"])
        for spec in payload["all_flora_species"]
        if spec.get("extinct", False)
    }
    assert extinct_in_payload == configured_species - live_species


@pytest.mark.asyncio
async def test_simulation_control_and_live_export_routes_cover_status_filters_and_htmx_badges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercises simulation control, telemetry export, and HTMX badge branches through the live API surface."""
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 2, 2, 15.0)
    draft_service.add_swarm_placement(draft, 0, 2, 2, 4, 20.0)
    draft.diet_matrix[0][0] = False
    config = draft.build_sim_config()

    pending_load_task = asyncio.create_task(asyncio.sleep(60))
    api_main._sim_task = pending_load_task

    class _CompletedTask:
        def done(self) -> bool:
            return True

        def cancel(self) -> None:
            return None

    def _close_coro_task(coro: object) -> _CompletedTask:
        if hasattr(coro, "close"):
            coro.close()
        return _CompletedTask()

    real_create_task = asyncio.create_task

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load", json=config.model_dump())
        status_resp = await client.get("/api/simulation/status")
        wind_resp = await client.put("/api/simulation/wind", json={"wind_x": 1.25, "wind_y": -0.5})
        step_resp = await client.post("/api/simulation/step")
        csv_resp = await client.get("/api/telemetry/export/csv")
        ndjson_resp = await client.get("/api/telemetry/export/json")
        chart_resp = await client.get("/api/telemetry/chartjs-data")
        table_resp = await client.get(
            "/api/telemetry/table_preview",
            params={
                "columns": "tick,plant_0_pop",
                "flora_ids": "0",
                "tick_interval": 1,
                "limit": 1,
            },
        )

        monkeypatch.setattr(api_main.asyncio, "create_task", _close_coro_task)
        start_resp = await client.post("/api/simulation/start", headers={"HX-Request": "true"})
        pause_resp = await client.post("/api/simulation/pause", headers={"HX-Request": "true"})

        pending_reset_task = real_create_task(asyncio.sleep(60))
        api_main._sim_task = pending_reset_task
        reset_resp = await client.post("/api/simulation/reset", headers={"HX-Request": "true"})

    assert load_resp.status_code == 200
    assert pending_load_task.cancelled()
    assert status_resp.status_code == 200
    assert status_resp.json()["tick"] == 0
    assert wind_resp.status_code == 200
    assert wind_resp.json()["wind_x"] == 1.25
    assert step_resp.status_code == 200
    assert step_resp.json()["tick"] == 1
    assert csv_resp.status_code == 200
    assert csv_resp.text.startswith("tick,")
    assert ndjson_resp.status_code == 200
    assert '"tick":' in ndjson_resp.text
    assert chart_resp.status_code == 200
    chart_payload = chart_resp.json()
    assert chart_payload["labels"] == [0]
    assert "plant_0_pop" in chart_payload["series"]
    assert table_resp.status_code == 200
    assert "plant_0_pop" in table_resp.text
    assert start_resp.status_code == 200
    assert "Running" in start_resp.text
    assert pause_resp.status_code == 200
    assert "Paused" in pause_resp.text
    assert reset_resp.status_code == 200
    assert pending_reset_task.cancelled()
    assert "Loaded" in reset_resp.text


@pytest.mark.asyncio
async def test_batch_routes_cover_invalid_drafts_successful_jobs_and_export_error_branches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exercises batch-start validation, asynchronous completion, status rendering, and export failure branches."""
    reset_draft()
    invalid_draft = get_draft()
    invalid_draft.flora_species.clear()
    invalid_draft.predator_species.clear()

    async with _default_client() as client:
        invalid_resp = await client.post(
            "/api/batch/start",
            json={"runs": 1, "max_ticks": 2, "scenario_name": "invalid"},
        )

    assert invalid_resp.status_code == 400
    assert "Invalid draft" in invalid_resp.text

    reset_draft()
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 1, 1, 12.0)
    draft_service.add_swarm_placement(draft, 0, 1, 1, 4, 16.0)
    monkeypatch.setattr(api_main, "_BATCH_DIR", tmp_path)

    scheduled_tasks: list[asyncio.Task[None]] = []
    original_create_task = asyncio.create_task

    def _capture_task(coro: object) -> asyncio.Task[None]:
        task = original_create_task(coro)
        scheduled_tasks.append(task)
        return task

    def _fake_execute_batch(
        self: batch_engine.BatchRunner,
        scenario_dict: dict[str, object],
        runs: int,
        max_ticks: int,
        job_id: str,
        output_dir: Path,
        on_progress: object | None = None,
    ) -> batch_engine.BatchResult:
        if callable(on_progress):
            on_progress(1)
            on_progress(runs)
        aggregate = {
            "ticks": [0, 1],
            "flora_population_mean": [10.0, 8.0],
            "flora_population_std": [0.0, 1.0],
            "predator_population_mean": [4.0, 5.0],
            "predator_population_std": [0.0, 1.0],
            "survival_probability_curve": [1.0, 0.5],
            "extinction_probability": 0.25,
            "runs_completed": runs,
            "per_flora_pop_mean": {"0": [10.0, 8.0]},
            "per_flora_pop_std": {"0": [0.0, 1.0]},
            "per_predator_pop_mean": {"0": [4.0, 5.0]},
            "per_predator_pop_std": {"0": [0.0, 1.0]},
        }
        (output_dir / f"{job_id}_summary.json").write_text(json.dumps(aggregate), encoding="utf-8")
        return batch_engine.BatchResult(
            job_id=job_id, runs=runs, per_run_telemetry=[], aggregate=aggregate
        )

    monkeypatch.setattr(api_main.asyncio, "create_task", _capture_task)
    monkeypatch.setattr("phids.engine.batch.BatchRunner.execute_batch", _fake_execute_batch)

    async with _default_client() as client:
        start_resp = await client.post(
            "/api/batch/start",
            json={"runs": 2, "max_ticks": 3, "scenario_name": "coverage batch"},
        )
        assert start_resp.status_code == 200
        job_id = start_resp.json()["job_id"]

        await asyncio.gather(*scheduled_tasks)

        status_resp = await client.get(f"/api/batch/status/{job_id}")
        ledger_resp = await client.get("/api/batch/ledger")
        view_resp = await client.get(f"/api/batch/view/{job_id}")
        csv_resp = await client.get(
            f"/api/batch/export/{job_id}",
            params={"format": "csv", "columns": "tick,flora_population_mean", "tick_interval": 1},
        )
        tex_table_resp = await client.get(
            f"/api/batch/export/{job_id}",
            params={"format": "tex_table", "tick_interval": 1},
        )
        tikz_resp = await client.get(
            f"/api/batch/export/{job_id}",
            params={"format": "tex_tikz", "chart_type": "survival", "title": "Survival"},
        )
        missing_status_resp = await client.get("/api/batch/status/does-not-exist")
        missing_export_resp = await client.get("/api/batch/export/does-not-exist")
        bad_format_resp = await client.get(f"/api/batch/export/{job_id}", params={"format": "png"})
        bad_tick_resp = await client.get(
            f"/api/batch/export/{job_id}",
            params={"format": "csv", "tick_interval": 0},
        )

    assert status_resp.status_code == 200
    assert "coverage batch" in status_resp.text
    assert ledger_resp.status_code == 200
    assert job_id in ledger_resp.text
    assert view_resp.status_code == 200
    assert "batch-survival-chart" in view_resp.text
    assert csv_resp.status_code == 200
    assert "flora_population_mean" in csv_resp.text
    assert tex_table_resp.status_code == 200
    assert "\\toprule" in tex_table_resp.text
    assert tikz_resp.status_code == 200
    assert "Simulations alive (%)" in tikz_resp.text
    assert missing_status_resp.status_code == 404
    assert missing_export_resp.status_code == 404
    assert bad_format_resp.status_code == 400
    assert bad_tick_resp.status_code == 400


def test_export_helpers_cover_dataframe_filters_and_all_chart_variants(tmp_path: Path) -> None:
    """Exercises telemetry export helpers across filtering, tabular, PNG, and TikZ pathways."""
    rows = _sample_telemetry_rows()
    assert telemetry_export._append_species_id("2", 0) == "0,2"
    assert telemetry_export._parse_species_ids(" 1, bad, 2 ,, ") == {1, 2}
    assert telemetry_export._parse_species_ids(None) is None

    filtered_rows = telemetry_export.filter_telemetry_rows(rows, flora_ids="1", predator_ids="1")
    assert filtered_rows[0]["plant_pop_by_species"] == {1: 4}
    assert filtered_rows[1]["swarm_pop_by_species"] == {1: 2}

    dataframe = telemetry_export.telemetry_to_dataframe(rows)
    assert {"tick", "plant_0_pop", "plant_1_energy", "swarm_1_pop", "defense_cost_0"}.issubset(
        dataframe.columns
    )
    narrowed = telemetry_export.filter_dataframe_columns(dataframe, "plant_0_pop")
    assert list(narrowed.columns) == ["tick", "plant_0_pop"]
    decimated = telemetry_export.decimate_dataframe(dataframe, 2)
    assert len(decimated) == 1

    polars_df = pl.DataFrame({"tick": [0, 1], "flora_population": [10, 8]})
    telemetry_export.export_csv(polars_df, tmp_path / "telemetry.csv")
    telemetry_export.export_json(polars_df, tmp_path / "telemetry.ndjson")
    assert (tmp_path / "telemetry.csv").read_text(encoding="utf-8").startswith("tick,")
    assert '"tick":0' in (tmp_path / "telemetry.ndjson").read_text(encoding="utf-8")
    assert telemetry_export.export_bytes_csv(polars_df).startswith(b"tick,")
    assert b'"tick":0' in telemetry_export.export_bytes_json(polars_df)

    latex_table = telemetry_export.export_bytes_tex_table(
        rows,
        columns="tick,plant_0_pop",
        include_flora_ids="0",
        tick_interval=2,
    )
    assert b"\\toprule" in latex_table
    assert telemetry_export.export_bytes_tex_table([], tick_interval=1) == b"% No telemetry data\n"

    flora_names = {0: "Grass", 1: "Clover"}
    predator_names = {0: "Aphid", 1: "Rabbit"}
    for plot_type in (
        "timeseries",
        "phasespace",
        "defense_economy",
        "biomass_stack",
        "survival_probability",
    ):
        png = telemetry_export.generate_png_bytes(
            rows,
            plot_type,
            flora_names=flora_names,
            predator_names=predator_names,
            prey_species_id=1,
            predator_species_id=1,
            title="Coverage",
            x_label="Tick",
            y_label="Value",
            x_max=20,
            y_max=20,
            dpi=40,
        )
        tikz = telemetry_export.generate_tikz_str(
            rows,
            plot_type,
            flora_names=flora_names,
            predator_names=predator_names,
            prey_species_id=1,
            predator_species_id=1,
            title="Coverage",
            x_label="Tick",
            y_label="Value",
            x_max=20,
            y_max=20,
        )
        assert png.startswith(b"\x89PNG")
        assert "\\begin{tikzpicture}" in tikz

    assert telemetry_export.generate_png_bytes([], "timeseries", dpi=40).startswith(b"\x89PNG")
    with pytest.raises(ValueError):
        telemetry_export.generate_png_bytes(rows, "unknown")
    with pytest.raises(ValueError):
        telemetry_export.generate_tikz_str(rows, "unknown")

    aggregate_frame = telemetry_export.aggregate_to_dataframe(
        {
            "ticks": [0, 1],
            "flora_population_mean": [10.0, 8.0],
            "flora_population_std": [0.0, 1.0],
            "predator_population_mean": [4.0, 5.0],
            "predator_population_std": [0.0, 1.0],
            "per_flora_pop_mean": {"0": [6.0, 5.0]},
            "per_flora_pop_std": {"0": [0.0, 1.0]},
            "per_predator_pop_mean": {"1": [1.0, 2.0]},
            "per_predator_pop_std": {"1": [0.0, 1.0]},
        },
        flora_names=flora_names,
        predator_names=predator_names,
    )
    assert not aggregate_frame.empty
    assert {"Grass_pop_mean", "Rabbit_pop_std"}.issubset(aggregate_frame.columns)
    assert telemetry_export.aggregate_to_dataframe({}).empty


def test_draft_state_mutators_and_condition_tree_helpers_cover_compaction_paths() -> None:
    """Exercises draft-state mutation helpers, trigger-condition tree editing, and ID compaction semantics."""
    draft = DraftState.default()
    draft_state_module._draft = None
    assert get_draft().scenario_name == "Default Scenario"
    set_draft(draft)
    assert get_draft() is draft

    assert SubstanceDefinition(substance_id=0).type_label == "Signal"
    assert (
        SubstanceDefinition(substance_id=1, is_toxin=True, lethal=True).type_label == "Lethal Toxin"
    )
    assert (
        SubstanceDefinition(substance_id=2, is_toxin=True, repellent=True).type_label
        == "Repellent Toxin"
    )
    assert SubstanceDefinition(substance_id=3, is_toxin=True).type_label == "Toxin"

    assert draft_state_module._legacy_signal_ids_to_activation_condition([0, 1]) == {
        "kind": "all_of",
        "conditions": [
            {"kind": "substance_active", "substance_id": 0},
            {"kind": "substance_active", "substance_id": 1},
        ],
    }
    assert draft_state_module._parse_condition_path("0.1.2") == [0, 1, 2]
    assert draft_state_module._default_activation_condition_node(
        "enemy_presence", predator_species_id=2, min_predator_population=0
    ) == {
        "kind": "enemy_presence",
        "predator_species_id": 2,
        "min_predator_population": 1,
    }
    with pytest.raises(ValueError):
        draft_state_module._default_activation_condition_node("unsupported")

    draft_service.add_flora(
        draft,
        FloraSpeciesParams(
            species_id=9,
            name="Clover",
            base_energy=9.0,
            max_energy=80.0,
            growth_rate=3.0,
            survival_threshold=1.0,
            reproduction_interval=8,
            triggers=[],
        ),
    )
    draft_service.add_predator(
        draft,
        PredatorSpeciesParams(
            species_id=9,
            name="Rabbit",
            energy_min=4.0,
            velocity=1,
            consumption_rate=2.5,
        ),
    )
    draft.substance_definitions = [
        SubstanceDefinition(substance_id=0, name="Alarm"),
        SubstanceDefinition(substance_id=1, name="Toxin", is_toxin=True, lethal=True),
    ]
    draft_service.add_trigger_rule(
        draft,
        1,
        1,
        1,
        min_predator_population=3,
        required_signal_ids=[0],
    )
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "substance_active",
        "substance_id": 0,
    }

    draft_service.update_trigger_rule(draft, 0, required_signal_ids=[0, 1])
    draft_service.set_trigger_rule_activation_condition(
        draft,
        0,
        {
            "kind": "all_of",
            "conditions": [
                {"kind": "enemy_presence", "predator_species_id": 1, "min_predator_population": 3}
            ],
        },
    )
    draft_service.append_trigger_rule_condition_child(
        draft,
        0,
        "",
        {"kind": "substance_active", "substance_id": 1},
    )
    draft_service.replace_trigger_rule_condition_node(
        draft,
        0,
        "1",
        {"kind": "enemy_presence", "predator_species_id": 1, "min_predator_population": 4},
    )
    draft_service.update_trigger_rule_condition_node(
        draft,
        0,
        "0",
        min_predator_population=5,
    )
    draft_service.delete_trigger_rule_condition_node(draft, 0, "1")
    with pytest.raises(IndexError):
        draft_service.replace_trigger_rule_condition_node(
            draft, 0, "9", {"kind": "substance_active", "substance_id": 0}
        )

    current_condition = draft.trigger_rules[0].activation_condition
    assert current_condition == {
        "kind": "all_of",
        "conditions": [
            {"kind": "enemy_presence", "predator_species_id": 1, "min_predator_population": 5}
        ],
    }
    assert (
        draft_state_module._condition_node_at_path(current_condition, [0])
        == current_condition["conditions"][0]
    )
    assert (
        draft_state_module._prune_empty_condition_groups({"kind": "all_of", "conditions": []})
        is None
    )
    remapped = draft_state_module._remap_condition_references(
        {
            "kind": "all_of",
            "conditions": [
                {"kind": "enemy_presence", "predator_species_id": 2, "min_predator_population": 2},
                {"kind": "substance_active", "substance_id": 2},
            ],
        },
        removed_predator_id=1,
        removed_substance_id=1,
    )
    assert remapped == {
        "kind": "all_of",
        "conditions": [
            {"kind": "enemy_presence", "predator_species_id": 1, "min_predator_population": 2},
            {"kind": "substance_active", "substance_id": 1},
        ],
    }

    draft_service.add_plant_placement(draft, 1, 3, 4, 12.0)
    draft_service.add_swarm_placement(draft, 1, 4, 5, 6, 18.0)
    config = draft.build_sim_config()
    assert len(config.flora_species) == 2
    assert len(config.predator_species) == 2
    assert len(config.initial_plants) == 1
    assert len(config.initial_swarms) == 1

    draft_service.remove_plant_placement(draft, 0)
    draft_service.remove_swarm_placement(draft, 0)
    draft_service.add_plant_placement(draft, 1, 2, 2, 11.0)
    draft_service.add_swarm_placement(draft, 1, 2, 2, 5, 14.0)
    draft_service.remove_predator(draft, 0)
    draft_service.remove_flora(draft, 0)
    assert draft.predator_species[0].species_id == 0
    assert draft.flora_species[0].species_id == 0
    draft_service.remove_trigger_rule(draft, 0)
    draft_service.clear_placements(draft)
    assert not draft.initial_plants
    assert not draft.initial_swarms
    with pytest.raises(ValueError):
        draft_service.remove_flora(draft, 99)
    with pytest.raises(ValueError):
        draft_service.remove_predator(draft, 99)

    empty = DraftState.default()
    empty.flora_species.clear()
    empty.predator_species.clear()
    with pytest.raises(ValueError):
        empty.build_sim_config()
    reset_draft()


def test_batch_engine_flow_replay_logging_and_cli_helpers_cover_remaining_support_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercises batch aggregation, flow fields, replay I/O, logging bootstrap, and CLI dispatch helpers."""
    plant_energy = np.zeros((3, 3), dtype=np.float64)
    plant_energy[2, 2] = 5.0
    toxin_layers = np.zeros((1, 3, 3), dtype=np.float64)
    toxin_layers[0, 0, 0] = 1.0
    gradient = flow_field.compute_flow_field(plant_energy, toxin_layers, 3, 3)
    assert gradient[2, 2] > gradient[0, 0]
    attenuated = gradient[2, 2]
    flow_field.apply_camouflage(gradient, 2, 2, 0.5)
    assert math.isclose(gradient[2, 2], attenuated * 0.5)
    assert (
        flow_field._compute_flow_field_impl(
            np.array([[1e-6]], dtype=np.float64),
            np.array([[0.0]], dtype=np.float64),
            1,
            1,
        )[0, 0]
        == 0.0
    )

    replay_buffer = replay.ReplayBuffer()
    replay_buffer.append({"tick": 0, "value": 1})
    replay_buffer.append({"tick": 1, "value": 2})
    replay_path = tmp_path / "state.replay"
    replay_buffer.save(replay_path)
    loaded_buffer = replay.ReplayBuffer.load(replay_path)
    assert len(replay_buffer) == 2
    assert loaded_buffer.get_frame(1)["value"] == 2
    assert replay.deserialise_state(replay.serialise_state({"tick": 9})) == {"tick": 9}

    truncated_path = tmp_path / "truncated.replay"
    truncated_path.write_bytes(replay_path.read_bytes()[:-1])
    truncated_loaded = replay.ReplayBuffer.load(truncated_path)
    assert len(truncated_loaded) == 1

    scenario_dict = DraftState.default().build_sim_config().model_dump()
    headless_rows = batch_engine._run_single_headless(scenario_dict, max_ticks=1, seed=3)
    assert isinstance(headless_rows, list)
    assert batch_engine.aggregate_batch_telemetry([]) == {}
    aggregate = batch_engine.aggregate_batch_telemetry(
        [_sample_telemetry_rows(), _sample_telemetry_rows()]
    )
    assert aggregate["runs_completed"] == 2
    assert aggregate["ticks"] == [0, 1]
    sanitized = batch_engine._sanitize_for_json(
        {"nan": float("nan"), "nested": [float("inf"), np.float64(1.5)]}
    )
    assert sanitized == {"nan": None, "nested": [None, 1.5]}

    expected_rows = _sample_telemetry_rows()
    monkeypatch.setattr(batch_engine, "_run_single_headless", lambda *args: expected_rows)
    assert (
        batch_engine._run_and_save((scenario_dict, 1, 2, "jobx", 0, str(tmp_path))) == expected_rows
    )

    class _FakeFuture:
        def __init__(self, value: list[dict[str, object]]) -> None:
            self._value = value

        def result(self) -> list[dict[str, object]]:
            return self._value

    class _FakeExecutor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._futures: list[_FakeFuture] = []

        def __enter__(self) -> _FakeExecutor:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        def submit(
            self, fn: object, args: tuple[dict[str, object], int, int, str, int, str]
        ) -> _FakeFuture:
            future = _FakeFuture(fn(args))
            self._futures.append(future)
            return future

    monkeypatch.setattr(batch_engine.concurrent.futures, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(
        batch_engine.concurrent.futures, "as_completed", lambda futures: list(futures)
    )
    monkeypatch.setattr(batch_engine.multiprocessing, "get_context", lambda mode: object())
    progress: list[int] = []
    batch_result = batch_engine.BatchRunner().execute_batch(
        scenario_dict,
        runs=2,
        max_ticks=1,
        job_id="coverage-job",
        output_dir=tmp_path,
        on_progress=progress.append,
    )
    assert batch_result.runs == 2
    assert progress == [1, 2]
    assert (tmp_path / "coverage-job_summary.json").exists()

    assert logging_config._coerce_log_level("bogus") == "INFO"
    assert logging_config._coerce_positive_int("0", default=7) == 7
    monkeypatch.setenv("PHIDS_LOG_LEVEL", "debug")
    monkeypatch.setenv("PHIDS_LOG_FILE_LEVEL", "warning")
    monkeypatch.setenv("PHIDS_LOG_FILE", str(tmp_path / "phids.log"))
    monkeypatch.setenv("PHIDS_LOG_SIM_DEBUG_INTERVAL", "12")
    logging_config.configure_logging(force=True)
    logger = logging.getLogger("phids.coverage")
    logger.warning("coverage logging smoke")
    assert logging_config.get_simulation_debug_interval() == 12
    assert any(
        entry["message"] == "coverage logging smoke"
        for entry in logging_config.get_recent_logs(limit=10)
    )
    assert (tmp_path / "phids.log").exists()

    parsed = phids_cli.build_parser().parse_args(
        ["--host", "0.0.0.0", "--port", "9000", "--reload"]
    )
    assert parsed.host == "0.0.0.0"
    assert parsed.port == 9000
    captured: dict[str, object] = {}

    def _fake_uvicorn_run(
        app_obj: object, host: str, port: int, reload: bool, log_level: str
    ) -> None:
        captured.update(
            {"app": app_obj, "host": host, "port": port, "reload": reload, "log_level": log_level}
        )

    monkeypatch.setattr("uvicorn.run", _fake_uvicorn_run)
    phids_cli.main(["--host", "0.0.0.0", "--port", "9001", "--reload", "--log-level", "debug"])
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9001
    assert captured["reload"] is True
    assert captured["log_level"] == "debug"


@pytest.mark.asyncio
async def test_batch_view_renders_survival_chart_when_summary_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates that the batch aggregate fragment includes the survival probability chart canvas."""
    job_id = "jobtest01"
    draft = get_draft()
    draft.active_batch_jobs[job_id] = BatchJobState(
        job_id=job_id,
        status="done",
        completed=2,
        total=2,
        scenario_name="smoke",
        started_at="now",
        max_ticks=4,
    )

    summary = {
        "ticks": [0, 1, 2, 3],
        "flora_population_mean": [10.0, 8.0, 6.0, 4.0],
        "flora_population_std": [0.0, 0.5, 0.5, 1.0],
        "predator_population_mean": [2.0, 3.0, 4.0, 5.0],
        "predator_population_std": [0.0, 0.5, 0.5, 1.0],
        "survival_probability_curve": [1.0, 1.0, 0.5, 0.5],
        "extinction_probability": 0.5,
        "runs_completed": 2,
    }
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / f"{job_id}_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(api_main, "_BATCH_DIR", batch_dir)

    async with _default_client() as client:
        resp = await client.get(f"/api/batch/view/{job_id}")

    assert resp.status_code == 200
    assert "batch-survival-chart" in resp.text
    assert "batch-table-preview" in resp.text
    assert "batch-export-stride" in resp.text
    assert "batch-chart-title" in resp.text
    assert "batch-columns" in resp.text
    assert "batch-chart-preset" in resp.text
    assert "batch-apply-chart" in resp.text
    assert "batch-apply-table" in resp.text


@pytest.mark.asyncio
async def test_load_persisted_batches_populates_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures persisted summary files can be reloaded into the in-memory batch ledger."""
    summary_path = tmp_path / "batches"
    summary_path.mkdir(parents=True, exist_ok=True)
    (summary_path / "persisted01_summary.json").write_text(
        json.dumps(
            {
                "ticks": [0, 1],
                "flora_population_mean": [5.0, 4.0],
                "flora_population_std": [0.0, 0.1],
                "predator_population_mean": [2.0, 2.0],
                "predator_population_std": [0.0, 0.1],
                "survival_probability_curve": [1.0, 1.0],
                "extinction_probability": 0.0,
                "runs_completed": 3,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(api_main, "_BATCH_DIR", summary_path)

    async with _default_client() as client:
        load_resp = await client.post("/api/batch/load-persisted")
        ledger_resp = await client.get("/api/batch/ledger")

    assert load_resp.status_code == 200
    assert load_resp.json()["loaded"] == 1
    assert ledger_resp.status_code == 200
    assert "persisted01" in ledger_resp.text


@pytest.mark.asyncio
async def test_batch_export_csv_respects_tick_interval_decimation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validates batch CSV export row count decreases when tick_interval increases."""
    job_id = "decimate01"
    summary = {
        "ticks": [0, 1, 2, 3, 4, 5],
        "flora_population_mean": [10, 9, 8, 7, 6, 5],
        "flora_population_std": [0, 0, 0, 0, 0, 0],
        "predator_population_mean": [1, 1, 2, 2, 3, 3],
        "predator_population_std": [0, 0, 0, 0, 0, 0],
        "survival_probability_curve": [1, 1, 1, 0.8, 0.8, 0.6],
        "extinction_probability": 0.4,
        "runs_completed": 5,
    }
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / f"{job_id}_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(api_main, "_BATCH_DIR", batch_dir)

    async with _default_client() as client:
        full_resp = await client.get(
            f"/api/batch/export/{job_id}", params={"format": "csv", "tick_interval": 1}
        )
        decimated_resp = await client.get(
            f"/api/batch/export/{job_id}", params={"format": "csv", "tick_interval": 2}
        )

    assert full_resp.status_code == 200
    assert decimated_resp.status_code == 200
    full_lines = [line for line in full_resp.text.splitlines() if line.strip()]
    decimated_lines = [line for line in decimated_resp.text.splitlines() if line.strip()]
    # Both include header; decimated export must contain fewer data rows.
    assert len(full_lines) > len(decimated_lines)


@pytest.mark.asyncio
async def test_batch_export_tikz_supports_survival_chart_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensures batch TikZ export can render survival-probability diagnostics."""
    job_id = "survival01"
    summary = {
        "ticks": [0, 1, 2],
        "flora_population_mean": [10, 8, 6],
        "flora_population_std": [0, 1, 1],
        "predator_population_mean": [2, 3, 4],
        "predator_population_std": [0, 1, 1],
        "survival_probability_curve": [1.0, 0.8, 0.5],
        "extinction_probability": 0.5,
        "runs_completed": 3,
    }
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / f"{job_id}_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(api_main, "_BATCH_DIR", batch_dir)

    async with _default_client() as client:
        resp = await client.get(
            f"/api/batch/export/{job_id}",
            params={"format": "tex_tikz", "chart_type": "survival", "title": "Survival"},
        )

    assert resp.status_code == 200
    assert "Simulations alive (%)" in resp.text


@pytest.mark.asyncio
async def test_export_route_accepts_metabolic_alias_and_returns_tikz() -> None:
    """Validates that the metabolic alias resolves to defense-economy export generation."""
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 2, 2, 20.0)
    draft_service.add_swarm_placement(draft, 0, 2, 2, 5, 20.0)

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load-draft")
        assert load_resp.status_code == 200
        await client.post("/api/simulation/step")
        resp = await client.get("/api/export/metabolic", params={"format": "tex_tikz"})

    assert resp.status_code == 200
    assert "Metabolic Defense Economy" in resp.text


@pytest.mark.asyncio
async def test_export_route_rejects_non_positive_tick_interval() -> None:
    """Ensures telemetry export returns HTTP 400 when tick_interval is below 1."""
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 1, 1, 10.0)
    draft_service.add_swarm_placement(draft, 0, 1, 1, 3, 12.0)

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load-draft")
        assert load_resp.status_code == 200
        resp = await client.get(
            "/api/export/timeseries",
            params={"format": "csv", "tick_interval": 0},
        )

    assert resp.status_code == 400
    assert "tick_interval" in resp.text


@pytest.mark.asyncio
async def test_placement_preview_data_includes_root_links() -> None:
    """
    Validates that placement preview data includes mycorrhizal root links and correct plant/swarm attributes.

    This test ensures that the placement preview endpoint returns data reflecting plant and swarm placements, including mycorrhizal links. The test supports the scientific requirement for accurate visualization and analysis of root network connectivity and population attributes in draft scenarios, facilitating reproducible ecological experimentation.
    """
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 4, 4, 12.0)
    draft_service.add_plant_placement(draft, 0, 4, 5, 11.0)
    draft_service.add_swarm_placement(draft, 0, 4, 4, 7, 20.0)

    async with _default_client() as client:
        resp = await client.get("/api/config/placements/data")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["plants"][0]["x"] == 4
    assert payload["swarms"][0]["population"] == 7
    assert payload["mycorrhizal_links"][0]["x1"] == 4
    assert payload["mycorrhizal_links"][0]["y2"] == 5


@pytest.mark.asyncio
async def test_ui_cell_details_returns_draft_preview_payload_with_mycorrhiza() -> None:
    """
    Ensures that cell details endpoint returns draft preview payload including mycorrhizal connections.

    This test verifies that the cell details endpoint provides draft mode data with correct plant, swarm, and mycorrhizal connection attributes. The test supports the scientific requirement for transparent reporting of root network connectivity and population attributes in draft scenarios, facilitating rigorous ecological analysis and scenario design.
    """
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 1, 2, 15.0)
    draft_service.add_plant_placement(draft, 0, 1, 3, 14.0)
    draft_service.add_swarm_placement(draft, 0, 1, 2, 7, 30.0)

    async with _default_client() as client:
        resp = await client.get("/api/ui/cell-details", params={"x": 1, "y": 2})

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "draft"
    assert data["plants"][0]["name"] == "Grass"
    assert data["plants"][0]["mycorrhizal_connections"] == 1
    assert data["plants"][0]["mycorrhizal_neighbours"][0]["y"] == 3
    assert data["mycorrhiza"]["link_count"] == 1
    assert data["swarms"][0]["name"] == "Herbivore"


@pytest.mark.asyncio
async def test_biotope_config_updates_and_clamps_mycorrhizal_growth_interval() -> None:
    """
    Validates that biotope configuration updates clamp mycorrhizal growth interval to minimum value.

    This test ensures that the biotope configuration endpoint enforces a minimum value for mycorrhizal growth interval ticks, supporting the scientific requirement for deterministic parameter validation and ecological realism in simulation configuration.
    """
    async with _default_client() as client:
        resp = await client.post(
            "/api/config/biotope",
            data={
                "grid_width": 40,
                "grid_height": 40,
                "max_ticks": 1000,
                "tick_rate_hz": 10.0,
                "wind_x": 0.0,
                "wind_y": 0.0,
                "num_signals": 4,
                "num_toxins": 4,
                "mycorrhizal_connection_cost": 1.0,
                "mycorrhizal_growth_interval_ticks": 0,
                "mycorrhizal_signal_velocity": 1,
            },
        )

    assert resp.status_code == 200
    assert 'name="mycorrhizal_growth_interval_ticks"' in resp.text
    assert 'value="1"' in resp.text
    assert get_draft().mycorrhizal_growth_interval_ticks == 1


@pytest.mark.asyncio
async def test_substance_and_diet_routes_delegate_to_service_and_compact_references() -> None:
    """Validates that builder routes preserve compact substance indexing and diet-matrix safety invariants.

    This integration experiment exercises the HTTP surface that fronts the centralized
    ``DraftService`` mutation boundary. The assertions verify that substance creation and update
    routes clamp operator input into bounded scientific parameters, that substance deletion removes
    orphaned trigger rules while remapping surviving activation-condition references, and that diet
    matrix edits mutate only valid trophic-compatibility coordinates. These route-level guarantees
    keep the server-rendered builder aligned with the deterministic draft-state architecture.
    """
    draft = get_draft()

    async with _default_client() as client:
        add_alarm = await client.post("/api/config/substances", data={"name": "Alarm"})
        add_shield = await client.post(
            "/api/config/substances",
            data={"name": "Shield", "is_toxin": "true", "lethal": "true"},
        )
        add_relay = await client.post("/api/config/substances", data={"name": "Relay"})

        update_resp = await client.put(
            "/api/config/substances/1",
            data={
                "name": "Shield+",
                "type_label": "Repellent Toxin",
                "synthesis_duration": 0,
                "aftereffect_ticks": -2,
                "repellent_walk_ticks": -3,
                "energy_cost_per_tick": -5.0,
                "irreversible": "on",
            },
        )
        toggle_diet = await client.post(
            "/api/matrices/diet",
            data={"predator_idx": 0, "flora_idx": 0, "compatible": "toggle"},
        )
        invalid_diet = await client.post(
            "/api/matrices/diet",
            data={"predator_idx": 9, "flora_idx": 9, "compatible": "true"},
        )

        missing_update = await client.put(
            "/api/config/substances/99",
            data={"name": "Missing"},
        )

    assert add_alarm.status_code == 200
    assert add_shield.status_code == 200
    assert add_relay.status_code == 200
    assert "Shield+" in update_resp.text
    assert toggle_diet.status_code == 200
    assert invalid_diet.status_code == 200
    assert missing_update.status_code == 404
    assert draft.diet_matrix[0][0] is False
    assert draft.substance_definitions[1].repellent is True
    assert draft.substance_definitions[1].aftereffect_ticks == 0
    assert draft.substance_definitions[1].repellent_walk_ticks == 0
    assert draft.substance_definitions[1].energy_cost_per_tick == pytest.approx(0.0)
    assert draft.substance_definitions[1].irreversible is True

    draft.substance_definitions[2].precursor_signal_id = 2
    draft_service.add_trigger_rule(
        draft,
        0,
        0,
        1,
        activation_condition={"kind": "substance_active", "substance_id": 1},
    )
    draft_service.add_trigger_rule(
        draft,
        0,
        0,
        2,
        activation_condition={"kind": "substance_active", "substance_id": 2},
    )

    async with _default_client() as client:
        delete_resp = await client.delete("/api/config/substances/1")
        missing_delete = await client.delete("/api/config/substances/99")

    assert delete_resp.status_code == 200
    assert missing_delete.status_code == 404
    assert [definition.substance_id for definition in draft.substance_definitions] == [0, 1]
    assert draft.substance_definitions[1].name == "Relay"
    assert draft.substance_definitions[1].precursor_signal_id == 1
    assert len(draft.trigger_rules) == 1
    assert draft.trigger_rules[0].substance_id == 1
    assert draft.trigger_rules[0].activation_condition == {
        "kind": "substance_active",
        "substance_id": 1,
    }


@pytest.mark.asyncio
async def test_live_dashboard_payload_and_cell_details_include_signals_and_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Validates that live dashboard payload and cell details include signals, mycorrhizal links, and triggered substances.

    This test simulates a live scenario with plant and swarm placements, trigger rules, and substance definitions. It verifies that the dashboard and cell details endpoints report active signals, mycorrhizal links, and triggered/aftereffect states for substances, supporting the scientific requirement for transparent reporting of emergent ecological dynamics and signal propagation in PHIDS.
    """
    monkeypatch.setattr(
        "phids.engine.systems.interaction._choose_neighbour_by_flow_probability",
        lambda swarm, flow_field, width, height, invert=False: (swarm.x, swarm.y),
    )

    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 2, 2, 18.0)
    draft_service.add_plant_placement(draft, 0, 2, 3, 16.0)
    draft_service.add_swarm_placement(draft, 0, 2, 2, 6, 24.0)
    draft.diet_matrix[0][0] = False
    draft.mycorrhizal_growth_interval_ticks = 1
    draft.substance_definitions.append(
        SubstanceDefinition(
            substance_id=0,
            name="Alarm Cloud",
            is_toxin=False,
            synthesis_duration=1,
            aftereffect_ticks=2,
        )
    )
    draft_service.add_trigger_rule(draft, 0, 0, 0, min_predator_population=5)

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load-draft", headers={"HX-Request": "true"})
        assert load_resp.status_code == 200

        step_resp = await client.post("/api/simulation/step")
        assert step_resp.status_code == 200

        dashboard_payload = build_live_dashboard_payload(
            api_main._sim_loop,
            substance_names=api_main._sim_substance_names,
        )
        details_resp = await client.get("/api/ui/cell-details", params={"x": 2, "y": 2})

        from phids.engine.components.swarm import SwarmComponent

        loop = api_main._sim_loop
        assert loop is not None
        swarm_entity = next(iter(loop.world.query(SwarmComponent)))
        swarm = swarm_entity.get_component(SwarmComponent)
        loop.world.move_entity(swarm.entity_id, swarm.x, swarm.y, 0, 0)
        swarm.x = 0
        swarm.y = 0

        second_step_resp = await client.post("/api/simulation/step")
        assert second_step_resp.status_code == 200
        aftereffect_details_resp = await client.get("/api/ui/cell-details", params={"x": 2, "y": 2})

    assert dashboard_payload["tick"] == 1
    assert any(0 in plant["active_signal_ids"] for plant in dashboard_payload["plants"])
    assert dashboard_payload["mycorrhizal_links"]
    assert details_resp.status_code == 200
    details = details_resp.json()
    assert details["mode"] == "live"
    assert details["tick"] == 1
    assert details["signal_concentrations"]
    triggered_alarm_clouds = [
        substance
        for plant in details["plants"]
        for substance in plant["active_substances"]
        if substance["name"] == "Alarm Cloud"
    ]
    assert any(substance["state"] == "triggered" for substance in triggered_alarm_clouds)
    assert details["mycorrhiza"]["link_count"] == 1
    assert details["swarms"][0]["population"] >= 6

    assert aftereffect_details_resp.status_code == 200
    aftereffect_details = aftereffect_details_resp.json()
    assert aftereffect_details["tick"] == 2
    assert aftereffect_details["signal_concentrations"]
    lingering_alarm_clouds = [
        substance
        for plant in aftereffect_details["plants"]
        for substance in plant["active_substances"]
        if substance["name"] == "Alarm Cloud"
    ]
    assert any(substance["state"] == "aftereffect" for substance in lingering_alarm_clouds)
    assert any(
        substance["state"] == "aftereffect" and substance["aftereffect_remaining_ticks"] == 1
        for substance in lingering_alarm_clouds
    )


@pytest.mark.asyncio
async def test_ui_cell_details_rejects_stale_live_tick() -> None:
    """
    Ensures that cell details endpoint rejects requests with stale expected tick in live mode.

    This test verifies that the cell details endpoint returns a 409 status and correct tick information when the expected tick is stale, supporting the scientific requirement for deterministic state synchronization and error reporting in live simulation scenarios.
    """
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 3, 3, 20.0)
    draft_service.add_swarm_placement(draft, 0, 3, 3, 5, 20.0)

    async with _default_client() as client:
        load_resp = await client.post("/api/scenario/load-draft")
        assert load_resp.status_code == 200

        step_resp = await client.post("/api/simulation/step")
        assert step_resp.status_code == 200

        resp = await client.get(
            "/api/ui/cell-details",
            params={"x": 3, "y": 3, "expected_tick": 0},
        )

    assert resp.status_code == 409
    data = resp.json()
    assert data["expected_tick"] == 0
    assert data["tick"] == 1


@pytest.mark.asyncio
async def test_model_diagnostics_and_telemetry_refresh_context() -> None:
    """
    Validates that model diagnostics and telemetry endpoints refresh context after simulation step.

    This test ensures that the diagnostics and telemetry endpoints report updated context after a simulation step, supporting the scientific requirement for transparent reporting of simulation progress, plant death diagnostics, and energy deficit watch in PHIDS.
    """
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 5, 5, 17.0)
    draft_service.add_swarm_placement(draft, 0, 5, 5, 8, 32.0)

    async with _default_client() as client:
        await client.post("/api/scenario/load-draft")
        await client.post("/api/simulation/step")
        model_resp = await client.get("/ui/diagnostics/model")
        telemetry_resp = await client.get("/api/telemetry")

    assert model_resp.status_code == 200
    assert "Latest telemetry" in model_resp.text
    assert "Plant death diagnostics" in model_resp.text
    assert "Energy deficit watch" in model_resp.text
    assert telemetry_resp.status_code == 200
    assert "tick 1" in telemetry_resp.text


@pytest.mark.asyncio
async def test_backend_diagnostics_shows_recent_logs() -> None:
    """
    Ensures that backend diagnostics endpoint displays recent logs for UI diagnostics.

    This test validates that the backend diagnostics endpoint exposes recent log entries, supporting the scientific requirement for transparent error reporting and backend health monitoring in PHIDS UI diagnostics workflows.
    """
    api_main.logger.info("UI diagnostics backend smoke test")

    async with _default_client() as client:
        resp = await client.get("/ui/diagnostics/backend")

    assert resp.status_code == 200
    assert "Recent logs" in resp.text
    assert "UI diagnostics backend smoke test" in resp.text


@pytest.mark.asyncio
async def test_scenario_export_and_import_round_trip_ui() -> None:
    """
    Validates scenario export and import round-trip functionality via the UI endpoints.

    This test ensures that the scenario export and import endpoints correctly serialize and deserialize scenario state, preserving mycorrhizal growth interval and placement attributes. The test supports the scientific requirement for reproducible scenario management and state persistence in PHIDS ecosystem simulation workflows.
    """
    export_path = Path("/tmp/phids-ui-test.json")
    draft = get_draft()
    draft_service.add_plant_placement(draft, 0, 2, 2, 10.0)
    draft_service.add_swarm_placement(draft, 0, 2, 2, 5, 18.0)
    draft.mycorrhizal_growth_interval_ticks = 13

    async with _default_client() as client:
        export_resp = await client.get("/api/scenario/export")
        assert export_resp.status_code == 200
        export_path.write_bytes(export_resp.content)

        with export_path.open("rb") as fh:
            import_resp = await client.post(
                "/api/scenario/import",
                files={"file": ("roundtrip.json", fh, "application/json")},
            )

    assert import_resp.status_code == 200
    assert import_resp.json()["message"] == "Scenario imported."
    assert get_draft().mycorrhizal_growth_interval_ticks == 13
