# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Server-side draft state model for the HTMX scenario-builder UI in PHIDS.

This module exposes the canonical :class:`DraftState` model, along with singleton
management functions (``get_draft``, ``set_draft``, ``reset_draft``) necessary to
power the builder UI state across multiple requests and API routers.

The internal logic is strictly divided:
- ``models.py`` holds the core dataclass and field schemas.
- ``convert.py`` encapsulates translation back and forth from engine ``SimulationConfig``.
- ``persistence.py`` manages autosave IO logic safely outside the watchfiles path.
- ``singleton.py`` provides the global active draft instance tracking.
"""

from __future__ import annotations

from phids.api.ui_state.state.models import DraftState
from phids.api.ui_state.state.singleton import get_draft, reset_draft, set_draft

__all__ = [
    "DraftState",
    "get_draft",
    "reset_draft",
    "set_draft",
]
