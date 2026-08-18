# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Lifecycle system: plant growth, mycorrhizal network formation, reproduction, and death.

This module implements the first of three ordered per-tick simulation phases executed by the
PHIDS ``SimulationLoop``. The lifecycle phase applies deterministic physiological dynamics to all
registered plant entities before any herbivore interactions are resolved, ensuring that the energy
state observed by the interaction and signaling phases reflects the current-tick growth outcome.

Per-tick growth increments the energy reserve of each plant by ``base_energy * (growth_rate / 100)``,
clamped to ``max_energy``. Reproduction is attempted on each tick that satisfies the
``reproduction_interval`` constraint and leaves sufficient energy surplus above ``seed_energy_cost``;
the seed is dispersed to a randomly sampled polar coordinate within ``[seed_min_dist, seed_max_dist]``
from the parent, and germination is rejected if the target cell is already occupied by any plant
entity registered in the spatial hash, preventing overcrowding without requiring dense distance
scans. Mycorrhizal root-network formation occurs at configurable intervals (``mycorrhizal_growth_interval_ticks``),
pairing adjacent plants (Manhattan distance 1) that share sufficient energy surplus above their
respective survival thresholds; each connection costs both participants ``connection_cost`` energy
units and is bidirectionally recorded in their ``PlantComponent.mycorrhizal_connections`` sets.
Plants whose energy falls below ``survival_threshold`` are unregistered from the spatial hash,
removed from the energy layer write buffer, and queued for bulk entity destruction via
``ECSWorld.collect_garbage``. Per-cause death counts are accumulated in the ``plant_death_causes``
dict for telemetry attribution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.systems.lifecycle.growth import (
    SLOW_TICK_STRIDE,
    _apply_mycorrhizal_tax_jit,
    _calculate_structural_upkeep_jit,
    _grow,
    _grow_structural,
)
from phids.engine.systems.lifecycle.mycorrhiza import (
    _establish_mycorrhizal_connections,
    _should_attempt_mycorrhizal_growth,
)
from phids.engine.systems.lifecycle.reproduction import _attempt_reproduction
from phids.shared.constants import STRUCTURAL_UPKEEP_SCALAR

if TYPE_CHECKING:
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


def run_lifecycle(
    world: ECSWorld,
    env: GridEnvironment,
    tick: int,
    flora_species_params: dict[int, object],
    mycorrhizal_connection_cost: float = 1.0,
    mycorrhizal_growth_interval_ticks: int = 8,
    mycorrhizal_inter_species: bool = False,
    plant_death_causes: dict[str, int] | None = None,
    force_all_entities: bool = False,
) -> None:
    """Execute one lifecycle tick: grow, connect, reproduce, and cull.

    Under Phase-Staggered Cohort execution, each plant entity updates its accumulated growth,
    mycorrhizal tax, reproduction, and survival checks when (entity_id % 168) == (tick % 168).
    This distributes per-tick computational load evenly across all ticks and eliminates macro
    telemetry sawtooth spikes while preserving full temporal scale conservation.

    Args:
        world: The ECS world registry.
        env: The GridEnvironment instance.
        tick: Current simulation tick index.
        flora_species_params: Mapping of species_id to species parameters.
        mycorrhizal_connection_cost: Energy cost per new root connection.
        mycorrhizal_growth_interval_ticks: Ticks between new root-growth
            attempts. At most one new link is created per attempt.
        mycorrhizal_inter_species: Allow inter-species root connections.
        plant_death_causes: Mapping of death causes to their respective counts.
        force_all_entities: Bypass phase-staggering cohort masks and update all entities.
    """
    dead: list[int] = []

    for entity in world.query(PlantComponent):
        plant: PlantComponent = entity.get_component(PlantComponent)
        plant.last_energy_loss_cause = None

        # Phase-Staggered Cohort check: update only entities in the active cohort for this tick
        if not force_all_entities and (plant.entity_id % SLOW_TICK_STRIDE) != (tick % SLOW_TICK_STRIDE):
            continue

        # Growth (Caloric Energy & Permanent Structural Mass)
        _grow(plant, tick)
        _grow_structural(plant, env)

        # Plan 3: Deduct M_structural-scaled maintenance cost
        upkeep_fee = _calculate_structural_upkeep_jit(
            plant.survival_threshold, plant.structural_mass, plant.max_structural_mass, STRUCTURAL_UPKEEP_SCALAR
        )
        if upkeep_fee > 0.0:
            plant.energy = max(0.0, plant.energy - upkeep_fee)

        # Apply continuous mycorrhizal carbon tax (256-bit SIMD JIT helper)
        if plant.mycorrhizal_tax_per_link > 0.0 and plant.mycorrhizal_connections:
            plant.energy = _apply_mycorrhizal_tax_jit(
                plant.energy, plant.mycorrhizal_tax_per_link, len(plant.mycorrhizal_connections)
            )

        # Reproduction
        _attempt_reproduction(plant, tick, world, env, flora_species_params)

        # Update biotope energy
        env.set_plant_energy(plant.x, plant.y, plant.species_id, plant.energy)
        env.set_apparent_nutrition(plant.x, plant.y, plant.apparent_nutrition_factor)

        # Prune dead mycorrhizal links
        plant.mycorrhizal_connections = {eid for eid in plant.mycorrhizal_connections if world.has_entity(eid)}

        # Survival check
        if plant.energy < plant.survival_threshold:
            cause_key = plant.last_energy_loss_cause or "death_background_deficit"
            if plant_death_causes is not None:
                plant_death_causes[cause_key] = plant_death_causes.get(cause_key, 0) + 1
            env.clear_plant_energy(plant.x, plant.y, plant.species_id)
            env.clear_structural_mass(plant.x, plant.y, plant.species_id)
            world.unregister_position(entity.entity_id, plant.x, plant.y)
            dead.append(entity.entity_id)

    # Establish new mycorrhizal root connections between adjacent plants
    if _should_attempt_mycorrhizal_growth(tick, mycorrhizal_growth_interval_ticks):
        _, mycorrhiza_dead = _establish_mycorrhizal_connections(
            world,
            env,
            mycorrhizal_connection_cost,
            mycorrhizal_inter_species,
            excluded_entity_ids=set(dead),
            plant_death_causes=plant_death_causes,
        )
        dead.extend(mycorrhiza_dead)

    world.collect_garbage(dead)
