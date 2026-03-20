"""Headless Monte Carlo batch processing engine for PHIDS ecosystem simulations.

This module implements the :class:`BatchRunner`, which executes a configurable number of
deterministic simulation runs in parallel using a :class:`concurrent.futures.ProcessPoolExecutor`
isolated from the FastAPI event loop. Each run is seeded with a unique integer so that,
while the per-tick mechanics remain deterministic for a given seed, population-level
stochasticity (e.g., probabilistic flow-field navigation, natal dispersal) produces
meaningfully varied trajectories across the ensemble, enabling Monte Carlo estimation of
extinction probabilities and Lotka-Volterra orbital stability.

The module-level function :func:`_run_single_headless` is intentionally not a class
method. Module-level callability is a strict requirement for :mod:`multiprocessing`
serialisation via ``pickle`` when using the ``spawn`` start method, which is mandatory on
platforms where forking a process that has loaded Numba JIT-compiled functions would cause
undefined behaviour. Each worker process independently JIT-compiles the flow-field kernel
on first invocation; subsequent runs within the same worker process reuse the cached
native code.

Statistical aggregation is performed by :func:`aggregate_batch_telemetry`, which aligns
the per-run telemetry row lists to the minimum observed tick count, stacks them into NumPy
arrays, and computes per-tick mean and standard deviation for flora population, herbivore
population, and per-species sub-populations. The resulting ``aggregate`` dictionary is
serialised to ``{output_dir}/{job_id}_summary.json`` for persistent retrieval and
Chart.js rendering of confidence bands in the batch dashboard.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import math
import multiprocessing
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TypeAlias, cast

import numpy as np

logger = logging.getLogger(__name__)

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
TelemetryRow: TypeAlias = dict[str, object]
TelemetryRuns: TypeAlias = list[list[TelemetryRow]]
BatchAggregate: TypeAlias = dict[str, object]


def _coerce_int(value: object) -> int:
    """Convert telemetry scalar to int with stable fallback semantics."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _coerce_float(value: object) -> float:
    """Convert telemetry scalar to float with stable fallback semantics."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _species_count(row: TelemetryRow, field: str, species_id: int) -> float:
    """Read one species count from a telemetry row field map with numeric fallback."""
    raw_map = row.get(field, {})
    if not isinstance(raw_map, dict):
        return 0.0
    return _coerce_float(raw_map.get(species_id, 0.0))


# ---------------------------------------------------------------------------
# Default output directory
# ---------------------------------------------------------------------------
_DEFAULT_BATCH_DIR = Path("data") / "batches"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class BatchResult:
    """Aggregated result of a completed batch simulation run.

    Attributes:
        job_id: Unique identifier for the batch job.
        runs: Number of individual simulation runs completed.
        per_run_telemetry: Nested list of raw telemetry row dicts per run.
        aggregate: Statistical summary produced by
            :func:`aggregate_batch_telemetry`.
    """

    job_id: str
    runs: int
    per_run_telemetry: TelemetryRuns = field(default_factory=list)
    aggregate: BatchAggregate = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pure headless simulation runner (module-level for pickle compatibility)
# ---------------------------------------------------------------------------


def _run_single_headless(
    scenario_dict: dict[str, object],
    max_ticks: int,
    seed: int,
) -> list[TelemetryRow]:
    """Execute a single deterministic simulation run without WebSocket or replay overhead.

    This function is the fundamental unit of computation for the batch engine.
    It instantiates a fresh :class:`~phids.api.schemas.SimulationConfig` from
    ``scenario_dict``, constructs independent :class:`~phids.engine.core.ecs.ECSWorld`
    and :class:`~phids.engine.core.biotope.GridEnvironment` objects, and advances
    the simulation through all five ordered phases (flow field, lifecycle,
    interaction, signaling, telemetry) for ``max_ticks`` steps. The ``seed``
    argument is applied to both :mod:`random` and :mod:`numpy.random` before
    simulation begins, ensuring reproducible trajectories for a given seed while
    enabling ensemble diversity across seeds.

    The function is intentionally module-level (not a class method) to satisfy
    ``multiprocessing.spawn`` picklability requirements. No asyncio infrastructure
    is created in this path; the :class:`~phids.engine.loop.SimulationLoop` is
    driven synchronously by calling ``asyncio.run`` within this worker process's
    own event loop.

    Args:
        scenario_dict: JSON-serialisable representation of a
            :class:`~phids.api.schemas.SimulationConfig` instance.
        max_ticks: Maximum number of simulation ticks to advance.
        seed: Random seed for reproducibility and ensemble diversity.

    Returns:
        list[TelemetryRow]: List of per-tick telemetry row dicts accumulated by
        :class:`~phids.telemetry.analytics.TelemetryRecorder`.
    """
    random.seed(seed)
    np.random.seed(seed)

    from phids.api.schemas import SimulationConfig
    from phids.engine.loop import SimulationLoop

    config = SimulationConfig.model_validate(scenario_dict)
    loop = SimulationLoop(config)

    async def _advance() -> None:
        for _ in range(max_ticks):
            result = await loop.step()
            if result.terminated:
                break

    asyncio.run(_advance())
    rows: list[TelemetryRow] = [cast(TelemetryRow, dict(row)) for row in loop.telemetry._rows]
    logger.debug(
        "Headless run complete (seed=%d, ticks=%d, rows=%d)",
        seed,
        loop.tick,
        len(rows),
    )
    return rows


def _run_and_save(
    args: tuple[dict[str, object], int, int, str, int, str],
) -> list[TelemetryRow]:
    """Execute one headless run, optionally save replay, and return telemetry rows.

    This thin wrapper unpacks the argument tuple, calls :func:`_run_single_headless`,
    and persists the replay buffer to disk when ``output_dir`` is provided. Argument
    packing into a single tuple is required because
    :meth:`concurrent.futures.ProcessPoolExecutor.submit` dispatches callables with
    positional arguments, and ``multiprocessing`` serialisation works most reliably
    with top-level callables and simple tuple arguments.

    Args:
        args: Tuple of
            ``(scenario_dict, max_ticks, seed, job_id, run_index, output_dir_str)``.

    Returns:
        list[TelemetryRow]: Per-tick telemetry rows for this run.
    """
    scenario_dict, max_ticks, seed, job_id, run_index, output_dir_str = args
    rows = _run_single_headless(scenario_dict, max_ticks, seed)
    logger.info("Batch run %d/%s complete (seed=%d, rows=%d)", run_index, job_id, seed, len(rows))
    return rows


# ---------------------------------------------------------------------------
# Statistical aggregation
# ---------------------------------------------------------------------------


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
        per_run: List of per-run row lists, each produced by
            :func:`_run_single_headless`.

    Returns:
        BatchAggregate: Aggregate summary with keys ``ticks``,
        ``flora_population_mean``, ``flora_population_std``,
        ``herbivore_population_mean``, ``herbivore_population_std``,
        ``total_flora_energy_mean``, ``total_flora_energy_std``,
        ``extinction_probability``, ``runs_completed``,
        ``survival_probability_curve``,
        ``per_flora_pop_mean``, ``per_flora_pop_std``,
        ``per_herbivore_pop_mean``, ``per_herbivore_pop_std``.
    """
    if not per_run:
        return {}

    # Align to minimum length to handle early termination
    min_len = min(len(rows) for rows in per_run)
    aligned = [rows[:min_len] for rows in per_run]
    ticks = [_coerce_int(r.get("tick", 0)) for r in aligned[0]]

    # Stack aggregate scalar columns
    flora_pop = np.array(
        [[_coerce_float(r.get("flora_population", 0.0)) for r in run] for run in aligned],
        dtype=np.float64,
    )
    herb_pop = np.array(
        [[_coerce_float(r.get("herbivore_population", 0.0)) for r in run] for run in aligned],
        dtype=np.float64,
    )
    flora_energy = np.array(
        [[_coerce_float(r.get("total_flora_energy", 0.0)) for r in run] for run in aligned],
        dtype=np.float64,
    )

    # Extinction probability: fraction of runs where flora hit zero at any tick
    extinction_count = int(np.sum(np.any(flora_pop == 0, axis=1)))
    extinction_probability = extinction_count / len(per_run)
    survival_probability_curve = np.mean(flora_pop > 0, axis=0).tolist()

    # Collect all per-species ids seen
    all_flora_ids: set[int] = set()
    all_herb_ids: set[int] = set()
    for run in aligned:
        for row in run:
            flora_map = row.get("plant_pop_by_species", {})
            herb_map = row.get("swarm_pop_by_species", {})
            if isinstance(flora_map, dict):
                all_flora_ids.update(k for k in flora_map.keys() if isinstance(k, int))
            if isinstance(herb_map, dict):
                all_herb_ids.update(k for k in herb_map.keys() if isinstance(k, int))

    per_flora_pop_mean: dict[int, list[float]] = {}
    per_flora_pop_std: dict[int, list[float]] = {}
    for fid in sorted(all_flora_ids):
        arr = np.array(
            [[_species_count(r, "plant_pop_by_species", fid) for r in run] for run in aligned],
            dtype=np.float64,
        )
        per_flora_pop_mean[fid] = arr.mean(axis=0).tolist()
        per_flora_pop_std[fid] = arr.std(axis=0).tolist()

    per_herb_pop_mean: dict[int, list[float]] = {}
    per_herb_pop_std: dict[int, list[float]] = {}
    for pid in sorted(all_herb_ids):
        arr = np.array(
            [[_species_count(r, "swarm_pop_by_species", pid) for r in run] for run in aligned],
            dtype=np.float64,
        )
        per_herb_pop_mean[pid] = arr.mean(axis=0).tolist()
        per_herb_pop_std[pid] = arr.std(axis=0).tolist()

    result: BatchAggregate = {
        "ticks": ticks,
        "flora_population_mean": flora_pop.mean(axis=0).tolist(),
        "flora_population_std": flora_pop.std(axis=0).tolist(),
        "herbivore_population_mean": herb_pop.mean(axis=0).tolist(),
        "herbivore_population_std": herb_pop.std(axis=0).tolist(),
        "total_flora_energy_mean": flora_energy.mean(axis=0).tolist(),
        "total_flora_energy_std": flora_energy.std(axis=0).tolist(),
        "extinction_probability": extinction_probability,
        "survival_probability_curve": survival_probability_curve,
        "runs_completed": len(per_run),
        "per_flora_pop_mean": {str(k): v for k, v in per_flora_pop_mean.items()},
        "per_flora_pop_std": {str(k): v for k, v in per_flora_pop_std.items()},
        "per_herbivore_pop_mean": {str(k): v for k, v in per_herb_pop_mean.items()},
        "per_herbivore_pop_std": {str(k): v for k, v in per_herb_pop_std.items()},
    }
    logger.info(
        "Batch aggregation complete (runs=%d, min_len=%d, extinction_prob=%.3f)",
        len(per_run),
        min_len,
        extinction_probability,
    )
    return result


