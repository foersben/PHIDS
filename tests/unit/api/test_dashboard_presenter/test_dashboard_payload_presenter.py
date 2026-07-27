# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for live dashboard payload construction and extinct species bifurcation."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from phids.api.presenters.dashboard import (
    _fallback_live_substance_payload,
    build_live_dashboard_payload,
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
from phids.engine.components.plant import PlantComponent
from phids.engine.loop import SimulationLoop
from phids.io.scenario import load_scenario_from_json


def _flora(species_id: int, *, triggers: list[TriggerConditionSchema] | None = None) -> FloraSpeciesParams:
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
    return HerbivoreSpeciesParams(
        species_id=species_id,
        name=f"herbivore-{species_id}",
        energy_min=1.0,
        velocity=1,
        consumption_rate=1.0,
        reproduction_energy_divisor=1.0,
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
    return SimulationConfig(
        grid_width=8,
        grid_height=8,
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
def _reset_draft() -> None:
    reset_draft()


def test_build_live_dashboard_payload_structural_contract() -> None:
    """Verifies dashboard payload carries all keys required by canvas renderer."""
    config = _minimal_config()
    loop = SimulationLoop(config)
    payload = build_live_dashboard_payload(loop, substance_names={})

    required_keys = {
        "tick",
        "grid_width",
        "grid_height",
        "max_energy",
        "species_energy",
        "all_flora_species",
        "signal_overlay",
        "toxin_overlay",
        "max_signal",
        "max_toxin",
        "plants",
        "mycorrhizal_links",
        "swarms",
        "terminated",
        "termination_reason",
        "running",
        "paused",
    }
    assert required_keys.issubset(payload.keys())


def test_build_live_dashboard_payload_tick_and_lifecycle_state() -> None:
    """Verifies tick and lifecycle flags reflect loop state."""
    config = _minimal_config()
    loop = SimulationLoop(config)
    payload = build_live_dashboard_payload(loop, substance_names={})

    assert payload["tick"] == 0
    assert payload["terminated"] is False
    assert payload["running"] is False
    assert payload["paused"] is False


def test_build_live_dashboard_payload_plant_and_swarm_entries() -> None:
    """Verifies live plant and swarm entities are serialized as columnar arrays."""
    config = _minimal_config(x=4, y=4)
    loop = SimulationLoop(config)
    payload = build_live_dashboard_payload(loop, substance_names={})

    plant_columns = payload["plants"]
    assert {"entity_id", "species_id", "x", "y", "energy"}.issubset(plant_columns.keys())
    plant_count = len(plant_columns["entity_id"])
    assert plant_count == 1

    swarm_columns = payload["swarms"]
    assert {"x", "y", "population", "species_id"}.issubset(swarm_columns.keys())
    swarm_count = len(swarm_columns["species_id"])
    assert swarm_count == 1


def test_build_live_dashboard_payload_extinct_species_bifurcation() -> None:
    """Verifies extinct-species bifurcation invariant across species_energy and all_flora_species."""
    config = load_scenario_from_json(Path("examples/meadow_defense.json"))
    loop = SimulationLoop(config)

    while loop.tick < 140:
        asyncio.run(loop.step())
        live_species = {entity.get_component(PlantComponent).species_id for entity in loop.world.query(PlantComponent)}
        if len(live_species) <= 1:
            break

    payload = build_live_dashboard_payload(loop, substance_names={})
    payload_species = {int(spec["species_id"]) for spec in payload["species_energy"]}
    legend_species = {int(spec["species_id"]) for spec in payload["all_flora_species"]}
    configured_species = {species.species_id for species in loop.config.flora_species}
    live_species = {entity.get_component(PlantComponent).species_id for entity in loop.world.query(PlantComponent)}

    assert payload_species == live_species
    assert legend_species == configured_species
    extinct_in_payload = {
        int(spec["species_id"]) for spec in payload["all_flora_species"] if spec.get("extinct", False)
    }
    assert extinct_in_payload == configured_species - live_species


def test_build_live_dashboard_payload_max_energy_is_positive() -> None:
    """Verifies max_energy is always a positive float."""
    config = _minimal_config()
    loop = SimulationLoop(config)
    payload = build_live_dashboard_payload(loop, substance_names={})
    assert payload["max_energy"] > 0.0


def test_fallback_live_substance_payload_snapshot_state() -> None:
    """Verifies fallback payload is in field_snapshot state."""
    payload = _fallback_live_substance_payload(2, is_toxin=False, substance_names={2: "Jasmonates"})
    assert payload["state"] == "field_snapshot"
    assert payload["snapshot_only"] is True
    assert payload["name"] == "Jasmonates"
