# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Emission and toxin logic for the signaling system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.systems.signaling.spatial import _collect_mycorrhizal_targets

if TYPE_CHECKING:
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld
    from phids.engine.systems.signaling.types import _ActiveToxinProps


def _apply_toxin_to_swarms(
    sub_id: int,
    lethal: bool,
    lethality_rate: float,
    repellent: bool,
    repellent_walk_ticks: int,
    env: GridEnvironment,
    world: ECSWorld,
) -> None:
    """Apply lethal and repellent toxin effects to swarms and immediately GC killed swarms."""
    dead_swarms: list[int] = []

    for entity in world.query(SwarmComponent):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        toxin_val = float(env.toxin_layers[sub_id, swarm.x, swarm.y])
        if toxin_val <= 0.0:
            continue

        if lethal and lethality_rate > 0.0:
            casualties = int(lethality_rate * toxin_val * swarm.population)
            if casualties > 0:
                swarm.population = max(0, swarm.population - casualties)
                # Remove the energetic mass of dead individuals; survivors cannot inherit it.
                energy_loss = casualties * swarm.energy_min
                swarm.energy = max(0.0, swarm.energy - energy_loss)

        if repellent and not swarm.repelled:
            swarm.repelled = True
            swarm.repelled_ticks_remaining = repellent_walk_ticks

        # Immediate localised GC: a swarm annihilated by chemical defense must not
        # linger as a ghost entity in the spatial hash until the next interaction tick.
        if swarm.population <= 0:
            world.unregister_position(entity.entity_id, swarm.x, swarm.y)
            dead_swarms.append(entity.entity_id)

    if dead_swarms:
        world.collect_garbage(dead_swarms)


def _process_substance_energy_maintenance(
    sub: SubstanceComponent,
    plant: PlantComponent,
    env: GridEnvironment,
    world: ECSWorld,
    active_substance_ids_by_owner: dict[int, set[int]],
    dead_plant_ids: set[int],
    dead_substances: list[int],
    dead_plants: list[int],
    plant_death_causes: dict[str, int] | None,
    entity_id: int,
) -> bool:
    if (
        sub.energy_cost_per_tick > 0.0
        and not sub.triggered_this_tick
        and not sub.irreversible
        and (plant.energy - sub.energy_cost_per_tick) < plant.survival_threshold
    ):
        sub.active = False
        sub.aftereffect_remaining_ticks = 0
        active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
        return False

    if sub.energy_cost_per_tick > 0.0:
        plant.energy -= sub.energy_cost_per_tick
        env.set_plant_energy(plant.x, plant.y, plant.species_id, plant.energy)
        plant.last_energy_loss_cause = "death_defense_maintenance"
        if plant.energy < plant.survival_threshold:
            if plant_death_causes is not None:
                plant_death_causes["death_defense_maintenance"] = (
                    plant_death_causes.get("death_defense_maintenance", 0) + 1
                )
            env.clear_plant_energy(plant.x, plant.y, plant.species_id)
            world.unregister_position(plant.entity_id, plant.x, plant.y)
            dead_plants.append(plant.entity_id)
            dead_plant_ids.add(plant.entity_id)
            sub.active = False
            active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
            dead_substances.append(entity_id)
            return False

    return True


def _process_toxin_emission(
    sub: SubstanceComponent,
    plant: PlantComponent,
    env: GridEnvironment,
    substance_emit_rate: float,
    active_toxin_props: dict[int, _ActiveToxinProps],
) -> None:
    if sub.substance_id < env.num_toxins:
        env.toxin_layers[sub.substance_id, plant.x, plant.y] = min(
            1.0,
            float(env.toxin_layers[sub.substance_id, plant.x, plant.y]) + substance_emit_rate,
        )
        if sub.substance_id not in active_toxin_props:
            active_toxin_props[sub.substance_id] = {
                "lethal": sub.lethal,
                "lethality_rate": sub.lethality_rate,
                "repellent": sub.repellent,
                "repellent_walk_ticks": sub.repellent_walk_ticks,
            }
        else:
            props = active_toxin_props[sub.substance_id]
            props["lethal"] = bool(props["lethal"] or sub.lethal)
            props["lethality_rate"] = max(float(props["lethality_rate"]), sub.lethality_rate)
            props["repellent"] = bool(props["repellent"] or sub.repellent)
            props["repellent_walk_ticks"] = max(
                int(props["repellent_walk_ticks"]),
                sub.repellent_walk_ticks,
            )


