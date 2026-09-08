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
import sys
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
    mod = sys.modules.get("phids.mcp_server")
    if mod:
        val = getattr(mod, "_PROJECT_ROOT", None)
        if val is not None:
            return cast("Path", val)
    return _DEFAULT_PROJECT_ROOT


def _default_get_active_sim_loop() -> Any | None:
    """Safely return the active live SimulationLoop instance if loaded under FastAPI.

    Returns:
        Any | None: Active SimulationLoop instance or None if not initialized.
    """
    try:
        from phids.api import main as api_main

        return getattr(api_main, "_sim_loop", None)
    except (ImportError, AttributeError):
        return None


def get_active_sim_loop() -> Any | None:
    """Resolve the active live SimulationLoop instance dynamically.

    Checks `phids.mcp_server._get_active_sim_loop` first to honor test patches.

    Returns:
        Any | None: The active simulation loop instance or None.
    """
    mod = sys.modules.get("phids.mcp_server")
    if mod:
        fn = getattr(mod, "_get_active_sim_loop", None)
        if callable(fn):
            return fn()
    return _default_get_active_sim_loop()


def get_current_draft() -> DraftState:
    """Resolve the active draft state dynamically.

    Returns:
        DraftState: Active configuration draft state instance.
    """
    mod = sys.modules.get("phids.mcp_server")
    if mod:
        fn = getattr(mod, "get_draft", None)
        if callable(fn):
            return cast("DraftState", fn())
    return get_draft()


def get_logs(limit: int = 80) -> list[dict[str, str]]:
    """Resolve recent diagnostic logs dynamically.

    Args:
        limit: Maximum number of structured log records to retrieve.

    Returns:
        list[dict[str, str]]: List of structured diagnostic log records.
    """
    mod = sys.modules.get("phids.mcp_server")
    if mod:
        fn = getattr(mod, "get_recent_logs", None)
        if callable(fn):
            return cast("list[dict[str, str]]", fn(limit=limit))
    return get_recent_logs(limit=limit)


def run_subprocess(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """Execute a subprocess command dynamically with test patching support.

    Args:
        *args: Positional arguments forwarded to `subprocess.run`.
        **kwargs: Keyword arguments forwarded to `subprocess.run`.

    Returns:
        subprocess.CompletedProcess[Any]: Result of the command invocation.
    """
    mod = sys.modules.get("phids.mcp_server")
    if mod:
        sub_mod = getattr(mod, "subprocess", None)
        if sub_mod and hasattr(sub_mod, "run"):
            return cast("subprocess.CompletedProcess[Any]", sub_mod.run(*args, **kwargs))
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
