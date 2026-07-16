# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""GBIF taxonomic synonym resolution.

Data source
-----------
- Service: GBIF Species Match API
- License: CC0 1.0
- DOI:     https://doi.org/10.15468/dl.gbif
- URL:     https://api.gbif.org/v1/species/match

Purpose
-------
Resolves all raw species name strings from the ingested databases to canonical
GBIF Backbone Taxonomy identifiers (usageKey).  This creates a shared primary
key across TRY, GLoBI, PanTHERIA, and Dr. Duke's datasets which may reference
the same species using different synonyms or outdated binomials.

Algorithm
---------
1. Collect all unique species names from all ingest caches.
2. For each name, POST to GBIF ``species/match`` with ``strict=False``
   to allow fuzzy matching.
3. If ``matchType == "EXACT"`` or ``"FUZZY"``, accept the ``usageKey``.
4. If ``matchType == "NONE"`` or confidence < 80, flag as ``unresolved``.
5. Build and return a synonym map: ``{raw_name: (canonical_name, usageKey)}``.

The synonym map is then used by downstream steps to join all DataFrames on
``canonical_key`` rather than raw string matching.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import polars as pl

logger = logging.getLogger(__name__)

GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
CACHE_PATH = Path(__file__).parent.parent / "cache" / "gbif_synonyms.parquet"

# Minimum confidence threshold for accepting a GBIF match (0-100)
MIN_CONFIDENCE = 80


def resolve_gbif_synonyms(
    species_names: list[str],
    force_refresh: bool = False,
) -> pl.DataFrame:
    """Resolve a list of species names to their canonical GBIF identifiers.

    Args:
        species_names: List of raw species name strings to resolve.
        force_refresh: Re-query GBIF even if cache exists.

    Returns:
        Polars DataFrame with columns:
            - raw_name: original string submitted
            - canonical_name: GBIF-accepted canonical species name
            - usage_key: GBIF integer identifier
            - match_type: "EXACT", "FUZZY", or "NONE"
            - confidence: int 0-100
            - resolved: bool (True if accepted match)
            - kingdom / phylum / class / order / family / genus (taxonomy hierarchy)

    """
    if CACHE_PATH.exists() and not force_refresh:
        cached = pl.read_parquet(CACHE_PATH)
        # Check if all requested names are in cache
        cached_names = set(cached["raw_name"].to_list())
        missing = [n for n in species_names if n not in cached_names]
        if not missing:
            logger.info("GBIF: all %d names resolved from cache", len(species_names))
            return cached.filter(pl.col("raw_name").is_in(species_names))

        logger.info("GBIF: %d names missing from cache, fetching delta", len(missing))
        new_records = _fetch_gbif_matches(missing)
        new_df = pl.DataFrame(new_records)
        combined = pl.concat([cached, new_df])
        combined.write_parquet(CACHE_PATH)
        return combined.filter(pl.col("raw_name").is_in(species_names))

    logger.info("GBIF: resolving %d species names", len(species_names))
    records = _fetch_gbif_matches(species_names)
    df = pl.DataFrame(records)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(CACHE_PATH)
    logger.info(
        "GBIF: resolved %d / %d names successfully", df.filter(pl.col("resolved"))["resolved"].sum(), len(species_names)
    )
    return df


def _fetch_gbif_matches(species_names: list[str]) -> list[dict[str, object]]:
    """Query GBIF for each name and parse the response.

    Args:
        species_names: Names to resolve.

    Returns:
        List of resolved record dicts.

    """
    records: list[dict[str, object]] = []
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for name in species_names:
            record = _query_single(client, name)
            records.append(record)
            time.sleep(0.2)  # polite rate limiting
    return records


def _query_single(client: httpx.Client, raw_name: str) -> dict[str, object]:
    """Query GBIF for one species name.

    Args:
        client: Active httpx Client.
        raw_name: Raw species name string.

    Returns:
        Resolved record dict.

    """
    base: dict[str, object] = {
        "raw_name": raw_name,
        "canonical_name": raw_name,  # default: keep original if unresolved
        "usage_key": None,
        "match_type": "NONE",
        "confidence": 0,
        "resolved": False,
        "kingdom": None,
        "phylum": None,
        "class_name": None,
        "order_name": None,
        "family": None,
        "genus": None,
    }

    try:
        resp = client.get(
            GBIF_MATCH_URL,
            params={"name": raw_name, "strict": "false"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        logger.warning("GBIF: failed to resolve '%s': %s", raw_name, exc)
        return base

    match_type = data.get("matchType", "NONE")
    confidence = int(data.get("confidence", 0))

    if match_type in ("EXACT", "FUZZY") and confidence >= MIN_CONFIDENCE:
        base["canonical_name"] = data.get("canonicalName") or data.get("scientificName", raw_name)
        base["usage_key"] = data.get("usageKey")
        base["match_type"] = match_type
        base["confidence"] = confidence
        base["resolved"] = True
        base["kingdom"] = data.get("kingdom")
        base["phylum"] = data.get("phylum")
        base["class_name"] = data.get("class")
        base["order_name"] = data.get("order")
        base["family"] = data.get("family")
        base["genus"] = data.get("genus")
    else:
        logger.debug("GBIF: unresolved '%s' (matchType=%s, confidence=%d)", raw_name, match_type, confidence)

    return base


def build_synonym_map(resolved_df: pl.DataFrame) -> dict[str, str]:
    """Build a dict mapping raw names to canonical GBIF names.

    Args:
        resolved_df: Output DataFrame from ``resolve_gbif_synonyms``.

    Returns:
        Dict: ``{raw_name: canonical_name}``.

    """
    return dict(
        zip(
            resolved_df["raw_name"].to_list(),
            resolved_df["canonical_name"].to_list(),
            strict=True,
        )
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data_pipeline.ingest.globi_client import HERBIVORE_CANDIDATES
    from data_pipeline.ingest.try_client import TARGET_SPECIES

    all_names = list(set(TARGET_SPECIES + HERBIVORE_CANDIDATES))
    result = resolve_gbif_synonyms(all_names)
    print(result.head(20))
    unresolved = result.filter(~pl.col("resolved"))
    print(f"\nUnresolved ({len(unresolved)}):\n{unresolved.select('raw_name')}")
