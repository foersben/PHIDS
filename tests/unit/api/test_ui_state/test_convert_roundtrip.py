# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests verifying lossless SimulationConfig <-> DraftState trigger round-trips."""

from __future__ import annotations

from phids.api.schemas.conditions import SubstanceActiveConditionSchema
from phids.api.schemas.simulation import SimulationConfig
from phids.api.schemas.species import (
    DietCompatibilityMatrix,
    FloraSpeciesParams,
    HerbivoreSpeciesParams,
)
from phids.api.schemas.triggers import (
    EnvironmentalSignalInitiator,
    HerbivoreAttackInitiator,
    ResourceWithdrawalAction,
    SynthesizeSubstanceAction,
    TriggerConditionSchema,
)
from phids.api.ui_state.state.convert import build_sim_config, from_sim_config


def test_draft_state_round_trip_preserves_triggers_hill_and_withdrawal() -> None:
    """Verify from_sim_config -> build_sim_config preserves Hill curves, withdrawal, and dual latencies."""
    unprimed_rule = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=4),
        action=SynthesizeSubstanceAction(substance_id=3, synthesis_duration=16, is_toxin=True, lethal=True),
        aftereffect_ticks=24,
    )
    primed_rule = TriggerConditionSchema(
        initiator=HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=2),
        activation_condition=SubstanceActiveConditionSchema(kind="substance_active", substance_id=0),
        action=SynthesizeSubstanceAction(substance_id=3, synthesis_duration=4, is_toxin=True, lethal=True),
        aftereffect_ticks=40,
    )
    hill_rule = TriggerConditionSchema(
        initiator=EnvironmentalSignalInitiator(
            signal_id=0,
            min_concentration=0.08,
            response_curve="hill",
            half_saturation=0.14,
            hill_cooperativity=3.25,
        ),
        action=SynthesizeSubstanceAction(substance_id=1, synthesis_duration=7),
        aftereffect_ticks=15,
    )
    withdrawal_rule = TriggerConditionSchema(
        initiator=EnvironmentalSignalInitiator(signal_id=1, min_concentration=0.05),
        action=ResourceWithdrawalAction(apparent_nutrition_factor=0.35, withdrawal_duration=22),
        aftereffect_ticks=18,
    )

    config = SimulationConfig(
        grid_width=16,
        grid_height=16,
        max_ticks=20,
        num_signals=2,
        num_toxins=2,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="P0",
                base_energy=10.0,
                max_energy=100.0,
                growth_rate=1.0,
                survival_threshold=1.0,
                reproduction_interval=20,
                seed_min_energy=40.0,
                seed_energy_cost=5.0,
                triggers=[unprimed_rule, primed_rule, hill_rule, withdrawal_rule],
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="H0",
                energy_min=1.0,
                velocity=1,
                consumption_rate=1.0,
                reproduction_energy_divisor=2.0,
                split_population_threshold=20,
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
    )

    draft = from_sim_config(config)
    rebuilt = build_sim_config(draft)
    rebuilt_triggers = rebuilt.flora_species[0].triggers
    assert len(rebuilt_triggers) == 4

    t0, t1, t2, t3 = rebuilt_triggers
    assert isinstance(t0.action, SynthesizeSubstanceAction)
    assert isinstance(t1.action, SynthesizeSubstanceAction)
    assert t0.action.substance_id == 3 and t0.action.synthesis_duration == 16 and t0.aftereffect_ticks == 24
    assert t1.action.substance_id == 3 and t1.action.synthesis_duration == 4 and t1.aftereffect_ticks == 40
    assert isinstance(t1.activation_condition, SubstanceActiveConditionSchema)

    assert isinstance(t2.initiator, EnvironmentalSignalInitiator)
    assert t2.initiator.response_curve == "hill"
    assert t2.initiator.half_saturation == 0.14
    assert t2.initiator.hill_cooperativity == 3.25
    assert isinstance(t2.action, SynthesizeSubstanceAction)
    assert t2.action.synthesis_duration == 7 and t2.aftereffect_ticks == 15

    assert isinstance(t3.action, ResourceWithdrawalAction)
    assert t3.action.apparent_nutrition_factor == 0.35
    assert t3.action.withdrawal_duration == 22
    assert t3.aftereffect_ticks == 18
