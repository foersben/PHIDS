# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""PHIDS Empirical Database ETL Pipeline Orchestrator.

Executes all pipeline phases in sequence, writing all outputs to a DuckDB
database and generating a JSON export for engine compatibility.

Usage
-----
    uv run --group pipeline python src/data_pipeline/run_all.py

Or via just:
    just etl
    just etl-refresh   # force-refresh all API caches

Pipeline phases
---------------
Phase 1 - Ingest:    Fetch from TRY, GLoBI, PanTHERIA, DrDuke, Pherobase.
                     Results cached as Parquet in src/data_pipeline/cache/.
Phase 2 - Align:     GBIF synonym resolution and cross-source merge.
Phase 3 - Impute:    Phylogenetically-grouped KNN imputation.
Phase 4 - Normalise: Min-Max / log-scale transforms → engine float bounds.
Phase 5 - Cluster:   K-Means archetype extraction (Rule of 16).
Phase 6 - Compile:   Trigger synthesis, substance registry, diet matrix.
Phase 7 - Persist:   Write all tables to DuckDB (bio_database.duckdb).
Phase 8 - Export:    Generate bio_database.json from DuckDB.
Phase 9 - Publish:   Optional Hugging Face Hub upload (CI mode).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Ensure src/ is on the import path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl

from data_pipeline.archetype_extractor import extract_flora_archetypes, extract_herbivore_archetypes
from data_pipeline.cleaning.gbif_resolver import build_synonym_map, resolve_gbif_synonyms
from data_pipeline.cleaning.knn_imputer import impute_missing_traits
from data_pipeline.db import (
    BioQuery,
    export_bio_database_json,
    publish_to_huggingface,
    write_all,
)
from data_pipeline.db.export import export_manifest_json
from data_pipeline.ingest.drduke_client import fetch_drduke
from data_pipeline.ingest.globi_client import HERBIVORE_CANDIDATES, fetch_globi
from data_pipeline.ingest.pantheria_client import fetch_pantheria
from data_pipeline.ingest.pherobase_client import fetch_pherobase
from data_pipeline.ingest.try_client import TARGET_SPECIES, fetch_try
from data_pipeline.provenance import CITATIONS, ProvenanceLedger, ProvenanceRecord, today_iso
from data_pipeline.transform import normalise_flora_dataframe, normalise_herbivore_dataframe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("phids.etl")

# ---------------------------------------------------------------------------
# Substance registry (stable IDs across pipeline runs)
# ---------------------------------------------------------------------------

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


