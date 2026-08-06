# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""End-to-end tests for ``BatchRunner.execute_batch`` orchestration.

This module tests the full ``execute_batch`` code path including mixed
future outcomes (success and failure), JSON sanitization of non-finite
aggregates, progress callback invocation, and strict output file persistence.

The ``ProcessPoolExecutor`` is replaced with a deterministic fake via
monkeypatch to avoid subprocess overhead in CI.

MUTATION_TESTING_EXEMPTION: None - orchestration logic is core deterministic
control flow covering executor lifecycle, progress tracking, and file I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def test_execute_batch_handles_success_and_failure_and_writes_strict_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    minimal_scenario: dict,
) -> None:
    """``execute_batch`` collects mixed future outcomes and persists strict JSON summaries.

    Intent:
        Verify the full ``BatchRunner.execute_batch`` path: successful and failing
        futures are both collected; progress is reported per-completed future;
        the aggregate summary is sanitized and written as strict JSON (no NaN/Infinity).

    Preconditions:
        - ProcessPoolExecutor replaced by a fake that returns one success and one failure.
        - aggregate_batch_telemetry patched to inject NaN into the output to exercise
          the ``_sanitize_for_json + allow_nan=False`` output path.
        - Output written to ``tmp_path``.

    Invariants Tested:
        - result.job_id == "jobmix".
        - result.runs == 2.
        - len(result.per_run_telemetry) == 2.
        - progress == [1, 2] (one callback per completed future).
        - Summary file exists at tmp_path / "jobmix_summary.json".
        - persisted["flora_population_mean"] == [None] (NaN sanitized to null).
    """
    from phids.engine.batch import orchestrator as batch_mod

    class _FakeFuture:
        def __init__(self, payload: list[dict] | None = None, exc: Exception | None = None) -> None:
            self._payload = payload
            self._exc = exc

        def result(self) -> list[dict]:
            if self._exc is not None:
                raise self._exc
            return self._payload or []

    class _FakeExecutor:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self._submitted = 0

        def __enter__(self) -> _FakeExecutor:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

        def submit(self, _fn: object, _args: object) -> _FakeFuture:
            self._submitted += 1
            if self._submitted == 1:
                return _FakeFuture(payload=[{"tick": 0, "flora_population": 2, "herbivore_population": 1}])
            return _FakeFuture(exc=RuntimeError("worker failed"))

    monkeypatch.setattr(batch_mod.concurrent.futures, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(batch_mod.concurrent.futures, "as_completed", lambda futures: list(futures.keys()))
    monkeypatch.setattr(batch_mod.multiprocessing, "get_context", lambda _method: object())

    monkeypatch.setattr(
        batch_mod,
        "aggregate_batch_telemetry",
        lambda _runs: {
            "ticks": [0],
            "flora_population_mean": [float("nan")],
            "runs_completed": 2,
        },
    )

    progress: list[int] = []
    runner = batch_mod.BatchRunner()
    result = runner.execute_batch(
        minimal_scenario,
        runs=2,
        max_ticks=3,
        job_id="jobmix",
        output_dir=tmp_path,
        on_progress=progress.append,
    )

    assert result.job_id == "jobmix"
    assert result.runs == 2
    assert len(result.per_run_telemetry) == 2
    assert progress == [1, 2]

    summary_path = tmp_path / "jobmix_summary.json"
    assert summary_path.exists(), f"Expected summary at {summary_path}"

    import json

    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted["flora_population_mean"] == [None]
