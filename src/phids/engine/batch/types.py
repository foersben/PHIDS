# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Data structures and type definitions for batch simulation execution.

This module isolates the core types used for orchestrating Monte Carlo ensembles
and communicating payload structures to external consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

type JSONScalar = bool | int | float | str | None
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
type TelemetryRow = dict[str, object]
type TelemetryRuns = list[list[TelemetryRow]]
type BatchAggregate = dict[str, object]


@dataclass(slots=True, frozen=True)
class BatchExecutionRequest:
    """Validated parameter bundle for a parallel Monte Carlo batch execution.

    Attributes:
        scenario_dict: JSON-serialisable ``SimulationConfig`` representation.
        runs: Number of independent simulation runs to execute.
        max_ticks: Maximum tick count per run.
        job_id: Unique batch job identifier for file naming.
        output_dir: Directory for output files; defaults to ``data/batches``.
        on_progress: Optional callback invoked with completed count as each
            future resolves.
        scenario_name: Optional display label persisted into the summary so
            restored ledgers can retain operator-selected names.
        seed_offset: Starting PRNG seed index for independent run seeds.
    """

    scenario_dict: dict[str, object]
    runs: int
    max_ticks: int
    job_id: str
    output_dir: Path | None = None
    on_progress: Callable[[int], None] | None = None
    scenario_name: str | None = None
    seed_offset: int = 0


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
