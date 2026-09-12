# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Helper functions for converting SimulationConfig to DraftState objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from phids.api.ui_state.triggers import TriggerRule

if TYPE_CHECKING:
    from phids.api.schemas.species import FloraSpeciesParams
    from phids.api.ui_state.substances import SubstanceDefinition


def _import_trigger_rules_from_flora(
    flora_spec: FloraSpeciesParams,
    seen_substance_ids: set[int],
    imported_trigger_rules: list[TriggerRule],
    imported_substances: list[SubstanceDefinition],
) -> None:
    """Import trigger rules and substances from a single flora species configuration.

    Args:
        flora_spec: The flora species parameters to import triggers from.
        seen_substance_ids: A set to keep track of imported substance IDs.
        imported_trigger_rules: A list to append imported trigger rules to.
        imported_substances: A list to append imported substance definitions to.
    """
    from phids.api.schemas.triggers import HerbivoreAttackInitiator, SynthesizeSubstanceAction
    from phids.api.ui_state.substances import SubstanceDefinition

    for trig in flora_spec.triggers:
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
                flora_species_id=flora_spec.species_id,
                initiator_type=i_type,
                herbivore_species_id=h_id,
                min_herbivore_population=min_pop,
                initiator_signal_id=sig_id,
                initiator_min_concentration=min_conc,
                substance_id=getattr(trig.action, "substance_id", -1),
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
