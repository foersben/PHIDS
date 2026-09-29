"""Trigger rules compilation logic."""

from __future__ import annotations

import json
from dataclasses import dataclass

import polars as pl

from data_pipeline.compile.registry import _SUBSTANCE_REGISTRY


@dataclass(slots=True, frozen=True)
class TriggerRuleConfig:
    """Configuration object for a single trigger rule row.

    Args:
        rule_id: Unique rule identifier.
        flora_id: FK to flora_species.species_id.
        rule_index: Position within species (0-based).
        min_pop: Minimum herbivore population threshold.
        aftereffect: Number of ticks the rule stays active after trigger.
        cond_kind: Condition discriminant string.
        cond_json: Full condition payload dict.
        act_type: Action type discriminant string.
        act_sub_id: FK to substances.substance_id (or None).
        act_is_toxin: Whether the action substance is a toxin.
        act_lethal: Whether the substance is lethal.
        act_lethality: Lethality rate float.
        act_repellent: Whether the substance is a repellent.
        act_repellent_ticks: Repellent duration in ticks.
        act_synthesis_dur: Synthesis duration in ticks.
        act_irreversible: Whether the effect is permanent.
        act_energy_cost: Energy cost per tick.
        act_nutrition_factor: Apparent nutrition factor (resource_withdrawal).
        act_json: Full action payload dict.
        act_withdrawal_duration: Withdrawal duration in ticks (resource_withdrawal).
    """

    rule_id: int
    flora_id: int
    rule_index: int
    min_pop: int
    aftereffect: int
    cond_kind: str
    cond_json: dict[str, object]
    act_type: str
    act_sub_id: int | None
    act_is_toxin: bool | None
    act_lethal: bool | None
    act_lethality: float | None
    act_repellent: bool | None
    act_repellent_ticks: int | None
    act_synthesis_dur: int | None
    act_irreversible: bool | None
    act_energy_cost: float | None
    act_nutrition_factor: float | None
    act_json: dict[str, object]
    act_withdrawal_duration: int | None


def _append_toxin_voc_stage1(
    rows: list[dict[str, object]],
    rule_id_counter: int,
    fid: int,
    voc_id: int,
) -> int:
    """Append stage 1 toxin/VOC rule to rules table.

    Args:
        rows: List of rule records to append to.
        rule_id_counter: Current rule ID counter (will be incremented).
        fid: Flora ID for this rule.
        voc_id: VOC substance ID for this rule.

    Returns:
        Next rule ID counter value.
    """
    cond1 = {"kind": "herbivore_presence", "min_herbivore_population": 5}
    act1 = {
        "type": "synthesize_substance",
        "substance_id": voc_id,
        "synthesis_duration": 3,
        "is_toxin": False,
        "lethal": False,
        "lethality_rate": 0.0,
        "repellent": True,
        "repellent_walk_ticks": 10,
        "energy_cost_per_tick": 0.1,
        "irreversible": False,
    }
    rows.append(
        _rule_row(
            TriggerRuleConfig(
                rule_id=rule_id_counter,
                flora_id=fid,
                rule_index=0,
                min_pop=5,
                aftereffect=15,
                cond_kind="herbivore_presence",
                cond_json=cond1,
                act_type="synthesize_substance",
                act_sub_id=voc_id,
                act_is_toxin=False,
                act_lethal=False,
                act_lethality=0.0,
                act_repellent=True,
                act_repellent_ticks=10,
                act_synthesis_dur=3,
                act_irreversible=False,
                act_energy_cost=0.1,
                act_nutrition_factor=None,
                act_json=act1,
                act_withdrawal_duration=None,
            )
        )
    )
    return rule_id_counter + 1


def _append_toxin_voc_stage2(
    rows: list[dict[str, object]], rule_id_counter: int, fid: int, voc_id: int, toxin_id: int, lethality: float
) -> int:
    """Append stage 2 toxin/VOC rule to rules table.

    Args:
        rows: List of rule records to append to.
        rule_id_counter: Current rule ID counter (will be incremented).
        fid: Flora ID for this rule.
        voc_id: VOC substance ID for this rule.
        toxin_id: Toxin substance ID for this rule.
        lethality: Lethality rate for the toxin.

    Returns:
        Next rule ID counter value.
    """
    cond2 = {
        "kind": "all_of",
        "conditions": [
            {"kind": "herbivore_presence", "min_herbivore_population": 15},
            {"kind": "substance_active", "substance_id": voc_id},
        ],
    }
    act2 = {
        "type": "synthesize_substance",
        "substance_id": toxin_id,
        "synthesis_duration": 5,
        "is_toxin": True,
        "lethal": lethality > 2.0,
        "lethality_rate": lethality,
        "repellent": False,
        "repellent_walk_ticks": 0,
        "energy_cost_per_tick": 0.3,
        "irreversible": lethality > 5.0,
    }
    rows.append(
        _rule_row(
            TriggerRuleConfig(
                rule_id=rule_id_counter,
                flora_id=fid,
                rule_index=1,
                min_pop=15,
                aftereffect=25,
                cond_kind="all_of",
                cond_json=cond2,
                act_type="synthesize_substance",
                act_sub_id=toxin_id,
                act_is_toxin=True,
                act_lethal=lethality > 2.0,
                act_lethality=lethality,
                act_repellent=False,
                act_repellent_ticks=0,
                act_synthesis_dur=5,
                act_irreversible=lethality > 5.0,
                act_energy_cost=0.3,
                act_nutrition_factor=None,
                act_json=act2,
                act_withdrawal_duration=None,
            )
        )
    )
    return rule_id_counter + 1


