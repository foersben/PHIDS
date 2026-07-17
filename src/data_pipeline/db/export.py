# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""JSON export: DuckDB → bio_database.json (engine compatibility layer).

The simulation engine and the HTMX UI currently load ``bio_database.json``
via ``src/phids/analytics/bio_database.py``.  This module generates that file
on demand from the DuckDB source of truth, preserving full backward
compatibility while making the JSON a derived artifact rather than the
authoritative store.

Export strategy
---------------
The JSON is reconstructed by assembling each entity from its DuckDB columns:

- Flora: scalar columns from ``flora_species`` + trigger rules joined from
  ``trigger_rules`` (action_json column for the nested payload).
- Herbivores: scalar columns from ``herbivore_species`` + diet list assembled
  from ``diet_matrix``.
- Substances: flat columns from ``substances``.

Hugging Face publishing
-----------------------
The DuckDB file itself is published alongside the JSON so downstream tools can
query it directly without having to re-parse JSON.  The HF repository at
``foersben/PHIDS-empirical-database`` stores:
  - ``bio_database.duckdb``: primary queryable database
  - ``bio_database.json``:   engine-compatibility export
  - ``manifest.json``:       provenance export from the DuckDB provenance table
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb  # noqa: TC002

from data_pipeline.db.schema import DB_PATH, open_connection

logger = logging.getLogger(__name__)

# Output paths
JSON_PATH = DB_PATH.parent / "bio_database.json"
MANIFEST_PATH = Path(__file__).parent.parent / "manifest.json"


def export_bio_database_json(
    conn: duckdb.DuckDBPyConnection | None = None,
    output_path: Path | None = None,
) -> Path:
    """Reconstruct ``bio_database.json`` from DuckDB tables.

    Args:
        conn: Active DuckDB connection.  Opens ``DB_PATH`` if None.
        output_path: Override output path.  Defaults to ``JSON_PATH``.

    Returns:
        The path to the written JSON file.

    Raises:
        FileNotFoundError: If the DuckDB file does not exist and no connection
            is provided.

    """
    out = Path(output_path) if output_path else JSON_PATH
    own_conn = conn is None
    if own_conn:
        conn = open_connection(read_only=True)

    try:
        payload: dict[str, object] = {
            "flora": _export_flora(conn),
            "herbivores": _export_herbivores(conn),
            "substances": _export_substances(conn),
        }
    finally:
        if own_conn:
            conn.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    flora_count = len(payload["flora"])  # type: ignore[arg-type]
    herb_count = len(payload["herbivores"])  # type: ignore[arg-type]
    sub_count = len(payload["substances"])  # type: ignore[arg-type]
    logger.info(
        "Export: wrote bio_database.json (%d flora, %d herbivores, %d substances) → %s",
        flora_count,
        herb_count,
        sub_count,
        out,
    )
    return out


def export_manifest_json(
    conn: duckdb.DuckDBPyConnection | None = None,
    output_path: Path | None = None,
) -> Path:
    """Export the provenance table to ``manifest.json`` for HF Hub upload.

    Args:
        conn: Active DuckDB connection.
        output_path: Override output path. Defaults to ``MANIFEST_PATH``.

    Returns:
        The path to the written manifest file.

    """
    import datetime

    out = Path(output_path) if output_path else MANIFEST_PATH
    own_conn = conn is None
    if own_conn:
        conn = open_connection(read_only=True)

    try:
        prov_df = conn.execute("SELECT * FROM provenance ORDER BY record_id").pl()
    finally:
        if own_conn:
            conn.close()

    # Embed full citation strings from the provenance.CITATIONS dict
    from data_pipeline.provenance import CITATIONS

    manifest: dict[str, object] = {
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "pipeline_version": "1.0.0",
        "database_format": "DuckDB 1.1+",
        "citations": CITATIONS,
        "records_count": len(prov_df),
        "records": prov_df.to_dicts(),
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False, default=str)

    logger.info("Export: wrote manifest.json (%d provenance records) → %s", len(prov_df), out)
    return out


# ---------------------------------------------------------------------------
# Per-section assemblers
# ---------------------------------------------------------------------------


