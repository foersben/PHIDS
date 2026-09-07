# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Headless Monte Carlo batch processing engine for PHIDS ecosystem simulations.

This package provides components to execute and aggregate ensembles of deterministic
simulation runs in parallel, facilitating Monte Carlo estimation and stochastic modeling.
"""

from phids.engine.batch.aggregation import aggregate_batch_telemetry
from phids.engine.batch.orchestrator import BatchRunner
from phids.engine.batch.runner import _run_and_save, _run_single_headless
from phids.engine.batch.types import (
    BatchAggregate,
    BatchResult,
    TelemetryRow,
    TelemetryRuns,
)

__all__ = [
    "BatchAggregate",
    "BatchResult",
    "BatchRunner",
    "TelemetryRow",
    "TelemetryRuns",
    "_run_and_save",
    "_run_single_headless",
    "aggregate_batch_telemetry",
]
