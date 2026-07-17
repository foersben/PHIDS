# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Global Biotic Interactions (GLoBI) ingest client.

Data source
-----------
- Database: Global Biotic Interactions (GLoBI)
- License:  CC-BY 4.0
- DOI:      https://doi.org/10.1016/j.ecoinf.2014.08.005
- Citation: Poelen, Simons & Mungall (2014). Ecological Informatics, 24, 148-159.

Attribution requirement (CC-BY 4.0)
------------------------------------
The citation above MUST appear in manifest.json and any public release.

Purpose
-------
Extracts trophic interaction records ("eats" / "is eaten by") to build the
boolean DietCompatibilityMatrix used by the simulation engine.  The matrix
entry [herbivore_i][flora_j] is True if and only if GLoBI provides at least
one documented "eats" interaction between that consumer and producer.

API
---
GLoBI REST API endpoint:
    https://api.globalbioticinteractions.org/interaction

Query parameters used:
    - sourceTaxon: herbivore species name
    - interactionType: eats
    - fields: source_taxon_name,target_taxon_name,interaction_type

One query is fired per herbivore candidate species.  The target plants
returned are then intersected with our flora candidate list.

Handling data gaps
------------------
GLoBI has strong bias toward well-studied North American / European species.
For any herbivore with ZERO documented eats-relationships to our flora list,
the client flags the species as ``diet_unresolved=True``.  The cleaning phase
will attempt phylogenetic imputation to fill these gaps.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import polars as pl

logger = logging.getLogger(__name__)

GLOBI_API_URL = "https://api.globalbioticinteractions.org/interaction"
CACHE_PATH = Path(__file__).parent.parent / "cache" / "globi_raw.parquet"

# Herbivore candidates: spans mammals and insects across multiple orders
HERBIVORE_CANDIDATES: list[str] = [
    # Cervids (Artiodactyla)
    "Odocoileus virginianus",  # White-tailed deer
    "Capreolus capreolus",  # Roe deer
    "Cervus elaphus",  # Red deer
    "Dama dama",  # Dama deer
    "Alces alces",  # Moose / elk
    # Bovids (Artiodactyla)
    "Ovis aries",  # Domestic sheep
    "Capra hircus",  # Domestic goat
    "Bos taurus",  # Domestic cattle
    "Bison bison",  # American bison
    # Small mammals (Rodentia, Lagomorpha)
    "Lepus europaeus",  # European brown hare
    "Oryctolagus cuniculus",  # European rabbit
    "Microtus agrestis",  # Field vole
    "Apodemus sylvaticus",  # Wood mouse
    "Arvicola amphibius",  # Water vole
    # Insects: Orthoptera (grasshoppers / locusts)
    "Schistocerca gregaria",  # Desert locust
    "Locusta migratoria",  # Migratory locust
    "Chorthippus parallelus",  # Meadow grasshopper
    # Insects: Lepidoptera (caterpillars)
    "Operophtera brumata",  # Winter moth (larva)
    "Lymantria dispar",  # Spongy moth (larva)
    "Pieris brassicae",  # Large white butterfly (larva)
    # Insects: Hemiptera (aphids / leafhoppers)
    "Aphis fabae",  # Black bean aphid
    "Acyrthosiphon pisum",  # Pea aphid
    "Myzus persicae",  # Green peach aphid
]


def fetch_globi(force_refresh: bool = False) -> pl.DataFrame:
    """Fetch biotic interaction records from the GLoBI REST API.

    Queries "eats" interactions for each herbivore candidate and returns a
    flat DataFrame of (source_herbivore, target_plant, interaction_type) tuples.

    Args:
        force_refresh: Re-fetch from GLoBI even if cache exists.

    Returns:
        Polars DataFrame with columns: source_taxon, target_taxon,
        interaction_type, diet_unresolved.

    Raises:
        httpx.HTTPStatusError: If the API is unreachable after retries.

    """
    if CACHE_PATH.exists() and not force_refresh:
        logger.info("GLoBI: loading from cache %s", CACHE_PATH)
        return pl.read_parquet(CACHE_PATH)

    all_records: list[dict[str, object]] = []

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for herbivore in HERBIVORE_CANDIDATES:
            logger.info("GLoBI: querying interactions for '%s'", herbivore)
            records = _query_globi(client, herbivore)
            all_records.extend(records)
            time.sleep(0.5)  # polite crawl delay

    if not all_records:
        logger.warning("GLoBI: no interaction records returned - returning empty frame")
        return _empty_globi_frame()

    df = pl.DataFrame(all_records)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info("GLoBI: cached %d interaction records to %s", len(df), CACHE_PATH)
    return df


def _query_globi(client: httpx.Client, taxon_name: str) -> list[dict[str, object]]:
    """Query GLoBI for all 'eats' interactions sourced from a given taxon.

    Args:
        client: Active httpx Client.
        taxon_name: Herbivore binomial name.

    Returns:
        List of interaction record dicts.

    """
    params: dict[str, str] = {
        "sourceTaxon": taxon_name,
        "interactionType": "eats",
        "resultType": "json.v2",
        "limit": "1000",
    }
    try:
        response = client.get(GLOBI_API_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        logger.warning("GLoBI: failed query for '%s': %s", taxon_name, exc)
        return [{"source_taxon": taxon_name, "target_taxon": None, "interaction_type": "eats", "diet_unresolved": True}]

    columns = payload.get("columns", [])
    interactions = payload.get("data", [])
    if not interactions:
        logger.debug("GLoBI: no 'eats' records for '%s'", taxon_name)
        return [{"source_taxon": taxon_name, "target_taxon": None, "interaction_type": "eats", "diet_unresolved": True}]

    records: list[dict[str, object]] = []
    for item in interactions:
        # GLoBI v2 JSON format returns lists of values corresponding to columns
        if isinstance(item, list):
            item = dict(zip(columns, item, strict=False))

        source = item.get("source_taxon_name", taxon_name)
        target = item.get("target_taxon_name", "")
        itype = item.get("interaction_type", "eats")
        if target:
            records.append(
                {
                    "source_taxon": source,
                    "target_taxon": target,
                    "interaction_type": itype,
                    "diet_unresolved": False,
                }
            )
    return (
        records
        if records
        else [{"source_taxon": taxon_name, "target_taxon": None, "interaction_type": "eats", "diet_unresolved": True}]
    )


def _empty_globi_frame() -> pl.DataFrame:
    """Return an empty DataFrame with the expected GLoBI schema."""
    return pl.DataFrame(
        {
            "source_taxon": pl.Series([], dtype=pl.Utf8),
            "target_taxon": pl.Series([], dtype=pl.Utf8),
            "interaction_type": pl.Series([], dtype=pl.Utf8),
            "diet_unresolved": pl.Series([], dtype=pl.Boolean),
        }
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = fetch_globi()
    print(result.head(20))
    print(f"Shape: {result.shape}")
    unresolved = result.filter(pl.col("diet_unresolved")).select("source_taxon").unique()
    print(f"Unresolved herbivores ({len(unresolved)}):\n{unresolved}")
