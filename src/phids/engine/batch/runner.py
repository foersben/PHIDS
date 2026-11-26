# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Execution wrappers for individual headless simulation runs."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, cast

import numpy as np

from phids.api.schemas.simulation import SimulationConfig
from phids.engine import loop as engine_loop

if TYPE_CHECKING:
    from phids.engine.batch.types import TelemetryRow

logger = logging.getLogger(__name__)


def _run_single_headless(
    scenario_dict: dict[str, object],
    max_ticks: int,
    seed: int,
) -> list[TelemetryRow]:
    """Execute a single deterministic simulation run without WebSocket or replay overhead.

    Why: Batch ensemble throughput depends on eliminating Zarr serialisation and WebSocket locking whilst isolating each replicate PRNG stream inside a picklable top-level worker entry point compatible with ``multiprocessing.spawn``.

    How: The worker seeds both ``random`` and ``numpy.random``, validates ``scenario_dict`` into ``SimulationConfig``, constructs a fresh ``SimulationLoop`` with ``disable_replay=True``, steps synchronously via ``asyncio.run`` until termination or ``max_ticks``, and returns copied telemetry rows.

    Args:
        scenario_dict: JSON-serialisable representation of a :class:`~phids.api.schemas.SimulationConfig` instance.
        max_ticks: Maximum number of simulation ticks to advance.
        seed: Random seed for reproducibility and ensemble diversity.

    Returns:
        list[TelemetryRow]: List of per-tick telemetry row dicts accumulated by :class:`~phids.telemetry.analytics.TelemetryRecorder`.
    """
    random.seed(seed)
    np.random.seed(seed)

    config = SimulationConfig.model_validate(scenario_dict)
    loop = engine_loop.SimulationLoop(config, disable_replay=True)

    async def _advance() -> None:
        """Advance the simulation for max_ticks ticks."""
        for _ in range(max_ticks):
            result = await loop.step()
            if result.terminated:
                break

    asyncio.run(_advance())
    rows: list[TelemetryRow] = [cast("TelemetryRow", dict(row)) for row in loop.telemetry._rows]
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

    This thin wrapper unpacks the argument tuple, calls :func:`_run_single_headless`, and persists the replay buffer to disk when ``output_dir`` is provided. Argument packing into a single tuple is required because :meth:`concurrent.futures.ProcessPoolExecutor.submit` dispatches callables with positional arguments, and ``multiprocessing`` serialisation works most reliably with top-level callables and simple tuple arguments.

    Args:
        args: Tuple containing the simulation run parameters. ``(scenario_dict, max_ticks, seed, job_id, run_index, output_dir_str)``.

    Returns:
        Per-tick telemetry rows for this run.
    """
    scenario_dict, max_ticks, seed, job_id, run_index, _output_dir_str = args
    rows = _run_single_headless(scenario_dict, max_ticks, seed)
    logger.info("Batch run %d/%s complete (seed=%d, rows=%d)", run_index, job_id, seed, len(rows))
    return rows