def run_all(
    force_refresh: bool = False,
    publish: bool = False,
    hf_repo: str = "foersben/PHIDS-empirical-database",
) -> None:
    """Execute the full PHIDS empirical database ETL pipeline.

    Args:
        force_refresh: Re-fetch and re-process all data sources even if caches exist.
        publish: Upload compiled database to Hugging Face Hub after compilation.
        hf_repo: Hugging Face repository ID for publishing.

    """
    t_start = time.perf_counter()
    ledger = ProvenanceLedger()

    # -------------------------------------------------------------------------
    # Phase 1: Ingest
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 1: Source Ingestion")
    logger.info("=" * 60)

    pantheria_df = fetch_pantheria(force_refresh=force_refresh)
    logger.info("P1.1 PanTHERIA (CC0): %d species rows", len(pantheria_df))

    try_df = fetch_try(force_refresh=force_refresh)
    n_try_species = try_df["species_name"].n_unique() if "species_name" in try_df.columns else 0
    logger.info("P1.2 TRY (CC-BY 4.0): %d trait records, %d species", len(try_df), n_try_species)

    globi_df = fetch_globi(force_refresh=force_refresh)
    logger.info("P1.3 GLoBI (CC-BY 4.0): %d interaction records", len(globi_df))

    phytochem_df = fetch_drduke(force_refresh=force_refresh)
    logger.info("P1.4 DrDuke + ToxValDB (CC0): %d compound records", len(phytochem_df))

    voc_df = fetch_pherobase(force_refresh=force_refresh)
    logger.info("P1.5 Pherobase (academic use): %d VOC records", len(voc_df))

    # -------------------------------------------------------------------------
    # Phase 2: Taxonomic Alignment
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 2: GBIF Synonym Resolution")
    logger.info("=" * 60)

    all_species = list(set(TARGET_SPECIES + HERBIVORE_CANDIDATES))
    gbif_df = resolve_gbif_synonyms(all_species, force_refresh=force_refresh)
    synonym_map = build_synonym_map(gbif_df)
    resolved_count = int(gbif_df.filter(pl.col("resolved"))["resolved"].sum())
    logger.info("P2.1 GBIF (CC0): %d / %d names resolved", resolved_count, len(all_species))

    # -------------------------------------------------------------------------
    # Phase 3: Merge + Impute
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 3: Data Merging & KNN Imputation")
    logger.info("=" * 60)

    flora_merged = _pivot_try_data(try_df, gbif_df, synonym_map)
    logger.info("P3.1 Flora merged: %d species, %d columns", len(flora_merged), len(flora_merged.columns))

    flora_numeric_cols = ["sla_cm2_per_g", "seed_dry_mass_g", "height_cm", "leaf_tensile_n_mm2", "lignin_pct"]
    flora_imputed = impute_missing_traits(
        flora_merged, numeric_cols=flora_numeric_cols, family_col="family", order_col="order_name"
    )

    pantheria_with_gbif = _join_pantheria_gbif(pantheria_df, gbif_df)
    herbivore_numeric_cols = [
        "5-1_AdultBodyMass_g",
        "18-1_BasalMetRate_mLO2hr",
        "25-1_WeaningAge_d",
        "10-1_PopulationGrpSize",
    ]
    herbivore_imputed = impute_missing_traits(
        pantheria_with_gbif, numeric_cols=herbivore_numeric_cols, family_col="family", order_col="order_name"
    )
    logger.info("P3.2 Imputation complete")

    # -------------------------------------------------------------------------
    # Phase 4: Normalise
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 4: Normalisation → Engine Bounds")
    logger.info("=" * 60)

    flora_normalised = normalise_flora_dataframe(flora_imputed)
    herbivore_normalised = normalise_herbivore_dataframe(herbivore_imputed)

    if "growth_rate" in flora_normalised.columns:
        gr_min = flora_normalised["growth_rate"].min()
        gr_max = flora_normalised["growth_rate"].max()
        logger.info("P4.1 growth_rate range: [%.4f, %.4f]", gr_min, gr_max)

    # -------------------------------------------------------------------------
    # Phase 5: Archetype Extraction
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 5: K-Means Archetypes (Rule of 16)")
    logger.info("=" * 60)

    flora_archetypes = extract_flora_archetypes(
        flora_normalised,
        species_name_col="species_name",
        force_refresh=force_refresh,
    )
    herbivore_archetypes = extract_herbivore_archetypes(
        herbivore_normalised,
        species_name_col="MSW05_Binomial",
        force_refresh=force_refresh,
    )
    logger.info(
        "P5.1 Flora archetypes: %d | Herbivore archetypes: %d", len(flora_archetypes), len(herbivore_archetypes)
    )

    # -------------------------------------------------------------------------
    # Phase 6: Compile substances, trigger rules, diet matrix
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 6: Trigger Compilation & Relational Assembly")
    logger.info("=" * 60)

    substances_df = _build_substances_df(voc_df, phytochem_df)
    logger.info("P6.1 Substances: %d rows", len(substances_df))

    # Assign stable integer species_ids
    flora_with_id = flora_archetypes.with_row_index("species_id")
    herbivore_with_id = herbivore_archetypes.with_row_index("species_id")

    trigger_rules_df = _build_trigger_rules_df(
        flora_with_id,
        phytochem_df,
        voc_df,
        species_name_col="species_name",
    )
    logger.info("P6.2 Trigger rules: %d rows", len(trigger_rules_df))

    diet_matrix_df = _build_diet_matrix_df(
        herbivore_with_id,
        flora_with_id,
        globi_df,
        herbivore_name_col="MSW05_Binomial",
        flora_name_col="species_name",
    )
    logger.info("P6.3 Diet matrix: %d edges", len(diet_matrix_df))

    # Add provenance entries for archetypes
    _record_archetype_provenance(ledger, flora_with_id, herbivore_with_id)

    # -------------------------------------------------------------------------
    # Phase 7: Write to DuckDB
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 7: Persist to DuckDB")
    logger.info("=" * 60)

    conn = write_all(
        flora_archetypes=flora_with_id,
        herbivore_archetypes=herbivore_with_id,
        substances_df=substances_df,
        trigger_rules_df=trigger_rules_df,
        diet_matrix_df=diet_matrix_df,
        provenance_df=ledger.to_dataframe(),
        overwrite=True,
    )

    summary = BioQuery.summary(conn)
    logger.info("P7.1 DuckDB row counts: %s", summary)

    # -------------------------------------------------------------------------
    # Phase 8: Export JSON (engine compatibility)
    # -------------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("PHASE 8: JSON Export & Manifest")
    logger.info("=" * 60)

    json_path = export_bio_database_json(conn=conn)
    manifest_path = export_manifest_json(conn=conn)
    conn.close()

    logger.info("P8.1 bio_database.json: %d bytes", json_path.stat().st_size)
    logger.info("P8.2 manifest.json:     %d bytes", manifest_path.stat().st_size)

    # -------------------------------------------------------------------------
    # Phase 9: Optional Hugging Face Publish
    # -------------------------------------------------------------------------
    if publish:
        logger.info("=" * 60)
        logger.info("PHASE 9: Hugging Face Hub → foersben/PHIDS-empirical-database")
        logger.info("=" * 60)
        hf_token = os.environ.get("HF_TOKEN")
        publish_to_huggingface(repo_id=hf_repo, hf_token=hf_token)

    elapsed = time.perf_counter() - t_start
    logger.info("=" * 60)
    logger.info("ETL PIPELINE COMPLETE in %.1fs", elapsed)
    for table, count in summary.items():
        logger.info("  %-30s %d rows", table + ":", count)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Phase 6 assemblers
