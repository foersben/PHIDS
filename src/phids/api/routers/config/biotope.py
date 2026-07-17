# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Biotope configuration routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

import phids.api.main as api_main
from phids.api.services.draft.biotope import update_biotope as draft_update_biotope
from phids.api.ui_state import get_draft

router = APIRouter()


@router.post("/api/config/biotope", response_class=HTMLResponse, summary="Update biotope draft config")
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
    signal_decay_factor: Annotated[float, Form()] = 0.85,
    substance_emit_rate: Annotated[float, Form()] = 0.1,
) -> Response:
    """Persist biotope parameters to the draft and return the updated partial.

    Args:
        request: The raw Starlette ASGI request object used for accessing underlying state.
        grid_width: The horizontal bounds of the simulation grid environment.
        grid_height: The vertical bounds of the simulation grid environment.
        max_ticks: The maximum number of simulation ticks (time steps) allowed for the execution budget.
        tick_rate_hz: WebSocket stream rate.
        wind_x: Uniform wind x-component.
        wind_y: Uniform wind y-component.
        num_signals: The total number of distinct signal (e.g. chemotactic gradients) layers maintained.
        num_toxins: The total number of distinct toxin (e.g. harmful localized concentrations) layers maintained.
        z2_flora_species_extinction: Flora species id for Z2 termination (-1 disables).
        z4_herbivore_species_extinction: Herbivore species id for Z4 termination (-1 disables).
        z6_max_total_flora_energy: Total flora energy threshold for Z6 termination (-1 disables).
        z7_max_total_herbivore_population: Herbivore population threshold for Z7 termination
            (-1 disables).
        mycorrhizal_inter_species: Inter-species root-link toggle.
        mycorrhizal_connection_cost: Root-link energy cost.
        mycorrhizal_growth_interval_ticks: Ticks between root-growth attempts.
        mycorrhizal_signal_velocity: Signal hops per tick.
        signal_decay_factor: Per-tick airborne signal retention (0.0-1.0).
        substance_emit_rate: Concentration increment per active emit tick (0.0-1.0).

    Returns:
        TemplateResponse: Updated biotope configuration partial.
    """
    draft = get_draft()
    values_were_clamped = draft_update_biotope(
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
        signal_decay_factor=signal_decay_factor,
        substance_emit_rate=substance_emit_rate,
    )
    api_main.logger.debug(
        (
            "Draft biotope updated (grid=%dx%d, max_ticks=%d, tick_rate_hz=%.2f, wind=(%.3f, %.3f), "
            "signals=%d, toxins=%d, z2=%d, z4=%d, z6=%.3f, z7=%d, mycorrhiza_interval=%d)"
        ),
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
