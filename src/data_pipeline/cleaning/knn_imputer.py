# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""K-Nearest Neighbours imputation for missing biological trait data.

Purpose
-------
Ecological datasets are notoriously sparse.  A species may have excellent
phytochemical records in Dr. Duke's but no SLA measurement in TRY, or vice
versa.  Naive deletion of these rows would destroy the coverage needed for
valid K-Means clustering.

Strategy
--------
We use ``sklearn.impute.KNNImputer`` with phylogenetic grouping:

1. Separate the merged DataFrame by taxonomic FAMILY (from GBIF resolution).
2. Within each family group, run KNN imputation with ``n_neighbors=5``.
3. If a family group has fewer than 5 members, fall back to ORDER grouping.
4. If ORDER also has fewer than 5, impute from the full dataset with a
   higher K (``n_neighbors=10``) to avoid over-fitting on tiny clades.

This ensures that a missing growth rate for *Pinus mugo* is imputed from
other Pinaceae, not from unrelated broadleaf angiosperms.

Boolean and categorical columns
--------------------------------
KNNImputer is only applied to float/numeric columns.  Boolean diet-matrix
columns and categorical compound-presence flags are handled separately:
- Booleans: imputed by majority vote within the family group.
- Categoricals: left as NaN / None; treated as "unknown" downstream.