def _export_flora(conn: duckdb.DuckDBPyConnection) -> dict[str, object]:
    """Assemble the flora section from flora_species + trigger_rules tables.

    Args:
        conn: Active DuckDB connection.

    Returns:
        Dict keyed by canonical_name with full flora entry payloads.

    """
    flora_rows = conn.execute("""
        SELECT
            f.species_id,
            f.canonical_name,
            f.growth_rate,
            f.max_energy,
            f.survival_threshold,
            f.seed_cost,
            f.seed_dispersion_radius,
            f.mechanical_damage_per_bite,
            f.digestibility_modifier,
            f.cluster_id,
            f.centroid_distance,
            f.source_databases
        FROM flora_species f
        ORDER BY f.species_id
    """).pl()

    # Fetch all trigger rules in one query, then group in Python
    rules_rows = conn.execute("""
        SELECT
            flora_species_id,
            rule_index,
            min_herbivore_population,
            aftereffect_ticks,
            condition_kind,
            condition_json,
            action_type,
            action_json
        FROM trigger_rules
        ORDER BY flora_species_id, rule_index
    """).pl()

    # Build per-species rule lists
    rules_by_species: dict[int, list[dict[str, object]]] = {}
    for row in rules_rows.to_dicts():
        fid = int(row["flora_species_id"])
        rules_by_species.setdefault(fid, [])
        # Reconstruct the rule payload the engine expects
        rule: dict[str, object] = {
            "min_herbivore_population": row["min_herbivore_population"],
            "aftereffect_ticks": row["aftereffect_ticks"],
            "activation_condition": _parse_json_field(row.get("condition_json"))
            or {"kind": row["condition_kind"], "min_herbivore_population": row["min_herbivore_population"]},
            "action": _parse_json_field(row.get("action_json")) or {"type": row["action_type"]},
        }
        rules_by_species[fid].append(rule)

    result: dict[str, object] = {}
    for row in flora_rows.to_dicts():
        sid = int(row["species_id"])
        name = str(row["canonical_name"])
        result[name] = {
            "base_metrics": {
                "growth_rate": row["growth_rate"],
                "max_energy": row["max_energy"],
                "survival_threshold": row["survival_threshold"],
                "seed_cost": row["seed_cost"],
                "seed_dispersion_radius": row["seed_dispersion_radius"],
            },
            "passive_defenses": {
                "mechanical_damage_per_bite": row["mechanical_damage_per_bite"],
                "digestibility_modifier": row["digestibility_modifier"],
            },
            "provenance": {
                "cluster_id": row.get("cluster_id"),
                "centroid_distance": row.get("centroid_distance"),
                "source_databases": row.get("source_databases"),
            },
            "trigger_rules": rules_by_species.get(sid, []),
        }
    return result


def _export_herbivores(conn: duckdb.DuckDBPyConnection) -> dict[str, object]:
    """Assemble the herbivores section from herbivore_species + diet_matrix.

    Args:
        conn: Active DuckDB connection.

    Returns:
        Dict keyed by canonical_name with full herbivore entry payloads.

    """
    herb_rows = conn.execute("""
        SELECT
            h.species_id,
            h.canonical_name,
            h.metabolism_upkeep,
            h.consumption_rate,
            h.mitosis_threshold,
            h.split_ratio,
            h.morphological_adaptation,
            h.chemical_neutralization,
            h.digestive_efficiency,
            h.cluster_id,
            h.source_databases
        FROM herbivore_species h
        ORDER BY h.species_id
    """).pl()

    # Build diet lists: one query, group in Python
    diet_rows = conn.execute("""
        SELECT
            dm.herbivore_species_id,
            f.canonical_name AS flora_name
        FROM diet_matrix dm
        JOIN flora_species f ON f.species_id = dm.flora_species_id
        WHERE dm.is_edible = TRUE
        ORDER BY dm.herbivore_species_id
    """).pl()

    diet_by_herbivore: dict[int, list[str]] = {}
    for row in diet_rows.to_dicts():
        hid = int(row["herbivore_species_id"])
        diet_by_herbivore.setdefault(hid, [])
        diet_by_herbivore[hid].append(str(row["flora_name"]))

    result: dict[str, object] = {}
    for row in herb_rows.to_dicts():
        hid = int(row["species_id"])
        name = str(row["canonical_name"])
        result[name] = {
            "base_metrics": {
                "metabolism_upkeep": row["metabolism_upkeep"],
                "consumption_rate": row["consumption_rate"],
                "mitosis_threshold": row["mitosis_threshold"],
                "split_ratio": row["split_ratio"],
            },
            "resistances": {
                "morphological_adaptation": row["morphological_adaptation"],
                "chemical_neutralization": row["chemical_neutralization"],
                "digestive_efficiency": row["digestive_efficiency"],
            },
            "provenance": {
                "cluster_id": row.get("cluster_id"),
                "centroid_distance": row.get("centroid_distance"),
                "source_databases": row.get("source_databases"),
            },
            "diet": diet_by_herbivore.get(hid, []),
        }
    return result


