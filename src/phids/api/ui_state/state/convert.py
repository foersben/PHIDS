# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Functions to convert draft state to and from simulation configuration."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Literal, NamedTuple, cast

from phids.api.schemas.placement import (
    InitialPlantPlacement,
    InitialSwarmPlacement,
)
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import DietCompatibilityMatrix, FloraSpeciesParams
from phids.api.schemas.triggers import (
    EnvironmentalSignalInitiator,
    HerbivoreAttackInitiator,
    ResourceWithdrawalAction,
    SynthesizeSubstanceAction,
    TriggerConditionSchema,
)
from phids.api.ui_state.placements import PlacedPlant, PlacedSwarm
from phids.api.ui_state.state.models import DraftState
from phids.api.ui_state.substances import SubstanceDefinition
from phids.api.ui_state.triggers import TriggerRule

logger = logging.getLogger(__name__)


class _ResolvedTriggerAction(NamedTuple):
    """Typed pair binding a compiled trigger action to its resolved aftereffect duration."""

    action: ResourceWithdrawalAction | SynthesizeSubstanceAction
    aftereffect: int


def _build_trigger_initiator(rule: TriggerRule) -> EnvironmentalSignalInitiator | HerbivoreAttackInitiator:
    """Construct the schema initiator node corresponding to a UI trigger rule."""
    if rule.initiator_type == "environmental_signal":
        return EnvironmentalSignalInitiator(
            signal_id=rule.initiator_signal_id,
            min_concentration=rule.initiator_min_concentration,
            response_curve=rule.initiator_response_curve,
            hill_cooperativity=rule.initiator_hill_cooperativity,
            half_saturation=rule.initiator_half_saturation,
        )
    return HerbivoreAttackInitiator(
        herbivore_species_id=rule.herbivore_species_id,
        min_herbivore_population=rule.min_herbivore_population,
    )


def _build_trigger_action(
    rule: TriggerRule, subs_by_id: dict[int, SubstanceDefinition]
) -> _ResolvedTriggerAction | None:
    """Resolve trigger action schema and aftereffect ticks, returning ``None`` when substance ID is absent."""
    if rule.action_type == "resource_withdrawal" or rule.substance_id == -1:
        return _ResolvedTriggerAction(
            action=ResourceWithdrawalAction(
                apparent_nutrition_factor=rule.apparent_nutrition_factor,
                withdrawal_duration=rule.withdrawal_duration,
            ),
            aftereffect=rule.aftereffect_ticks,
        )
    sd = subs_by_id.get(rule.substance_id)
    if sd is None:
        return None
    synth_dur = rule.synthesis_duration if rule.synthesis_duration is not None else sd.synthesis_duration
    aftereffect = (
        rule.aftereffect_ticks_override if rule.aftereffect_ticks_override is not None else sd.aftereffect_ticks
    )
    return _ResolvedTriggerAction(
        action=SynthesizeSubstanceAction(
            substance_id=rule.substance_id,
            synthesis_duration=synth_dur,
            is_toxin=sd.is_toxin,
            lethal=sd.lethal,
            lethality_rate=sd.lethality_rate,
            repellent=sd.repellent,
            repellent_walk_ticks=sd.repellent_walk_ticks,
            energy_cost_per_tick=sd.energy_cost_per_tick,
            irreversible=sd.irreversible,
        ),
        aftereffect=aftereffect,
    )


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
    triggers_by_flora: dict[int, list[TriggerConditionSchema]] = {}
    for rule in trigger_rules:
        resolved = _build_trigger_action(rule, subs_by_id)
        if resolved is None:
            continue
        triggers_by_flora.setdefault(rule.flora_species_id, []).append(
            TriggerConditionSchema(
                initiator=_build_trigger_initiator(rule),
                aftereffect_ticks=resolved.aftereffect,
                activation_condition=cast("Any", deepcopy(rule.activation_condition)),
                action=resolved.action,
            )
        )
    return triggers_by_flora


def build_sim_config(state: DraftState) -> SimulationConfig:
    """Assemble a :class:`~phids.api.schemas.SimulationConfig`.

    Why: Decoupling UI builder accumulation from frozen engine schemas ensures partial edits in web forms cannot inject invalid species indices, dangling trigger substance IDs, or inconsistent diet matrix dimensions into ``SimulationLoop``.

    How: The translator validates non-empty flora and herbivore species sets, compiles trigger-rule graphs per flora species with resolved substance properties, trims the boolean diet matrix to ``(N_herbivore, N_flora)``, maps initial placements, and validates the resulting Pydantic ``SimulationConfig``.

    Args:
        state: The draft state to convert.

    Returns:
        SimulationConfig: Validated simulation configuration.

    Raises:
        ValueError: If no flora or herbivore species defined.
    """
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


class _ExtractedInitiatorFields(NamedTuple):
    """Flattened UI draft initiator fields decoded from a simulation trigger schema."""

    initiator_type: Literal["herbivore_attack", "environmental_signal"]
    herbivore_species_id: int
    min_herbivore_population: int
    initiator_signal_id: int
    initiator_min_concentration: float
    initiator_response_curve: Literal["step", "hill", "logarithmic"]
    initiator_hill_cooperativity: float
    initiator_half_saturation: float


class _ExtractedActionFields(NamedTuple):
    """Flattened UI draft action fields decoded from a simulation trigger schema."""

    action_type: Literal["synthesize_substance", "resource_withdrawal"]
    substance_id: int
    synthesis_duration: int | None
    apparent_nutrition_factor: float
    withdrawal_duration: int


