# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Statistical aggregation routines for batch telemetry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from phids.engine.batch.utils import _coerce_float, _coerce_int, _get_int_keys, _species_count

if TYPE_CHECKING:
    from phids.engine.batch.types import BatchAggregate, TelemetryRow, TelemetryRuns

logger = logging.getLogger(__name__)


def _pad_telemetry_runs(per_run: TelemetryRuns, max_len: int) -> list[list[TelemetryRow]]:
    """Pad run telemetry with terminal data to match max_len.

    Args:
        per_run: The per-run telemetry.
        max_len: The maximum length.

    Returns:
        The padded per-run telemetry.
    """
    aligned: list[list[TelemetryRow]] = []
    for rows in per_run:
        if len(rows) < max_len:
            pad_count = max_len - len(rows)
            last: TelemetryRow = dict(rows[-1]) if rows else {}
            last["death_herbivore_feeding"] = 0.0
            last["death_defense_maintenance"] = 0.0
            aligned.append(rows + [last] * pad_count)
        else:
            aligned.append(rows)
    return aligned


def _extract_scalar_matrix(aligned: list[list[TelemetryRow]], key: str) -> np.ndarray:
    """Extract a 2D matrix of scalars from aligned telemetry runs.

    Args:
        aligned: The aligned per-run telemetry.
        key: The key to extract.

    Returns:
        The extracted matrix.
    """
    return np.array(
        [[_coerce_float(r.get(key, 0.0)) for r in run] for run in aligned],
        dtype=np.float64,
    )


def _extract_species_matrix(aligned: list[list[TelemetryRow]], field: str, species_id: int) -> np.ndarray:
    """Extract a 2D matrix of specific species counts from aligned telemetry runs.

    Args:
        aligned: The aligned per-run telemetry.
        field: The field name.
        species_id: The species identifier.

    Returns:
        The extracted matrix.
    """
    return np.array(
        [[_species_count(r, field, species_id) for r in run] for run in aligned],
        dtype=np.float64,
    )


def _stack_scalar_aggregates(aligned: list[list[TelemetryRow]]) -> dict[str, object]:
    """Stack scalar population and energy metrics into NumPy arrays.

    Args:
        aligned: The aligned per-run telemetry.

    Returns:
        The stacked scalar aggregates.
    """
    flora_pop = _extract_scalar_matrix(aligned, "flora_population")
    herb_pop = _extract_scalar_matrix(aligned, "herbivore_population")
    flora_energy = _extract_scalar_matrix(aligned, "total_flora_energy")
    death_herbivore = _extract_scalar_matrix(aligned, "death_herbivore_feeding")
    death_defense = _extract_scalar_matrix(aligned, "death_defense_maintenance")
    death_starvation = _extract_scalar_matrix(aligned, "death_starvation")

    # Extinction probability: fraction of runs where flora hit zero at any tick
    extinction_count = int(np.sum(np.any(flora_pop == 0, axis=1)))
    extinction_probability = extinction_count / len(aligned) if aligned else 0.0
    survival_probability_curve = np.mean(flora_pop > 0, axis=0).tolist() if aligned else []

    return {
        "flora_population_mean": flora_pop.mean(axis=0).tolist() if aligned else [],
        "flora_population_std": flora_pop.std(axis=0).tolist() if aligned else [],
        "herbivore_population_mean": herb_pop.mean(axis=0).tolist() if aligned else [],
        "herbivore_population_std": herb_pop.std(axis=0).tolist() if aligned else [],
        "total_flora_energy_mean": flora_energy.mean(axis=0).tolist() if aligned else [],
        "total_flora_energy_std": flora_energy.std(axis=0).tolist() if aligned else [],
        "death_herbivore_feeding_mean": death_herbivore.mean(axis=0).tolist() if aligned else [],
        "death_defense_maintenance_mean": death_defense.mean(axis=0).tolist() if aligned else [],
        "death_starvation_mean": death_starvation.mean(axis=0).tolist() if aligned else [],
        "extinction_probability": extinction_probability,
        "survival_probability_curve": survival_probability_curve,
    }


