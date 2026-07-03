import asyncio
from unittest.mock import MagicMock, patch

import pytest
from deap import creator
from pydantic import ValidationError

from phids.analytics.bio_database import BioDatabase
from phids.analytics.dse_genotype import StructuralGenes
from phids.analytics.dse_optimizer import DSEOptimizer
from phids.api.schemas import UniformPlacement
from phids.api.services.dse_service import DSETaskManager


def test_bio_database_operations():
    """Verify Mode A matching and Mode B bounding bounds operations in BioDatabase."""
    db = BioDatabase()

    # Mode A match flora
    flora_match = db.mode_a_match_flora([0.15, 20.0, 5.0])
    assert flora_match == "Trifolium repens"

    # Mode A match herbivore
    herb_match = db.mode_a_match_herbivore([0.1, 50.0])
    assert herb_match == "Odocoileus virginianus"

    # Mode B bounds flora
    flora_bounds = db.mode_b_get_bounds_flora("Trifolium repens")
    assert "growth_rate" in flora_bounds
    assert flora_bounds["growth_rate"][0] >= 1e-4  # Ensure clamping

    # Mode B bounds herbivore
    herb_bounds = db.mode_b_get_bounds_herbivore("Odocoileus virginianus")
    assert "metabolism_upkeep" in herb_bounds
    assert herb_bounds["metabolism_upkeep"][0] >= 1e-4

    with pytest.raises(ValueError):
        db.mode_b_get_bounds_flora("NonExistent")
    with pytest.raises(ValueError):
        db.mode_b_get_bounds_herbivore("NonExistent")


def test_dse_genotype_rule_of_16():
    """Verify that matrices exceeding 16x16 are strictly rejected by StructuralGenes validator."""
    valid_matrix = [[True] * 16] * 16
    invalid_matrix = [[True] * 17] * 16

    # Valid
    StructuralGenes(
        flora_placement=UniformPlacement(density=0.1),
        herbivore_placement=UniformPlacement(density=0.1),
        diet_matrix=valid_matrix,
        trigger_matrix=[[0] * 16] * 16,
    )

    # Invalid
    with pytest.raises(ValidationError):
        StructuralGenes(
            flora_placement=UniformPlacement(density=0.1),
            herbivore_placement=UniformPlacement(density=0.1),
            diet_matrix=invalid_matrix,
            trigger_matrix=[[0] * 16] * 16,
        )


@pytest.mark.asyncio
async def test_dse_optimizer_evaluation(config_builder):
    """Verify that evaluate_candidate executes headless simulations correctly and returns a fitness tuple."""
    config = config_builder(max_ticks=2)
    optimizer = DSEOptimizer(base_config=config, pop_size=2, generations=1)

    # Mock individual genotype
    ind = creator.Individual([0.5] * 10)

    # Test evaluate with None genotype (should run base_config)
    ind.genotype = None
    fitness = await optimizer.evaluate_candidate(ind)
    assert len(fitness) == 3
    assert fitness[0] >= 0.0


@pytest.mark.asyncio
async def test_dse_task_manager_lifecycle(config_builder):
    """Verify starting and stopping a DSE background task manages threading.Event triggers correctly."""
    ws_manager = MagicMock()
    manager = DSETaskManager(websocket_manager=ws_manager)

    config = config_builder(max_ticks=2)

    # Verify starting and stopping task doesn't raise exceptions
    with patch("phids.api.services.dse_service.DSEOptimizer") as mock_optimizer_class:
        mock_opt = MagicMock()
        mock_optimizer_class.return_value = mock_opt

        manager.start_dse_task(config)
        assert manager._active_task is not None

        manager.stop_dse_task()
        assert manager._cancel_event.is_set()

        try:
            await manager._active_task
        except Exception:
            pass


def test_dse_task_manager_callback():
    """Verify the task manager schedules websocket broadcasts thread-safely onto the running asyncio event loop."""
    ws_manager = MagicMock()
    manager = DSETaskManager(websocket_manager=ws_manager)

    loop = asyncio.get_event_loop()

    # Mock the running loop to be current event loop
    with patch("asyncio.get_running_loop", return_value=loop):
        callback = manager._broadcast_payload()

        # Calling callback schedules task on the loop
        with patch("asyncio.run_coroutine_threadsafe") as mock_run_safe:
            callback({"test": "data"})
            mock_run_safe.assert_called_once()