def _initiator_to_fields(
    initiator: EnvironmentalSignalInitiator | HerbivoreAttackInitiator,
) -> _ExtractedInitiatorFields:
    """Flatten a trigger initiator schema into draft UI rule attributes."""
    if isinstance(initiator, HerbivoreAttackInitiator):
        return _ExtractedInitiatorFields(
            initiator_type="herbivore_attack",
            herbivore_species_id=initiator.herbivore_species_id,
            min_herbivore_population=initiator.min_herbivore_population,
            initiator_signal_id=-1,
            initiator_min_concentration=0.0,
            initiator_response_curve="step",
            initiator_hill_cooperativity=2.0,
            initiator_half_saturation=0.05,
        )
    return _ExtractedInitiatorFields(
        initiator_type="environmental_signal",
        herbivore_species_id=-1,
        min_herbivore_population=0,
        initiator_signal_id=initiator.signal_id,
        initiator_min_concentration=initiator.min_concentration,
        initiator_response_curve=initiator.response_curve,
        initiator_hill_cooperativity=initiator.hill_cooperativity,
        initiator_half_saturation=initiator.half_saturation,
    )


def _action_to_fields(
    action: ResourceWithdrawalAction | SynthesizeSubstanceAction,
) -> _ExtractedActionFields:
    """Flatten a trigger action schema into draft UI rule attributes."""
    if isinstance(action, SynthesizeSubstanceAction):
        return _ExtractedActionFields(
            action_type="synthesize_substance",
            substance_id=action.substance_id,
            synthesis_duration=action.synthesis_duration,
            apparent_nutrition_factor=0.2,
            withdrawal_duration=10,
        )
    return _ExtractedActionFields(
        action_type="resource_withdrawal",
        substance_id=-1,
        synthesis_duration=None,
        apparent_nutrition_factor=action.apparent_nutrition_factor,
        withdrawal_duration=action.withdrawal_duration,
    )


def _record_substance_definition(
    action: ResourceWithdrawalAction | SynthesizeSubstanceAction,
    aftereffect_ticks: int,
    seen_ids: set[int],
    out: list[SubstanceDefinition],
) -> None:
    """Collect a unique UI substance definition when the trigger action synthesises a substance."""
    if not isinstance(action, SynthesizeSubstanceAction):
        return
    if action.substance_id in seen_ids:
        return
    seen_ids.add(action.substance_id)
    out.append(
        SubstanceDefinition(
            substance_id=action.substance_id,
            name=f"Substance {action.substance_id}",
            is_toxin=action.is_toxin,
            lethal=action.lethal,
            repellent=action.repellent,
            synthesis_duration=action.synthesis_duration,
            aftereffect_ticks=aftereffect_ticks,
            lethality_rate=action.lethality_rate,
            repellent_walk_ticks=action.repellent_walk_ticks,
            energy_cost_per_tick=action.energy_cost_per_tick,
            irreversible=action.irreversible,
        )
    )


def _extract_triggers(
    config: SimulationConfig,
) -> tuple[list[TriggerRule], list[SubstanceDefinition]]:
    """Extract trigger rules and substance definitions from simulation config."""
    imported_trigger_rules: list[TriggerRule] = []
    imported_substances: list[SubstanceDefinition] = []
    seen_substance_ids: set[int] = set()

    for flora_spec in config.flora_species:
        for trig in flora_spec.triggers:
            init_f = _initiator_to_fields(trig.initiator)
            act_f = _action_to_fields(trig.action)
            activation = (
                trig.activation_condition.model_dump(mode="json") if trig.activation_condition is not None else None
            )
            imported_trigger_rules.append(
                TriggerRule(
                    flora_species_id=flora_spec.species_id,
                    initiator_type=init_f.initiator_type,
                    herbivore_species_id=init_f.herbivore_species_id,
                    min_herbivore_population=init_f.min_herbivore_population,
                    initiator_signal_id=init_f.initiator_signal_id,
                    initiator_min_concentration=init_f.initiator_min_concentration,
                    initiator_response_curve=init_f.initiator_response_curve,
                    initiator_hill_cooperativity=init_f.initiator_hill_cooperativity,
                    initiator_half_saturation=init_f.initiator_half_saturation,
                    substance_id=act_f.substance_id,
                    action_type=act_f.action_type,
                    synthesis_duration=act_f.synthesis_duration,
                    apparent_nutrition_factor=act_f.apparent_nutrition_factor,
                    withdrawal_duration=act_f.withdrawal_duration,
                    aftereffect_ticks=trig.aftereffect_ticks,
                    aftereffect_ticks_override=trig.aftereffect_ticks,
                    activation_condition=activation,
                )
            )
            _record_substance_definition(trig.action, trig.aftereffect_ticks, seen_substance_ids, imported_substances)
    return imported_trigger_rules, imported_substances


def from_sim_config(config: SimulationConfig, scenario_name: str = "") -> DraftState:
    """Reconstruct a ``DraftState`` from a validated :class:`SimulationConfig`.

    Args:
        config: Validated simulation configuration to reconstruct from.
        scenario_name: Human-readable label; defaults to the grid dimensions.

    Returns:
        DraftState: Reconstructed draft ready for use in the builder UI.
    """
    imported_trigger_rules, imported_substances = _extract_triggers(config)

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
