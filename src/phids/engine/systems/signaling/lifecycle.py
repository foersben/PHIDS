# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Lifecycle management logic for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent

if TYPE_CHECKING:
    from phids.engine.core.ecs import ECSWorld


def _phase_index_and_clean_substances(
    world: ECSWorld,
    dead_substances: list[int],
) -> tuple[dict[tuple[int, int], SubstanceComponent], dict[int, set[int]]]:
    substance_entities = world.query(SubstanceComponent)
    for entity in substance_entities:
        sub = entity.get_component(SubstanceComponent)
        if not world.has_entity(sub.owner_plant_id):
            dead_substances.append(entity.entity_id)

    world.collect_garbage(dead_substances)
    dead_substances.clear()
    substance_entities = world.query(SubstanceComponent)

    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent] = {}
    active_substance_ids_by_owner: dict[int, set[int]] = {}
    for entity in substance_entities:
        sub = entity.get_component(SubstanceComponent)
        owner_substance_by_key[(sub.owner_plant_id, sub.substance_id)] = sub
        if sub.active:
            active_substance_ids_by_owner.setdefault(sub.owner_plant_id, set()).add(sub.substance_id)
        sub.triggered_this_tick = False

    return owner_substance_by_key, active_substance_ids_by_owner


def _phase_manage_nutrition_recovery(world: ECSWorld) -> None:
    for entity in world.query(PlantComponent):
        plant = entity.get_component(PlantComponent)
        if plant.withdrawal_ticks_remaining > 0:
            plant.withdrawal_ticks_remaining -= 1
            if plant.withdrawal_ticks_remaining <= 0:
                plant.apparent_nutrition_factor = 1.0


def _process_single_aftereffect(
    sub: SubstanceComponent,
    entity_id: int,
    world: ECSWorld,
    active_substance_ids_by_owner: dict[int, set[int]],
    dead_plant_ids: set[int],
    dead_substances: list[int],
) -> None:
    if not sub.active:
        return

    if not world.has_entity(sub.owner_plant_id):
        dead_substances.append(entity_id)
        return

    owner_entity = world.get_entity(sub.owner_plant_id)
    plant = owner_entity.get_component(PlantComponent)
    if plant.entity_id in dead_plant_ids:
        sub.active = False
        active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
        dead_substances.append(entity_id)
        return

    if sub.triggered_this_tick:
        sub.aftereffect_remaining_ticks = sub.aftereffect_ticks
        return

    if sub.irreversible:
        return

    if sub.aftereffect_remaining_ticks > 0:
        sub.aftereffect_remaining_ticks -= 1
        if sub.aftereffect_remaining_ticks <= 0:
            sub.active = False
            active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
    else:
        sub.active = False
        active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)


def _phase_process_aftereffects(
    world: ECSWorld,
    active_substance_ids_by_owner: dict[int, set[int]],
    dead_plant_ids: set[int],
    dead_substances: list[int],
) -> None:
    for entity in world.query(SubstanceComponent):
        _process_single_aftereffect(
            entity.get_component(SubstanceComponent),
            entity.entity_id,
            world,
            active_substance_ids_by_owner,
            dead_plant_ids,
            dead_substances,
        )
