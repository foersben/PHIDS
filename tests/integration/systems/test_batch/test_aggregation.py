# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Validates statistical aggregation of Monte Carlo run ensembles.

This module verifies ``aggregate_batch_telemetry`` and the ``_sanitize_for_json``
helper via synthetic uniform telemetry rows. Covers mean/std computation,
extinction probability, tick-length padding, per-species means, survival
probability curves, and non-finite value sanitization.

MUTATION_TESTING_EXEMPTION: None - all aggregation paths are deterministic core logic.
"""

from __future__ import annotations

import json

import numpy as np


def _make_rows(n_ticks: int, flora_val: int, herbivore_val: int) -> list[dict]:
    """Build synthetic uniform telemetry rows for a single run.

    Args:
        n_ticks: Number of ticks to generate.
        flora_val: Constant flora_population value per tick.
        herbivore_val: Constant herbivore_population value per tick.

    Returns:
        A list of tick-level telemetry row dicts.
    """
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


class TestAggregateBatchTelemetry:
    """Validates statistical aggregation of Monte Carlo run ensembles.

    All tests use synthetic constant-valued telemetry rows to allow
    closed-form expected value calculation.
    """

    def test_mean_of_identical_runs_equals_value(self) -> None:
        """Aggregate mean equals the constant population when all runs are identical.

        Intent:
            Verify the mean aggregation collapses to the constant value when
            all runs produce the same telemetry.

        Preconditions:
            - 4 runs, each with 5 ticks, flora_population=10, herbivore_population=3.

        Invariants Tested:
            - flora_population_mean[0] == 10.0.
            - herbivore_population_mean[0] == 3.0.
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        runs = [_make_rows(5, 10, 3) for _ in range(4)]
        agg = aggregate_batch_telemetry(runs)
        assert abs(agg["flora_population_mean"][0] - 10.0) < 1e-6
        assert abs(agg["herbivore_population_mean"][0] - 3.0) < 1e-6

    def test_std_of_identical_runs_is_zero(self) -> None:
        """Standard deviation across identical runs is zero for all ticks.

        Intent:
            Confirm the variance (and hence std) collapses to zero when all
            runs are exactly identical.

        Preconditions:
            - 3 runs, 5 ticks, flora_population=10, herbivore_population=3.

        Invariants Tested:
            - All values in flora_population_std are < 1e-6.
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        runs = [_make_rows(5, 10, 3) for _ in range(3)]
        agg = aggregate_batch_telemetry(runs)
        for v in agg["flora_population_std"]:
            assert abs(v) < 1e-6

    def test_extinction_probability_all_zero(self) -> None:
        """Extinction probability is 0.0 when no run ever hits flora_population == 0.

        Intent:
            Verify the extinction probability counter remains at zero when
            flora populations stay positive throughout.

        Preconditions:
            - 4 runs, flora_population=10 (never zero).

        Invariants Tested:
            - agg["extinction_probability"] == 0.0.
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        runs = [_make_rows(5, 10, 3) for _ in range(4)]
        agg = aggregate_batch_telemetry(runs)
        assert agg["extinction_probability"] == 0.0

    def test_extinction_probability_all_extinct(self) -> None:
        """Extinction probability is 1.0 when every run hits flora_population == 0.

        Intent:
            Verify the counter saturates to 1.0 when all runs reach zero flora.

        Preconditions:
            - 3 runs, flora_population=0 throughout.

        Invariants Tested:
            - agg["extinction_probability"] == 1.0.
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        runs = [_make_rows(5, 0, 0) for _ in range(3)]
        agg = aggregate_batch_telemetry(runs)
        assert agg["extinction_probability"] == 1.0

    def test_ticks_padded_to_maximum(self) -> None:
        """Aggregate ticks are padded to the longest run (max-length padding).

        Intent:
            Confirm runs with different lengths are padded so the output tick
            array has the length of the longest run.

        Preconditions:
            - One run with 3 ticks and one with 5 ticks, same flora/herbivore values.

        Invariants Tested:
            - len(agg["ticks"]) == 5.
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        runs = [_make_rows(3, 5, 2), _make_rows(5, 5, 2)]
        agg = aggregate_batch_telemetry(runs)
        assert len(agg["ticks"]) == 5

    def test_empty_input_returns_empty(self) -> None:
        """An empty per_run list returns an empty aggregate dict.

        Intent:
            Verify the function handles empty input gracefully.

        Preconditions:
            - Empty list passed as per_run.

        Invariants Tested:
            - agg == {}.
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        agg = aggregate_batch_telemetry([])
        assert agg == {}

    def test_per_species_means_computed(self) -> None:
        """Per-species population means are present in the aggregate output.

        Intent:
            Confirm that per-flora and per-swarm species breakdowns are computed
            and accessible by string species ID key.

        Preconditions:
            - 2 runs, 4 ticks, flora_population=8, herbivore_population=2.

        Invariants Tested:
            - "per_flora_pop_mean" in agg.
            - "0" in agg["per_flora_pop_mean"].
            - agg["per_flora_pop_mean"]["0"][0] == 8.0.
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        runs = [_make_rows(4, 8, 2) for _ in range(2)]
        agg = aggregate_batch_telemetry(runs)
        assert "per_flora_pop_mean" in agg
        assert "0" in agg["per_flora_pop_mean"]
        assert abs(agg["per_flora_pop_mean"]["0"][0] - 8.0) < 1e-6

    def test_survival_probability_curve_present(self) -> None:
        """Aggregate output includes per-tick survival fractions across runs.

        Intent:
            Verify the survival probability curve is emitted and all values
            are 1.0 when no run goes extinct.

        Preconditions:
            - 2 runs, 4 ticks, flora_population=8 (never zero).

        Invariants Tested:
            - "survival_probability_curve" in agg.
            - agg["survival_probability_curve"] == [1.0, 1.0, 1.0, 1.0].
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        runs = [_make_rows(4, 8, 2), _make_rows(4, 8, 2)]
        agg = aggregate_batch_telemetry(runs)
        assert "survival_probability_curve" in agg
        assert agg["survival_probability_curve"] == [1.0, 1.0, 1.0, 1.0]

    def test_survival_probability_curve_monotonic_for_terminal_extinction(self) -> None:
        """Survival curve decreases when a run reaches terminal flora extinction.

        Intent:
            Confirm the curve drops at the tick where one out of two runs
            goes permanently extinct, and stays flat thereafter.

        Preconditions:
            - One alive run (flora=6, 4 ticks) and one extinct run (flora=0 at tick 1).

        Invariants Tested:
            - survival_probability_curve == [1.0, 0.5, 0.5, 0.5].
        """
        from phids.engine.batch.aggregation import aggregate_batch_telemetry

        alive = _make_rows(4, 6, 2)
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

    Intent:
        Verify the batch export path normalizes non-finite floats (NaN, Inf, -Inf)
        to None recursively, ensuring ``json.dumps(..., allow_nan=False)`` succeeds.

    Preconditions:
        - Input dict with scalar NaN, nested NumPy NaN, and list with Inf/-Inf.

    Invariants Tested:
        - sanitized["scalar_nan"] is None.
        - sanitized["nested"]["np_nan"] is None.
        - sanitized["nested"]["arr"] == [1.0, None, None].
        - json.dumps(sanitized, allow_nan=False) does not raise.
    """
    from phids.engine.batch.utils import _sanitize_for_json

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

    json.dumps(sanitized, allow_nan=False)
