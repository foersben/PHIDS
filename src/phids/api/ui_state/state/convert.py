# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Functions to convert draft state to and from simulation configuration."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Literal, cast

from phids.api.ui_state.state.models import DraftState
from phids.api.ui_state.triggers import TriggerRule

if TYPE_CHECKING:
    from phids.api.schemas.simulation import SimulationConfig
    from phids.api.schemas.triggers import TriggerConditionSchema
    from phids.api.ui_state.substances import SubstanceDefinition

logger = logging.getLogger(__name__)


def _build_triggers_by_flora(
    trigger_rules: list[TriggerRule], subs_by_id: dict[int, SubstanceDefinition]
) -> dict[int, list[TriggerConditionSchema]]:
    """Build triggers for each flora species.

    Args:
        trigger_rules: The trigger rules.
        subs_by_id: The substance definitions.

    Returns:
        The triggers for each flora species.
    """
    from phids.api.schemas.triggers import (
        EnvironmentalSignalInitiator,
        HerbivoreAttackInitiator,
        ResourceWithdrawalAction,
        SynthesizeSubstanceAction,
        TriggerConditionSchema,
    )

    triggers_by_flora: dict[int, list[TriggerConditionSchema]] = {}
    for rule in trigger_rules:
        initiator: EnvironmentalSignalInitiator | HerbivoreAttackInitiator
        if rule.initiator_type == "environmental_signal":
            initiator = EnvironmentalSignalInitiator(
                signal_id=rule.initiator_signal_id,
                min_concentration=rule.initiator_min_concentration,
            )
        else:
            initiator = HerbivoreAttackInitiator(
                herbivore_species_id=rule.herbivore_species_id,
                min_herbivore_population=rule.min_herbivore_population,
            )
        action: ResourceWithdrawalAction | SynthesizeSubstanceAction
        if rule.action_type == "resource_withdrawal" or rule.substance_id == -1:
            action = ResourceWithdrawalAction(
                apparent_nutrition_factor=rule.apparent_nutrition_factor,
                withdrawal_duration=rule.withdrawal_duration,
            )
            aftereffect = rule.aftereffect_ticks
        else:
            sd = subs_by_id.get(rule.substance_id)
            if sd is None:
                continue
            action = SynthesizeSubstanceAction(
                substance_id=rule.substance_id,
                synthesis_duration=sd.synthesis_duration,
                is_toxin=sd.is_toxin,
                lethal=sd.lethal,
                lethality_rate=sd.lethality_rate,
                repellent=sd.repellent,
                repellent_walk_ticks=sd.repellent_walk_ticks,
                energy_cost_per_tick=sd.energy_cost_per_tick,
                irreversible=sd.irreversible,
            )
            aftereffect = sd.aftereffect_ticks
        triggers_by_flora.setdefault(rule.flora_species_id, []).append(
            TriggerConditionSchema(
                initiator=initiator,
                aftereffect_ticks=aftereffect,
                activation_condition=cast("Any", deepcopy(rule.activation_condition)),
                action=action,
            )
        )
    return triggers_by_flora


