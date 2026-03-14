"""Signaling system: substance synthesis, activation and local toxin effects.

This module manages the lifecycle of VOC signals and defensive toxins,
including trigger evaluation via the spatial hash, synthesis countdowns,
delegation of airborne signal diffusion to :class:`GridEnvironment`,
mycorrhizal signal relays and application of toxin effects to swarms.
"""

from __future__ import annotations

from typing import Any

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.shared.constants import SUBSTANCE_EMIT_RATE


def _is_substance_active_for_owner(
    owner_plant_id: int,
    substance_id: int,
    world: ECSWorld,
) -> bool:
    """Return whether a given substance is currently active on the owner plant."""
    for entity in world.query(SubstanceComponent):
        sub: SubstanceComponent = entity.get_component(SubstanceComponent)
        if sub.owner_plant_id == owner_plant_id and sub.substance_id == substance_id and sub.active:
            return True
    return False


def _check_activation_condition(
    plant: PlantComponent,
    owner_plant_id: int,
    activation_condition: dict[str, Any] | None,
    world: ECSWorld,
) -> bool:
    """Evaluate a nested activation predicate tree for one plant-owned substance."""
    if activation_condition is None:
        return True

    kind = activation_condition.get("kind")
    if kind == "enemy_presence":
        predator_species_id = int(activation_condition.get("predator_species_id", -1))
        min_predator_population = int(activation_condition.get("min_predator_population", 1))
        return (
            _co_located_swarm_population(world, plant.x, plant.y, predator_species_id)
            >= min_predator_population
        )
    if kind == "substance_active":
        substance_id = int(activation_condition.get("substance_id", -1))
        return _is_substance_active_for_owner(owner_plant_id, substance_id, world)
    if kind == "all_of":
        conditions = activation_condition.get("conditions", [])
        return bool(conditions) and all(
            _check_activation_condition(plant, owner_plant_id, child, world)
            for child in conditions
            if isinstance(child, dict)
        )
    if kind == "any_of":
        conditions = activation_condition.get("conditions", [])
        return any(
            _check_activation_condition(plant, owner_plant_id, child, world)
            for child in conditions
            if isinstance(child, dict)
        )
    return False


def _apply_toxin_to_swarms(
    sub: SubstanceComponent,
    env: GridEnvironment,
    world: ECSWorld,
) -> None:
    """Apply lethal and repellent toxin effects to swarms at affected cells.

    Args:
        sub: Substance component representing the toxin.
        env: GridEnvironment providing toxin concentrations.
        world: ECSWorld to iterate swarms.
    """
    for entity in list(world.query(SwarmComponent)):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        toxin_val = float(env.toxin_layers[sub.substance_id, swarm.x, swarm.y])
        if toxin_val <= 0.0:
            continue

        if sub.lethal and sub.lethality_rate > 0.0:
            casualties = int(sub.lethality_rate * toxin_val * swarm.population)
            swarm.population = max(0, swarm.population - casualties)

        if sub.repellent and not swarm.repelled:
            swarm.repelled = True
            swarm.repelled_ticks_remaining = sub.repellent_walk_ticks


def _co_located_swarm_population(
    world: ECSWorld,
    x: int,
    y: int,
    predator_species_id: int,
) -> int:
    """Return total population of a predator species at one grid cell.

    Args:
        world: ECSWorld used for spatial hash lookup.
        x: Grid x-coordinate.
        y: Grid y-coordinate.
        predator_species_id: Predator species to aggregate.

    Returns:
        int: Sum of populations for matching swarms at ``(x, y)``.
    """
    total_population = 0
    for co_eid in world.entities_at(x, y):
        if not world.has_entity(co_eid):
            continue
        co_entity = world.get_entity(co_eid)
        if not co_entity.has_component(SwarmComponent):
            continue
        swarm: SwarmComponent = co_entity.get_component(SwarmComponent)
        if swarm.species_id == predator_species_id:
            total_population += swarm.population
    return total_population


def _relay_signal_via_mycorrhizal(
    source_plant: PlantComponent,
    signal_id: int,
    amount: float,
    env: GridEnvironment,
    world: ECSWorld,
    mycorrhizal_inter_species: bool,
    signal_velocity: int,
    tick: int,
) -> None:
    """Propagate a signal through root-network connections.

    The signal is deposited directly into connected plant cells' signal
    layers, bypassing airborne diffusion. Inter-species relay can be
    disabled via ``mycorrhizal_inter_species``.

    Args:
        source_plant: Originating plant component.
        signal_id: Signal layer index.
        amount: Amount to deposit at each neighbour.
        env: GridEnvironment instance.
        world: ECSWorld instance.
        mycorrhizal_inter_species: Allow inter-species relay when True.
        signal_velocity: Attenuation factor applied per hop.
        tick: Current simulation tick (unused here but provided for parity).
    """
    for neighbour_id in source_plant.mycorrhizal_connections:
        if not world.has_entity(neighbour_id):
            continue
        neighbour_entity = world.get_entity(neighbour_id)
        if not neighbour_entity.has_component(PlantComponent):
            continue
        neighbour: PlantComponent = neighbour_entity.get_component(PlantComponent)
        if not mycorrhizal_inter_species and neighbour.species_id != source_plant.species_id:
            continue
        # Deposit signal at neighbour cell (scaled by velocity as simple attenuation)
        if signal_id < env.num_signals:
            env.signal_layers[signal_id, neighbour.x, neighbour.y] += amount / max(
                1, signal_velocity
            )


