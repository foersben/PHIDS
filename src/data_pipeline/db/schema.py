# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""DuckDB schema: DDL definitions and connection management.

The database lives at a single file path and is accessed exclusively through
this module's ``open_connection`` factory.  All DDL is idempotent
(``CREATE TABLE IF NOT EXISTS``) so the schema can be safely re-applied on
every pipeline run without data loss.

Design principles
-----------------
- Every scalar parameter is a proper typed column (not JSON) for columnar
  pushdown and predicate filtering without deserialisation.
- Nested structures (trigger rule condition trees, action payloads) are stored
  as ``JSON`` columns alongside their key discriminant scalars.  This allows
  fast indexed queries on the discriminant (e.g. ``WHERE action_type = ...``)
  while preserving full fidelity of the nested payload for export.
- The diet matrix is a normalised relational table with FK constraints and an
  explicit ``globi_documented`` flag distinguishing empirical from imputed edges.
- The provenance table replaces the flat ``manifest.json``: it is queryable,
  groupable by source/license, and filterable by date for incremental audits.
- ``CHECK`` constraints enforce the 1e-4 subnormal floor at the database layer
  as a second line of defence after the transform step.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

# Primary database location.  The JSON export is a derived artifact alongside it.
DB_PATH = Path(__file__).parent.parent.parent / "phids" / "analytics" / "bio_database.duckdb"

