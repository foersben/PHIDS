"""Unit tests for the Design Space Exploration (DSE) NSGA-II optimizer.

Verifies fitness sorting and JIT compiler cache pre-warming logic.
"""

from unittest.mock import MagicMock, patch

from deap import creator

from phids.analytics.dse_optimizer import DSEOptimizer
from phids.api.schemas import SimulationConfig


def test_dse_optimizer_fitness_max_sorting() -> None:
    """Verify that DEAP FitnessMax properly sorts (longevity, stability, dispersion) tuples."""
    # We just need to check the creator logic from the module
    ind1 = creator.Individual()
    ind1.fitness.values = (100.0, 0.5, 0.1)  # low longevity

    ind2 = creator.Individual()
    ind2.fitness.values = (500.0, 0.5, 0.1)  # high longevity

    assert ind2.fitness > ind1.fitness


@patch("phids.analytics.dse_optimizer.SimulationLoop")
def test_dse_optimizer_warm_numba_cache(mock_simulation_loop):
    """Verify that _warm_numba_cache executes the 10x10 dummy grid properly."""
    from unittest.mock import AsyncMock

    mock_loop_instance = MagicMock()
    mock_loop_instance.step = AsyncMock()
    mock_simulation_loop.return_value = mock_loop_instance

    base_config = SimulationConfig.model_construct()

    optimizer = DSEOptimizer(base_config=base_config)
    import asyncio

    asyncio.run(optimizer._warm_numba_cache())

    # The loop should be instantiated with a deepcopy of the config modified to 10x10 and 5 ticks
    instantiated_config = mock_simulation_loop.call_args[0][0]
    assert instantiated_config.grid_width == 10
    assert instantiated_config.grid_height == 10
    assert instantiated_config.max_ticks == 5

    assert mock_loop_instance.step.call_count >= 1
