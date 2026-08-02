# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Assembler functions for compiling PHIDS triggers, substances, and diet matrices."""

from __future__ import annotations

import json

import polars as pl

_SUBSTANCE_REGISTRY: dict[str, int] = {
    "alpha-pinene": 0,
    "beta-caryophyllene": 1,
    "(Z)-3-hexenyl acetate": 2,
    "methyl salicylate": 3,
    "linalool": 4,
    "indole": 5,
    "(E)-beta-farnesene": 6,
    "taxine": 10,
    "atropine": 11,
    "hyoscine": 12,
    "coniine": 13,
    "colchicine": 14,
    "aconitine": 15,
    "veratrine": 16,
    "protoanemonin": 17,
    "solanine": 18,
    "digitoxin": 19,
    "digoxin": 20,
    "amygdalin": 21,
    "linamarin": 22,
    "dhurrin": 23,
    "tannic acid": 30,
    "gallotannin": 31,
    "ellagitannin": 32,
}

_VOC_IDS: set[int] = {0, 1, 2, 3, 4, 5, 6}


def _append_voc_substance(rows: list[dict[str, object]], row: dict[str, object]) -> None:
    """Append a VOC substance row to the list of rows.

    Args:
        rows: The list of rows to append to.
        row: The row to append.
    """
    compound = str(row["compound_name"])
    sub_id = _SUBSTANCE_REGISTRY.get(compound)
    if sub_id is not None:
        rows.append(
            {
                "substance_id": sub_id,
                "name": compound,
                "compound_class": "voc",
                "is_toxin": False,
                "lethal": False,
                "lethality_rate": 0.0,
                "repellent": True,
                "repellent_walk_ticks": 10,
                "energy_cost_per_tick": 0.1,
                "synthesis_duration": 3,
                "irreversible": False,
                "diffusion_coefficient": float(row.get("diffusion_coefficient", 0.3)),
                "ld50_mg_kg": None,
                "source_db": "Pherobase",
            }
        )


def _append_toxin_substance(rows: list[dict[str, object]], row: dict[str, object], seen: set[str]) -> None:
    """Append a single toxin substance record to the list for synthesis table.

    Args:
        rows: List of substance records to append to.
        row: Single toxin row from ToxValDB / Dr.Duke.
        seen: Set of seen compound names to avoid duplicates.
    """
    from data_pipeline.transform import normalise_lethality_rate

    compound = str(row["compound_name"])
    if compound in seen:
        return
    seen.add(compound)
    sub_id = _SUBSTANCE_REGISTRY.get(compound)
    if sub_id is None:
        return

    ld50 = row.get("ld50_mg_kg")
    lethality = normalise_lethality_rate(float(ld50) if ld50 is not None else None)
    rows.append(
        {
            "substance_id": sub_id,
            "name": compound,
            "compound_class": str(row.get("compound_class", "alkaloid")),
            "is_toxin": True,
            "lethal": lethality > 2.0,
            "lethality_rate": lethality,
            "repellent": lethality <= 2.0,
            "repellent_walk_ticks": 5 if lethality <= 2.0 else 0,
            "energy_cost_per_tick": round(0.3 + lethality * 0.02, 4),
            "synthesis_duration": 5,
            "irreversible": lethality > 5.0,
            "diffusion_coefficient": None,
            "ld50_mg_kg": float(ld50) if ld50 is not None else None,
            "source_db": "DrDuke+ToxValDB",
        }
    )


def _build_substances_df(voc_df: pl.DataFrame, phytochem_df: pl.DataFrame) -> pl.DataFrame:
    """Build the substances DataFrame for DuckDB insertion.

    Args:
        voc_df: Pherobase VOC data.
        phytochem_df: DrDuke + ToxValDB compound data.

    Returns:
        Substances Polars DataFrame matching the DuckDB schema.
    """
    rows: list[dict[str, object]] = []

    # VOC substances
    if "compound_name" in voc_df.columns and "diffusion_coefficient" in voc_df.columns:
        for row in voc_df.to_dicts():
            _append_voc_substance(rows, row)

    # Toxin substances
    if "compound_name" in phytochem_df.columns and "has_compound" in phytochem_df.columns:
        seen: set[str] = set()
        for row in (
            phytochem_df.filter(pl.col("has_compound") & pl.col("compound_class").is_in(["alkaloid", "glycoside"]))
            .unique("compound_name")
            .to_dicts()
        ):
            _append_toxin_substance(rows, row, seen)

    return pl.DataFrame(rows) if rows else pl.DataFrame()


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
            rule_id_counter,
            fid,
            0,
            5,
            15,
            "herbivore_presence",
            cond1,
            "synthesize_substance",
            voc_id,
            False,
            False,
            0.0,
            True,
            10,
            3,
            False,
            0.1,
            None,
            act1,
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
            rule_id_counter,
            fid,
            1,
            15,
            25,
            "all_of",
            cond2,
            "synthesize_substance",
            toxin_id,
            True,
            lethality > 2.0,
            lethality,
            False,
            0,
            5,
            lethality > 5.0,
            0.3,
            None,
            act2,
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
            rule_id_counter,
            fid,
            0,
            10,
            20,
            "herbivore_presence",
            cond,
            "synthesize_substance",
            toxin_id,
            True,
            lethality > 2.0,
            lethality,
            False,
            0,
            5,
            lethality > 5.0,
            0.3,
            None,
            act,
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
            rule_id_counter,
            fid,
            0,
            5,
            15,
            "herbivore_presence",
            cond,
            "synthesize_substance",
            voc_id,
            False,
            False,
            0.0,
            True,
            10,
            3,
            False,
            0.1,
            None,
            act,
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
            rule_id_counter,
            fid,
            0,
            50,
            30,
            "herbivore_presence",
            cond,
            "resource_withdrawal",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0.2,
            act,
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


