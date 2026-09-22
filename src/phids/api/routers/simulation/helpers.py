# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Simulation routing helpers for PHIDS.

This module groups the routes that transition validated configuration data into a live
`SimulationLoop` and then control that runtime through deterministic lifecycle operations. The
endpoints preserve the draft-versus-live boundary: draft editing occurs in separate builder routes,
while this surface performs scenario loading, single-loop execution control, wind mutation, and
serialization import/export. The computational objective is strict reproducibility of ecological
state trajectories, and the biological objective is controlled experimentation over trophic,
signaling, and metabolic dynamics without introducing ad hoc client-side state transitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, Response, UploadFile

from phids.api.services.draft.biotope import update_biotope as draft_update_biotope
from phids.api.ui_state.state import get_draft

if TYPE_CHECKING:
    from starlette.datastructures import FormData


def _status_badge_fragment() -> Response:
    """Return a 204 No Content response that triggers UI updates.

    Instead of rendering OOB swaps (which can cause DOM duplication if interrupted),
    this canonical helper simply tells HTMX to trigger 'updateStatusBadge' and
    'updateMainActionBtn' events on the client.
    """
    return Response(
        status_code=204,
        headers={"HX-Trigger": "updateStatusBadge, updateMainActionBtn"},
    )


def _form_scalar(form_data: FormData, key: str) -> str | None:
    """Return a scalar form value as string, ignoring file uploads."""
    value = form_data.get(key)
    if value is None or isinstance(value, UploadFile):
        return None
    return str(value)


def _form_int(form_data: FormData, key: str) -> int | None:
    """Parse an optional integer form field with explicit validation failures."""
    raw = _form_scalar(form_data, key)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid integer value for '{key}': {raw!r}",
        ) from exc


def _form_float(form_data: FormData, key: str) -> float | None:
    """Parse an optional float form field with explicit validation failures."""
    raw = _form_scalar(form_data, key)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid float value for '{key}': {raw!r}",
        ) from exc


def _apply_optional_biotope_overrides(
    *,
    grid_width: int | None,
    grid_height: int | None,
    max_ticks: int | None,
    tick_rate_hz: float | None,
    wind_x: float | None,
    wind_y: float | None,
    num_signals: int | None,
    num_toxins: int | None,
    z2_flora_species_extinction: int | None,
    z4_herbivore_species_extinction: int | None,
    z6_max_total_flora_energy: float | None,
    z7_max_total_herbivore_population: int | None,
    mycorrhizal_inter_species: str | None,
    mycorrhizal_connection_cost: float | None,
    mycorrhizal_growth_interval_ticks: int | None,
    mycorrhizal_signal_velocity: int | None,
) -> None:
    """Persist optional biotope form fields into draft state when present.

    This helper enables simulation-control actions to commit pending builder edits
    in the same request, avoiding stale draft state when users type and click a
    control button without waiting for autosave round-trips.
    """
    provided = any(
        value is not None
        for value in (
            grid_width,
            grid_height,
            max_ticks,
            tick_rate_hz,
            wind_x,
            wind_y,
            num_signals,
            num_toxins,
            z2_flora_species_extinction,
            z4_herbivore_species_extinction,
            z6_max_total_flora_energy,
            z7_max_total_herbivore_population,
            mycorrhizal_inter_species,
            mycorrhizal_connection_cost,
            mycorrhizal_growth_interval_ticks,
            mycorrhizal_signal_velocity,
        )
    )

    if not provided:
        return

    draft = get_draft()
    draft_update_biotope(
        draft,
        grid_width=grid_width if grid_width is not None else draft.grid_width,
        grid_height=grid_height if grid_height is not None else draft.grid_height,
        max_ticks=max_ticks if max_ticks is not None else draft.max_ticks,
        tick_rate_hz=tick_rate_hz if tick_rate_hz is not None else draft.tick_rate_hz,
        wind_x=wind_x if wind_x is not None else draft.wind_x,
        wind_y=wind_y if wind_y is not None else draft.wind_y,
        num_signals=num_signals if num_signals is not None else draft.num_signals,
        num_toxins=num_toxins if num_toxins is not None else draft.num_toxins,
        z2_flora_species_extinction=(
            z2_flora_species_extinction
            if z2_flora_species_extinction is not None
            else draft.z2_flora_species_extinction
        ),
        z4_herbivore_species_extinction=(
            z4_herbivore_species_extinction
            if z4_herbivore_species_extinction is not None
            else draft.z4_herbivore_species_extinction
        ),
        z6_max_total_flora_energy=(
            z6_max_total_flora_energy if z6_max_total_flora_energy is not None else draft.z6_max_total_flora_energy
        ),
        z7_max_total_herbivore_population=(
            z7_max_total_herbivore_population
            if z7_max_total_herbivore_population is not None
            else draft.z7_max_total_herbivore_population
        ),
        mycorrhizal_inter_species=(
            (mycorrhizal_inter_species or "off") == "on"
            if mycorrhizal_inter_species is not None
            else draft.mycorrhizal_inter_species
        ),
        mycorrhizal_connection_cost=(
            mycorrhizal_connection_cost
            if mycorrhizal_connection_cost is not None
            else draft.mycorrhizal_connection_cost
        ),
        mycorrhizal_growth_interval_ticks=(
            mycorrhizal_growth_interval_ticks
            if mycorrhizal_growth_interval_ticks is not None
            else draft.mycorrhizal_growth_interval_ticks
        ),
        mycorrhizal_signal_velocity=(
            mycorrhizal_signal_velocity
            if mycorrhizal_signal_velocity is not None
            else draft.mycorrhizal_signal_velocity
        ),
    )


def _apply_optional_biotope_overrides_from_form(form_data: FormData) -> None:
    """Extract known biotope fields from form-data and apply draft overrides."""
    _apply_optional_biotope_overrides(
        grid_width=_form_int(form_data, "grid_width"),
        grid_height=_form_int(form_data, "grid_height"),
        max_ticks=_form_int(form_data, "max_ticks"),
        tick_rate_hz=_form_float(form_data, "tick_rate_hz"),
        wind_x=_form_float(form_data, "wind_x"),
        wind_y=_form_float(form_data, "wind_y"),
        num_signals=_form_int(form_data, "num_signals"),
        num_toxins=_form_int(form_data, "num_toxins"),
        z2_flora_species_extinction=_form_int(form_data, "z2_flora_species_extinction"),
        z4_herbivore_species_extinction=_form_int(form_data, "z4_herbivore_species_extinction"),
        z6_max_total_flora_energy=_form_float(form_data, "z6_max_total_flora_energy"),
        z7_max_total_herbivore_population=_form_int(
            form_data,
            "z7_max_total_herbivore_population",
        ),
        mycorrhizal_inter_species=_form_scalar(form_data, "mycorrhizal_inter_species"),
        mycorrhizal_connection_cost=_form_float(form_data, "mycorrhizal_connection_cost"),
        mycorrhizal_growth_interval_ticks=_form_int(form_data, "mycorrhizal_growth_interval_ticks"),
        mycorrhizal_signal_velocity=_form_int(form_data, "mycorrhizal_signal_velocity"),
    )