def _append_toxin_only(
    rows: list[dict[str, object]], rule_id_counter: int, fid: int, toxin_id: int, lethality: float
) -> int:
    """Append toxin-only rule to rules table.

    Args:
        rows: List of rule records to append to.
        rule_id_counter: Current rule ID counter (will be incremented).
        fid: Flora ID for this rule.
        toxin_id: Toxin substance ID for this rule.
        lethality: Lethality rate for the toxin.

    Returns:
        Next rule ID counter value.
    """
    cond = {"kind": "herbivore_presence", "min_herbivore_population": 10}
    act = {
        "type": "synthesize_substance",
        "substance_id": toxin_id,
        "synthesis_duration": 5,
        "is_toxin": True,
        "lethal": lethality > 2.0,
        "lethality_rate": lethality,
        "repellent": False,
        "repellent_walk_ticks": 0,
        "energy_cost_per_tick": 0.3,
        "irreversible": lethality > 5.0,
    }
    rows.append(
        _rule_row(
            TriggerRuleConfig(
                rule_id=rule_id_counter,
                flora_id=fid,
                rule_index=0,
                min_pop=10,
                aftereffect=20,
                cond_kind="herbivore_presence",
                cond_json=cond,
                act_type="synthesize_substance",
                act_sub_id=toxin_id,
                act_is_toxin=True,
                act_lethal=lethality > 2.0,
                act_lethality=lethality,
                act_repellent=False,
                act_repellent_ticks=0,
                act_synthesis_dur=5,
                act_irreversible=lethality > 5.0,
                act_energy_cost=0.3,
                act_nutrition_factor=None,
                act_json=act,
                act_withdrawal_duration=None,
            )
        )
    )
    return rule_id_counter + 1


def _append_voc_only(rows: list[dict[str, object]], rule_id_counter: int, fid: int, voc_id: int) -> int:
    """Append VOC-only rule to rules table.

    Args:
        rows: List of rule records to append to.
        rule_id_counter: Current rule ID counter (will be incremented).
        fid: Flora ID for this rule.
        voc_id: VOC substance ID for this rule.

    Returns:
        Next rule ID counter value.
    """
    cond = {"kind": "herbivore_presence", "min_herbivore_population": 5}
    act = {
        "type": "synthesize_substance",
        "substance_id": voc_id,
        "synthesis_duration": 3,
        "is_toxin": False,
        "lethal": False,
        "lethality_rate": 0.0,
        "repellent": True,
        "repellent_walk_ticks": 10,
        "energy_cost_per_tick": 0.1,
        "irreversible": False,
    }
    rows.append(
        _rule_row(
            TriggerRuleConfig(
                rule_id=rule_id_counter,
                flora_id=fid,
                rule_index=0,
                min_pop=5,
                aftereffect=15,
                cond_kind="herbivore_presence",
                cond_json=cond,
                act_type="synthesize_substance",
                act_sub_id=voc_id,
                act_is_toxin=False,
                act_lethal=False,
                act_lethality=0.0,
                act_repellent=True,
                act_repellent_ticks=10,
                act_synthesis_dur=3,
                act_irreversible=False,
                act_energy_cost=0.1,
                act_nutrition_factor=None,
                act_json=act,
                act_withdrawal_duration=None,
            )
        )
    )
    return rule_id_counter + 1


def _get_species_toxins_and_vocs(
    species: str, phytochem_df: pl.DataFrame, voc_df: pl.DataFrame
) -> tuple[list[dict[str, object]], list[str]]:
    """Get toxins and VOCs for a single species.

    Args:
        species: Species binomial name.
        phytochem_df: Dr.Duke + ToxValDB compound data.
        voc_df: Pherobase VOC data.

    Returns:
        Tuple of (species_toxins, species_vocs).
    """
    species_toxins: list[dict[str, object]] = []
    if "species_name" in phytochem_df.columns:
        species_toxins = phytochem_df.filter(
            (pl.col("species_name") == species)
            & pl.col("has_compound")
            & pl.col("compound_class").is_in(["alkaloid", "glycoside"])
        ).to_dicts()

    species_vocs: list[str] = []
    if "plant_associations" in voc_df.columns:
        for voc_row in voc_df.to_dicts():
            if species in str(voc_row.get("plant_associations", "")).split("|"):
                species_vocs.append(str(voc_row["compound_name"]))

    return species_toxins, species_vocs


