# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Shared compile-time constants for the PHIDS simulation engine.

This module centralises all numeric sentinels, hard upper limits, and physical simulation
parameters that must remain consistent across the engine core, API schemas, and telemetry
sub-packages. The Rule-of-16 caps (``MAX_FLORA_SPECIES``, ``MAX_HERBIVORE_SPECIES``,
``MAX_SUBSTANCE_TYPES``) govern the maximum cardinality of pre-allocated NumPy matrices in the
``GridEnvironment`` and ECS world; exceeding these limits during scenario construction is
intercepted by Pydantic validation at the API ingress boundary and is never permitted to reach
the engine simulation loop. Grid dimension bounds (``GRID_W_MAX``, ``GRID_H_MAX``) define the
maximum spatial extent of the biotope, constraining convolution and Jacobi propagation cost.

The diffusion constant ``SIGNAL_EPSILON`` is a performance invariant: after each
Gaussian diffusion step, values below ``SIGNAL_EPSILON`` are zeroed to maintain
matrix sparsity and avoid accumulation of subnormal floating-point values that would
degrade Numba JIT-compiled kernel throughput.

Note: ``SIGNAL_DECAY_FACTOR`` and ``SUBSTANCE_EMIT_RATE`` were intentionally moved to
``SimulationConfig`` to allow dynamic parameter tuning during Design Space Exploration.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Rule of 16 - hard upper limits for pre-allocated matrices
# ---------------------------------------------------------------------------
MAX_FLORA_SPECIES: int = 16
MAX_HERBIVORE_SPECIES: int = 16
MAX_SUBSTANCE_TYPES: int = 16

# ---------------------------------------------------------------------------
# Grid constraints
# ---------------------------------------------------------------------------
GRID_W_MAX: int = 10_000
GRID_H_MAX: int = 10_000

# ---------------------------------------------------------------------------
# Diffusion / CA constants
# ---------------------------------------------------------------------------
SIGNAL_EPSILON: float = 1e-4  # values below this are zeroed after convolution

# ---------------------------------------------------------------------------
# Misc numeric sentinels
# ---------------------------------------------------------------------------
MAX_TELEMETRY_TICKS: int = 10_000
MAX_REPLAY_FRAMES: int = 2_000

# Number of candidate directional choices (current position + 4 cardinal neighbours)
VON_NEUMANN_CHOICE_COUNT: int = 5

# ---------------------------------------------------------------------------
# Seed dispersal defaults (global, species-overridable)
# ---------------------------------------------------------------------------
SEED_DROP_HEIGHT_DEFAULT: float = 1.25
SEED_TERMINAL_VELOCITY_DEFAULT: float = 0.8

# ---------------------------------------------------------------------------
# Substance emission / dissipation rates
# ---------------------------------------------------------------------------
SUBSTANCE_EMIT_RATE: float = 0.1  # concentration added per tick when active

# ---------------------------------------------------------------------------
# Dual-Proxy Architecture defaults (E_current / M_structural)
# ---------------------------------------------------------------------------
# Newly spawned seeds carry zero structural (lignin) mass - they are soft and
# completely vulnerable to trampling. This matches the biological seed stage.
M_STRUCTURAL_SEED_VALUE: float = 0.0

# Fraction of max_energy added to M_structural per slow-tick (168-hour stride).
# This is a global placeholder default. Plan 2 will replace it with a per-species
# value sourced from the empirical bio-database via the EEDSE optimizer.
M_STRUCTURAL_GROWTH_RATE: float = 0.01

# Multiplier for M_structural-scaled maintenance cost deduction per hour.
# Evaluated on the slow-loop cohort interval (SLOW_TICK_STRIDE = 168 hours):
# Upkeep_fee = survival_threshold * STRUCTURAL_UPKEEP_SCALAR * (M_structural / max_M_structural) * SLOW_TICK_STRIDE.
# Calibrated so that full structural mass incurs 0.5 * survival_threshold fee per weekly cohort cycle.
STRUCTURAL_UPKEEP_SCALAR: float = 0.5 / 168.0

# ---------------------------------------------------------------------------
# Multi-Scale Temporal Strides
# ---------------------------------------------------------------------------
MEDIUM_TICK_STRIDE: int = 24  # Hours per diurnal cycle (medium-loop metabolic gating)
SLOW_TICK_STRIDE: int = 168  # Hours per weekly cycle (slow-loop structural growth & mitosis gating)

# ---------------------------------------------------------------------------
# Lifecycle and Growth Conversion Constants
# ---------------------------------------------------------------------------
PERCENTAGE_DIVISOR: float = 100.0  # Scalar divisor converting integer percentage [0, 100] to fractional rate [0.0, 1.0]

# ---------------------------------------------------------------------------
# Anemochorous Seed Dispersal Aerodynamics (Okubo & Levin, 1989)
# ---------------------------------------------------------------------------
# Minimum crosswind standard deviation in meters (prevents degenerate zero-width plume)
MIN_CROSSWIND_DISPERSAL_SIGMA: float = 0.15
# Linear scaling coefficient of lateral plume spread with downwind distance
LATERAL_EDDY_DIFFUSIVITY_COEFFICIENT: float = 0.35

# ---------------------------------------------------------------------------
# Signaling Activation and Translocation Thresholds
# ---------------------------------------------------------------------------
DEFAULT_ACTIVATION_MIN_CONCENTRATION: float = 0.01  # Fallback minimum threshold for environmental trigger activation
DEFAULT_NUTRITION_TARGET: float = 0.1  # Fallback target nutrition factor during induced defense withdrawal
# Minimum cooperativity priming factor required to trigger downstream defense cascade
HILL_PRIMING_THRESHOLD: float = 0.05

# ---------------------------------------------------------------------------
# Heterotrophic Kinematics and Movement Constants
# ---------------------------------------------------------------------------
# Directional preference weight for continuing along current heading (10:1 inertia)
ORTHOKINETIC_MOMENTUM_WEIGHT: float = 10.0
MVT_DEPARTURE_SIGMOID_STEEPNESS: float = 5.0  # Logistic sigmoid steepness parameter k for patch departure probability
TILE_CARRYING_CAPACITY: int = 500  # Default maximum aggregate herbivore individuals permitted per grid tile
MITOSIS_DIVISOR: int = 2  # Binary fission demographic bisection divisor for supercolony fission
# Ticks an herbivore swarm remains repelled following encounter with an incompatible host plant
INCOMPATIBLE_DIET_REPULSION_TICKS: int = 2
