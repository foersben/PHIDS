"""Shared constants for PHIDS – Rule of 16 and grid bounds."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Rule of 16 – hard upper limits for pre-allocated matrices
# ---------------------------------------------------------------------------
MAX_FLORA_SPECIES: int = 16
MAX_PREDATOR_SPECIES: int = 16
MAX_SUBSTANCE_TYPES: int = 16

# ---------------------------------------------------------------------------
# Grid constraints
# ---------------------------------------------------------------------------
GRID_W_MAX: int = 80
GRID_H_MAX: int = 80

# ---------------------------------------------------------------------------
# Diffusion / CA constants
# ---------------------------------------------------------------------------
SIGNAL_EPSILON: float = 1e-4  # values below this are zeroed after convolution

# ---------------------------------------------------------------------------
# Misc numeric sentinels
# ---------------------------------------------------------------------------
EMPTY_CELL: int = -1
