# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""K-Means archetype extraction for the PHIDS empirical database pipeline.

Purpose
-------
Reduces the full ~50-species flora and ~24-species herbivore datasets to a
set of representative archetypes that:
1. Respect the engine's "Rule of 16" memory bound (max 16 per taxon).
2. Preserve maximum ecological strategy diversity across the parameter space.

Algorithm
---------
1. Run K-Means (K=50 for flora, K=24 for herbivores) over the normalised
   feature vectors to identify distinct ecological clusters.
2. For each cluster, identify the species closest to the centroid (argmin
   Euclidean distance in the normalised feature space).
3. This centroid species is the official representative archetype for that
   cluster.
4. Apply a second reduction pass: merge the 50 flora clusters into ≤16 by
   re-running K-Means on the centroid feature vectors.

This two-pass approach ensures that the 16 final archetypes span the maximum
biological variance, not just the 16 most common species in the dataset.

Reproducibility
---------------
K-Means uses ``random_state=42`` for deterministic clustering across pipeline
runs.  The cluster assignments and centroid distances are logged to allow
verification that the same archetypes are selected across dataset refreshes.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

FLORA_ARCHETYPE_CACHE = Path(__file__).parent / "cache" / "flora_archetypes.parquet"
HERBIVORE_ARCHETYPE_CACHE = Path(__file__).parent / "cache" / "herbivore_archetypes.parquet"

# Engine memory bound: maximum species slots per taxon
ENGINE_MAX_FLORA: int = 16
ENGINE_MAX_HERBIVORES: int = 16

# K-Means cluster counts for first pass (max diversity extraction)
K_FLORA_PASS1: int = 50
K_HERBIVORE_PASS1: int = 24

FLORA_FEATURE_COLS: list[str] = [
    "growth_rate",
    "max_energy",
    "survival_threshold",
    "mechanical_damage_per_bite",
    "digestibility_modifier",
    "lethality_rate",
    "seed_dispersion_radius",
]

HERBIVORE_FEATURE_COLS: list[str] = [
    "metabolism_upkeep",
    "consumption_rate",
    "reproduction_energy_divisor",
    "split_population_threshold",
]


def extract_flora_archetypes(
    flora_df: pl.DataFrame,
    species_name_col: str = "species_name",
    force_refresh: bool = False,
) -> pl.DataFrame:
    """Extract up to ENGINE_MAX_FLORA representative flora archetypes.

    Args:
        flora_df: Normalised flora DataFrame with feature columns.
        species_name_col: Column containing the canonical species name.
        force_refresh: Re-run clustering even if cache exists.

    Returns:
        Polars DataFrame of archetype rows (≤16 rows).

    Raises:
        ValueError: If no valid feature columns are found in the DataFrame.

    """
    if FLORA_ARCHETYPE_CACHE.exists() and not force_refresh:
        logger.info("Archetypes: loading flora archetypes from cache")
        return pl.read_parquet(FLORA_ARCHETYPE_CACHE)

    available_features = [c for c in FLORA_FEATURE_COLS if c in flora_df.columns]
    if not available_features:
        raise ValueError(f"No flora feature columns found. Expected one of: {FLORA_FEATURE_COLS}")

    logger.info("Archetypes: extracting flora archetypes from %d species", len(flora_df))

    # Pass 1: K=50 clusters (or len(df) if < 50)
    k1 = min(K_FLORA_PASS1, len(flora_df))
    pass1_centroids, pass1_archetypes = _run_kmeans_and_extract(
        flora_df, available_features, species_name_col, k=k1, label="flora_pass1"
    )

    # Pass 2: Reduce to ≤16 archetypes by re-clustering centroid vectors
    if len(pass1_archetypes) > ENGINE_MAX_FLORA:
        k2 = min(ENGINE_MAX_FLORA, len(pass1_archetypes))
        _, final_archetypes = _run_kmeans_and_extract(
            pass1_archetypes, available_features, species_name_col, k=k2, label="flora_pass2"
        )
    else:
        final_archetypes = pass1_archetypes

    FLORA_ARCHETYPE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    final_archetypes.write_parquet(FLORA_ARCHETYPE_CACHE)
    logger.info("Archetypes: selected %d flora archetypes", len(final_archetypes))
    return final_archetypes


