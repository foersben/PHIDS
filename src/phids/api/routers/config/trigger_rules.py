"""Trigger rules configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.services.draft_service import DraftService
from phids.api.ui_state import (
    ActivationConditionNode,
    DraftState,
    _condition_node_at_path,
    _parse_condition_path,
    get_draft,
)

router = APIRouter()
draft_service = DraftService()


def _render_trigger_rules_partial(request: Request, draft: DraftState) -> Response:
    """Render the canonical trigger-rules partial response."""
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
    )


def _render_placement_list_partial(request: Request, draft: DraftState) -> Response:
    """Render the canonical placement-ledger partial response."""
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


def _flora_update_payload(
    *,
    name: str | None,
    base_energy: float | None,
    max_energy: float | None,
    growth_rate: float | None,
    survival_threshold: float | None,
    reproduction_interval: int | None,
    seed_min_dist: float | None,
    seed_max_dist: float | None,
    seed_energy_cost: float | None,
    camouflage: str | None,
    camouflage_factor: float | None,
) -> dict[str, object]:
    """Collect flora patch fields with deterministic clamping semantics."""
    updates = _flora_update_payload(
        name=name,
        base_energy=base_energy,
        max_energy=max_energy,
        growth_rate=growth_rate,
        survival_threshold=survival_threshold,
        reproduction_interval=reproduction_interval,
        seed_min_dist=seed_min_dist,
        seed_max_dist=seed_max_dist,
        seed_energy_cost=seed_energy_cost,
        camouflage=camouflage,
        camouflage_factor=camouflage_factor,
    )
    return updates


def _herbivore_update_payload(
    *,
    name: str | None,
    energy_min: float | None,
    velocity: int | None,
    consumption_rate: float | None,
    reproduction_energy_divisor: float | None,
    energy_upkeep_per_individual: float | None,
    split_population_threshold: int | None,
) -> dict[str, object]:
    """Collect herbivore patch fields with deterministic clamping semantics."""
    updates = _herbivore_update_payload(
        name=name,
        energy_min=energy_min,
        velocity=velocity,
        consumption_rate=consumption_rate,
        reproduction_energy_divisor=reproduction_energy_divisor,
        energy_upkeep_per_individual=energy_upkeep_per_individual,
        split_population_threshold=split_population_threshold,
    )
    return updates


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
    return _render_trigger_rules_partial(request, draft)


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
    return _render_trigger_rules_partial(request, draft)


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
    return _render_trigger_rules_partial(request, draft)


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
            raise HTTPException(status_code=400, detail="Trigger rule has no activation condition to update.")
        draft_service.set_trigger_rule_activation_condition(
            draft,
            index,
            api_main._default_activation_condition_for_rule(draft, rule, kind),
        )
        return _render_trigger_rules_partial(request, draft)

    try:
        current_node: ActivationConditionNode = (
            _condition_node_at_path(rule.activation_condition, _parse_condition_path(path))
            if path
            else rule.activation_condition
        )

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
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _render_trigger_rules_partial(request, draft)


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
    return _render_trigger_rules_partial(request, draft)


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
    return _render_trigger_rules_partial(request, draft)