def _rule_row(
    rule_id: int,
    flora_id: int,
    rule_index: int,
    min_pop: int,
    aftereffect: int,
    cond_kind: str,
    cond_json: dict[str, object],
    act_type: str,
    act_sub_id: int | None,
    act_is_toxin: bool | None,
    act_lethal: bool | None,
    act_lethality: float | None,
    act_repellent: bool | None,
    act_repellent_ticks: int | None,
    act_synthesis_dur: int | None,
    act_irreversible: bool | None,
    act_energy_cost: float | None,
    act_nutrition_factor: float | None,
    act_json: dict[str, object],
) -> dict[str, object]:
    """Build a single trigger rule row dict.

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

    Returns:
        Dict matching the DuckDB trigger_rules schema.
    """
    return {
        "rule_id": rule_id,
        "flora_species_id": flora_id,
        "rule_index": rule_index,
        "min_herbivore_population": min_pop,
        "aftereffect_ticks": aftereffect,
        "condition_kind": cond_kind,
        "condition_json": json.dumps(cond_json),
        "action_type": act_type,
        "action_substance_id": act_sub_id,
        "action_is_toxin": act_is_toxin,
        "action_lethal": act_lethal,
        "action_lethality_rate": act_lethality,
        "action_repellent": act_repellent,
        "action_repellent_walk_ticks": act_repellent_ticks,
        "action_synthesis_duration": act_synthesis_dur,
        "action_irreversible": act_irreversible,
        "action_energy_cost_per_tick": act_energy_cost,
        "action_nutrition_factor": act_nutrition_factor,
        "action_json": json.dumps(act_json),
    }


def _get_documented_targets(herb_name: str, globi_df: pl.DataFrame) -> set[str]:
    """Get documented targets for a herbivore.

    Args:
        herb_name: Herbivore binomial name.
        globi_df: GloBI interaction data.

    Returns:
        Set of documented target flora names.
    """
    documented_targets: set[str] = set()
    if not globi_df.is_empty() and "source_taxon" in globi_df.columns:
        herb_interactions = globi_df.filter((pl.col("source_taxon") == herb_name) & ~pl.col("diet_unresolved"))
        for irow in herb_interactions.to_dicts():
            target = str(irow.get("target_taxon", ""))
            if target:
                documented_targets.add(target.lower())
    return documented_targets


def _append_diet_matrix_rows(
    rows: list[dict[str, object]],
    hid: int,
    flora_name_to_id: dict[str, int],
    documented_targets: set[str],
) -> None:
    """Append diet matrix rows for a single herbivore.

    Args:
        rows: List of diet matrix rows to append to.
        hid: Herbivore species ID.
        flora_name_to_id: Mapping from flora names to IDs.
        documented_targets: Set of documented target flora names.
    """
    for flora_name, fid in flora_name_to_id.items():
        # GLoBI match: fuzzy name overlap
        globi_match = any(flora_name.lower() in t or t in flora_name.lower() for t in documented_targets)
        rows.append(
            {
                "herbivore_species_id": hid,
                "flora_species_id": fid,
                "is_edible": True if not documented_targets else globi_match,
                "globi_documented": globi_match,
            }
        )


def _build_diet_matrix_df(
    herbivore_df: pl.DataFrame,
    flora_df: pl.DataFrame,
    globi_df: pl.DataFrame,
    herbivore_name_col: str = "MSW05_Binomial",
    flora_name_col: str = "species_name",
) -> pl.DataFrame:
    """Build the full diet compatibility matrix as a relational DataFrame.

    Args:
        herbivore_df: Herbivore archetypes with species_id.
        flora_df: Flora archetypes with species_id.
        globi_df: GLoBI interaction DataFrame.
        herbivore_name_col: Column for herbivore species names.
        flora_name_col: Column for flora species names.

    Returns:
        Diet matrix DataFrame matching the DuckDB schema.
    """
    rows: list[dict[str, object]] = []

    flora_name_to_id = {
        str(r[flora_name_col]): int(r["species_id"]) for r in flora_df.to_dicts() if flora_name_col in r
    }
    for herb_row in herbivore_df.to_dicts():
        herb_name = str(herb_row.get(herbivore_name_col, ""))
        hid = int(herb_row["species_id"])

        documented_targets = _get_documented_targets(herb_name, globi_df)
        _append_diet_matrix_rows(rows, hid, flora_name_to_id, documented_targets)

    return pl.DataFrame(rows) if rows else pl.DataFrame()