def _extract_species_ids(aligned: list[list[TelemetryRow]]) -> tuple[set[int], set[int]]:
    """Collect all unique flora and herbivore species identifiers seen across runs.

    Args:
        aligned: The aligned per-run telemetry.

    Returns:
        A tuple containing the set of flora species identifiers and the set of herbivore species identifiers.
    """
    all_flora_ids: set[int] = set()
    all_herb_ids: set[int] = set()
    for run in aligned:
        for row in run:
            all_flora_ids.update(_get_int_keys(row.get("plant_pop_by_species", {})))
            all_herb_ids.update(_get_int_keys(row.get("swarm_pop_by_species", {})))
    return all_flora_ids, all_herb_ids


def _compute_species_aggregates(
    aligned: list[list[TelemetryRow]],
    all_flora_ids: set[int],
    all_herb_ids: set[int],
) -> dict[str, dict[str, list[float]]]:
    """Compute mean and std dev for individual tracked species over the batch.

    Args:
        aligned: The aligned per-run telemetry.
        all_flora_ids: The set of flora species identifiers.
        all_herb_ids: The set of herbivore species identifiers.

    Returns:
        The computed species aggregates.
    """
    per_flora_pop_mean: dict[int, list[float]] = {}
    per_flora_pop_std: dict[int, list[float]] = {}
    for fid in sorted(all_flora_ids):
        arr = _extract_species_matrix(aligned, "plant_pop_by_species", fid)
        per_flora_pop_mean[fid] = arr.mean(axis=0).tolist()
        per_flora_pop_std[fid] = arr.std(axis=0).tolist()

    per_herb_pop_mean: dict[int, list[float]] = {}
    per_herb_pop_std: dict[int, list[float]] = {}
    for pid in sorted(all_herb_ids):
        arr = _extract_species_matrix(aligned, "swarm_pop_by_species", pid)
        per_herb_pop_mean[pid] = arr.mean(axis=0).tolist()
        per_herb_pop_std[pid] = arr.std(axis=0).tolist()

    return {
        "per_flora_pop_mean": {str(k): v for k, v in per_flora_pop_mean.items()},
        "per_flora_pop_std": {str(k): v for k, v in per_flora_pop_std.items()},
        "per_herbivore_pop_mean": {str(k): v for k, v in per_herb_pop_mean.items()},
        "per_herbivore_pop_std": {str(k): v for k, v in per_herb_pop_std.items()},
    }


def aggregate_batch_telemetry(
    per_run: TelemetryRuns,
) -> BatchAggregate:
    """Compute per-tick statistical summaries across an ensemble of simulation runs.

    Aligns all runs to the minimum tick count observed in the ensemble (to handle
    early-termination runs without padding), then stacks scalar population and
    energy metrics into NumPy arrays for vectorised mean and standard deviation
    computation. Per-species populations are similarly aggregated where the union
    of all species identifiers seen across all runs is used as the index.

    The extinction probability is estimated as the fraction of runs in which the
    total flora population reached zero at any tick, providing a coarse measure of
    ecosystem collapse risk under the configured parameter regime.
    A per-tick survival curve is also computed as the fraction of runs that retain
    strictly positive flora population at each aligned tick.

    Args:
        per_run: List of per-run row lists, each produced by :func:`_run_single_headless`.

    Returns:
        BatchAggregate: Aggregate summary containing mean, std dev, and extinction metrics.
    """
    if not per_run:
        return {}

    max_len = max(len(rows) for rows in per_run)
    longest_run = max(per_run, key=len)
    ticks = [_coerce_int(r.get("tick", 0)) for r in longest_run]

    aligned = _pad_telemetry_runs(per_run, max_len)
    scalars = _stack_scalar_aggregates(aligned)
    all_flora_ids, all_herb_ids = _extract_species_ids(aligned)
    species_aggs = _compute_species_aggregates(aligned, all_flora_ids, all_herb_ids)

    result: BatchAggregate = {
        "ticks": ticks,
        "runs_completed": len(per_run),
        # Unpack scalars
        **scalars,
        # Unpack species aggs
        **species_aggs,
    }

    logger.info(
        "Batch aggregation complete (runs=%d, max_len=%d, extinction_prob=%.3f)",
        len(per_run),
        max_len,
        scalars["extinction_probability"],
    )
    return result
