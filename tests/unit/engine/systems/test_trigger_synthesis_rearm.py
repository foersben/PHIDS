# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for trigger activation and substance re-arm synthesis branches."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from phids.api.schemas.triggers import SynthesizeSubstanceAction
from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling.triggers import _apply_synthesize_action


@pytest.mark.unit
def test_trigger_rearm_synthesis_when_inactive() -> None:
    """Verify that re-triggering an inactive, expired substance re-arms synthesis_remaining.

    Raises:
        AssertionError: If synthesis_remaining is not reset to synthesis_duration upon re-triggering.
    """
    world = ECSWorld()

    plant_entity = world.create_entity()
    plant = PlantComponent(
        entity_id=plant_entity.entity_id,
        species_id=0,
        x=5,
        y=5,
        energy=100.0,
        max_energy=100.0,
        base_energy=20.0,
        growth_rate=0.05,
        survival_threshold=5.0,
        reproduction_interval=50,
        seed_min_dist=1.0,
        seed_max_dist=5.0,
        seed_energy_cost=10.0,
    )

    sub_entity = world.create_entity()
    sub = SubstanceComponent(
        entity_id=sub_entity.entity_id,
        substance_id=1,
        owner_plant_id=plant_entity.entity_id,
        active=False,
        synthesis_duration=10,
        synthesis_remaining=0,
        aftereffect_remaining_ticks=0,
    )

    action = SynthesizeSubstanceAction(
        substance_id=1,
        is_toxin=True,
        synthesis_duration=10,
        lethal=False,
        lethality_rate=0.0,
        repellent=False,
        repellent_walk_ticks=0,
        energy_cost_per_tick=0.0,
        irreversible=False,
    )
    trig = MagicMock()
    trig.schema.action = action
    trig.schema.aftereffect_ticks = 0
    trig.activation_condition_dump = None

    owner_substance_map = {(plant_entity.entity_id, 1): sub}
    sub_entities: list[object] = []

    _apply_synthesize_action(
        trig=trig,
        plant=plant,
        world=world,
        owner_substance_by_key=owner_substance_map,
        substance_entities=sub_entities,  # type: ignore[arg-type]
    )

    assert sub.synthesis_remaining == 10
    assert sub.triggered_this_tick is True
