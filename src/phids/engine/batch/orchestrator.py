# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Orchestration of parallel Monte Carlo batch simulations.

This module implements the :class:`BatchRunner`, which manages the parallel execution of headless simulation runs using a ProcessPoolExecutor.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import multiprocessing
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

from phids.engine.batch.aggregation import aggregate_batch_telemetry
from phids.engine.batch.runner import _run_and_save
from phids.engine.batch.types import BatchExecutionRequest, BatchResult
from phids.engine.batch.utils import _sanitize_for_json

if TYPE_CHECKING:
    from phids.engine.batch.types import BatchAggregate, TelemetryRuns

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default output directory
# ---------------------------------------------------------------------------
_DEFAULT_BATCH_DIR = Path("data") / "batches"


def _init_batch_worker() -> None:
    """Initialize process environment for batch Monte Carlo worker process.

    Enforces single-threaded Numba execution per worker process to prevent thread oversubscription across process pool workers.
    """
    os.environ["NUMBA_NUM_THREADS"] = "1"


# ---------------------------------------------------------------------------
# BatchRunner class
# ---------------------------------------------------------------------------


class BatchRunner:
    """Orchestrate parallel Monte Carlo simulation runs using ProcessPoolExecutor.

    The :class:`BatchRunner` dispatches :func:`_run_and_save` to a ``ProcessPoolExecutor`` configured with the ``spawn`` multiprocessing context to avoid Numba/asyncio fork conflicts. Progress is reported via an optional ``on_progress`` callback invoked in the main process after each completed future, enabling the FastAPI background task to update the ``BatchJobState`` without blocking the event loop.

    Aggregate results are written to ``{output_dir}/{job_id}_summary.json`` upon completion of all runs, making them available for retrieval via the ``GET /api/batch/view/{job_id}`` endpoint.
    """

    def execute_batch(
        self,
        request: BatchExecutionRequest,
    ) -> BatchResult:
        """Execute ``request.runs`` independent simulation trajectories in parallel.

        Dispatches all runs to a :class:`concurrent.futures.ProcessPoolExecutor` using the ``spawn`` start method, collects telemetry as futures complete, and computes statistical aggregates. The summary JSON is written to ``{output_dir}/{job_id}_summary.json``.

        Args:
            request: Frozen batch execution configuration bundle.

        Returns:
            Completed result with all per-run telemetry and aggregate.
        """
        scenario_dict = request.scenario_dict
        runs = request.runs
        max_ticks = request.max_ticks
        job_id = request.job_id
        save_dir = request.output_dir or _DEFAULT_BATCH_DIR
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
            for idx, seed in enumerate(range(request.seed_offset, request.seed_offset + runs))
        ]

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=max_workers, mp_context=mp_ctx, initializer=_init_batch_worker
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
                if request.on_progress is not None:
                    request.on_progress(completed)

        aggregate = aggregate_batch_telemetry(per_run_telemetry)
        persisted_scenario_name = (request.scenario_name or str(scenario_dict.get("scenario_name", ""))).strip()
        aggregate["scenario_name"] = persisted_scenario_name or "unnamed"
        aggregate = cast("BatchAggregate", _sanitize_for_json(aggregate))

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
