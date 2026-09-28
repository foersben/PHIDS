# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""UI HTML routes for configuration editors and forms."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.presenters.trigger_rules import trigger_rules_template_context
from phids.api.ui_state.state import get_draft

BIO_DB_PATH = Path("src/phids/analytics/bio_database.json")

router = APIRouter()


@router.get("/ui/biotope", response_class=HTMLResponse, summary="Biotope config partial")
async def ui_biotope(request: Request) -> Response:
    """Render the biotope parameter editor.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/biotope_config.html` fragment bound to the current
        draft.
    """
    return api_main.templates.TemplateResponse(
        request,
        "partials/biotope_config.html",
        {"draft": get_draft()},
    )


@router.get("/ui/flora", response_class=HTMLResponse, summary="Flora config partial")
async def ui_flora(request: Request) -> Response:
    """Render the flora-species editor table.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/flora_config.html` fragment with all configured flora
        species rows.
    """
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "partials/flora_config.html",
        {"flora_species": draft.flora_species},
    )


@router.get("/ui/herbivores", response_class=HTMLResponse, summary="Herbivore config partial")
async def ui_herbivores(request: Request) -> Response:
    """Render the herbivore-species editor table.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/herbivore_config.html` fragment with all configured
        herbivore species rows.
    """
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "partials/herbivore_config.html",
        {"herbivore_species": draft.herbivore_species},
    )


@router.get("/ui/substances", response_class=HTMLResponse, summary="Substance config partial")
async def ui_substances(request: Request) -> Response:
    """Render the substance-definition editor.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/substance_config.html` fragment describing named
        signals and toxins in the draft scenario.
    """
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "partials/substance_config.html",
        {"substances": draft.substance_definitions},
    )


@router.get("/ui/diet-matrix", response_class=HTMLResponse, summary="Diet matrix partial")
async def ui_diet_matrix(request: Request) -> Response:
    """Render the herbivore-to-flora compatibility matrix.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/diet_matrix.html` fragment containing the canonical
        edibility matrix.
    """
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "partials/diet_matrix.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "diet_matrix": draft.diet_matrix,
        },
    )


@router.get("/ui/trigger-rules", response_class=HTMLResponse, summary="Trigger rules partial")
async def ui_trigger_rules(request: Request) -> Response:
    """Render the trigger-rule editor."""
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        trigger_rules_template_context(draft),
    )


@router.get("/ui/morphology-defense", response_class=HTMLResponse, summary="Morphology and Defense partial")
async def ui_morphology_defense(request: Request) -> Response:
    """Render the morphology and defense editor partial."""
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "partials/morphology_defense_tab.html",
        {
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "substances": draft.substance_definitions,
            "trigger_rules": draft.trigger_rules,
            "trigger_rule_condition_summary": trigger_rules_template_context(draft).get(
                "trigger_rule_condition_summary"
            ),
            "condition_group_kinds": ["all_of", "any_of"],
            "condition_leaf_kinds": ["herbivore_presence", "substance_active", "environmental_signal"],
        },
    )


@router.get("/ui/placements", response_class=HTMLResponse, summary="Placement editor partial")
async def ui_placements(request: Request) -> Response:
    """Render the spatial placement editor and draft placement ledger.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/placement_editor.html` fragment containing plant and
        swarm placements for the current draft.
    """
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "partials/placement_editor.html",
        {
            "draft": draft,
            "flora_species": draft.flora_species,
            "herbivore_species": draft.herbivore_species,
            "initial_plants": draft.initial_plants,
            "initial_swarms": draft.initial_swarms,
        },
    )


@router.get("/ui/dse", response_class=HTMLResponse, summary="DSE Optimizer partial")
async def ui_dse(request: Request) -> Response:
    """Render the Design Space Exploration (DSE) panel."""
    return api_main.templates.TemplateResponse(
        request,
        "dse/container.html",
        {},
    )
