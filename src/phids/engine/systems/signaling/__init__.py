# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Signaling system: substance synthesis, activation, emission, diffusion, and toxin effects.

This module implements the third and final per-tick simulation phase of the PHIDS engine,
governing the full lifecycle of volatile organic compound (VOC) signals and defensive toxins.
The signaling phase is executed after both the lifecycle and interaction phases have committed
their energy mutations, ensuring that plant survival status and herbivore co-location data reflect
the current tick's resolved state before chemical-defense decisions are made.

The phase proceeds through six ordered sub-steps. First, orphaned substance entities whose owner
plants were destroyed in earlier phases are garbage-collected. Second, trigger-condition trees are
evaluated for each living plant against the per-cell herbivore census index
(``_build_swarm_population_index``): direct herbivore co-presence (``herbivore_presence`` nodes) or
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

from typing import TYPE_CHECKING

from phids.engine.systems.signaling.emission import _phase_emit_signals_and_toxins
from phids.engine.systems.signaling.lifecycle import (
    _phase_index_and_clean_substances,
    _phase_manage_nutrition_recovery,
    _phase_process_aftereffects,
)
from phids.engine.systems.signaling.spatial import _build_swarm_population_index
from phids.engine.systems.signaling.synthesis import _phase_advance_synthesis
from phids.engine.systems.signaling.triggers import _phase_evaluate_triggers

if TYPE_CHECKING:
    from phids.api.schemas import TriggerConditionSchema
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld


def run_signaling(
    world: ECSWorld,
    env: GridEnvironment,
    trigger_conditions: dict[int, list[TriggerConditionSchema]],
    mycorrhizal_inter_species: bool,
    signal_velocity: int,
    tick: int,  # noqa: ARG001
    plant_death_causes: dict[str, int] | None = None,
    substance_emit_rate: float = 0.1,
    signal_decay_factor: float = 0.85,
) -> None:
    """Execute one signaling tick, handling synthesis, emission and diffusion.

    Args:
        world: The central ECSWorld instance containing all entity component mappings and active systems.
        env: Grid environment holding signal/toxin layers.
        trigger_conditions: Mapping of flora species_id to trigger schemas.
        mycorrhizal_inter_species: Whether inter-species mycorrhizal signaling
            is permitted.
        signal_velocity: Ticks per hop for root-network relays.
        tick: Current simulation tick.
        plant_death_causes: Mapping of death causes to their respective counts.
        substance_emit_rate: Concentration increment added per tick when an active
            SubstanceComponent emits. Defaults to 0.1 (module-level constant value).
        signal_decay_factor: Per-tick airborne signal retention after Gaussian diffusion
            (0.0-1.0). Defaults to 0.85 (module-level constant value).

    """
    dead_substances: list[int] = []
    dead_plants: list[int] = []
    dead_plant_ids: set[int] = set()

    owner_substance_by_key, active_substance_ids_by_owner = _phase_index_and_clean_substances(world, dead_substances)

    swarm_population_by_cell_species = _build_swarm_population_index(world)

    env.toxin_layers[:] = 0.0
    env._toxin_layers_write[:] = 0.0

    _phase_evaluate_triggers(
        world,
        env,
        trigger_conditions,
        owner_substance_by_key,
        swarm_population_by_cell_species,
        active_substance_ids_by_owner,
    )

    _phase_manage_nutrition_recovery(world)

    _phase_advance_synthesis(
        world,
        env,
        swarm_population_by_cell_species,
        active_substance_ids_by_owner,
        dead_substances,
    )

    _phase_emit_signals_and_toxins(
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
    )

    _phase_process_aftereffects(
        world,
        active_substance_ids_by_owner,
        dead_plant_ids,
        dead_substances,
    )

    env.diffuse_signals(signal_decay_factor=signal_decay_factor)

    world.collect_garbage(dead_plants)
    world.collect_garbage(dead_substances)
