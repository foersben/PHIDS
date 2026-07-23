# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""DSE background task manager.

Manages running, cancelling, and streaming live progress metrics from the Design Space
Exploration (DSE) genetic algorithm task in a non-blocking background worker thread.
"""

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from phids.analytics.dse_optimizer import DSEOptimizer
from phids.api.schemas.simulation import SimulationConfig

if TYPE_CHECKING:
    from phids.api.websockets.manager import DSEStreamManager

logger = logging.getLogger(__name__)


class DSETaskManager:
    """Manages the background execution of the DSE Optimizer.

    Attributes:
        websocket_manager: The websocket manager instance used to broadcast generation progress.
        pareto_cache: Cache of the current Pareto front candidate configs.

    """

    def __init__(self, websocket_manager: "DSEStreamManager") -> None:
        """Initialize the DSE Task Manager.

        Args:
            websocket_manager: WS stream manager for DSE metrics.

        """
        self.websocket_manager = websocket_manager
        self._active_task: asyncio.Task[Any] | None = None
        self._cancel_event: threading.Event | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self.pareto_cache: list[SimulationConfig] = []

    def _broadcast_payload(self) -> Callable[[dict[str, Any], list[SimulationConfig]], None]:
        """Create a synchronous closure that safely schedules the broadcast on the main event loop.

        Returns:
            A callback closure matching the DSE optimizer callback interface.

        """

        def callback(payload: dict[str, Any], configs: list[SimulationConfig]) -> None:
            self.pareto_cache = configs
            if self._main_loop is not None:
                asyncio.run_coroutine_threadsafe(self.websocket_manager.broadcast_dse(payload), self._main_loop)

        return callback

    def start_dse_task(self, config: SimulationConfig) -> None:
        """Start the DSE optimization in a background thread.

        Args:
            config: Base simulation config blueprint.

        """
        if self._active_task is not None and not self._active_task.done():
            logger.warning("Attempted to start DSE task, but one is already running.")
            return

        self._main_loop = asyncio.get_running_loop()
        self._cancel_event = threading.Event()

        optimizer = DSEOptimizer(base_config=config)

        def _run_optimizer() -> None:
            try:
                # Run the CPU-bound optimizer with the sync callback hook
                optimizer.run(
                    sync_callback=self._broadcast_payload(),
                    cancel_event=self._cancel_event,
                )
            except Exception:
                logger.exception("DSE Optimizer task failed.")

        # Run in a separate thread so we don't block the FastAPI event loop
        self._active_task = asyncio.create_task(asyncio.to_thread(_run_optimizer))
        logger.info("DSE background task started.")

    def stop_dse_task(self) -> None:
        """Gracefully stop the DSE optimization."""
        if self._cancel_event:
            self._cancel_event.set()

        # We don't cancel the task directly as it runs in a thread
        # Setting the event allows the optimizer loop to break gracefully

        self._active_task = None
        logger.info("DSE background task stop requested.")


# Create a global singleton instance (requires init with WS manager later)
dse_task_manager: DSETaskManager | None = None


def get_dse_manager(ws_manager: "DSEStreamManager") -> DSETaskManager:
    """Return the global DSE Task Manager.

    Args:
        ws_manager: The websocket manager to initialize with.

    Returns:
        The singleton DSETaskManager instance.

    """
    global dse_task_manager
    if dse_task_manager is None:
        dse_task_manager = DSETaskManager(ws_manager)
    return dse_task_manager
