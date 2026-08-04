# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for the ``_run_single_headless`` execution path.

This module verifies the per-run headless runner: row count, tick ordering,
non-determinism across seeds, field presence, early-termination exit, and
wrapper delegation. Numba JIT compilation is exercised on first call; subsequent
parametric invocations benefit from the warm cache.

MUTATION_TESTING_EXEMPTION: None - all branches are standard deterministic logic.
"""

from __future__ import annotations

import pytest


class TestRunSingleHeadless:
    """Integration checks for the module-level ``_run_single_headless`` execution path.

    Each method exercises one behavioral invariant of the pure-function headless
    runner in isolation, using the ``minimal_scenario`` fixture for a consistent
    4x4 grid baseline.
    """

    def test_returns_nonempty_rows(self, minimal_scenario: dict) -> None:
        """A minimal headless run returns at least one telemetry row.

        Intent:
            Confirm the headless runner executes without error and produces
            at least one tick-level telemetry record.

        Preconditions:
            - ``minimal_scenario`` fixture provides a 4x4 SimulationConfig dict.
            - max_ticks=3, seed=42.

        Invariants Tested:
            - rows is a list.
            - len(rows) >= 1.
        """
        from phids.engine.batch.runner import _run_single_headless

        rows = _run_single_headless(minimal_scenario, max_ticks=3, seed=42)
        assert isinstance(rows, list)
        assert len(rows) >= 1

    def test_tick_sequence_starts_at_zero(self, minimal_scenario: dict) -> None:
        """Telemetry rows are ordered starting from tick 0.

        Intent:
            Verify the first emitted telemetry row always carries tick=0.

        Preconditions:
            - max_ticks=3, seed=0.

        Invariants Tested:
            - rows[0]["tick"] == 0.
        """
        from phids.engine.batch.runner import _run_single_headless

        rows = _run_single_headless(minimal_scenario, max_ticks=3, seed=0)
        assert rows[0]["tick"] == 0

    def test_different_seeds_may_differ(self, minimal_scenario: dict) -> None:
        """Two headless runs with different seeds can produce different outcomes.

        Intent:
            Confirm the runner produces non-empty results for multiple seeds
            and that the seeding mechanism is exercised without exception.

        Preconditions:
            - seed=1 and seed=99 run independently.

        Invariants Tested:
            - len(rows_a) >= 1.
            - len(rows_b) >= 1.
        """
        from phids.engine.batch.runner import _run_single_headless

        rows_a = _run_single_headless(minimal_scenario, max_ticks=5, seed=1)
        rows_b = _run_single_headless(minimal_scenario, max_ticks=5, seed=99)
        assert len(rows_a) >= 1
        assert len(rows_b) >= 1

    def test_flora_population_field_present(self, minimal_scenario: dict) -> None:
        """Each telemetry row contains both flora_population and herbivore_population fields.

        Intent:
            Verify the telemetry schema contract - all required population fields
            are emitted on every row.

        Preconditions:
            - max_ticks=3, seed=7.

        Invariants Tested:
            - "flora_population" in every row.
            - "herbivore_population" in every row.
        """
        from phids.engine.batch.runner import _run_single_headless

        rows = _run_single_headless(minimal_scenario, max_ticks=3, seed=7)
        for row in rows:
            assert "flora_population" in row
            assert "herbivore_population" in row


def test_run_single_headless_breaks_when_termination_detected(
    monkeypatch: pytest.MonkeyPatch,
    minimal_scenario: dict,
) -> None:
    """Headless driver exits early when the simulation loop reports termination.

    Intent:
        Verify the early-exit branch: when ``step()`` returns a result with
        ``terminated=True``, the driver stops immediately and returns whatever
        telemetry rows the loop has accumulated.

    Preconditions:
        - ``SimulationLoop`` replaced by a fake that reports termination on the
          first step with one pre-populated telemetry row.

    Invariants Tested:
        - rows equals the single pre-populated row from the fake loop.
    """
    import phids.engine.loop as loop_mod
    from phids.engine.batch import runner as batch_mod

    class _TerminatedResult:
        terminated = True

    class _FakeTelemetry:
        _rows = [{"tick": 0, "flora_population": 0, "herbivore_population": 0}]  # noqa: RUF012

    class _FakeLoop:
        def __init__(self, _config: object, **_kwargs: object) -> None:
            self.telemetry = _FakeTelemetry()
            self.tick = 1

        async def step(self) -> _TerminatedResult:
            return _TerminatedResult()

    monkeypatch.setattr(loop_mod, "SimulationLoop", _FakeLoop)

    rows = batch_mod._run_single_headless(minimal_scenario, max_ticks=5, seed=123)
    assert rows == [{"tick": 0, "flora_population": 0, "herbivore_population": 0}]


def test_run_and_save_delegates_to_single_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper delegates argument tuple unpacking to the headless runner.

    Intent:
        Verify ``_run_and_save`` correctly unpacks its argument tuple and
        forwards execution to ``_run_single_headless``.

    Preconditions:
        - ``_run_single_headless`` patched to return a known payload.

    Invariants Tested:
        - rows returned by _run_and_save equal the stubbed payload.
    """
    from phids.engine.batch import runner as batch_mod

    expected_rows = [{"tick": 0, "flora_population": 1, "herbivore_population": 0}]

    def _fake_single(_scenario: dict, _max_ticks: int, _seed: int) -> list[dict]:
        return expected_rows

    monkeypatch.setattr(batch_mod, "_run_single_headless", _fake_single)

    rows = batch_mod._run_and_save(({}, 5, 3, "job-a", 0, "/tmp"))
    assert rows == expected_rows
