# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Scenario and simulation control router for PHIDS.

This module groups the routes that transition validated configuration data into a live `SimulationLoop` and then control that runtime through deterministic lifecycle operations. The endpoints preserve the draft-versus-live boundary: draft editing occurs in separate builder routes, while this surface performs scenario loading, single-loop execution control, wind mutation, and serialization import/export. The computational objective is strict reproducibility of ecological state trajectories, and the biological objective is controlled experimentation over trophic, signaling, and metabolic dynamics without introducing ad hoc client-side state transitions.
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

    Instead of rendering OOB swaps (which can cause DOM duplication if interrupted), this canonical helper simply tells HTMX to trigger 'updateStatusBadge' and 'updateMainActionBtn' events on the client.
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


def _pick[T](value: T | None, fallback: T) -> T:
    """Return an override value when provided, otherwise retain the draft fallback."""
    return fallback if value is None else value


def _resolve_inter_species(raw_value: str | None, fallback: bool) -> bool:
    """Resolve checkbox string overrides for inter-species mycorrhizal connectivity."""
    return fallback if raw_value is None else raw_value == "on"


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

    This helper enables simulation-control actions to commit pending builder edits in the same request, avoiding stale draft state when users type and click a control button without waiting for autosave round-trips.
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
        grid_width=_pick(grid_width, draft.grid_width),
        grid_height=_pick(grid_height, draft.grid_height),
        max_ticks=_pick(max_ticks, draft.max_ticks),
        tick_rate_hz=_pick(tick_rate_hz, draft.tick_rate_hz),
        wind_x=_pick(wind_x, draft.wind_x),
        wind_y=_pick(wind_y, draft.wind_y),
        num_signals=_pick(num_signals, draft.num_signals),
        num_toxins=_pick(num_toxins, draft.num_toxins),
        z2_flora_species_extinction=_pick(z2_flora_species_extinction, draft.z2_flora_species_extinction),
        z4_herbivore_species_extinction=_pick(
            z4_herbivore_species_extinction,
            draft.z4_herbivore_species_extinction,
        ),
        z6_max_total_flora_energy=_pick(z6_max_total_flora_energy, draft.z6_max_total_flora_energy),
        z7_max_total_herbivore_population=_pick(
            z7_max_total_herbivore_population,
            draft.z7_max_total_herbivore_population,
        ),
        mycorrhizal_inter_species=_resolve_inter_species(
            mycorrhizal_inter_species,
            draft.mycorrhizal_inter_species,
        ),
        mycorrhizal_connection_cost=_pick(mycorrhizal_connection_cost, draft.mycorrhizal_connection_cost),
        mycorrhizal_growth_interval_ticks=_pick(
            mycorrhizal_growth_interval_ticks,
            draft.mycorrhizal_growth_interval_ticks,
        ),
        mycorrhizal_signal_velocity=_pick(mycorrhizal_signal_velocity, draft.mycorrhizal_signal_velocity),
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
