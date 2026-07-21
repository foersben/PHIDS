# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Synthesis advancement logic for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.systems.signaling.conditions import _check_activation_condition

if TYPE_CHECKING:
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


def _process_advance_single_synthesis(
    sub: SubstanceComponent,
    entity_id: int,
    world: ECSWorld,
    env: GridEnvironment,
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    dead_substances: list[int],
) -> None:
    if sub.active and sub.irreversible:
        sub.triggered_this_tick = True

    if sub.active:
        return
    if not sub.triggered_this_tick:
        return
    owner_entity = world.get_entity(sub.owner_plant_id) if world.has_entity(sub.owner_plant_id) else None
    if owner_entity is None:
        dead_substances.append(entity_id)
        return
    plant = owner_entity.get_component(PlantComponent)
    if sub.synthesis_remaining > 0:
        sub.synthesis_remaining -= 1
    if sub.synthesis_remaining <= 0:
        if not _check_activation_condition(
            plant,
            sub.owner_plant_id,
            sub.activation_condition,
            env,
            swarm_population_by_cell_species,
            active_substance_ids_by_owner,
        ):
            return
        sub.active = True
        sub.aftereffect_remaining_ticks = sub.aftereffect_ticks
        active_substance_ids_by_owner.setdefault(sub.owner_plant_id, set()).add(sub.substance_id)


def _phase_advance_synthesis(
    world: ECSWorld,
    env: GridEnvironment,
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
    dead_substances: list[int],
) -> None:
    for entity in world.query(SubstanceComponent):
        _process_advance_single_synthesis(
            entity.get_component(SubstanceComponent),
            entity.entity_id,
            world,
            env,
            swarm_population_by_cell_species,
            active_substance_ids_by_owner,
            dead_substances,
        )
