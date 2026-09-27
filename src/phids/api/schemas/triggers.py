# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Trigger action schemas and the TriggerConditionSchema interaction-matrix entry.

``TriggerAction`` is a discriminated union of two concrete action types:
``SynthesizeSubstanceAction`` (active chemical defense) and
``ResourceWithdrawalAction`` (apparent nutrition reduction / stress response).
``TriggerConditionSchema`` maps a (plant, herbivore) species pair to an action
and an optional compound activation-condition predicate tree.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from phids.api.schemas.base import HerbivoreId, StrictBaseModel, SubstanceId
from phids.api.schemas.conditions import ConditionNode


class SynthesizeSubstanceAction(StrictBaseModel):
    """Action to synthesize a specific chemical substance."""

    type: Literal["synthesize_substance"] = "synthesize_substance"
    substance_id: SubstanceId = Field(..., description="[ID] Substance to synthesise.")
    synthesis_duration: int = Field(..., gt=0, description="[Ticks] Ticks to synthesise T(s_x).")
    is_toxin: bool = Field(default=False, description="[Flag] True for toxins, False for signals.")
    lethal: bool = Field(default=False, description="[Flag] Lethal toxin flag.")
    lethality_rate: float = Field(default=0.0, ge=0.0, description="[Absolute] Individuals eliminated per tick.")
    repellent: bool = Field(default=False, description="[Flag] Repellent toxin flag.")
    repellent_walk_ticks: int = Field(default=0, ge=0, description="[Ticks] Random-walk duration k on repel trigger.")
    energy_cost_per_tick: float = Field(
        default=0.0, ge=0.0, description="[Absolute] Energy drained from the plant per tick while active."
    )
    irreversible: bool = Field(
        default=False,
        description="If true, activation is irreversible: once active, the substance remains active until owner death.",
    )


class ResourceWithdrawalAction(StrictBaseModel):
    """Action to trigger apparent nutrition withdrawal (stress response)."""

    type: Literal["resource_withdrawal"] = "resource_withdrawal"
    apparent_nutrition_factor: float = Field(
        default=1.0, ge=0.0, le=1.0, description="[%] Multiplier for energy apparent to herbivores and flow field."
    )
    withdrawal_duration: int = Field(
        default=10,
        ge=1,
        description=(
            "[Ticks] Duration of the nutrition withdrawal. It determines how many ticks the apparent "
            "nutrition factor will remain dimmed. Note that the duration is immediately decremented by 1 at the end "
            "of the tick the trigger fires, so a duration of 1 means it recovers on the next tick."
        ),
    )


TriggerAction = Annotated[SynthesizeSubstanceAction | ResourceWithdrawalAction, Field(discriminator="type")]


class HerbivoreAttackInitiator(StrictBaseModel):
    """Initiator that triggers when a herbivore population reaches a threshold."""

    type: Literal["herbivore_attack"] = "herbivore_attack"
    herbivore_species_id: HerbivoreId
    min_herbivore_population: int = Field(..., gt=0, description="Minimum swarm size n_i,min to trigger the rule.")


class EnvironmentalSignalInitiator(StrictBaseModel):
    """Initiator that triggers when an environmental signal reaches a concentration threshold."""

    type: Literal["environmental_signal"] = "environmental_signal"
    signal_id: int = Field(..., ge=0, description="The substance ID of the environmental signal to monitor.")
    min_concentration: float = Field(
        default=0.01, ge=0.0, description="Minimum concentration threshold in the flow field."
    )
    response_curve: Literal["step", "hill", "logarithmic"] = Field(
        default="step", description="Dose-response curve type: step, hill (sigmoidal kinetics), or logarithmic."
    )
    hill_cooperativity: float = Field(
        default=2.0, gt=0.0, description="Hill cooperativity exponent n controlling dose-response steepness."
    )
    half_saturation: float = Field(
        default=0.05, gt=0.0, description="Semi-saturation constant Kd (concentration where response is 50%)."
    )


TriggerInitiator = Annotated[HerbivoreAttackInitiator | EnvironmentalSignalInitiator, Field(discriminator="type")]


class TriggerConditionSchema(StrictBaseModel):
    """Trigger condition for defense actions (Interaction Matrix entry).

    Maps an initiator (e.g. herbivore presence, environmental signal) to an action
    that should be executed when the trigger conditions are met.
    """

    model_config = ConfigDict(extra="forbid")

    initiator: TriggerInitiator = Field(..., description="The condition that initiates this rule.")
    aftereffect_ticks: int = Field(
        default=0,
        ge=0,
        description="Aftereffect duration T_k (action effect lingers after trigger ceases).",
    )
    activation_condition: ConditionNode | None = Field(
        default=None,
        description=(
            "Optional nested predicate tree controlling whether the configured action may activate. "
            "Supports explicit all_of/any_of composition over herbivore_presence and substance_active leaves."
        ),
    )
    action: TriggerAction = Field(..., description="The action to perform when triggered.")

    @model_validator(mode="before")
    @classmethod
    def _map_legacy_trigger_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Maps legacy `herbivore_species_id` and `min_herbivore_population` to `initiator`."""
        if isinstance(data, dict) and "initiator" not in data:
            if "herbivore_species_id" in data:
                data["initiator"] = {
                    "type": "herbivore_attack",
                    "herbivore_species_id": data.pop("herbivore_species_id"),
                    "min_herbivore_population": data.pop("min_herbivore_population", 5),
                }
        return data


class PassiveDefensesSchema(StrictBaseModel):
    """Morphological (passive) defenses of a flora species."""

    mechanical_damage_per_bite: float = Field(
        default=0.0, ge=0.0, description="[Absolute] Thorns/spines damage per feeding event."
    )
    digestibility_modifier: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="[%] Lignin/silica calorie discount multiplier (e.g. 0.5 = 50% metabolized).",
    )