def build_sim_config(state: DraftState) -> SimulationConfig:
    """Assemble a :class:`~phids.api.schemas.SimulationConfig`.

    Args:
        state: The draft state to convert.

    Returns:
        SimulationConfig: Validated simulation configuration.

    Raises:
        ValueError: If no flora or herbivore species defined.
    """
    from phids.api.schemas.placement import (
        InitialPlantPlacement,
        InitialSwarmPlacement,
    )
    from phids.api.schemas.simulation import SimulationConfig
    from phids.api.schemas.species import DietCompatibilityMatrix, FloraSpeciesParams

    if not state.flora_species or not state.herbivore_species:
        logger.warning(
            "Draft build rejected because required species are missing (flora=%d, herbivores=%d)",
            len(state.flora_species),
            len(state.herbivore_species),
        )
        raise ValueError("At least one flora and one herbivore species are required.")

    subs_by_id: dict[int, SubstanceDefinition] = {sd.substance_id: sd for sd in state.substance_definitions}

    triggers_by_flora = _build_triggers_by_flora(state.trigger_rules, subs_by_id)

    flora_with_triggers: list[FloraSpeciesParams] = []
    for fp in state.flora_species:
        triggers = triggers_by_flora.get(fp.species_id, [])
        flora_with_triggers.append(fp.model_copy(update={"triggers": triggers}))

    n_herbivore = len(state.herbivore_species)
    n_flora = len(flora_with_triggers)
    diet_rows = [
        (state.diet_matrix[pi][:n_flora] if pi < len(state.diet_matrix) else [False] * n_flora)
        for pi in range(n_herbivore)
    ]

    plant_placements = [
        InitialPlantPlacement(species_id=p.species_id, x=p.x, y=p.y, energy=p.energy) for p in state.initial_plants
    ]
    swarm_placements = [
        InitialSwarmPlacement(
            species_id=s.species_id,
            x=s.x,
            y=s.y,
            population=s.population,
            energy=s.energy,
        )
        for s in state.initial_swarms
    ]

    config = SimulationConfig(
        placement_mode=state.placement_mode,
        flora_placement_strategy=state.flora_placement_strategy,
        herbivore_placement_strategy=state.herbivore_placement_strategy,
        grid_width=state.grid_width,
        grid_height=state.grid_height,
        max_ticks=state.max_ticks,
        tick_rate_hz=state.tick_rate_hz,
        num_signals=state.num_signals,
        num_toxins=state.num_toxins,
        wind_x=state.wind_x,
        wind_y=state.wind_y,
        flora_species=flora_with_triggers,
        herbivore_species=state.herbivore_species,
        diet_matrix=DietCompatibilityMatrix(rows=diet_rows),
        initial_plants=plant_placements,
        initial_swarms=swarm_placements,
        mycorrhizal_inter_species=state.mycorrhizal_inter_species,
        mycorrhizal_connection_cost=state.mycorrhizal_connection_cost,
        mycorrhizal_growth_interval_ticks=state.mycorrhizal_growth_interval_ticks,
        mycorrhizal_signal_velocity=state.mycorrhizal_signal_velocity,
        z2_flora_species_extinction=state.z2_flora_species_extinction,
        z4_herbivore_species_extinction=state.z4_herbivore_species_extinction,
        z6_max_total_flora_energy=state.z6_max_total_flora_energy,
        z7_max_total_herbivore_population=state.z7_max_total_herbivore_population,
        signal_decay_factor=state.signal_decay_factor,
        substance_emit_rate=state.substance_emit_rate,
    )
    logger.info(
        (
            "Draft converted to SimulationConfig "
            "(grid=%dx%d, flora=%d, herbivores=%d, trigger_rules=%d, plants=%d, swarms=%d)"
        ),
        state.grid_width,
        state.grid_height,
        len(flora_with_triggers),
        len(state.herbivore_species),
        len(state.trigger_rules),
        len(state.initial_plants),
        len(state.initial_swarms),
    )
    return config