def _append_resource_withdrawal(rows: list[dict[str, object]], rule_id_counter: int, fid: int) -> int:
    """Append resource withdrawal rule to rules table.

    Args:
        rows: List of rule records to append to.
        rule_id_counter: Current rule ID counter (will be incremented).
        fid: Flora ID for this rule.

    Returns:
        Next rule ID counter value.
    """
    cond = {"kind": "herbivore_presence", "min_herbivore_population": 50}
    act = {"type": "resource_withdrawal", "apparent_nutrition_factor": 0.2}
    rows.append(
        _rule_row(
            TriggerRuleConfig(
                rule_id=rule_id_counter,
                flora_id=fid,
                rule_index=0,
                min_pop=50,
                aftereffect=30,
                cond_kind="herbivore_presence",
                cond_json=cond,
                act_type="resource_withdrawal",
                act_sub_id=None,
                act_is_toxin=None,
                act_lethal=None,
                act_lethality=None,
                act_repellent=None,
                act_repellent_ticks=None,
                act_synthesis_dur=None,
                act_irreversible=None,
                act_energy_cost=None,
                act_nutrition_factor=0.2,
                act_json=act,
                act_withdrawal_duration=10,
            )
        )
    )
    return rule_id_counter + 1


def _build_trigger_rules_df(
    flora_df: pl.DataFrame,
    phytochem_df: pl.DataFrame,
    voc_df: pl.DataFrame,
    species_name_col: str = "species_name",
) -> pl.DataFrame:
    """Build a flat trigger rules DataFrame for DuckDB insertion.

    Args:
        flora_df: Flora archetypes with species_id column.
        phytochem_df: Phytochemical data.
        voc_df: VOC data.
        species_name_col: Column containing species names.

    Returns:
        Trigger rules DataFrame matching the DuckDB schema.
    """
    from data_pipeline.transform import normalise_lethality_rate

    rows: list[dict[str, object]] = []
    rule_id_counter = 0

    for flora_row in flora_df.to_dicts():
        species = str(flora_row.get(species_name_col, "Unknown"))
        fid = int(flora_row["species_id"])

        species_toxins, species_vocs = _get_species_toxins_and_vocs(species, phytochem_df, voc_df)

        has_toxin = len(species_toxins) > 0
        has_voc = len(species_vocs) > 0

        if has_toxin and has_voc:
            voc_name = species_vocs[0]
            voc_id = _SUBSTANCE_REGISTRY.get(voc_name, 0)
            toxin_compound = str(species_toxins[0]["compound_name"])
            toxin_id = _SUBSTANCE_REGISTRY.get(toxin_compound, 10)
            ld50 = species_toxins[0].get("ld50_mg_kg")
            lethality = normalise_lethality_rate(float(ld50) if ld50 is not None else None)

            rule_id_counter = _append_toxin_voc_stage1(rows, rule_id_counter, fid, voc_id)
            rule_id_counter = _append_toxin_voc_stage2(rows, rule_id_counter, fid, voc_id, toxin_id, lethality)

        elif has_toxin:
            toxin_compound = str(species_toxins[0]["compound_name"])
            toxin_id = _SUBSTANCE_REGISTRY.get(toxin_compound, 10)
            ld50 = species_toxins[0].get("ld50_mg_kg")
            lethality = normalise_lethality_rate(float(ld50) if ld50 is not None else None)

            rule_id_counter = _append_toxin_only(rows, rule_id_counter, fid, toxin_id, lethality)

        elif has_voc:
            voc_name = species_vocs[0]
            voc_id = _SUBSTANCE_REGISTRY.get(voc_name, 0)
            rule_id_counter = _append_voc_only(rows, rule_id_counter, fid, voc_id)

        else:
            rule_id_counter = _append_resource_withdrawal(rows, rule_id_counter, fid)

    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _rule_row(config: TriggerRuleConfig) -> dict[str, object]:
    """Build a single trigger rule row dict from a configuration object.

    Args:
        config: Configuration object containing all fields.

    Returns:
        Dict matching the DuckDB trigger_rules schema.
    """
    return {
        "rule_id": config.rule_id,
        "flora_species_id": config.flora_id,
        "rule_index": config.rule_index,
        "min_herbivore_population": config.min_pop,
        "aftereffect_ticks": config.aftereffect,
        "condition_kind": config.cond_kind,
        "condition_json": json.dumps(config.cond_json),
        "action_type": config.act_type,
        "action_substance_id": config.act_sub_id,
        "action_is_toxin": config.act_is_toxin,
        "action_lethal": config.act_lethal,
        "action_lethality_rate": config.act_lethality,
        "action_repellent": config.act_repellent,
        "action_repellent_walk_ticks": config.act_repellent_ticks,
        "action_synthesis_duration": config.act_synthesis_dur,
        "action_irreversible": config.act_irreversible,
        "action_energy_cost_per_tick": config.act_energy_cost,
        "action_nutrition_factor": config.act_nutrition_factor,
        "action_withdrawal_duration": config.act_withdrawal_duration,
        "action_json": json.dumps(config.act_json),
    }
