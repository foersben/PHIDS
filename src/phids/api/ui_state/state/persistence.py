# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Persistence helpers for draft configuration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from phids.api.ui_state.state.convert import build_sim_config, from_sim_config

if TYPE_CHECKING:
    from phids.api.ui_state.state.models import DraftState

logger = logging.getLogger(__name__)

# Draft persistence path (outside src/ so watchfiles ignores it)
_DRAFT_AUTOSAVE_PATH: Path = Path("data") / "draft_autosave.json"


def persist_draft(state: DraftState) -> None:
    """Write the draft to ``data/draft_autosave.json`` for hot-reload survival.

    Silently skips if the draft cannot be serialized (e.g. incomplete species list).

    Args:
        state: The draft state to persist.
    """
    try:
        config = build_sim_config(state)
    except ValueError:
        # Draft is incomplete (e.g. no species yet) - skip persistence.
        return
    try:
        _DRAFT_AUTOSAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DRAFT_AUTOSAVE_PATH.write_text(
            config.model_dump_json(indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not persist draft to %s: %s", _DRAFT_AUTOSAVE_PATH, exc)


def restore_draft() -> DraftState | None:
    """Attempt to load a draft from ``data/draft_autosave.json``.

    Returns:
        Restored :class:`DraftState` if the file exists and is valid, otherwise ``None``.
    """
    from phids.api.schemas.simulation import SimulationConfig

    if not _DRAFT_AUTOSAVE_PATH.exists():
        return None
    try:
        raw = _DRAFT_AUTOSAVE_PATH.read_text(encoding="utf-8")
        config = SimulationConfig.model_validate_json(raw)
        state = from_sim_config(config, scenario_name="autosaved")
        logger.info(
            "Draft state restored from autosave %s (grid=%dx%d, flora=%d, herbivores=%d)",
            _DRAFT_AUTOSAVE_PATH,
            config.grid_width,
            config.grid_height,
            len(config.flora_species),
            len(config.herbivore_species),
        )
        return state
    except Exception as exc:
        logger.warning(
            "Draft autosave at %s could not be loaded (%s) - falling back to default.",
            _DRAFT_AUTOSAVE_PATH,
            exc,
        )
        return None
