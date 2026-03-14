"""Shared constants for PHIDS.

This module defines compile-time limits (Rule of 16), grid bounds and
other numeric sentinel values used across the codebase.
"""

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
SIGNAL_DECAY_FACTOR: float = 0.85  # per-tick airborne signal retention after diffusion

# ---------------------------------------------------------------------------
# Misc numeric sentinels
# ---------------------------------------------------------------------------
EMPTY_CELL: int = -1
MAX_TELEMETRY_TICKS: int = 10_000

# ---------------------------------------------------------------------------
# Substance emission / dissipation rates
# ---------------------------------------------------------------------------
SUBSTANCE_EMIT_RATE: float = 0.1  # concentration added per tick when active
