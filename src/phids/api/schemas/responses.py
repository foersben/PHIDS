# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""REST API response and request payload schemas.

These models are used exclusively at the HTTP boundary and carry no engine-internal
state. They are never passed into ``SimulationLoop`` construction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from phids.api.schemas.base import StrictBaseModel


class SimulationStatusResponse(StrictBaseModel):
    """Response model for simulation state queries."""

    tick: int
    tick_rate_hz: float
    running: bool
    paused: bool
    terminated: bool
    termination_reason: str | None = None


class WindUpdatePayload(StrictBaseModel):
    """REST payload for dynamically updating wind vectors."""

    wind_x: float
    wind_y: float


class TickRateUpdatePayload(StrictBaseModel):
    """REST payload for dynamically updating live simulation tick speed."""

    tick_rate_hz: float = Field(default=10.0, gt=0.0)


class BatchJobState(StrictBaseModel):
    """Runtime state record for a single Monte Carlo batch simulation job.

    Each batch job corresponds to ``N`` independent simulation runs dispatched
    to a :class:`concurrent.futures.ProcessPoolExecutor`. Progress is tracked as
    completed run count relative to the total, and the final aggregate summary is
    persisted to disk for retrieval via the ledger and view endpoints.

    Attributes:
        job_id: Universally unique identifier assigned at job creation.
        status: Lifecycle state of the job.
        completed: Number of runs that have completed (successfully or not).
        total: Total number of runs requested.
        scenario_name: Display label derived from the source scenario config.
        started_at: ISO-8601 timestamp of job creation.
        finished_at: ISO-8601 timestamp of completion, or ``None`` if pending.
        max_ticks: Maximum tick count per individual run.

    """

    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    completed: int = 0
    total: int = 1
    scenario_name: str = "unnamed"
    started_at: str = ""
    finished_at: str | None = None
    max_ticks: int = 500


class BatchStartPayload(StrictBaseModel):
    """HTTP request payload for initiating a Monte Carlo batch simulation job.

    Encapsulates the simulation scenario and batch execution parameters
    submitted via ``POST /api/batch/start``. The ``scenario`` field accepts a
    complete :class:`SimulationConfig` that overrides the current server-side
    draft, enabling fully reproducible parameterized batch studies.

    Attributes:
        runs: Number of independent simulation runs to execute in parallel.
        max_ticks: Maximum simulation tick count per run.
        scenario_name: Optional display label for the ledger.

    """

    runs: int = Field(default=10, ge=1, le=256, description="Number of parallel Monte Carlo runs.")
    max_ticks: int = Field(default=500, gt=0, description="Maximum ticks per run.")
    scenario_name: str = Field(default="", description="Optional display label for the job ledger.")