# DDL: executed in dependency order (referenced tables first)
_DDL_STATEMENTS: list[str] = [
    # ------------------------------------------------------------------
    # 1. Flora scalar parameters
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS flora_species (
        species_id                 INTEGER PRIMARY KEY,
        canonical_name             VARCHAR  NOT NULL UNIQUE,
        growth_rate                FLOAT    NOT NULL CHECK (growth_rate >= 1e-4),
        max_energy                 FLOAT    NOT NULL CHECK (max_energy >= 5.0),
        survival_threshold         FLOAT    NOT NULL CHECK (survival_threshold >= 0.5),
        seed_cost                  FLOAT    NOT NULL CHECK (seed_cost >= 0.5),
        seed_dispersion_radius     FLOAT    NOT NULL CHECK (seed_dispersion_radius >= 1.0),
        mechanical_damage_per_bite FLOAT    NOT NULL CHECK (mechanical_damage_per_bite >= 0.0),
        digestibility_modifier     FLOAT    NOT NULL CHECK (digestibility_modifier BETWEEN 0.5 AND 1.0),
        -- Taxonomy (GBIF-resolved)
        family                     VARCHAR,
        order_name                 VARCHAR,
        class_name                 VARCHAR,
        phylum                     VARCHAR,
        -- Archetype clustering metadata
        cluster_id                 INTEGER,
        centroid_distance          FLOAT,
        knn_influences             VARCHAR,  -- JSON string of species that influenced imputation
        source_databases           VARCHAR   -- comma-separated: 'TRY,DrDuke'
    )
    """,
    # ------------------------------------------------------------------
    # 2. Herbivore scalar parameters
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS herbivore_species (
        species_id                  INTEGER PRIMARY KEY,
        canonical_name              VARCHAR  NOT NULL UNIQUE,
        metabolism_upkeep           FLOAT    NOT NULL CHECK (metabolism_upkeep >= 1e-4),
        consumption_rate            FLOAT    NOT NULL CHECK (consumption_rate >= 0.5),
        mitosis_threshold           FLOAT    NOT NULL CHECK (mitosis_threshold >= 10.0),
        split_ratio                 FLOAT    NOT NULL DEFAULT 0.5,
        reproduction_energy_divisor FLOAT    CHECK (reproduction_energy_divisor >= 2.0),
        split_population_threshold  FLOAT,
        -- Passive resistances
        morphological_adaptation    FLOAT    NOT NULL DEFAULT 0.1,
        chemical_neutralization     FLOAT    NOT NULL DEFAULT 0.1,
        digestive_efficiency        FLOAT    NOT NULL DEFAULT 1.0,
        -- Taxonomy
        family                      VARCHAR,
        order_name                  VARCHAR,
        class_name                  VARCHAR,
        -- Archetype metadata
        cluster_id                  INTEGER,
        centroid_distance           FLOAT,
        source_databases            VARCHAR
    )
    """,
    # ------------------------------------------------------------------
    # 3. Substances (signals, toxins, repellents)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS substances (
        substance_id          INTEGER PRIMARY KEY,
        name                  VARCHAR  NOT NULL UNIQUE,
        compound_class        VARCHAR  NOT NULL,  -- 'alkaloid','glycoside','tannin','voc'
        is_toxin              BOOLEAN  NOT NULL,
        lethal                BOOLEAN  NOT NULL,
        lethality_rate        FLOAT    NOT NULL CHECK (lethality_rate >= 0.0),
        repellent             BOOLEAN  NOT NULL,
        repellent_walk_ticks  INTEGER  NOT NULL DEFAULT 0,
        energy_cost_per_tick  FLOAT    NOT NULL CHECK (energy_cost_per_tick >= 0.0),
        synthesis_duration    INTEGER  NOT NULL DEFAULT 3,
        irreversible          BOOLEAN  NOT NULL DEFAULT FALSE,
        diffusion_coefficient FLOAT    CHECK (diffusion_coefficient BETWEEN 0.01 AND 0.90),
        ld50_mg_kg            FLOAT,   -- raw empirical value (auditability)
        source_db             VARCHAR
    )
    """,
    # ------------------------------------------------------------------
    # 4. Trigger rules (normalised, key discriminants + full JSON payload)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS trigger_rules (
        rule_id                   INTEGER PRIMARY KEY,
        flora_species_id          INTEGER  NOT NULL REFERENCES flora_species(species_id),
        rule_index                INTEGER  NOT NULL,  -- ordering within species (0-based)
        min_herbivore_population  INTEGER  NOT NULL,
        aftereffect_ticks         INTEGER  NOT NULL,
        -- Condition: scalar discriminant + full tree for complex conditions
        condition_kind            VARCHAR  NOT NULL,  -- 'herbivore_presence','all_of'
        condition_json            JSON,               -- full condition tree
        -- Action: scalar fields for fast queries + full payload for export
        action_type               VARCHAR  NOT NULL,  -- 'synthesize_substance','resource_withdrawal'
        action_substance_id       INTEGER  REFERENCES substances(substance_id),
        action_is_toxin           BOOLEAN,
        action_lethal             BOOLEAN,
        action_lethality_rate     FLOAT,
        action_repellent          BOOLEAN,
        action_repellent_walk_ticks INTEGER,
        action_synthesis_duration INTEGER,
        action_irreversible       BOOLEAN,
        action_energy_cost_per_tick FLOAT,
        action_nutrition_factor   FLOAT,  -- resource_withdrawal only
        action_json               JSON    -- full action payload for JSON export
    )
    """,
    # ------------------------------------------------------------------
    # 5. Diet compatibility matrix
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS diet_matrix (
        herbivore_species_id INTEGER  NOT NULL REFERENCES herbivore_species(species_id),
        flora_species_id     INTEGER  NOT NULL REFERENCES flora_species(species_id),
        is_edible            BOOLEAN  NOT NULL,
        globi_documented     BOOLEAN  NOT NULL DEFAULT FALSE,
        PRIMARY KEY (herbivore_species_id, flora_species_id)
    )
    """,
    # ------------------------------------------------------------------
    # 6. Provenance ledger (replaces manifest.json)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS provenance (
        record_id         INTEGER PRIMARY KEY,
        species_canonical VARCHAR  NOT NULL,
        source_db         VARCHAR  NOT NULL,
        source_license    VARCHAR  NOT NULL,
        source_doi        VARCHAR,
        source_citation   VARCHAR,
        access_date       DATE     NOT NULL,
        raw_trait_key     VARCHAR  NOT NULL,
        raw_trait_value   DOUBLE,
        derived_param     VARCHAR  NOT NULL,
        derived_value     DOUBLE   NOT NULL
    )
    """,
    # ------------------------------------------------------------------
    # 7. Index for common query patterns
    # ------------------------------------------------------------------
    "CREATE INDEX IF NOT EXISTS idx_flora_growth ON flora_species(growth_rate)",
    "CREATE INDEX IF NOT EXISTS idx_flora_family ON flora_species(family)",
    "CREATE INDEX IF NOT EXISTS idx_herbivore_family ON herbivore_species(family)",
    "CREATE INDEX IF NOT EXISTS idx_trigger_action ON trigger_rules(action_type)",
    "CREATE INDEX IF NOT EXISTS idx_trigger_flora ON trigger_rules(flora_species_id)",
    "CREATE INDEX IF NOT EXISTS idx_diet_herbivore ON diet_matrix(herbivore_species_id)",
    "CREATE INDEX IF NOT EXISTS idx_prov_source ON provenance(source_db)",
    "CREATE INDEX IF NOT EXISTS idx_prov_species ON provenance(species_canonical)",
]


def open_connection(db_path: Path | str | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection to the bio database file.

    Args:
        db_path: Path to the ``.duckdb`` file. Defaults to ``DB_PATH``.
        read_only: If True, open in read-only mode (safe for concurrent reads).

    Returns:
        An active ``DuckDBPyConnection``.

    """
    path = Path(db_path) if db_path else Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path), read_only=read_only)
    logger.debug("DuckDB: opened %s (read_only=%s)", path, read_only)
    return conn


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply all DDL statements to create or verify the schema.

    This is idempotent: ``IF NOT EXISTS`` guards ensure re-runs are safe.

    Args:
        conn: An active DuckDB connection.

    """
    for statement in _DDL_STATEMENTS:
        conn.execute(statement)
    conn.commit()
    logger.info("DuckDB: schema applied (%d statements)", len(_DDL_STATEMENTS))