def _sanitize_for_json(value: object) -> object:
    """Recursively coerce aggregate values into strict JSON-compatible scalars.

    This sanitiser replaces all non-finite floating-point values (``NaN``,
    ``+inf``, ``-inf``) with ``None`` so downstream ``json.dump(...,
    allow_nan=False)`` remains standards-compliant and browser ``JSON.parse``
    never encounters invalid numeric tokens.

    Args:
        value: Arbitrary Python/NumPy value.

    Returns:
        object: JSON-safe structure preserving the original shape.
    """
    if isinstance(value, dict):
        return {str(k): _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_json(v) for v in value]
    if isinstance(value, np.generic):
        return _sanitize_for_json(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


# ---------------------------------------------------------------------------
# BatchRunner class
# ---------------------------------------------------------------------------


class BatchRunner:
    """Orchestrate parallel Monte Carlo simulation runs using ProcessPoolExecutor.

    The :class:`BatchRunner` dispatches :func:`_run_and_save` to a
    ``ProcessPoolExecutor`` configured with the ``spawn`` multiprocessing
    context to avoid Numba/asyncio fork conflicts. Progress is reported via
    an optional ``on_progress`` callback invoked in the main process after
    each completed future, enabling the FastAPI background task to update the
    ``BatchJobState`` without blocking the event loop.

    Aggregate results are written to ``{output_dir}/{job_id}_summary.json``
    upon completion of all runs, making them available for retrieval via the
    ``GET /api/batch/view/{job_id}`` endpoint.
    """

    def execute_batch(
        self,
        scenario_dict: dict[str, object],
        runs: int,
        max_ticks: int,
        job_id: str,
        output_dir: Path | None = None,
        on_progress: Callable[[int], None] | None = None,
        scenario_name: str | None = None,
    ) -> BatchResult:
        """Execute ``runs`` independent simulation trajectories in parallel.

        Dispatches all runs to a :class:`concurrent.futures.ProcessPoolExecutor`
        using the ``spawn`` start method, collects telemetry as futures complete,
        and computes statistical aggregates. The summary JSON is written to
        ``{output_dir}/{job_id}_summary.json``.

        Args:
            scenario_dict: JSON-serialisable ``SimulationConfig`` representation.
            runs: Number of independent simulation runs to execute.
            max_ticks: Maximum tick count per run.
            job_id: Unique batch job identifier for file naming.
            output_dir: Directory for output files; defaults to ``data/batches``.
            on_progress: Optional callback invoked with completed count as each
                future resolves.
            scenario_name: Optional display label persisted into the summary so
                restored ledgers can retain operator-selected names.

        Returns:
            BatchResult: Completed result with all per-run telemetry and aggregate.
        """
        save_dir = output_dir or _DEFAULT_BATCH_DIR
        save_dir.mkdir(parents=True, exist_ok=True)

        max_workers = min(runs, os.cpu_count() or 1)
        mp_ctx = multiprocessing.get_context("spawn")
        per_run_telemetry: TelemetryRuns = []
        completed = 0

        logger.info(
            "Batch job %s starting (runs=%d, max_ticks=%d, workers=%d)",
            job_id,
            runs,
            max_ticks,
            max_workers,
        )

        args_list = [
            (scenario_dict, max_ticks, seed, job_id, idx, str(save_dir))
            for idx, seed in enumerate(range(runs))
        ]

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=max_workers, mp_context=mp_ctx
        ) as executor:
            futures = {executor.submit(_run_and_save, args): i for i, args in enumerate(args_list)}
            for future in concurrent.futures.as_completed(futures):
                try:
                    rows = future.result()
                    per_run_telemetry.append(rows)
                except Exception:
                    logger.exception("Batch run %s failed", futures[future])
                    per_run_telemetry.append([])

                completed += 1
                if on_progress is not None:
                    on_progress(completed)

        aggregate = aggregate_batch_telemetry(per_run_telemetry)
        persisted_scenario_name = (
            scenario_name or str(scenario_dict.get("scenario_name", ""))
        ).strip()
        aggregate["scenario_name"] = persisted_scenario_name or "unnamed"
        aggregate = cast(BatchAggregate, _sanitize_for_json(aggregate))

        summary_path = save_dir / f"{job_id}_summary.json"
        with summary_path.open("w", encoding="utf-8") as fp:
            json.dump(aggregate, fp, allow_nan=False)
        logger.info("Batch job %s complete; summary written to %s", job_id, summary_path)

        return BatchResult(
            job_id=job_id,
            runs=runs,
            per_run_telemetry=per_run_telemetry,
            aggregate=aggregate,
        )