def extract_herbivore_archetypes(
    herbivore_df: pl.DataFrame,
    species_name_col: str = "MSW05_Binomial",
    force_refresh: bool = False,
) -> pl.DataFrame:
    """Extract up to ENGINE_MAX_HERBIVORES representative herbivore archetypes.

    Args:
        herbivore_df: Normalised herbivore DataFrame with feature columns.
        species_name_col: Column containing the canonical species name.
        force_refresh: Re-run clustering even if cache exists.

    Returns:
        Polars DataFrame of archetype rows (≤16 rows).

    Raises:
        ValueError: If no valid feature columns are found.

    """
    if HERBIVORE_ARCHETYPE_CACHE.exists() and not force_refresh:
        logger.info("Archetypes: loading herbivore archetypes from cache")
        return pl.read_parquet(HERBIVORE_ARCHETYPE_CACHE)

    available_features = [c for c in HERBIVORE_FEATURE_COLS if c in herbivore_df.columns]
    if not available_features:
        raise ValueError(f"No herbivore feature columns found. Expected one of: {HERBIVORE_FEATURE_COLS}")

    # Filter to ecologically relevant herbivore orders (exclude omnivores, carnivores)
    herbivore_df = _filter_herbivore_orders(herbivore_df)
    logger.info("Archetypes: extracting herbivore archetypes from %d species", len(herbivore_df))

    k = min(K_HERBIVORE_PASS1, len(herbivore_df))
    if k < 1:
        logger.warning("Archetypes: insufficient herbivore data for clustering")
        return herbivore_df

    # For herbivores, we may already have ≤16 candidates; a single pass suffices
    if len(herbivore_df) <= ENGINE_MAX_HERBIVORES:
        final_archetypes = herbivore_df
    else:
        k_final = min(ENGINE_MAX_HERBIVORES, len(herbivore_df))
        _, final_archetypes = _run_kmeans_and_extract(
            herbivore_df, available_features, species_name_col, k=k_final, label="herbivore"
        )

    HERBIVORE_ARCHETYPE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    final_archetypes.write_parquet(HERBIVORE_ARCHETYPE_CACHE)
    logger.info("Archetypes: selected %d herbivore archetypes", len(final_archetypes))
    return final_archetypes


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_kmeans_and_extract(
    df: pl.DataFrame,
    feature_cols: list[str],
    species_col: str,
    k: int,
    label: str,
) -> tuple[np.ndarray, pl.DataFrame]:
    """Run K-Means and extract the centroid-nearest species row per cluster.

    Args:
        df: DataFrame with normalised feature columns.
        feature_cols: Feature columns for clustering.
        species_col: Column containing species names.
        k: Number of clusters.
        label: Human-readable label for logging.

    Returns:
        Tuple of (centroid_array, archetype_DataFrame).

    """
    feature_matrix = df.select(feature_cols).to_numpy(allow_copy=True).astype(np.float64)

    # Standardise features for clustering (KMeans is Euclidean distance-based)
    scaler = StandardScaler()
    feature_scaled = scaler.fit_transform(feature_matrix)

    # Replace NaN rows with zero (should be none after imputation, but defensive)
    nan_mask = np.any(np.isnan(feature_scaled), axis=1)
    if nan_mask.sum() > 0:
        logger.warning("Archetypes (%s): %d rows with NaN features replaced with zeros", label, nan_mask.sum())
        feature_scaled[nan_mask] = 0.0

    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    cluster_labels = kmeans.fit_predict(feature_scaled)
    centroids = kmeans.cluster_centers_

    # Find the species closest to each cluster centroid
    archetype_indices: list[int] = []
    for cluster_id in range(k):
        cluster_mask = cluster_labels == cluster_id
        cluster_indices = np.where(cluster_mask)[0]
        if len(cluster_indices) == 0:
            continue
        cluster_features = feature_scaled[cluster_indices]
        centroid = centroids[cluster_id]
        distances = np.linalg.norm(cluster_features - centroid, axis=1)
        nearest_local_idx = int(np.argmin(distances))
        nearest_global_idx = int(cluster_indices[nearest_local_idx])
        archetype_indices.append(nearest_global_idx)

        species_name = "unknown"
        if species_col in df.columns:
            species_name = str(df[species_col][nearest_global_idx])
        logger.debug(
            "Archetypes (%s): cluster %d → %s (dist=%.4f)", label, cluster_id, species_name, float(np.min(distances))
        )

    archetype_df = df[archetype_indices]
    logger.info("Archetypes (%s): K=%d → %d archetypes selected", label, k, len(archetype_df))
    return centroids, archetype_df


def _filter_herbivore_orders(df: pl.DataFrame) -> pl.DataFrame:
    """Filter mammal DataFrame to ecologically herbivorous orders only.

    Excludes carnivore and omnivore-dominated orders to focus the cluster
    space on genuine plant consumers.

    Args:
        df: PanTHERIA DataFrame with MSW05_Order column.

    Returns:
        Filtered DataFrame.

    """
    if "MSW05_Order" not in df.columns:
        return df

    herbivore_orders = {
        "Artiodactyla",  # deer, cattle, sheep, goats, bison
        "Perissodactyla",  # horses, rhinos, tapirs
        "Lagomorpha",  # rabbits, hares, pikas
        "Rodentia",  # many herbivorous rodents (voles, mice, etc.)
        "Proboscidea",  # elephants
        "Sirenia",  # manatees (aquatic herbivores)
    }

    filtered = df.filter(pl.col("MSW05_Order").is_in(herbivore_orders))
    excluded = len(df) - len(filtered)
    if excluded > 0:
        logger.info("Archetypes: excluded %d non-herbivore mammal species by order filter", excluded)
    return filtered


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Quick smoke test with synthetic data
    import polars as pl

    synthetic_flora = pl.DataFrame(
        {
            "species_name": [f"Species_{i}" for i in range(20)],
            "growth_rate": [float(i) * 0.05 for i in range(20)],
            "max_energy": [float(i) * 5.0 + 5.0 for i in range(20)],
            "survival_threshold": [float(i) * 0.5 + 0.5 for i in range(20)],
            "mechanical_damage_per_bite": [float(i) * 0.015 for i in range(20)],
            "digestibility_modifier": [1.0 - float(i) * 0.025 for i in range(20)],
            "lethality_rate": [float(i) * 0.5 for i in range(20)],
            "seed_dispersion_radius": [1.0 + float(i) * 0.2 for i in range(20)],
        }
    )

    archetypes = extract_flora_archetypes(synthetic_flora, force_refresh=True)
    print(f"Flora archetypes ({len(archetypes)}):")
    print(archetypes.select(["species_name", "growth_rate", "max_energy"]))
