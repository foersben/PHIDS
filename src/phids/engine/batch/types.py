# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Data structures and type definitions for batch simulation execution.

This module isolates the core types used for orchestrating Monte Carlo ensembles
and communicating payload structures to external consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

type JSONScalar = None | bool | int | float | str
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
type TelemetryRow = dict[str, object]
type TelemetryRuns = list[list[TelemetryRow]]
type BatchAggregate = dict[str, object]


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
