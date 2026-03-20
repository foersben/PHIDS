"""Focused mutation-pilot regressions for dashboard presenter branch-critical unions."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from phids.api.presenters.dashboard import build_live_dashboard_payload
from phids.api.schemas import SimulationConfig
from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.loop import SimulationLoop

pytestmark = pytest.mark.mutation_pilot


def _find_plant_entity_id(loop: SimulationLoop) -> int:
    """Return the single baseline plant entity id from the configured loop fixture."""
    plants = [entity.get_component(PlantComponent) for entity in loop.world.query(PlantComponent)]
    assert len(plants) == 1
    return plants[0].entity_id


def test_active_signal_ids_union_field_residue_with_visible_runtime_substances(
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Signal ids include both local field residues and visible live substance entities via set union."""
    loop = SimulationLoop(loop_config_builder(max_ticks=5))
    plant_id = _find_plant_entity_id(loop)
    plant = loop.world.get_entity(plant_id).get_component(PlantComponent)

    loop.env.signal_layers[1, plant.x, plant.y] = 0.3
    sub_entity = loop.world.create_entity()
    loop.world.add_component(
        sub_entity.entity_id,
        SubstanceComponent(
            entity_id=sub_entity.entity_id,
            substance_id=0,
            owner_plant_id=plant_id,
            is_toxin=False,
            active=True,
        ),
    )

    payload = build_live_dashboard_payload(loop, substance_names={0: "sig-0", 1: "sig-1"})
    index = payload["plants"]["entity_id"].index(plant_id)
    assert payload["plants"]["active_signal_ids"][index] == [0, 1]


def test_active_toxin_ids_union_field_residue_with_visible_runtime_substances(
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Toxin ids include both local toxin-layer residues and visible live toxin entities via union."""
    loop = SimulationLoop(loop_config_builder(max_ticks=5))
    plant_id = _find_plant_entity_id(loop)
    plant = loop.world.get_entity(plant_id).get_component(PlantComponent)

    loop.env.toxin_layers[1, plant.x, plant.y] = 0.4
    sub_entity = loop.world.create_entity()
    loop.world.add_component(
        sub_entity.entity_id,
        SubstanceComponent(
            entity_id=sub_entity.entity_id,
            substance_id=0,
            owner_plant_id=plant_id,
            is_toxin=True,
            active=True,
        ),
    )

    payload = build_live_dashboard_payload(loop, substance_names={0: "tox-0", 1: "tox-1"})
    index = payload["plants"]["entity_id"].index(plant_id)
    assert payload["plants"]["active_toxin_ids"][index] == [0, 1]
