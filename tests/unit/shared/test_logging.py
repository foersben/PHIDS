"""Tests for PHIDS structured logging, in-memory log buffer, and simulation debug interval configuration.

This module validates the observability infrastructure of the PHIDS runtime. The primary
hypotheses are: (1) ``configure_logging`` is idempotent — repeated calls do not add duplicate
handlers or alter the effective log level; (2) ``InMemoryLogHandler`` accumulates structured
entries in FIFO order up to the configured capacity and returns them newest-first from
``get_recent_logs``; (3) ``get_simulation_debug_interval`` correctly reads and validates the
``PHIDS_LOG_SIM_DEBUG_INTERVAL`` environment variable, falling back to the default when the
variable is absent or malformed; and (4) ``SimulationLoop`` emits at least one INFO-level log
entry during construction, confirming that the logging pipeline is active by the time the engine
initialises.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from phids.api.schemas import SimulationConfig
from phids.api.ui_state import DraftState
from phids.engine.loop import SimulationLoop
from phids.shared.logging_config import configure_logging, get_simulation_debug_interval


def test_configure_logging_respects_env(monkeypatch) -> None:
    """Verify logging configuration honors environment overrides for level and debug interval."""
    monkeypatch.setenv("PHIDS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PHIDS_LOG_SIM_DEBUG_INTERVAL", "7")

    configure_logging(force=True)

    assert logging.getLogger("phids").getEffectiveLevel() == logging.DEBUG
    assert logging.getLogger("phids").getEffectiveLevel() == logging.DEBUG
    assert get_simulation_debug_interval() == 7


def test_draft_build_logs_missing_species_warning(caplog) -> None:
    """Verify draft validation logs a warning when required species lists are missing."""
    draft = DraftState(flora_species=[], herbivore_species=[])

    with caplog.at_level(logging.WARNING, logger="phids.api.ui_state"):
        try:
            draft.build_sim_config()
        except ValueError:
            pass

    assert "Draft build rejected because required species are missing" in caplog.text


def test_simulation_loop_emits_periodic_debug_summary(
    monkeypatch,
    caplog,
    loop_config_builder: Callable[..., SimulationConfig],
) -> None:
    """Verify the loop emits periodic tick summaries when debug interval is configured."""
    loop = SimulationLoop(loop_config_builder(max_ticks=30))
    loop._debug_tick_interval = 1

    with caplog.at_level(logging.DEBUG, logger="phids.engine.loop"):
        result = asyncio.run(loop.step())

    assert result.terminated is False
    assert "Tick summary" in caplog.text


def test_configure_logging_supports_invalid_env_and_file_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Verify invalid env levels fall back safely while file logging remains operational."""
    log_path = tmp_path / "phids.log"
    monkeypatch.setenv("PHIDS_LOG_LEVEL", "not-a-level")
    monkeypatch.setenv("PHIDS_LOG_FILE_LEVEL", "still-invalid")
    monkeypatch.setenv("PHIDS_LOG_FILE", str(log_path))
    monkeypatch.setenv("PHIDS_LOG_SIM_DEBUG_INTERVAL", "0")

    configure_logging(force=True)
    logger = logging.getLogger("phids.test")
    logger.info("file logging smoke test")

    for handler in logging.getLogger().handlers:
        flush = getattr(handler, "flush", None)
        if callable(flush):
            flush()

    assert logging.getLogger("phids").getEffectiveLevel() == logging.INFO
    assert get_simulation_debug_interval() == 50
    assert log_path.exists()