# ---------------------------------------------------------------------------


def _build_substances_df(voc_df: pl.DataFrame, phytochem_df: pl.DataFrame) -> pl.DataFrame:
    """Build the substances DataFrame for DuckDB insertion.

    Args:
        voc_df: Pherobase VOC data.
        phytochem_df: DrDuke + ToxValDB compound data.

    Returns:
        Substances Polars DataFrame matching the DuckDB schema.

    """
    from data_pipeline.transform import normalise_lethality_rate

    rows: list[dict[str, object]] = []

    # VOC substances
    if "compound_name" in voc_df.columns and "diffusion_coefficient" in voc_df.columns:
        for row in voc_df.to_dicts():
            compound = str(row["compound_name"])
            sub_id = _SUBSTANCE_REGISTRY.get(compound)
            if sub_id is None:
                continue
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

    # Toxin substances
    if "compound_name" in phytochem_df.columns and "has_compound" in phytochem_df.columns:
        seen: set[str] = set()
        for row in (
            phytochem_df.filter(pl.col("has_compound") & pl.col("compound_class").is_in(["alkaloid", "glycoside"]))
            .unique("compound_name")
            .to_dicts()
        ):
            compound = str(row["compound_name"])
            if compound in seen:
                continue
            seen.add(compound)
            sub_id = _SUBSTANCE_REGISTRY.get(compound)
            if sub_id is None:
                continue
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

    return pl.DataFrame(rows) if rows else pl.DataFrame()


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

        # Determine toxin and VOC presence for this species
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

        has_toxin = len(species_toxins) > 0
        has_voc = len(species_vocs) > 0

        if has_toxin and has_voc:
            voc_name = species_vocs[0]
            voc_id = _SUBSTANCE_REGISTRY.get(voc_name, 0)
            toxin_compound = str(species_toxins[0]["compound_name"])
            toxin_id = _SUBSTANCE_REGISTRY.get(toxin_compound, 10)
            ld50 = species_toxins[0].get("ld50_mg_kg")
            lethality = normalise_lethality_rate(float(ld50) if ld50 is not None else None)

            # Stage 1: presence → VOC
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
            rule_id_counter += 1

            # Stage 2: presence + VOC active → toxin
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
            rule_id_counter += 1

        elif has_toxin:
            toxin_compound = str(species_toxins[0]["compound_name"])
            toxin_id = _SUBSTANCE_REGISTRY.get(toxin_compound, 10)
            ld50 = species_toxins[0].get("ld50_mg_kg")
            lethality = normalise_lethality_rate(float(ld50) if ld50 is not None else None)
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
            rule_id_counter += 1

        elif has_voc:
            voc_name = species_vocs[0]
            voc_id = _SUBSTANCE_REGISTRY.get(voc_name, 0)
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
                    10,
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
            rule_id_counter += 1

        else:
            # Resource withdrawal for chemically undocumented species
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
            rule_id_counter += 1

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

        # Resolve GLoBI documented interactions
        documented_targets: set[str] = set()
        if not globi_df.is_empty() and "source_taxon" in globi_df.columns:
            herb_interactions = globi_df.filter((pl.col("source_taxon") == herb_name) & ~pl.col("diet_unresolved"))
            for irow in herb_interactions.to_dicts():
                target = str(irow.get("target_taxon", ""))
                if target:
                    documented_targets.add(target.lower())

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

    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _record_archetype_provenance(
    ledger: ProvenanceLedger,
    flora_df: pl.DataFrame,
    herbivore_df: pl.DataFrame,
) -> None:
    """Add provenance records for all compiled archetypes.

    Args:
        ledger: ProvenanceLedger to append to.
        flora_df: Flora archetypes DataFrame.
        herbivore_df: Herbivore archetypes DataFrame.

    """
    date = today_iso()
    for row in flora_df.to_dicts():
        ledger.add(
            ProvenanceRecord(
                species_canonical=str(row.get("species_name", "unknown")),
                source_db="TRY+DrDuke+Pherobase",
                source_license="CC-BY 4.0 (TRY); CC0 (DrDuke); Academic (Pherobase)",
                source_doi=CITATIONS["TRY"]["doi"],
                source_citation=CITATIONS["TRY"]["citation"],
                access_date=date,
                raw_trait_key="archetype_k_means",
                raw_trait_value=None,
                derived_param="growth_rate",
                derived_value=float(row.get("growth_rate", 0.0)),
            )
        )
    for row in herbivore_df.to_dicts():
        ledger.add(
            ProvenanceRecord(
                species_canonical=str(row.get("MSW05_Binomial", "unknown")),
                source_db="PanTHERIA+GLoBI",
                source_license="CC0 (PanTHERIA); CC-BY 4.0 (GLoBI)",
                source_doi=CITATIONS["PanTHERIA"]["doi"],
                source_citation=CITATIONS["PanTHERIA"]["citation"],
                access_date=date,
                raw_trait_key="archetype_k_means",
                raw_trait_value=None,
                derived_param="metabolism_upkeep",
                derived_value=float(row.get("metabolism_upkeep", 0.0)),
            )
        )


