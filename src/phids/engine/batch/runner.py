# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Execution wrappers for individual headless simulation runs."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, cast

import numpy as np

if TYPE_CHECKING:
    from phids.engine.batch.types import TelemetryRow

logger = logging.getLogger(__name__)


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

    from phids.api.schemas.simulation import SimulationConfig
    from phids.engine.loop import SimulationLoop

    config = SimulationConfig.model_validate(scenario_dict)
    loop = SimulationLoop(config, disable_replay=True)

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

    This thin wrapper unpacks the argument tuple, calls :func:`_run_single_headless`,
    and persists the replay buffer to disk when ``output_dir`` is provided. Argument
    packing into a single tuple is required because
    :meth:`concurrent.futures.ProcessPoolExecutor.submit` dispatches callables with
    positional arguments, and ``multiprocessing`` serialisation works most reliably
    with top-level callables and simple tuple arguments.

    Args:
        args: Tuple containing the simulation run parameters.
            ``(scenario_dict, max_ticks, seed, job_id, run_index, output_dir_str)``.

    Returns:
        Per-tick telemetry rows for this run.
    """
    scenario_dict, max_ticks, seed, job_id, run_index, _output_dir_str = args
    rows = _run_single_headless(scenario_dict, max_ticks, seed)
    logger.info("Batch run %d/%s complete (seed=%d, rows=%d)", run_index, job_id, seed, len(rows))
    return rows
