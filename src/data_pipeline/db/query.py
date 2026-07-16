# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Convenience query interface for the PHIDS bio database.

Provides typed, named query methods covering the patterns needed by:
- The HTMX UI API endpoints (filtering, searching, paging)
- The DSE optimizer (batch parameter retrieval, diet matrix lookup)
- Diagnostic scripts (provenance audits, coverage reports)

All methods accept an open ``DuckDBPyConnection`` rather than opening their
own to allow callers to manage connection lifecycle (especially important in
the FastAPI async context).

Example usage
-------------
    from data_pipeline.db import open_connection, BioQuery

    with open_connection(read_only=True) as conn:
        # Partial load: only fetch scalars, not trigger_rules
        fast_growers = BioQuery.flora_by_growth_rate(conn, min_rate=0.3)
        # Diet compatibility
        diet = BioQuery.diet_for_herbivore(conn, "Capreolus capreolus")
        # Provenance audit
        try_records = BioQuery.provenance_by_source(conn, "TRY")
"""

from __future__ import annotations

import logging

import duckdb
import polars as pl

logger = logging.getLogger(__name__)


class BioQuery:
    """Typed query methods for the PHIDS bio database.

    All methods are static and accept a connection, so they compose cleanly
    without implicit state.
    """

    # ------------------------------------------------------------------
    # Flora queries
    # ------------------------------------------------------------------

    @staticmethod
    def all_flora_scalars(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
        """Load all flora species scalars without trigger_rules (fast partial load).

        This is the primary partial-load pattern: the engine never needs trigger
        rules at query time; they are only needed at simulation bootstrap.

        Args:
            conn: Active DuckDB connection.

        Returns:
            Polars DataFrame with all flora scalar columns.

        """
        return conn.execute("""
            SELECT
                species_id, canonical_name,
                growth_rate, max_energy, survival_threshold,
                seed_cost, seed_dispersion_radius,
                mechanical_damage_per_bite, digestibility_modifier,
                family, order_name, cluster_id, source_databases
            FROM flora_species
            ORDER BY canonical_name
        """).pl()

    @staticmethod
    def flora_by_growth_rate(
        conn: duckdb.DuckDBPyConnection,
        min_rate: float = 0.0,
        max_rate: float = 1.0,
    ) -> pl.DataFrame:
        """Filter flora by growth rate range.

        Args:
            conn: Active DuckDB connection.
            min_rate: Lower bound (inclusive).
            max_rate: Upper bound (inclusive).

        Returns:
            Filtered flora DataFrame.

        """
        return conn.execute(
            """
            SELECT species_id, canonical_name, growth_rate, max_energy,
                   digestibility_modifier, lethality_rate_max
            FROM flora_species f
            LEFT JOIN (
                SELECT flora_species_id, MAX(action_lethality_rate) AS lethality_rate_max
                FROM trigger_rules
                WHERE action_type = 'synthesize_substance'
                GROUP BY flora_species_id
            ) tr ON tr.flora_species_id = f.species_id
            WHERE f.growth_rate BETWEEN ? AND ?
            ORDER BY f.growth_rate DESC
            """,
            [min_rate, max_rate],
        ).pl()

    @staticmethod
    def toxic_flora(
        conn: duckdb.DuckDBPyConnection,
        min_lethality: float = 2.0,
    ) -> pl.DataFrame:
        """Find flora species with documented toxin trigger rules above a lethality threshold.

        Args:
            conn: Active DuckDB connection.
            min_lethality: Minimum lethality_rate threshold.

        Returns:
            DataFrame of toxic flora with their max lethality rate.

        """
        return conn.execute(
            """
            SELECT f.canonical_name, f.growth_rate, f.digestibility_modifier,
                   MAX(tr.action_lethality_rate) AS max_lethality,
                   COUNT(tr.rule_id) AS rule_count
            FROM flora_species f
            JOIN trigger_rules tr ON tr.flora_species_id = f.species_id
            WHERE tr.action_is_toxin = TRUE
              AND tr.action_lethality_rate >= ?
            GROUP BY f.species_id, f.canonical_name, f.growth_rate, f.digestibility_modifier
            ORDER BY max_lethality DESC
            """,
            [min_lethality],
        ).pl()

    @staticmethod
    def flora_with_voc(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
        """Find all flora species that emit at least one VOC signal.

        Args:
            conn: Active DuckDB connection.

        Returns:
            DataFrame of flora with VOC rules.

        """
        return conn.execute("""
            SELECT DISTINCT f.canonical_name, f.growth_rate, f.family,
                   s.name AS voc_name, s.diffusion_coefficient
            FROM flora_species f
            JOIN trigger_rules tr ON tr.flora_species_id = f.species_id
            JOIN substances s ON s.substance_id = tr.action_substance_id
            WHERE tr.action_is_toxin = FALSE
              AND s.repellent = TRUE
              AND s.diffusion_coefficient IS NOT NULL
            ORDER BY s.diffusion_coefficient DESC
        """).pl()

    # ------------------------------------------------------------------
    # Herbivore queries
    # ------------------------------------------------------------------

    @staticmethod
    def all_herbivore_scalars(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
        """Load all herbivore scalars without the diet list (fast partial load).

        Args:
            conn: Active DuckDB connection.

        Returns:
            Polars DataFrame with all herbivore scalar columns.

        """
        return conn.execute("""
            SELECT
                species_id, canonical_name,
                metabolism_upkeep, consumption_rate,
                mitosis_threshold, split_ratio,
                reproduction_energy_divisor, split_population_threshold,
                morphological_adaptation, chemical_neutralization, digestive_efficiency,
                family, order_name, cluster_id
            FROM herbivore_species
            ORDER BY canonical_name
        """).pl()

    @staticmethod
    def diet_for_herbivore(
        conn: duckdb.DuckDBPyConnection,
        herbivore_name: str,
    ) -> pl.DataFrame:
        """Retrieve the edible flora list for a specific herbivore.

        Args:
            conn: Active DuckDB connection.
            herbivore_name: Canonical species name.

        Returns:
            DataFrame of edible flora species (canonical_name, is_edible, globi_documented).

        """
        return conn.execute(
            """
            SELECT f.canonical_name, dm.is_edible, dm.globi_documented,
                   f.growth_rate, f.digestibility_modifier
            FROM diet_matrix dm
            JOIN herbivore_species h ON h.species_id = dm.herbivore_species_id
            JOIN flora_species f ON f.species_id = dm.flora_species_id
            WHERE h.canonical_name = ?
              AND dm.is_edible = TRUE
            ORDER BY f.canonical_name
            """,
            [herbivore_name],
        ).pl()

    @staticmethod
    def herbivores_that_eat(
        conn: duckdb.DuckDBPyConnection,
        flora_name: str,
    ) -> pl.DataFrame:
        """Find all herbivores documented to eat a given flora species.

        Args:
            conn: Active DuckDB connection.
            flora_name: Canonical flora species name.

        Returns:
            DataFrame of herbivore species that eat the given plant.

        """
        return conn.execute(
            """
            SELECT h.canonical_name, h.metabolism_upkeep, h.consumption_rate,
                   dm.globi_documented
            FROM diet_matrix dm
            JOIN herbivore_species h ON h.species_id = dm.herbivore_species_id
            JOIN flora_species f ON f.species_id = dm.flora_species_id
            WHERE f.canonical_name = ?
              AND dm.is_edible = TRUE
            ORDER BY h.canonical_name
            """,
            [flora_name],
        ).pl()

    # ------------------------------------------------------------------
    # Substance queries
    # ------------------------------------------------------------------

    @staticmethod
    def all_substances(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
        """Load the full substances table.

        Args:
            conn: Active DuckDB connection.

        Returns:
            Complete substances DataFrame.

        """
        return conn.execute("SELECT * FROM substances ORDER BY substance_id").pl()

    @staticmethod
    def volatile_substances(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
        """Load all substances with a diffusion coefficient (VOC / volatile signals).

        Args:
            conn: Active DuckDB connection.

        Returns:
            DataFrame of volatile substances ordered by diffusion coefficient.

        """
        return conn.execute("""
            SELECT substance_id, name, compound_class, diffusion_coefficient,
                   repellent, repellent_walk_ticks, lethality_rate
            FROM substances
            WHERE diffusion_coefficient IS NOT NULL
            ORDER BY diffusion_coefficient DESC
        """).pl()

    # ------------------------------------------------------------------
    # Provenance / audit queries
    # ------------------------------------------------------------------

    @staticmethod
    def provenance_by_source(
        conn: duckdb.DuckDBPyConnection,
        source_db: str,
    ) -> pl.DataFrame:
        """Retrieve all provenance records from a specific database.

        Args:
            conn: Active DuckDB connection.
            source_db: Source database name (e.g. 'TRY', 'GLoBI').

        Returns:
            Provenance records for that source.

        """
        return conn.execute(
            "SELECT * FROM provenance WHERE source_db = ? ORDER BY species_canonical",
            [source_db],
        ).pl()

    @staticmethod
    def coverage_report(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
        """Generate a data coverage summary grouped by source database.

        Args:
            conn: Active DuckDB connection.

        Returns:
            DataFrame with source_db, record_count, unique_species, license.

        """
        return conn.execute("""
            SELECT
                source_db,
                COUNT(*) AS record_count,
                COUNT(DISTINCT species_canonical) AS unique_species,
                ANY_VALUE(source_license) AS license
            FROM provenance
            GROUP BY source_db
            ORDER BY record_count DESC
        """).pl()

    @staticmethod
    def unresolved_diet_edges(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
        """Find diet matrix edges that were not GLoBI-documented (imputed).

        Useful for identifying where the pipeline fell back to phylogenetic
        imputation or the all-flora permissive fallback.

        Args:
            conn: Active DuckDB connection.

        Returns:
            DataFrame of imputed diet edges.

        """
        return conn.execute("""
            SELECT h.canonical_name AS herbivore, f.canonical_name AS flora,
                   dm.is_edible
            FROM diet_matrix dm
            JOIN herbivore_species h ON h.species_id = dm.herbivore_species_id
            JOIN flora_species f ON f.species_id = dm.flora_species_id
            WHERE dm.globi_documented = FALSE
            ORDER BY h.canonical_name, f.canonical_name
        """).pl()

    # ------------------------------------------------------------------
    # Database metadata
    # ------------------------------------------------------------------

    @staticmethod
    def summary(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
        """Return a summary of row counts for all tables.

        Args:
            conn: Active DuckDB connection.

        Returns:
            Dict mapping table name to row count.

        """
        tables = ["flora_species", "herbivore_species", "substances", "trigger_rules", "diet_matrix", "provenance"]
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