# ---------------------------------------------------------------------------
# Merge helpers (unchanged from previous version)
# ---------------------------------------------------------------------------


def _pivot_try_data(
    try_df: pl.DataFrame,
    gbif_df: pl.DataFrame,
    synonym_map: dict[str, str],
) -> pl.DataFrame:
    """Pivot TRY long-format to wide per-species and join GBIF taxonomy.

    Args:
        try_df: Long-format TRY DataFrame.
        gbif_df: GBIF resolution DataFrame.
        synonym_map: Raw-to-canonical name map.

    Returns:
        Wide-format flora DataFrame.

    """
    if try_df.is_empty() or "trait_id" not in try_df.columns:
        return _fallback_flora_frame()

    trait_id_to_col: dict[int, str] = {
        3117: "sla_cm2_per_g",
        26: "seed_dry_mass_g",
        3106: "height_cm",
        163: "leaf_tensile_n_mm2",
        146: "lignin_pct",
        55: "leaf_dry_mass_g",
    }

    agg = try_df.group_by(["species_name", "trait_id"]).agg(pl.col("std_value").median().alias("median_value"))

    species_list = agg["species_name"].unique().to_list()
    rows: list[dict[str, object]] = []
    for species in species_list:
        canonical = synonym_map.get(species, species)
        row: dict[str, object] = {"species_name": canonical, "raw_species_name": species}
        for trait_row in agg.filter(pl.col("species_name") == species).to_dicts():
            col_name = trait_id_to_col.get(int(trait_row["trait_id"]))
            if col_name:
                row[col_name] = trait_row["median_value"]
        rows.append(row)

    flora_wide = pl.DataFrame(rows)

    gbif_select = gbif_df.select(
        pl.col("canonical_name").alias("species_name"),
        "family",
        "order_name",
        "class_name",
        "phylum",
    ).unique("species_name")

    return flora_wide.join(gbif_select, on="species_name", how="left")


def _fallback_flora_frame() -> pl.DataFrame:
    """Return a minimal flora frame with null traits when TRY is unavailable.

    Returns:
        Flora DataFrame with null trait columns for KNN imputation to fill.

    """
    n = len(TARGET_SPECIES)
    return pl.DataFrame(
        {
            "species_name": TARGET_SPECIES,
            "sla_cm2_per_g": [None] * n,
            "seed_dry_mass_g": [None] * n,
            "height_cm": [None] * n,
            "leaf_tensile_n_mm2": [None] * n,
            "lignin_pct": [None] * n,
            "family": [None] * n,
            "order_name": [None] * n,
        }
    )


def _join_pantheria_gbif(
    pantheria_df: pl.DataFrame,
    gbif_df: pl.DataFrame,
) -> pl.DataFrame:
    """Join GBIF taxonomy onto PanTHERIA by binomial name.

    Args:
        pantheria_df: Raw PanTHERIA DataFrame.
        gbif_df: GBIF resolution DataFrame.

    Returns:
        PanTHERIA with taxonomy columns appended.

    """
    if "MSW05_Binomial" not in pantheria_df.columns:
        return pantheria_df

    gbif_select = gbif_df.select(
        pl.col("raw_name").alias("MSW05_Binomial"),
        "family",
        "order_name",
        "class_name",
    ).unique("MSW05_Binomial")

    return pantheria_df.join(gbif_select, on="MSW05_Binomial", how="left")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PHIDS Empirical Database ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-fetch all sources ignoring Parquet caches",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Upload to foersben/PHIDS-empirical-database on Hugging Face Hub",
    )
    parser.add_argument(
        "--hf-repo",
        type=str,
        default="foersben/PHIDS-empirical-database",
        help="Hugging Face repository ID",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_all(force_refresh=args.force_refresh, publish=args.publish, hf_repo=args.hf_repo)
