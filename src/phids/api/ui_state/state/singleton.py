# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Singleton management for the active draft state."""

from __future__ import annotations

import logging

from phids.api.ui_state.state.models import DraftState
from phids.api.ui_state.state.persistence import _DRAFT_AUTOSAVE_PATH, persist_draft, restore_draft

logger = logging.getLogger(__name__)

# Module-level singleton
_draft: DraftState | None = None


def get_draft() -> DraftState:
    """Return the current draft state, restoring from autosave or defaulting if needed.

    On first access after a process restart, the function attempts to reload the
    previously persisted draft from ``data/draft_autosave.json`` before falling
    back to the built-in default scenario. This makes the draft survive uvicorn
    hot-reloads triggered by source-file edits.

    Returns:
        DraftState: The active draft configuration.
    """
    global _draft
    if _draft is None:
        _draft = restore_draft()
        if _draft is None:
            _draft = DraftState.default()
            logger.info("Draft state initialised with built-in default scenario")
    return _draft


def set_draft(state: DraftState) -> None:
    """Replace the active draft state and persist it to disk.

    Args:
        state: New :class:`DraftState` to activate.
    """
    global _draft
    _draft = state
    logger.info(
        "Draft state replaced (scenario_name=%s, flora=%d, herbivores=%d, substances=%d)",
        state.scenario_name,
        len(state.flora_species),
        len(state.herbivore_species),
        len(state.substance_definitions),
    )
    persist_draft(state)


def reset_draft() -> None:
    """Reset the draft state to the built-in default and remove the autosave file."""
    global _draft
    _draft = DraftState.default()
    logger.info("Draft state reset to built-in default scenario")
    if _DRAFT_AUTOSAVE_PATH.exists():
        try:
            _DRAFT_AUTOSAVE_PATH.unlink()
        except OSError as exc:
            logger.warning("Could not remove draft autosave %s: %s", _DRAFT_AUTOSAVE_PATH, exc)
