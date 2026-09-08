# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Modular flow-field solver and stencil kernels for the PHIDS engine.

Provides finite difference stencils, toroidal boundary propagators, and parallel
Jacobi relaxation solvers for botanical attraction and toxin repellent gradients.
"""

from __future__ import annotations

from phids.engine.core.flow.boundaries import (
    _propagate_boundaries_jit,
    _propagate_boundaries_jit_pow2,
    _propagate_inner_jit,
    _update_boundary_x_jit,
    _update_boundary_x_jit_pow2,
    _update_boundary_y_jit,
    _update_boundary_y_jit_pow2,
)
from phids.engine.core.flow.solvers import (
    NUMBA_PARALLEL_THRESHOLD_CELLS,
    _compute_flow_field,
    _compute_flow_field_impl,
    _propagate_iteration_jit,
    _propagate_iteration_jit_parallel,
    _propagate_iteration_jit_pow2,
    _propagate_iteration_jit_pow2_parallel,
    _run_pow2_parallel,
    _run_pow2_serial,
    _run_standard_parallel,
    _run_standard_serial,
    apply_camouflage,
    compute_flow_field,
)
from phids.engine.core.flow.stencils import (
    _init_base_and_current_jit,
    _sum_neighbours_jit,
    _sum_neighbours_jit_pow2,
    _truncate_subnormals_jit,
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
