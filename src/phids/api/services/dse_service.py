import asyncio
import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from phids.analytics.dse_optimizer import DSEOptimizer
from phids.api.schemas import SimulationConfig

if TYPE_CHECKING:
    from phids.api.websockets.manager import DSEStreamManager

logger = logging.getLogger(__name__)


class DSETaskManager:
    """Manages the background execution of the DSE Optimizer."""

    def __init__(self, websocket_manager: "DSEStreamManager") -> None:
        """Initialize the DSE Task Manager."""
        self.websocket_manager = websocket_manager
        self._active_task: asyncio.Task[Any] | None = None
        self._cancel_event: threading.Event | None = None
        self.pareto_cache: list[SimulationConfig] = []

    def _broadcast_payload(self) -> Callable[[dict[str, Any], list[SimulationConfig]], None]:
        """Create a synchronous closure that safely schedules the broadcast on the main event loop."""
        main_loop = asyncio.get_running_loop()

        def callback(payload: dict[str, Any], configs: list[SimulationConfig]) -> None:
            self.pareto_cache = configs
            asyncio.run_coroutine_threadsafe(self.websocket_manager.broadcast_dse(payload), main_loop)

        return callback

    def start_dse_task(self, config: SimulationConfig) -> None:
        """Start the DSE optimization in a background thread."""
        if self._active_task is not None and not self._active_task.done():
            logger.warning("Attempted to start DSE task, but one is already running.")
            return

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
    """Return the global DSE Task Manager."""
    global dse_task_manager
    if dse_task_manager is None:
        dse_task_manager = DSETaskManager(ws_manager)
    return dse_task_manager
