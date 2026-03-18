"""Tests for the headless Monte Carlo batch runner.

This test module validates the correctness of :mod:`phids.engine.batch`,
including the :func:`~phids.engine.batch._run_single_headless` pure-function
runner, the statistical aggregation performed by
:func:`~phids.engine.batch.aggregate_batch_telemetry`, and the end-to-end
:class:`~phids.engine.batch.BatchRunner` execution path. Because
:func:`_run_single_headless` invokes Numba JIT compilation on first call, the
tests use minimal grid dimensions (2×2) and short tick counts (3–5) to keep
wall-clock time acceptable in CI. The tests do not exercise the
``ProcessPoolExecutor`` path to avoid subprocess overhead in unit testing;
instead, the aggregation and single-run interfaces are tested in-process via
``asyncio.run`` emulation.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _minimal_scenario() -> dict:
    """Return a JSON-serialisable SimulationConfig dict for a 4×4 grid with one flora and one herbivore."""
    from phids.api.schemas import (
        DietCompatibilityMatrix,
        FloraSpeciesParams,
        HerbivoreSpeciesParams,
        InitialPlantPlacement,
        InitialSwarmPlacement,
        SimulationConfig,
    )

    config = SimulationConfig(
        grid_width=4,
        grid_height=4,
        max_ticks=5,
        num_signals=1,
        num_toxins=1,
        flora_species=[
            FloraSpeciesParams(
                species_id=0,
                name="TestPlant",
                base_energy=10.0,
                max_energy=50.0,
                growth_rate=1.0,
                survival_threshold=1.0,
                reproduction_interval=20,
            )
        ],
        herbivore_species=[
            HerbivoreSpeciesParams(
                species_id=0,
                name="TestBug",
                energy_min=1.0,
                velocity=1,
                consumption_rate=0.5,
            )
        ],
        diet_matrix=DietCompatibilityMatrix(rows=[[True]]),
        initial_plants=[InitialPlantPlacement(species_id=0, x=1, y=1, energy=20.0)],
        initial_swarms=[InitialSwarmPlacement(species_id=0, x=2, y=2, population=3, energy=5.0)],
    )
    return config.model_dump()


class TestRunSingleHeadless:
    """Integration checks for the module-level `_run_single_headless` execution path."""

    def test_returns_nonempty_rows(self) -> None:
        """A minimal headless run returns at least one telemetry row."""
        from phids.engine.batch import _run_single_headless

        rows = _run_single_headless(_minimal_scenario(), max_ticks=3, seed=42)
        assert isinstance(rows, list)
        assert len(rows) >= 1

    def test_tick_sequence_starts_at_zero(self) -> None:
        """Telemetry rows are ordered starting from tick 0."""
        from phids.engine.batch import _run_single_headless

        rows = _run_single_headless(_minimal_scenario(), max_ticks=3, seed=0)
        assert rows[0]["tick"] == 0

    def test_different_seeds_may_differ(self) -> None:
        """Two headless runs with different seeds can produce different outcomes."""
        from phids.engine.batch import _run_single_headless

        rows_a = _run_single_headless(_minimal_scenario(), max_ticks=5, seed=1)
        rows_b = _run_single_headless(_minimal_scenario(), max_ticks=5, seed=99)
        # At minimum, both return non-empty results
        assert len(rows_a) >= 1
        assert len(rows_b) >= 1

    def test_flora_population_field_present(self) -> None:
        """Each telemetry row contains the flora_population scalar field."""
        from phids.engine.batch import _run_single_headless

        rows = _run_single_headless(_minimal_scenario(), max_ticks=3, seed=7)
        for row in rows:
            assert "flora_population" in row
            assert "herbivore_population" in row


class TestAggregateBatchTelemetry:
    """Validates statistical aggregation of Monte Carlo run ensembles."""

    def _make_rows(self, n_ticks: int, flora_val: int, herbivore_val: int) -> list[dict]:
        """Build synthetic uniform telemetry rows for a single run."""
        return [
            {
                "tick": t,
                "flora_population": flora_val,
                "herbivore_population": herbivore_val,
                "total_flora_energy": float(flora_val * 10),
                "plant_pop_by_species": {0: flora_val},
                "swarm_pop_by_species": {0: herbivore_val},
            }
            for t in range(n_ticks)
        ]

    def test_mean_of_identical_runs_equals_value(self) -> None:
        """Aggregate mean equals the constant population when all runs are identical."""
        from phids.engine.batch import aggregate_batch_telemetry

        runs = [self._make_rows(5, 10, 3) for _ in range(4)]
        agg = aggregate_batch_telemetry(runs)
        assert abs(agg["flora_population_mean"][0] - 10.0) < 1e-6
        assert abs(agg["herbivore_population_mean"][0] - 3.0) < 1e-6

    def test_std_of_identical_runs_is_zero(self) -> None:
        """Standard deviation across identical runs is zero for all ticks."""
        from phids.engine.batch import aggregate_batch_telemetry

        runs = [self._make_rows(5, 10, 3) for _ in range(3)]
        agg = aggregate_batch_telemetry(runs)
        for v in agg["flora_population_std"]:
            assert abs(v) < 1e-6

    def test_extinction_probability_all_zero(self) -> None:
        """Extinction probability is 0.0 when no run ever hits flora_population == 0."""
        from phids.engine.batch import aggregate_batch_telemetry

        runs = [self._make_rows(5, 10, 3) for _ in range(4)]
        agg = aggregate_batch_telemetry(runs)
        assert agg["extinction_probability"] == 0.0

    def test_extinction_probability_all_extinct(self) -> None:
        """Extinction probability is 1.0 when every run hits flora_population == 0."""
        from phids.engine.batch import aggregate_batch_telemetry

        runs = [self._make_rows(5, 0, 0) for _ in range(3)]
        agg = aggregate_batch_telemetry(runs)
        assert agg["extinction_probability"] == 1.0

    def test_ticks_aligned_to_minimum(self) -> None:
        """Aggregate ticks are aligned to the shortest run (min-length truncation)."""
        from phids.engine.batch import aggregate_batch_telemetry

        runs = [self._make_rows(3, 5, 2), self._make_rows(5, 5, 2)]
        agg = aggregate_batch_telemetry(runs)
        assert len(agg["ticks"]) == 3

    def test_empty_input_returns_empty(self) -> None:
        """An empty per_run list returns an empty aggregate dict."""
        from phids.engine.batch import aggregate_batch_telemetry

        agg = aggregate_batch_telemetry([])
        assert agg == {}

    def test_per_species_means_computed(self) -> None:
        """Per-species population means are present in the aggregate output."""
        from phids.engine.batch import aggregate_batch_telemetry

        runs = [self._make_rows(4, 8, 2) for _ in range(2)]
        agg = aggregate_batch_telemetry(runs)
        assert "per_flora_pop_mean" in agg
        assert "0" in agg["per_flora_pop_mean"]
        assert abs(agg["per_flora_pop_mean"]["0"][0] - 8.0) < 1e-6

    def test_survival_probability_curve_present(self) -> None:
        """Aggregate output includes per-tick survival fractions across runs."""
        from phids.engine.batch import aggregate_batch_telemetry

        runs = [self._make_rows(4, 8, 2), self._make_rows(4, 8, 2)]
        agg = aggregate_batch_telemetry(runs)
        assert "survival_probability_curve" in agg
        assert agg["survival_probability_curve"] == [1.0, 1.0, 1.0, 1.0]

    def test_survival_probability_curve_monotonic_for_terminal_extinction(self) -> None:
        """Survival curve decreases when a run reaches terminal flora extinction."""
        from phids.engine.batch import aggregate_batch_telemetry

        alive = self._make_rows(4, 6, 2)
        extinct = [
            {
                "tick": 0,
                "flora_population": 6,
                "herbivore_population": 2,
                "total_flora_energy": 60.0,
                "plant_pop_by_species": {0: 6},
                "swarm_pop_by_species": {0: 2},
            },
            {
                "tick": 1,
                "flora_population": 0,
                "herbivore_population": 1,
                "total_flora_energy": 0.0,
                "plant_pop_by_species": {0: 0},
                "swarm_pop_by_species": {0: 1},
            },
            {
                "tick": 2,
                "flora_population": 0,
                "herbivore_population": 1,
                "total_flora_energy": 0.0,
                "plant_pop_by_species": {0: 0},
                "swarm_pop_by_species": {0: 1},
            },
            {
                "tick": 3,
                "flora_population": 0,
                "herbivore_population": 1,
                "total_flora_energy": 0.0,
                "plant_pop_by_species": {0: 0},
                "swarm_pop_by_species": {0: 1},
            },
        ]

        agg = aggregate_batch_telemetry([alive, extinct])
        assert agg["survival_probability_curve"] == [1.0, 0.5, 0.5, 0.5]


def test_sanitize_for_json_replaces_non_finite_values_with_none() -> None:
    """JSON sanitization replaces NaN/Inf values so strict dumps do not fail.

    The batch export path writes aggregate summaries to disk for later browser
    consumption. This regression test verifies that non-finite floating-point
    values are recursively normalized to ``None`` before serialization, so
    ``json.dumps(..., allow_nan=False)`` remains standards-compliant.
    """
    from phids.engine.batch import _sanitize_for_json

    raw = {
        "scalar_nan": float("nan"),
        "nested": {
            "np_nan": np.float64(np.nan),
            "arr": [1.0, float("inf"), float("-inf")],
        },
    }

    sanitized = _sanitize_for_json(raw)
    assert sanitized["scalar_nan"] is None
    assert sanitized["nested"]["np_nan"] is None
    assert sanitized["nested"]["arr"] == [1.0, None, None]

    # Must serialize under strict JSON rules (no NaN/Infinity literals).
    json.dumps(sanitized, allow_nan=False)


def test_run_and_save_delegates_to_single_runner(monkeypatch) -> None:
    """Wrapper delegates argument tuple unpacking to the headless runner."""
    from phids.engine import batch as batch_mod

    expected_rows = [{"tick": 0, "flora_population": 1, "herbivore_population": 0}]

    def _fake_single(_scenario: dict, _max_ticks: int, _seed: int) -> list[dict]:
        return expected_rows

    monkeypatch.setattr(batch_mod, "_run_single_headless", _fake_single)

    rows = batch_mod._run_and_save(({}, 5, 3, "job-a", 0, "/tmp"))
    assert rows == expected_rows


def test_run_single_headless_breaks_when_termination_detected(monkeypatch) -> None:
    """Headless driver exits early when the simulation loop reports termination."""
    from phids.engine import batch as batch_mod
    import phids.engine.loop as loop_mod

    class _TerminatedResult:
        terminated = True

    class _FakeTelemetry:
        _rows = [{"tick": 0, "flora_population": 0, "herbivore_population": 0}]

    class _FakeLoop:
        def __init__(self, _config: object) -> None:
            self.telemetry = _FakeTelemetry()
            self.tick = 1

        async def step(self) -> _TerminatedResult:
            return _TerminatedResult()

    monkeypatch.setattr(loop_mod, "SimulationLoop", _FakeLoop)

    rows = batch_mod._run_single_headless(_minimal_scenario(), max_ticks=5, seed=123)
    assert rows == [{"tick": 0, "flora_population": 0, "herbivore_population": 0}]


def test_execute_batch_handles_success_and_failure_and_writes_strict_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """execute_batch collects mixed future outcomes and persists strict JSON summaries."""
    from phids.engine import batch as batch_mod

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

        def __enter__(self) -> "_FakeExecutor":
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

        def submit(self, _fn: object, _args: object) -> _FakeFuture:
            self._submitted += 1
            if self._submitted == 1:
                return _FakeFuture(
                    payload=[{"tick": 0, "flora_population": 2, "herbivore_population": 1}]
                )
            return _FakeFuture(exc=RuntimeError("worker failed"))

    monkeypatch.setattr(batch_mod.concurrent.futures, "ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(
        batch_mod.concurrent.futures, "as_completed", lambda futures: list(futures.keys())
    )
    monkeypatch.setattr(batch_mod.multiprocessing, "get_context", lambda _method: object())

    # Inject NaN to verify _sanitize_for_json + allow_nan=False output path.
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
        _minimal_scenario(),
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
    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted["flora_population_mean"] == [None]
