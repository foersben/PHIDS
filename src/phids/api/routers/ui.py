"""UI HTML route partition for the PHIDS control surface.

This module contains the server-rendered HTML endpoints that drive the HTMX and Jinja control
centre. The extraction isolates view assembly from the application bootstrap logic while keeping
`phids.api.main` as the canonical owner of live runtime state, shared helper functions, and
WebSocket orchestration. The resulting boundary is intentionally conservative: the router renders
partials and page shells, but it does not alter the draft-versus-live transition semantics that are
central to deterministic ecological experimentation. By retaining server-side rendering, the module
continues to expose biologically meaningful state such as telemetry summaries, metabolic deficit
watchlists, and mycorrhizal placement previews without moving those calculations into brittle
browser-side replicas.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.ui_state import get_draft
from phids.shared.logging_config import get_recent_logs

router = APIRouter()


@router.get("/ui/batch", response_class=HTMLResponse, summary="Batch runner dashboard")
async def ui_batch_dashboard(request: Request) -> Response:
    """Render the Monte Carlo batch runner dashboard shell.

    Args:
        request: FastAPI request object used by Jinja to resolve URL and template context state.

    Returns:
        TemplateResponse: Rendered `batch_dashboard.html` surface for batch orchestration and
        aggregate inspection.
    """
    return api_main.templates.TemplateResponse(request, "batch_dashboard.html")


@router.get("/ui/diagnostics/model", response_class=HTMLResponse, summary="Diagnostics model tab")
async def ui_diagnostics_model(request: Request) -> Response:
    """Render live ecological counters and deficit diagnostics.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/diagnostics_model.html` fragment populated from live
        telemetry and draft metadata.
    """
    return api_main.templates.TemplateResponse(
        request,
        "partials/diagnostics_model.html",
        {
            "draft": get_draft(),
            "live_summary": api_main._build_live_summary(),
            "latest_metrics": api_main._sim_loop.telemetry.get_latest_metrics()
            if api_main._sim_loop is not None
            else None,
            "energy_deficit_swarms": api_main._build_energy_deficit_swarms(),
        },
    )


@router.get(
    "/ui/diagnostics/frontend", response_class=HTMLResponse, summary="Diagnostics frontend tab"
)
async def ui_diagnostics_frontend(request: Request) -> Response:
    """Render the browser-observation diagnostics shell.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/diagnostics_frontend.html` fragment.
    """
    return api_main.templates.TemplateResponse(request, "partials/diagnostics_frontend.html")


@router.get(
    "/ui/diagnostics/backend", response_class=HTMLResponse, summary="Diagnostics backend tab"
)
async def ui_diagnostics_backend(request: Request) -> Response:
    """Render recent structured backend logs for operator inspection.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/diagnostics_backend.html` fragment with bounded recent
        log context.
    """
    return api_main.templates.TemplateResponse(
        request,
        "partials/diagnostics_backend.html",
        {"recent_logs": get_recent_logs(limit=120)},
    )


@router.get("/", response_class=HTMLResponse, summary="Main UI")
async def root(request: Request) -> Response:
    """Render the PHIDS control-centre root page.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `index.html` page shell seeded with the current draft scenario
        name.
    """
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "index.html",
        {
            "scenario_name": draft.scenario_name,
            "default_tick_rate_hz": draft.tick_rate_hz,
        },
    )


@router.get("/ui/dashboard", response_class=HTMLResponse, summary="Dashboard partial")
async def ui_dashboard(request: Request) -> Response:
    """Render the live dashboard partial.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/dashboard.html` fragment.
    """
    return api_main.templates.TemplateResponse(request, "partials/dashboard.html")


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
    """Render the trigger-rule editor.

    Args:
        request: FastAPI request object used by the template renderer.

    Returns:
        TemplateResponse: Rendered `partials/trigger_rules.html` fragment populated from the draft
        rule set and activation-condition tree summaries.
    """
    draft = get_draft()
    return api_main.templates.TemplateResponse(
        request,
        "partials/trigger_rules.html",
        api_main._trigger_rules_template_context(draft),
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
