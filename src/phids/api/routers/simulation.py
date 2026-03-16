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

import asyncio
import contextlib
import json
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

import phids.api.main as api_main
from phids.api.schemas import SimulationConfig, SimulationStatusResponse, WindUpdatePayload
from phids.api.ui_state import (
    DraftState,
    PlacedPlant,
    PlacedSwarm,
    SubstanceDefinition,
    TriggerRule,
    get_draft,
    set_draft,
)
from phids.engine.loop import SimulationLoop

router = APIRouter()


@router.post("/api/scenario/load", summary="Load simulation scenario")
async def load_scenario(config: SimulationConfig) -> dict[str, Any]:
    """Initialize live runtime state from a validated scenario payload.

    The endpoint is the strict ingress boundary between static configuration and executable
    ecological dynamics. Existing background execution is cancelled before loop replacement so
    trophic and signaling trajectories remain single-source and deterministic.

    Args:
        config: Validated simulation configuration crossing the API boundary.

    Returns:
        Confirmation payload containing loaded grid dimensions.
    """
    if api_main._sim_task is not None and not api_main._sim_task.done():
        api_main.logger.info(
            "Cancelling existing background simulation task before loading a new scenario"
        )
        api_main._sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await api_main._sim_task

    api_main._sim_loop = SimulationLoop(config)
    api_main._set_simulation_substance_names(config)
    api_main.logger.info(
        "Scenario loaded: %dx%d grid, %d flora species, %d predator species",
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.predator_species),
    )
    return {
        "message": "Scenario loaded.",
        "grid_width": config.grid_width,
        "grid_height": config.grid_height,
    }


@router.post("/api/simulation/start", summary="Start or resume simulation")
async def start_simulation(request: Request) -> Any:
    """Start or resume asynchronous simulation advancement for the active loop.

    Args:
        request: Incoming HTTP request used to select JSON or HTMX fragment responses.

    Returns:
        Status payload or status-badge fragment, depending on caller context.

    Raises:
        HTTPException: A terminated simulation is asked to restart without reset.
    """
    loop = api_main._get_loop()

    if loop.running and not loop.paused:
        api_main.logger.info("Start requested while simulation was already running")
        if api_main._is_htmx_request(request):
            return HTMLResponse(content=api_main._render_status_badge_html())
        return {"message": "Simulation already running."}

    if loop.terminated:
        api_main.logger.warning(
            "Start requested for a terminated simulation (reason=%s)", loop.termination_reason
        )
        raise HTTPException(status_code=400, detail="Simulation has terminated.")

    loop.start()

    async def _bg() -> None:
        await loop.run()

    api_main._sim_task = asyncio.create_task(_bg())
    api_main.logger.info("Background simulation task created")
    if api_main._is_htmx_request(request):
        return HTMLResponse(content=api_main._render_status_badge_html())
    return {"message": "Simulation started."}


@router.post("/api/simulation/pause", summary="Pause or resume simulation")
async def pause_simulation(request: Request) -> Any:
    """Toggle pause state of the active live simulation loop.

    Args:
        request: Incoming HTTP request used to select JSON or HTMX fragment responses.

    Returns:
        Status payload or status-badge fragment with updated pause state.
    """
    loop = api_main._get_loop()
    loop.pause()
    state = "paused" if loop.paused else "resumed"
    api_main.logger.info("Simulation %s via API", state)
    if api_main._is_htmx_request(request):
        return HTMLResponse(content=api_main._render_status_badge_html())
    return {"message": f"Simulation {state}."}


@router.post("/api/simulation/step", summary="Advance simulation by one tick")
async def step_simulation(request: Request) -> Any:
    """Execute exactly one deterministic tick on the active simulation loop.

    Raises:
        HTTPException: If the simulation is currently running or has already terminated.
    """
    loop = api_main._get_loop()

    if (
        api_main._sim_task is not None
        and not api_main._sim_task.done()
        and loop.running
        and not loop.paused
    ):
        api_main.logger.warning("Single-step requested while simulation is already running")
        raise HTTPException(status_code=400, detail="Pause the simulation before stepping.")

    if loop.terminated:
        api_main.logger.warning(
            "Single-step requested for a terminated simulation (reason=%s)",
            loop.termination_reason,
        )
        raise HTTPException(status_code=400, detail="Simulation has terminated.")

    result = await loop.step()
    api_main.logger.info(
        "Simulation advanced by one tick via API (tick=%d, terminated=%s)",
        loop.tick,
        result.terminated,
    )
    if api_main._is_htmx_request(request):
        return HTMLResponse(content=api_main._render_status_badge_html())
    return {
        "message": "Simulation advanced by one tick.",
        "tick": loop.tick,
        "terminated": loop.terminated,
        "termination_reason": loop.termination_reason,
    }


