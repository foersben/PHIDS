"""Signaling system: substance synthesis, activation and toxin effects.

This module manages the lifecycle of VOC signals and defensive toxins,
including trigger evaluation via the spatial hash, synthesis countdowns,
delegation of airborne diffusion to :class:`GridEnvironment`, mycorrhizal
signal relays and application of toxin effects to swarms.
"""

from __future__ import annotations

from phytodynamics.engine.components.plant import PlantComponent
from phytodynamics.engine.components.substances import SubstanceComponent
from phytodynamics.engine.components.swarm import SwarmComponent
from phytodynamics.engine.core.biotope import GridEnvironment
from phytodynamics.engine.core.ecs import ECSWorld
from phytodynamics.shared.constants import SUBSTANCE_EMIT_RATE


def _check_precursor_active(
    owner_plant_id: int,
    precursor_signal_id: int,
    world: ECSWorld,
) -> bool:
    """Return True if the required precursor signal is active for the owner.

    Args:
        owner_plant_id: Plant entity id that owns the substance.
        precursor_signal_id: Required precursor signal id or -1 for none.
        world: ECSWorld instance to query for active substances.

    Returns:
        bool: True if the precursor is active or not required.
    """
    if precursor_signal_id < 0:
        return True
    for entity in world.query(SubstanceComponent):
        sub: SubstanceComponent = entity.get_component(SubstanceComponent)
        if (
            sub.owner_plant_id == owner_plant_id
            and sub.substance_id == precursor_signal_id
            and not sub.is_toxin
            and sub.active
        ):
            return True
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
            swarm.target_plant_id = -1


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
    from phytodynamics.api.schemas import TriggerConditionSchema  # avoid circular at module level

    dead_substances: list[int] = []

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
            triggered = False
            for co_eid in world.entities_at(plant.x, plant.y):
                co_entity = world.get_entity(co_eid)
                if not co_entity.has_component(SwarmComponent):
                    continue
                swarm: SwarmComponent = co_entity.get_component(SwarmComponent)
                if (
                    swarm.species_id == trig.predator_species_id
                    and swarm.population >= trig.min_predator_population
                ):
                    triggered = True
                    break

            if not triggered:
                continue

            # Ensure a substance entity exists for this (plant, substance_id) pair
            existing_sub = None
            for sub_entity in world.query(SubstanceComponent):
                sub: SubstanceComponent = sub_entity.get_component(SubstanceComponent)
                if sub.owner_plant_id == plant.entity_id and sub.substance_id == trig.substance_id:
                    existing_sub = sub
                    break

            if existing_sub is None:
                # Spawn new substance entity
                new_entity = world.create_entity()
                existing_sub = SubstanceComponent(
                    entity_id=new_entity.entity_id,
                    substance_id=trig.substance_id,
                    owner_plant_id=plant.entity_id,
                    synthesis_remaining=trig.synthesis_duration,
                )
                world.add_component(new_entity.entity_id, existing_sub)

    # ------------------------------------------------------------------
    # 2. Advance synthesis timers & activate substances
    # ------------------------------------------------------------------
    for entity in list(world.query(SubstanceComponent)):
        sub = entity.get_component(SubstanceComponent)
        if sub.active:
            continue
        if sub.synthesis_remaining > 0:
            sub.synthesis_remaining -= 1
        if sub.synthesis_remaining <= 0:
            # Check precursor requirement
            if not _check_precursor_active(sub.owner_plant_id, sub.precursor_signal_id, world):
                continue
            sub.active = True

    # ------------------------------------------------------------------
    # 3. Emit active signals / toxins into environment layers
    # ------------------------------------------------------------------
    for entity in list(world.query(SubstanceComponent)):
        sub = entity.get_component(SubstanceComponent)
        if not sub.active:
            continue

        owner_entity = (
            world.get_entity(sub.owner_plant_id)
            if world.has_entity(sub.owner_plant_id)
            else None
        )
        if owner_entity is None:
            dead_substances.append(entity.entity_id)
            continue

        plant = owner_entity.get_component(PlantComponent)

        if sub.is_toxin:
            if sub.substance_id < env.num_toxins:
                env.toxin_layers[sub.substance_id, plant.x, plant.y] = min(
                    1.0,
                    float(env.toxin_layers[sub.substance_id, plant.x, plant.y])
                    + SUBSTANCE_EMIT_RATE,
                )
            # Apply toxin effects to nearby swarms
            _apply_toxin_to_swarms(sub, env, world)
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

        # For toxins: dissipate instantly when no triggering predator is present
        if sub.is_toxin:
            owner_entity = world.get_entity(sub.owner_plant_id)
            plant = owner_entity.get_component(PlantComponent)
            still_triggered = any(
                world.get_entity(co_eid).has_component(SwarmComponent)
                for co_eid in world.entities_at(plant.x, plant.y)
                if world.has_entity(co_eid)
            )
            if not still_triggered:
                if sub.aftereffect_ticks > 0:
                    sub.aftereffect_ticks -= 1
                else:
                    sub.active = False
                    # Clear toxin layer contribution
                    if sub.substance_id < env.num_toxins:
                        env.toxin_layers[sub.substance_id, plant.x, plant.y] = max(
                            0.0,
                            float(env.toxin_layers[sub.substance_id, plant.x, plant.y])
                            - SUBSTANCE_EMIT_RATE,
                        )

    # ------------------------------------------------------------------
    # 5. Diffusion (delegated to GridEnvironment)
    # ------------------------------------------------------------------
    env.diffuse_signals()
    env.diffuse_toxins()

    # ------------------------------------------------------------------
    # 6. Garbage collect expired substance entities
    # ------------------------------------------------------------------
    world.collect_garbage(dead_substances)