def _export_substances(conn: duckdb.DuckDBPyConnection) -> dict[str, object]:
    """Assemble the substances section from the substances table.

    Args:
        conn: Active DuckDB connection.

    Returns:
        Dict keyed by substance_id (as string) with substance payloads.

    """
    rows = conn.execute("SELECT * FROM substances ORDER BY substance_id").pl()
    result: dict[str, object] = {}
    for row in rows.to_dicts():
        sid = str(row["substance_id"])
        entry: dict[str, object] = {
            "name": row["name"],
            "is_toxin": row["is_toxin"],
            "lethal": row["lethal"],
            "lethality_rate": row["lethality_rate"],
            "repellent": row["repellent"],
            "repellent_walk_ticks": row["repellent_walk_ticks"],
            "energy_cost_per_tick": row["energy_cost_per_tick"],
            "synthesis_duration": row["synthesis_duration"],
            "irreversible": row["irreversible"],
        }
        if row.get("diffusion_coefficient") is not None:
            entry["diffusion_coefficient"] = row["diffusion_coefficient"]
        result[sid] = entry
    return result


# ---------------------------------------------------------------------------
# Hugging Face Hub publishing
# ---------------------------------------------------------------------------


def publish_to_huggingface(
    repo_id: str = "foersben/PHIDS-empirical-database",
    hf_token: str | None = None,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> None:
    """Upload the DuckDB database, JSON export, and manifest to Hugging Face Hub.

    Publishes three files to the ``foersben/PHIDS-empirical-database`` dataset:
    - ``bio_database.duckdb``: primary queryable database
    - ``bio_database.json``: engine-compatibility JSON export
    - ``manifest.json``: provenance and citation ledger

    Authentication via ``HF_TOKEN`` environment variable or explicit token.
    In GitHub Actions, OIDC is preferred (no secret exposure).

    Args:
        repo_id: Hugging Face Hub dataset repository ID.
        hf_token: Explicit HF access token. Falls back to ``HF_TOKEN`` env var.
        conn: Active DuckDB connection for on-demand export. Opened if None.

    """
    import os

    # -------------------------------------------------------------------------
    # Layer 3 Protection: NC-Source Publish Guard
    # Scan the provenance table for any records sourced from NC-licensed
    # databases before a single byte is uploaded. This is a hard abort.
    # -------------------------------------------------------------------------
    core_repo = "foersben/PHIDS-empirical-database"

    if repo_id == core_repo:
        own_conn_check = conn is None
        _check_conn = open_connection(read_only=True) if own_conn_check else conn
        try:
            nc_rows = _check_conn.execute(
                "SELECT DISTINCT source_db FROM provenance WHERE source_db IN ('BIEN', 'LEDA', 'GIFT')"
            ).fetchall()
        finally:
            if own_conn_check:
                _check_conn.close()

        if nc_rows:
            found = {r[0] for r in nc_rows}
            raise RuntimeError(
                "\n"
                "=" * 70 + "\n"
                "LICENSE VIOLATION BLOCKED: NC data detected in core dataset publish.\n"
                "=" * 70 + "\n"
                f"\nThe DuckDB provenance table contains records from NC-licensed\n"
                f"sources: {found}\n\n"
                f"These sources are INCOMPATIBLE with the Proprietary Commercial\n"
                f"License and MUST NOT be published to:\n"
                f"  {core_repo}\n\n"
                f"To publish the extended academic dataset, use:\n"
                f"  publish_to_huggingface(repo_id='foersben/PHIDS-extended-dataset')\n"
                f"Or run: just etl-publish-extended\n" + "=" * 70
            )
        logger.info("License guard OK: no NC sources in provenance. Proceeding with publish.")

    try:
        from huggingface_hub import HfApi
    except ImportError:
        logger.error("huggingface_hub not installed. Run: uv sync --group pipeline")
        return

    token = hf_token or os.environ.get("HF_TOKEN")
    api = HfApi(token=token)

    # Ensure exports are fresh before uploading
    own_conn = conn is None
    if own_conn:
        conn = open_connection(read_only=True)

    try:
        json_path = export_bio_database_json(conn=conn)
        manifest_path = export_manifest_json(conn=conn)
    finally:
        if own_conn:
            conn.close()

    uploads = [
        (str(DB_PATH), "bio_database.duckdb"),
        (str(json_path), "bio_database.json"),
        (str(manifest_path), "manifest.json"),
    ]

    for local_path, remote_name in uploads:
        if not Path(local_path).exists():
            logger.warning("HuggingFace: skipping %s (file not found)", local_path)
            continue
        logger.info("HuggingFace: uploading %s → %s/%s", local_path, repo_id, remote_name)
        api.upload_file(
            path_or_fileobj=local_path,
            path_in_repo=remote_name,
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"chore(etl): update {remote_name}",
        )

    logger.info("HuggingFace: all uploads complete → https://huggingface.co/datasets/%s", repo_id)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _parse_json_field(value: object) -> dict[str, object] | None:
    """Parse a JSON field that may be a string or already-parsed dict.

    Args:
        value: Raw value from DuckDB (string JSON or dict).

    Returns:
        Parsed dict or None if value is None/empty.

    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)  # type: ignore[return-value]
        except json.JSONDecodeError:
            return None
    return None
