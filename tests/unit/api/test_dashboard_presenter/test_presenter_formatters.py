# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for low-level dashboard formatters, condition builders, and coordinate guards."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from phids.api.presenters.dashboard import (
    _live_substance_state_payload,
    validate_cell_coordinates,
)
from phids.api.schemas.placement import InitialPlantPlacement, InitialSwarmPlacement
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreResistancesSchema,
    HerbivoreSpeciesParams,
)
from phids.api.schemas.triggers import PassiveDefensesSchema, TriggerConditionSchema
from phids.api.ui_state.state import reset_draft


def _flora(species_id: int, *, triggers: list[TriggerConditionSchema] | None = None) -> FloraSpeciesParams:
    """Construct a minimal FloraSpeciesParams fixture for testing."""
    return FloraSpeciesParams(
        species_id=species_id,
        name=f"flora-{species_id}",
        base_energy=10.0,
        max_energy=20.0,
        growth_rate=2.0,
        survival_threshold=1.0,
        reproduction_interval=2,
        seed_min_dist=1.0,
        seed_max_dist=2.0,
        seed_energy_cost=1.0,
        triggers=triggers or [],
        passive_defenses=PassiveDefensesSchema(mechanical_damage_per_bite=0.0, digestibility_modifier=1.0),
    )


def _herbivore(species_id: int) -> HerbivoreSpeciesParams:
    """Construct a minimal HerbivoreSpeciesParams fixture for testing."""
    return HerbivoreSpeciesParams(
        species_id=species_id,
        name=f"herbivore-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        reproduction_energy_divisor=2.0,
        resistances=HerbivoreResistancesSchema(),
    )


def _minimal_config(
    *,
    x: int = 2,
    y: int = 2,
    num_signals: int = 1,
    num_toxins: int = 1,
    triggers: list[TriggerConditionSchema] | None = None,
) -> SimulationConfig:
    """Build a minimal SimulationConfig with one plant and one swarm at (x, y)."""
    return SimulationConfig(
        grid_width=16,
        grid_height=16,
        max_ticks=20,
        tick_rate_hz=20.0,
        num_signals=num_signals,
        num_toxins=num_toxins,
        flora_species=[_flora(0, triggers=triggers)],
        herbivore_species=[_herbivore(0)],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=x, y=y, energy=10.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=x, y=y, population=4, energy=5.0)],
        mycorrhizal_growth_interval_ticks=6,
    )


@pytest.fixture(autouse=True)
def _reset_draft_state() -> None:
    """Reset draft singleton to a pristine state before each test."""
    reset_draft()


def test_validate_cell_coordinates_accepts_valid_cell() -> None:
    """Verifies that in-bounds coordinates do not raise exception."""
    validate_cell_coordinates(0, 0, 8, 8)
    validate_cell_coordinates(7, 7, 8, 8)
    validate_cell_coordinates(3, 5, 8, 8)


def test_validate_cell_coordinates_rejects_out_of_bounds() -> None:
    """Verifies that out-of-bounds coordinates raise HTTP 404."""
    with pytest.raises(HTTPException) as exc_info:
        validate_cell_coordinates(8, 0, 8, 8)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException):
        validate_cell_coordinates(0, 8, 8, 8)

    with pytest.raises(HTTPException):
        validate_cell_coordinates(-1, 0, 8, 8)


@pytest.mark.parametrize(
    ("kwargs", "expected_state"),
    [
        (
            dict(
                is_toxin=False,
                active=False,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
                snapshot_only=True,
            ),
            "field_snapshot",
        ),
        (
            dict(
                is_toxin=False,
                active=False,
                triggered_this_tick=False,
                synthesis_remaining=2,
                aftereffect_remaining_ticks=0,
            ),
            "synthesizing",
        ),
        (
            dict(
                is_toxin=False,
                active=True,
                triggered_this_tick=True,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "triggered",
        ),
        (
            dict(
                is_toxin=False,
                active=True,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=3,
            ),
            "aftereffect",
        ),
        (
            dict(
                is_toxin=True,
                active=True,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "active",
        ),
        (
            dict(
                is_toxin=False,
                active=True,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "active",
        ),
        (
            dict(
                is_toxin=False,
                active=False,
                triggered_this_tick=True,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "triggered",
        ),
        (
            dict(
                is_toxin=False,
                active=False,
                triggered_this_tick=False,
                synthesis_remaining=0,
                aftereffect_remaining_ticks=0,
            ),
            "configured",
        ),
    ],
)
def test_live_substance_state_payload_state_machine(
    kwargs: dict,
    expected_state: str,
) -> None:
    """Verify each runtime flag combination maps to expected state token."""
    state, _ = _live_substance_state_payload(**kwargs)
    assert state == expected_state
