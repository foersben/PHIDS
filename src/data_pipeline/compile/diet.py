"""Diet matrix compilation logic."""

from __future__ import annotations

import polars as pl


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
