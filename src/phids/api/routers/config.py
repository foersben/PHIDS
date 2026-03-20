"""Configuration router for draft-state builder mutation routes.

This module defines the HTMX-driven configuration endpoints that mutate `DraftState` during
scenario construction. The routes cover biotope parameters, flora and herbivore species CRUD,
substance definitions, diet-matrix compatibility toggles, trigger-rule condition trees, and
placement-editor operations. The computational purpose is to maintain a rigorously validated draft
representation before any transition into a live deterministic `SimulationLoop`. The biological
purpose is to preserve explicit, inspectable parameterization of growth, predation, signaling,
mycorrhizal coupling, and toxic response mechanisms while retaining server-side authority over all
configuration transformations.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import phids.api.main as api_main
from phids.api.presenters.dashboard import build_draft_mycorrhizal_links
from phids.api.schemas import FloraSpeciesParams, HerbivoreSpeciesParams
from phids.api.services.draft_service import DraftService
from phids.api.ui_state import SubstanceDefinition, get_draft

router = APIRouter()
draft_service = DraftService()


@router.post(
    "/api/config/biotope", response_class=HTMLResponse, summary="Update biotope draft config"
)
async def config_biotope(
    request: Request,
    grid_width: Annotated[int, Form()] = 40,
    grid_height: Annotated[int, Form()] = 40,
    max_ticks: Annotated[int, Form()] = 1000,
    tick_rate_hz: Annotated[float, Form()] = 10.0,
    wind_x: Annotated[float, Form()] = 0.0,
    wind_y: Annotated[float, Form()] = 0.0,
    num_signals: Annotated[int, Form()] = 4,
    num_toxins: Annotated[int, Form()] = 4,
    z2_flora_species_extinction: Annotated[int, Form()] = -1,
    z4_herbivore_species_extinction: Annotated[int, Form()] = -1,
    z6_max_total_flora_energy: Annotated[float, Form()] = -1.0,
    z7_max_total_herbivore_population: Annotated[int, Form()] = -1,
    mycorrhizal_inter_species: Annotated[str, Form()] = "off",
    mycorrhizal_connection_cost: Annotated[float, Form()] = 1.0,
    mycorrhizal_growth_interval_ticks: Annotated[int, Form()] = 8,
    mycorrhizal_signal_velocity: Annotated[int, Form()] = 1,
) -> Response:
    """Persist biotope parameters to the draft and return the updated partial.

    Args:
        request: Starlette request.
        grid_width: Grid width.
        grid_height: Grid height.
        max_ticks: Tick budget.
        tick_rate_hz: WebSocket stream rate.
        wind_x: Uniform wind x-component.
        wind_y: Uniform wind y-component.
        num_signals: Signal layer count.
        num_toxins: Toxin layer count.
        z2_flora_species_extinction: Flora species id for Z2 termination (-1 disables).
        z4_herbivore_species_extinction: Herbivore species id for Z4 termination (-1 disables).
        z6_max_total_flora_energy: Total flora energy threshold for Z6 termination (-1 disables).
        z7_max_total_herbivore_population: Herbivore population threshold for Z7 termination
            (-1 disables).
        mycorrhizal_inter_species: Inter-species root-link toggle.
        mycorrhizal_connection_cost: Root-link energy cost.
        mycorrhizal_growth_interval_ticks: Ticks between root-growth attempts.
        mycorrhizal_signal_velocity: Signal hops per tick.

    Returns:
        TemplateResponse: Updated biotope configuration partial.
    """
    draft = get_draft()
    values_were_clamped = draft_service.update_biotope(
        draft,
        grid_width=grid_width,
        grid_height=grid_height,
        max_ticks=max_ticks,
        tick_rate_hz=tick_rate_hz,
        wind_x=wind_x,
        wind_y=wind_y,
        num_signals=num_signals,
        num_toxins=num_toxins,
        z2_flora_species_extinction=z2_flora_species_extinction,
        z4_herbivore_species_extinction=z4_herbivore_species_extinction,
        z6_max_total_flora_energy=z6_max_total_flora_energy,
        z7_max_total_herbivore_population=z7_max_total_herbivore_population,
        mycorrhizal_inter_species=mycorrhizal_inter_species == "on",
        mycorrhizal_connection_cost=mycorrhizal_connection_cost,
        mycorrhizal_growth_interval_ticks=mycorrhizal_growth_interval_ticks,
        mycorrhizal_signal_velocity=mycorrhizal_signal_velocity,
    )
    api_main.logger.debug(
        "Draft biotope updated (grid=%dx%d, max_ticks=%d, tick_rate_hz=%.2f, wind=(%.3f, %.3f), signals=%d, toxins=%d, z2=%d, z4=%d, z6=%.3f, z7=%d, mycorrhiza_interval=%d)",
        draft.grid_width,
        draft.grid_height,
        draft.max_ticks,
        draft.tick_rate_hz,
        draft.wind_x,
        draft.wind_y,
        draft.num_signals,
        draft.num_toxins,
        draft.z2_flora_species_extinction,
        draft.z4_herbivore_species_extinction,
        draft.z6_max_total_flora_energy,
        draft.z7_max_total_herbivore_population,
        draft.mycorrhizal_growth_interval_ticks,
    )
    if values_were_clamped:
        api_main.logger.warning(
            "Draft biotope values were clamped to valid ranges (requested_grid=%dx%d, applied_grid=%dx%d)",
            grid_width,
            grid_height,
            draft.grid_width,
            draft.grid_height,
        )

    # Keep live runtime wind synchronized with draft edits when a simulation loop exists,
    # so users can observe wind effects without forcing an explicit draft reload.
    if api_main._sim_loop is not None:
        api_main._sim_loop.update_wind(draft.wind_x, draft.wind_y)
        api_main.logger.debug(
            "Live loop wind synchronized from draft biotope update (vx=%.3f, vy=%.3f)",
            draft.wind_x,
            draft.wind_y,
        )

    return api_main.templates.TemplateResponse(
        request,
        "partials/biotope_config.html",
        {"draft": draft},
    )


@router.post("/api/config/flora", response_class=HTMLResponse, summary="Add flora species to draft")
async def config_flora_add(
    request: Request,
    name: Annotated[str, Form()] = "NewFlora",
    base_energy: Annotated[float, Form()] = 10.0,
    max_energy: Annotated[float, Form()] = 100.0,
    growth_rate: Annotated[float, Form()] = 5.0,
    survival_threshold: Annotated[float, Form()] = 1.0,
    reproduction_interval: Annotated[int, Form()] = 10,
    seed_min_dist: Annotated[float, Form()] = 1.0,
    seed_max_dist: Annotated[float, Form()] = 3.0,
    seed_energy_cost: Annotated[float, Form()] = 5.0,
    camouflage: Annotated[str, Form()] = "off",
    camouflage_factor: Annotated[float, Form()] = 1.0,
) -> Response:
    """Add one flora species to the draft and render the updated flora table."""
    draft = get_draft()
    if len(draft.flora_species) >= 16:
        api_main.logger.warning("Rule-of-16 rejected flora creation")
        raise HTTPException(status_code=400, detail="Rule of 16: maximum flora species reached.")
    new_id = len(draft.flora_species)
    params = FloraSpeciesParams(
        species_id=new_id,
        name=name,
        base_energy=base_energy,
        max_energy=max_energy,
        growth_rate=growth_rate,
        survival_threshold=survival_threshold,
        reproduction_interval=reproduction_interval,
        seed_min_dist=seed_min_dist,
        seed_max_dist=seed_max_dist,
        seed_energy_cost=seed_energy_cost,
        camouflage=camouflage == "on",
        camouflage_factor=max(0.0, min(1.0, camouflage_factor)),
        triggers=[],
    )
    draft_service.add_flora(draft, params)
    api_main.logger.info("Flora species added via API (species_id=%d, name=%s)", new_id, name)
    return api_main.templates.TemplateResponse(
        request,
        "partials/flora_config.html",
        {"flora_species": draft.flora_species},
    )


@router.put(
    "/api/config/flora/{species_id}",
    response_class=HTMLResponse,
    summary="Update flora species row",
)
async def config_flora_update(
    request: Request,
    species_id: int,
    name: Annotated[str | None, Form()] = None,
    base_energy: Annotated[float | None, Form()] = None,
    max_energy: Annotated[float | None, Form()] = None,
    growth_rate: Annotated[float | None, Form()] = None,
    survival_threshold: Annotated[float | None, Form()] = None,
    reproduction_interval: Annotated[int | None, Form()] = None,
    seed_min_dist: Annotated[float | None, Form()] = None,
    seed_max_dist: Annotated[float | None, Form()] = None,
    seed_energy_cost: Annotated[float | None, Form()] = None,
    camouflage: Annotated[str | None, Form()] = None,
    camouflage_factor: Annotated[float | None, Form()] = None,
) -> Response:
    """Patch one flora species in the draft and render the updated flora table."""
    draft = get_draft()
    idx = next(
        (
            i
            for i, fp in enumerate(draft.flora_species)
            if isinstance(fp, FloraSpeciesParams) and fp.species_id == species_id
        ),
        None,
    )
    if idx is None:
        api_main.logger.warning("Flora update requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=f"Flora species {species_id} not found.")

    fp = draft.flora_species[idx]
    if not isinstance(fp, FloraSpeciesParams):
        raise HTTPException(status_code=400, detail="Invalid flora species entry in draft state.")
    updates: dict[str, Any] = {}
    if name is not None:
        updates["name"] = name
    if base_energy is not None:
        updates["base_energy"] = base_energy
    if max_energy is not None:
        updates["max_energy"] = max_energy
    if growth_rate is not None:
        updates["growth_rate"] = growth_rate
    if survival_threshold is not None:
        updates["survival_threshold"] = survival_threshold
    if reproduction_interval is not None:
        updates["reproduction_interval"] = reproduction_interval
    if seed_min_dist is not None:
        updates["seed_min_dist"] = seed_min_dist
    if seed_max_dist is not None:
        updates["seed_max_dist"] = seed_max_dist
    if seed_energy_cost is not None:
        updates["seed_energy_cost"] = seed_energy_cost
    if camouflage is not None:
        updates["camouflage"] = camouflage == "on"
    if camouflage_factor is not None:
        updates["camouflage_factor"] = max(0.0, min(1.0, camouflage_factor))

    draft.flora_species[idx] = fp.model_copy(update=updates)
    api_main.logger.debug(
        "Flora species updated via API (species_id=%d, fields=%s)", species_id, sorted(updates)
    )
    return api_main.templates.TemplateResponse(
        request,
        "partials/flora_config.html",
        {"flora_species": draft.flora_species},
    )


@router.delete(
    "/api/config/flora/{species_id}", response_class=HTMLResponse, summary="Delete flora species"
)
async def config_flora_delete(species_id: int) -> HTMLResponse:
    """Remove one flora species from the draft."""
    draft = get_draft()
    try:
        draft_service.remove_flora(draft, species_id)
    except ValueError as exc:
        api_main.logger.warning("Flora delete requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(content="")


@router.post(
    "/api/config/herbivores", response_class=HTMLResponse, summary="Add herbivore species to draft"
)
async def config_herbivore_add(
    request: Request,
    name: Annotated[str, Form()] = "NewHerbivore",
    energy_min: Annotated[float, Form()] = 5.0,
    velocity: Annotated[int, Form()] = 2,
    consumption_rate: Annotated[float, Form()] = 10.0,
    reproduction_energy_divisor: Annotated[float, Form()] = 1.0,
    energy_upkeep_per_individual: Annotated[float, Form()] = 0.05,
    split_population_threshold: Annotated[int, Form()] = 0,
) -> Response:
    """Add one herbivore species to the draft and render the updated herbivore table."""
    draft = get_draft()
    if len(draft.herbivore_species) >= 16:
        api_main.logger.warning("Rule-of-16 rejected herbivore creation")
        raise HTTPException(
            status_code=400, detail="Rule of 16: maximum herbivore species reached."
        )
    new_id = len(draft.herbivore_species)
    params = HerbivoreSpeciesParams(
        species_id=new_id,
        name=name,
        energy_min=energy_min,
        velocity=velocity,
        consumption_rate=consumption_rate,
        reproduction_energy_divisor=max(1.0, reproduction_energy_divisor),
        energy_upkeep_per_individual=energy_upkeep_per_individual,
        split_population_threshold=split_population_threshold,
    )
    draft_service.add_herbivore(draft, params)
    api_main.logger.info("Herbivore species added via API (species_id=%d, name=%s)", new_id, name)
    return api_main.templates.TemplateResponse(
        request,
        "partials/herbivore_config.html",
        {"herbivore_species": draft.herbivore_species},
    )


@router.put(
    "/api/config/herbivores/{species_id}",
    response_class=HTMLResponse,
    summary="Update herbivore species row",
)
async def config_herbivore_update(
    request: Request,
    species_id: int,
    name: Annotated[str | None, Form()] = None,
    energy_min: Annotated[float | None, Form()] = None,
    velocity: Annotated[int | None, Form()] = None,
    consumption_rate: Annotated[float | None, Form()] = None,
    reproduction_energy_divisor: Annotated[float | None, Form()] = None,
    energy_upkeep_per_individual: Annotated[float | None, Form()] = None,
    split_population_threshold: Annotated[int | None, Form()] = None,
) -> Response:
    """Patch one herbivore species in the draft and render the updated herbivore table."""
    draft = get_draft()
    idx = next(
        (
            i
            for i, pp in enumerate(draft.herbivore_species)
            if isinstance(pp, HerbivoreSpeciesParams) and pp.species_id == species_id
        ),
        None,
    )
    if idx is None:
        api_main.logger.warning("Herbivore update requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=f"Herbivore species {species_id} not found.")

    pp = draft.herbivore_species[idx]
    if not isinstance(pp, HerbivoreSpeciesParams):
        raise HTTPException(
            status_code=400, detail="Invalid herbivore species entry in draft state."
        )
    updates: dict[str, Any] = {}
    if name is not None:
        updates["name"] = name
    if energy_min is not None:
        updates["energy_min"] = energy_min
    if velocity is not None:
        updates["velocity"] = velocity
    if consumption_rate is not None:
        updates["consumption_rate"] = consumption_rate
    if reproduction_energy_divisor is not None:
        updates["reproduction_energy_divisor"] = max(1.0, reproduction_energy_divisor)
    if energy_upkeep_per_individual is not None:
        updates["energy_upkeep_per_individual"] = energy_upkeep_per_individual
    if split_population_threshold is not None:
        updates["split_population_threshold"] = split_population_threshold

    draft.herbivore_species[idx] = pp.model_copy(update=updates)
    api_main.logger.debug(
        "Herbivore species updated via API (species_id=%d, fields=%s)", species_id, sorted(updates)
    )
    return api_main.templates.TemplateResponse(
        request,
        "partials/herbivore_config.html",
        {"herbivore_species": draft.herbivore_species},
    )


@router.delete(
    "/api/config/herbivores/{species_id}",
    response_class=HTMLResponse,
    summary="Delete herbivore species",
)
async def config_herbivore_delete(species_id: int) -> HTMLResponse:
    """Remove one herbivore species from the draft."""
    draft = get_draft()
    try:
        draft_service.remove_herbivore(draft, species_id)
    except ValueError as exc:
        api_main.logger.warning("Herbivore delete requested for unknown species_id=%d", species_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(content="")


@router.post(
    "/api/config/substances",
    response_class=HTMLResponse,
    summary="Add substance definition to draft",
)
async def config_substance_add(
    request: Request,
    name: Annotated[str, Form()] = "Signal",
    is_toxin: Annotated[str, Form()] = "false",
    lethal: Annotated[str, Form()] = "false",
    repellent: Annotated[str, Form()] = "false",
    synthesis_duration: Annotated[int, Form()] = 3,
    aftereffect_ticks: Annotated[int, Form()] = 0,
    lethality_rate: Annotated[float, Form()] = 0.0,
    repellent_walk_ticks: Annotated[int, Form()] = 3,
    energy_cost_per_tick: Annotated[float, Form()] = 1.0,
    irreversible: Annotated[str, Form()] = "false",
) -> Response:
    """Add one substance definition to the draft and render the updated substance table."""
    draft = get_draft()
    try:
        definition: SubstanceDefinition = draft_service.add_substance(
            draft,
            name=name,
            is_toxin=is_toxin,
            lethal=lethal,
            repellent=repellent,
            synthesis_duration=synthesis_duration,
            aftereffect_ticks=aftereffect_ticks,
            lethality_rate=lethality_rate,
            repellent_walk_ticks=repellent_walk_ticks,
            energy_cost_per_tick=energy_cost_per_tick,
            irreversible=irreversible,
        )
    except ValueError as exc:
        api_main.logger.warning("Rule-of-16 rejected substance creation")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    api_main.logger.info(
        "Substance added via API (substance_id=%d, name=%s, is_toxin=%s)",
        definition.substance_id,
        definition.name,
        definition.is_toxin,
    )
    return api_main.templates.TemplateResponse(
        request,
        "partials/substance_config.html",
        {"substances": draft.substance_definitions},
    )


@router.put(
    "/api/config/substances/{substance_id}",
    response_class=HTMLResponse,
    summary="Update substance definition row",
)
async def config_substance_update(
    request: Request,
    substance_id: int,
    name: Annotated[str | None, Form()] = None,
    type_label: Annotated[str | None, Form()] = None,
    synthesis_duration: Annotated[int | None, Form()] = None,
    aftereffect_ticks: Annotated[int | None, Form()] = None,
    lethality_rate: Annotated[float | None, Form()] = None,
    repellent_walk_ticks: Annotated[int | None, Form()] = None,
    energy_cost_per_tick: Annotated[float | None, Form()] = None,
    irreversible: Annotated[str | None, Form()] = None,
) -> Response:
    """Patch one substance definition in the draft and render the updated table."""
    draft = get_draft()
    try:
        sd: SubstanceDefinition = draft_service.update_substance(
            draft,
            substance_id,
            name=name,
            type_label=type_label,
            synthesis_duration=synthesis_duration,
            aftereffect_ticks=aftereffect_ticks,
            lethality_rate=lethality_rate,
            repellent_walk_ticks=repellent_walk_ticks,
            energy_cost_per_tick=energy_cost_per_tick,
            irreversible=irreversible,
        )
    except ValueError as exc:
        api_main.logger.warning(
            "Substance update requested for unknown substance_id=%d", substance_id
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    api_main.logger.debug(
        "Substance updated via API (substance_id=%d, name=%s)", substance_id, sd.name
    )

    return api_main.templates.TemplateResponse(
        request,
        "partials/substance_config.html",
        {"substances": draft.substance_definitions},
    )


@router.delete(
    "/api/config/substances/{substance_id}",
    response_class=HTMLResponse,
    summary="Delete substance definition",
)
async def config_substance_delete(substance_id: int) -> HTMLResponse:
    """Remove one substance definition from the draft."""
    draft = get_draft()
    try:
        draft_service.remove_substance(draft, substance_id)
    except ValueError as exc:
        api_main.logger.warning(
            "Substance delete requested for unknown substance_id=%d", substance_id
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    api_main.logger.info("Substance deleted via API (substance_id=%d)", substance_id)
    return HTMLResponse(content="")


@router.post("/api/matrices/diet", response_class=HTMLResponse, summary="Toggle diet matrix cell")
async def matrix_diet(
    request: Request,
    herbivore_idx: Annotated[int, Form()],
    flora_idx: Annotated[int, Form()],
    compatible: Annotated[str, Form()] = "toggle",
) -> Response:
    """Toggle or set one diet compatibility cell in the draft matrix."""
    draft = get_draft()
    updated_value = draft_service.set_diet_compatibility(
        draft,
        herbivore_idx,
        flora_idx,
        compatible,
    )
    if updated_value is not None:
        api_main.logger.debug(
            "Diet matrix updated (herbivore_idx=%d, flora_idx=%d, compatible=%s)",
            herbivore_idx,
            flora_idx,
            updated_value,
        )
    else:
        api_main.logger.warning(
            "Diet matrix update ignored for out-of-range indices (herbivore_idx=%d, flora_idx=%d)",
            herbivore_idx,
            flora_idx,
        )
    return api_main.templates.TemplateResponse(
        request,
        "partials/diet_matrix.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "diet_matrix": draft.diet_matrix,
        },
    )


@router.post("/api/config/trigger-rules", response_class=HTMLResponse, summary="Add a trigger rule")
async def config_trigger_rule_add(
    request: Request,
    flora_species_id: Annotated[int, Form()],
    herbivore_species_id: Annotated[int, Form()],
    substance_id: Annotated[int, Form()],
    min_herbivore_population: Annotated[int, Form()] = 5,
    activation_condition_json: Annotated[str, Form()] = "",
) -> Response:
    """Add one trigger rule to the draft and render the updated trigger-rule table."""
    draft = get_draft()
    draft_service.add_trigger_rule(
        draft,
        flora_species_id=flora_species_id,
        herbivore_species_id=herbivore_species_id,
        substance_id=substance_id,
        min_herbivore_population=max(1, min_herbivore_population),
        activation_condition=api_main._parse_activation_condition_json(activation_condition_json),
    )
    api_main.logger.info(
        "Trigger rule added via API (flora_species_id=%d, herbivore_species_id=%d, substance_id=%d)",
        flora_species_id,
        herbivore_species_id,
        substance_id,
    )
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
    )


@router.put(
    "/api/config/trigger-rules/{index}",
    response_class=HTMLResponse,
    summary="Update a trigger rule",
)
async def config_trigger_rule_update(
    request: Request,
    index: int,
    flora_species_id: Annotated[int | None, Form()] = None,
    herbivore_species_id: Annotated[int | None, Form()] = None,
    substance_id: Annotated[int | None, Form()] = None,
    min_herbivore_population: Annotated[int | None, Form()] = None,
    activation_condition_json: Annotated[str | None, Form()] = None,
) -> Response:
    """Update one trigger rule in the draft and render the updated trigger-rule table."""
    draft = get_draft()
    if index < 0 or index >= len(draft.trigger_rules):
        api_main.logger.warning("Trigger rule update requested for unknown index=%d", index)
        raise HTTPException(status_code=404, detail=f"Trigger rule {index} not found.")

    draft_service.update_trigger_rule(
        draft,
        index,
        flora_species_id=flora_species_id,
        herbivore_species_id=herbivore_species_id,
        substance_id=substance_id,
        min_herbivore_population=min_herbivore_population,
        activation_condition=(
            api_main._parse_activation_condition_json(activation_condition_json)
            if activation_condition_json is not None
            else None
        ),
    )
    api_main.logger.debug("Trigger rule updated via API (index=%d)", index)
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
    )


@router.post(
    "/api/config/trigger-rules/{index}/condition/root",
    response_class=HTMLResponse,
    summary="Create or replace a trigger rule root condition",
)
async def config_trigger_rule_condition_root(
    request: Request,
    index: int,
    node_kind: Annotated[str, Form()],
) -> Response:
    """Create or replace the root activation-condition node for one trigger rule."""
    draft = get_draft()
    rule = api_main._trigger_rule_by_index(draft, index)
    draft_service.set_trigger_rule_activation_condition(
        draft,
        index,
        api_main._default_activation_condition_for_rule(draft, rule, node_kind),
    )
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
    )


@router.post(
    "/api/config/trigger-rules/{index}/condition/child",
    response_class=HTMLResponse,
    summary="Append a child node to a trigger-rule condition group",
)
async def config_trigger_rule_condition_child_add(
    request: Request,
    index: int,
    node_kind: Annotated[str, Form()],
    parent_path: Annotated[str, Form()] = "",
) -> Response:
    """Append one child activation-condition node to a group node."""
    draft = get_draft()
    rule = api_main._trigger_rule_by_index(draft, index)
    try:
        draft_service.append_trigger_rule_condition_child(
            draft,
            index,
            parent_path,
            api_main._default_activation_condition_for_rule(draft, rule, node_kind),
        )
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
    )


@router.put(
    "/api/config/trigger-rules/{index}/condition/node",
    response_class=HTMLResponse,
    summary="Update one node in a trigger-rule condition tree",
)
async def config_trigger_rule_condition_node_update(
    request: Request,
    index: int,
    path: Annotated[str, Form()],
    kind: Annotated[str | None, Form()] = None,
    herbivore_species_id: Annotated[int | None, Form()] = None,
    min_herbivore_population: Annotated[int | None, Form()] = None,
    substance_id: Annotated[int | None, Form()] = None,
    signal_id: Annotated[int | None, Form()] = None,
    min_concentration: Annotated[float | None, Form()] = None,
) -> Response:
    """Update or replace one node in a trigger-rule activation-condition tree."""
    draft = get_draft()
    rule = api_main._trigger_rule_by_index(draft, index)

    if rule.activation_condition is None:
        if kind is None or path:
            raise HTTPException(
                status_code=400, detail="Trigger rule has no activation condition to update."
            )
        draft_service.set_trigger_rule_activation_condition(
            draft,
            index,
            api_main._default_activation_condition_for_rule(draft, rule, kind),
        )
        return api_main.templates.TemplateResponse(
            request,
            "partials/trigger_rules.html",
            api_main._trigger_rules_template_context(draft),
        )

    try:
        current_node: dict[str, Any] = rule.activation_condition
        if path:
            path_indices = [int(part) for part in path.split(".") if part != ""]
            for child_index in path_indices:
                children = current_node.get("conditions")
                if current_node.get("kind") not in {"all_of", "any_of"} or not isinstance(
                    children, list
                ):
                    raise IndexError("Condition path traversed into a non-group node.")
                next_node = children[child_index]
                if not isinstance(next_node, dict):
                    raise IndexError("Condition path resolved to an invalid child node.")
                current_node = next_node

        if kind is not None and current_node.get("kind") != kind:
            replacement = api_main._default_activation_condition_for_rule(draft, rule, kind)
            draft_service.replace_trigger_rule_condition_node(draft, index, path, replacement)
        else:
            updates: dict[str, object] = {}
            if current_node.get("kind") == "herbivore_presence":
                if herbivore_species_id is not None:
                    updates["herbivore_species_id"] = herbivore_species_id
                if min_herbivore_population is not None:
                    updates["min_herbivore_population"] = max(1, min_herbivore_population)
            elif current_node.get("kind") == "substance_active":
                if substance_id is not None:
                    updates["substance_id"] = substance_id
            elif current_node.get("kind") == "environmental_signal":
                if signal_id is not None:
                    updates["signal_id"] = signal_id
                if min_concentration is not None:
                    updates["min_concentration"] = max(0.0, min_concentration)
            elif current_node.get("kind") in {"all_of", "any_of"} and kind is not None:
                updates["kind"] = kind

            if updates:
                draft_service.update_trigger_rule_condition_node(draft, index, path, **updates)
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
    )


@router.post(
    "/api/config/trigger-rules/{index}/condition/delete",
    response_class=HTMLResponse,
    summary="Delete a node from a trigger-rule condition tree",
)
async def config_trigger_rule_condition_delete(
    request: Request,
    index: int,
    path: Annotated[str, Form()] = "",
) -> Response:
    """Delete one trigger-rule condition node or clear the whole condition tree."""
    draft = get_draft()
    api_main._trigger_rule_by_index(draft, index)
    try:
        draft_service.delete_trigger_rule_condition_node(draft, index, path)
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
    )


@router.delete(
    "/api/config/trigger-rules/{index}",
    response_class=HTMLResponse,
    summary="Delete a trigger rule",
)
async def config_trigger_rule_delete(request: Request, index: int) -> Response:
    """Remove one trigger rule from the draft and render the updated trigger table."""
    draft = get_draft()
    try:
        draft_service.remove_trigger_rule(draft, index)
    except IndexError as exc:
        api_main.logger.warning("Trigger rule delete requested for unknown index=%d", index)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
    )


@router.get("/api/config/placements/data", summary="Get placement data as JSON")
async def placement_data() -> JSONResponse:
    """Return draft placement data and inferred root links for canvas rendering."""
    draft = get_draft()
    plants = [
        {"idx": i, "species_id": p.species_id, "x": p.x, "y": p.y, "energy": p.energy}
        for i, p in enumerate(draft.initial_plants)
    ]
    swarms = [
        {
            "idx": i,
            "species_id": s.species_id,
            "x": s.x,
            "y": s.y,
            "population": s.population,
            "energy": s.energy,
        }
        for i, s in enumerate(draft.initial_swarms)
    ]
    flora = [
        {"species_id": getattr(fp, "species_id", i), "name": getattr(fp, "name", f"Flora {i}")}
        for i, fp in enumerate(draft.flora_species)
    ]
    herbivores = [
        {
            "species_id": getattr(hp, "species_id", i),
            "name": getattr(hp, "name", f"Herb {i}"),
        }
        for i, hp in enumerate(draft.herbivore_species)
    ]
    mycorrhizal_links = build_draft_mycorrhizal_links(draft)
    return JSONResponse(
        content={
            "plants": plants,
            "swarms": swarms,
            "grid_width": draft.grid_width,
            "grid_height": draft.grid_height,
            "flora_species": flora,
            "herbivore_species": herbivores,
            "mycorrhizal_links": mycorrhizal_links,
        }
    )


@router.post(
    "/api/config/placements/plant", response_class=HTMLResponse, summary="Place a plant on the grid"
)
async def config_placement_plant_add(
    request: Request,
    species_id: Annotated[int, Form()],
    x: Annotated[int, Form()],
    y: Annotated[int, Form()],
    energy: Annotated[float, Form()] = 10.0,
) -> Response:
    """Create one plant placement and render the updated placement ledger."""
    draft = get_draft()
    x = max(0, min(draft.grid_width - 1, x))
    y = max(0, min(draft.grid_height - 1, y))
    draft_service.add_plant_placement(draft, species_id, x, y, max(0.1, energy))
    api_main.logger.info(
        "Plant placement added via API (species_id=%d, x=%d, y=%d)", species_id, x, y
    )
    return api_main.templates.TemplateResponse(
        request,
        "partials/placement_list.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "initial_plants": draft.initial_plants,
            "initial_swarms": draft.initial_swarms,
        },
    )


@router.post(
    "/api/config/placements/swarm", response_class=HTMLResponse, summary="Place a swarm on the grid"
)
async def config_placement_swarm_add(
    request: Request,
    species_id: Annotated[int, Form()],
    x: Annotated[int, Form()],
    y: Annotated[int, Form()],
    population: Annotated[int, Form()] = 10,
    energy: Annotated[float, Form()] = 50.0,
) -> Response:
    """Create one swarm placement and render the updated placement ledger."""
    draft = get_draft()
    x = max(0, min(draft.grid_width - 1, x))
    y = max(0, min(draft.grid_height - 1, y))
    draft_service.add_swarm_placement(
        draft,
        species_id,
        x,
        y,
        max(1, population),
        max(0.1, energy),
    )
    api_main.logger.info(
        "Swarm placement added via API (species_id=%d, x=%d, y=%d, population=%d)",
        species_id,
        x,
        y,
        max(1, population),
    )
    return api_main.templates.TemplateResponse(
        request,
        "partials/placement_list.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "initial_plants": draft.initial_plants,
            "initial_swarms": draft.initial_swarms,
        },
    )


@router.delete(
    "/api/config/placements/plant/{index}",
    response_class=HTMLResponse,
    summary="Remove a placed plant",
)
async def config_placement_plant_delete(request: Request, index: int) -> Response:
    """Remove one plant placement and render the updated placement ledger."""
    draft = get_draft()
    try:
        draft_service.remove_plant_placement(draft, index)
    except IndexError as exc:
        api_main.logger.warning("Plant placement delete requested for unknown index=%d", index)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return api_main.templates.TemplateResponse(
        request,
        "partials/placement_list.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "initial_plants": draft.initial_plants,
            "initial_swarms": draft.initial_swarms,
        },
    )


@router.delete(
    "/api/config/placements/swarm/{index}",
    response_class=HTMLResponse,
    summary="Remove a placed swarm",
)
async def config_placement_swarm_delete(request: Request, index: int) -> Response:
    """Remove one swarm placement and render the updated placement ledger."""
    draft = get_draft()
    try:
        draft_service.remove_swarm_placement(draft, index)
    except IndexError as exc:
        api_main.logger.warning("Swarm placement delete requested for unknown index=%d", index)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return api_main.templates.TemplateResponse(
        request,
        "partials/placement_list.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "initial_plants": draft.initial_plants,
            "initial_swarms": draft.initial_swarms,
        },
    )


@router.post(
    "/api/config/placements/clear", response_class=HTMLResponse, summary="Clear all placements"
)
async def config_placements_clear(request: Request) -> Response:
    """Clear all plant and swarm placements and render the updated placement ledger."""
    draft = get_draft()
    draft_service.clear_placements(draft)
    api_main.logger.info("All draft placements cleared via API")
    return api_main.templates.TemplateResponse(
        request,
        "partials/placement_list.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "initial_plants": draft.initial_plants,
            "initial_swarms": draft.initial_swarms,
        },
    )
