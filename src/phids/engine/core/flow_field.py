# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Flow-field gradient generation accelerated with Numba ``@njit`` for deterministic ecological simulation.

Decomposed into the modular :mod:`phids.engine.core.flow` package.
This module serves as the backwards-compatible public facade re-exporting all
solver kernels, stencils, boundary relaxations, and public entry points.
"""

from __future__ import annotations

from phids.engine.core.flow import (
    NUMBA_PARALLEL_THRESHOLD_CELLS,
    _compute_flow_field,
    _compute_flow_field_impl,
    _init_base_and_current_jit,
    _propagate_boundaries_jit,
    _propagate_boundaries_jit_pow2,
    _propagate_inner_jit,
    _propagate_iteration_jit,
    _propagate_iteration_jit_parallel,
    _propagate_iteration_jit_pow2,
    _propagate_iteration_jit_pow2_parallel,
    _run_pow2_parallel,
    _run_pow2_serial,
    _run_standard_parallel,
    _run_standard_serial,
    _sum_neighbours_jit,
    _sum_neighbours_jit_pow2,
    _truncate_subnormals_jit,
    _update_boundary_x_jit,
    _update_boundary_x_jit_pow2,
    _update_boundary_y_jit,
    _update_boundary_y_jit_pow2,
    apply_camouflage,
    compute_flow_field,
)

__all__ = [
    "NUMBA_PARALLEL_THRESHOLD_CELLS",
    "_compute_flow_field",
    "_compute_flow_field_impl",
    "_init_base_and_current_jit",
    "_propagate_boundaries_jit",
    "_propagate_boundaries_jit_pow2",
    "_propagate_inner_jit",
    "_propagate_iteration_jit",
    "_propagate_iteration_jit_parallel",
    "_propagate_iteration_jit_pow2",
    "_propagate_iteration_jit_pow2_parallel",
    "_run_pow2_parallel",
    "_run_pow2_serial",
    "_run_standard_parallel",
    "_run_standard_serial",
    "_sum_neighbours_jit",
    "_sum_neighbours_jit_pow2",
    "_truncate_subnormals_jit",
    "_update_boundary_x_jit",
    "_update_boundary_x_jit_pow2",
    "_update_boundary_y_jit",
    "_update_boundary_y_jit_pow2",
    "apply_camouflage",
    "compute_flow_field",
]