def run_signaling(
    world: ECSWorld,
    env: GridEnvironment,
    trigger_conditions: dict[int, list[object]],
    mycorrhizal_inter_species: bool,
    signal_velocity: int,
    tick: int,
    plant_death_causes: dict[str, int] | None = None,
) -> None:
    """Execute one signaling tick, handling synthesis, emission and diffusion.

    Args:
        world: ECS world registry.
        env: Grid environment holding signal/toxin layers.
        trigger_conditions: Mapping of flora species_id to trigger schemas.
        mycorrhizal_inter_species: Whether inter-species mycorrhizal signaling
            is permitted.
        signal_velocity: Ticks per hop for root-network relays.
        tick: Current simulation tick.
    """
    from phids.api.schemas import TriggerConditionSchema  # avoid circular at module level

    dead_substances: list[int] = []
    dead_plants: list[int] = []
    dead_plant_ids: set[int] = set()

    # ------------------------------------------------------------------
    # 0. Garbage-collect orphaned substances before any trigger checks
    # ------------------------------------------------------------------
    for entity in list(world.query(SubstanceComponent)):
        sub = entity.get_component(SubstanceComponent)
        if not world.has_entity(sub.owner_plant_id):
            dead_substances.append(entity.entity_id)

    world.collect_garbage(dead_substances)
    dead_substances.clear()

    # Toxins are rebuilt from currently active emitters each signaling pass
    # and remain local to living plant tissue. Non-triggered toxins remain
    # active only through configured aftereffects (or indefinitely when
    # irreversible=True).
    env.toxin_layers[:] = 0.0
    env._toxin_layers_write[:] = 0.0

    for entity in world.query(SubstanceComponent):
        sub = entity.get_component(SubstanceComponent)
        sub.triggered_this_tick = False

    # ------------------------------------------------------------------
    # 1. Evaluate trigger conditions for all plants
    # ------------------------------------------------------------------
    for entity in list(world.query(PlantComponent)):
        plant: PlantComponent = entity.get_component(PlantComponent)
        triggers = trigger_conditions.get(plant.species_id, [])

        for trig_raw in triggers:
            if not isinstance(trig_raw, TriggerConditionSchema):
                continue
            trig: TriggerConditionSchema = trig_raw

            # Check for predator presence at this cell via spatial hash
            triggered = (
                _co_located_swarm_population(
                    world,
                    plant.x,
                    plant.y,
                    trig.predator_species_id,
                )
                >= trig.min_predator_population
            )

            if not triggered:
                continue

            # Ensure a substance entity exists for this (plant, substance_id) pair
            existing_sub = None
            for sub_entity in world.query(SubstanceComponent):
                candidate_sub: SubstanceComponent = sub_entity.get_component(SubstanceComponent)
                if (
                    candidate_sub.owner_plant_id == plant.entity_id
                    and candidate_sub.substance_id == trig.substance_id
                ):
                    existing_sub = candidate_sub
                    break

            if existing_sub is None:
                # Spawn new substance entity with full properties from trigger
                new_entity = world.create_entity()
                existing_sub = SubstanceComponent(
                    entity_id=new_entity.entity_id,
                    substance_id=trig.substance_id,
                    owner_plant_id=plant.entity_id,
                    is_toxin=trig.is_toxin,
                    synthesis_duration=trig.synthesis_duration,
                    synthesis_remaining=trig.synthesis_duration,
                    lethal=trig.lethal,
                    lethality_rate=trig.lethality_rate,
                    repellent=trig.repellent,
                    repellent_walk_ticks=trig.repellent_walk_ticks,
                    aftereffect_ticks=trig.aftereffect_ticks,
                    aftereffect_remaining_ticks=trig.aftereffect_ticks,
                    precursor_signal_id=trig.precursor_signal_id,
                    precursor_signal_ids=tuple(trig.precursor_signal_ids),
                    activation_condition=(
                        trig.activation_condition.model_dump(mode="json")
                        if trig.activation_condition is not None
                        else None
                    ),
                    energy_cost_per_tick=trig.energy_cost_per_tick,
                    irreversible=trig.irreversible,
                    trigger_predator_species_id=trig.predator_species_id,
                    trigger_min_predator_population=trig.min_predator_population,
                )
                world.add_component(new_entity.entity_id, existing_sub)
            else:
                if (
                    not existing_sub.active
                    and existing_sub.synthesis_remaining <= 0
                    and existing_sub.aftereffect_remaining_ticks <= 0
                ):
                    existing_sub.synthesis_remaining = existing_sub.synthesis_duration

            existing_sub.triggered_this_tick = True

    # ------------------------------------------------------------------
    # 2. Advance synthesis timers & activate substances
    # ------------------------------------------------------------------
    for entity in list(world.query(SubstanceComponent)):
        sub = entity.get_component(SubstanceComponent)
        if sub.active:
            continue
        if not sub.triggered_this_tick:
            continue
        owner_entity = (
            world.get_entity(sub.owner_plant_id) if world.has_entity(sub.owner_plant_id) else None
        )
        if owner_entity is None:
            dead_substances.append(entity.entity_id)
            continue
        plant = owner_entity.get_component(PlantComponent)
        if sub.synthesis_remaining > 0:
            sub.synthesis_remaining -= 1
        if sub.synthesis_remaining <= 0:
            if not _check_activation_condition(
                plant,
                sub.owner_plant_id,
                sub.activation_condition,
                world,
            ):
                continue
            sub.active = True
            sub.aftereffect_remaining_ticks = sub.aftereffect_ticks

    # ------------------------------------------------------------------
    # 2b. Irreversible induced defense lock
    # ------------------------------------------------------------------
    for entity in list(world.query(SubstanceComponent)):
        sub = entity.get_component(SubstanceComponent)
        if sub.active and sub.irreversible:
            sub.triggered_this_tick = True

    # ------------------------------------------------------------------
    # 3. Emit active signals / toxins into environment layers
    # ------------------------------------------------------------------
    active_toxin_types: dict[int, SubstanceComponent] = {}

    for entity in list(world.query(SubstanceComponent)):
        sub = entity.get_component(SubstanceComponent)
        if not sub.active:
            continue

        if not sub.triggered_this_tick:
            if not sub.irreversible and sub.aftereffect_remaining_ticks <= 0:
                sub.active = False
                continue

        owner_entity = (
            world.get_entity(sub.owner_plant_id) if world.has_entity(sub.owner_plant_id) else None
        )
        if owner_entity is None:
            dead_substances.append(entity.entity_id)
            continue

        plant = owner_entity.get_component(PlantComponent)
        if plant.entity_id in dead_plant_ids:
            sub.active = False
            dead_substances.append(entity.entity_id)
            continue

        # --- Energy maintenance cost (Section 4: continuous depletion) ---
        if (
            sub.energy_cost_per_tick > 0.0
            and not sub.triggered_this_tick
            and not sub.irreversible
            and (plant.energy - sub.energy_cost_per_tick) < plant.survival_threshold
        ):
            sub.active = False
            sub.aftereffect_remaining_ticks = 0
            continue

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
                dead_substances.append(entity.entity_id)
                continue

        if sub.is_toxin:
            if sub.substance_id < env.num_toxins:
                env.toxin_layers[sub.substance_id, plant.x, plant.y] = min(
                    1.0,
                    float(env.toxin_layers[sub.substance_id, plant.x, plant.y])
                    + SUBSTANCE_EMIT_RATE,
                )
                active_toxin_types.setdefault(sub.substance_id, sub)
        else:
            if sub.substance_id < env.num_signals:
                env.signal_layers[sub.substance_id, plant.x, plant.y] = min(
                    1.0,
                    float(env.signal_layers[sub.substance_id, plant.x, plant.y])
                    + SUBSTANCE_EMIT_RATE,
                )
            # Relay via mycorrhizal network
            _relay_signal_via_mycorrhizal(
                plant,
                sub.substance_id,
                SUBSTANCE_EMIT_RATE,
                env,
                world,
                mycorrhizal_inter_species,
                signal_velocity,
                tick,
            )

    for sub in active_toxin_types.values():
        _apply_toxin_to_swarms(sub, env, world)

    # ------------------------------------------------------------------
    # 4. Check aftereffects and deactivate expired substances
    # ------------------------------------------------------------------
    for entity in list(world.query(SubstanceComponent)):
        sub = entity.get_component(SubstanceComponent)
        if not sub.active:
            continue

        # Verify owner still exists
        if not world.has_entity(sub.owner_plant_id):
            dead_substances.append(entity.entity_id)
            continue

        owner_entity = world.get_entity(sub.owner_plant_id)
        plant = owner_entity.get_component(PlantComponent)
        if plant.entity_id in dead_plant_ids:
            sub.active = False
            dead_substances.append(entity.entity_id)
            continue

        if sub.triggered_this_tick:
            sub.aftereffect_remaining_ticks = sub.aftereffect_ticks
            continue

        if sub.irreversible:
            continue

        if sub.aftereffect_remaining_ticks > 0:
            sub.aftereffect_remaining_ticks -= 1
            if sub.aftereffect_remaining_ticks <= 0:
                sub.active = False
        else:
            sub.active = False

    # ------------------------------------------------------------------
    # 5. Diffusion (delegated to GridEnvironment)
    # ------------------------------------------------------------------
    env.diffuse_signals()

    # ------------------------------------------------------------------
    # 6. Garbage collect expired substance entities
    # ------------------------------------------------------------------
    world.collect_garbage(dead_plants)
    world.collect_garbage(dead_substances)
