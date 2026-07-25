# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the hyperparameter tuning module.

Mocks the differential evolution and process pool executors to
verify the optimization bounds mapping and evaluation logic without overhead.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from phids.analytics.tuning import TrophicOptimizer
from phids.api.ui_state import DraftState


@pytest.fixture
def base_blueprint() -> dict:
    """Provide a base valid scenario configuration."""
    return DraftState.default().build_sim_config().model_dump()


def test_trophic_optimizer_init(base_blueprint: dict) -> None:
    """Test that optimizer bounds and parameters map correctly."""
    opt = TrophicOptimizer(base_blueprint, runs_per_eval=2, max_ticks=10)
    assert len(opt.bounds) > 0
    assert len(opt.param_mapping) == len(opt.bounds)


@patch("phids.analytics.tuning.differential_evolution")
def test_trophic_optimizer_optimize(mock_de: MagicMock, base_blueprint: dict) -> None:
    """Verify that the optimization loop calls the scipy optimizer and applies params."""
    opt = TrophicOptimizer(base_blueprint, runs_per_eval=2, max_ticks=10)

    mock_result = MagicMock()
    mock_result.x = np.ones(len(opt.bounds))
    mock_result.fun = 10.5
    mock_de.return_value = mock_result

    best_config = opt.optimize()
    assert mock_de.called
    assert best_config is not None

    category, idx, key = opt.param_mapping[0]
    assert best_config[category][idx][key] == 1.0


@patch("phids.analytics.tuning.concurrent.futures.ProcessPoolExecutor")
def test_trophic_optimizer_evaluate(mock_executor: MagicMock, base_blueprint: dict) -> None:
    """Verify the fitness evaluation calculates metrics over a batch of mock runs."""
    opt = TrophicOptimizer(base_blueprint, runs_per_eval=2, max_ticks=10)

    mock_pool = MagicMock()
    mock_executor.return_value.__enter__.return_value = mock_pool

    dummy_telemetry = [
        {"tick": 0, "flora_population": 100, "herbivore_population": 50},
        {"tick": 9, "flora_population": 80, "herbivore_population": 60},
    ]
    mock_pool.map.return_value = [dummy_telemetry, dummy_telemetry]

    score = opt._evaluate(np.ones(len(opt.bounds)))

    assert isinstance(score, float)
    assert mock_pool.map.called
