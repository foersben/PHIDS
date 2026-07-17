"""Tests for the DSE Task Manager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from phids.api.schemas import SimulationConfig
from phids.api.services.dse.task_manager import DSETaskManager


@pytest.fixture
def mock_ws_manager() -> MagicMock:
    """Provide a mock websocket manager."""
    manager = MagicMock()
    manager.broadcast_dse = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_dse_task_manager_start_and_stop(mock_ws_manager: MagicMock) -> None:
    """Test starting and stopping the DSE optimization background thread."""
    task_manager = DSETaskManager(mock_ws_manager)
    config = MagicMock(spec=SimulationConfig)

    with patch("phids.api.services.dse.task_manager.DSEOptimizer") as mock_optimizer:
        mock_opt_instance = mock_optimizer.return_value

        # Start
        task_manager.start_dse_task(config)

        assert task_manager._main_loop is not None
        assert task_manager._active_task is not None
        assert task_manager._cancel_event is not None
        assert not task_manager._cancel_event.is_set()

        # Ensure thread starts and optimizer is run
        await asyncio.sleep(0.1)  # Let the background thread reach the run call
        mock_opt_instance.run.assert_called_once()

        # Stop
        task_manager.stop_dse_task()
        assert task_manager._cancel_event.is_set()


@pytest.mark.asyncio
async def test_dse_task_manager_broadcast(mock_ws_manager: MagicMock) -> None:
    """Test that DSE payloads are safely broadcasted to the main thread loop."""
    task_manager = DSETaskManager(mock_ws_manager)
    task_manager._main_loop = asyncio.get_running_loop()

    callback = task_manager._broadcast_payload()

    payload = {"generation": 1}
    configs = [MagicMock(spec=SimulationConfig)]

    # Run callback synchronously as it would be from the thread
    callback(payload, configs)

    # Wait a bit for the threadsafe call to be executed by the loop
    await asyncio.sleep(0.1)

    mock_ws_manager.broadcast_dse.assert_called_once_with(payload)
    assert task_manager.pareto_cache == configs
