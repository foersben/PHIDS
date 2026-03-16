"""Signaling system: substance synthesis, activation, emission, diffusion, and toxin effects.

This module implements the third and final per-tick simulation phase of the PHIDS engine,
governing the full lifecycle of volatile organic compound (VOC) signals and defensive toxins.
The signaling phase is executed after both the lifecycle and interaction phases have committed
their energy mutations, ensuring that plant survival status and predator co-location data reflect
the current tick's resolved state before chemical-defense decisions are made.

The phase proceeds through six ordered sub-steps. First, orphaned substance entities whose owner
plants were destroyed in earlier phases are garbage-collected. Second, trigger-condition trees are
evaluated for each living plant against the per-cell predator census index
(``_build_swarm_population_index``): direct predator co-presence (``enemy_presence`` nodes) or
indirect conditions (``substance_active``, ``environmental_signal``, ``all_of``, ``any_of``
composites) can independently satisfy a trigger. Third, synthesis countdown timers are decremented
for triggered substances; substances with zero remaining countdown and satisfied activation
conditions are transitioned to ``active`` state. Fourth, active substances emit concentration
increments (``SUBSTANCE_EMIT_RATE``) into signal or toxin environment layers, deduct
``energy_cost_per_tick`` from the owner plant, relay VOC signals through mycorrhizal root
networks, and record toxin property aggregates for batch application. Fifth, toxin effects
(lethality and repellency) are applied to all co-located swarms via ``_apply_toxin_to_swarms``,
with immediate spatial-hash deregistration and garbage collection of swarms annihilated by
chemical defense. Sixth, Gaussian diffusion is delegated to ``GridEnvironment.diffuse_signals``,
which convolves each airborne signal layer with the pre-computed kernel and applies the
``SIGNAL_EPSILON`` sparsity threshold to eliminate subnormal tail values.
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
    active_substance_ids_by_owner: dict[int, set[int]],
) -> bool:
    """Return whether a given substance is currently active on the owner plant."""
    return substance_id in active_substance_ids_by_owner.get(owner_plant_id, set())


def _build_swarm_population_index(world: ECSWorld) -> dict[tuple[int, int, int], int]:
    """Return a per-cell, per-species swarm-population index for one signaling tick."""
    populations: dict[tuple[int, int, int], int] = {}
    for entity in world.query(SwarmComponent):
        swarm: SwarmComponent = entity.get_component(SwarmComponent)
        key = (swarm.x, swarm.y, swarm.species_id)
        populations[key] = populations.get(key, 0) + swarm.population
    return populations


def _check_activation_condition(
    plant: PlantComponent,
    owner_plant_id: int,
    activation_condition: dict[str, Any] | None,
    env: GridEnvironment,
    swarm_population_by_cell_species: dict[tuple[int, int, int], int],
    active_substance_ids_by_owner: dict[int, set[int]],
) -> bool:
    """Evaluate a nested activation predicate tree for one plant-owned substance.

    Recursively traverses the condition tree rooted at ``activation_condition``, evaluating
    ``enemy_presence`` leaves against the per-cell predator census index, ``substance_active``
    leaves against the owner's active substance set, ``environmental_signal`` leaves against
    the current signal-layer concentration at the plant's coordinates, and ``all_of`` / ``any_of``
    composites using short-circuit Boolean logic.

    Args:
        plant: The plant entity whose grid coordinates are used for spatial condition checks.
        owner_plant_id: Entity identifier of the owning plant, used to look up currently active
            substances in ``active_substance_ids_by_owner``.
        activation_condition: JSON-serialisable condition node dictionary, or ``None`` for
            unconditional activation.
        env: ``GridEnvironment`` providing read access to signal-layer concentrations for
            ``environmental_signal`` predicates.
        swarm_population_by_cell_species: Pre-built census index mapping
            ``(x, y, species_id)`` to aggregate swarm population; used for ``enemy_presence``
            evaluations without additional ECS world queries.
        active_substance_ids_by_owner: Mapping from plant entity id to its set of currently
            active substance layer indices; used for ``substance_active`` leaf evaluation.

    Returns:
        ``True`` when the condition tree evaluates to true; ``False`` otherwise.
    """
    if activation_condition is None:
        return True

    kind = activation_condition.get("kind")
    if kind == "enemy_presence":
        predator_species_id = int(activation_condition.get("predator_species_id", -1))
        min_predator_population = int(activation_condition.get("min_predator_population", 1))
        return (
            swarm_population_by_cell_species.get((plant.x, plant.y, predator_species_id), 0)
            >= min_predator_population
        )

    if kind == "substance_active":
        substance_id = int(activation_condition.get("substance_id", -1))
        return _is_substance_active_for_owner(
            owner_plant_id,
            substance_id,
            active_substance_ids_by_owner,
        )

    if kind == "environmental_signal":
        signal_id = int(activation_condition.get("signal_id", -1))
        min_conc = float(activation_condition.get("min_concentration", 0.01))
        if 0 <= signal_id < env.num_signals:
            return float(env.signal_layers[signal_id, plant.x, plant.y]) >= min_conc
        return False

    if kind == "all_of":
        conditions = activation_condition.get("conditions", [])
        return bool(conditions) and all(
            _check_activation_condition(
                plant,
                owner_plant_id,
                child,
                env,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
            )
            for child in conditions
            if isinstance(child, dict)
        )

    if kind == "any_of":
        conditions = activation_condition.get("conditions", [])
        return any(
            _check_activation_condition(
                plant,
                owner_plant_id,
                child,
                env,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
            )
            for child in conditions
            if isinstance(child, dict)
        )

    return False


def _apply_toxin_to_swarms(
    sub_id: int,
    lethal: bool,
    lethality_rate: float,
    repellent: bool,
    repellent_walk_ticks: int,
    env: GridEnvironment,
    world: ECSWorld,
) -> None:
    """Apply lethal and repellent toxin effects to swarms and immediately GC killed swarms.

    This function constitutes the chemical-defense enforcement step within the signaling
    phase. For each swarm co-located with a non-zero toxin concentration, lethal casualties
    are subtracted from the swarm population according to the substance's configured
    lethality rate. Repellent substances additionally set the ``repelled`` flag, initiating
    a stochastic random-walk dispersal sequence in the subsequent interaction phase.

    Critically, any swarm whose population reaches zero as a direct result of toxin
    mortality is subjected to immediate localised garbage collection: its spatial-hash
    registration is revoked via ``world.unregister_position`` and the entity is queued for
    bulk destruction via ``world.collect_garbage``. Without this step, zero-population
    swarm entities would persist as "ghost" entries in the spatial hash until the interaction
    phase of the following tick purged them, thereby corrupting O(1) spatial-hash lookups and
    confounding predator-presence evaluations in ``_check_activation_condition``.

    Args:
        sub_id: Toxin layer index.
        lethal: Whether the toxin can kill individuals.
        lethality_rate: Lethal attrition factor.
        repellent: Whether the toxin marks swarms as repelled.
        repellent_walk_ticks: Duration of repelled random-walk behavior.
        env: GridEnvironment providing per-cell toxin concentrations via
            ``env.toxin_layers``.
        world: ECSWorld to iterate swarms, update the spatial hash, and execute GC.
    """
    dead_swarms: list[int] = []

    for entity in list(world.query(SwarmComponent)):
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
    del signal_velocity
    del tick

    for neighbour_id in source_plant.mycorrhizal_connections:
        if not world.has_entity(neighbour_id):
            continue
        neighbour_entity = world.get_entity(neighbour_id)
        if not neighbour_entity.has_component(PlantComponent):
            continue
        neighbour: PlantComponent = neighbour_entity.get_component(PlantComponent)
        if not mycorrhizal_inter_species and neighbour.species_id != source_plant.species_id:
            continue
        # Deposit a per-neighbour budget share; caller enforces total budget conservation.
        if signal_id < env.num_signals:
            env.signal_layers[signal_id, neighbour.x, neighbour.y] += amount


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
        plant_death_causes: Mapping of death causes to their respective counts.
    """
    from phids.api.schemas import TriggerConditionSchema  # avoid circular at module level

    dead_substances: list[int] = []
    dead_plants: list[int] = []
    dead_plant_ids: set[int] = set()

    # ------------------------------------------------------------------
    # 0. Garbage-collect orphaned substances before any trigger checks
    # ------------------------------------------------------------------
    substance_entities = list(world.query(SubstanceComponent))
    for entity in substance_entities:
        sub = entity.get_component(SubstanceComponent)
        if not world.has_entity(sub.owner_plant_id):
            dead_substances.append(entity.entity_id)

    world.collect_garbage(dead_substances)
    dead_substances.clear()
    substance_entities = list(world.query(SubstanceComponent))

    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent] = {}
    active_substance_ids_by_owner: dict[int, set[int]] = {}
    for entity in substance_entities:
        sub = entity.get_component(SubstanceComponent)
        owner_substance_by_key[(sub.owner_plant_id, sub.substance_id)] = sub
        if sub.active:
            active_substance_ids_by_owner.setdefault(sub.owner_plant_id, set()).add(
                sub.substance_id
            )

    swarm_population_by_cell_species = _build_swarm_population_index(world)

    # Toxins are rebuilt from currently active emitters each signaling pass
    # and remain local to living plant tissue. Non-triggered toxins remain
    # active only through configured aftereffects (or indefinitely when
    # irreversible=True).
    env.toxin_layers[:] = 0.0
    env._toxin_layers_write[:] = 0.0

    for entity in substance_entities:
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

            # Check for predator presence at this cell via spatial hash.
            predator_present = (
                swarm_population_by_cell_species.get(
                    (plant.x, plant.y, trig.predator_species_id), 0
                )
                >= trig.min_predator_population
            )

            # Evaluate optional condition trees as an alternative trigger path.
            # This enables alarm-chain behavior where a plant reacts to an
            # already-active internal condition without requiring direct
            # predator co-location on the same cell.
            condition_met = False
            if trig.activation_condition is not None:
                condition_met = _check_activation_condition(
                    plant,
                    plant.entity_id,
                    trig.activation_condition.model_dump(mode="json"),
                    env,
                    swarm_population_by_cell_species,
                    active_substance_ids_by_owner,
                )

            triggered = predator_present or condition_met

            if not triggered:
                continue

            # Ensure a substance entity exists for this (plant, substance_id) pair
            existing_sub = owner_substance_by_key.get((plant.entity_id, trig.substance_id))

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
                owner_substance_by_key[(plant.entity_id, trig.substance_id)] = existing_sub
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
                env,
                swarm_population_by_cell_species,
                active_substance_ids_by_owner,
            ):
                continue
            sub.active = True
            sub.aftereffect_remaining_ticks = sub.aftereffect_ticks
            active_substance_ids_by_owner.setdefault(sub.owner_plant_id, set()).add(
                sub.substance_id
            )

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
    active_toxin_props: dict[int, dict[str, Any]] = {}

    for entity in list(world.query(SubstanceComponent)):
        sub = entity.get_component(SubstanceComponent)
        if not sub.active:
            continue

        if not sub.triggered_this_tick:
            if not sub.irreversible and sub.aftereffect_remaining_ticks <= 0:
                sub.active = False
                active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(
                    sub.substance_id
                )
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
            active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
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
            active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
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
                active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(
                    sub.substance_id
                )
                dead_substances.append(entity.entity_id)
                continue

        if sub.is_toxin:
            if sub.substance_id < env.num_toxins:
                env.toxin_layers[sub.substance_id, plant.x, plant.y] = min(
                    1.0,
                    float(env.toxin_layers[sub.substance_id, plant.x, plant.y])
                    + SUBSTANCE_EMIT_RATE,
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
                    props["lethality_rate"] = max(
                        float(props["lethality_rate"]), sub.lethality_rate
                    )
                    props["repellent"] = bool(props["repellent"] or sub.repellent)
                    props["repellent_walk_ticks"] = max(
                        int(props["repellent_walk_ticks"]),
                        sub.repellent_walk_ticks,
                    )
        else:
            if sub.substance_id < env.num_signals:
                valid_relay_targets = [
                    neighbour_id
                    for neighbour_id in plant.mycorrhizal_connections
                    if world.has_entity(neighbour_id)
                    and world.get_entity(neighbour_id).has_component(PlantComponent)
                    and (
                        mycorrhizal_inter_species
                        or world.get_entity(neighbour_id).get_component(PlantComponent).species_id
                        == plant.species_id
                    )
                ]
                total_slots = 1 + len(valid_relay_targets)
                per_slot_budget = SUBSTANCE_EMIT_RATE / total_slots

                # Airborne and root-relay emission share one fixed per-tick budget.
                env.signal_layers[sub.substance_id, plant.x, plant.y] = (
                    float(env.signal_layers[sub.substance_id, plant.x, plant.y]) + per_slot_budget
                )

                if valid_relay_targets:
                    _relay_signal_via_mycorrhizal(
                        plant,
                        sub.substance_id,
                        per_slot_budget,
                        env,
                        world,
                        mycorrhizal_inter_species,
                        signal_velocity,
                        tick,
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
            active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)
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
                active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(
                    sub.substance_id
                )
        else:
            sub.active = False
            active_substance_ids_by_owner.get(sub.owner_plant_id, set()).discard(sub.substance_id)

    # ------------------------------------------------------------------
    # 5. Diffusion (delegated to GridEnvironment)
    # ------------------------------------------------------------------
    env.diffuse_signals()

    # ------------------------------------------------------------------
    # 6. Garbage collect expired substance entities
    # ------------------------------------------------------------------
    world.collect_garbage(dead_plants)
    world.collect_garbage(dead_substances)