@router.post("/api/simulation/reset", summary="Reset simulation to the loaded scenario")
async def reset_simulation(request: Request) -> Any:
    """Recreate live runtime state from the loaded baseline scenario.

    Args:
        request: Incoming HTTP request used to select JSON or HTMX fragment responses.

    Returns:
        Status payload or status-badge fragment for the reset state.
    """
    loop = api_main._get_loop()

    if api_main._sim_task is not None and not api_main._sim_task.done():
        api_main.logger.info("Cancelling existing background simulation task before reset")
        api_main._sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await api_main._sim_task

    api_main._sim_loop = SimulationLoop(loop.config)
    api_main._sim_task = None
    api_main._set_simulation_substance_names(loop.config)
    api_main.logger.info("Simulation reset to the loaded scenario")
    if api_main._is_htmx_request(request):
        return HTMLResponse(content=api_main._render_status_badge_html())
    return {"message": "Simulation reset.", "tick": 0}


@router.get(
    "/api/simulation/status",
    response_model=SimulationStatusResponse,
    summary="Get simulation status",
)
async def simulation_status() -> SimulationStatusResponse:
    """Return lifecycle status and tick position for the active simulation.

    Returns:
        Structured lifecycle state for polling and control-plane diagnostics.
    """
    loop = api_main._get_loop()
    return SimulationStatusResponse(
        tick=loop.tick,
        running=loop.running,
        paused=loop.paused,
        terminated=loop.terminated,
        termination_reason=loop.termination_reason,
    )


@router.put("/api/simulation/wind", summary="Update wind vector")
async def update_wind(payload: WindUpdatePayload) -> dict[str, Any]:
    """Update the uniform wind vector field of the active environment.

    Args:
        payload: Requested wind components in simulation coordinate space.

    Returns:
        Confirmation payload echoing the applied wind vector.
    """
    loop = api_main._get_loop()
    loop.update_wind(payload.wind_x, payload.wind_y)
    api_main.logger.info(
        "Wind updated via API to (vx=%.3f, vy=%.3f)", payload.wind_x, payload.wind_y
    )
    return {"message": "Wind updated.", "wind_x": payload.wind_x, "wind_y": payload.wind_y}


@router.get("/api/scenario/export", summary="Export draft as JSON")
async def scenario_export() -> Response:
    """Serialize draft configuration into a downloadable scenario artifact.

    Returns:
        JSON response with attachment headers for scenario persistence.

    Raises:
        HTTPException: Draft state cannot be transformed into a valid schema payload.
    """
    draft = get_draft()
    try:
        config = draft.build_sim_config()
        data = json.dumps(config.model_dump(), indent=2)
    except (ValueError, AttributeError) as exc:
        api_main.logger.warning("Scenario export failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    api_main.logger.info("Draft scenario exported (scenario_name=%s)", draft.scenario_name)
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{draft.scenario_name.replace(" ", "_")}.json"'
            )
        },
    )