Subnormal float protection
---------------------------
Any imputed float value below 1e-4 is clamped to 1e-4 before writing.
This is a defensive measure: imputed values near zero can occur when the
nearest neighbours all have very small measurements, and we must never
allow subnormal floats to enter the normalisation pipeline.
"""

from __future__ import annotations

import logging

import numpy as np
import polars as pl
from sklearn.impute import KNNImputer

logger = logging.getLogger(__name__)

# Minimum positive float in the engine (flush-to-zero threshold)
_SUBNORMAL_FLOOR: float = 1e-4

# Number of neighbours for imputation within a clade group
_K_WITHIN_FAMILY: int = 5
_K_WITHIN_ORDER: int = 5
_K_GLOBAL_FALLBACK: int = 10


def impute_missing_traits(
    df: pl.DataFrame,
    numeric_cols: list[str],
    family_col: str = "family",
    order_col: str = "order_name",
) -> pl.DataFrame:
    """Impute missing numeric trait values using phylogenetically-grouped KNN.

    Args:
        df: Input Polars DataFrame with potential null values in numeric columns.
        numeric_cols: List of float column names to impute.
        family_col: Column name containing the taxonomic family label.
        order_col: Column name containing the taxonomic order label.

    Returns:
        Polars DataFrame with imputed values in the specified columns.
        All imputed values are clamped to >= 1e-4.

    """
    existing_numeric = [c for c in numeric_cols if c in df.columns]
    if not existing_numeric:
        logger.warning("KNN imputer: no target numeric columns found in DataFrame")
        return df

    null_counts = df.select(existing_numeric).null_count().row(0)
    total_nulls = sum(null_counts)
    if total_nulls == 0:
        logger.info("KNN imputer: no missing values found, skipping")
        return df

    logger.info("KNN imputer: %d null values across %d columns", total_nulls, len(existing_numeric))

    # Work in pandas for scikit-learn compatibility, then convert back
    # We do this per-group to enforce phylogenetic locality
    result_df = df.clone()

    groups_processed = 0
    if family_col in df.columns:
        families = df[family_col].drop_nulls().unique().to_list()
        for family in families:
            mask = pl.col(family_col) == family
            group_df = df.filter(mask)

            if len(group_df) >= _K_WITHIN_FAMILY:
                imputed = _run_knn_imputer(group_df, existing_numeric, k=_K_WITHIN_FAMILY)
                result_df = _update_rows(result_df, mask, imputed, existing_numeric)
                groups_processed += 1
            elif order_col in df.columns:
                # Fall back to order-level imputation
                order_val = group_df[order_col].drop_nulls().first() if len(group_df) > 0 else None
                if order_val is not None:
                    order_mask = pl.col(order_col) == order_val
                    order_group = df.filter(order_mask)
                    if len(order_group) >= _K_WITHIN_ORDER:
                        imputed = _run_knn_imputer(order_group, existing_numeric, k=_K_WITHIN_ORDER)
                        # Only update the rows from this family within the order group
                        family_in_order = (
                            imputed.filter(pl.col(family_col) == family) if family_col in imputed.columns else imputed
                        )
                        result_df = _update_rows(result_df, mask, family_in_order, existing_numeric)
                        groups_processed += 1
                        continue

            # Global fallback for very small clades
            imputed = _run_knn_imputer(df, existing_numeric, k=_K_GLOBAL_FALLBACK)
            result_df = _update_rows(result_df, mask, imputed.filter(mask), existing_numeric)
            groups_processed += 1

    else:
        # No taxonomy info: global imputation only
        logger.warning("KNN imputer: no family column '%s' found, running global imputation", family_col)
        imputed = _run_knn_imputer(df, existing_numeric, k=_K_GLOBAL_FALLBACK)
        result_df = imputed

    logger.info("KNN imputer: processed %d taxonomic groups", groups_processed)

    # Final subnormal floor clamping
    for col in existing_numeric:
        if col in result_df.columns and result_df[col].dtype in (pl.Float64, pl.Float32):
            result_df = result_df.with_columns(
                pl.when(pl.col(col) < _SUBNORMAL_FLOOR).then(pl.lit(_SUBNORMAL_FLOOR)).otherwise(pl.col(col)).alias(col)
            )

    after_nulls = result_df.select(existing_numeric).null_count().row(0)
    remaining_nulls = sum(after_nulls)
    if remaining_nulls > 0:
        logger.warning("KNN imputer: %d null values remain after imputation (insufficient data)", remaining_nulls)

    return result_df


def _run_knn_imputer(
    df: pl.DataFrame,
    numeric_cols: list[str],
    k: int,
) -> pl.DataFrame:
    """Execute sklearn KNNImputer on the numeric columns of a DataFrame.

    Args:
        df: Polars DataFrame to impute.
        numeric_cols: Columns to impute (must be float).
        k: Number of neighbours for KNN.

    Returns:
        Polars DataFrame with imputed numeric columns and knn_influences.

    """
    available = [c for c in numeric_cols if c in df.columns]
    if not available:
        if "knn_influences" not in df.columns:
            df = df.with_columns(pl.lit("[]").alias("knn_influences"))
        return df

    pdf = df.select(available).to_pandas()
    # Find neighbors to record influences before imputing
    species_list = df["species_name"].to_list() if "species_name" in df.columns else []
    influences = ["[]"] * len(df)

    # Protect against deriving everything from a single plant (or zero)
    valid_rows_count = pdf.dropna(how="all").shape[0]
    if valid_rows_count < 2:
        logger.warning("KNN imputer: insufficient valid rows (%d), skipping imputation.", valid_rows_count)
        if "knn_influences" not in df.columns:
            df = df.with_columns(pl.lit("[]").alias("knn_influences"))
        return df

    # We only have neighbors if there are >= 2 rows
    if len(df) > 1 and species_list:
        import json

        from sklearn.neighbors import NearestNeighbors

        # We find neighbors using only rows that don't have NaNs for a rough approximation,
        # or just find neighbors using the imputed values.
        imputer = KNNImputer(n_neighbors=min(k, max(1, len(df) - 1)), keep_empty_features=True)
        imputed_array = imputer.fit_transform(pdf.values.astype(np.float64))

        nn = NearestNeighbors(n_neighbors=min(k, len(df) - 1))
        nn.fit(imputed_array)
        distances, indices = nn.kneighbors(imputed_array)

        for i, (_dist_row, idx_row) in enumerate(zip(distances, indices, strict=False)):
            # Record neighbors (excluding self)
            neighbor_species = [species_list[idx] for idx in idx_row if idx != i and idx < len(species_list)]
            influences[i] = json.dumps(neighbor_species)

    else:
        imputer = KNNImputer(n_neighbors=min(k, max(1, len(df) - 1)), keep_empty_features=True)
        imputed_array = imputer.fit_transform(pdf.values.astype(np.float64))

    imputed_df = pl.from_numpy(imputed_array, schema=available)
    imputed_df = imputed_df.with_columns(pl.Series("knn_influences", influences))

    # Replace original numeric columns with imputed values
    result = df.drop(available)
    if "knn_influences" in result.columns:
        result = result.drop("knn_influences")
    return pl.concat([result, imputed_df], how="horizontal")


def _update_rows(
    full_df: pl.DataFrame,
    mask: pl.Expr,
    imputed_group: pl.DataFrame,
    numeric_cols: list[str],
) -> pl.DataFrame:
    """Update specific rows in full_df with values from imputed_group.

    This is a safe in-place-style update: rows not matching the mask
    are untouched.

    Args:
        full_df: The complete DataFrame to update.
        mask: Boolean expression selecting the rows to update.
        imputed_group: The imputed rows to write back.
        numeric_cols: The columns that were imputed.

    Returns:
        Updated Polars DataFrame.

    """
    if len(imputed_group) == 0:
        return full_df

    # Ensure column alignment
    available = [c for c in numeric_cols if c in imputed_group.columns and c in full_df.columns]
    if not available:
        return full_df

    # Add temporary index for alignment
    full_indexed = full_df.with_row_index("__row_idx__")
    group_indices = full_indexed.filter(mask).select("__row_idx__").to_series().to_list()

    if len(group_indices) != len(imputed_group):
        # Size mismatch: skip to avoid corrupt joins
        logger.debug("KNN imputer: row count mismatch in update, skipping group")
        return full_df

    for col in available:
        new_values = imputed_group[col].to_list()
        # Build a series-level update
        updated_col = full_df[col].to_list()
        for idx, val in zip(group_indices, new_values, strict=True):
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                updated_col[idx] = float(val)
        full_df = full_df.with_columns(pl.Series(col, updated_col))

    return full_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Quick smoke test
    test_df = pl.DataFrame(
        {
            "species": ["A", "B", "C", "D", "E"],
            "family": ["Poaceae", "Poaceae", "Poaceae", "Pinaceae", "Pinaceae"],
            "order_name": ["Poales", "Poales", "Poales", "Pinales", "Pinales"],
            "growth_rate": [0.15, None, 0.12, 0.04, 0.05],
            "max_energy": [20.0, 25.0, None, 80.0, 100.0],
        }
    )
    result = impute_missing_traits(test_df, ["growth_rate", "max_energy"])
    print(result)
    print(f"Remaining nulls: {result.null_count()}")
