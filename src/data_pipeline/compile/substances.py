"""Substances compilation logic."""

from __future__ import annotations

import polars as pl

from data_pipeline.compile.registry import _SUBSTANCE_REGISTRY


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
