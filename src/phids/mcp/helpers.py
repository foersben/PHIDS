# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Internal serialization helpers and dynamic dispatchers for MCP tools.

Provides draft serialization to JSON, dynamic lookup for active simulation loops,
recent log ring buffers, project root paths, and external command execution with
built-in support for test monkeypatching.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from phids.api.ui_state.state import get_draft
from phids.shared.logging_config import get_recent_logs

if TYPE_CHECKING:
    from phids.api.ui_state.state import DraftState

# Resolved at import time: src/phids/mcp/helpers.py -> parents[0]=mcp, [1]=phids, [2]=src, [3]=PHIDS
_DEFAULT_PROJECT_ROOT: Path = Path(__file__).parents[3]
_PROJECT_ROOT: Path = _DEFAULT_PROJECT_ROOT


def get_project_root() -> Path:
    """Resolve the active project root directory dynamically.

    Returns:
        Path: Filesystem path to the root of the PHIDS workspace.
    """
    return _PROJECT_ROOT


def get_active_sim_loop() -> Any | None:
    """Safely return the active live SimulationLoop instance if loaded under FastAPI.

    Returns:
        Any | None: Active SimulationLoop instance or None if not initialized.
    """
    try:
        from phids.api import main as api_main

        return getattr(api_main, "_sim_loop", None)
    except (ImportError, AttributeError):
        return None


def get_current_draft() -> DraftState:
    """Resolve the active draft state dynamically.

    Returns:
        DraftState: Active configuration draft state instance.
    """
    return get_draft()


def get_logs(limit: int = 80) -> list[dict[str, str]]:
    """Resolve recent diagnostic logs dynamically.

    Args:
        limit: Maximum number of structured log records to retrieve.

    Returns:
        list[dict[str, str]]: List of structured diagnostic log records.
    """
    return get_recent_logs(limit=limit)


def run_subprocess(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """Execute a subprocess command dynamically with test patching support.

    Args:
        *args: Positional arguments forwarded to `subprocess.run`.
        **kwargs: Keyword arguments forwarded to `subprocess.run`.

    Returns:
        subprocess.CompletedProcess[Any]: Result of the command invocation.
    """
    return subprocess.run(*args, **kwargs)


def _draft_to_json(draft: DraftState) -> str:
    """Serialize a mixed dataclass/Pydantic DraftState tree to JSON.

    ``DraftState`` is a stdlib dataclass whose list fields contain a mix of
    further stdlib dataclasses (``TriggerRule``, ``PlacedPlant``, ...) and Pydantic
    models (``FloraSpeciesParams``, ``HerbivoreSpeciesParams``, ``BatchJobState``).
    ``dataclasses.asdict`` handles the dataclass hierarchy but copies Pydantic
    models verbatim; the ``_default`` hook converts those during JSON encoding.

    Args:
        draft: The active :class:`~phids.api.ui_state.state.DraftState` instance.

    Returns:
        str: Indented JSON string suitable for agent consumption.

    Raises:
        TypeError: If an object within the tree is not JSON serializable.
    """

    def _default(obj: object) -> Any:
        if hasattr(obj, "model_dump"):
            return cast("Any", obj).model_dump()
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")

    return json.dumps(dataclasses.asdict(draft), indent=2, default=_default)