@router.post("/api/scenario/import", summary="Import scenario from JSON file")
async def scenario_import(file: UploadFile = File(...)) -> JSONResponse:
    """Parse an uploaded scenario JSON document and replace draft state.

    Args:
        file: Uploaded JSON scenario artifact.

    Returns:
        Confirmation payload with imported grid dimensions.

    Raises:
        HTTPException: Uploaded content fails JSON parsing or scenario-schema validation.
    """
    raw = await file.read()
    try:
        payload = json.loads(raw)
        config = SimulationConfig.model_validate(payload)
    except Exception as exc:
        api_main.logger.warning("Scenario import failed for file %s: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=f"Invalid scenario JSON: {exc}") from exc

    imported_trigger_rules: list[TriggerRule] = []
    imported_substances: list[SubstanceDefinition] = []
    seen_substance_ids: set[int] = set()
    for flora_spec in config.flora_species:
        for trig in flora_spec.triggers:
            imported_trigger_rules.append(
                TriggerRule(
                    flora_species_id=flora_spec.species_id,
                    predator_species_id=trig.predator_species_id,
                    substance_id=trig.substance_id,
                    min_predator_population=trig.min_predator_population,
                    activation_condition=(
                        trig.activation_condition.model_dump(mode="json")
                        if trig.activation_condition is not None
                        else None
                    ),
                )
            )
            if trig.substance_id not in seen_substance_ids:
                seen_substance_ids.add(trig.substance_id)
                imported_substances.append(
                    SubstanceDefinition(
                        substance_id=trig.substance_id,
                        name=f"Substance {trig.substance_id}",
                        is_toxin=trig.is_toxin,
                        lethal=trig.lethal,
                        repellent=trig.repellent,
                        synthesis_duration=trig.synthesis_duration,
                        aftereffect_ticks=trig.aftereffect_ticks,
                        lethality_rate=trig.lethality_rate,
                        repellent_walk_ticks=trig.repellent_walk_ticks,
                        energy_cost_per_tick=trig.energy_cost_per_tick,
                        irreversible=trig.irreversible,
                        precursor_signal_id=(
                            trig.precursor_signal_ids[0]
                            if len(trig.precursor_signal_ids) == 1
                            else trig.precursor_signal_id
                        ),
                        min_predator_population=trig.min_predator_population,
                    )
                )

    new_draft = DraftState(
        scenario_name=(file.filename or "imported").replace(".json", ""),
        grid_width=config.grid_width,
        grid_height=config.grid_height,
        max_ticks=config.max_ticks,
        tick_rate_hz=config.tick_rate_hz,
        wind_x=config.wind_x,
        wind_y=config.wind_y,
        num_signals=config.num_signals,
        num_toxins=config.num_toxins,
        mycorrhizal_inter_species=config.mycorrhizal_inter_species,
        mycorrhizal_connection_cost=config.mycorrhizal_connection_cost,
        mycorrhizal_growth_interval_ticks=config.mycorrhizal_growth_interval_ticks,
        mycorrhizal_signal_velocity=config.mycorrhizal_signal_velocity,
        flora_species=list(config.flora_species),
        predator_species=list(config.predator_species),
        diet_matrix=[list(row) for row in config.diet_matrix.rows],
        trigger_rules=imported_trigger_rules,
        substance_definitions=imported_substances,
        initial_plants=[
            PlacedPlant(species_id=p.species_id, x=p.x, y=p.y, energy=p.energy)
            for p in config.initial_plants
        ],
        initial_swarms=[
            PlacedSwarm(
                species_id=s.species_id,
                x=s.x,
                y=s.y,
                population=s.population,
                energy=s.energy,
            )
            for s in config.initial_swarms
        ],
    )
    set_draft(new_draft)
    api_main.logger.info(
        "Scenario imported into draft (file=%s, grid=%dx%d, flora=%d, predators=%d)",
        file.filename,
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.predator_species),
    )
    return JSONResponse(
        content={
            "message": "Scenario imported.",
            "grid_width": config.grid_width,
            "grid_height": config.grid_height,
        }
    )


@router.post(
    "/api/scenario/load-draft",
    response_class=HTMLResponse,
    summary="Load draft config into simulation engine",
)
async def scenario_load_draft(request: Request) -> Any:
    """Build a validated config from the draft and instantiate a new live loop.

    Args:
        request: Incoming request used for HTMX status-badge rendering.

    Returns:
        Updated status-badge fragment representing live runtime state.

    Raises:
        HTTPException: Draft cannot be transformed into a valid simulation configuration.
    """
    draft = get_draft()
    try:
        config = draft.build_sim_config()
    except (ValueError, Exception) as exc:
        api_main.logger.warning("Draft load into simulation failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if api_main._sim_task is not None and not api_main._sim_task.done():
        api_main.logger.info("Cancelling existing background simulation task before loading draft")
        api_main._sim_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await api_main._sim_task

    api_main._sim_loop = SimulationLoop(config)
    api_main._sim_task = None
    api_main._set_simulation_substance_names(config, draft=draft)
    api_main.logger.info(
        "Draft loaded: %dx%d grid, %d flora, %d predators",
        config.grid_width,
        config.grid_height,
        len(config.flora_species),
        len(config.predator_species),
    )
    return HTMLResponse(content=api_main._render_status_badge_html())