def _import_trigger_rule(
    trig: TriggerConditionSchema,
    flora_spec_id: int,
    seen_substance_ids: set[int],
    imported_substances: list[SubstanceDefinition],
    imported_trigger_rules: list[TriggerRule],
) -> None:
    from phids.api.schemas.triggers import HerbivoreAttackInitiator, SynthesizeSubstanceAction
    from phids.api.ui_state.substances import SubstanceDefinition

    i_type: Literal["herbivore_attack", "environmental_signal"]
    if isinstance(trig.initiator, HerbivoreAttackInitiator):
        i_type = "herbivore_attack"
        h_id = trig.initiator.herbivore_species_id
        min_pop = trig.initiator.min_herbivore_population
        sig_id = -1
        min_conc = 0.0
    else:
        i_type = "environmental_signal"
        h_id = -1
        min_pop = 0
        sig_id = trig.initiator.signal_id
        min_conc = trig.initiator.min_concentration

    imported_trigger_rules.append(
        TriggerRule(
            flora_species_id=flora_spec_id,
            initiator_type=i_type,
            herbivore_species_id=h_id,
            min_herbivore_population=min_pop,
            initiator_signal_id=sig_id,
            initiator_min_concentration=min_conc,
            substance_id=(trig.action.substance_id if isinstance(trig.action, SynthesizeSubstanceAction) else -1),
            activation_condition=(
                trig.activation_condition.model_dump(mode="json") if trig.activation_condition is not None else None
            ),
        )
    )

    if isinstance(trig.action, SynthesizeSubstanceAction):
        if trig.action.substance_id not in seen_substance_ids:
            seen_substance_ids.add(trig.action.substance_id)
            imported_substances.append(
                SubstanceDefinition(
                    substance_id=trig.action.substance_id,
                    name=f"Substance {trig.action.substance_id}",
                    is_toxin=trig.action.is_toxin,
                    lethal=trig.action.lethal,
                    repellent=trig.action.repellent,
                    synthesis_duration=trig.action.synthesis_duration,
                    aftereffect_ticks=trig.aftereffect_ticks,
                    lethality_rate=trig.action.lethality_rate,
                    repellent_walk_ticks=trig.action.repellent_walk_ticks,
                    energy_cost_per_tick=trig.action.energy_cost_per_tick,
                    irreversible=trig.action.irreversible,
                )
            )


def from_sim_config(config: SimulationConfig, scenario_name: str = "") -> DraftState:
    """Reconstruct a ``DraftState`` from a validated :class:`SimulationConfig`.

    Args:
        config: Validated simulation configuration to reconstruct from.
        scenario_name: Human-readable label; defaults to the grid dimensions.

    Returns:
        DraftState: Reconstructed draft ready for use in the builder UI.
    """
    from phids.api.ui_state.placements import PlacedPlant, PlacedSwarm

    imported_trigger_rules: list[TriggerRule] = []
    imported_substances: list[SubstanceDefinition] = []
    seen_substance_ids: set[int] = set()

    for flora_spec in config.flora_species:
        for trig in flora_spec.triggers:
            _import_trigger_rule(
                trig,
                flora_spec.species_id,
                seen_substance_ids,
                imported_substances,
                imported_trigger_rules,
            )

    return DraftState(
        scenario_name=scenario_name or f"{config.grid_width}x{config.grid_height}",
        grid_width=config.grid_width,
        grid_height=config.grid_height,
        max_ticks=config.max_ticks,
        tick_rate_hz=config.tick_rate_hz,
        wind_x=config.wind_x,
        wind_y=config.wind_y,
        num_signals=config.num_signals,
        num_toxins=config.num_toxins,
        z2_flora_species_extinction=config.z2_flora_species_extinction,
        z4_herbivore_species_extinction=config.z4_herbivore_species_extinction,
        z6_max_total_flora_energy=config.z6_max_total_flora_energy,
        z7_max_total_herbivore_population=config.z7_max_total_herbivore_population,
        signal_decay_factor=config.signal_decay_factor,
        substance_emit_rate=config.substance_emit_rate,
        mycorrhizal_inter_species=config.mycorrhizal_inter_species,
        mycorrhizal_connection_cost=config.mycorrhizal_connection_cost,
        mycorrhizal_growth_interval_ticks=config.mycorrhizal_growth_interval_ticks,
        mycorrhizal_signal_velocity=config.mycorrhizal_signal_velocity,
        placement_mode=config.placement_mode,
        flora_placement_strategy=config.flora_placement_strategy,
        herbivore_placement_strategy=config.herbivore_placement_strategy,
        flora_species=list(config.flora_species),
        herbivore_species=list(config.herbivore_species),
        diet_matrix=[list(row) for row in config.diet_matrix.rows],
        trigger_rules=imported_trigger_rules,
        substance_definitions=imported_substances,
        initial_plants=[
            PlacedPlant(species_id=p.species_id, x=p.x, y=p.y, energy=p.energy) for p in config.initial_plants
        ],
        initial_swarms=[
            PlacedSwarm(
                species_id=s.species_id,
                x=s.x,
                y=s.y,
                population=s.population,
                energy=s.energy,
            )
            for s in config.initial_swarms
        ],
    )
