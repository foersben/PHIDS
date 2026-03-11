"""Central logging configuration for PHIDS.

The package uses a single idempotent logging bootstrap so API, UI, engine,
telemetry, and I/O modules share consistent formatting and levels.
Configuration is environment-driven to keep detailed debugging available
without paying for verbose logs by default.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
import logging
import logging.config
import os
from pathlib import Path
from threading import Lock
from typing import Final

_DEFAULT_LOG_LEVEL: Final[str] = "INFO"
_DEFAULT_SIM_DEBUG_INTERVAL: Final[int] = 50
_LOGGER_NAMES: Final[tuple[str, ...]] = ("phids",)
_RECENT_LOG_CAPACITY: Final[int] = 250
_CONFIGURED: bool = False
_RECENT_LOGS: deque[dict[str, str]] = deque(maxlen=_RECENT_LOG_CAPACITY)
_RECENT_LOGS_LOCK: Lock = Lock()


class InMemoryLogHandler(logging.Handler):
    """Capture recent structured log entries for the diagnostics UI."""

    def emit(self, record: logging.LogRecord) -> None:
        """Append one formatted record to the in-memory diagnostics buffer."""
        try:
            message = record.getMessage()
            if record.exc_info:
                exc_text = self.formatException(record.exc_info)
                if exc_text:
                    message = f"{message}\n{exc_text}"
            entry = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "module": record.module,
                "message": message,
            }
            with _RECENT_LOGS_LOCK:
                _RECENT_LOGS.append(entry)
        except Exception:  # pragma: no cover - logging must never fail app code
            self.handleError(record)


def get_recent_logs(*, limit: int = 80) -> list[dict[str, str]]:
    """Return the newest structured PHIDS log entries first.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        list[dict[str, str]]: Structured log entries for diagnostics panels.
    """
    clamped_limit = max(1, limit)
    with _RECENT_LOGS_LOCK:
        return list(reversed(list(_RECENT_LOGS)[-clamped_limit:]))


def _coerce_log_level(value: str | None, *, default: str = _DEFAULT_LOG_LEVEL) -> str:
    """Return a valid logging level name.

    Args:
        value: Raw environment value.
        default: Fallback level name.

    Returns:
        str: Upper-case logging level accepted by ``logging``.
    """
    candidate = (value or default).upper()
    if candidate in logging.getLevelNamesMapping():
        return candidate
    return default


def _coerce_positive_int(value: str | None, *, default: int) -> int:
    """Return a positive integer from a raw environment value.

    Args:
        value: Raw environment value.
        default: Fallback value.

    Returns:
        int: Parsed positive integer or the fallback.
    """
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def get_simulation_debug_interval() -> int:
    """Return the interval used for periodic simulation debug summaries.

    Returns:
        int: Tick interval for DEBUG summaries.
    """
    return _coerce_positive_int(
        os.getenv("PHIDS_LOG_SIM_DEBUG_INTERVAL"),
        default=_DEFAULT_SIM_DEBUG_INTERVAL,
    )


def configure_logging(*, force: bool = False) -> None:
    """Configure PHIDS package logging.

    Environment variables:
        ``PHIDS_LOG_LEVEL``: Package log level (default ``INFO``).
        ``PHIDS_LOG_FILE``: Optional file path for a rotating debug log.
        ``PHIDS_LOG_FILE_LEVEL``: File handler level (default ``DEBUG``).
        ``PHIDS_LOG_SIM_DEBUG_INTERVAL``: Tick interval for engine summaries.

    Args:
        force: Reconfigure logging even if already configured.
    """
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED and not force:
        return

    package_level = _coerce_log_level(os.getenv("PHIDS_LOG_LEVEL"))
    file_level = _coerce_log_level(os.getenv("PHIDS_LOG_FILE_LEVEL"), default="DEBUG")
    log_file = os.getenv("PHIDS_LOG_FILE")

    handlers: dict[str, dict[str, object]] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": package_level,
            "formatter": "standard",
        },
        "memory": {
            "class": "phids.shared.logging_config.InMemoryLogHandler",
            "level": package_level,
        },
    }
    root_handlers = ["console", "memory"]

    if force:
        with _RECENT_LOGS_LOCK:
            _RECENT_LOGS.clear()

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": file_level,
            "formatter": "standard",
            "filename": str(log_path),
            "maxBytes": 2_000_000,
            "backupCount": 3,
            "encoding": "utf-8",
        }
        root_handlers.append("file")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"format": ("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")}
            },
            "handlers": handlers,
            "root": {
                "level": "WARNING",
                "handlers": root_handlers,
            },
            "loggers": {
                logger_name: {
                    "level": package_level,
                    "handlers": [],
                    "propagate": True,
                }
                for logger_name in _LOGGER_NAMES
            },
        }
    )

    _CONFIGURED = True
    logging.getLogger(__name__).debug(
        "Logging configured (package_level=%s, file_logging=%s, sim_debug_interval=%d)",
        package_level,
        bool(log_file),
        get_simulation_debug_interval(),
    )