def _process_signal_emission(
    sub: SubstanceComponent,
    plant: PlantComponent,
    env: GridEnvironment,
    world: ECSWorld,
    substance_emit_rate: float,
    mycorrhizal_inter_species: bool,
    signal_velocity: int,
) -> None:
    relay_targets = _collect_mycorrhizal_targets(
        plant,
        world,
        mycorrhizal_inter_species,
    )
    relay_count = len(relay_targets)
    airborne_amount = substance_emit_rate / float(relay_count + 1)
    if sub.substance_id < env.num_signals:
        env.signal_layers[sub.substance_id, plant.x, plant.y] = (
            float(env.signal_layers[sub.substance_id, plant.x, plant.y]) + airborne_amount
        )

    if relay_count > 0:
        relay_amount = substance_emit_rate - airborne_amount
        per_target_amount = relay_amount / float(relay_count)
        for relay_target in relay_targets:
            if sub.substance_id < env.num_signals:
                env.signal_layers[
                    sub.substance_id,
                    relay_target.x,
                    relay_target.y,
                ] += per_target_amount / max(1, signal_velocity)


def _process_single_emission(
    sub: SubstanceComponent,
    entity_id: int,
    world: ECSWorld,
    env: GridEnvironment,
    substance_emit_rate: float,
    mycorrhizal_inter_species: bool,
    signal_velocity: int,
    active_substance_ids_by_owner: dict[int, set[int]],
    dead_plant_ids: set[int],
    dead_substances: list[int],
    dead_plants: list[int],
    plant_death_causes: dict[str, int] | None,
    active_toxin_props: dict[int, _ActiveToxinProps],
) -> None:
    if not sub.active:
        return

    if not sub.triggered_this_tick:
        if not sub.irreversible and sub.aftereffect_remaining_ticks <= 0:
            sub.active = False
            active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
            return

    owner_entity = world.get_entity(sub.owner_plant_id) if world.has_entity(sub.owner_plant_id) else None
    if owner_entity is None:
        dead_substances.append(entity_id)
        return

    plant = owner_entity.get_component(PlantComponent)
    if plant.entity_id in dead_plant_ids:
        sub.active = False
        active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
        dead_substances.append(entity_id)
        return

    if not _process_substance_energy_maintenance(
        sub,
        plant,
        env,
        world,
        active_substance_ids_by_owner,
        dead_plant_ids,
        dead_substances,
        dead_plants,
        plant_death_causes,
        entity_id,
    ):
        return

    if sub.is_toxin:
        _process_toxin_emission(sub, plant, env, substance_emit_rate, active_toxin_props)
    else:
        _process_signal_emission(
            sub, plant, env, world, substance_emit_rate, mycorrhizal_inter_species, signal_velocity
        )


def _phase_emit_signals_and_toxins(
    world: ECSWorld,
    env: GridEnvironment,
    substance_emit_rate: float,
    mycorrhizal_inter_species: bool,
    signal_velocity: int,
    active_substance_ids_by_owner: dict[int, set[int]],
    dead_plant_ids: set[int],
    dead_substances: list[int],
    dead_plants: list[int],
    plant_death_causes: dict[str, int] | None,
) -> None:
    active_toxin_props: dict[int, _ActiveToxinProps] = {}

    for entity in world.query(SubstanceComponent):
        _process_single_emission(
            entity.get_component(SubstanceComponent),
            entity.entity_id,
            world,
            env,
            substance_emit_rate,
            mycorrhizal_inter_species,
            signal_velocity,
            active_substance_ids_by_owner,
            dead_plant_ids,
            dead_substances,
            dead_plants,
            plant_death_causes,
            active_toxin_props,
        )

    for sub_id, props in active_toxin_props.items():
        _apply_toxin_to_swarms(
            sub_id,
            bool(props["lethal"]),
            float(props["lethality_rate"]),
            bool(props["repellent"]),
            int(props["repellent_walk_ticks"]),
            env,
            world,
        )
