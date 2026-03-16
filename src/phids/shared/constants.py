"""Shared compile-time constants for the PHIDS simulation engine.

This module centralises all numeric sentinels, hard upper limits, and physical simulation
parameters that must remain consistent across the engine core, API schemas, and telemetry
sub-packages. The Rule-of-16 caps (``MAX_FLORA_SPECIES``, ``MAX_PREDATOR_SPECIES``,
``MAX_SUBSTANCE_TYPES``) govern the maximum cardinality of pre-allocated NumPy matrices in the
``GridEnvironment`` and ECS world; exceeding these limits during scenario construction is
intercepted by Pydantic validation at the API ingress boundary and is never permitted to reach
the engine simulation loop. Grid dimension bounds (``GRID_W_MAX``, ``GRID_H_MAX``) define the
maximum spatial extent of the biotope, constraining convolution and Jacobi propagation cost.

The diffusion constants ``SIGNAL_EPSILON`` and ``SIGNAL_DECAY_FACTOR`` are performance
invariants: after each Gaussian diffusion step, values below ``SIGNAL_EPSILON`` are zeroed to
maintain matrix sparsity and avoid accumulation of subnormal floating-point values that would
degrade Numba JIT-compiled kernel throughput. ``SUBSTANCE_EMIT_RATE`` controls the per-tick
concentration increment applied to signal and toxin layers when an active ``SubstanceComponent``
emits into the environment.
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
